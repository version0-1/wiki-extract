#!/usr/bin/env bash
#
# 初回セットアップ: dumps/ と out/ を自分の権限で作成し、ダンプをダウンロードする。
# 配布先で誰でも同じ手順で使えるように、必ずこのスクリプトを先に実行してから docker compose すること。
#
# 使い方: ./setup.sh [日付]
#   日付なし: latest を取得
#   例: ./setup.sh 20260201
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "1. dumps/ と out/ を作成します（自分の権限で）"
mkdir -p dumps out

if [ -n "$(find dumps -maxdepth 1 -type f 2>/dev/null)" ]; then
  echo "Error: dumps/ に既にファイルがあります。再ダウンロードする場合は古いファイルを削除してから実行してください。"
  echo "  例: rm -f dumps/jawiki-*"
  exit 1
fi

echo "2. ダンプファイルをダウンロードします（数GBのため時間がかかります）"
"$SCRIPT_DIR/download.sh" "$@"

echo ""
echo "セットアップ完了。次のコマンドでコンテナを起動してください:"
echo "  docker compose up -d"
echo "  docker compose exec wiki_extract uv run python -m wiki_extract extract-pages"
echo "  docker compose exec wiki_extract uv run python -m wiki_extract extract-character-candidates"
echo "  docker compose exec wiki_extract uv run python -m wiki_extract ai-characters-filter --input-list /out/character_candidates.csv ..."
echo "  docker compose exec wiki_extract uv run python -m wiki_extract ai-characters-split ..."
