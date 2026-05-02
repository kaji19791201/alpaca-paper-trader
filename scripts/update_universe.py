"""月次 UNIVERSE 更新スクリプト

候補プール ~80 銘柄をモメンタム・流動性・SPY 相関でスコアリングし、
上位 20 銘柄を src/trading/config.py の UNIVERSE に書き込む。

使い方:
  dotenvx run -- uv run python scripts/update_universe.py
"""

import argparse
import re
import sys
import time
from datetime import date, datetime, timedelta

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

sys.path.insert(0, "src")

from trading import broker  # noqa: E402

CANDIDATES = [
    # 現 UNIVERSE
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "AMZN",
    "META",
    "TSLA",
    "JPM",
    "V",
    "UNH",
    "XOM",
    "LLY",
    "AVGO",
    "MA",
    "HD",
    "CVX",
    "MRK",
    "ABBV",
    "PEP",
    "KO",
    # テック追加
    "AMD",
    "QCOM",
    "TXN",
    "MU",
    "CRM",
    "NOW",
    "PANW",
    "CRWD",
    "SNOW",
    "AMAT",
    # ヘルスケア
    "AMGN",
    "GILD",
    "REGN",
    "BMY",
    "TMO",
    "DHR",
    "SYK",
    "BSX",
    "ISRG",
    # 金融
    "GS",
    "MS",
    "BAC",
    "BLK",
    "AXP",
    "SCHW",
    "ICE",
    # 生活必需品（低相関傾向）
    "WMT",
    "COST",
    "TGT",
    "CLX",
    "PG",
    "CL",
    "GIS",
    # 公益・インフラ（低相関傾向）
    "NEE",
    "DUK",
    "SO",
    "AEP",
    "SRE",
    "AWK",
    # 素材・エネルギー
    "FCX",
    "NEM",
    "NUE",
    "APD",
    "OXY",
    "SLB",
    "COP",
    "PSX",
    "VLO",
    # 産業
    "CAT",
    "DE",
    "RTX",
    "GD",
    "LMT",
    "HON",
    "UPS",
    "FDX",
    "NSC",
    # 消費財（裁量）
    "LULU",
    "MCD",
    "SBUX",
    "YUM",
    "DPZ",
    "NKE",
    # REIT
    "AMT",
    "PLD",
    "O",
    "EQR",
]

CONFIG_PATH = "src/trading/config.py"
CHANGE_LOG_PATH = "docs/change_log.md"
LOOKBACK_DAYS = 200
USE_DAYS = 120
BATCH_SIZE = 10
TARGET_COUNT = 20


def fetch_bars(symbols: list[str]) -> dict[str, pd.DataFrame]:
    end = datetime.now()
    start = end - timedelta(days=LOOKBACK_DAYS)
    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )
    bars = broker.data.get_stock_bars(req)
    df = bars.df
    if df.empty:
        return {}

    result = {}
    for sym in symbols:
        try:
            if isinstance(df.index, pd.MultiIndex):
                sym_df = df.xs(sym, level="symbol").sort_index()
            else:
                sym_df = df.sort_index()
            result[sym] = sym_df
        except KeyError:
            pass
    return result


def compute_metrics(
    bars: dict[str, pd.DataFrame], spy_returns: pd.Series | None
) -> pd.DataFrame:
    rows = []
    for sym, df in bars.items():
        if len(df) < 60:
            print(f"  [skip] {sym}: データ不足 ({len(df)} 日)")
            continue

        df = df.tail(USE_DAYS)
        closes = df["close"]
        volumes = df["volume"]

        momentum = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]
        liquidity = volumes.mean()

        daily_ret = closes.pct_change().dropna()
        spy_corr = 0.0
        if spy_returns is not None:
            aligned = daily_ret.align(spy_returns, join="inner")[0]
            spy_aligned = daily_ret.align(spy_returns, join="inner")[1]
            if len(aligned) >= 30:
                spy_corr = float(aligned.corr(spy_aligned))

        rows.append(
            {
                "ticker": sym,
                "momentum": momentum,
                "liquidity": liquidity,
                "spy_corr": spy_corr,
            }
        )

    if not rows:
        return pd.DataFrame()

    df_scores = pd.DataFrame(rows)

    mn, mx = df_scores["momentum"].min(), df_scores["momentum"].max()
    df_scores["momentum_norm"] = (
        (df_scores["momentum"] - mn) / (mx - mn) if mx > mn else 0.5
    )

    ln, lx = df_scores["liquidity"].min(), df_scores["liquidity"].max()
    df_scores["liquidity_norm"] = (
        (df_scores["liquidity"] - ln) / (lx - ln) if lx > ln else 0.5
    )

    df_scores["composite"] = (
        0.40 * df_scores["momentum_norm"]
        + 0.30 * df_scores["liquidity_norm"]
        - 0.30 * df_scores["spy_corr"]
    )

    return df_scores.sort_values("composite", ascending=False).reset_index(drop=True)


def update_config(new_universe: list[str]) -> list[str]:
    with open(CONFIG_PATH) as f:
        content = f.read()

    m = re.search(r"(UNIVERSE\s*=\s*\[)(.*?)(\])", content, re.DOTALL)
    if not m:
        raise ValueError("config.py に UNIVERSE = [...] が見つかりません")

    old_list_str = m.group(2)
    old_universe = re.findall(r'"([A-Z]+)"', old_list_str)

    items = ",\n".join(f'    "{sym}"' for sym in new_universe)
    new_block = f"UNIVERSE = [\n{items},\n]"
    new_content = re.sub(r"UNIVERSE\s*=\s*\[.*?\]", new_block, content, flags=re.DOTALL)

    with open(CONFIG_PATH, "w") as f:
        f.write(new_content)

    return old_universe


def append_change_log(
    date_str: str,
    df_scores: pd.DataFrame,
    old_universe: list[str],
    new_universe: list[str],
) -> None:
    added = [s for s in new_universe if s not in old_universe]
    removed = [s for s in old_universe if s not in new_universe]

    top_table = df_scores.head(TARGET_COUNT)[
        ["ticker", "momentum_norm", "liquidity_norm", "spy_corr", "composite"]
    ]
    table_lines = [
        "| ticker | momentum | liquidity | spy_corr | composite |",
        "|--------|----------|-----------|----------|-----------|",
    ]
    for _, row in top_table.iterrows():
        table_lines.append(
            f"| {row['ticker']:6s} | {row['momentum_norm']:.2f}     | {row['liquidity_norm']:.2f}      | {row['spy_corr']:+.2f}     | {row['composite']:.3f}     |"
        )

    added_str = ", ".join(added) if added else "（なし）"
    removed_str = ", ".join(removed) if removed else "（なし）"

    entry = f"""
## {date_str} — UNIVERSE 月次更新

{chr(10).join(table_lines)}

- 追加: {added_str}
- 削除: {removed_str}
"""

    with open(CHANGE_LOG_PATH, "a") as f:
        f.write(entry)


def is_first_monday() -> bool:
    today = date.today()
    return today.weekday() == 0 and today.day <= 7


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force", action="store_true", help="月初第1月曜チェックをスキップ"
    )
    args = parser.parse_args()

    if not args.force and not is_first_monday():
        print("skip: 月初第1月曜ではありません")
        sys.exit(0)

    print("[update_universe] スコアリング開始...")

    # SPY を先に取得
    print("  SPY データ取得中...")
    spy_bars = fetch_bars(["SPY"])
    spy_returns = None
    if "SPY" in spy_bars and len(spy_bars["SPY"]) >= 60:
        spy_df = spy_bars["SPY"].tail(USE_DAYS)
        spy_returns = spy_df["close"].pct_change().dropna()
        print(f"  SPY: {len(spy_returns)} 日分のリターン取得")
    else:
        print("  [warn] SPY データ取得失敗 — 相関ペナルティをスキップ")

    # 候補プールをバッチで取得
    all_bars: dict[str, pd.DataFrame] = {}
    batches = [
        CANDIDATES[i : i + BATCH_SIZE] for i in range(0, len(CANDIDATES), BATCH_SIZE)
    ]
    print(f"  {len(CANDIDATES)} 銘柄を {len(batches)} バッチで取得...")
    for i, batch in enumerate(batches):
        print(f"  バッチ {i + 1}/{len(batches)}: {batch}")
        try:
            bars = fetch_bars(batch)
            all_bars.update(bars)
        except Exception as e:
            print(f"  [warn] バッチ {i + 1} エラー: {e}")
        if i < len(batches) - 1:
            time.sleep(0.3)  # IEX 5 req/sec 制限

    print(f"  データ取得完了: {len(all_bars)} 銘柄")

    df_scores = compute_metrics(all_bars, spy_returns)
    if df_scores.empty:
        print("[error] スコアリング結果なし — 終了")
        return

    new_universe = df_scores.head(TARGET_COUNT)["ticker"].tolist()

    print(f"\nTOP {TARGET_COUNT} by composite score:")
    print(
        f"{'ticker':8s} {'momentum':>10s} {'liquidity':>10s} {'spy_corr':>10s} {'composite':>10s}"
    )
    for _, row in df_scores.head(TARGET_COUNT).iterrows():
        print(
            f"  {row['ticker']:6s}  {row['momentum_norm']:8.2f}  {row['liquidity_norm']:9.2f}  {row['spy_corr']:+9.2f}  {row['composite']:9.3f}"
        )

    old_universe = update_config(new_universe)

    added = [s for s in new_universe if s not in old_universe]
    removed = [s for s in old_universe if s not in new_universe]
    print(f"\nUNIVERSE updated: +{len(added)} added, -{len(removed)} removed")
    if added:
        print(f"  added  : {', '.join(added)}")
    if removed:
        print(f"  removed: {', '.join(removed)}")

    date_str = datetime.now().strftime("%Y-%m-%d")
    append_change_log(date_str, df_scores, old_universe, new_universe)
    print("change_log written.")


if __name__ == "__main__":
    main()
