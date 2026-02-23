"""
パス解決の共通ユーティリティ。
"""

import sys
from pathlib import Path

from wiki_extract.util.log import log


def validate_input_file(path: Path | None, error_message: str) -> None:
    """
    入力ファイルの存在を検証する。存在しなければ error_message をログして exit(1)。
    path が None の場合もエラーとする。
    """
    if path is None or not path.is_file():
        log(error_message)
        sys.exit(1)


def progress_path_for(output_path: Path, name: str) -> Path:
    """出力ファイルと同じ dir に置く進捗ファイルのパス。name は 'split' や 'filter' など。"""
    return output_path.parent / f'.{name}_progress'


def read_progress_ints(progress_path: Path, expected_count: int) -> list[int] | None:
    """
    進捗ファイルを読む。1 行のカンマ区切り整数が expected_count 個ならリストで返す。不正時は None。
    """
    try:
        with open(progress_path, encoding='utf-8') as f:
            line = f.read().strip()
        parts = line.split(',')
        if len(parts) != expected_count:
            return None
        return [int(p) for p in parts]
    except (ValueError, OSError):
        return None


def resolve_output_path(
    input_path: Path,
    output_arg: Path | None,
    default_filename: str,
) -> Path:
    """
    入力パスとオプションの出力指定から出力ファイルパスを決める。
    output_arg が未指定なら input_path の親 dir / default_filename。
    指定がディレクトリならその下に default_filename を付与する。
    """
    base_dir = input_path.parent
    path = Path(output_arg) if output_arg else base_dir / default_filename
    if path.is_dir():
        path = path / default_filename
    return path
