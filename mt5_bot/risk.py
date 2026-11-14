# ============================================================
# MT5 Endeks Botu — Risk yönetimi
# ============================================================

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date


def position_size(
    balance: float,
    risk_pct: float,
    sl_distance: float,
    tick_size: float,
    tick_value: float,
    volume_min: float,
    volume_step: float,
    volume_max: float,
) -> tuple[float, str]:
    """
    Zarar kes seviyesine gelindiğinde kaybın bakiyenin risk_pct'i
    kadar olacağı lot miktarını hesaplar.
    Dönüş: (lot, açıklama). lot == 0 ise işlem açılmamalı.
    """
    if min(balance, sl_distance, tick_size, tick_value, volume_step) <= 0:
        return 0.0, "geçersiz sembol/hesap bilgisi"
    risk_money = balance * risk_pct / 100
    loss_per_lot = sl_distance / tick_size * tick_value
    raw = risk_money / loss_per_lot
    volume = math.floor(raw / volume_step + 1e-9) * volume_step
    volume = round(min(volume, volume_max), 8)
    if volume < volume_min:
        # En küçük lot bile planlanan riskin 1.5 katından fazlaysa işlem yapma
        if volume_min * loss_per_lot > risk_money * 1.5:
            return 0.0, (
                f"en küçük lot ({volume_min}) riski {volume_min * loss_per_lot:.2f} > "
                f"izin verilen {risk_money:.2f}; işlem atlandı"
            )
        volume = volume_min
    return volume, f"risk {risk_money:.2f} / lot başı kayıp {loss_per_lot:.2f}"


@dataclass
class DailyGuard:
    """Günlük kayıp ve işlem sayısı sınırı."""
    max_daily_loss_pct: float
    max_trades_per_day: int
    day: date | None = None
    start_equity: float = 0.0
    trades_today: int = 0
    halted: bool = False
    halt_reason: str = ""
    _log: list = field(default_factory=list)

    def new_day_check(self, today: date, equity: float) -> None:
        if self.day != today:
            self.day = today
            self.start_equity = equity
            self.trades_today = 0
            self.halted = False
            self.halt_reason = ""

    def check_loss(self, equity: float) -> bool:
        """Günlük kayıp sınırı aşıldıysa True (bot durmalı)."""
        if self.start_equity <= 0:
            return False
        loss_pct = (self.start_equity - equity) / self.start_equity * 100
        if loss_pct >= self.max_daily_loss_pct:
            self.halted = True
            self.halt_reason = f"günlük kayıp %{loss_pct:.2f} ≥ %{self.max_daily_loss_pct}"
        return self.halted

    def can_trade(self) -> tuple[bool, str]:
        if self.halted:
            return False, self.halt_reason
        if self.trades_today >= self.max_trades_per_day:
            return False, f"günlük işlem sınırı ({self.max_trades_per_day}) doldu"
        return True, ""

    def record_trade(self) -> None:
        self.trades_today += 1
