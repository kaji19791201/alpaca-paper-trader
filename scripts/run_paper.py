"""ペーパートレード実行スクリプト
起動方法:
  dotenvx run -- uv run python scripts/run_paper.py          # 定期実行（毎日9:35 ET）
  dotenvx run -- uv run python scripts/run_paper.py --once   # 今すぐ1回だけ
  dotenvx run -- uv run python scripts/run_paper.py --dry    # シグナル確認のみ（注文しない）
"""
import sys, argparse
sys.path.insert(0, "src")

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from trading.runner import run_once


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="1回実行して終了")
    parser.add_argument("--dry",  action="store_true", help="シグナル確認のみ（注文なし）")
    args = parser.parse_args()

    if args.once or args.dry:
        run_once(dry_run=args.dry)
        return

    scheduler = BlockingScheduler(timezone="America/New_York")
    # 毎取引日 9:35（市場オープン5分後）に実行
    scheduler.add_job(
        run_once,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=35, timezone="America/New_York"),
        kwargs={"dry_run": False},
    )
    logger.info("スケジューラ起動: 毎取引日 9:35 ET に実行")
    scheduler.start()


if __name__ == "__main__":
    main()
