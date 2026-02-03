"""
メインエントリポイント: ダンプ読込・SQL/XML 処理・出力のオーケストレーション。
"""

import sys
import threading
from queue import Empty, Queue
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, as_completed, wait
from pathlib import Path

from wiki_extract import config
from wiki_extract.character_filter import is_likely_character
from wiki_extract.data_dir import find_dump_optional, require_dumps
from wiki_extract.log import format_elapsed, log, log_progress, Timer
from wiki_extract.sql_categorylinks import run_categorylinks
from wiki_extract.sql_page import run_page
from wiki_extract.xml_stream import stream_pages
from wiki_extract.xml_workers import init_worker, process_page


def main() -> None:
    """パイプライン全体を実行: ダンプ確認、SQL、XML ストリーム、マージ、出力書き出し。"""
    args = config.parse_args()
    data_dir = args.data_dir
    output_dir = args.output_dir
    workers = args.workers
    if workers is None or workers < 1:
        workers = 1

    log('Starting wiki_extract')
    log(f'  workers: {workers}')
    with Timer() as total_timer:
        # 1) ダンプファイルの解決と確認
        log_progress('startup: checking dumps', elapsed=total_timer.elapsed)
        cl_path, page_path, xml_path = require_dumps(data_dir)
        log(f'  categorylinks: {cl_path.name}')
        log(f'  page: {page_path.name}')
        log(f'  pages-articles: {xml_path.name}')

        # 2) page ダンプ: main_id_to_title, category_id_to_title, toujo_page_ids
        log_progress('page: loading', elapsed=total_timer.elapsed)
        main_id_to_title, category_id_to_title, toujo_page_ids = run_page(
            page_path, log_progress_fn=True
        )
        log(f'  main pages: {len(main_id_to_title)}, toujo pages: {len(toujo_page_ids)}')

        # 3) Categorylinks: 架空の人物の page_ids（1.45+ の場合は linktarget 必須）
        linktarget_path = find_dump_optional(data_dir, 'linktarget')
        if linktarget_path is None:
            log('  linktarget: 未配置（1.45+ の categorylinks の場合は必須。download.ps1 / download.sh で jawiki-latest-linktarget.sql.gz を取得）')
        log_progress('categorylinks: loading', elapsed=total_timer.elapsed)
        fictional_page_ids = run_categorylinks(
            cl_path, category_id_to_title, linktarget_path=linktarget_path, log_progress_fn=True
        )

        # 4) SQL から fictional_from_cat を構築（架空は (作品名, キャラ名) のペア。カテゴリ由来は出典を「カテゴリ」に）
        fictional_from_cat: set[tuple[str, str]] = set()
        for pid in fictional_page_ids:
            if pid not in main_id_to_title:
                continue
            name = main_id_to_title[pid]
            if is_likely_character(name):
                fictional_from_cat.add(('カテゴリ', name))
        log_progress(
            'merge: SQL sets',
            count=len(fictional_from_cat),
            elapsed=total_timer.elapsed,
        )

        def work_title_from_page_id(pid: int) -> str:
            """ページ ID から作品名を取得。専用ページなら「の登場人物」を除去。"""
            title = main_id_to_title.get(pid, '')
            if pid in toujo_page_ids:
                t = title.replace('の登場人物一覧', '').replace('の登場人物', '')
                return t.strip('_') or title
            return title

        # 5) XML をストリームし、登場人物ページ/セクションから (作品名, キャラ名) を収集
        # XML 読取は別スレッドでキューに投入し、メインは submit と結果回収に専念
        fictional_from_xml: set[tuple[str, str]] = set()
        page_count = 0
        chunk_size = 5000
        xml_queue: Queue = Queue(maxsize=10000)

        def xml_reader() -> None:
            for page_id, ns, text in stream_pages(xml_path):
                if ns == 0:
                    xml_queue.put((page_id, ns, text))
            xml_queue.put(None)

        log_progress('xml: streaming pages', elapsed=total_timer.elapsed)
        reader_thread = threading.Thread(target=xml_reader)
        reader_thread.start()
        with ProcessPoolExecutor(
            max_workers=workers, initializer=init_worker, initargs=(toujo_page_ids,)
        ) as executor:
            futures: dict = {}  # fut -> page_id の対応
            while True:
                item = xml_queue.get()
                if item is None:
                    break
                page_id, ns, text = item
                page_count += 1
                if page_count % 50000 == 0:
                    log_progress(
                        'xml: pages read',
                        count=page_count,
                        elapsed=total_timer.elapsed,
                    )
                fut = executor.submit(process_page, (page_id, ns, text))
                futures[fut] = page_id
                while len(futures) >= chunk_size:
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for f in done:
                        pid = futures.pop(f)
                        work = work_title_from_page_id(pid)
                        for char in f.result():
                            if is_likely_character(char):
                                fictional_from_xml.add((work, char))
            reader_thread.join()
            for fut in as_completed(futures):
                pid = futures.pop(fut)
                work = work_title_from_page_id(pid)
                for char in fut.result():
                    if is_likely_character(char):
                        fictional_from_xml.add((work, char))

        log_progress(
            'xml: done',
            count=page_count,
            elapsed=total_timer.elapsed,
        )
        log(f'  fictional (work, char) pairs from XML: {len(fictional_from_xml)}')

        fictional_characters = fictional_from_cat | fictional_from_xml

        # 6) 出力書き出し（UTF-8）
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        fic_path = output_dir / 'fictional_characters.tsv'

        # 出力時はアンダースコアをスペースに置換（Wiki検索しやすくする）
        def for_display(s: str) -> str:
            return s.replace('_', ' ')

        log_progress('write: fictional_characters.tsv', elapsed=total_timer.elapsed)
        with open(fic_path, 'w', encoding='utf-8') as f:
            f.write('作品名\tキャラクター名\n')
            for work, char in sorted(fictional_characters):
                f.write(f'{for_display(work)}\t{for_display(char)}\n')

    log_progress(
        'done',
        count=len(fictional_characters),
        elapsed=total_timer.elapsed,
    )
    log('')
    log(f'  実行時間: {format_elapsed(total_timer.elapsed)} ({total_timer.elapsed:.1f}秒)')
    log('')
    log(f'  fictional_characters.tsv: {fic_path}')


if __name__ == '__main__':
    main()
    sys.exit(0)
