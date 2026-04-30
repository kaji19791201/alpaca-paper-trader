from loguru import logger
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.enums import DataFeed
from . broker import trading, data
from . import config


def buy(symbol: str, qty: int):
    if qty <= 0:
        logger.warning(f"{symbol}: qty={qty} で注文スキップ")
        return None

    q = data.get_stock_latest_quote(
        StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
    )[symbol]
    price = float(q.ask_price) or float(q.bid_price)

    take_profit = round(price * (1 + config.TAKE_PROFIT_PCT), 2)
    stop_loss   = round(price * (1 - config.STOP_LOSS_PCT), 2)

    order = trading.submit_order(MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        take_profit=TakeProfitRequest(limit_price=take_profit),
        stop_loss=StopLossRequest(stop_price=stop_loss),
    ))
    logger.info(f"BUY {symbol} x{qty}  TP=${take_profit} SL=${stop_loss}  [{order.id}]")
    return order


def sell(symbol: str):
    positions = trading.get_all_positions()
    pos = next((p for p in positions if p.symbol == symbol), None)
    if not pos:
        logger.warning(f"{symbol}: ポジションなし、売りスキップ")
        return None

    order = trading.submit_order(MarketOrderRequest(
        symbol=symbol,
        qty=abs(float(pos.qty)),
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    ))
    logger.info(f"SELL {symbol} x{pos.qty}  [{order.id}]")
    return order
