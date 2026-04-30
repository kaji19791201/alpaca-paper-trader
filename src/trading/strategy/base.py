from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import pandas as pd


class Signal(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class StrategyResult:
    symbol: str
    signal: Signal
    reason: str


class BaseStrategy(ABC):
    @abstractmethod
    def generate(self, symbol: str, df: pd.DataFrame) -> StrategyResult: ...
