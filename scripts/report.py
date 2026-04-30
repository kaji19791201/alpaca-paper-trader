"""P&L レポート出力
使い方:
  dotenvx run -- uv run python scripts/report.py           # 直近30日
  dotenvx run -- uv run python scripts/report.py --days 7  # 直近7日
"""

import sys
import argparse
import math

sys.path.insert(0, "src")

from trading.tracker import get_performance, get_orders, DB_PATH


def sharpe(pnls: list[float]) -> float:
    if len(pnls) < 2:
        return float("nan")
    n = len(pnls)
    mean = sum(pnls) / n
    variance = sum((x - mean) ** 2 for x in pnls) / (n - 1)
    std = math.sqrt(variance)
    if std == 0:
        return float("nan")
    return mean / std * math.sqrt(252)


def max_drawdown(equities: list[float]) -> float:
    if not equities:
        return 0.0
    peak = equities[0]
    max_dd = 0.0
    for eq in equities:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd:
            max_dd = dd
    return max_dd


def main():
    parser = argparse.ArgumentParser(description="P&L レポートを出力する")
    parser.add_argument("--days", type=int, default=30, help="集計期間（日数）")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"DB が見つかりません: {DB_PATH}")
        print("まず run_paper.py を実行してデータを蓄積してください。")
        return

    perf = get_performance(args.days)
    orders = get_orders(args.days)

    print(f"\n{'=' * 50}")
    print(f"  P&L レポート（直近 {args.days} 日）")
    print(f"{'=' * 50}")

    if not perf:
        print("パフォーマンスデータがありません。")
    else:
        pnls = [row["daily_pnl"] for row in perf]
        equities = [row["equity"] for row in perf]
        cumulative_pnl = sum(pnls)
        win_days = sum(1 for p in pnls if p > 0)
        win_rate = win_days / len(pnls) * 100 if pnls else 0.0
        sr = sharpe(pnls)
        mdd = max_drawdown(equities)

        print(f"  期間          : {perf[0]['date']} 〜 {perf[-1]['date']}")
        print(f"  取引日数      : {len(pnls)} 日")
        print(f"  累計 P&L      : ${cumulative_pnl:+,.2f}")
        print(f"  勝率          : {win_rate:.1f}%  ({win_days}/{len(pnls)} 日)")
        print(f"  最大ドローダウン: {mdd * 100:.2f}%")
        print(
            f"  シャープレシオ : {sr:.2f}"
            if not math.isnan(sr)
            else "  シャープレシオ : N/A"
        )
        print(f"  最終資産      : ${equities[-1]:,.2f}")

        print("\n  --- 日次 P&L ---")
        for row in perf:
            sign = "+" if row["daily_pnl"] >= 0 else ""
            print(
                f"  {row['date']}  ${sign}{row['daily_pnl']:,.2f}  (equity ${row['equity']:,.2f})"
            )

    print(f"\n  --- 注文履歴 ({len(orders)} 件) ---")
    if not orders:
        print("  注文データなし")
    else:
        for o in orders:
            filled = (
                f"@${o['filled_avg_price']:.2f}"
                if o["filled_avg_price"]
                else "(未約定)"
            )
            print(
                f"  {o['created_at'][:10]}  {o['side'].upper():4s} {o['symbol']:5s} x{o['qty']:.0f}  {filled}  [{o['status']}]"
            )

    print(f"\n{'=' * 50}\n")


if __name__ == "__main__":
    main()
