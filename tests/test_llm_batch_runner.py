"""
llm/batch_runner のテスト。stagger_batch_start, run_llm_batch_loop（モックで）。
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from wiki_extract.llm import batch_runner as br


def test_stagger_batch_start_no_delay():
    """(batch_start // batch_size) % workers == 0 のときは sleep しない。"""
    with patch.object(time, 'sleep') as mock_sleep:
        br.stagger_batch_start(0, 10, 2)
    mock_sleep.assert_not_called()


def test_stagger_batch_start_delay():
    """delay > 0 のときは sleep(delay) が呼ばれる。"""
    with patch.object(time, 'sleep') as mock_sleep:
        br.stagger_batch_start(5, 5, 2)  # (5//5)%2 = 1 -> delay=1
    mock_sleep.assert_called_once_with(1)


def test_run_llm_batch_loop_success():
    """全バッチ成功時は on_success が呼ばれ errors=0。"""
    rows = [('p', f'n{i}') for i in range(5)]
    results = []
    def process(batch_start, batch_rows, **kwargs):
        return ('ok', batch_rows)
    def on_success(batch_start, batch_rows, result, processed_count_after):
        results.append((batch_start, len(batch_rows), processed_count_after))
    class Timer:
        elapsed = 0.0
    errs = br.run_llm_batch_loop(
        rows, 2, process, {}, 1, Timer(), 'test', 0, 5, on_success,
    )
    assert errs == 0
    assert len(results) >= 2  # 2件と2件と1件のバッチなど
    assert sum(r[1] for r in results) == 5
    assert results[-1][2] == 5


def test_run_llm_batch_loop_exception_counted():
    """バッチで例外が出ると errors が増える。"""
    rows = [1, 2, 3]
    def process(batch_start, batch_rows, **kwargs):
        raise OSError('connection refused')
    on_success = MagicMock()
    class Timer:
        elapsed = 0.0
    errs = br.run_llm_batch_loop(
        rows, 2, process, {}, 1, Timer(), 'test', 0, 3, on_success,
    )
    assert errs >= 1
    on_success.assert_not_called()
