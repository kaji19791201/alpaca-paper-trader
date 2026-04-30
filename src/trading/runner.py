"""メインループ: 全銘柄をスキャンしてシグナルを評価・執行する"""
from loguru import logger
from . import config
from . data import get_bars
from . strategy.ma_cross import MACrossStrategy
from . strategy.base import Signal
from . import risk, executor


def run_once(dry_run: bool = False):
    strategy = MACrossStrategy()
    logger.info(f"=== スキャン開始 ({len(config.UNIVERSE)}銘柄) dry_run={dry_run} ===")

    for symbol in config.UNIVERSE:
        try:
            df = get_bars(symbol, days=120)
            result = strategy.generate(symbol, df)

            if result.signal == Signal.HOLD:
                logger.debug(f"{symbol}: HOLD  {result.reason}")
                continue

            logger.info(f"{symbol}: {result.signal.value.upper()}  {result.reason}")

            if result.signal == Signal.BUY:
                ok, reason = risk.can_open(symbol)
                if not ok:
                    logger.info(f"{symbol}: BUYスキップ → {reason}")
                    continue
                qty = risk.position_size(symbol)
                if not dry_run:
                    executor.buy(symbol, qty)
                else:
                    logger.info(f"[DRY] BUY {symbol} x{qty}")

            elif result.signal == Signal.SELL:
                if not risk.has_position(symbol):
                    logger.debug(f"{symbol}: 未保有につきSELLスキップ")
                    continue
                if not dry_run:
                    executor.sell(symbol)
                else:
                    logger.info(f"[DRY] SELL {symbol}")

        except Exception as e:
            logger.error(f"{symbol}: エラー → {e}")

    logger.info("=== スキャン完了 ===")
