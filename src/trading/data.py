from datetime import datetime, timedelta, date
import pandas as pd
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from loguru import logger
from . import broker

IEX_EARLIEST = date(2020, 1, 1)


def get_bars(
    symbol: str, days: int = 60, timeframe: TimeFrame = TimeFrame.Day
) -> pd.DataFrame:
    end = datetime.now()
    start = end - timedelta(days=days)
    if start.date() < IEX_EARLIEST:
        logger.warning(
            f"{symbol}: start={start.date()} は IEX_EARLIEST({IEX_EARLIEST}) より古い。データ欠損の可能性あり"
        )
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )
    bars = broker.data.get_stock_bars(req)
    df = bars.df
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level="symbol")
    df = df.sort_index()
    if len(df) == 0:
        logger.warning(
            f"{symbol}: データが0件。IEX無料フィードの制限か銘柄コードが無効な可能性あり"
        )
    return df
