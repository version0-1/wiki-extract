"""
CSV のソートと LLM バッチ処理完了時の共通処理。
"""

import csv
from pathlib import Path

from wiki_extract.util.log import log
from wiki_extract.util.path_util import read_progress_ints


def prepare_resume_by_rows(
    progress_path: Path,
    rows: list,
    batch_size: int,
    output_paths: list[Path],
) -> tuple[list, int, bool]:
    """
    再開時: 進捗を読み、最後のバッチ分を出力CSVから削除してから再実行する対象を返す。
    output_paths[0] が primary（必須）。進捗は「path1の削除行数, path2の削除行数, ..., cumulative」の形式。
    返り値: (rows_to_do, skipped_count, file_has_data)
    """
    if not output_paths:
        return (rows, 0, False)
    primary = output_paths[0]
    if not progress_path.is_file() or not primary.is_file() or primary.stat().st_size == 0:
        return (rows, 0, False)

    ints = read_progress_ints(progress_path, len(output_paths) + 1)
    if ints is None:
        return (rows, 0, False)
    cumulative = ints[-1]
    if cumulative <= 0 or cumulative > len(rows):
        return (rows, 0, False)

    if not truncate_csv_tail(primary, ints[0]):
        return (rows, 0, False)
    for i in range(1, len(output_paths)):
        path = output_paths[i]
        if path.is_file():
            truncate_csv_tail(path, ints[i])

    start_idx = max(0, cumulative - batch_size)
    return (rows[start_idx:], start_idx, True)


def truncate_csv_tail(csv_path: Path, remove_count: int) -> bool:
    """
    CSV のデータ行の末尾を remove_count 行削除して上書きする。
    1 行目はヘッダとして残す。ファイルがない・ヘッダのみの場合は何もしず False。
    正常に削除した場合 True。
    """
    if not csv_path.is_file() or csv_path.stat().st_size == 0:
        return False
    with open(csv_path, encoding='utf-8', newline='') as f:
        rows = list(csv.reader(f))
    if len(rows) <= 1:
        return False
    header, data = rows[0], rows[1:]
    if remove_count > 0 and len(data) >= remove_count:
        data = data[:-remove_count]
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f).writerows([header] + data)
    return True


def sort_csv_by_page_and_name(csv_path: Path) -> None:
    """
    CSV を 1・2 列目（ページ名・名前）の順でソートして上書きする。
    1 行目はヘッダとする。
    """
    if not csv_path.is_file():
        return
    with open(csv_path, encoding='utf-8', newline='') as f:
        rows = list(csv.reader(f))
    if len(rows) <= 1:
        return
    header, data = rows[0], rows[1:]
    data.sort(key=lambda r: (r[0], r[1]) if len(r) >= 2 else (r[0], ''))
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f).writerows([header] + data)


def finalize_output_with_sort(
    progress_path: Path,
    processed_count: int,
    total_rows: int,
    *,
    paths_to_sort: list[Path] | None = None,
    sort_log_message: str = '',
    has_output: bool = True,
) -> None:
    """
    完了時にソートと進捗ファイル削除を行う。
    processed_count >= total_rows のとき、has_output かつ paths_to_sort があれば
    sort_log_message をログし各パスをソート。その後 progress_path を削除する。
    """
    if processed_count < total_rows:
        return
    if has_output and paths_to_sort and sort_log_message:
        log(sort_log_message)
        for p in paths_to_sort:
            sort_csv_by_page_and_name(p)
    if progress_path.is_file():
        try:
            progress_path.unlink()
        except OSError:
            pass
