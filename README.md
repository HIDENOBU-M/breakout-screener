# 東証プライム 新高値ブレイクアウト スクリーナー

毎営業日の引け後に自動でスクリーニングを行い、LINE で通知するツールです。

## スクリーニング条件

| 条件 | 内容 |
|------|------|
| 対象市場 | 東証プライム全体（約1,600銘柄） |
| 新高値 | 当日終値が過去5年高値を更新 |
| 出来高 | 当日出来高が20日平均の1.5倍以上 |
| 実行タイミング | 毎営業日 15:35 JST |

---

## セットアップ手順

### 1. LINE Messaging API のチャンネルを作成する

① **LINE Developers にログイン**
- https://developers.line.biz/ja/ にアクセス
- 普段使いの LINE アカウントでログイン（Business ID 不要）

② **プロバイダーを作成**
- コンソールトップ →「新規プロバイダー作成」
- 名前は何でも OK（例: `株スクリーナー`）

③ **Messaging API チャンネルを作成**
- プロバイダー内で「チャンネルを作成」→「Messaging API」を選択
- チャンネル名・説明を入力して作成

④ **自分の公式アカウントを友だち追加**
- 作成したチャンネルの「Messaging API 設定」タブを開く
- 表示されている QR コードをスマホで読み込んで友だち追加

⑤ **チャンネルアクセストークンを発行**
- 「Messaging API 設定」タブの一番下
- 「チャンネルアクセストークン（長期）」の「発行」をクリック
- 表示されたトークンをコピーして保管

⑥ **自分のユーザーIDを取得**
- 「チャンネル基本設定」タブ →「あなたのユーザーID」をコピー
- （`U` から始まる文字列）

### 2. GitHub リポジトリを作成する

```bash
git init
git add .
git commit -m "初期コミット"
git remote add origin https://github.com/あなたのユーザー名/breakout-screener.git
git push -u origin main
```

### 3. GitHub Secrets に登録する

リポジトリ → Settings → Secrets and variables → Actions → 「New repository secret」

| Name | Value |
|------|-------|
| `LINE_CHANNEL_TOKEN` | チャンネルアクセストークン |
| `LINE_USER_ID` | あなたのユーザーID（`U`から始まる） |

### 4. GitHub Actions を有効化してテスト実行

1. リポジトリの「Actions」タブ → ワークフローを有効化
2. 「Run workflow」で手動実行して動作確認

---

## LINE 通知の例

```
【新高値ブレイクアウト】2026/06/05
該当: 3 銘柄

■ 7203
  終値: ¥3,250  5年高値: ¥3,248
  出来高: 2.31倍（平均比）

■ 6758
  終値: ¥12,480  5年高値: ¥12,450
  出来高: 1.87倍（平均比）
```

---

## ローカルでテスト実行する場合

```bash
pip install -r requirements.txt
LINE_CHANNEL_TOKEN=トークン LINE_USER_ID=ユーザーID python screener.py
```

どちらも省略するとコンソールに結果が出力されます。

---

## カスタマイズ

`screener.py` の設定値を変更することで条件を調整できます。

```python
VOLUME_RATIO_THRESHOLD = 1.5   # 出来高倍率（例: 2.0 に変更で厳しめ）
YEARS_HIGH = 5                 # 高値の年数
VOLUME_MA_DAYS = 20            # 出来高平均の計算日数
```

---

## 注意事項

- LINE Messaging API の無料枠は月200通。毎日1通なら約7ヶ月分に相当しますが、超過分は有料になります
- yfinance は非公式ライブラリのため、Yahoo Finance の仕様変更で動作しなくなる場合があります
- GitHub Actions の無料枠（月2,000分）で十分運用できます
- データ取得に約10〜15分かかる場合があります
