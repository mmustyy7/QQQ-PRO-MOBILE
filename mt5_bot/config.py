# ============================================================
# MT5 Endeks Botu — Ayarlar
#
# Değiştirmek için mt5_bot/config.json oluşturun (örnek:
# config.example.json). JSON'da olmayan alanlar varsayılanı kullanır.
# ============================================================

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


@dataclass
class BotConfig:
    # --- Semboller: FP Markets'taki adları Piyasa Gözlemi'nden kontrol edin
    #     (python -m mt5_bot.bot --list-symbols)
    symbols: list[str] = field(default_factory=lambda: ["US100", "US500"])
    timeframe: str = "M15"            # M1, M5, M15, M30, H1, H4, D1
    history_bars: int = 400

    # --- Strateji: trend filtresi + kırılım (breakout)
    ema_fast: int = 50
    ema_slow: int = 200
    breakout_bars: int = 20           # son N barın en yüksek/en düşüğü
    atr_period: int = 14
    sl_atr: float = 1.5               # zarar kes = 1.5 × ATR
    tp_atr: float = 3.0               # kâr al   = 3.0 × ATR  (2R)
    allow_short: bool = True

    # --- Risk
    risk_per_trade_pct: float = 0.5   # işlem başına bakiyenin %0.5'i
    max_daily_loss_pct: float = 2.0   # günlük kayıp bunu aşarsa bot durur
    max_open_positions: int = 2
    max_trades_per_day: int = 4

    # --- Zaman (New York saati). ABD nakit seansı 09:30-16:00
    entry_start_ny: str = "09:45"
    entry_end_ny: str = "15:30"
    close_eod: bool = True            # gün sonunda pozisyonları kapat (gece riski yok)
    close_eod_ny: str = "15:55"
    server_minus_ny_hours: int = 7    # MT5 sunucu saati - New York saati (backtest için)

    # --- Emir
    magic: int = 2611401
    deviation_points: int = 20
    backtest_spread_points: float = 1.0   # backtest maliyeti (fiyat birimi)

    poll_seconds: int = 10

    @classmethod
    def load(cls, path: str | Path | None) -> "BotConfig":
        if not path or not Path(path).exists():
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"config.json içinde bilinmeyen alan(lar): {sorted(unknown)}")
        return cls(**data)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)
