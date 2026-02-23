# Extract fictional character names from Japanese Wikipedia dumps

English | [日本語](#日本語)

This tool uses dumps of Japanese Wikipedia to extract character names from the "架空の人物" (Fictional people) category and from "登場人物" (cast) sections on article and cast-list pages.

## Pipeline overview

The pipeline has four stages. Each stage is a separate command because processing is time-consuming.

If you do not need to run `ai-characters-filter` or `ai-characters-split` on the full dataset, edit `out/*.csv` to keep only the rows you need before running those commands.

| Stage | Command | Description | Main output | Typical time |
|-------|---------|-------------|-------------|--------------|
| 1 | **extract-pages** | Extract pages from the "架空の人物" category, cast-list pages, and normal pages that have a cast section; save Wiki source per page. | `out/pages/*.txt`<br>`out/page_meta.json` | ~13 min |
| 2 | **extract-character-candidates** | Extract character name candidates per line. Exclude exact matches and "の" + suffix matches from `excluded_names.json`. | `out/character_candidates.csv`<br>`out/character_candidates_excluded.csv` (excluded items) | ~2 min |
| 3 | **ai-characters-filter** | Use an LLM to decide if each candidate is a name; exclude non-names and sentence fragments. | `out/characters_target.csv`<br>`out/characters_excluded.csv` | ~4.5 h with `--workers 16` (full run) |
| 4 | **ai-characters-split** | Use an LLM to split names into family and given name. | `out/characters.csv` | ~4.5 h with `--workers 16` (full run) |

### Final output (characters.csv)

Accuracy is not 100%. Edit the CSV directly or see *When extraction fails for some works* below if needed.

| Column | Description |
|--------|-------------|
| ページ名 | Wikipedia page title (work title, etc.) |
| キャラクター名 | Extracted character name (as written) |
| 姓 | Family name (blank if not split) |
| 名 | Given name (blank if not split) |
| 氏名フラグ | `True` if treated as a character name, `False` if title/role only |

### Output files

You can use files from the [latest release](https://github.com/version0-1/wiki-extract/releases/latest) if you do not need to regenerate them.

| Path | Stage | Description |
|------|-------|-------------|
| `./out/pages/*.txt` | extract-pages | Wiki source per page |
| `./out/page_meta.json` | extract-pages | Metadata |
| `./out/character_candidates.csv` | extract-character-candidates | Page title, name (candidates before LLM) |
| `./out/character_candidates_excluded.csv` | extract-character-candidates | Excluded items (same name prefix as character_candidates) |
| `./out/characters_target.csv` | ai-characters-filter | Rows classified as character names |
| `./out/characters_excluded.csv` | ai-characters-filter | Rows classified as non-names or not proper nouns |
| `./out/characters.csv` | ai-characters-split | Page title, character name, family name, given name, is_name flag |

### Pipeline and dump details

See [docs/DETAIL_en.md](docs/DETAIL_en.md) (English) or [docs/DETAIL_ja.md](docs/DETAIL_ja.md) (日本語).

## Required dump files

Run `./setup.sh` (Linux) or `.\setup.ps1` (Windows PowerShell) at the project root to download files into `dumps/`. Or place the following in `dumps/` manually from [Wikipedia dumps](https://dumps.wikimedia.org/jawiki/). Use `latest` unless you need a specific date; if using a dated dump, use the same date for all files.

Total size is about 5 GB.

| File | Required | Notes |
|------|----------|-------|
| `*page*.sql.gz` | Yes | e.g. jawiki-latest-page.sql.gz |
| `*categorylinks*.sql.gz` | Yes | e.g. jawiki-latest-categorylinks.sql.gz |
| `*pages-articles*.xml` or `*.xml.bz2` | Yes | Prefer decompressed .xml; otherwise .xml.bz2 (usually use bz2 as-is) |
| `*linktarget*.sql.gz` | Yes | e.g. jawiki-latest-linktarget.sql.gz |

*pages-articles*.xml is very large (~20 GB decompressed). You can use it decompressed, but using the bz2 file as-is is usually faster.

## Quick start

### Requirements

- **Runtime**: Docker. On Windows, use [Docker Desktop](https://www.docker.com/products/docker-desktop/).
- **LLM**: Gemini or Ollama. Choose one; configure in *.env* (see below).

### Setup

Run before starting the container.

Execute `setup.sh` (Linux) or `setup.ps1` (Windows PowerShell) to download dumps and create directories. If you already started the container, recreate `dumps/` and `out/` with your user so they are writable.

On Windows, run the following to avoid execution policy errors:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

As of Feb 2026, about 5 GB is downloaded.

To use a specific dump date:

```bash
# Linux
bash setup.sh 20260201
```

```powershell
# Windows PowerShell (from repo root)
.\setup.ps1 20260201
```

### .env

Copy `.env.example` to `.env`.

**Gemini**: Set `GEMINI_API_KEY` (Vertex AI). For full runs, `gemini-2.5-flash-lite` with `--workers 16` is recommended (~4.5 h).

**Ollama**: Pull a model (default `gemma3:4b`), set `WIKI_LLM_PROVIDER=ollama`. Default URL is `http://host.docker.internal:11434`. On Linux without Docker Desktop, set `LLM_OLLAMA_BASE_URL=http://localhost:11434` if Ollama runs on the host.

### Start container

```bash
cd wiki-extract
docker compose up -d
```

On Linux with Ollama on localhost:

```bash
docker compose -f docker-compose.yml -f docker-compose_linux.yml up -d
```

### Run commands

```bash
docker compose exec wiki_extract uv run python -m wiki_extract <command> [options]
```

- **extract-pages** — Writes Wiki source to `out/pages`. (~1.5 GB as of Feb 2026.)
- **extract-character-candidates** — Builds `out/character_candidates.csv` from pages; strips wiki markup and applies exclude list.
- **ai-characters-filter** — Builds `out/characters_target.csv` from candidates using the LLM. Resumable; delete the output file to start over.
- **ai-characters-split** — Builds `out/characters.csv` (family/given name split). Resumable; delete the output file to start over.

### Options (override .env)

| Option | Default | Description |
|--------|--------|-------------|
| `--provider` | `gemini` | LLM provider. Use `gemini` for parallel full runs. |
| `--model` | Gemini: `gemini-2.5-flash-lite`, Ollama: `gemma3:4b` | Model name. Pull the model first for Ollama. |
| `--batch-size` | `30` | Rows per LLM call. Recommend up to ~50. |
| `--workers` | `1` | Parallel LLM calls. For full run with Gemini, e.g. `--workers 16` (~4.5 h). For Ollama, match GPU count. |
| `--timeout` | `300` | API timeout (seconds). |
| `--exclude-list` | `data/excluded_names.json` | Exclude blacklist (JSON): `{"exact": [...], "suffix": [...]}`. |

## When extraction fails for some works

- Prefer re-running only on the rows you need (edit the CSV) instead of a full re-run.
- If extra text appears after a name (e.g. role text), the LLM may misbehave. Remove such lines and re-run.
- You can edit prompts under `data/prompts` or add terms to `data/excluded_names.json` (exact and "の" + suffix). Check `character_candidates_excluded.csv` and `characters_excluded.csv`, then re-run `extract-character-candidates` to apply exclude-list changes.

---

<a id="日本語"></a>
# 日本語Wikipediaダンプから架空の人物一覧を抽出する

日本語Wikipediaのダンプを使い、「架空の人物」カテゴリと各作品の「登場人物」セクションからキャラクター名を抽出します。

なおこのツールはCursorでバイブコーディング作成したものなので、コードに関する細かいツッコミはなしでお願いします。

## 処理一覧

処理は4段階です。概要は次の表のとおりです。
処理時間が長いため、それぞれ別コマンドになっています。

`ai-characters-filter`と`ai-characters-split`は全量実行の必要がなければ、`out/*.csv`を直接編集して必要な行以外削除してからの実行をおすすめします。

| 段階 | コマンド | 処理内容 | 主な出力 | 目安時間 |
|------|----------|----------|----------|----------|
| 1 | **extract-pages** | ダンプから「架空の人物」カテゴリ・登場人物専用ページ・登場人物セクションがある通常ページを抽出し、Wikiソースをページ単位で保存する。 | `out/pages/*.txt`<br>`out/page_meta.json` | 約13分 |
| 2 | **extract-character-candidates** | 登場人物候補を行で抽出。<br>`excluded_names.json`に記載した単語の完全一致・「の」+語尾一致を除外する。| `out/character_candidates.csv`<br>`out/character_candidates_excluded.csv`（除外項目一覧） | 約2分 |
| 3 | **ai-characters-filter** | LLMで名前かどうか判定し、名前でないもの・文章断片を除外する。 | `out/characters_target.csv`<br>`out/characters_excluded.csv` | `--workers 16`で約4時間半（全量） |
| 4 | **ai-characters-split** | LLMで姓・名に分割する。 | `out/characters.csv` | `--workers 16`で約4時間半（全量） |

### 最終成果物（characters.csv）

精度は100%ではありません。
必要であればCSVの直接編集、または後述の`うまく取得できない作品がある場合`を参照してください。

| 列名 | 説明 |
|------|------|
| ページ名 | Wikipediaのページ名（作品名など） |
| キャラクター名 | 抽出されたキャラクター名（表記のまま） |
| 姓 | 姓に相当する部分（分割不可なら空欄） |
| 名 | 名に相当する部分（分割不可なら空欄） |
| 氏名フラグ | キャラクター名（架空含む）なら`True`、役職・肩書きのみなら`False` |

### 出力ファイル

再作成の必要がなければ[最新リリース](https://github.com/version0-1/wiki-extract/releases/latest)のファイルを利用してください。

| ファイルパス | 作成工程 | 内容説明 |
|---|---|---|
| `./out/pages/*.txt` | extract-pages | ページごとの Wiki ソース |
| `./out/page_meta.json` | extract-pages | メタ情報 |
| `./out/character_candidates.csv` | extract-character-candidates | ページ名, 名前（LLM判定前候補リスト） |
| `./out/character_candidates_excluded.csv` | extract-character-candidates | 除外された項目リスト（character_candidates.csv と同名プレフィックス） |
| `./out/characters_target.csv` | ai-characters-filter | キャラ名として認識されたもののリスト |
| `./out/characters_excluded.csv` | ai-characters-filter | 名前でない・固有名詞でないと判定された項目リスト |
| `./out/characters.csv` | ai-characters-split | ページ名, キャラクター名, 姓, 名, 氏名フラグ（氏名分割後リスト） |

### 処理の詳細・各ダンプの役割

[docs/DETAIL_ja.md](docs/DETAIL_ja.md)を参照

## 必要なダンプファイル

プロジェクトルートで `./setup.sh`（Linux）または `.\setup.ps1`（Windows PowerShell）を実行すると `dumps/` にダウンロードされます。
手動で取得する場合は [Wikipedia](https://dumps.wikimedia.org/jawiki/) から `dumps/` に以下を置いてください。  
特に指定がなければ `latest` を使用してください。日付別のファイルを使用する場合はすべて同じ日付にしてください。

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

## クイックスタート

### 環境準備

#### 実行環境

Dockerコンテナを使用しています。
`Windows`の場合は[Docker Desktop](https://www.docker.com/ja-jp/products/docker-desktop/)の利用を想定。

#### 生成AI

GeminiとOllamaに対応しています。どちらか一方を選んでください。具体的な設定は次の「.envの作成」で行います。

### セットアップ

コンテナ起動前に実行してください。

`setup.sh`（Linux）または `setup.ps1`（Windows PowerShell）を実行し、必要なファイルのダウンロードとディレクトリの作成を行います。
実行前にコンテナを起動してしまった場合は`dumps/` と `out/` を自分の権限で再作成してください。

`Windows`の場合はそのままだと権限エラーになるため、以下を実行してください。

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

2026年2月現在で`約5GB`がダウンロードされます。

#### ダンプファイルの日付を指定したい場合

`latest`以外を使用したい場合は[過去のダンプファイルの日付](https://dumps.wikimedia.org/jawiki/)を確認して指定してください。

```bash
# Linux
bash setup.sh 20260201
```

```powershell
# Windows PowerShell（リポジトリのルートで）
.\setup.ps1 20260201
```

### .envの作成

`.env.example`をコピーして`.env`を作成します。

#### Geminiを利用する場合

GCPのVertexAIでAPI Keyを発行し、`.env`の`GEMINI_API_KEY`を設定してください。

```bash
GEMINI_API_KEY=your_vertex_api_key_here

# 別リージョンに接続する場合は設定
LLM_GEMINI_BASE_URL=https://us-central1-aiplatform.googleapis.com

# 別モデルを使用したい場合は設定
WIKI_LLM_DEFAULT_MODEL_GEMINI=gemini-2.5-flash
```

全量を処理する場合、`--worker 16`で4時間半ほどかかるので`Flash Lite`推奨です。

#### Ollamaを利用する場合

Ollamaで使用するモデルをダウンロードしておいてください。
デフォルトは`gemma3:4b`になっています。

```bash
ollama pull gemma3:4b
```

`.env`の`WIKI_LLM_PROVIDER`を`ollama`に変更します。

```bash
WIKI_LLM_PROVIDER=ollama

# 別モデルを使用したい場合は設定
WIKI_LLM_DEFAULT_MODEL_OLLAMA=gemma3:12b
```

Ollamaの接続先の既定は `http://host.docker.internal:11434`です。
LinuxでDocker Desktopを使用せず環境を構築している場合は`LLM_OLLAMA_BASE_URL`を`localhost`に変更してください。

```bash
# LinuxでDocker Desktopを使用していない場合に設定
LLM_OLLAMA_BASE_URL=http://localhost:11434
```

### コンテナの起動

カレントディレクトリで起動してください。
```bash
cd wiki-extract
docker compose up -d
```

LinuxでOllamaを`localhost`実行したい場合は`docker-compose_linux.yml`を渡します。

```bash
cd wiki-extract
docker compose -f docker-compose.yml -f docker-compose_linux.yml up -d
```

### コマンド実行

#### 基本

実行する機能名とオプションを指定して実行してください。

```bash
docker compose exec wiki_extract uv run python -m wiki_extract 【機能名】 【各種オプション】
```

#### extract-pages

`out/pages`に`Wiki構文のソース`を出力します。
2026年2月現在で`約1.5GB`のファイルが作成されます。

```bash
docker compose exec wiki_extract uv run python -m wiki_extract extract-pages
```

#### extract-character-candidates

`extract-pages`で作成したファイルから`out/character_candidates.csv`を作成します。
正規表現で不要なWiki構文のコードや固有名詞ではない文字列を分離します。

```bash
docker compose exec wiki_extract uv run python -m wiki_extract extract-character-candidates
```

#### ai-characters-filter

`extract-character-candidates`で作成したファイルから`out/characters_target.csv`を作成します。
生成AIを使用して正規表現では取り切れなかった不要な文字列を分離します。

処理を中断した場合、再度実行すると続きから開始します。
再作成したい場合は`out/characters_target.csv`を削除してください。

```bash
docker compose exec wiki_extract uv run python -m wiki_extract ai-characters-filter
```

#### ai-characters-split

`ai-characters-filter`で作成したファイルから`out/characters.csv`を作成します。
生成AIを使用して姓と名を分離します。
固有名詞ではないと判定されたものは最後の列に`False`が付きます。

処理を中断した場合、再度実行すると続きから開始します。
再作成したい場合は`out/characters.csv`を削除してください。

```bash
docker compose exec wiki_extract uv run python -m wiki_extract ai-characters-split
```

### オプション

指定すると`.env`の設定を上書きします。
利用頻度が高いと思われるのは`batch-size`と`workers`の2つです。

| オプション | 既定値 | 説明 |
|------------|--------|------|
| `--provider` | `gemini` | LLM プロバイダの指定。<br>全量を処理する場合は並列処理可能な`gemini`推奨。 |
| `--model` | Gemini: `gemini-2.5-flash-lite`<br>Ollama: `gemma3:4b` | モデル名の指定。<br>Ollamaは事前に必要なモデルをPullしておくこと。 |
| `--batch-size` | `30` | 1回でLLMに渡す行数。<br>行数が多すぎるとLLMが正しく動作しない可能性がある。<br>〜50程度までを推奨。 |
| `--workers` | `1` | 並列 LLM 呼び出し数。<br>Geminiの場合、全量を処理する場合は`gemini-2.5-flash-lite`+ `--workers 16`で4時間半ほどかかる。<br>Ollamaでローカル実行する場合、GPUの処理能力によるがGPUの枚数と同じ数(1枚挿しなら1)を推奨） |
| `--timeout` | `300` | API のタイムアウト（秒） |
| `--exclude-list` | パッケージ内 `data/excluded_names.json` | 除外対象ブラックリスト（JSON のみ）。`{"exact": [...], "suffix": [...]}`。 |

## うまく取得できない作品がある場合

### 再実行する前に

全量を再実行すると時間がかかるため、可能であれば再実行が必要な項目のみをCSVに残して実行してください。

### 各種CSVに不要な文字列が出力されていないか確認する

名前の後ろに説明文が書いてある場合、生成AIが正しく動作しない場合があります。

```csv
税務調査官・窓際太郎の事件簿,大矢栄一（民自党の大物衆議院議員・日本の臓器移植を推進する会の会長）
```

`ai-characters-filter`で除外される想定ですが、残っている場合は手動削除してから再度コマンドを実行してみてください。

### プロンプトを修正してみる

`data/prompts`のプロンプトを修正すると改善する可能性があります。
既存プロンプトは`Gemini` / `Gemma`のGoogle系LLMで調整してありますが、他のモデルを使用する場合はモデルに合わせた書き方をしたほうがよい場合があります。

### ブラックリストを修正してみる

`data/excluded_names.json`に単語を追加すると除外リスト（exact 完全一致・「の」+語尾一致）で除外されます。
`character_candidates_excluded.csv` や `characters_excluded.csv` に分離された項目を確認し、必要であれば調整してみてください。
`extract-character-candidates`を実行すると`character_candidates.csv`に反映されます。
