from loguru import logger
from alpaca.trading.requests import MarketOrderRequest, TrailingStopOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from .broker import trading
from . import config


def buy(symbol: str, qty: float):
    """成行BUY → 直後にトレーリングストップSELLを設定"""
    if qty <= 0:
        logger.warning(f"{symbol}: qty={qty} で注文スキップ")
        return None

    order = trading.submit_order(
        MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
    )
    logger.info(f"BUY {symbol} x{qty}  [{order.id}]")

    # トレーリングストップを別注文で設定（GTC）
    ts_order = trading.submit_order(
        TrailingStopOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC,
            trail_percent=config.TRAILING_STOP_PCT,
        )
    )
    logger.info(
        f"TrailingStop {symbol} x{qty}  trail={config.TRAILING_STOP_PCT}%  [{ts_order.id}]"
    )
    return order


def sell(symbol: str):
    """シグナルによる手動売却（オープンなトレーリングストップをキャンセルしてから成行売り）"""
    positions = trading.get_all_positions()
    pos = next((p for p in positions if p.symbol == symbol), None)
    if not pos:
        logger.warning(f"{symbol}: ポジションなし、売りスキップ")
        return None

    # 同銘柄のオープン注文（trailing stop等）をキャンセル
    open_orders = trading.get_orders()
    for o in open_orders:
        if o.symbol == symbol and o.side == OrderSide.SELL:
            trading.cancel_order_by_id(str(o.id))
            logger.info(f"キャンセル: {o.id} ({symbol} SELL)")

    qty = abs(float(pos.qty))
    order = trading.submit_order(
        MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
    )
    logger.info(f"SELL {symbol} x{qty}  [{order.id}]")
    return order
