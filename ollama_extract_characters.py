#!/usr/bin/env python3
"""
Wikipedia の登場人物セクションのテキスト（HTML または Wiki構文）を外部の txt ファイルから読み込み、
Ollama (gemma3:27b) で登場人物名をCSV形式で抽出する。
標準モジュールのみ使用。

使い方: python3 ollama_extract_characters.py <入力txtファイル>
"""

import json
import re
import sys
import urllib.request
import urllib.error
from html.parser import HTMLParser


OLLAMA_URL = 'http://localhost:11434/api/chat'
MODEL = 'gemma3:4b'
BATCH_SIZE = 30

SYSTEM_PROMPT = """あなたはCSVデータ抽出ツールです。
入力された登場人物名リストからCSV形式で出力します。
説明、コメント、感想は一切出力しません。CSVデータのみを出力します。

出力形式:
名前,姓,名

ルール:
- 「姓＋名」に明確に分かれる場合のみ姓・名を記入（表記のまま、読み仮名は不使用）
- 単名・あだ名・境目不明の場合は姓・名を空欄にする → 「名前,,」
- 括弧内の読み仮名は無視する"""

EXAMPLE_INPUT_1 = """山田太郎（やまだ たろう）
ルフィ
田村玲子（たむら れいこ）"""

EXAMPLE_OUTPUT_1 = """名前,姓,名
山田太郎,山田,太郎
ルフィ,,
田村玲子,田村,玲子"""


class DtExtractor(HTMLParser):
    """<dt>タグの内容を抽出する"""

    def __init__(self):
        super().__init__()
        self.in_dt = False
        self.dt_contents = []
        self.current_text = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'dt':
            self.in_dt = True
            self.current_text = ''

    def handle_endtag(self, tag):
        if tag == 'dt' and self.in_dt:
            self.in_dt = False
            text = self.current_text.strip()
            if text:
                self.dt_contents.append(text)

    def handle_data(self, data):
        if self.in_dt:
            self.current_text += data


def extract_from_html(html: str) -> list[str]:
    """HTMLから<dt>タグの内容を抽出"""
    parser = DtExtractor()
    parser.feed(html)
    return parser.dt_contents


def extract_from_wiki(text: str) -> list[str]:
    """Wiki構文から登場人物名を抽出"""
    results = []
    for line in text.splitlines():
        line = line.strip()

        if line.startswith(';'):
            content = line[1:].strip()
            if not content:
                continue
            if content.startswith('第') and '話' in content:
                continue
            results.append(content)

        elif line.startswith(':*'):
            content = line[2:].strip()
            if not content:
                continue
            if content.startswith('[[') and content.endswith(']]'):
                continue
            if ' - ' in content:
                char_name = content.split(' - ')[0].strip()
                if char_name:
                    results.append(char_name)

    return results


def extract_names(data: str) -> list[str]:
    """HTMLかWiki構文かを自動判別して名前を抽出"""
    if '<dt>' in data:
        names = extract_from_html(data)
        print('形式: HTML (<dt>タグ検出)', file=sys.stderr)
    else:
        names = extract_from_wiki(data)
        print('形式: Wiki構文 (;行検出)', file=sys.stderr)
    return names


def call_ollama(user_input: str) -> str:
    """Ollama APIを呼び出してCSVを取得"""
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': EXAMPLE_INPUT_1},
        {'role': 'assistant', 'content': EXAMPLE_OUTPUT_1},
        {'role': 'user', 'content': user_input},
    ]

    body = json.dumps({
        'model': MODEL,
        'messages': messages,
        'stream': False,
        'options': {
            'temperature': 0,
        },
    }, ensure_ascii=False).encode('utf-8')

    req = urllib.request.Request(
        OLLAMA_URL,
        data=body,
        method='POST',
        headers={'Content-Type': 'application/json'},
    )

    with urllib.request.urlopen(req, timeout=300) as res:
        result = json.loads(res.read().decode('utf-8'))

    message = result.get('message', {})
    response = message.get('content')
    if response is None:
        error = result.get('error', 'Unknown error')
        raise RuntimeError(f'Ollama error: {error}')

    return response


def parse_csv_response(response: str) -> list[str]:
    """CSVレスポンスからデータ行を抽出（ヘッダー除去）"""
    lines = []
    for line in response.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if line == '名前,姓,名':
            continue
        if ',' in line:
            lines.append(line)
    return lines


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('Usage: python3 ollama_extract_characters.py <入力txtファイル>')

    input_path = sys.argv[1]
    try:
        with open(input_path, encoding='utf-8') as f:
            data = f.read()
    except OSError as e:
        sys.exit(f'Cannot read file "{input_path}": {e}')

    names = extract_names(data)
    if not names:
        sys.exit('登場人物名が見つかりませんでした')

    print(f'抽出した名前数: {len(names)}', file=sys.stderr)

    all_csv_lines = []
    total_batches = (len(names) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(names), BATCH_SIZE):
        batch = names[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f'処理中: バッチ {batch_num}/{total_batches} ({len(batch)}件)', file=sys.stderr)

        user_input = '\n'.join(batch)

        try:
            response = call_ollama(user_input)
            csv_lines = parse_csv_response(response)
            all_csv_lines.extend(csv_lines)
        except Exception as e:
            print(f'バッチ {batch_num} でエラー: {e}', file=sys.stderr)
            continue

    print('名前,姓,名')
    for line in all_csv_lines:
        print(line)


if __name__ == '__main__':
    main()
