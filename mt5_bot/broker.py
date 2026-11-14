# ============================================================
# MT5 Endeks Botu — MetaTrader 5 bağlantısı
#
# Gereksinim: Windows + açık MT5 terminali + "Algo Trading" düğmesi AÇIK
#   pip install MetaTrader5
# ============================================================

from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd

ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2
SYMBOL_FILLING_FOK, SYMBOL_FILLING_IOC = 1, 2


@dataclass
class SymbolSpec:
    name: str
    digits: int
    point: float
    tick_size: float
    tick_value: float
    volume_min: float
    volume_step: float
    volume_max: float
    stops_level: int
    filling_mode: int


@dataclass
class Position:
    ticket: int
    symbol: str
    direction: str
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float


@dataclass
class OrderResult:
    ok: bool
    message: str
    ticket: int = 0
    price: float = 0.0


class MT5Broker:
    def __init__(self, magic: int, deviation: int):
        import MetaTrader5 as mt5  # yalnızca Windows

        self.mt5 = mt5
        self.magic = magic
        self.deviation = deviation

    # ---------- bağlantı / hesap
    def connect(self) -> None:
        kwargs = {}
        if os.getenv("MT5_LOGIN"):
            kwargs = {
                "login": int(os.environ["MT5_LOGIN"]),
                "password": os.getenv("MT5_PASSWORD", ""),
                "server": os.getenv("MT5_SERVER", ""),
            }
        if os.getenv("MT5_PATH"):
            kwargs["path"] = os.environ["MT5_PATH"]
        if not self.mt5.initialize(**kwargs):
            raise RuntimeError(f"MT5'e bağlanılamadı: {self.mt5.last_error()}")

    def shutdown(self) -> None:
        self.mt5.shutdown()

    def is_demo(self) -> bool:
        return self.mt5.account_info().trade_mode == self.mt5.ACCOUNT_TRADE_MODE_DEMO

    def account(self) -> dict:
        a = self.mt5.account_info()
        return {"login": a.login, "server": a.server, "currency": a.currency,
                "balance": a.balance, "equity": a.equity}

    def algo_trading_enabled(self) -> bool:
        info = self.mt5.terminal_info()
        return bool(info and info.trade_allowed)

    def find_symbols(self, patterns=("*100*", "*500*", "*NAS*", "*SPX*", "*US*")) -> list[str]:
        names: set[str] = set()
        for p in patterns:
            for s in self.mt5.symbols_get(group=p) or []:
                names.add(s.name)
        return sorted(names)

    # ---------- piyasa verisi
    def spec(self, symbol: str) -> SymbolSpec:
        if not self.mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Sembol bulunamadı: {symbol} (--list-symbols ile kontrol edin)")
        s = self.mt5.symbol_info(symbol)
        return SymbolSpec(symbol, s.digits, s.point, s.trade_tick_size, s.trade_tick_value,
                          s.volume_min, s.volume_step, s.volume_max, s.trade_stops_level,
                          s.filling_mode)

    def closed_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        tf = getattr(self.mt5, f"TIMEFRAME_{timeframe}")
        rates = self.mt5.copy_rates_from_pos(symbol, tf, 0, count + 1)
        if rates is None or len(rates) < 2:
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df.index = pd.to_datetime(df["time"], unit="s")  # sunucu saati
        return df[["open", "high", "low", "close"]].iloc[:-1]  # son (oluşan) bar hariç

    def history_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        return self.closed_bars(symbol, timeframe, count)

    def tick(self, symbol: str) -> tuple[float, float]:
        t = self.mt5.symbol_info_tick(symbol)
        return t.bid, t.ask

    def positions(self, symbol: str | None = None) -> list[Position]:
        raw = self.mt5.positions_get(symbol=symbol) if symbol else self.mt5.positions_get()
        out = []
        for p in raw or []:
            if p.magic != self.magic:
                continue
            out.append(Position(p.ticket, p.symbol, "BUY" if p.type == 0 else "SELL",
                                p.volume, p.price_open, p.sl, p.tp, p.profit))
        return out

    # ---------- emirler
    def _filling(self, spec: SymbolSpec) -> int:
        if spec.filling_mode & SYMBOL_FILLING_FOK:
            return ORDER_FILLING_FOK
        if spec.filling_mode & SYMBOL_FILLING_IOC:
            return ORDER_FILLING_IOC
        return ORDER_FILLING_RETURN

    def _request(self, spec, direction, volume, price, sl=0.0, tp=0.0, position=0, comment="mt5_bot"):
        mt5 = self.mt5
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": spec.name,
            "volume": float(volume),
            "type": mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling(spec),
        }
        if sl:
            req["sl"] = sl
        if tp:
            req["tp"] = tp
        if position:
            req["position"] = position
        return req

    def send(self, spec, direction, volume, price, sl, tp, dry_run: bool) -> OrderResult:
        req = self._request(spec, direction, volume, price, sl, tp)
        if dry_run:
            chk = self.mt5.order_check(req)  # emri GÖNDERMEDEN doğrular (marjin vb.)
            if chk is None:
                return OrderResult(False, f"order_check hatası: {self.mt5.last_error()}")
            return OrderResult(chk.retcode == 0, f"[KURU] kontrol: {chk.comment}", 0, price)
        res = self.mt5.order_send(req)
        if res is None:
            return OrderResult(False, f"order_send hatası: {self.mt5.last_error()}")
        ok = res.retcode == self.mt5.TRADE_RETCODE_DONE
        return OrderResult(ok, f"{res.retcode} {res.comment}", res.order, res.price)

    def close(self, pos: Position, dry_run: bool) -> OrderResult:
        spec = self.spec(pos.symbol)
        bid, ask = self.tick(pos.symbol)
        direction = "SELL" if pos.direction == "BUY" else "BUY"
        price = bid if direction == "SELL" else ask
        if dry_run:
            return OrderResult(True, "[KURU] kapatma atlandı")
        req = self._request(spec, direction, pos.volume, price, position=pos.ticket, comment="mt5_bot close")
        res = self.mt5.order_send(req)
        if res is None:
            return OrderResult(False, f"order_send hatası: {self.mt5.last_error()}")
        return OrderResult(res.retcode == self.mt5.TRADE_RETCODE_DONE, f"{res.retcode} {res.comment}")
