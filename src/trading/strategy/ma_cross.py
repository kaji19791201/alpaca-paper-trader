import pandas as pd
from . base import BaseStrategy, StrategyResult, Signal
from .. import config


class MACrossStrategy(BaseStrategy):
    """SMA短期/長期クロス戦略"""

    def __init__(self, short: int = config.SMA_SHORT, long: int = config.SMA_LONG):
        self.short = short
        self.long  = long

    def generate(self, symbol: str, df: pd.DataFrame) -> StrategyResult:
        if len(df) < self.long + 1:
            return StrategyResult(symbol, Signal.HOLD, "データ不足")

        close = df["close"]
        sma_s = close.rolling(self.short).mean()
        sma_l = close.rolling(self.long).mean()

        prev_above = sma_s.iloc[-2] > sma_l.iloc[-2]
        curr_above = sma_s.iloc[-1] > sma_l.iloc[-1]

        if not prev_above and curr_above:
            return StrategyResult(symbol, Signal.BUY,
                f"SMA{self.short} が SMA{self.long} を上抜け "
                f"({sma_s.iloc[-1]:.2f} > {sma_l.iloc[-1]:.2f})")

        if prev_above and not curr_above:
            return StrategyResult(symbol, Signal.SELL,
                f"SMA{self.short} が SMA{self.long} を下抜け "
                f"({sma_s.iloc[-1]:.2f} < {sma_l.iloc[-1]:.2f})")

        direction = "上" if curr_above else "下"
        return StrategyResult(symbol, Signal.HOLD,
            f"クロスなし（SMA{self.short} は SMA{self.long} の{direction}）")
