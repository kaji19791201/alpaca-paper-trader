# alpaca-paper-trader

Alpaca API を使った完全自動株式売買システム。EMA+RSI戦略＋トレーリングストップで運用。

## セットアップ

### 依存パッケージのインストール

```bash
uv sync
```

### APIキーの登録

**重要: APIキーはチャットや `!` コマンドで貼らない。これらはログに残る。**

#### ペーパートレード用（Alpaca Paper API）

```bash
cd projects/stock-trading

# 方法A: クリップボードから（推奨）
pbpaste | dotenvx set ALPACA_API_KEY
pbpaste | dotenvx set ALPACA_SECRET_KEY

# 方法B: 対話入力
read -s ALPACA_API_KEY && dotenvx set ALPACA_API_KEY "$ALPACA_API_KEY" && unset ALPACA_API_KEY
read -s ALPACA_SECRET_KEY && dotenvx set ALPACA_SECRET_KEY "$ALPACA_SECRET_KEY" && unset ALPACA_SECRET_KEY
```

ペーパー用はデフォルト設定のままでOK（`ALPACA_BASE_URL` は `paper-api.alpaca.markets` を向いている）。

#### 本番用（Alpaca Live API）

```bash
# 本番キーを登録
pbpaste | dotenvx set ALPACA_LIVE_API_KEY
pbpaste | dotenvx set ALPACA_LIVE_SECRET_KEY

# 本番URLに切り替え
dotenvx set ALPACA_BASE_URL "https://api.alpaca.markets"
```

本番実行は明示的に `scripts/run_live.py` を使う。ペーパーと本番のキーは別変数で管理する。

### 接続確認

```bash
dotenvx run -- uv run python -c "
from trading.broker import get_broker
b = get_broker()
print(b.get_account())
"
```

## 実行方法

### ペーパートレード（1回実行）

```bash
dotenvx run -- uv run python scripts/run_paper.py --once
```

### ペーパートレード（ループ実行）

```bash
dotenvx run -- uv run python scripts/run_paper.py
```

### バックテスト

```bash
dotenvx run -- uv run python scripts/backtest.py --start 2023-01-01 --end 2024-12-31
dotenvx run -- uv run python scripts/backtest.py --compare   # 戦略比較
```

### P&Lレポート

```bash
dotenvx run -- uv run python scripts/report.py --days 7
```

### 手動売買 CLI

```bash
dotenvx run -- uv run python scripts/trade.py list
dotenvx run -- uv run python scripts/trade.py buy AAPL 1
dotenvx run -- uv run python scripts/trade.py cancel --all
```

## 戦略

現行: **EMA10/30 + RSIフィルター + トレーリングストップ10%**

| 条件 | アクション |
|------|-----------|
| EMA10 > EMA30 かつ RSI 50-70 | BUY |
| RSI > 80 | SELL（過熱エグジット） |
| EMA10 < EMA30 | SELL |
| エントリー価格から-10% | トレーリングストップ自動発動 |

バックテスト2年（2023-2024）: +24.91%（年率〜11.8%）

## リスク設定

```python
UNIVERSE          = 20銘柄（S&P500流動性上位）
POSITION_SIZE_PCT = 0.10   # 口座残高の10%/銘柄
MAX_POSITIONS     = 5
TRAILING_STOP_PCT = 10.0   # %
MAX_DAILY_LOSS    = 0.05   # 日次-5%でその日の取引停止（10%trailing×5pos最悪ケース対応）
```

## 自動実行スケジュール

| ジョブ | 時刻 | Routine ID |
|--------|------|------------|
| ペーパートレード（毎営業日） | 13:35 UTC（9:35 ET） | `trig_01K91YxuWUAcR8qa6gky5nRA` |
| 週次P&Lレポート（毎週月曜） | 14:00 UTC | `trig_017S24zQEBzeyha1pJ4xMt87` |

## 本番移行判断基準

以下をすべて満たしたら `run_live.py` に切り替える：

1. ペーパーで2週間以上連続稼働
2. 勝率 > 55%
3. 最大ドローダウン < 10%
4. シャープレシオ > 1.0
