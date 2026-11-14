# ============================================================
# MT5 Endeks Botu — Ana program
#
#   python -m mt5_bot.bot --list-symbols          # sembol adlarını bul
#   python -m mt5_bot.bot --backtest US100        # geçmiş veride test
#   python -m mt5_bot.bot                         # KURU çalışma (emir göndermez)
#   python -m mt5_bot.bot --live                  # demo hesapta GERÇEK emir
#
# Acil durdurma: mt5_bot klasörüne "STOP" adlı boş bir dosya koyun
# -> bot tüm pozisyonlarını kapatır ve çıkar.
# ============================================================

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time as _time
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import BotConfig
from .risk import DailyGuard, position_size
from .strategy import latest_signal

NY = ZoneInfo("America/New_York")
HERE = Path(__file__).resolve().parent
LOG_DIR = HERE / "logs"
STOP_FILE = HERE / "STOP"


def _t(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    log = logging.getLogger("mt5_bot")
    if not log.handlers:
        log.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        for h in (logging.StreamHandler(sys.stdout),
                  logging.FileHandler(LOG_DIR / "bot.log", encoding="utf-8")):
            h.setFormatter(fmt)
            log.addHandler(h)
    return log


class Bot:
    def __init__(self, broker, cfg: BotConfig, live: bool, log: logging.Logger,
                 journal_path: Path | None = None, stop_file: Path = STOP_FILE):
        self.b = broker
        self.cfg = cfg
        self.dry = not live
        self.log = log
        self.guard = DailyGuard(cfg.max_daily_loss_pct, cfg.max_trades_per_day)
        self.last_bar: dict[str, object] = {}
        self.eod_done_for = None
        self.halt_closed_for = None
        self.journal_path = journal_path or (LOG_DIR / "journal.csv")
        self.stop_file = stop_file

    # ---------------- yardımcılar
    def journal(self, **row) -> None:
        self.journal_path.parent.mkdir(exist_ok=True)
        new = not self.journal_path.exists()
        with self.journal_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row))
            if new:
                w.writeheader()
            w.writerow(row)

    def close_all(self, why: str) -> None:
        for p in self.b.positions():
            r = self.b.close(p, self.dry)
            self.log.warning("KAPAT %s %s %.2f lot (%s): %s", p.symbol, p.direction, p.volume, why, r.message)

    # ---------------- tek adım
    def step(self, now_ny: datetime) -> str:
        cfg = self.cfg
        if self.stop_file.exists():
            self.close_all("STOP dosyası")
            return "stop"

        acct = self.b.account()
        today = now_ny.date()
        self.guard.new_day_check(today, acct["equity"])

        if self.guard.check_loss(acct["equity"]):
            if self.halt_closed_for != today:
                self.log.error("GÜNLÜK KAYIP SINIRI: %s — pozisyonlar kapatılıyor", self.guard.halt_reason)
                self.close_all("günlük kayıp sınırı")
                self.halt_closed_for = today
            return "halted"

        if cfg.close_eod and now_ny.time() >= _t(cfg.close_eod_ny) and self.eod_done_for != today:
            self.close_all("gün sonu")
            self.eod_done_for = today

        if now_ny.weekday() >= 5 or not (_t(cfg.entry_start_ny) <= now_ny.time() <= _t(cfg.entry_end_ny)):
            return "outside_session"

        for sym in cfg.symbols:
            bars = self.b.closed_bars(sym, cfg.timeframe, cfg.history_bars)
            if bars.empty:
                self.log.warning("%s: veri yok", sym)
                continue
            bar_time = bars.index[-1]
            if self.last_bar.get(sym) == bar_time:
                continue  # bu bar zaten değerlendirildi
            self.last_bar[sym] = bar_time

            sig = latest_signal(bars, cfg)
            if sig is None:
                continue
            self.log.info("SİNYAL %s %s — %s", sym, sig.direction, sig.reason)

            if self.b.positions(sym):
                self.log.info("%s: zaten açık pozisyon var, atlandı", sym)
                continue
            if len(self.b.positions()) >= cfg.max_open_positions:
                self.log.info("en fazla açık pozisyon sayısına ulaşıldı, atlandı")
                continue
            ok, why = self.guard.can_trade()
            if not ok:
                self.log.info("%s: işlem yok — %s", sym, why)
                continue

            spec = self.b.spec(sym)
            bid, ask = self.b.tick(sym)
            price = ask if sig.direction == "BUY" else bid
            min_stop = spec.stops_level * spec.point
            sl_d = max(sig.sl_distance, min_stop)
            tp_d = max(sig.tp_distance, min_stop)
            if sig.direction == "BUY":
                sl, tp = price - sl_d, price + tp_d
            else:
                sl, tp = price + sl_d, price - tp_d
            sl, tp = round(sl, spec.digits), round(tp, spec.digits)

            vol, note = position_size(acct["balance"], cfg.risk_per_trade_pct, sl_d, spec.tick_size,
                                      spec.tick_value, spec.volume_min, spec.volume_step, spec.volume_max)
            if vol <= 0:
                self.log.warning("%s: %s", sym, note)
                continue

            res = self.b.send(spec, sig.direction, vol, price, sl, tp, dry_run=self.dry)
            level = logging.INFO if res.ok else logging.ERROR
            self.log.log(level, "%s %s %s %.2f lot @ %.2f SL %.2f TP %.2f (%s) -> %s",
                         "KURU" if self.dry else "EMİR", sym, sig.direction, vol, price, sl, tp, note, res.message)
            self.journal(time=now_ny.isoformat(timespec="seconds"), mode="dry" if self.dry else "live",
                         symbol=sym, direction=sig.direction, volume=vol, price=price, sl=sl, tp=tp,
                         ok=res.ok, message=res.message, reason=sig.reason)
            if res.ok:
                self.guard.record_trade()
        return "ok"


# ---------------- komut satırı
def main() -> None:
    p = argparse.ArgumentParser(description="MT5 ABD 100 / ABD 500 botu")
    p.add_argument("--config", default=str(HERE / "config.json"))
    p.add_argument("--live", action="store_true", help="Gerçekten emir gönder (varsayılan: kuru çalışma)")
    p.add_argument("--allow-real", action="store_true", help="GERÇEK (demo olmayan) hesapta çalışmaya izin ver")
    p.add_argument("--list-symbols", action="store_true")
    p.add_argument("--backtest", metavar="SEMBOL")
    p.add_argument("--bars", type=int, default=20000, help="Backtest için bar sayısı")
    p.add_argument("--once", action="store_true", help="Tek adım çalış ve çık")
    args = p.parse_args()

    cfg = BotConfig.load(args.config)
    log = setup_logging()

    from .broker import MT5Broker
    broker = MT5Broker(cfg.magic, cfg.deviation_points)
    broker.connect()
    try:
        acct = broker.account()
        log.info("Bağlandı: %s @ %s, bakiye %.2f %s, %s", acct["login"], acct["server"],
                 acct["balance"], acct["currency"], "DEMO" if broker.is_demo() else "GERÇEK HESAP")

        if args.list_symbols:
            print("\n".join(broker.find_symbols()))
            return

        if args.backtest:
            from .backtest import run_backtest
            bars = broker.history_bars(args.backtest, cfg.timeframe, args.bars)
            trades, stats = run_backtest(bars, cfg)
            print(f"\n{args.backtest} {cfg.timeframe} — {bars.index[0]} → {bars.index[-1]}")
            for k, v in stats.items():
                print(f"  {k:28s} {v}")
            out = LOG_DIR / f"backtest_{args.backtest}.csv"
            import pandas as pd
            pd.DataFrame([t.__dict__ for t in trades]).to_csv(out, index=False)
            print(f"  işlem listesi: {out}")
            return

        if not broker.is_demo() and not args.allow_real:
            log.error("Bu bir GERÇEK hesap. Güvenlik için bot durduruldu (--allow-real olmadan çalışmaz).")
            return
        if args.live and not broker.algo_trading_enabled():
            log.error("MT5'te 'Algo Trading' düğmesi kapalı. Açıp tekrar deneyin.")
            return

        for sym in cfg.symbols:
            broker.spec(sym)  # sembol adlarını baştan doğrula

        log.info("Mod: %s | Semboller: %s | %s | risk %%%s/işlem, günlük en fazla kayıp %%%s",
                 "CANLI EMİR" if args.live else "KURU ÇALIŞMA (emir gönderilmez)",
                 ", ".join(cfg.symbols), cfg.timeframe, cfg.risk_per_trade_pct, cfg.max_daily_loss_pct)

        bot = Bot(broker, cfg, live=args.live, log=log)
        while True:
            state = bot.step(datetime.now(NY))
            if state == "stop":
                log.warning("STOP dosyası bulundu, bot kapandı.")
                break
            if args.once:
                break
            _time.sleep(cfg.poll_seconds)
    except KeyboardInterrupt:
        log.info("Kullanıcı tarafından durduruldu (pozisyonlar açık bırakıldı).")
    finally:
        broker.shutdown()


if __name__ == "__main__":
    main()
