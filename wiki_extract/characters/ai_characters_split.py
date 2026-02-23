"""
② ①で作成した対象CSV（characters_target.csv）を読み、LLMで氏名分割して characters.csv を出力する。
"""

import csv
import os
import sys
from pathlib import Path

from wiki_extract.llm.batch_runner import run_llm_batch_loop, stagger_batch_start
from wiki_extract.llm.client import (
    call_llm_chat,
    load_prompt,
    resolve_ollama_chat_url,
    DEFAULT_LLM_SPLIT_BATCH_SIZE,
)
from wiki_extract.llm.parser_common import log_llm_batch_header, log_ollama_connection_refused_hint, make_llm_parser, resolve_llm_options
from wiki_extract.util.csv_util import finalize_output_with_sort, prepare_resume_by_rows
from wiki_extract.util.log import format_elapsed, log, log_progress, Timer
from wiki_extract.util.path_util import progress_path_for, resolve_output_path, validate_input_file


def _get_split_system_prompt() -> str:
    return load_prompt('split_system')


def _get_split_example_input() -> str:
    return load_prompt('split_example_input')


def _get_split_example_output() -> str:
    return load_prompt('split_example_output')


def _call_split_llm(
    provider: str,
    api_url: str,
    model: str,
    user_input: str,
    timeout: int,
    *,
    api_key: str | None = None,
) -> str:
    """共通 LLM で氏名分割用メッセージを組み立てて呼び出す。"""
    return call_llm_chat(
        provider,
        api_url,
        model,
        _get_split_system_prompt(),
        user_input,
        timeout,
        few_shot=[
            {'role': 'user', 'content': _get_split_example_input()},
            {'role': 'assistant', 'content': _get_split_example_output()},
        ],
        api_key=api_key,
    )


def parse_csv_response(response: str) -> list[tuple[str, str, str, bool]]:
    """API の CSV レスポンスから (名前, 姓, 名, 氏名フラグ) のリストを返す。"""
    rows = []
    for line in response.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('名前,'):
            continue
        if ',' not in line:
            continue
        parts = line.split(',', 3)
        name = parts[0].strip() if len(parts) > 0 else ''
        sei = parts[1].strip() if len(parts) > 1 else ''
        mei = parts[2].strip() if len(parts) > 2 else ''
        is_name_raw = parts[3].strip() if len(parts) > 3 else 'True'
        is_name = is_name_raw.lower() == 'true'
        rows.append((name, sei, mei, is_name))
    return rows


def load_input_rows(target_path: Path) -> list[tuple[str, str]]:
    """characters_target.csv を読み、(page_title, name) のリストで返す。行単位でバッチする用。"""
    rows: list[tuple[str, str]] = []
    with open(target_path, encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            page_title, name = row[0].strip(), row[1].strip()
            if not name:
                continue
            rows.append((page_title, name))
    return rows


def _prepare_resume_split(output_path: Path, rows: list[tuple[str, str]], batch_size: int) -> tuple[list[tuple[str, str]], int, bool]:
    """再開時: 進捗を読み、最後のバッチ分を出力CSVから削除してから再実行する対象を返す。"""
    return prepare_resume_by_rows(progress_path_for(output_path, 'split'), rows, batch_size, [output_path])


def _row_from_parsed(page_title: str, name: str, parsed_row: list) -> tuple[str, str, str, str, bool]:
    """LLM の 1 行パース結果を (page_title, name, sei, mei, is_name) に変換する。"""
    if len(parsed_row) >= 4:
        name_out, sei, mei, is_name = parsed_row[0], parsed_row[1], parsed_row[2], parsed_row[3]
    else:
        name_out, sei, mei, is_name = name, '', '', True
    return (page_title, name_out or name, sei, mei, is_name)


def _process_one_batch(
    batch_start: int,
    batch_rows: list[tuple[str, str]],
    provider: str,
    api_url: str,
    model: str,
    timeout: int,
    *,
    batch_size: int = 1,
    workers: int = 1,
) -> tuple[int, list[tuple[str, str, str, str, bool]]]:
    """
    1バッチ分のLLM呼び出しで氏名分割し、(page_title, name, sei, mei, 氏名フラグ) のリストを返す。
    """
    stagger_batch_start(batch_start, batch_size, workers)
    take = batch_rows
    user_input = '\n'.join([n for _, n in take])
    response = _call_split_llm(provider, api_url, model, user_input, timeout)
    parsed = parse_csv_response(response)

    out: list[tuple[str, str, str, str, bool]] = []
    for (page_title, name), parsed_row in zip(take, parsed):
        out.append(_row_from_parsed(page_title, name, parsed_row))
    for (page_title, name) in take[len(parsed):]:
        out.append((page_title, name, '', '', True))
    return (batch_start, out)


def parse_args() -> object:
    p = make_llm_parser(
        '①の対象CSVをLLMで氏名分割し、characters.csv を出力する',
        'WIKI_LLM_SPLIT_BATCH_SIZE',
        DEFAULT_LLM_SPLIT_BATCH_SIZE,
    )
    p.add_argument('--input-target', type=Path, default=Path('out/characters_target.csv'),
                   help='①の対象CSV（characters_target.csv）。既定: out/characters_target.csv')
    p.add_argument('--output', type=Path, default=None,
                   help='出力CSV（既定: <inputの同dir>/characters.csv）')
    return p.parse_args()


def _run_split_batches(
    rows_to_do: list,
    output_path: Path,
    progress_path: Path,
    skipped_count: int,
    total_rows: int,
    batch_size: int,
    provider: str,
    api_url: str,
    model: str,
    timeout: int,
    workers: int,
    total_timer: Timer,
    file_has_data: bool,
) -> tuple[int, int]:
    """
    バッチ単位で LLM を呼び出し、結果を output_path に追記する。
    返り値: (今回書き込み行数, エラー数)
    """
    total_rows_written: list[int] = [0]

    def on_success(_batch_start: int, _batch_rows: list, result: tuple, processed_count_after: int) -> None:
        _, page_rows = result
        for row in page_rows:
            writer.writerow(row)
            total_rows_written[0] += 1
        try:
            with open(progress_path, 'w', encoding='utf-8') as pf:
                pf.write(f'{len(page_rows)},{processed_count_after}\n')
        except OSError:
            pass

    with open(output_path, 'a' if file_has_data else 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        if not file_has_data:
            writer.writerow(['ページ名', 'キャラクター名', '姓', '名', '氏名フラグ'])
            f.flush()
        errors = run_llm_batch_loop(
            rows_to_do,
            batch_size,
            _process_one_batch,
            {
                'provider': provider,
                'api_url': api_url,
                'model': model,
                'timeout': timeout,
                'batch_size': batch_size,
                'workers': workers,
            },
            workers,
            total_timer,
            'ai-characters-split: rows processed',
            skipped_count,
            total_rows,
            on_success,
            on_after_batch=f.flush,
        )
    return (total_rows_written[0], errors)


def _finalize_split_output(
    output_path: Path,
    progress_path: Path,
    processed_count: int,
    total_rows: int,
    total_rows_written: int,
) -> None:
    """完了時にソートと進捗ファイル削除を行う。"""
    finalize_output_with_sort(
        progress_path,
        processed_count,
        total_rows,
        paths_to_sort=[output_path],
        sort_log_message='  出力CSVを ページ名・キャラクター名 でソートしています…',
        has_output=total_rows_written > 0,
    )


def main() -> None:
    args = parse_args()
    target_path = Path(args.input_target)
    validate_input_file(
        target_path,
        f'Error: 入力ファイルが見つかりません: {target_path} （--input-target で①の characters_target.csv を指定するか、既定の out/characters_target.csv を用意してください）',
    )
    output_path = resolve_output_path(target_path, args.output, 'characters.csv')

    provider, model, batch_size, workers, timeout = resolve_llm_options(args)
    api_url = resolve_ollama_chat_url()

    rows = load_input_rows(target_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_to_do, skipped_count, file_has_data = _prepare_resume_split(output_path, rows, batch_size)
    total_rows = len(rows)
    num_batches_total = (len(rows_to_do) + batch_size - 1) // batch_size if rows_to_do else 0

    log_llm_batch_header(
        'ai-characters-split: 対象CSVをLLMで氏名分割（characters.csv、CSV行単位でバッチ）',
        provider, api_url, model, batch_size, workers, timeout,
        total_rows, num_batches_total, skipped_count, len(rows_to_do),
    )
    progress_path = progress_path_for(output_path, 'split')

    with Timer() as total_timer:
        total_rows_written, errors = _run_split_batches(
            rows_to_do,
            output_path,
            progress_path,
            skipped_count,
            total_rows,
            batch_size,
            provider,
            api_url,
            model,
            timeout,
            workers,
            total_timer,
            file_has_data,
        )
        processed_count = skipped_count + len(rows_to_do)
        _finalize_split_output(output_path, progress_path, processed_count, total_rows, total_rows_written)
        log(f'  出力: {output_path}, 今回書き込み行: {total_rows_written}, エラー数: {errors}')
    log('')
    log(f'  実行時間: {format_elapsed(total_timer.elapsed)} ({total_timer.elapsed:.1f}秒)')


if __name__ == '__main__':
    main()
    sys.exit(0)
