"""週次パラメータチューニング

EMA_SHORT / EMA_LONG / TRAILING_STOP_PCT のグリッドサーチを行い、
スコア最大の組み合わせを config.py に反映する。

スコア = total_return_pct * sharpe（両方正の場合に意味を持つ複合評価）

使い方:
  dotenvx run -- uv run python scripts/tune_params.py
  dotenvx run -- uv run python scripts/tune_params.py --dry-run
"""

import sys
import argparse
import math
import re
from datetime import date, timedelta
from itertools import product

sys.path.insert(0, "src")


GRID = {
    "EMA_SHORT": [8, 10, 12],
    "EMA_LONG": [25, 30, 35],
    "TRAILING_STOP_PCT": [8.0, 10.0, 12.0],
}

CONFIG_PATH = "src/trading/config.py"
CHANGELOG_PATH = "docs/change_log.md"


def _score(result: dict) -> float:
    r = result["total_return_pct"]
    s = result["sharpe"]
    if math.isnan(s):
        return float("-inf")
    return r * s


def run_grid_search(symbols: list[str], start: date, end: date) -> list[dict]:
    import trading.config as cfg
    from backtest import run_backtest

    rows = []
    combos = list(
        product(GRID["EMA_SHORT"], GRID["EMA_LONG"], GRID["TRAILING_STOP_PCT"])
    )
    total = len(combos)

    for i, (ema_s, ema_l, ts_pct) in enumerate(combos, 1):
        if ema_s >= ema_l:
            continue
        cfg.EMA_SHORT = ema_s
        cfg.EMA_LONG = ema_l
        cfg.TRAILING_STOP_PCT = ts_pct

        print(
            f"  [{i:>2}/{total}] EMA {ema_s}/{ema_l}  TS {ts_pct:.0f}%  ...",
            end=" ",
            flush=True,
        )
        result = run_backtest(symbols, start, end, "ema_rsi", ts_pct / 100.0)
        sc = _score(result)
        rows.append(
            {
                "ema_short": ema_s,
                "ema_long": ema_l,
                "trailing_stop_pct": ts_pct,
                "total_return_pct": result["total_return_pct"],
                "sharpe": result["sharpe"],
                "max_drawdown_pct": result["max_drawdown_pct"],
                "win_rate": result["win_rate"],
                "num_trades": result["num_trades"],
                "score": sc,
            }
        )
        print(
            f"ret={result['total_return_pct']:+.1f}%  sharpe={result['sharpe']:.2f}  score={sc:.2f}"
        )

    return sorted(rows, key=lambda x: x["score"], reverse=True)


def print_results(rows: list[dict], best: dict):
    print(f"\n{'=' * 75}")
    print("  グリッドサーチ結果（スコア降順）")
    print(f"{'=' * 75}")
    fmt = "  {:>3}/{:>3}  TS{:>4.0f}%  ret={:>+7.2f}%  sharpe={:>6.2f}  dd={:>5.2f}%  score={:>7.2f}"
    for r in rows[:10]:
        print(
            fmt.format(
                r["ema_short"],
                r["ema_long"],
                r["trailing_stop_pct"],
                r["total_return_pct"],
                r["sharpe"],
                r["max_drawdown_pct"],
                r["score"],
            )
        )
    if len(rows) > 10:
        print(f"  ... 他 {len(rows) - 10} 件")
    print(f"{'=' * 75}")
    print(
        f"  ★ 最適: EMA {best['ema_short']}/{best['ema_long']}  TS {best['trailing_stop_pct']:.0f}%"
        f"  score={best['score']:.2f}  ret={best['total_return_pct']:+.2f}%  sharpe={best['sharpe']:.2f}"
    )
    print(f"{'=' * 75}\n")


def update_config(best: dict, dry_run: bool, prev: dict) -> bool:
    with open(CONFIG_PATH) as f:
        content = f.read()

    new_content = re.sub(
        r"^EMA_SHORT\s*=\s*\d+",
        f"EMA_SHORT = {best['ema_short']}",
        content,
        flags=re.MULTILINE,
    )
    new_content = re.sub(
        r"^EMA_LONG\s*=\s*\d+",
        f"EMA_LONG = {best['ema_long']}",
        new_content,
        flags=re.MULTILINE,
    )
    new_content = re.sub(
        r"^TRAILING_STOP_PCT\s*=\s*[\d.]+",
        f"TRAILING_STOP_PCT = {best['trailing_stop_pct']}",
        new_content,
        flags=re.MULTILINE,
    )

    changed = (
        prev["EMA_SHORT"] != best["ema_short"]
        or prev["EMA_LONG"] != best["ema_long"]
        or prev["TRAILING_STOP_PCT"] != best["trailing_stop_pct"]
    )

    if not changed:
        print("  config.py: 変更なし（現在値が最適）")
        return False

    if dry_run:
        print("  [DRY-RUN] config.py 更新予定:")
        print(f"    EMA_SHORT: {prev['EMA_SHORT']} → {best['ema_short']}")
        print(f"    EMA_LONG: {prev['EMA_LONG']} → {best['ema_long']}")
        print(
            f"    TRAILING_STOP_PCT: {prev['TRAILING_STOP_PCT']} → {best['trailing_stop_pct']}"
        )
        return False

    with open(CONFIG_PATH, "w") as f:
        f.write(new_content)
    print(
        f"  config.py 更新: EMA {best['ema_short']}/{best['ema_long']}  TS {best['trailing_stop_pct']:.0f}%"
    )
    return True


def update_changelog(best: dict, prev: dict, start: date, end: date):
    today = date.today().isoformat()
    entry = (
        f"\n## {today} — 週次パラメータチューニング\n\n"
        f"- 期間: {start} 〜 {end}\n"
        f"- グリッド: EMA_SHORT={GRID['EMA_SHORT']}  EMA_LONG={GRID['EMA_LONG']}  "
        f"TRAILING_STOP_PCT={GRID['TRAILING_STOP_PCT']}\n"
        f"- 変更前: EMA {prev['EMA_SHORT']}/{prev['EMA_LONG']}  TS {prev['TRAILING_STOP_PCT']:.0f}%\n"
        f"- 変更後: EMA {best['ema_short']}/{best['ema_long']}  TS {best['trailing_stop_pct']:.0f}%\n"
        f"- スコア: {best['score']:.2f}  ret={best['total_return_pct']:+.2f}%  "
        f"sharpe={best['sharpe']:.2f}  dd={best['max_drawdown_pct']:.2f}%\n"
    )
    with open(CHANGELOG_PATH, "a") as f:
        f.write(entry)
    print(f"  {CHANGELOG_PATH} 追記完了")


def main():
    parser = argparse.ArgumentParser(description="週次パラメータチューニング")
    parser.add_argument(
        "--dry-run", action="store_true", help="config.py を実際には更新しない"
    )
    parser.add_argument(
        "--start", default=None, help="開始日 (YYYY-MM-DD、省略時は1年前)"
    )
    parser.add_argument("--end", default=None, help="終了日 (YYYY-MM-DD、省略時は昨日)")
    args = parser.parse_args()

    end = date.fromisoformat(args.end) if args.end else date.today() - timedelta(days=1)
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=365)

    from trading import config

    prev = {
        "EMA_SHORT": config.EMA_SHORT,
        "EMA_LONG": config.EMA_LONG,
        "TRAILING_STOP_PCT": config.TRAILING_STOP_PCT,
    }
    symbols = config.UNIVERSE

    print(f"\n週次チューニング開始: {start} 〜 {end}")
    print(
        f"現在値: EMA {prev['EMA_SHORT']}/{prev['EMA_LONG']}  TS {prev['TRAILING_STOP_PCT']:.0f}%\n"
    )

    rows = run_grid_search(symbols, start, end)
    if not rows:
        print("有効な結果が得られませんでした")
        return

    best = rows[0]
    print_results(rows, best)

    changed = update_config(best, args.dry_run, prev)
    if changed:
        update_changelog(best, prev, start, end)
    elif not args.dry_run:
        update_changelog(best, prev, start, end)


if __name__ == "__main__":
    main()
