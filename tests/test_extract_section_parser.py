"""
section_parser のテスト。登場人物セクション抽出とキャラ名パース。
"""

import pytest

from wiki_extract.extract import section_parser as sp


def test_extract_toujo_section_none():
    """「登場人物」が含まれないと None。"""
    assert sp.extract_toujo_section('== あらすじ ==\n本文') is None


def test_extract_toujo_section_found():
    """最初の登場人物セクションを同レベル以上の次の見出しまで抽出。"""
    wikitext = """== あらすじ ==
概要。

== 登場人物 ==
=== 主人公 ===
; 太郎（たろう）
主人公。

=== サブ ===
; 花子
"""
    got = sp.extract_toujo_section(wikitext)
    assert got is not None
    assert '=== 主人公 ===' in got
    assert '; 太郎' in got
    assert '=== サブ ===' in got
    assert '== あらすじ ==' not in got


def test_extract_toujo_section_stops_at_same_level():
    """同レベル以上の見出しでセクション終了。"""
    wikitext = """== 登場人物 ==
=== A ===
a

== 脚注 ==
"""
    got = sp.extract_toujo_section(wikitext)
    assert got is not None
    assert '=== A ===' in got
    assert '== 脚注 ==' not in got


def test_extract_toujo_section_stops_at_hochu():
    """「補足」を含む見出し手前で止める。"""
    wikitext = """== 登場人物 ==
=== A ===
a

=== 役名に関する補足 ===
"""
    got = sp.extract_toujo_section(wikitext)
    assert got is not None
    assert '補足' not in got


def test_normalize_title():
    """#アンカー除去、空白をアンダースコアに。"""
    assert sp._normalize_title('Foo Bar') == 'Foo_Bar'
    assert sp._normalize_title('Foo#Bar') == 'Foo'
    assert sp._normalize_title('') == ''


def test_is_likely_group_heading():
    """グループ見出し（人物、その他等）は True。"""
    assert sp._is_likely_group_heading('主要人物') is True
    assert sp._is_likely_group_heading('その他') is True
    assert sp._is_likely_group_heading('呪術師') is True  # 人物で終わる
    assert sp._is_likely_group_heading('虎杖 悠仁') is False
    assert sp._is_likely_group_heading('') is True


def test_headings_with_dt_in_body():
    """見出し直下に ; 行がある見出しタイトルを返す。"""
    section = """=== 主要人物 ===
; 太郎
; 花子

=== 単独 ===
名前のみ
"""
    got = sp._headings_with_dt_in_body(section)
    assert '主要人物' in got
    assert '単独' not in got


def test_strip_ref_tags():
    """<ref>...</ref> を除去。"""
    wikitext = '太郎<ref>出典</ref>です。'
    got = sp._strip_ref_tags(wikitext)
    assert 'ref' not in got or '出典' not in got


def test_heading_title_to_name():
    """見出し/用語からキャラ名を正規化。括弧読みは除去。"""
    assert sp._heading_title_to_name('虎杖 悠仁（いたどり ゆうじ）') == '虎杖_悠仁'
    assert sp._heading_title_to_name('[[志村ケン太]]') == '志村ケン太'
    assert sp._heading_title_to_name('主要人物') is None


def test_extract_character_names_from_toujo_section():
    """見出しと ; 行からキャラ名を yield、重複なし。"""
    section = """=== 主人公 ===
; 虎杖 悠仁（いたどり ゆうじ）
; 伏黒 恵

=== その他 ===
; 七海 建人
"""
    names = list(sp.extract_character_names_from_toujo_section(section))
    assert '虎杖_悠仁' in names
    assert '伏黒_恵' in names
    assert '七海_建人' in names
    assert 'その他' not in names


def test_extract_character_names_bold_only_line():
    """'''名前''' の行からも抽出。"""
    section = """'''ミギー'''
'''田宮 良子'''（たみや りょうこ）
"""
    names = list(sp.extract_character_names_from_toujo_section(section))
    assert 'ミギー' in names
    assert '田宮_良子' in names


def test_extract_links_from_wikitext():
    """メイン名前空間の内部リンクを yield、Category 等は除外。"""
    wikitext = '[[太郎]]と[[花子]]。[[Category:人物]]'
    links = list(sp.extract_links_from_wikitext(wikitext))
    assert '太郎' in links
    assert '花子' in links
    assert not any('Category' in l for l in links)


def test_extract_fictional_links_from_page_ns_not_zero():
    """ns != 0 なら空集合。"""
    assert sp.extract_fictional_links_from_page(1, 14, '[[x]]', set()) == set()


def test_extract_fictional_links_from_page_toujo_page():
    """toujo_page_ids に含まれる page_id は本文全体からキャラ名抽出。"""
    text = """== 登場人物 ==
=== 主人公 ===
; キャラX
"""
    got = sp.extract_fictional_links_from_page(42, 0, text, {42})
    assert len(got) >= 1
    assert 'キャラX' in got or 'キャラ_X' in got


def test_extract_fictional_links_from_page_normal_page():
    """通常ページは登場人物セクションのみから抽出。"""
    text = """== あらすじ ==
[[本文のリンク]]

== 登場人物 ==
; キャラY
"""
    got = sp.extract_fictional_links_from_page(1, 0, text, set())
    assert len(got) >= 1
    assert 'キャラY' in got or 'キャラ_Y' in got
