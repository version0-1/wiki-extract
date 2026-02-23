"""
sql_page のテスト。_normalize_page_title と TOUJO_PATTERN。
"""

import pytest

from wiki_extract.extract import sql_page


def test_normalize_page_title():
    """NFKC 正規化、空白・全角スペースをアンダースコアに。"""
    assert sql_page._normalize_page_title('Foo Bar') == 'Foo_Bar'
    assert sql_page._normalize_page_title('') == ''
    assert sql_page._normalize_page_title('  a  b  ') == 'a_b'


def test_toujo_pattern_match():
    """「○○の登場人物」「○○の登場人物一覧」にマッチ。"""
    assert sql_page.TOUJO_PATTERN.match('呪術廻戦の登場人物') is not None
    assert sql_page.TOUJO_PATTERN.match('作品の登場人物一覧') is not None
    assert sql_page.TOUJO_PATTERN.match('作品の主要な登場人物') is not None


def test_toujo_pattern_no_match():
    """「登場人物」だけや他形式はマッチしない。"""
    assert sql_page.TOUJO_PATTERN.match('登場人物') is None
    assert sql_page.TOUJO_PATTERN.match('あらすじ') is None
