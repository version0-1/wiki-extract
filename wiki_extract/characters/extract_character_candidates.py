"""
ページから登場人物候補を抽出し、（ページ名, 名前）のCSVで出力する。
出力は ai-characters-filter の入力として利用する。
"""

import csv
import json
import os
import re
import sys
from pathlib import Path

from wiki_extract.extract.section_parser import extract_toujo_section
from wiki_extract.util.log import format_elapsed, log, log_progress, Timer


def strip_efn(s: str) -> str:
    """
    Wikipedia の脚注テンプレート {{efn|...}} / {{efn2|...}} などを除去する。
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    while i < len(s):
        if i <= len(s) - 5 and s[i:i + 4].lower() == '{{ef':
            # {{efn| / {{Efn| / {{efn2| など（大文字小文字区別しない）
            j = i + 4
            if j < len(s) and s[j].lower() == 'n':
                j += 1
            while j < len(s) and s[j].isdigit():
                j += 1
            if j < len(s) and s[j] == '|':
                # 対応する }} を探す（ネストを考慮）
                depth = 1
                k = j + 1
                while k < len(s) and depth > 0:
                    if k < len(s) - 1 and s[k:k + 2] == '{{':
                        depth += 1
                        k += 2
                    elif k < len(s) - 1 and s[k:k + 2] == '}}':
                        depth -= 1
                        k += 2
                    else:
                        k += 1
                i = k
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_sfn(s: str) -> str:
    """
    Wikipedia の出典テンプレート {{Sfn|...}} / {{sfn|...}} を除去する。
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    while i < len(s):
        if i <= len(s) - 6 and s[i:i + 2] == '{{' and s[i + 2:i + 5].lower() == 'sfn' and s[i + 5] == '|':
            j = i + 5
            depth = 1
            k = j + 1
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            i = k
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_refnest(s: str) -> str:
    """
    Wikipedia の脚注テンプレート {{Refnest|...}} を除去する。
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    while i < len(s):
        if i <= len(s) - 11 and s[i:i + 2] == '{{' and s[i + 2:i + 9].lower() == 'refnest':
            j = i + 9
            if j < len(s) and s[j] == '|':
                depth = 1
                k = j + 1
                while k < len(s) and depth > 0:
                    if k < len(s) - 1 and s[k:k + 2] == '{{':
                        depth += 1
                        k += 2
                    elif k < len(s) - 1 and s[k:k + 2] == '}}':
                        depth -= 1
                        k += 2
                    else:
                        k += 1
                i = k
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_ruby(s: str) -> str:
    """
    Wikipedia の {{Ruby|表示テキスト|ルビ}} を表示テキストだけに置き換える（ルビは不要）。
    例: 金沢良造（{{Ruby|天松屋良造|てんまつやよしぞう}}）→ 金沢良造（天松屋良造）
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'Ruby'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag.lower() and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            end = k
            pos = param_start
            depth2 = 0
            while pos < k:
                if pos < len(s) - 1 and s[pos:pos + 2] == '{{':
                    depth2 += 1
                    pos += 2
                elif pos < len(s) - 1 and s[pos:pos + 2] == '}}':
                    if depth2 == 0:
                        end = pos
                        break
                    depth2 -= 1
                    pos += 2
                elif s[pos] == '|' and depth2 == 0:
                    end = pos
                    break
                else:
                    pos += 1
                    end = pos
            result.append(s[param_start:end].strip())
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_yomigana(s: str) -> str:
    """
    Wikipedia の {{読み仮名|表記|読み}} を表記だけに置き換える（読みは不要）。
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = '読み仮名'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len] == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            end = param_start
            pos = param_start
            depth2 = 0
            while pos < k:
                if pos < len(s) - 1 and s[pos:pos + 2] == '{{':
                    depth2 += 1
                    pos += 2
                elif pos < len(s) - 1 and s[pos:pos + 2] == '}}':
                    depth2 -= 1
                    pos += 2
                elif s[pos] == '|' and depth2 == 0:
                    end = pos
                    break
                pos += 1
                end = pos
            result.append(s[param_start:end].strip())
            i = k
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_yomigana_ruby_fushiyo(s: str) -> str:
    """
    Wikipedia の {{読み仮名_ruby不使用|表示名|読み}} を表示名に置換する。
    例: 高梨さん,{{読み仮名_ruby不使用|高梨 悦子|たかなし えつこ}} → 高梨さん,高梨 悦子
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = '読み仮名_ruby不使用'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len] == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            result.append(_template_first_param(s, param_start, k))
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_kari_link(s: str) -> str:
    """
    Wikipedia の {{仮リンク|表示名|...}} を表示名だけに置き換える。
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = '仮リンク'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len] == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            # 第1パラメータ（表示名）の終端: ネスト外の | または }}
            end = param_start
            pos = param_start
            while pos < k:
                if pos < len(s) - 1 and s[pos:pos + 2] == '{{':
                    depth2 = 1
                    pos += 2
                    while pos < len(s) and depth2 > 0:
                        if pos < len(s) - 1 and s[pos:pos + 2] == '{{':
                            depth2 += 1
                            pos += 2
                        elif pos < len(s) - 1 and s[pos:pos + 2] == '}}':
                            depth2 -= 1
                            pos += 2
                        else:
                            pos += 1
                    continue
                if s[pos] == '|' or (pos < len(s) - 1 and s[pos:pos + 2] == '}}'):
                    end = pos
                    break
                pos += 1
                end = pos
            result.append(s[param_start:end].strip())
            i = k
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_visible_anchor(s: str) -> str:
    """
    Wikipedia の {{Visible anchor|...|表示名}} を表示名だけに置き換える。
    最後のパラメータ（ネスト外の最後の | より後）を表示名とする。
    {{Visible anchor | ヘンリエッタ | ヘンリエッタ }} のようにタグ直後のスペースにも対応。
    """
    result = []
    i = 0
    tag = 'Visible anchor'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag.lower():
            pipe_pos = i + 2 + tag_len
            while pipe_pos < len(s) and s[pipe_pos] == ' ':
                pipe_pos += 1
            if pipe_pos < len(s) and s[pipe_pos] == '|':
                content_start = pipe_pos + 1
                depth = 1
                k = content_start
                while k < len(s) and depth > 0:
                    if k < len(s) - 1 and s[k:k + 2] == '{{':
                        depth += 1
                        k += 2
                    elif k < len(s) - 1 and s[k:k + 2] == '}}':
                        depth -= 1
                        k += 2
                    else:
                        k += 1
                content = s[content_start:k - 2] if k >= 2 else s[content_start:k]
                last_pipe = -1
                pos = 0
                depth2 = 0
                while pos < len(content):
                    if pos < len(content) - 1 and content[pos:pos + 2] == '{{':
                        depth2 += 1
                        pos += 2
                    elif pos < len(content) - 1 and content[pos:pos + 2] == '}}':
                        depth2 -= 1
                        pos += 2
                    elif content[pos] == '|' and depth2 == 0:
                        last_pipe = pos
                        pos += 1
                    else:
                        pos += 1
                if last_pipe >= 0:
                    display = content[last_pipe + 1:].strip()
                else:
                    display = content.strip()
                result.append(display)
                i = k
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_ref(s: str) -> str:
    """
    Wikipedia の <ref ...>...</ref> および <ref ... /> を除去する。
    属性内の引用符（group=""登場"" など）に対応する。
    """
    result = []
    i = 0
    while i < len(s):
        if i <= len(s) - 5 and s[i:i + 4] == '<ref':
            j = i + 4
            # 開始タグの終端 > または /> を探す（属性内の "..." はスキップ）
            while j < len(s):
                if s[j] == '"':
                    j += 1
                    while j < len(s) and s[j] != '"':
                        j += 1
                    if j < len(s):
                        j += 1
                    continue
                if s[j] == '>' or (j + 1 < len(s) and s[j:j + 2] == '/>'):
                    break
                j += 1
            if j >= len(s):
                result.append(s[i])
                i += 1
                continue
            if s[j] == '>':
                # <ref ...>...</ref> の閉じタグを探す
                end_tag = '</ref>'
                k = s.find(end_tag, j + 1)
                if k != -1:
                    i = k + len(end_tag)
                    continue
            else:
                # <ref ... />
                i = j + 2
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


_FONT_SUFFIX = 'フォント|'
_FONT_SUFFIX_LEN = len('フォント')  # 4


def strip_font_template(s: str) -> str:
    """
    Wikipedia の {{XXXフォント|文字}}（JIS2004フォント、JIS90フォント 等）を文字に置換する。
    例: {{JIS2004フォント|葛}}葉 キョウジ → 葛葉 キョウジ、{{JIS90フォント|葛}}葉 → 葛葉
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    while i < len(s):
        if i <= len(s) - 2 and s[i:i + 2] == '{{':
            j = s.find(_FONT_SUFFIX, i + 2)
            if j != -1 and '}' not in s[i + 2:j]:
                param_start = j + _FONT_SUFFIX_LEN + 1
                depth = 1
                k = param_start
                while k < len(s) and depth > 0:
                    if k < len(s) - 1 and s[k:k + 2] == '{{':
                        depth += 1
                        k += 2
                    elif k < len(s) - 1 and s[k:k + 2] == '}}':
                        depth -= 1
                        k += 2
                    else:
                        k += 1
                result.append(_template_first_param(s, param_start, k))
                i = k
                while i < len(s) and s[i] == '}':
                    i += 1
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_hojo_kanji_font(s: str) -> str:
    """
    Wikipedia の {{補助漢字フォント|...}} を削除する。
    例: 冴羽{{補助漢字フォント|...}} → 冴羽
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = '補助漢字フォント'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len] == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_hash_tag(s: str) -> str:
    """
    MediaWiki の {{#tag|...}} / {{#tag:...}} を削除する。
    例: 三原一郎{{#tag|ref|...}} → 三原一郎
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = '#tag'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len] == tag:
            pipe_pos = i + 2 + tag_len
            while pipe_pos < len(s) and s[pipe_pos] == ' ':
                pipe_pos += 1
            if pipe_pos < len(s) and (s[pipe_pos] == '|' or s[pipe_pos] == ':'):
                param_start = pipe_pos + 1
                depth = 1
                k = param_start
                while k < len(s) and depth > 0:
                    if k < len(s) - 1 and s[k:k + 2] == '{{':
                        depth += 1
                        k += 2
                    elif k < len(s) - 1 and s[k:k + 2] == '}}':
                        depth -= 1
                        k += 2
                    else:
                        k += 1
                i = k
                while i < len(s) and s[i] == '}':
                    i += 1
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_ill2(s: str) -> str:
    """
    Wikipedia の {{ill2|...|label=表示}} を表示テキストに置き換える。
    label= がなければ第1パラメータを使用。例: {{ill2|アラジン (ディズニー)|en|...|label=アラジン}} → アラジン
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'ill2'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            content = s[param_start:k]
            display = ''
            # label= または label = を探す
            label_match = re.search(r'label\s*=\s*([^|}]*)', content)
            if label_match:
                display = label_match.group(1).strip()
            if not display:
                first_pipe = content.find('|')
                if first_pipe >= 0:
                    display = content[:first_pipe].strip()
                else:
                    display = content.strip()
            result.append(display)
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_trailing_latin_paren(s: str) -> str:
    """
    末尾の「（ラテン文字のみ）」を削除する。キャラ名のみにしたい場合用。
    例: アラジン（Aladdin）→ アラジン
    """
    # 全角括弧
    if s and '（' in s:
        i = s.rfind('（')
        j = s.find('）', i + 1)
        if j != -1:
            inner = s[i + 1:j].strip()
            if inner and re.match(r'^[a-zA-Z0-9\s\-\.\']+$', inner):
                s = (s[:i].rstrip() + s[j + 1:]).strip()
    # 半角括弧
    if s and '(' in s:
        i = s.rfind('(')
        j = s.find(')', i + 1)
        if j != -1:
            inner = s[i + 1:j].strip()
            if inner and re.match(r'^[a-zA-Z0-9\s\-\.\']+$', inner):
                s = (s[:i].rstrip() + s[j + 1:]).strip()
    return s


def strip_enlink(s: str) -> str:
    """
    Wikipedia の {{enlink|英語版タイトル|表示}} を削除する（表示は残さずタグごと除去）。
    例: ヘアフォード司教{{enlink|Bishop of Hereford (Robin Hood)|Bishop of Hereford}} → ヘアフォード司教
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'enlink'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_kirokijinbutsu(s: str) -> str:
    """
    Wikipedia の {{軌跡人物|表示名}} を表示名に置換する。
    例: {{軌跡人物|エステル・ブライト}} → エステル・ブライト
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = '軌跡人物'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len] == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            content = s[param_start:k].strip()
            result.append(content)
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def _template_first_param(s: str, param_start: int, k: int) -> str:
    """テンプレート内の最初の | の手前（第1パラメータ）を返す。ネスト外の | のみ対象。"""
    content = s[param_start:k]
    first_pipe = len(content)
    pos = 0
    depth = 0
    while pos < len(content):
        if pos < len(content) - 1 and content[pos:pos + 2] == '{{':
            depth += 1
            pos += 2
        elif pos < len(content) - 1 and content[pos:pos + 2] == '}}':
            depth -= 1
            pos += 2
        elif content[pos] == '|' and depth == 0:
            first_pipe = pos
            break
        else:
            pos += 1
    return content[:first_pipe].strip()


def _template_last_param(s: str, param_start: int, k: int) -> str:
    """テンプレート内の最後の | より後（最後のパラメータ）を返す。ネスト外の | のみ対象。"""
    content = s[param_start:k]
    last_pipe = -1
    pos = 0
    depth = 0
    while pos < len(content):
        if pos < len(content) - 1 and content[pos:pos + 2] == '{{':
            depth += 1
            pos += 2
        elif pos < len(content) - 1 and content[pos:pos + 2] == '}}':
            depth -= 1
            pos += 2
        elif content[pos] == '|' and depth == 0:
            last_pipe = pos
            pos += 1
        else:
            pos += 1
    if last_pipe >= 0:
        return content[last_pipe + 1:].strip()
    return content.strip()


def strip_yomi(s: str) -> str:
    """
    Wikipedia の {{読み|表記|表示読み}} を表示読みに置換する。
    例: {{読み|ぬ〜べ〜|ぬーべー}} → ぬーべー
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = '読み'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len] == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            result.append(_template_last_param(s, param_start, k))
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_color(s: str) -> str:
    """
    Wikipedia の {{color|色|表示}} を表示に置換する。
    例: {{color|blue|ファイヤーSHIN-MEN ゴゥ}} → ファイヤーSHIN-MEN ゴゥ
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'color'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            result.append(_template_last_param(s, param_start, k))
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_font_color(s: str) -> str:
    """
    Wikipedia の {{Font color|色|表示}} を表示に置換する。
    例: 柳 踏青　{{Font color|red|(死亡)}} → 柳 踏青　(死亡)
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'Font color'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag.lower() and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            result.append(_template_last_param(s, param_start, k))
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_weight(s: str) -> str:
    """
    Wikipedia の {{weight|...|表示}} を表示に置換する。
    例: ...{{weight|normal|（結婚前）→}}... → ...（結婚前）→...
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'weight'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            result.append(_template_last_param(s, param_start, k))
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_fontsize(s: str) -> str:
    """
    Wikipedia の {{fontsize|...|表示}} を表示に置換する。
    例: アマシス{{fontsize|small|(英語版)}}（イアフメス2世）→ アマシス(英語版)（イアフメス2世）
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'fontsize'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            result.append(_template_last_param(s, param_start, k))
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_abbr(s: str) -> str:
    """
    Wikipedia の {{abbr|表示テキスト|説明}} を表示テキスト（第1パラメータ）に置換する。
    例: ナンバー{{abbr|86|エイティシックス}}（ファニー・フルブライト）→ ナンバー86（ファニー・フルブライト）
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'abbr'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            result.append(_template_first_param(s, param_start, k))
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_flagicon(s: str) -> str:
    """
    Wikipedia の {{flagicon|...}} を削除する。
    例: キン肉万太郎 {{flagicon|JPN}} → キン肉万太郎
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'flagicon'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_small(s: str) -> str:
    """
    Wikipedia の {{small|...}} を中身に置換する。
    例: コナン（{{small|英：}}Conan）→ コナン（英：Conan）
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'small'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            content = s[param_start:k].strip()
            result.append(content)
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_nobold(s: str) -> str:
    """
    Wikipedia の {{nobold|...}} を削除する。
    例: ウォレス・ブリーン博士{{nobold|（）}} → ウォレス・ブリーン博士
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'nobold'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_wiki_bold(s: str) -> str:
    """
    Wikipedia の '''太字''' マーカーを削除する。
    例: '''火の王アズロン（'''{{Lang-en|Azulon}}'''）''' → 火の王アズロン（Azulon）
    """
    return s.replace("'''", "")


def _strip_simple_template(s: str, tag: str) -> str:
    """{{TAG}} または {{TAG|...}} を削除する。ネストした {{ }} に対応。"""
    result = []
    i = 0
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len] == tag:
            after_tag = i + 2 + tag_len
            if after_tag < len(s) and s[after_tag] == '}':
                if after_tag + 1 < len(s) and s[after_tag:after_tag + 2] == '}}':
                    i = after_tag + 2
                    continue
            if after_tag < len(s) and s[after_tag] == '|':
                param_start = after_tag + 1
                depth = 1
                k = param_start
                while k < len(s) and depth > 0:
                    if k < len(s) - 1 and s[k:k + 2] == '{{':
                        depth += 1
                        k += 2
                    elif k < len(s) - 1 and s[k:k + 2] == '}}':
                        depth -= 1
                        k += 2
                    else:
                        k += 1
                i = k
                while i < len(s) and s[i] == '}':
                    i += 1
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_syc(s: str) -> str:
    """{{SYC}} / {{SYC|...}} を削除。例: ヘタリア,{{SYC}} → ヘタリア,"""
    return _strip_simple_template(s, 'SYC')


def strip_kia(s: str) -> str:
    """{{KIA}} / {{KIA|...}} を削除。例: Doctor Venom{{KIA}} → Doctor Venom"""
    return _strip_simple_template(s, 'KIA')


def strip_full(s: str) -> str:
    """{{Full|...}} を削除。例: エミリー・ブルックス{{Full|date=2017年7月}} → エミリー・ブルックス"""
    return _strip_simple_template(s, 'Full')


def strip_vanchor(s: str) -> str:
    """{{Vanchor|...}} を削除。例: {{Vanchor|真奥 貞夫}} → 空（タグのみの行は空になる）"""
    return _strip_simple_template(s, 'Vanchor')


def strip_r(s: str) -> str:
    """
    Wikipedia の {{R|...}} 参照タグを削除する。
    例: バット将軍{{R|大全83}}{{R|全書87}} → バット将軍
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    while i < len(s):
        if i <= len(s) - 5 and s[i:i + 2] == '{{' and s[i + 2].lower() == 'r' and s[i + 3] == '|':
            param_start = i + 4
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_yoshuttei(s: str) -> str:
    """
    Wikipedia の {{要出典|...}} / {{要出典 | ...}} を表示テキストに置き換えまたは削除する。
    {{要出典|=かなめ|date=...}} のように先頭が |=表示 の場合は表示テキスト（かなめ）を残す。
    それ以外はタグごと削除。例: ソン・マンホ{{要出典 | date = 2017年9月}} → ソン・マンホ
    タグ直後のスペースに対応。ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = '要出典'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len] == tag:
            pipe_pos = i + 2 + tag_len
            while pipe_pos < len(s) and s[pipe_pos] == ' ':
                pipe_pos += 1
            if pipe_pos < len(s) and s[pipe_pos] == '|':
                param_start = pipe_pos + 1
                depth = 1
                k = param_start
                while k < len(s) and depth > 0:
                    if k < len(s) - 1 and s[k:k + 2] == '{{':
                        depth += 1
                        k += 2
                    elif k < len(s) - 1 and s[k:k + 2] == '}}':
                        depth -= 1
                        k += 2
                    else:
                        k += 1
                # 先頭が "=表示テキスト" ならそのテキストを残す（| または }} の手前まで）
                replacement = ''
                if param_start < k and s[param_start] == '=':
                    end = param_start + 1
                    pos = param_start + 1
                    depth2 = 0
                    while pos < k:
                        if pos < len(s) - 1 and s[pos:pos + 2] == '{{':
                            depth2 += 1
                            pos += 2
                        elif pos < len(s) - 1 and s[pos:pos + 2] == '}}':
                            depth2 -= 1
                            pos += 2
                        elif (s[pos] == '|' or (pos < len(s) - 1 and s[pos:pos + 2] == '}}')) and depth2 == 0:
                            end = pos
                            break
                        else:
                            pos += 1
                            end = pos
                    replacement = s[param_start + 1:end].strip()
                result.append(replacement)
                i = k
                while i < len(s) and s[i] == '}':
                    i += 1
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_yoshuttei_range(s: str) -> str:
    """
    Wikipedia の {{要出典範囲|...}} を削除する。
    例: 経歴：埼玉県「{{要出典範囲|...|date=2025年10月}}」代表 → 経歴：埼玉県「」代表
    タグ直後のスペースに対応。ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = '要出典範囲'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len] == tag:
            pipe_pos = i + 2 + tag_len
            while pipe_pos < len(s) and s[pipe_pos] == ' ':
                pipe_pos += 1
            if pipe_pos < len(s) and s[pipe_pos] == '|':
                param_start = pipe_pos + 1
                depth = 1
                k = param_start
                while k < len(s) and depth > 0:
                    if k < len(s) - 1 and s[k:k + 2] == '{{':
                        depth += 1
                        k += 2
                    elif k < len(s) - 1 and s[k:k + 2] == '}}':
                        depth -= 1
                        k += 2
                    else:
                        k += 1
                i = k
                while i < len(s) and s[i] == '}':
                    i += 1
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_anchors(s: str) -> str:
    """
    Wikipedia の {{Anchors|...}} を削除する（表示テキストはタグの後ろに続くため、タグだけ除去）。
    例: {{Anchors|乙雅三}}乙 雅三 → 乙 雅三
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'Anchors'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag.lower() and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_vanc(s: str) -> str:
    """
    Wikipedia の {{Vanc|表示テキスト}} を表示テキストだけに置き換える。
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'Vanc'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag.lower() and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            # 第1パラメータ（| の後）の終端: ネスト外の | または }} の手前
            end = k
            pos = param_start
            depth2 = 0
            while pos < k:
                if pos < len(s) - 1 and s[pos:pos + 2] == '{{':
                    depth2 += 1
                    pos += 2
                elif pos < len(s) - 1 and s[pos:pos + 2] == '}}':
                    if depth2 == 0:
                        end = pos
                        break
                    depth2 -= 1
                    pos += 2
                elif s[pos] == '|' and depth2 == 0:
                    end = pos
                    break
                else:
                    pos += 1
                    end = pos
            result.append(s[param_start:end].strip())
            i = k
            # 余分な閉じ括弧 } が続く場合はすべてスキップ（}} の後の } が残らないように）
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_wiki_links(s: str) -> str:
    """
    Wikipedia の [[リンク]] または [[リンク|表示テキスト]] を表示テキストだけに置き換える。
    カッコ [[]] を除去する。
    """
    result = []
    i = 0
    while i < len(s):
        if i <= len(s) - 4 and s[i:i + 2] == '[[':
            end = s.find(']]', i + 2)
            if end == -1:
                result.append(s[i])
                i += 1
                continue
            content = s[i + 2:end]
            # [[リンク|表示]] は最初の | がリンクと表示の区切り。表示内に | が含まれる（例: {{読み仮名|表記|読み}}）ので rfind は使わない
            first_pipe = content.find('|')
            if first_pipe >= 0:
                display = content[first_pipe + 1:].strip()
            else:
                display = content.strip()
            result.append(display)
            i = end + 2
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_en(s: str) -> str:
    """
    Wikipedia の {{en|...}} を削除する。
    例: レディ {{en|(lady)}} → レディ
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    while i < len(s):
        if i <= len(s) - 5 and s[i:i + 2] == '{{' and s[i + 2:i + 4].lower() == 'en' and (i + 4 < len(s) and s[i + 4] == '|'):
            param_start = i + 5
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_lang_xx(s: str) -> str:
    """
    Wikipedia の {{lang-XX|...}} / {{Lang-XX|...}} を削除する（外国語表記は残さない）。
    lang-pt, lang-sv, lang-fi-short, Lang-en など、lang- で始まるタグをすべて削除。
    例: 東のエデン,{{lang-pt|Juiz}} → 東のエデン,  ムーミントロール（{{lang-sv|Mumintrollet}} → ムーミントロール（
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    while i < len(s):
        if i <= len(s) - 8 and s[i:i + 2] == '{{' and s[i + 2:i + 7].lower() == 'lang-':
            pipe_pos = i + 7
            while pipe_pos < len(s) and s[pipe_pos] not in '|}' and (s[pipe_pos].isalnum() or s[pipe_pos] == '-'):
                pipe_pos += 1
            if pipe_pos < len(s) and s[pipe_pos] == '|':
                param_start = pipe_pos + 1
                depth = 1
                k = param_start
                while k < len(s) and depth > 0:
                    if k < len(s) - 1 and s[k:k + 2] == '{{':
                        depth += 1
                        k += 2
                    elif k < len(s) - 1 and s[k:k + 2] == '}}':
                        depth -= 1
                        k += 2
                    else:
                        k += 1
                i = k
                while i < len(s) and s[i] == '}':
                    i += 1
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_lang_en_short(s: str) -> str:
    """
    Wikipedia の {{lang-en-short|表示テキスト|...}} を表示テキストに置き換える。
    例: ナウシカ（{{lang-en-short|Nausicaä|links=no}}）→ ナウシカ（Nausicaä）
    ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'lang-en-short'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len + 1) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag and s[i + 2 + tag_len] == '|':
            param_start = i + 2 + tag_len + 1
            depth = 1
            k = param_start
            while k < len(s) and depth > 0:
                if k < len(s) - 1 and s[k:k + 2] == '{{':
                    depth += 1
                    k += 2
                elif k < len(s) - 1 and s[k:k + 2] == '}}':
                    depth -= 1
                    k += 2
                else:
                    k += 1
            # 第1パラメータ（最初の | の手前まで）が表示テキスト
            end = k
            pos = param_start
            depth2 = 0
            while pos < k:
                if pos < len(s) - 1 and s[pos:pos + 2] == '{{':
                    depth2 += 1
                    pos += 2
                elif pos < len(s) - 1 and s[pos:pos + 2] == '}}':
                    depth2 -= 1
                    pos += 2
                elif s[pos] == '|' and depth2 == 0:
                    end = pos
                    break
                else:
                    pos += 1
            result.append(s[param_start:end].strip())
            i = k
            while i < len(s) and s[i] == '}':
                i += 1
            continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_lang(s: str) -> str:
    """
    Wikipedia の {{lang|言語コード|表示テキスト}} を表示テキストだけに置き換える。全言語対応。
    例: エルキュール・ポアロ（{{lang|en|Hercule Poirot}}）→ エルキュール・ポアロ（Hercule Poirot）
    タグ直後のスペースにも対応。ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'lang'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag:
            pipe_pos = i + 2 + tag_len
            while pipe_pos < len(s) and s[pipe_pos] == ' ':
                pipe_pos += 1
            if pipe_pos < len(s) and s[pipe_pos] == '|':
                param_start = pipe_pos + 1
                depth = 1
                k = param_start
                while k < len(s) and depth > 0:
                    if k < len(s) - 1 and s[k:k + 2] == '{{':
                        depth += 1
                        k += 2
                    elif k < len(s) - 1 and s[k:k + 2] == '}}':
                        depth -= 1
                        k += 2
                    else:
                        k += 1
                # 第2パラメータ（2番目の | の後）が表示テキスト
                first_pipe = s.find('|', param_start)
                if param_start <= first_pipe < k:
                    text_start = first_pipe + 1
                    depth2 = 0
                    pos = text_start
                    end = k
                    while pos < k:
                        if pos < len(s) - 1 and s[pos:pos + 2] == '{{':
                            depth2 += 1
                            pos += 2
                        elif pos < len(s) - 1 and s[pos:pos + 2] == '}}':
                            if depth2 == 0:
                                end = pos
                                break
                            depth2 -= 1
                            pos += 2
                        elif s[pos] == '|' and depth2 == 0:
                            end = pos
                            break
                        else:
                            pos += 1
                            end = pos
                    result.append(s[text_start:end].strip())
                i = k
                while i < len(s) and s[i] == '}':
                    i += 1
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_llang(s: str) -> str:
    """
    Wikipedia の {{llang|言語コード|表示テキスト}} を表示テキストだけに置き換える。
    全言語対応。例: チェ・リム（{{llang|ko|채림}}）［Chae Lim］→ チェ・リム（채림）［Chae Lim］
    タグ直後のスペースにも対応。ネストした {{ }} に対応する。
    """
    result = []
    i = 0
    tag = 'llang'
    tag_len = len(tag)
    while i < len(s):
        if i <= len(s) - (2 + tag_len) and s[i:i + 2] == '{{' and s[i + 2:i + 2 + tag_len].lower() == tag:
            pipe_pos = i + 2 + tag_len
            while pipe_pos < len(s) and s[pipe_pos] == ' ':
                pipe_pos += 1
            if pipe_pos < len(s) and s[pipe_pos] == '|':
                param_start = pipe_pos + 1
                depth = 1
                k = param_start
                while k < len(s) and depth > 0:
                    if k < len(s) - 1 and s[k:k + 2] == '{{':
                        depth += 1
                        k += 2
                    elif k < len(s) - 1 and s[k:k + 2] == '}}':
                        depth -= 1
                        k += 2
                    else:
                        k += 1
                first_pipe = s.find('|', param_start)
                if param_start <= first_pipe < k:
                    text_start = first_pipe + 1
                    depth2 = 0
                    pos = text_start
                    end = k
                    while pos < k:
                        if pos < len(s) - 1 and s[pos:pos + 2] == '{{':
                            depth2 += 1
                            pos += 2
                        elif pos < len(s) - 1 and s[pos:pos + 2] == '}}':
                            if depth2 == 0:
                                end = pos
                                break
                            depth2 -= 1
                            pos += 2
                        elif s[pos] == '|' and depth2 == 0:
                            end = pos
                            break
                        else:
                            pos += 1
                            end = pos
                    result.append(s[text_start:end].strip())
                i = k
                while i < len(s) and s[i] == '}':
                    i += 1
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_trailing_voice_paren(s: str) -> str:
    """
    末尾の「（声：…）」または (声：…) を削除する。声優表記はキャラ名ではないため除去。
    例: 香田 ちるみ（こうだ ちるみ）（声：斎藤桃子）→ 香田 ちるみ（こうだ ちるみ）
    """
    # 全角 （声：
    voice_marker = '（声：'
    if voice_marker in s:
        i = s.rfind(voice_marker)
        j = s.find('）', i + len(voice_marker))
        if j != -1:
            s = (s[:i].rstrip() + s[j + 1:]).strip()
    # 半角 (声：
    voice_marker_h = '(声：'
    if voice_marker_h in s:
        i = s.rfind(voice_marker_h)
        j = s.find(')', i + len(voice_marker_h))
        if j != -1:
            s = (s[:i].rstrip() + s[j + 1:]).strip()
    return s


def strip_trailing_cast_paren(s: str) -> str:
    """
    末尾の「（演：…）」または (演：…) を削除する。役者表記はキャラ名ではないため除去。
    例: ハナ（演：木内晶子）→ ハナ
    """
    cast_marker = '（演：'
    if cast_marker in s:
        i = s.rfind(cast_marker)
        j = s.find('）', i + len(cast_marker))
        if j != -1:
            s = (s[:i].rstrip() + s[j + 1:]).strip()
    cast_marker_h = '(演：'
    if cast_marker_h in s:
        i = s.rfind(cast_marker_h)
        j = s.find(')', i + len(cast_marker_h))
        if j != -1:
            s = (s[:i].rstrip() + s[j + 1:]).strip()
    return s


def strip_trailing_voice_dash(s: str) -> str:
    """
    「 - 声：…」「 - 演：…」を削除する。声優・演者表記はキャラ名ではないため除去。
    例: スコア - 声：斎藤晴彦 → スコア、アキラ - 演：宮川彬良 → アキラ
    """
    for marker in (' - 声：', ' - 演：'):
        if marker in s:
            s = s[:s.rfind(marker)].strip()
    return s


def strip_border_size(s: str) -> str:
    """
    Wikipedia の画像サイズ指定 border|NxNpx を削除する。
    例: border|22x20px 神聖ローマ → 神聖ローマ
    """
    s = re.sub(r'border\|\d+x\d+px\s*', '', s)
    return s.strip()


def strip_frame_pixel_prefix(s: str) -> str:
    """
    画像・フレーム指定の装飾を先頭から削除する。
    例: 右|フレームなし|250x250ピクセルノーマ・デズモンド → ノーマ・デズモンド
    """
    s = re.sub(r'^.*?\d+[x×]?\d*ピクセル', '', s)
    return s.strip()


def strip_empty_paren(s: str) -> str:
    """
    空の括弧「（）」「()」を削除する。
    例: タイリー（）→ タイリー
    """
    while '（）' in s:
        s = s.replace('（）', '').strip()
    while '()' in s:
        s = s.replace('()', '').strip()
    return s


def strip_trailing_yomigana_paren(s: str) -> str:
    """
    末尾の「（よみがな）」または (よみがな) を削除する。
    例: 魚住 陸生（うおずみ りくお）→ 魚住 陸生。浅月 香介 (あさづき こうすけ) → 浅月 香介
    括弧内がひらがな・カタカナ・ー・・・スペースのみの場合に除去する。全角・半角どちらも対応。
    """
    yomigana_re = re.compile(r'^[ぁ-んァ-ンー・\s]+$')
    # 全角括弧
    if s and '（' in s:
        i = s.rfind('（')
        j = s.find('）', i + 1)
        if j != -1:
            inner = s[i + 1:j]
            if inner and yomigana_re.match(inner):
                s = (s[:i].rstrip() + s[j + 1:]).strip()
    # 半角括弧
    if s and '(' in s:
        i = s.rfind('(')
        j = s.find(')', i + 1)
        if j != -1:
            inner = s[i + 1:j]
            if inner and yomigana_re.match(inner):
                s = (s[:i].rstrip() + s[j + 1:]).strip()
    return s


def strip_html_comments(s: str) -> str:
    """HTMLコメント <!-- ... --> を除去する。"""
    result = []
    i = 0
    while i < len(s):
        if i <= len(s) - 7 and s[i:i + 4] == '<!--':
            k = s.find('-->', i + 4)
            if k != -1:
                i = k + 3
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_span(s: str) -> str:
    """
    <span style="...">...</span> などの span タグを除去し、内側のテキストのみ残す。
    ネストした <span> に対応する。
    """
    result = []
    i = 0
    while i < len(s):
        if i <= len(s) - 6 and s[i:i + 5].lower() == '<span':
            j = i + 5
            while j < len(s):
                if s[j] == '"':
                    j += 1
                    while j < len(s) and s[j] != '"':
                        j += 1
                    if j < len(s):
                        j += 1
                    continue
                if s[j] == '>':
                    break
                j += 1
            if j >= len(s):
                result.append(s[i])
                i += 1
                continue
            content_start = j + 1
            depth = 1
            pos = content_start
            content_end = -1
            while pos < len(s) and depth > 0:
                close_idx = s.find('</span>', pos)
                open_idx = s.find('<span', pos)
                if close_idx == -1:
                    break
                if open_idx == -1 or close_idx < open_idx:
                    depth -= 1
                    if depth == 0:
                        content_end = close_idx
                        break
                    pos = close_idx + 7
                else:
                    depth += 1
                    pos = open_idx + 5
            if content_end != -1:
                result.append(strip_span(s[content_start:content_end]))
                i = content_end + 7
                continue
        result.append(s[i])
        i += 1
    return ''.join(result).strip()


def strip_span_lang_html(s: str) -> str:
    """
    HTML の <span lang="ko">...</span> / <span lang="zh">...</span> などを除去する。
    外国語表記は残さず、日本語のみ残す。例: レニ・ハルシュタイル（<span lang="ko">레니 할슈타일</span>、Lenni Halshteil、<span lang="zh">雷妮・哈修泰爾</span>）→ レニ・ハルシュタイル（、Lenni Halshteil、）
    """
    s = re.sub(r'<span\s+lang="[^"]*">[^<]*</span>', '', s)
    return s.strip()


def strip_paren_if_no_japanese(s: str) -> str:
    """
    末尾の「（…）」の括弧内に日本語（ひらがな・カタカナ・漢字）が1字もない場合は括弧ごと削除する。
    例: レニ・ハルシュタイル（、Lenni Halshteil、）→ レニ・ハルシュタイル
    """
    if not s or '（' not in s:
        return s
    i = s.rfind('（')
    j = s.find('）', i + 1)
    if j == -1:
        return s
    inner = s[i + 1:j]
    if not re.search(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]', inner):
        s = (s[:i].rstrip() + s[j + 1:]).strip()
    return s


def split_multi_names(s: str) -> list[str]:
    """
    「、」「＆」「&」「 / 」で区切られた複数キャラ名を分割し、空白除去したリストで返す。
    """
    parts = re.split(r'[、＆&]|\s*/\s*', s)
    return [p.strip() for p in parts if p.strip()]


def clean_wiki_content(s: str) -> str:
    """
    Wiki行のテキストにタグ除去・正規化を順に適用する。
    追加・並び替え時は括弧の数え間違いが起きない。
    """
    s = strip_efn(s)
    s = strip_sfn(s)
    s = strip_refnest(s)
    s = strip_kari_link(s)
    s = strip_wiki_links(s)
    s = strip_yomigana(s)
    s = strip_yomigana_ruby_fushiyo(s)
    s = strip_ruby(s)
    s = strip_vanc(s)
    s = strip_yoshuttei(s)
    s = strip_yoshuttei_range(s)
    s = strip_lang_xx(s)
    s = strip_lang(s)
    s = strip_llang(s)
    s = strip_en(s)
    s = strip_r(s)
    s = strip_nobold(s)
    s = strip_syc(s)
    s = strip_kia(s)
    s = strip_full(s)
    s = strip_vanchor(s)
    s = strip_wiki_bold(s)
    s = strip_small(s)
    s = strip_flagicon(s)
    s = strip_kirokijinbutsu(s)
    s = strip_yomi(s)
    s = strip_color(s)
    s = strip_font_color(s)
    s = strip_weight(s)
    s = strip_fontsize(s)
    s = strip_abbr(s)
    s = strip_font_template(s)
    s = strip_hojo_kanji_font(s)
    s = strip_hash_tag(s)
    s = strip_enlink(s)
    s = strip_ill2(s)
    s = strip_anchors(s)
    s = strip_visible_anchor(s)
    s = strip_ref(s)
    s = strip_html_comments(s)
    s = strip_span_lang_html(s)
    s = strip_span(s)
    s = strip_trailing_voice_paren(s)
    s = strip_trailing_cast_paren(s)
    s = strip_trailing_voice_dash(s)
    s = strip_trailing_yomigana_paren(s)
    s = strip_trailing_latin_paren(s)
    s = strip_paren_if_no_japanese(s)
    s = strip_border_size(s)
    s = strip_frame_pixel_prefix(s)
    s = strip_empty_paren(s)
    return s.strip()


def extract_from_wiki(text: str) -> list[str]:
    """Wiki構文から登場人物名の行（内容のみ）を抽出。専用ページの「;」行用。"""
    results = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(';'):
            content = line[1:].strip()
            if not content:
                continue
            content = clean_wiki_content(content)
            if not content:
                continue
            # 「; キャラ名: 説明」の形式ならキャラ名のみにする
            if ':' in content:
                content = content.split(':', 1)[0].strip()
                if not content:
                    continue
            if content.startswith('第') and '話' in content:
                continue
            results.extend(split_multi_names(content))
        elif line.startswith(':*'):
            content = line[2:].strip()
            if not content:
                continue
            content = clean_wiki_content(content)
            if not content:
                continue
            if content.startswith('[[') and content.endswith(']]'):
                continue
            if ' - ' in content:
                char_name = content.split(' - ')[0].strip()
                # 「名前 - 説明」は名前が短い。「3 - 4刷」のような範囲で誤分割されないよう、前半が長すぎる行は名前扱いしない
                if char_name and len(char_name) <= 50:
                    results.extend(split_multi_names(char_name))
    return results


def get_names_for_toujo_page(text: str) -> list[str]:
    """「○○の登場人物」専用ページ: ; で始まる行の内容を名前候補として返す。"""
    return extract_from_wiki(text)


def get_names_for_normal_page(text: str) -> list[str]:
    """通常ページ: 登場人物セクションから名前候補を返す。"""
    section = extract_toujo_section(text)
    if section is None:
        return []
    return extract_from_wiki(section)


def load_excluded_set(path: Path | None) -> tuple[set[str], set[str]]:
    """
    除外ブラックリストを読み込む。JSON の exact のみ使用。
    完全一致と「の」+ exact の末尾一致で判定する。返り値: (exact_set, exact_set)。
    """
    if path is None or not Path(path).is_file():
        return (set(), set())
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    exact_set = set(data.get('exact', []))
    return (exact_set, exact_set)


# 第1話・第14話・第16話） など話数表記にマッチ（末尾の ）は許容）
_EPISODE_NAME_PATTERN = re.compile(r'^第\d+話[）)]?$')
# N回（9回、9回（最終回）など回次表記）にマッチ
_EPISODE_REP_PATTERN = re.compile(r'^\d+回')
# 第N作（第15作「…」など作品回次表記）は対象外
_EPISODE_SAKU_PATTERN = re.compile(r'^第\d+作')
# 最終話「〇〇」などは対象外
_FINAL_EPISODE_PATTERN = re.compile(r'^最終話')
# 声優クレジット（声 - 〇〇、声：〇〇、キャラ名 声：声優名、（声優：〇〇） など）は対象外
_VOICE_CREDIT_PATTERN = re.compile(r'声\s*[-:：]')
_VOICE_SEIYU_PATTERN = re.compile(r'声優\s*[:：]')
# 役者クレジット（演 - 〇〇、〇〇 演 - 〇〇 など）は対象外
_ACTOR_CREDIT_PATTERN = re.compile(r'演\s*[-:：]')


def is_excluded_name(name: str, exact_set: set[str], _suffix_set: set[str]) -> bool:
    """
    名前が除外対象なら True。完全一致・「の」+exact の末尾一致・「第N話」形式・「N回」形式・「第N作」形式・「最終話」形式・「〇〇する/した■■」形式・「登場作品」含む・声優/役者クレジット・数字のみ。
    _suffix_set は load_excluded_set の第2返り値（exact と同じ）で、「の」+exact の末尾一致に使う。
    """
    if name in exact_set:
        return True
    if any(name.endswith('の' + e) for e in exact_set):
        return True
    if name.endswith('に登場したキャラクター'):
        return True
    if name.endswith('おじさん'):
        return True
    # 〇〇の父/の母（括弧付きなど末尾以外も含む。例: ゲンの父（ACT.2〜））
    if 'の父' in name or 'の母' in name:
        return True
    # 数字のみの名前は対象外
    if name and name.isdigit():
        return True
    if _EPISODE_NAME_PATTERN.match(name) is not None:
        return True
    if _EPISODE_REP_PATTERN.match(name) is not None:
        return True
    if _EPISODE_SAKU_PATTERN.match(name) is not None:
        return True
    if _FINAL_EPISODE_PATTERN.match(name) is not None:
        return True
    # 〇〇する■■ / 〇〇した■■（動詞句による説明であり固有名ではない）
    if 'する' in name or 'した' in name:
        return True
    # 登場作品：〇〇（作品一覧などの見出しでありキャラ名ではない）
    if '登場作品' in name:
        return True
    # 見出し・カテゴリ（アニメーション作品、文字設定、ゲーム作品 などが含まれる名前）
    if 'アニメーション作品' in name or '文字設定' in name or 'ゲーム作品' in name:
        return True
    # 声優クレジット（声 - 〇〇、〇〇 声：〇〇、（声優：〇〇））
    if _VOICE_CREDIT_PATTERN.search(name) is not None:
        return True
    if _VOICE_SEIYU_PATTERN.search(name) is not None:
        return True
    # 役者クレジット（演 - 〇〇、〇〇 演 - 〇〇）
    if _ACTOR_CREDIT_PATTERN.search(name) is not None:
        return True
    return False


def parse_args() -> object:
    """コマンドライン引数。"""
    import argparse
    p = argparse.ArgumentParser(
        description='ページから登場人物候補を抽出し（ページ名, 名前）のCSVで出力する（生成AIは使わない）'
    )
    _input_dir = os.environ.get('WIKI_INPUT_DIR', '').strip() or '/out'
    p.add_argument('--input-dir', type=Path, default=Path(_input_dir),
                   help='extract-pages の出力ディレクトリ。既定: WIKI_INPUT_DIR または /out')
    p.add_argument('--output', type=Path, default=None,
                   help='出力CSVパス（既定: <input-dir>/character_candidates.csv）')
    p.add_argument('--exclude-list', type=Path, default=None,
                   help='除外ブラックリスト（JSON）。既定: WIKI_EXCLUDE_LIST または data/excluded_names.json')
    p.add_argument('--output-excluded', type=Path, default=None,
                   help='ブラックリスト該当を書き出すCSV（既定: <outputの同dir>/character_candidates_excluded.csv）')
    return p.parse_args()


def main() -> None:
    """エントリポイント。"""
    args = parse_args()
    input_dir = Path(args.input_dir)
    pages_dir = input_dir / 'pages'
    meta_path = input_dir / 'page_meta.json'
    if args.output is not None:
        output_path = Path(args.output)
    else:
        output_path = input_dir / 'character_candidates.csv'
    _exclude_env = os.environ.get('WIKI_EXCLUDE_LIST', '').strip()
    default_exclude_path = Path(_exclude_env) if _exclude_env else Path(__file__).resolve().parent.parent / 'data' / 'excluded_names.json'
    exclude_list_path = args.exclude_list if args.exclude_list is not None else default_exclude_path
    exact_set, suffix_set = load_excluded_set(exclude_list_path)
    if args.output_excluded is not None:
        output_excluded_path = Path(args.output_excluded)
    else:
        output_excluded_path = output_path.parent / 'character_candidates_excluded.csv'
    if exact_set:
        msg = f'  除外ブラックリスト: {exclude_list_path} 完全一致＆「の」+exact末尾一致 {len(exact_set)}語'
        log(f'{msg}。該当は {output_excluded_path} に取り分け')

    if not pages_dir.is_dir():
        log(f'エラー: ページ用ディレクトリが見つかりません: {pages_dir}')
        sys.exit(1)
    if not meta_path.is_file():
        log(f'エラー: page_meta.json が見つかりません: {meta_path}')
        sys.exit(1)

    with open(meta_path, encoding='utf-8') as f:
        meta = json.load(f)
    main_id_to_title: dict[str, str] = meta['main_id_to_title']
    toujo_page_ids: set[int] = set(meta['toujo_page_ids'])

    log('extract-character-candidates: ページから登場人物候補を抽出')
    with Timer() as total_timer:
        items: list[dict[str, str | list[str]]] = []
        page_files = sorted(pages_dir.glob('*.txt'), key=lambda p: int(p.stem) if p.stem.isdigit() else 0)
        total_pages = len(page_files)
        processed = 0

        for idx, path in enumerate(page_files):
            if not path.stem.isdigit():
                continue
            page_id = int(path.stem)
            page_title = main_id_to_title.get(str(page_id), path.stem)
            page_display = page_title.replace('_', ' ')

            try:
                text = path.read_text(encoding='utf-8')
            except OSError as e:
                log(f'  スキップ {path.name}: 読み込みエラー {e}')
                continue

            is_toujo = page_id in toujo_page_ids
            if is_toujo:
                names = get_names_for_toujo_page(text)
            else:
                names = get_names_for_normal_page(text)

            if not names:
                continue

            items.append({'page_title': page_display, 'names': names})
            processed += 1
            if (idx + 1) % 500 == 0 or (idx + 1) == total_pages:
                log_progress('extract-character-candidates: pages', count=processed, elapsed=total_timer.elapsed)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        row_count = 0
        excluded_count = 0
        with open(output_path, 'w', encoding='utf-8', newline='') as f_out, \
             open(output_excluded_path, 'w', encoding='utf-8', newline='') as f_ex:
            w_out = csv.writer(f_out)
            w_ex = csv.writer(f_ex)
            w_out.writerow(['ページ名', '名前'])
            w_ex.writerow(['ページ名', '名前'])
            for item in items:
                page_title = item['page_title']
                for name in item['names']:
                    if is_excluded_name(name, exact_set, suffix_set):
                        w_ex.writerow([page_title, name])
                        excluded_count += 1
                    else:
                        w_out.writerow([page_title, name])
                        row_count += 1

        log(f'  LLM用: {output_path}, {row_count} 行')
        if excluded_count:
            log(f'  除外取り分け: {output_excluded_path}, {excluded_count} 行')
    log('')
    log(f'  実行時間: {format_elapsed(total_timer.elapsed)} ({total_timer.elapsed:.1f}秒)')


if __name__ == '__main__':
    main()
    sys.exit(0)
