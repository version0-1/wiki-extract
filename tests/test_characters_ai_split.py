"""
ai_characters_split の parse 系のテスト。
"""

import pytest

from wiki_extract.characters import ai_characters_split as asp


def test_parse_csv_response_header_skipped():
    """「名前,」で始まる行はスキップ。"""
    response = """名前,姓,名,氏名フラグ
太郎,太郎,,True
"""
    got = asp.parse_csv_response(response)
    assert len(got) == 1
    assert got[0][0] == '太郎'


def test_parse_csv_response_columns():
    """名前,姓,名,氏名フラグ の4列。"""
    response = """山田,山田,,True
"""
    got = asp.parse_csv_response(response)
    assert got == [('山田', '山田', '', True)]


def test_parse_csv_response_is_name_false():
    """氏名フラグが False のとき。"""
    response = """不明,,,False
"""
    got = asp.parse_csv_response(response)
    assert got[0][3] is False


def test_parse_csv_response_empty():
    """空・ヘッダのみなら空リスト。"""
    assert asp.parse_csv_response('') == []
    assert asp.parse_csv_response('名前,姓,名,氏名フラグ') == []


def test_row_from_parsed():
    """パース結果を (page_title, name, sei, mei, is_name) に変換。"""
    row = asp._row_from_parsed('ページ', 'キャラ', ['山田', '山田', '太郎', True])
    assert row == ('ページ', '山田', '山田', '太郎', True)


def test_row_from_parsed_short():
    """列が足りないときは name をそのまま。"""
    row = asp._row_from_parsed('ページ', 'キャラ', ['x'])
    assert row[1] in ('x', 'キャラ')
    assert row[4] is True
