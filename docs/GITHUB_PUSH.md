# GitHub に Push する手順

アカウントはある前提。手順を間違えないよう番号順に実行する。

---

## 1. リポジトリを用意する

### パターンA: まだ GitHub にリポジトリがない場合

1. [GitHub](https://github.com) にログインする。
2. 右上の **+** → **New repository** をクリック。
3. **Repository name** に `wiki-extract` など好きな名前を入れる。
4. **Public** を選ぶ。
5. **Add a README file** や **Add .gitignore** は**チェックしない**（ローカルに既にあるため）。
6. **Create repository** をクリック。
7. 表示された **Repository URL**（`https://github.com/あなたのユーザー名/wiki-extract.git`）をコピーする。

### パターンB: すでに GitHub にリポジトリがある場合

- そのリポジトリの URL（`https://github.com/あなたのユーザー名/リポジトリ名.git`）をコピーしておく。

---

## 2. ローカルで Git を初期化する（まだの場合だけ）

プロジェクトのルート（`/app`）で:

```bash
cd /app
git init
```

すでに `git init` 済みならこのステップは飛ばす。

---

## 3. リモートを追加する

```bash
git remote add origin https://github.com/あなたのユーザー名/リポジトリ名.git
```

- **すでに `origin` がある場合**（別の URL を入れたいとき）:
  ```bash
  git remote set-url origin https://github.com/あなたのユーザー名/リポジトリ名.git
  ```
- 確認: `git remote -v`

---

## 4. ファイルをステージする

```bash
git add .
```

- `.gitignore` に入っている `dumps/` や `out/` は追加されない。
- 追加されるものだけ確認したいとき: `git status`

---

## 5. コミットする

```bash
git commit -m "Initial commit"
```

- メッセージは自由に変えてよい（例: `"Add wiki-extract: extract fictional characters from jawiki dumps"`）。

---

## 6. ブランチ名を合わせる（必要なときだけ）

GitHub のデフォルトブランチが `main` の場合:

```bash
git branch -M main
```

すでに `main` なら不要。

---

## 7. Push する

```bash
git push -u origin main
```

- 初回は GitHub の認証（ブラウザまたはトークン）を聞かれることがある。
- 2回目以降は: `git push` だけでよい。

---

## よくある失敗と対処

| 状況 | 対処 |
|------|------|
| `remote: Permission denied` | GitHub にログインし直す、または Personal Access Token を使う。 |
| `Updates were rejected` | 先に `git pull origin main --rebase` してから `git push`。 |
| `dumps/` や `out/` を push してしまった | `.gitignore` に追加し、`git rm -r --cached dumps/ out/` で追跡解除してから再度 commit & push。 |
| リモートの URL を間違えた | `git remote set-url origin 正しいURL` で修正。 |

---

## 短いチェックリスト（慣れてきたら）

1. GitHub でリポジトリ作成（README 等は作らない）
2. `git init`（まだなら）
3. `git remote add origin <URL>`
4. `git add .`
5. `git commit -m "Initial commit"`
6. `git branch -M main`
7. `git push -u origin main`
