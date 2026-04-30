"""tracker.py と report.py の計算ロジックをテストする"""

import sys
import math
from datetime import date

sys.path.insert(0, "src")


# --- tracker.py のテスト ---


def test_tracker_init_and_record(tmp_path, monkeypatch):
    import trading.tracker as tracker

    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "test.db")

    tracker.init_db()
    assert (tmp_path / "test.db").exists()


def test_record_performance_and_get(tmp_path, monkeypatch):
    import trading.tracker as tracker

    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "test.db")

    tracker.record_performance(date(2025, 1, 2), 101_000.0, 1000.0)
    tracker.record_performance(date(2025, 1, 3), 100_500.0, -500.0)
    tracker.record_performance(date(2025, 1, 6), 102_000.0, 1500.0)

    rows = tracker.get_performance(days=30)
    assert len(rows) == 3
    assert rows[0]["date"] == "2025-01-02"
    assert rows[-1]["equity"] == 102_000.0


def test_record_performance_upsert(tmp_path, monkeypatch):
    import trading.tracker as tracker

    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "test.db")

    tracker.record_performance(date(2025, 1, 2), 100_000.0, 0.0)
    tracker.record_performance(date(2025, 1, 2), 101_000.0, 1000.0)

    rows = tracker.get_performance(days=30)
    assert len(rows) == 1
    assert rows[0]["equity"] == 101_000.0


def test_record_order_dict(tmp_path, monkeypatch):
    import trading.tracker as tracker
    from datetime import date

    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "test.db")

    today = date.today().isoformat()
    order = {
        "id": "abc-123",
        "symbol": "AAPL",
        "side": "buy",
        "qty": 10.0,
        "filled_qty": 0.0,
        "filled_avg_price": None,
        "status": "pending",
        "created_at": f"{today}T10:00:00",
        "filled_at": None,
    }
    tracker.record_order(order)

    rows = tracker.get_orders(days=7)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"


def test_record_fill(tmp_path, monkeypatch):
    import trading.tracker as tracker
    from datetime import date

    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "test.db")

    today = date.today().isoformat()
    order = {
        "id": "xyz-456",
        "symbol": "MSFT",
        "side": "buy",
        "qty": 5.0,
        "filled_qty": 0.0,
        "filled_avg_price": None,
        "status": "pending",
        "created_at": f"{today}T10:00:00",
        "filled_at": None,
    }
    tracker.record_order(order)
    tracker.record_fill("xyz-456", 300.0, 5.0)

    rows = tracker.get_orders(days=7)
    assert rows[0]["status"] == "filled"
    assert rows[0]["filled_avg_price"] == 300.0


# --- report.py の計算ロジックテスト ---


def test_sharpe_normal():
    import importlib.util

    sys.path.insert(0, "scripts")
    import importlib

    spec = importlib.util.spec_from_file_location("report", "scripts/report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    pnls = [100.0, -50.0, 200.0, 150.0, -30.0]
    sr = mod.sharpe(pnls)
    assert not math.isnan(sr)
    assert isinstance(sr, float)


def test_sharpe_too_short():
    import importlib

    spec = importlib.util.spec_from_file_location("report", "scripts/report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert math.isnan(mod.sharpe([100.0]))
    assert math.isnan(mod.sharpe([]))


def test_max_drawdown_flat():
    import importlib

    spec = importlib.util.spec_from_file_location("report", "scripts/report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.max_drawdown([100_000.0, 100_000.0, 100_000.0]) == 0.0


def test_max_drawdown_decline():
    import importlib

    spec = importlib.util.spec_from_file_location("report", "scripts/report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    equities = [100_000.0, 110_000.0, 99_000.0, 105_000.0]
    dd = mod.max_drawdown(equities)
    expected = (110_000 - 99_000) / 110_000
    assert abs(dd - expected) < 1e-9
