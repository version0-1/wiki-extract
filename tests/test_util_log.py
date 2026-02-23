"""
log のテスト。format_elapsed, Timer, log / log_progress の出力。
"""

import time

import pytest

from wiki_extract.util import log as log_module


def test_format_elapsed_seconds():
    """1分未満は「N秒」。"""
    assert log_module.format_elapsed(0) == '0秒'
    assert log_module.format_elapsed(30) == '30秒'
    assert log_module.format_elapsed(59.4) == '59秒'


def test_format_elapsed_minutes():
    """1分以上1時間未満は「N分M秒」。"""
    assert log_module.format_elapsed(60) == '1分0秒'
    assert log_module.format_elapsed(90) == '1分30秒'
    assert log_module.format_elapsed(3599) == '59分59秒'


def test_format_elapsed_hours():
    """1時間以上は「N時間M分S秒」。"""
    assert log_module.format_elapsed(3600) == '1時間0分0秒'
    assert log_module.format_elapsed(3723) == '1時間2分3秒'


def test_format_elapsed_negative():
    """負の値は 0 として扱い「0秒」。"""
    assert log_module.format_elapsed(-1) == '0秒'


def test_timer_elapsed_increases():
    """Timer の elapsed は時間が経つと増える。"""
    with log_module.Timer() as t:
        time.sleep(0.05)
        e1 = t.elapsed
        time.sleep(0.05)
        e2 = t.elapsed
    assert e2 >= e1
    assert e1 >= 0.04
    assert e2 >= 0.09


def test_log_writes_to_stderr(capsys):
    """log は stderr に書き出す。"""
    log_module.log('hello')
    err = capsys.readouterr().err
    assert 'hello' in err


def test_log_progress_format(capsys):
    """log_progress は [stage] count=N elapsed=M の形式。"""
    log_module.log_progress('stage1', count=10, elapsed=1.5)
    err = capsys.readouterr().err
    assert '[stage1]' in err
    assert 'count=10' in err
    assert 'elapsed=1.5' in err
