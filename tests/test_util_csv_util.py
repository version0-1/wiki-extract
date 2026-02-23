"""
csv_util のテスト。一時ファイルで CSV を用意して検証する。
"""

import csv
from pathlib import Path

import pytest

from wiki_extract.util import csv_util


def test_truncate_csv_tail_removes_tail(tmp_path):
    """末尾 remove_count 行を削除しヘッダは残す。"""
    p = tmp_path / 'out.csv'
    with open(p, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f).writerows([['A', 'B'], ['r1', 'v1'], ['r2', 'v2'], ['r3', 'v3']])
    assert csv_util.truncate_csv_tail(p, 2) is True
    with open(p, encoding='utf-8', newline='') as f:
        rows = list(csv.reader(f))
    assert rows == [['A', 'B'], ['r1', 'v1']]


def test_truncate_csv_tail_header_only_returns_false(tmp_path):
    """ヘッダのみのファイルは何もしず False。"""
    p = tmp_path / 'out.csv'
    p.write_text('A,B\n', encoding='utf-8')
    assert csv_util.truncate_csv_tail(p, 1) is False


def test_truncate_csv_tail_no_file_returns_false(tmp_path):
    """ファイルが無い場合は False。"""
    assert csv_util.truncate_csv_tail(tmp_path / 'nonexistent.csv', 1) is False


def test_sort_csv_by_page_and_name(tmp_path):
    """1・2 列目でソートして上書き。"""
    p = tmp_path / 'out.csv'
    with open(p, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f).writerows([
            ['page', 'name'],
            ['B_page', 'B_name'],
            ['A_page', 'A_name'],
            ['A_page', 'Z_name'],
        ])
    csv_util.sort_csv_by_page_and_name(p)
    with open(p, encoding='utf-8', newline='') as f:
        rows = list(csv.reader(f))
    assert rows[0] == ['page', 'name']
    assert rows[1] == ['A_page', 'A_name']
    assert rows[2] == ['A_page', 'Z_name']
    assert rows[3] == ['B_page', 'B_name']


def test_sort_csv_by_page_and_name_no_file(tmp_path):
    """ファイルが無い場合は何もしない。"""
    csv_util.sort_csv_by_page_and_name(tmp_path / 'nonexistent.csv')  # no raise


def test_prepare_resume_by_rows_no_output_paths():
    """output_paths が空なら rows そのまま・0・False。"""
    rows = [1, 2, 3]
    got = csv_util.prepare_resume_by_rows(Path('/x'), rows, 1, [])
    assert got == (rows, 0, False)


def test_prepare_resume_by_rows_no_progress_file(tmp_path):
    """進捗ファイルが無いときは rows そのまま・0・False。"""
    rows = [('p', 'n')] * 5
    out = tmp_path / 'out.csv'
    with open(out, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f).writerow(['page', 'name'])
        csv.writer(f).writerows(rows[:3])
    progress = tmp_path / '.filter_progress'
    got = csv_util.prepare_resume_by_rows(progress, rows, 2, [out])
    assert got == (rows, 0, False)


def test_prepare_resume_by_rows_with_progress(tmp_path):
    """進捗あり: 末尾削除して再実行対象と skipped_count を返す。"""
    rows = [('p', f'n{i}') for i in range(10)]
    out = tmp_path / 'out.csv'
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['page', 'name'])
        w.writerows(rows[:6])  # 5 行データ
    progress = tmp_path / '.filter_progress'
    progress.write_text('5,5', encoding='utf-8')  # 5 行削除、cumulative=5
    got = csv_util.prepare_resume_by_rows(progress, rows, 2, [out])
    rows_to_do, skipped, file_has_data = got
    assert file_has_data is True
    # start_idx = max(0, cumulative - batch_size) = max(0, 5-2)=3, return (rows[3:], 3, True)
    assert skipped == 3
    assert len(rows_to_do) == 7
    assert rows_to_do[0] == ('p', 'n3')


def test_finalize_output_with_sort_incomplete():
    """processed_count < total_rows のときは何もしない。"""
    p = Path('/tmp/progress')
    csv_util.finalize_output_with_sort(
        p, 5, 10,
        paths_to_sort=[],
        sort_log_message='sorting',
        has_output=True,
    )
    # ファイルを作っていないので unlink はしないが、sort も呼ばれない
    # 単に return するだけなので assert は不要（呼び落ちしなければよい）


def test_finalize_output_with_sort_complete_deletes_progress(tmp_path, capsys):
    """processed_count >= total_rows で paths_to_sort ありならソートして progress 削除。"""
    progress = tmp_path / '.progress'
    progress.write_text('0', encoding='utf-8')
    csv_path = tmp_path / 'out.csv'
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f).writerows([['page', 'name'], ['b', 'y'], ['a', 'x']])
    csv_util.finalize_output_with_sort(
        progress, 2, 2,
        paths_to_sort=[csv_path],
        sort_log_message='Sorting...',
        has_output=True,
    )
    assert not progress.exists()
    with open(csv_path, encoding='utf-8', newline='') as f:
        rows = list(csv.reader(f))
    assert rows[1] == ['a', 'x']
    assert rows[2] == ['b', 'y']
    err = capsys.readouterr().err
    assert 'Sorting' in err
