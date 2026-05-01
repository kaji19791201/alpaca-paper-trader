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

# $500実口座向け: フラクショナルシェアで10%×5ポジション
POSITION_SIZE_PCT = 0.10
MAX_POSITIONS = 5
STOP_LOSS_PCT = 0.03  # 固定SL（TRAILING_STOP_PCT使用時は未使用）
TAKE_PROFIT_PCT = 0.06  # 固定TP（TRAILING_STOP_PCT使用時は未使用）
# 10%トレーリング×5ポジション最悪ケース(5%)をカバー。30%DD許容に対して十分な余裕
MAX_DAILY_LOSS = 0.05

# トレーリングストップ（10% = 峰値から10%下落で撤退）
TRAILING_STOP_PCT = 10.0

# EMA+RSI戦略パラメータ
EMA_SHORT = 8
EMA_LONG = 30
RSI_PERIOD = 14

# 旧SMAパラメータ（後方互換）
SMA_SHORT = 20
SMA_LONG = 50
