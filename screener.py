"""
東証プライム 新高値ブレイクアウト スクリーナー
条件: 5年高値更新 + 出来高が20日平均の1.5倍以上
通知: LINE Messaging API
"""

import os
import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# ──────────────────────────────────────────
# 設定
# ──────────────────────────────────────────
# LINE Messaging API の設定（GitHub Secrets で管理）
LINE_CHANNEL_TOKEN = os.environ.get("LINE_CHANNEL_TOKEN", "")  # チャンネルアクセストークン
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")              # 送信先ユーザーID（自分のID）
VOLUME_RATIO_THRESHOLD = 1.5   # 出来高：20日平均の何倍以上か
YEARS_HIGH = 5                 # 何年高値か
VOLUME_MA_DAYS = 20            # 出来高移動平均の日数
BATCH_SIZE = 50                # API負荷軽減のためのバッチ処理数
SLEEP_BETWEEN_BATCHES = 2      # バッチ間の待機秒数


def get_prime_tickers() -> list[str]:
    """
    東証プライム銘柄コードを取得する。
    JPXのCSVから取得（最新の上場銘柄リスト）。
    """
    url = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
    print("JPX から上場銘柄リストを取得中...")

    try:
        df = pd.read_excel(url, header=0)
        # 市場区分でプライム市場を絞り込む
        prime_df = df[df["市場・商品区分"].str.contains("プライム", na=False)]
        codes = prime_df["コード"].astype(str).str.zfill(4).tolist()
        tickers = [f"{code}.T" for code in codes]
        print(f"  → {len(tickers)} 銘柄を取得しました")
        return tickers
    except Exception as e:
        print(f"JPX からの取得に失敗しました: {e}")
        print("フォールバック: 代表的な銘柄リストを使用します")
        # フォールバック用の代表銘柄（テスト用）
        sample_codes = [
            "7203", "6758", "9984", "8306", "7974",
            "6861", "4063", "9433", "8035", "6367"
        ]
        return [f"{code}.T" for code in sample_codes]


def fetch_data(tickers: list[str]) -> dict:
    """
    yfinance で株価・出来高データを一括取得する。
    """
    period_days = YEARS_HIGH * 365 + 30  # 余裕を持って取得
    end_date = datetime.today()
    start_date = end_date - timedelta(days=period_days)

    results = {}
    total = len(tickers)

    print(f"\n株価データを取得中（{total} 銘柄）...")

    for i in range(0, total, BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        batch_str = " ".join(batch)
        pct = (i + len(batch)) / total * 100

        try:
            data = yf.download(
                batch_str,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
            )

            for ticker in batch:
                try:
                    if len(batch) == 1:
                        ticker_data = data
                    else:
                        ticker_data = data[ticker]

                    if ticker_data is not None and len(ticker_data) > VOLUME_MA_DAYS + 5:
                        results[ticker] = ticker_data
                except Exception:
                    pass

        except Exception as e:
            print(f"  バッチ取得エラー ({i}〜): {e}")

        print(f"  {pct:.0f}% 完了 ({i + len(batch)}/{total})", end="\r")

        if i + BATCH_SIZE < total:
            time.sleep(SLEEP_BETWEEN_BATCHES)

    print(f"\n  → {len(results)} 銘柄のデータを取得しました")
    return results


def screen(data: dict) -> list[dict]:
    """
    ブレイクアウト条件でスクリーニングを実行する。
    条件1: 本日終値 >= 5年高値（本日を除く過去5年）
    条件2: 本日出来高 >= 20日平均出来高 × 1.5
    """
    hits = []
    cutoff_date = datetime.today() - timedelta(days=YEARS_HIGH * 365)

    for ticker, df in data.items():
        try:
            df = df.dropna(subset=["Close", "Volume"])
            if len(df) < VOLUME_MA_DAYS + 5:
                continue

            today_row = df.iloc[-1]
            today_close = today_row["Close"]
            today_volume = today_row["Volume"]

            # 5年高値（本日を除く）
            historical = df.iloc[:-1]
            historical_5y = historical[historical.index >= cutoff_date]
            if len(historical_5y) < 20:
                continue

            high_5y = historical_5y["High"].max()

            # 出来高20日平均（本日を除く）
            vol_ma20 = historical["Volume"].iloc[-VOLUME_MA_DAYS:].mean()

            # 条件チェック
            is_new_high = today_close >= high_5y
            is_volume_surge = today_volume >= vol_ma20 * VOLUME_RATIO_THRESHOLD

            if is_new_high and is_volume_surge:
                code = ticker.replace(".T", "")
                hits.append({
                    "ticker": ticker,
                    "code": code,
                    "close": round(float(today_close), 1),
                    "high_5y": round(float(high_5y), 1),
                    "volume": int(today_volume),
                    "vol_ma20": int(vol_ma20),
                    "vol_ratio": round(today_volume / vol_ma20, 2),
                })

        except Exception:
            pass

    # 出来高倍率の高い順にソート
    hits.sort(key=lambda x: x["vol_ratio"], reverse=True)
    return hits


def send_line_message(message: str, channel_token: str, user_id: str) -> bool:
    """LINE Messaging API でプッシュメッセージを送信する。"""
    if not channel_token or not user_id:
        print("[LINE] トークンまたはユーザーIDが設定されていません。コンソールに出力します。")
        print(message)
        return False

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {channel_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        print("[LINE] 通知を送信しました ✓")
        return True
    else:
        print(f"[LINE] 送信失敗: {response.status_code} {response.text}")
        return False


def build_message(hits: list[dict]) -> str:
    """LINE 通知メッセージを組み立てる。"""
    today = datetime.today().strftime("%Y/%m/%d")

    if not hits:
        return f"\n【新高値ブレイクアウト】{today}\n該当銘柄なし"

    lines = [f"\n【新高値ブレイクアウト】{today}", f"該当: {len(hits)} 銘柄\n"]

    # LINEの文字数制限(1000文字)を考慮して上位15銘柄まで
    for h in hits[:15]:
        lines.append(
            f"■ {h['code']}\n"
            f"  終値: ¥{h['close']:,.0f}  5年高値: ¥{h['high_5y']:,.0f}\n"
            f"  出来高: {h['vol_ratio']}倍（平均比）"
        )

    if len(hits) > 15:
        lines.append(f"\n... 他 {len(hits) - 15} 銘柄")

    return "\n".join(lines)


def main():
    print("=" * 50)
    print("東証プライム 新高値ブレイクアウト スクリーナー")
    print(f"条件: {YEARS_HIGH}年高値更新 + 出来高{VOLUME_RATIO_THRESHOLD}倍以上")
    print("=" * 50)

    # 1. 銘柄リスト取得
    tickers = get_prime_tickers()

    # 2. データ取得
    data = fetch_data(tickers)

    # 3. スクリーニング
    print("\nスクリーニング実行中...")
    hits = screen(data)
    print(f"  → {len(hits)} 銘柄が条件を満たしました")

    # 4. LINE 通知
    message = build_message(hits)
    send_line_message(message, LINE_CHANNEL_TOKEN, LINE_USER_ID)

    # 5. CSV 保存（ログ用）
    if hits:
        today_str = datetime.today().strftime("%Y%m%d")
        df_out = pd.DataFrame(hits)
        csv_path = f"results_{today_str}.csv"
        df_out.to_csv(csv_path, index=False, encoding="utf-8-bom")
        print(f"  結果を {csv_path} に保存しました")


if __name__ == "__main__":
    main()
