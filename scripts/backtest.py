"""バックテスト
使い方:
  dotenvx run -- uv run python scripts/backtest.py
  dotenvx run -- uv run python scripts/backtest.py --start 2023-01-01 --end 2024-12-31
  dotenvx run -- uv run python scripts/backtest.py --symbols AAPL MSFT NVDA
  dotenvx run -- uv run python scripts/backtest.py --strategy ema_rsi
  dotenvx run -- uv run python scripts/backtest.py --compare   # 全戦略を比較
"""

import sys
import argparse
import math
from datetime import datetime, date

sys.path.insert(0, "src")

import pandas as pd
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from loguru import logger


INITIAL_EQUITY = 100_000.0


def fetch_bars(symbols: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    from trading import broker
    from trading.data import IEX_EARLIEST

    if start < IEX_EARLIEST:
        logger.warning(
            f"IEX無料フィードは {IEX_EARLIEST} 以降のみ取得可。start={start} は一部データが欠損する可能性あり"
        )

    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=datetime.combine(start, datetime.min.time()),
        end=datetime.combine(end, datetime.min.time()),
        feed=DataFeed.IEX,
    )
    bars = broker.data.get_stock_bars(req)
    df_all = bars.df

    result = {}
    for sym in symbols:
        try:
            if isinstance(df_all.index, pd.MultiIndex):
                df = df_all.xs(sym, level="symbol").sort_index()
            else:
                df = df_all.sort_index()
            if len(df) > 0:
                result[sym] = df
        except KeyError:
            logger.warning(f"{sym}: データなし、スキップ")
    return result


def _load_strategy(name: str):
    if name == "ma_cross":
        from trading.strategy.ma_cross import MACrossStrategy

        return MACrossStrategy()
    if name == "ema_rsi":
        from trading.strategy.ema_rsi import EmaRsiStrategy
        from trading import config

        return EmaRsiStrategy(short=config.EMA_SHORT, long=config.EMA_LONG)
    raise ValueError(f"不明な戦略: {name}")


def run_backtest(
    symbols: list[str],
    start: date,
    end: date,
    strategy_name: str = "ma_cross",
    trailing_stop: float | None = None,
) -> dict:
    from trading import config
    from trading.strategy.base import Signal

    exit_mode = (
        f"trailing-{trailing_stop * 100:.0f}%" if trailing_stop else "fixed-TP/SL"
    )
    label = f"{strategy_name}+{exit_mode}"
    logger.info(
        f"バックテスト開始: {start} 〜 {end}  銘柄数={len(symbols)}  戦略={label}"
    )
    bars = fetch_bars(symbols, start, end)
    if not bars:
        raise RuntimeError("取得できたデータが0銘柄")

    strategy = _load_strategy(strategy_name)
    equity = INITIAL_EQUITY
    cash = INITIAL_EQUITY
    positions: dict[str, dict] = {}  # symbol -> {qty, entry_price, peak_price}

    all_dates = sorted(
        set(
            idx.date() if hasattr(idx, "date") else idx
            for df in bars.values()
            for idx in df.index
        )
    )

    daily_equities: list[tuple[date, float]] = []
    trades: list[dict] = []

    for d in all_dates:
        day_str = d.isoformat() if hasattr(d, "isoformat") else str(d)

        for sym, pos in list(positions.items()):
            if sym not in bars:
                continue
            df = bars[sym]
            day_data = (
                df[df.index.date == d]
                if hasattr(df.index[0], "date")
                else df[df.index == day_str]
            )
            if day_data.empty:
                continue
            close = float(day_data["close"].iloc[-1])

            if trailing_stop is not None:
                # トレーリングストップ: 峰値を更新しながら峰値から下落したら撤退
                if close > pos.get("peak_price", pos["entry_price"]):
                    pos["peak_price"] = close
                trail_sl = pos.get("peak_price", pos["entry_price"]) * (
                    1 - trailing_stop
                )
                if close <= trail_sl:
                    pnl = (close - pos["entry_price"]) * pos["qty"]
                    cash += close * pos["qty"]
                    trades.append(
                        {
                            "symbol": sym,
                            "entry": pos["entry_price"],
                            "exit": close,
                            "qty": pos["qty"],
                            "pnl": pnl,
                            "date": day_str,
                            "reason": "TrailSL",
                        }
                    )
                    del positions[sym]
            else:
                tp = pos["entry_price"] * (1 + config.TAKE_PROFIT_PCT)
                sl = pos["entry_price"] * (1 - config.STOP_LOSS_PCT)
                if close >= tp or close <= sl:
                    pnl = (close - pos["entry_price"]) * pos["qty"]
                    cash += close * pos["qty"]
                    trades.append(
                        {
                            "symbol": sym,
                            "entry": pos["entry_price"],
                            "exit": close,
                            "qty": pos["qty"],
                            "pnl": pnl,
                            "date": day_str,
                            "reason": "TP/SL",
                        }
                    )
                    del positions[sym]

        for sym, df in bars.items():
            idx_dates = [i.date() if hasattr(i, "date") else i for i in df.index]
            if d not in idx_dates:
                continue
            pos_in_idx = idx_dates.index(d)
            if pos_in_idx < config.SMA_LONG + 1:
                continue

            sub_df = df.iloc[: pos_in_idx + 1]
            result = strategy.generate(sym, sub_df)

            if (
                result.signal == Signal.BUY
                and sym not in positions
                and len(positions) < config.MAX_POSITIONS
            ):
                close = float(df.iloc[pos_in_idx]["close"])
                budget = equity * config.POSITION_SIZE_PCT
                qty = int(budget / close)
                if qty > 0 and cash >= close * qty:
                    cash -= close * qty
                    positions[sym] = {"qty": qty, "entry_price": close}
                    trades.append(
                        {
                            "symbol": sym,
                            "entry": close,
                            "exit": None,
                            "qty": qty,
                            "pnl": None,
                            "date": day_str,
                            "reason": "BUY",
                        }
                    )

            elif result.signal == Signal.SELL and sym in positions:
                pos = positions.pop(sym)
                close = float(df.iloc[pos_in_idx]["close"])
                pnl = (close - pos["entry_price"]) * pos["qty"]
                cash += close * pos["qty"]
                trades.append(
                    {
                        "symbol": sym,
                        "entry": pos["entry_price"],
                        "exit": close,
                        "qty": pos["qty"],
                        "pnl": pnl,
                        "date": day_str,
                        "reason": "SELL",
                    }
                )

        pos_value = sum(
            float(
                bars[sym].iloc[
                    [
                        i.date() if hasattr(i, "date") else i for i in bars[sym].index
                    ].index(d)
                    if d
                    in [i.date() if hasattr(i, "date") else i for i in bars[sym].index]
                    else -1
                ]["close"]
            )
            * pos["qty"]
            for sym, pos in positions.items()
            if sym in bars
            and d in [i.date() if hasattr(i, "date") else i for i in bars[sym].index]
        )
        equity = cash + pos_value
        daily_equities.append((d, equity))

    closed = [t for t in trades if t["pnl"] is not None]
    wins = [t for t in closed if t["pnl"] > 0]
    total_pnl = sum(t["pnl"] for t in closed)
    win_rate = len(wins) / len(closed) * 100 if closed else 0.0

    equities_only = [e for _, e in daily_equities]
    peak = INITIAL_EQUITY
    max_dd = 0.0
    for eq in equities_only:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd:
            max_dd = dd

    daily_pnls = [0.0] + [
        equities_only[i] - equities_only[i - 1] for i in range(1, len(equities_only))
    ]
    if len(daily_pnls) >= 2:
        mean = sum(daily_pnls) / len(daily_pnls)
        var = sum((x - mean) ** 2 for x in daily_pnls) / (len(daily_pnls) - 1)
        std = math.sqrt(var)
        sharpe = mean / std * math.sqrt(252) if std > 0 else float("nan")
    else:
        sharpe = float("nan")

    return {
        "strategy": label,
        "start": start,
        "end": end,
        "initial_equity": INITIAL_EQUITY,
        "final_equity": equity,
        "total_pnl": total_pnl,
        "total_return_pct": (equity - INITIAL_EQUITY) / INITIAL_EQUITY * 100,
        "num_trades": len(closed),
        "win_rate": win_rate,
        "max_drawdown_pct": max_dd * 100,
        "sharpe": sharpe,
        "daily_equities": daily_equities,
        "trades": trades,
    }


def print_report(r: dict):
    print(f"\n{'=' * 55}")
    print(f"  バックテスト結果 [{r.get('strategy', '?')}]")
    print(f"  期間: {r['start']} 〜 {r['end']}")
    print(f"{'=' * 55}")
    print(f"  初期資産         : ${r['initial_equity']:>12,.2f}")
    print(f"  最終資産         : ${r['final_equity']:>12,.2f}")
    print(
        f"  累計 P&L         : ${r['total_pnl']:>+12,.2f}  ({r['total_return_pct']:+.2f}%)"
    )
    print(f"  取引回数         : {r['num_trades']} 回")
    print(f"  勝率             : {r['win_rate']:.1f}%")
    print(f"  最大ドローダウン : {r['max_drawdown_pct']:.2f}%")
    sr = r["sharpe"]
    print(
        f"  シャープレシオ   : {sr:.2f}"
        if not math.isnan(sr)
        else "  シャープレシオ   : N/A"
    )
    print(f"{'=' * 55}\n")

    closed = [t for t in r["trades"] if t["pnl"] is not None]
    if closed:
        print("  --- 取引明細（上位10件） ---")
        for t in sorted(closed, key=lambda x: abs(x["pnl"]), reverse=True)[:10]:
            sign = "+" if t["pnl"] >= 0 else ""
            print(
                f"  {t['date']}  {t['symbol']:5s} x{t['qty']}  "
                f"entry=${t['entry']:.2f} exit=${t['exit']:.2f}  P&L=${sign}{t['pnl']:,.2f}"
            )
        print()


def print_comparison(results: list[dict]):
    headers = ["戦略", "リターン", "勝率", "取引数", "最大DD", "シャープ"]
    print(f"\n{'=' * 65}")
    print("  戦略比較")
    print(f"{'=' * 65}")
    fmt = "  {:<12} {:>8} {:>7} {:>6} {:>8} {:>8}"
    print(fmt.format(*headers))
    print(f"  {'-' * 62}")
    for r in results:
        sr = r["sharpe"]
        sr_str = f"{sr:.2f}" if not math.isnan(sr) else "N/A"
        print(
            fmt.format(
                r.get("strategy", "?"),
                f"{r['total_return_pct']:+.2f}%",
                f"{r['win_rate']:.1f}%",
                str(r["num_trades"]),
                f"{r['max_drawdown_pct']:.2f}%",
                sr_str,
            )
        )
    print(f"{'=' * 65}\n")


def main():
    parser = argparse.ArgumentParser(description="バックテスト")
    parser.add_argument("--start", default="2023-01-01", help="開始日 (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-12-31", help="終了日 (YYYY-MM-DD)")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="対象銘柄（省略時は config.UNIVERSE 全銘柄）",
    )
    parser.add_argument(
        "--strategy",
        default="ma_cross",
        choices=["ma_cross", "ema_rsi"],
        help="使用する戦略",
    )
    parser.add_argument(
        "--trailing-stop",
        type=float,
        default=None,
        metavar="PCT",
        help="トレーリングストップ率 (例: 0.10 = 10%%)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="複数設定を比較する",
    )
    args = parser.parse_args()

    from trading import config

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    symbols = args.symbols or config.UNIVERSE

    if args.compare:
        # fixed TP/SL vs trailing stop 10% / 15% の4パターン比較
        combos = [
            ("ma_cross", None),
            ("ma_cross", 0.10),
            ("ema_rsi", None),
            ("ema_rsi", 0.10),
        ]
        results = []
        for strategy, ts in combos:
            result = run_backtest(symbols, start, end, strategy, ts)
            print_report(result)
            results.append(result)
        print_comparison(results)
    else:
        result = run_backtest(symbols, start, end, args.strategy, args.trailing_stop)
        print_report(result)


if __name__ == "__main__":
    main()
