"""
sql_categorylinks の純粋関数のテスト。
"""

import pytest

from wiki_extract.extract import sql_categorylinks as sqlcl


def test_normalize_title():
    """空白・全角をアンダースコア、NFKC。"""
    assert sqlcl._normalize_title('Foo Bar') == 'Foo_Bar'
    assert sqlcl._normalize_title(None) == ''
    assert sqlcl._normalize_title('  a  ') == 'a'


def test_canonical_title():
    """比較用: 制御文字除去、空白・アンダースコア除去。"""
    assert sqlcl._canonical_title('Foo_Bar') == 'FooBar'
    assert sqlcl._canonical_title(None) == ''


def test_is_garbage_linktarget_title():
    """ゴミとみなすタイトルは True。"""
    assert sqlcl._is_garbage_linktarget_title('') is True
    assert sqlcl._is_garbage_linktarget_title('_+_') is True
    assert sqlcl._is_garbage_linktarget_title('data-mw-x') is True
    assert sqlcl._is_garbage_linktarget_title('"short"') is True
    assert sqlcl._is_garbage_linktarget_title('正常なカテゴリ') is False


def test_build_category_set():
    """seed 配下の全カテゴリ名を固定点で求める。"""
    subcat_rows = [(2, '架空の人物'), (3, 'サブ')]  # cl_from, 親カテゴリ名
    category_page_id_to_title = {2: 'サブ', 3: 'サブサブ'}
    got = sqlcl._build_category_set(subcat_rows, category_page_id_to_title, '架空の人物')
    assert len(got) >= 1
    # seed と子カテゴリが含まれる（正規化でアンダースコアになる場合あり）
    assert 'サブ' in got
    assert 'サブサブ' in got


def test_build_category_page_id_set():
    """seed_page_id 配下の全カテゴリ page_id。"""
    subcat_rows_by_lt = [(2, 1), (3, 1)]  # cl_from, parent lt_id
    lt_id_to_page_id = {1: 100}  # seed の page_id が 100
    got = sqlcl._build_category_page_id_set(subcat_rows_by_lt, lt_id_to_page_id, 100)
    assert 100 in got
    assert 2 in got
    assert 3 in got


def test_resolve_seed_page_id_exact():
    """正規化一致するカテゴリの page_id を返す。"""
    category_page_id_to_title = {10: '架空の人物', 20: '他のカテゴリ'}
    got = sqlcl._resolve_seed_page_id('架空の人物', category_page_id_to_title)
    assert got == 10


def test_resolve_seed_page_id_no_match():
    """一致が無ければ None。"""
    category_page_id_to_title = {10: '他のカテゴリ'}
    assert sqlcl._resolve_seed_page_id('架空の人物', category_page_id_to_title) is None
