from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from . import config

trading = TradingClient(
    api_key=config.ALPACA_API_KEY,
    secret_key=config.ALPACA_SECRET_KEY,
    paper=True,
)

data = StockHistoricalDataClient(
    api_key=config.ALPACA_API_KEY,
    secret_key=config.ALPACA_SECRET_KEY,
)


def get_account():
    return trading.get_account()


def get_positions():
    return trading.get_all_positions()
