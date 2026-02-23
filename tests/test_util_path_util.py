"""
path_util のテスト。
"""

import sys
from pathlib import Path

import pytest

from wiki_extract.util import path_util


def test_progress_path_for():
    """進捗ファイルパスは出力と同じ親 dir に .{name}_progress になる。"""
    out = Path('/out/foo.csv')
    assert path_util.progress_path_for(out, 'split') == Path('/out/.split_progress')
    assert path_util.progress_path_for(out, 'filter') == Path('/out/.filter_progress')


def test_read_progress_ints_valid(tmp_path):
    """進捗ファイルが期待個数のカンマ区切り整数ならリストで返す。"""
    p = tmp_path / 'progress'
    p.write_text('3,2,5', encoding='utf-8')
    assert path_util.read_progress_ints(p, 3) == [3, 2, 5]


def test_read_progress_ints_wrong_count(tmp_path):
    """期待個数と違うと None。"""
    p = tmp_path / 'progress'
    p.write_text('1,2', encoding='utf-8')
    assert path_util.read_progress_ints(p, 3) is None


def test_read_progress_ints_invalid_int(tmp_path):
    """非数値が含まれると None。"""
    p = tmp_path / 'progress'
    p.write_text('1,abc,3', encoding='utf-8')
    assert path_util.read_progress_ints(p, 3) is None


def test_read_progress_ints_no_file(tmp_path):
    """ファイルが存在しないと None。"""
    assert path_util.read_progress_ints(tmp_path / 'nonexistent', 2) is None


def test_resolve_output_path_no_arg():
    """output_arg 未指定なら input の親 dir / default_filename。"""
    inp = Path('/in/candidates.csv')
    got = path_util.resolve_output_path(inp, None, 'characters_target.csv')
    assert got == Path('/in/characters_target.csv')


def test_resolve_output_path_with_file_arg():
    """output_arg にファイルパスを指定するとそのまま。"""
    inp = Path('/in/candidates.csv')
    out = Path('/out/target.csv')
    got = path_util.resolve_output_path(inp, out, 'characters_target.csv')
    assert got == Path('/out/target.csv')


def test_resolve_output_path_with_dir_arg():
    """output_arg がディレクトリならその下に default_filename。"""
    inp = Path('/in/candidates.csv')
    out_dir = Path('/out')
    out_dir.mkdir(parents=True, exist_ok=True)
    got = path_util.resolve_output_path(inp, out_dir, 'characters_target.csv')
    assert got == Path('/out/characters_target.csv')


def test_validate_input_file_none_exits(capsys):
    """path が None のときログして exit(1)。"""
    with pytest.raises(SystemExit) as exc_info:
        path_util.validate_input_file(None, 'file required')
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert 'file required' in err


def test_validate_input_file_missing_exits(tmp_path, capsys):
    """存在しないファイルのときログして exit(1)。"""
    missing = tmp_path / 'missing.csv'
    with pytest.raises(SystemExit) as exc_info:
        path_util.validate_input_file(missing, 'file required')
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert 'file required' in err


def test_validate_input_file_ok(tmp_path):
    """存在するファイルのときは正常終了（exit しない）。"""
    f = tmp_path / 'ok.csv'
    f.write_text('a,b', encoding='utf-8')
    path_util.validate_input_file(f, 'ignored')  # no raise
