"""EMAクロス + RSIフィルター戦略

SMAより応答が速いEMAを使い、RSIでオーバーバウト・ダイバージェンスをフィルタ。
- BUY : EMA(short) が EMA(long) を上抜け かつ 50 < RSI < 70
- SELL: EMA(short) が EMA(long) を下抜け または RSI > 80（過熱エグジット）
"""

import pandas as pd
from .base import BaseStrategy, StrategyResult, Signal


class EmaRsiStrategy(BaseStrategy):
    def __init__(
        self,
        short: int = 10,
        long: int = 30,
        rsi_period: int = 14,
        rsi_buy_min: float = 50.0,
        rsi_buy_max: float = 70.0,
        rsi_exit: float = 80.0,
    ):
        self.short = short
        self.long = long
        self.rsi_period = rsi_period
        self.rsi_buy_min = rsi_buy_min
        self.rsi_buy_max = rsi_buy_max
        self.rsi_exit = rsi_exit

    def _rsi(self, close: pd.Series) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=self.rsi_period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=self.rsi_period - 1, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float("inf"))
        return 100 - 100 / (1 + rs)

    def generate(self, symbol: str, df: pd.DataFrame) -> StrategyResult:
        min_len = self.long + self.rsi_period + 2
        if len(df) < min_len:
            return StrategyResult(symbol, Signal.HOLD, "データ不足")

        close = df["close"]
        ema_s = close.ewm(span=self.short, adjust=False).mean()
        ema_l = close.ewm(span=self.long, adjust=False).mean()
        rsi = self._rsi(close)

        prev_above = ema_s.iloc[-2] > ema_l.iloc[-2]
        curr_above = ema_s.iloc[-1] > ema_l.iloc[-1]
        rsi_now = rsi.iloc[-1]

        # オーバーバウトによる強制エグジット
        if curr_above and rsi_now > self.rsi_exit:
            return StrategyResult(
                symbol, Signal.SELL, f"RSI過熱エグジット (RSI={rsi_now:.1f})"
            )

        if not prev_above and curr_above:
            if self.rsi_buy_min <= rsi_now <= self.rsi_buy_max:
                return StrategyResult(
                    symbol,
                    Signal.BUY,
                    f"EMA{self.short}↑EMA{self.long} RSI={rsi_now:.1f}",
                )
            return StrategyResult(
                symbol,
                Signal.HOLD,
                f"EMAクロスあり / RSIフィルタ落ち ({rsi_now:.1f})",
            )

        if prev_above and not curr_above:
            return StrategyResult(
                symbol,
                Signal.SELL,
                f"EMA{self.short}↓EMA{self.long} RSI={rsi_now:.1f}",
            )

        direction = "上" if curr_above else "下"
        return StrategyResult(
            symbol,
            Signal.HOLD,
            f"シグナルなし（EMA{self.short} は EMA{self.long} の{direction}）",
        )
