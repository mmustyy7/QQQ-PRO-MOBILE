from datetime import datetime
from zoneinfo import ZoneInfo
import logging

import numpy as np
import pandas as pd
import pytest

from mt5_bot.backtest import run_backtest
from mt5_bot.bot import Bot
from mt5_bot.broker import OrderResult, Position, SymbolSpec
from mt5_bot.config import BotConfig
from mt5_bot.risk import DailyGuard, position_size
from mt5_bot.strategy import latest_signal

NY = ZoneInfo("America/New_York")


def bars(n=600, drift=0.5, seed=0, breakout=True):
    rng = np.random.default_rng(seed)
    close = 20000 + np.cumsum(drift + rng.normal(0, 8, n))
    if breakout:
        close[-1] = close[-25:-1].max() + 40
    idx = pd.date_range("2026-11-02 14:00", periods=n, freq="15min")
    return pd.DataFrame({"open": close - 1, "high": close + 3, "low": close - 3, "close": close}, index=idx)


def test_buy_signal_on_uptrend_breakout():
    s = latest_signal(bars(), BotConfig())
    assert s and s.direction == "BUY" and s.tp_distance == pytest.approx(2 * s.sl_distance)


def test_sell_signal_on_downtrend_breakdown():
    df = bars(drift=-0.5, breakout=False)
    df.iloc[-1, df.columns.get_loc("close")] = df["low"].iloc[-25:-1].min() - 40
    s = latest_signal(df, BotConfig())
    assert s and s.direction == "SELL"
    assert latest_signal(df, BotConfig(allow_short=False)) is None


def test_no_signal_without_enough_bars():
    assert latest_signal(bars(n=100), BotConfig()) is None


def test_position_size():
    # 10000 bakiye, %0.5 risk = 50. SL 30 puan, tick 0.01 değer 0.01 => lot başı 30 kayıp
    vol, _ = position_size(10000, 0.5, 30, 0.01, 0.01, 0.01, 0.01, 100)
    assert vol == pytest.approx(1.66)
    vol, why = position_size(100, 0.5, 30, 0.01, 0.01, 1.0, 1.0, 100)
    assert vol == 0 and "atlandı" in why


def test_daily_guard():
    g = DailyGuard(2.0, 2)
    g.new_day_check(datetime(2026, 11, 2).date(), 10000)
    assert not g.check_loss(9850)
    g.record_trade(); g.record_trade()
    assert not g.can_trade()[0]
    assert g.check_loss(9790)
    g.new_day_check(datetime(2026, 11, 3).date(), 9790)
    assert g.can_trade()[0]


def test_backtest_runs_and_summarizes():
    trades, stats = run_backtest(bars(n=4000, drift=0.3, breakout=False), BotConfig())
    assert stats["işlem"] == len(trades) > 0
    for t in trades:
        assert t.exit_reason in {"SL", "TP", "gün sonu"}
        if t.exit_reason == "SL":
            assert t.result_r == pytest.approx(-1)
        if t.exit_reason == "TP":
            assert t.result_r == pytest.approx(2)


class FakeBroker:
    def __init__(self, df):
        self.df, self.sent, self.closed, self.pos = df, [], [], []
        self.equity = 10000.0

    def account(self):
        return {"balance": 10000.0, "equity": self.equity}

    def closed_bars(self, sym, tf, n):
        return self.df

    def positions(self, sym=None):
        return [p for p in self.pos if sym is None or p.symbol == sym]

    def spec(self, sym):
        return SymbolSpec(sym, 2, 0.01, 0.01, 0.01, 0.01, 0.01, 100, 0, 1)

    def tick(self, sym):
        c = float(self.df["close"].iloc[-1])
        return c - 0.5, c + 0.5

    def send(self, spec, direction, vol, price, sl, tp, dry_run):
        self.sent.append((spec.name, direction, vol, price, sl, tp, dry_run))
        return OrderResult(True, "ok")

    def close(self, p, dry_run):
        self.closed.append(p.ticket)
        return OrderResult(True, "closed")


def make_bot(tmp_path, fb, **cfg):
    c = BotConfig(symbols=["US100"], **cfg)
    return Bot(fb, c, live=False, log=logging.getLogger("t"),
               journal_path=tmp_path / "j.csv", stop_file=tmp_path / "STOP")


def test_bot_sends_order_once_per_bar(tmp_path):
    fb = FakeBroker(bars())
    bot = make_bot(tmp_path, fb)
    now = datetime(2026, 11, 4, 11, 0, tzinfo=NY)
    bot.step(now); bot.step(now)
    assert len(fb.sent) == 1
    name, d, vol, price, sl, tp, dry = fb.sent[0]
    assert d == "BUY" and dry and sl < price < tp and vol > 0
    assert (tmp_path / "j.csv").exists()


def test_bot_respects_session_and_existing_position(tmp_path):
    fb = FakeBroker(bars())
    bot = make_bot(tmp_path, fb)
    assert bot.step(datetime(2026, 11, 4, 8, 0, tzinfo=NY)) == "outside_session"
    assert bot.step(datetime(2026, 11, 7, 11, 0, tzinfo=NY)) == "outside_session"  # cumartesi
    fb.pos = [Position(1, "US100", "BUY", 1, 1, 0, 0, 0)]
    bot.step(datetime(2026, 11, 4, 11, 0, tzinfo=NY))
    assert fb.sent == []


def test_bot_daily_loss_halt_and_stop_and_eod(tmp_path):
    fb = FakeBroker(bars())
    fb.pos = [Position(7, "US100", "BUY", 1, 1, 0, 0, 0)]
    bot = make_bot(tmp_path, fb)
    bot.step(datetime(2026, 11, 4, 10, 0, tzinfo=NY))
    fb.equity = 9700
    assert bot.step(datetime(2026, 11, 4, 10, 30, tzinfo=NY)) == "halted"
    assert fb.closed == [7]

    fb2 = FakeBroker(bars()); fb2.pos = [Position(8, "US100", "BUY", 1, 1, 0, 0, 0)]
    bot2 = make_bot(tmp_path, fb2)
    bot2.step(datetime(2026, 11, 4, 15, 56, tzinfo=NY))
    assert fb2.closed == [8]

    (tmp_path / "STOP").touch()
    assert bot2.step(datetime(2026, 11, 4, 11, 0, tzinfo=NY)) == "stop"


def test_config_rejects_unknown(tmp_path):
    f = tmp_path / "c.json"; f.write_text('{"risk_per_trade_pct": 1, "typo": 2}')
    with pytest.raises(ValueError):
        BotConfig.load(f)
    f.write_text('{"risk_per_trade_pct": 1}')
    assert BotConfig.load(f).risk_per_trade_pct == 1
