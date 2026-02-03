# Extract Fictional Character Names from Japanese Wikipedia Dumps

Uses Japanese Wikipedia dumps to extract character names from the "架空の人物" (Fictional people) category and from "登場人物" (Cast) sections of articles, and outputs TSV (work title, character name).

**Pipeline details / role of each dump**: [docs/DETAIL_en.md](docs/DETAIL_en.md) (English)

This tool was created with Cursor pair programming; please refrain from nitpicking the code.

---

## Required Dump Files

Download the following from [Wikipedia dumps (jawiki)](https://dumps.wikimedia.org/jawiki/) and place them in `dumps/`. Use `latest` unless you need a specific date; if using dated dumps, use the same date for all files.

All four files total about 5GB.

| File | Required | Notes |
|------|----------|-------|
| `*page*.sql.gz` | ✓ | e.g. jawiki-latest-page.sql.gz |
| `*categorylinks*.sql.gz` | ✓ | e.g. jawiki-latest-categorylinks.sql.gz |
| `*pages-articles*.xml` or `*.xml.bz2` | ✓ | Prefer decompressed .xml; otherwise .xml.bz2 (usually use bz2 as-is) |
| `*linktarget*.sql.gz` | ✓ | e.g. jawiki-latest-linktarget.sql.gz |

*pages-articles*.xml is about 20GB when decompressed. You can use it decompressed, but using the bz2 file as-is is usually faster. Other files are used as .gz.

The file contents are also described [here](https://v0-1.net/en/wikipedia-character-names-extraction).

---

## Usage

Expect roughly 1 to several hours depending on the environment.  
Sample output: [sample/fictional_characters_20260202.zip](sample/fictional_characters_20260202.zip) (TSV inside: work title, character name). If you don't need the latest data, use this zip; it contains data as of 2026/02/02.

With Docker:

```bash
docker compose up -d
docker compose exec wiki_extract uv run python -m wiki_extract
```

- Dumps: `./dumps` → `/data` in the container; output: `./out` → `/out`.
- Output file: `out/fictional_characters.tsv` (header: `作品名\tキャラクター名`).

Options (inside container):

```bash
uv run python -m wiki_extract --data-dir /data --output-dir /out --workers 4
```

---

## Output

| File | Content |
|------|---------|
| **fictional_characters.tsv** | TSV of work title and character name (from category + cast sections). |

---

## When Some Works Aren't Extracted

Check the structure of the "登場人物" section on the relevant Wikipedia article and consider adding extraction logic in `wiki_extract/section_parser.py`.

---

# 日本語Wikipediaダンプから架空の人物一覧を抽出する

日本語Wikipediaのダンプを使い、「架空の人物」カテゴリと各作品の「登場人物」セクションからキャラクター名を抽出し、TSV（作品名・キャラクター名）を出力します。

**処理の詳細・各ダンプの役割**: [docs/DETAIL_ja.md](docs/DETAIL_ja.md)

なおこのツールはCursorでバイブコーディング作成したものなので、コードに関する細かいツッコミはなしでお願いします。

---

## 必要なダンプファイル

[Wikipedia](https://dumps.wikimedia.org/jawiki/)から必要なファイルをダウンロードして`dumps/` に以下を置きます。  
特に指定がなければ`latest`を使用してください。  
日付別のファイルを使用する場合はすべて同じ日付のファイルを使用してください。

4つすべて合わせて5GB程度あります。

| ファイル | 必須 | 備考 |
|----------|------|------|
| `*page*.sql.gz` | ○ | 例: jawiki-latest-page.sql.gz |
| `*categorylinks*.sql.gz` | ○ | 例: jawiki-latest-categorylinks.sql.gz |
| `*pages-articles*.xml` または `*.xml.bz2` | ○ | 解凍済み .xml を優先、なければ .xml.bz2 を使用(通常はbz2のまま使用する) |
| `*linktarget*.sql.gz` | ○ | 例: jawiki-latest-linktarget.sql.gz |

*pages-articles*.xmlは解凍すると20GB程度になる巨大ファイルです。  
解凍後のファイルも使えるようになってはいますが、ほとんどの場合bz2のまま使ったほうが処理が高速なので、解凍する必要はありません。

他のファイルもgzのまま使用します。

ファイルの内容は[こちらにも記述してあります。](https://v0-1.net/ja/wikipedia-character-names-extraction)

---

## 使い方

実行環境によりますが、1時間～数時間かかると思ってください。  
最新版が不要な場合は[fictional_characters_20260202.zip](fictional_characters_20260202.zip)が2026/02/02のデータなのでこちらを利用してください。

Docker で実行する場合:

```bash
docker compose up -d
docker compose exec wiki_extract uv run python -m wiki_extract
```

- ダンプは `./dumps` → コンテナ内 `/data`、出力は `./out` → `/out` にマウントされています。
- 出力: `out/fictional_characters.tsv`（1行目ヘッダー `作品名\tキャラクター名`）

オプション（コンテナ内で）:

```bash
uv run python -m wiki_extract --data-dir /data --output-dir /out --workers 4
```

---

## 出力ファイル

| ファイル | 内容 |
|----------|------|
| **fictional_characters.tsv** | 作品名とキャラクター名の TSV（カテゴリ由来 + 登場人物セクション由来） |

---

## うまく取得できない作品がある場合

該当のWikipediaページで登場人物カテゴリーの構造を確認し、wiki_extract/section_parser.pyに取得処理を追加してみてください。
