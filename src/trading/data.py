from datetime import datetime, timedelta
import pandas as pd
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from . import broker


def get_bars(
    symbol: str, days: int = 60, timeframe: TimeFrame = TimeFrame.Day
) -> pd.DataFrame:
    end = datetime.now()
    start = end - timedelta(days=days)
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
    return df
