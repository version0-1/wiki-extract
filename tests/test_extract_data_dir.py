"""
data_dir のテスト。tmp_path にダンプ名のファイルを置いて検証。
"""

from pathlib import Path

import pytest

from wiki_extract.extract import data_dir


def test_find_dump_found(tmp_path):
    """substring を含むファイルを1つ返す。"""
    (tmp_path / 'jawiki-latest-categorylinks.sql.gz').touch()
    got = data_dir.find_dump(tmp_path, 'categorylinks')
    assert got.name == 'jawiki-latest-categorylinks.sql.gz'


def test_find_dump_not_dir_raises(tmp_path):
    """data_dir がディレクトリでないと FileNotFoundError。"""
    f = tmp_path / 'file'
    f.touch()
    with pytest.raises(FileNotFoundError, match='データディレクトリが存在しません'):
        data_dir.find_dump(f, 'x')


def test_find_dump_missing_raises(tmp_path):
    """該当ファイルが無いと FileNotFoundError。"""
    with pytest.raises(FileNotFoundError, match="を含むファイルがありません"):
        data_dir.find_dump(tmp_path, 'categorylinks')


def test_find_dump_optional_found(tmp_path):
    """見つかればその Path。"""
    (tmp_path / 'page.sql.gz').touch()
    got = data_dir.find_dump_optional(tmp_path, 'page')
    assert got is not None
    assert 'page' in got.name


def test_find_dump_optional_missing(tmp_path):
    """見つからなければ None。"""
    assert data_dir.find_dump_optional(tmp_path, 'nonexistent') is None


def test_find_dump_optional_not_dir(tmp_path):
    """ディレクトリでなければ None。"""
    f = tmp_path / 'f'
    f.touch()
    assert data_dir.find_dump_optional(f, 'x') is None


def test_find_pages_articles_prefers_xml(tmp_path):
    """解凍済み .xml を優先。"""
    (tmp_path / 'jawiki-pages-articles.xml').touch()
    (tmp_path / 'jawiki-pages-articles.xml.bz2').touch()
    got = data_dir.find_pages_articles(tmp_path)
    assert got.name.endswith('.xml') and not got.name.endswith('.xml.bz2')


def test_find_pages_articles_uses_bz2_if_no_xml(tmp_path):
    """.xml が無ければ .xml.bz2 を返す。"""
    (tmp_path / 'jawiki-pages-articles.xml.bz2').touch()
    got = data_dir.find_pages_articles(tmp_path)
    assert got.name.endswith('.xml.bz2')


def test_find_pages_articles_missing_raises(tmp_path):
    """pages-articles が無いと FileNotFoundError。"""
    with pytest.raises(FileNotFoundError, match='pages-articles'):
        data_dir.find_pages_articles(tmp_path)


def test_require_dumps_ok(tmp_path):
    """categorylinks, page の .sql.gz と pages-articles があれば 3 つ返す。"""
    (tmp_path / 'jawiki-categorylinks.sql.gz').touch()
    (tmp_path / 'jawiki-page.sql.gz').touch()
    (tmp_path / 'jawiki-pages-articles.xml').touch()
    cl, page, xml = data_dir.require_dumps(tmp_path)
    assert 'categorylinks' in cl.name and cl.name.endswith('.sql.gz')
    assert 'page' in page.name and page.name.endswith('.sql.gz')
    assert 'pages-articles' in xml.name


def test_require_dumps_invalid_categorylinks_raises(tmp_path):
    """categorylinks が .sql.gz でないと FileNotFoundError。"""
    (tmp_path / 'categorylinks.txt').touch()
    (tmp_path / 'page.sql.gz').touch()
    (tmp_path / 'pages-articles.xml').touch()
    with pytest.raises(FileNotFoundError, match='categorylinks 用 SQL ダンプ'):
        data_dir.require_dumps(tmp_path)
