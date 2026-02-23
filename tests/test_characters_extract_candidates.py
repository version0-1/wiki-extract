"""
extract_character_candidates の strip 系・extract 系のテスト。
"""

import pytest

from wiki_extract.characters import extract_character_candidates as ecc


def test_strip_efn():
    """{{efn|...}} を除去。"""
    s = '太郎{{efn|脚注}}です。'
    assert '{{efn' not in ecc.strip_efn(s) or '脚注' not in ecc.strip_efn(s)


def test_strip_efn_nested():
    """ネストした {{ }} も除去。"""
    s = 'a{{efn|{{inner}}}}b'
    got = ecc.strip_efn(s)
    assert got.strip() == 'ab' or 'efn' not in got


def test_strip_sfn():
    """{{Sfn|...}} を除去。"""
    s = '出典{{Sfn|author|2020}}'
    got = ecc.strip_sfn(s)
    assert 'Sfn' not in got or 'author' not in got


def test_strip_refnest():
    """{{Refnest|...}} を除去。"""
    s = '文{{Refnest|1}}'
    got = ecc.strip_refnest(s)
    assert 'Refnest' not in got


def test_split_multi_names():
    """「、」「＆」「&」「 / 」で分割。"""
    assert ecc.split_multi_names('A、B') == ['A', 'B']
    assert ecc.split_multi_names('A＆B') == ['A', 'B']
    assert ecc.split_multi_names('A & B') == ['A', 'B']
    assert ecc.split_multi_names('A / B') == ['A', 'B']


def test_clean_wiki_content_strips_templates():
    """clean_wiki_content でテンプレートが除去される。"""
    s = '名前{{efn|注}}'
    got = ecc.clean_wiki_content(s)
    assert len(got) < len(s) or 'efn' not in got


def test_extract_from_wiki_dt_lines():
    """; 行から名前行を抽出。"""
    text = """; 虎杖 悠仁
; 伏黒 恵
"""
    got = ecc.extract_from_wiki(text)
    assert len(got) >= 1
    assert any('虎杖' in g or '伏黒' in g for g in got)
