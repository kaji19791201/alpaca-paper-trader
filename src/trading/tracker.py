"""SQLite による注文・P&L 永続化"""

import sqlite3
from datetime import date, datetime, UTC
from pathlib import Path

DB_PATH = Path(__file__).parents[3] / "data" / "trading.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                id               TEXT PRIMARY KEY,
                symbol           TEXT NOT NULL,
                side             TEXT NOT NULL,
                qty              REAL NOT NULL,
                filled_qty       REAL DEFAULT 0,
                filled_avg_price REAL,
                status           TEXT NOT NULL,
                created_at       TEXT NOT NULL,
                filled_at        TEXT
            );
            CREATE TABLE IF NOT EXISTS performance (
                date       TEXT PRIMARY KEY,
                equity     REAL NOT NULL,
                daily_pnl  REAL NOT NULL
            );
        """)


def record_order(order) -> None:
    """Alpaca Order オブジェクトまたは dict を受け取って保存する"""
    if hasattr(order, "__dict__"):
        d = {
            "id": str(order.id),
            "symbol": order.symbol,
            "side": str(order.side.value)
            if hasattr(order.side, "value")
            else str(order.side),
            "qty": float(order.qty or 0),
            "filled_qty": float(order.filled_qty or 0),
            "filled_avg_price": float(order.filled_avg_price)
            if order.filled_avg_price
            else None,
            "status": str(order.status.value)
            if hasattr(order.status, "value")
            else str(order.status),
            "created_at": str(order.created_at),
            "filled_at": str(order.filled_at) if order.filled_at else None,
        }
    else:
        d = order

    init_db()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO orders (id, symbol, side, qty, filled_qty, filled_avg_price,
                                status, created_at, filled_at)
            VALUES (:id, :symbol, :side, :qty, :filled_qty, :filled_avg_price,
                    :status, :created_at, :filled_at)
            ON CONFLICT(id) DO UPDATE SET
                filled_qty       = excluded.filled_qty,
                filled_avg_price = excluded.filled_avg_price,
                status           = excluded.status,
                filled_at        = excluded.filled_at
        """,
            d,
        )


def record_fill(order_id: str, fill_price: float, fill_qty: float) -> None:
    init_db()
    with _conn() as con:
        con.execute(
            """
            UPDATE orders
            SET filled_avg_price = ?, filled_qty = ?, status = 'filled',
                filled_at = ?
            WHERE id = ?
        """,
            (fill_price, fill_qty, datetime.now(UTC).isoformat(), order_id),
        )


def record_performance(trade_date: date | str, equity: float, daily_pnl: float) -> None:
    init_db()
    key = str(trade_date)
    with _conn() as con:
        con.execute(
            """
            INSERT INTO performance (date, equity, daily_pnl)
            VALUES (?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET equity = excluded.equity, daily_pnl = excluded.daily_pnl
        """,
            (key, equity, daily_pnl),
        )


def get_performance(days: int = 30) -> list[sqlite3.Row]:
    init_db()
    with _conn() as con:
        rows = con.execute(
            """
            SELECT * FROM performance
            ORDER BY date DESC
            LIMIT ?
        """,
            (days,),
        ).fetchall()
    return list(reversed(rows))


def get_orders(days: int = 30) -> list[sqlite3.Row]:
    init_db()
    with _conn() as con:
        rows = con.execute(
            """
            SELECT * FROM orders
            WHERE created_at >= date('now', ? || ' days')
            ORDER BY created_at DESC
        """,
            (f"-{days}",),
        ).fetchall()
    return rows
