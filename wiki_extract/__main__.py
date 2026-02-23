"""
メインエントリポイント: extract-pages、extract-character-candidates、ai-characters-filter（①）、ai-characters-split（②）をサブコマンドで起動する。

環境変数（GEMINI_API_KEY, LLM_OLLAMA_BASE_URL, LLM_GEMINI_BASE_URL 等）は Docker の場合は docker-compose.yml の env_file: .env からのみ読み込む。Python 側では .env を読まない。
"""

import sys

from wiki_extract.extract.extract_pages import main as main_extract_pages
from wiki_extract.characters.extract_character_candidates import main as main_extract_character_candidates
from wiki_extract.characters.ai_characters_filter import main as main_ai_characters_filter
from wiki_extract.characters.ai_characters_split import main as main_ai_characters_split


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == 'extract-pages':
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        main_extract_pages()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'extract-character-candidates':
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        main_extract_character_candidates()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'ai-characters-filter':
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        main_ai_characters_filter()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'ai-characters-split':
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        main_ai_characters_split()
    else:
        print('Usage: python -m wiki_extract extract-pages [--data-dir DIR] [--output-dir DIR]', file=sys.stderr)
        print('       python -m wiki_extract extract-character-candidates [--input-dir DIR] [--output CSV]', file=sys.stderr)
        print('       python -m wiki_extract ai-characters-filter [--input-list CSV] [--output-target CSV] [--output-excluded CSV] ...', file=sys.stderr)
        print('       python -m wiki_extract ai-characters-split --input-target CSV [--output CSV] ...', file=sys.stderr)
        print('', file=sys.stderr)
        print('  extract-pages:          ダンプから対象ページのWikiソースをページごとファイルで出力', file=sys.stderr)
        print('  extract-character-candidates: ページから登場人物候補を抽出しCSVで出力（生成AIは使わない）', file=sys.stderr)
        print('  ai-characters-filter:   ① 対象/除外をLLMで判定し、2種のCSVを出力', file=sys.stderr)
        print('  ai-characters-split:    ② 対象CSVをLLMで氏名分割し characters.csv を出力', file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
