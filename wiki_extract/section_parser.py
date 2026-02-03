"""
ウィキテキストから「登場人物」セクションを抽出し、以下からキャラ名をパースする:
- 見出し (=== / ====) → HTML <h3>/<h4>
- 定義リストの用語 (; 用語) → HTML <dt>
"""

import re
from typing import Iterator

import mwparserfromhell


# "== 登場人物 ==" や "=== 登場人物 ===" などにマッチ
SECTION_HEADING_RE = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$", re.MULTILINE)
# 定義リストの用語: "; 虎杖 悠仁（いたどり ゆうじ）" や ";; ネスト" → HTML <dt>
DT_LINE_RE = re.compile(r"^\s*;+\s*(.*)$", re.MULTILINE)
# 見出し内の読み仮名を除く（例: 虎杖 悠仁（いたどり ゆうじ） -> 虎杖 悠仁）
READING_PAREN_RE = re.compile(r"\s*[（(].*?[）)]\s*$")
# 行全体が「'''名前'''」または「'''名前'''（読み）」の形（寄生獣など ; を使わない記事用）
BOLD_ONLY_LINE_RE = re.compile(r"^\s*'''([^']+)'''\s*(?:[（(][^）)]*[）)])?\s*$", re.MULTILINE)

# 登場人物セクション内の「グループ見出し」：キャラ名ではなくカテゴリ名なので除外する。
# 作品に依存しない汎用パターンのみ（「見出し直下に ; 行がある」構造ルールで大半は除外される）。
GROUP_HEADING_SUFFIXES = (
    "人物", "関係者", "隊", "一派", "一家", "キャラクター", "その他", "一覧", "図",
)
GROUP_HEADING_CONTAINS = (
    "・", "とその関係者", "の関係者", "編", "の親族", "親族・友人",
    "その他", "追加キャラクター", "DLC", "アップデート", "プレイアブル",
)
GROUP_HEADING_EXACT = frozenset({
    "その他", "主要人物",
})


def extract_toujo_section(wikitext: str) -> str | None:
    """
    最初の「登場人物」セクションを抽出（見出しから、同レベル以上の次の見出しまで）。
    「役名に関する補足」などの補足サブセクション手前で止め、役者名・説明文を避ける。
    該当セクションがなければ None を返す。
    """
    if "登場人物" not in wikitext:
        return None
    lines = wikitext.split("\n")
    in_section = False
    section_level = 0
    result: list[str] = []
    for line in lines:
        m = SECTION_HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            if "登場人物" in title:
                in_section = True
                section_level = level
                result = []
                continue
            if in_section:
                if level <= section_level:
                    in_section = False
                    break
                if "補足" in title:
                    in_section = False
                    break
        if in_section:
            result.append(line)
    return "\n".join(result) if result else None


def _normalize_title(title: str) -> str:
    """メイン名前空間のタイトル: #アンカーを除去し、空白をアンダースコアに置換。"""
    if "#" in title:
        title = title.split("#", 1)[0].strip()
    return title.replace(" ", "_") if title else ""


def _is_likely_group_heading(plain_title: str) -> bool:
    """
    見出しがカテゴリ/グループ（主要人物、呪術師、一般人など）に見える場合 True。
    個別キャラ名ではない。そのような見出しはキャラ名としては返さない。
    """
    t = plain_title.strip()
    if not t or len(t) < 2:
        return True
    if t in GROUP_HEADING_EXACT:
        return True
    for suffix in GROUP_HEADING_SUFFIXES:
        if t.endswith(suffix):
            return True
    for sub in GROUP_HEADING_CONTAINS:
        if sub in t:
            return True
    return False


def _headings_with_dt_in_body(section_wikitext: str) -> set[str]:
    """
    見出し直下の本文に定義リスト（; 行）が1行以上ある見出しのタイトルを返す。
    そのような見出しは「グループ見出し」とみなし、キャラ名としては出力しない（; 行のみから抽出する）。
    作品ごとの文言に依存しない汎用ルール。
    """
    lines = section_wikitext.splitlines()
    result: set[str] = set()
    i = 0
    while i < len(lines):
        m = SECTION_HEADING_RE.match(lines[i])
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            if level in (3, 4):
                j = i + 1
                while j < len(lines):
                    next_m = SECTION_HEADING_RE.match(lines[j])
                    if next_m and len(next_m.group(1)) <= level:
                        break
                    dt_m = DT_LINE_RE.match(lines[j])
                    if dt_m and dt_m.group(1).strip():
                        result.add(title)
                        break
                    j += 1
            i += 1
        else:
            i += 1
    return result


def _strip_ref_tags(wikitext: str) -> str:
    """
    ウィキテキストから <ref>...</ref> と <ref .../> を除去する。
    レンダリング後の HTML の <sup class="reference"> はウィキテキストでは <ref> になる。
    出典番号・説明文をキャラ名から除外するため、ref タグごと除去する。
    """
    parsed = mwparserfromhell.parse(wikitext)
    for tag in list(parsed.filter_tags()):
        if tag.tag == 'ref':
            parsed.remove(tag)
    return str(parsed).strip()


def _heading_title_to_name(heading_title: str) -> str | None:
    """
    見出し/用語（例: "おこりや長介（[[いかりや長介]]）" や "[[志村ケン太]]"）から
    正規化したキャラ名を返す。使えない場合は None。
    グループ見出し（主要人物、呪術師、一般人など）はスキップする。
    括弧内がリンク（モデル・実在人物へのリンク）の場合は括弧前のテキストをキャラ名とする。
    <ref> タグ（HTML の class="reference"）は除去してからキャラ名を判定する。
    """
    s = heading_title.strip()
    if not s:
        return None
    s = _strip_ref_tags(s)
    if not s:
        return None
    parsed = mwparserfromhell.parse(s)
    # まず括弧前のテキストをキャラ名候補とする（「キャラ名（モデル名）」でモデルだけリンクの記事で正しくキャラ名を取る）
    plain = parsed.strip_code().strip()
    plain_before_paren = READING_PAREN_RE.sub("", plain).strip()
    if plain_before_paren and not _is_likely_group_heading(plain_before_paren):
        return plain_before_paren.replace(" ", "_")
    # 括弧前が空またはグループ見出しのときのみ、リンク先を採用（例: 見出しが [[志村ケン太]] のみ）
    for node in parsed.filter_wikilinks():
        if not isinstance(node, mwparserfromhell.nodes.Wikilink):
            continue
        title = node.title.strip_code().strip()
        if ":" in title:
            prefix = title.split(":", 1)[0].strip()
            if prefix in ("Category", "File", "Image", "Wikipedia", "Template", "Help", "Portal", "Draft", "User", "Talk", "WP"):
                continue
        name = _normalize_title(title)
        if name and not _is_likely_group_heading(title):
            return name
    return None


def extract_character_names_from_toujo_section(section_wikitext: str) -> Iterator[str]:
    """
    登場人物セクションからキャラ名を yield する:
    1. レベル 3/4 の見出し (=== / ====) → <h3>/<h4>（グループ見出しは除外）
    2. 定義リストの用語 (; 名前) → <dt>（キャラ名の行）

    汎用ルール: 見出し直下に定義リスト（; 行）がある場合はその見出しをグループ名とみなし、
    キャラ名としては出力しない（; 行のみから抽出）。作品ごとの文言に依存しない。
    """
    seen: set[str] = set()
    headings_with_dt = _headings_with_dt_in_body(section_wikitext)
    parsed = mwparserfromhell.parse(section_wikitext)
    # (1) 見出し（=== / ====）から（直下に ; 行がある見出しはスキップ）
    for heading in parsed.filter_headings():
        level = heading.level
        if level < 3 or level > 4:
            continue
        title = str(heading.title).strip()
        if title in headings_with_dt:
            continue
        name = _heading_title_to_name(title)
        if name and name not in seen:
            seen.add(name)
            yield name
    # (2) 定義リストの用語（; 虎杖 悠仁（いたどり ゆうじ））から
    for line in section_wikitext.splitlines():
        m = DT_LINE_RE.match(line)
        if not m:
            continue
        term = m.group(1).strip()
        if not term:
            continue
        name = _heading_title_to_name(term)
        if name and name not in seen:
            seen.add(name)
            yield name
    # (3) 行全体が「'''名前'''」または「'''名前'''（読み）」の形（寄生獣など ; を使わない記事用）
    for line in section_wikitext.splitlines():
        m = BOLD_ONLY_LINE_RE.match(line)
        if not m:
            continue
        raw_name = m.group(1).strip()
        if not raw_name:
            continue
        name = raw_name.replace(" ", "_")
        if _is_likely_group_heading(raw_name) or name in seen:
            continue
        seen.add(name)
        yield name


def extract_links_from_wikitext(wikitext: str) -> Iterator[str]:
    """
    ウィキテキストからメイン名前空間の内部リンク先を yield する。
    Category:, File: などは除外。[[title]] と [[title|label]] に対応。
    """
    parsed = mwparserfromhell.parse(wikitext)
    for node in parsed.filter_wikilinks():
        if not isinstance(node, mwparserfromhell.nodes.Wikilink):
            continue
        title = node.title.strip_code().strip()
        if not title:
            continue
        if ":" in title:
            prefix = title.split(":", 1)[0].strip()
            if prefix in ("Category", "File", "Image", "Wikipedia", "Template", "Help", "Portal", "Draft", "User", "Talk", "WP"):
                continue
        if "#" in title:
            title = title.split("#", 1)[0].strip()
        if title:
            yield title.replace(" ", "_")


def extract_fictional_links_from_page(
    page_id: int,
    ns: int,
    text: str,
    toujo_page_ids: set[int],
) -> set[str]:
    """
    XML ダンプの1ページに対して: ns != 0 なら空集合を返す。
    登場人物セクション内の見出し (=== または ====) からのキャラ名のみ抽出するため、
    本文中のリンク（声優名・地名・一般名詞など）は含めない。
    メイン名前空間のタイトル（アンダースコアで正規化）の集合を返す。
    """
    if ns != 0:
        return set()
    if page_id in toujo_page_ids:
        return set(extract_character_names_from_toujo_section(text))
    section = extract_toujo_section(text)
    if section is None:
        return set()
    return set(extract_character_names_from_toujo_section(section))
