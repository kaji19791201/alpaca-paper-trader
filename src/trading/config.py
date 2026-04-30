import os

ALPACA_API_KEY = os.environ["ALPACA_API_KEY"]
ALPACA_SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]
ALPACA_BASE_URL = os.environ["ALPACA_BASE_URL"]

UNIVERSE = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "AMZN",
    "META",
    "TSLA",
    "JPM",
    "V",
    "UNH",
    "XOM",
    "LLY",
    "AVGO",
    "MA",
    "HD",
    "CVX",
    "MRK",
    "ABBV",
    "PEP",
    "KO",
]

POSITION_SIZE_PCT = 0.05
MAX_POSITIONS = 5
STOP_LOSS_PCT = 0.03
TAKE_PROFIT_PCT = 0.06
MAX_DAILY_LOSS = 0.02

SMA_SHORT = 20
SMA_LONG = 50
