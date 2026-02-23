"""
ダンプから対象ページの Wiki ソースをページごとファイルで出力する。

対象: 架空の人物カテゴリ、○○の登場人物専用ページ、登場人物セクションがある通常ページ。
"""

import json
import sys
from pathlib import Path

from wiki_extract.extract.data_dir import find_dump_optional, require_dumps
from wiki_extract.extract.section_parser import extract_toujo_section
from wiki_extract.extract.sql_categorylinks import run_categorylinks
from wiki_extract.extract.sql_page import run_page
from wiki_extract.extract.xml_stream import stream_pages
from wiki_extract.util.log import format_elapsed, log, log_progress, Timer


def parse_args() -> object:
    """コマンドライン引数。"""
    import argparse
    import os
    _data = os.environ.get('WIKI_DATA_DIR', '').strip() or '/data'
    _out = os.environ.get('WIKI_OUTPUT_DIR', '').strip() or '/out'
    p = argparse.ArgumentParser(description='ダンプから対象ページのWikiソースをページごとファイルで出力する')
    p.add_argument('--data-dir', type=Path, default=Path(_data),
                   help='SQL/XML ダンプを置くディレクトリ。既定: WIKI_DATA_DIR または /data')
    p.add_argument('--output-dir', type=Path, default=Path(_out),
                   help='出力ディレクトリ。既定: WIKI_OUTPUT_DIR または /out。pages/ と page_meta.json をここに作成')
    return p.parse_args()


def main() -> None:
    """エントリポイント。"""
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)

    log('extract-pages: ページごとデータファイルの作成')
    with Timer() as total_timer:
        # 1) ダンプ解決
        log_progress('起動: ダンプ確認', elapsed=total_timer.elapsed)
        cl_path, page_path, xml_path = require_dumps(data_dir)
        log(f'  categorylinks: {cl_path.name}')
        log(f'  page: {page_path.name}')
        log(f'  pages-articles: {xml_path.name}')

        # 2) page ダンプ
        log_progress('page: 読込', elapsed=total_timer.elapsed)
        main_id_to_title, category_id_to_title, toujo_page_ids = run_page(
            page_path, log_progress_fn=True
        )
        log(f'  main pages: {len(main_id_to_title)}, toujo pages: {len(toujo_page_ids)}')

        # 3) categorylinks: 架空の人物の page_ids
        linktarget_path = find_dump_optional(data_dir, 'linktarget')
        if linktarget_path is None:
            log('  linktarget: 未配置（1.45+ の categorylinks の場合は必須。download.ps1 / download.sh で jawiki-latest-linktarget.sql.gz を取得）')
        log_progress('categorylinks: 読込', elapsed=total_timer.elapsed)
        fictional_page_ids = run_categorylinks(
            cl_path, category_id_to_title, linktarget_path=linktarget_path, log_progress_fn=True
        )
        log(f'  fictional_page_ids: {len(fictional_page_ids)}')

        # 対象 = 架空の人物 ∪ 登場人物専用ページ（XML ストリーム時に「登場人物」セクションありも追加）
        target_ids: set[int] = fictional_page_ids | toujo_page_ids

        # 4) 出力ディレクトリ
        pages_dir = output_dir / 'pages'
        pages_dir.mkdir(parents=True, exist_ok=True)

        # 5) XML ストリームで対象ページのみ書き出し
        written = 0
        checked_with_section = 0
        log_progress('xml: ストリーム・ページ書き出し', elapsed=total_timer.elapsed)
        for page_id, ns, text in stream_pages(xml_path):
            if ns != 0:
                continue
            if page_id in target_ids:
                out_path = pages_dir / f'{page_id}.txt'
                out_path.write_text(text, encoding='utf-8')
                written += 1
                continue
            # 登場人物セクションがあるか判定（軽量チェック後で extract_toujo_section）
            if '登場人物' not in text:
                continue
            checked_with_section += 1
            if extract_toujo_section(text) is None:
                continue
            out_path = pages_dir / f'{page_id}.txt'
            out_path.write_text(text, encoding='utf-8')
            written += 1
            if checked_with_section % 10000 == 0 and checked_with_section:
                log_progress('xml: 登場人物セクション確認済み', count=checked_with_section, elapsed=total_timer.elapsed)

        log_progress('xml: 完了', count=written, elapsed=total_timer.elapsed)
        log(f'  書き出しページ数: {written}')

        # 6) page_meta.json（extract-character-candidates で使用）
        page_meta = {
            'main_id_to_title': main_id_to_title,
            'toujo_page_ids': list(toujo_page_ids),
        }
        meta_path = output_dir / 'page_meta.json'
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(page_meta, f, ensure_ascii=False, indent=0)
        log(f'  page_meta.json: {meta_path}')

    log('')
    log(f'  実行時間: {format_elapsed(total_timer.elapsed)} ({total_timer.elapsed:.1f}秒)')
    log(f'  出力: {pages_dir} と {meta_path}')


if __name__ == '__main__':
    main()
    sys.exit(0)
