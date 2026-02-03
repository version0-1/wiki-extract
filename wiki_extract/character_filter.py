"""
架空の人物名として不自然なタイトルを除外する。
"""

import re


# キャラ名でないとみなすパターン（除外する）
# 先頭が . または数字（弾薬名 .277_FURY弾 など）
LEADING_DOT_OR_DIGIT = re.compile(r"^[.\d]")
# 末尾が「弾」（銃弾・弾薬）
ENDS_WITH_DAN = re.compile(r"弾$")
# 英数字・記号のみの短いタイトル（.LIVE, .hack など）
ALNUM_ONLY_SHORT = re.compile(r"^[a-zA-Z0-9._\-]+$")


def is_likely_character(title: str) -> bool:
    """
    タイトルが明らかにキャラ名でない（弾薬・商品名など）場合は False を返す。
    fictional_characters 出力のノイズ削減に使用する。
    """
    if not title or len(title) < 2:
        return False
    if LEADING_DOT_OR_DIGIT.search(title):
        return False
    if ENDS_WITH_DAN.search(title):
        return False
    # 英数字・記号のみで 20 文字以下は作品名や略語の可能性が高い（キャラ名は漢字混じりが多い）
    if len(title) <= 20 and ALNUM_ONLY_SHORT.search(title):
        return False
    return True
