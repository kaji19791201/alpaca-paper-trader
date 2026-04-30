"""手動売買CLI
使い方:
  uv run python scripts/trade.py buy  AAPL 10
  uv run python scripts/trade.py sell AAPL 10
  uv run python scripts/trade.py list
  uv run python scripts/trade.py quote AAPL
"""
import sys
sys.path.insert(0, "src")

import argparse
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.requests import StockLatestQuoteRequest
from trading.broker import trading, data, get_account, get_positions
from loguru import logger


def buy(symbol: str, qty: float):
    order = trading.submit_order(MarketOrderRequest(
        symbol=symbol.upper(),
        qty=qty,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    ))
    logger.info(f"BUY {symbol.upper()} x{qty} → 注文ID: {order.id} [{order.status}]")


def sell(symbol: str, qty: float):
    order = trading.submit_order(MarketOrderRequest(
        symbol=symbol.upper(),
        qty=qty,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    ))
    logger.info(f"SELL {symbol.upper()} x{qty} → 注文ID: {order.id} [{order.status}]")


def list_positions():
    acct = get_account()
    logger.info(f"現金: ${float(acct.cash):,.2f}  ポートフォリオ: ${float(acct.portfolio_value):,.2f}")
    positions = get_positions()
    if not positions:
        logger.info("保有ポジションなし")
    else:
        for p in positions:
            pl = float(p.unrealized_pl)
            pl_pct = float(p.unrealized_plpc) * 100
            sign = "+" if pl >= 0 else ""
            logger.info(f"  {p.symbol:<6} {p.qty}株  現在値 ${float(p.current_price):,.2f}  損益 {sign}{pl:,.2f} ({sign}{pl_pct:.2f}%)")

    orders = trading.get_orders()
    if orders:
        logger.info("--- 注文中 ---")
        for o in orders:
            logger.info(f"  [{o.status.value}] {o.side.value.upper()} {o.symbol} x{o.qty}")


def quote(symbol: str):
    req = StockLatestQuoteRequest(symbol_or_symbols=symbol.upper())
    result = data.get_stock_latest_quote(req)
    q = result[symbol.upper()]
    logger.info(f"{symbol.upper()}  Bid: ${q.bid_price}  Ask: ${q.ask_price}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")

    b = sub.add_parser("buy")
    b.add_argument("symbol")
    b.add_argument("qty", type=float)

    s = sub.add_parser("sell")
    s.add_argument("symbol")
    s.add_argument("qty", type=float)

    sub.add_parser("list")

    q = sub.add_parser("quote")
    q.add_argument("symbol")

    args = parser.parse_args()

    if args.cmd == "buy":
        buy(args.symbol, args.qty)
    elif args.cmd == "sell":
        sell(args.symbol, args.qty)
    elif args.cmd == "list":
        list_positions()
    elif args.cmd == "quote":
        quote(args.symbol)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
