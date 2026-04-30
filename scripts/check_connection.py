"""Alpaca接続確認・口座情報表示"""

import sys

sys.path.insert(0, "src")

from trading.broker import get_account, get_positions
from loguru import logger


def main():
    acct = get_account()
    logger.info(f"口座ID       : {acct.id}")
    logger.info(f"ステータス   : {acct.status}")
    logger.info(f"現金         : ${float(acct.cash):,.2f}")
    logger.info(f"ポートフォリオ: ${float(acct.portfolio_value):,.2f}")
    logger.info(f"買付余力     : ${float(acct.buying_power):,.2f}")

    positions = get_positions()
    if positions:
        logger.info(f"保有銘柄数   : {len(positions)}")
        for p in positions:
            logger.info(f"  {p.symbol}: {p.qty}株 @ ${float(p.current_price):,.2f}")
    else:
        logger.info("保有ポジションなし")


if __name__ == "__main__":
    main()
