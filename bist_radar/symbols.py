# ============================================================
# BIST endeks listeleri
#
# NOT: Endeks bileşenleri Borsa İstanbul tarafından her çeyrek
# güncellenir. Güncel liste için:
#   https://www.borsaistanbul.com/tr/endeksler
# Listede olmayan / adı değişen hisse, taramada "veri yok"
# olarak raporlanır; programı bozmaz. Listeyi buradan düzenleyin.
# ============================================================

BIST30 = [
    "AKBNK", "ALARK", "ASELS", "ASTOR", "BIMAS", "DSTKF", "EKGYO",
    "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF", "ISCTR", "KCHOL",
    "KRDMD", "MGROS", "PETKM", "PGSUS", "SAHOL", "SASA", "SISE",
    "TAVHL", "TCELL", "THYAO", "TOASO", "TRALT", "TTKOM", "TUPRS",
    "ULKER", "YKBNK",
]

_BIST50_EXTRA = [
    "AEFES", "AGHOL", "AKSA", "AKSEN", "ARCLK", "BRSAN", "CCOLA",
    "CIMSA", "DOAS", "ENJSA", "HALKB", "HEKTS", "KONTR", "MAVI",
    "MPARK", "OYAKC", "SOKM", "TSKB", "TTRAK", "VAKBN",
]

_BIST100_EXTRA = [
    "AGROT", "AHGAZ", "AKFYE", "ALFAS", "ALTNY", "ANSGR", "BERA",
    "BINHO", "BJKAS", "BSOKE", "BTCIM", "CANTE", "CLEBI", "CWENE",
    "DOHOL", "ECILC", "EGEEN", "ENERY", "ENTRA", "EUPWR", "FENER",
    "GESAN", "GLRMK", "GRSEL", "GSRAY", "IEYHO", "ISMEN", "KCAER",
    "KONYA", "KTLEV", "LMKDC", "MAGEN", "MIATK", "OBAMS", "ODAS",
    "OTKAR", "PASEU", "PSGYO", "QUAGR", "RALYH", "REEDR", "SKBNK",
    "SMRTG", "TABGD", "TKFEN", "TUKAS", "TURSG", "VESTL", "YEOTK",
    "ZOREN",
]

BIST50 = BIST30 + _BIST50_EXTRA
BIST100 = BIST50 + _BIST100_EXTRA

INDEXES = {
    "BIST 30": BIST30,
    "BIST 50": BIST50,
    "BIST 100": BIST100,
}


def parse_custom_list(text: str) -> list[str]:
    """'asels, thyao  KCHOL\\nSASA.IS' -> ['ASELS', 'THYAO', 'KCHOL', 'SASA']"""
    out: list[str] = []
    for raw in text.replace(",", " ").replace(";", " ").split():
        code = raw.strip().upper().removesuffix(".IS")
        if code.isalnum() and code not in out:
            out.append(code)
    return out


def to_yahoo(code: str) -> str:
    return f"{code}.IS"
