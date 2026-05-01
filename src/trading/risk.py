from loguru import logger
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.enums import DataFeed
from . import config
from .broker import trading, data


def _latest_ask(symbol: str) -> float:
    req = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
    q = data.get_stock_latest_quote(req)[symbol]
    return float(q.ask_price) or float(q.bid_price)


def position_size(symbol: str) -> float:
    """口座残高の POSITION_SIZE_PCT 分の株数を返す（フラクショナルシェア対応）"""
    acct = trading.get_account()
    budget = float(acct.equity) * config.POSITION_SIZE_PCT
    price = _latest_ask(symbol)
    qty = round(budget / price, 6)
    logger.debug(f"{symbol}: budget=${budget:.2f}, price=${price:.2f}, qty={qty}")
    return qty


def can_open(symbol: str) -> tuple[bool, str]:
    """新規ポジションを開けるか検証"""
    positions = trading.get_all_positions()

    if len(positions) >= config.MAX_POSITIONS:
        return False, f"最大ポジション数({config.MAX_POSITIONS})に達している"

    if any(p.symbol == symbol for p in positions):
        return False, f"{symbol} は既に保有中"

    acct = trading.get_account()
    daily_pl = float(acct.equity) - float(acct.last_equity)
    if (
        daily_pl < 0
        and abs(daily_pl) / float(acct.last_equity) >= config.MAX_DAILY_LOSS
    ):
        return False, f"日次損失上限({config.MAX_DAILY_LOSS * 100:.0f}%)に達している"

    return True, "OK"


def has_position(symbol: str) -> bool:
    return any(p.symbol == symbol for p in trading.get_all_positions())
