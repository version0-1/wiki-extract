"""
ai_characters_filter の純粋関数のテスト。
"""

import pytest

from wiki_extract.characters import ai_characters_filter as af


def test_should_force_exclude():
    """回次表記などは True。"""
    assert af.should_force_exclude('1回（最終回）') is True
    assert af.should_force_exclude('2回目・最終回') is True
    assert af.should_force_exclude('太郎') is False
    assert af.should_force_exclude('') is False


def test_looks_like_sentence_fragment():
    """文の断片なら True。"""
    assert af.looks_like_sentence_fragment('ああ。') is True
    assert af.looks_like_sentence_fragment('あ' * 61) is True
    assert af.looks_like_sentence_fragment('虎杖 悠仁') is False


def test_looks_like_proper_noun():
    """固有名詞らしければ True。"""
    assert af.looks_like_proper_noun('虎杖 悠仁') is True
    assert af.looks_like_proper_noun('スドオ') is True
    assert af.looks_like_proper_noun('') is False
    assert af.looks_like_proper_noun('あ' * 51) is False


def test_normalize_status():
    """'target' / 'exclude' 以外は 'target'。"""
    assert af._normalize_status('target') == 'target'
    assert af._normalize_status('exclude') == 'exclude'
    assert af._normalize_status('unknown') == 'target'
    assert af._normalize_status('') == 'target'


def test_strip_json_code_block():
    """先頭・末尾の ``` ブロックを除去。"""
    assert af._strip_json_code_block('```\n[1,2]\n```') == '[1,2]'
    assert af._strip_json_code_block('[1,2]') == '[1,2]'
    assert af._strip_json_code_block('  ```\n[]\n```  ') == '[]'


def test_parse_filter_response_valid():
    """有効な JSON なら (name, status) のリスト。"""
    names = ['A', 'B', 'C']
    response = '[{"name":"A","status":"target"},{"name":"B","status":"exclude"}]'
    got = af.parse_filter_response(response, names)
    assert got == [('A', 'target'), ('B', 'exclude'), ('C', 'target')]


def test_parse_filter_response_with_code_block():
    """``` で囲まれた JSON もパース。"""
    names = ['X']
    response = '```json\n[{"name":"X","status":"exclude"}]\n```'
    got = af.parse_filter_response(response, names)
    assert got == [('X', 'exclude')]


def test_parse_filter_response_invalid_fallback():
    """パース失敗時は入力順で target。"""
    names = ['A', 'B']
    got = af.parse_filter_response('not json', names)
    assert got == [('A', 'target'), ('B', 'target')]
