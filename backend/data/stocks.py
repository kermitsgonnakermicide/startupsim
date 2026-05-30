"""Master startup list for StartupMarket — AI-powered private startup valuation simulator.
All companies below are private/unlisted Indian startups. Prices are derived from
BASE_VALUATIONS (in ₹ crore) modulated by real-time demand pressure from student trades.
"""

STOCKS = [
    # FINTECH
    {"symbol": "RZRPAY", "name": "Razorpay", "sector": "Fintech"},
    {"symbol": "BHARATPE", "name": "BharatPe", "sector": "Fintech"},
    {"symbol": "JUSPAY", "name": "Juspay", "sector": "Fintech"},
    {"symbol": "KREDITBEE", "name": "KreditBee", "sector": "Fintech"},
    {"symbol": "SLICE", "name": "Slice", "sector": "Fintech"},
    {"symbol": "UNICARDS", "name": "Uni Cards", "sector": "Fintech"},
    {"symbol": "RAISE", "name": "Raise Financial", "sector": "Fintech"},
    {"symbol": "JUPITER", "name": "Jupiter Money", "sector": "Fintech"},
    {"symbol": "FIMONEY", "name": "Fi Money", "sector": "Fintech"},
    {"symbol": "FREO", "name": "Freo", "sector": "Fintech"},
    {"symbol": "CASHFREE", "name": "Cashfree Payments", "sector": "Fintech"},
    {"symbol": "SETU", "name": "Setu", "sector": "Fintech"},
    {"symbol": "PERFIOS", "name": "Perfios", "sector": "Fintech"},
    {"symbol": "SIGNZY", "name": "Signzy", "sector": "Fintech"},
    {"symbol": "YAP", "name": "Yap", "sector": "Fintech"},
    # EDTECH
    {"symbol": "MERITTO", "name": "Meritto", "sector": "Edtech"},
    {"symbol": "CLASSPLUS", "name": "Classplus", "sector": "Edtech"},
    {"symbol": "TEACHMINT", "name": "Teachmint", "sector": "Edtech"},
    {"symbol": "SCALER", "name": "Scaler Academy", "sector": "Edtech"},
    {"symbol": "LEVEDU", "name": "Leverage Edu", "sector": "Edtech"},
    {"symbol": "PRACTICAL", "name": "Practically", "sector": "Edtech"},
    {"symbol": "SUNSTONE", "name": "Sunstone Eduversity", "sector": "Edtech"},
    {"symbol": "INURTURE", "name": "iNurture", "sector": "Edtech"},
    # HEALTHTECH
    {"symbol": "PRISTYN", "name": "Pristyn Care", "sector": "Healthtech"},
    {"symbol": "INNOVACR", "name": "Innovaccer", "sector": "Healthtech"},
    {"symbol": "MFINE", "name": "Mfine", "sector": "Healthtech"},
    {"symbol": "HLTHPLIX", "name": "Healthplix", "sector": "Healthtech"},
    {"symbol": "MEDIKABZ", "name": "Medikabazaar", "sector": "Healthtech"},
    {"symbol": "WELLTHY", "name": "Wellthy Therapeutics", "sector": "Healthtech"},
    {"symbol": "TRICOG", "name": "Tricog Health", "sector": "Healthtech"},
    {"symbol": "NIRAMAI", "name": "Niramai", "sector": "Healthtech"},
    {"symbol": "SIGTUPLE", "name": "SigTuple", "sector": "Healthtech"},
    {"symbol": "PERIWKL", "name": "Periwinkle Tech", "sector": "Healthtech"},
    # AGRITECH
    {"symbol": "DEHAAT", "name": "DeHaat", "sector": "Agritech"},
    {"symbol": "NINJACART", "name": "Ninjacart", "sector": "Agritech"},
    {"symbol": "BIJAK", "name": "Bijak", "sector": "Agritech"},
    {"symbol": "AGROSTAR", "name": "AgroStar", "sector": "Agritech"},
    {"symbol": "GRAMOPH", "name": "Gramophone", "sector": "Agritech"},
    {"symbol": "FARMART", "name": "Farmart", "sector": "Agritech"},
    {"symbol": "ARYAAG", "name": "Arya.ag", "sector": "Agritech"},
    {"symbol": "WAYCOOL", "name": "WayCool Foods", "sector": "Agritech"},
    {"symbol": "JAIKISAN", "name": "Jai Kisan", "sector": "Agritech"},
    {"symbol": "SAMUNNATI", "name": "Samunnati", "sector": "Agritech"},
    # LOGISTICS
    {"symbol": "SHIPRKT", "name": "Shiprocket", "sector": "Logistics"},
    {"symbol": "SHWFAX", "name": "Shadowfax", "sector": "Logistics"},
    {"symbol": "PICKRR", "name": "Pickrr", "sector": "Logistics"},
    {"symbol": "ELASTRUN", "name": "ElasticRun", "sector": "Logistics"},
    {"symbol": "FAREYE", "name": "FarEye", "sector": "Logistics"},
    {"symbol": "LOCUS", "name": "Locus", "sector": "Logistics"},
    {"symbol": "LOADSHARE", "name": "Loadshare Networks", "sector": "Logistics"},
    {"symbol": "ITHINKLOG", "name": "iThink Logistics", "sector": "Logistics"},
    {"symbol": "PROZO", "name": "Prozo", "sector": "Logistics"},
    # SAAS / B2B
    {"symbol": "ZOHO", "name": "Zoho Corporation", "sector": "SaaS"},
    {"symbol": "DRWNBOX", "name": "Darwinbox", "sector": "SaaS"},
    {"symbol": "FACILIO", "name": "Facilio", "sector": "SaaS"},
    {"symbol": "UNIPHORE", "name": "Uniphore", "sector": "SaaS"},
    {"symbol": "EXOTEL", "name": "Exotel", "sector": "SaaS"},
    {"symbol": "KAPTUREX", "name": "Kapture CX", "sector": "SaaS"},
    {"symbol": "LEADSQR", "name": "LeadSquared", "sector": "SaaS"},
    {"symbol": "ZENOTI", "name": "Zenoti", "sector": "SaaS"},
    # CONSUMER / D2C
    {"symbol": "WAKEFIT", "name": "Wakefit", "sector": "Consumer"},
    {"symbol": "LICIOUS", "name": "Licious", "sector": "Consumer"},
    {"symbol": "CTRYDEL", "name": "Country Delight", "sector": "Consumer"},
    {"symbol": "VAHDAM", "name": "Vahdam Teas", "sector": "Consumer"},
    {"symbol": "BOMBSHAV", "name": "Bombay Shaving Company", "sector": "Consumer"},
    {"symbol": "PEESAFE", "name": "Pee Safe", "sector": "Consumer"},
    {"symbol": "USTRAA", "name": "Ustraa", "sector": "Consumer"},
    {"symbol": "HUFT", "name": "Heads Up For Tails", "sector": "Consumer"},
    {"symbol": "MOKOBARA", "name": "Mokobara", "sector": "Consumer"},
    # EV / CLEANTECH
    {"symbol": "BOUNCE", "name": "Bounce Infinity", "sector": "EV & Cleantech"},
    {"symbol": "YULU", "name": "Yulu", "sector": "EV & Cleantech"},
    {"symbol": "EULERMOT", "name": "Euler Motors", "sector": "EV & Cleantech"},
    {"symbol": "LOG9MAT", "name": "Log9 Materials", "sector": "EV & Cleantech"},
    {"symbol": "ZYPPEV", "name": "Zypp Electric", "sector": "EV & Cleantech"},
    {"symbol": "OBENEV", "name": "Oben Electric", "sector": "EV & Cleantech"},
    {"symbol": "CHARZER", "name": "Charzer", "sector": "EV & Cleantech"},
    {"symbol": "STATIQ", "name": "Statiq", "sector": "EV & Cleantech"},
    # GAMING / CREATOR
    {"symbol": "MPL", "name": "Mobile Premier League", "sector": "Gaming"},
    {"symbol": "WINZO", "name": "WinZO Games", "sector": "Gaming"},
    {"symbol": "BOMBPLAY", "name": "Bombay Play", "sector": "Gaming"},
    {"symbol": "ROOTER", "name": "Rooter", "sector": "Gaming"},
    {"symbol": "LOCO", "name": "Loco", "sector": "Gaming"},
    {"symbol": "SHARECHAT", "name": "ShareChat", "sector": "Gaming"},
    {"symbol": "KUTUMB", "name": "Kutumb", "sector": "Gaming"},
    # SPACE / DEEPTECH
    {"symbol": "AGNIKUL", "name": "Agnikul Cosmos", "sector": "Deeptech"},
    {"symbol": "SKYROOT", "name": "Skyroot Aerospace", "sector": "Deeptech"},
    {"symbol": "PIXXEL", "name": "Pixxel", "sector": "Deeptech"},
    {"symbol": "SATTVA", "name": "Sattva Space", "sector": "Deeptech"},
    {"symbol": "BELLATRX", "name": "Bellatrix Aerospace", "sector": "Deeptech"},
]

# Valuation in ₹ crore — updated to realistic 2026 estimates based on
# latest funding rounds, markdowns (BharatPe, ShareChat, MPL, Bounce),
# and growth (Innovaccer, Slice).
BASE_VALUATIONS = {
    # FINTECH
    "RZRPAY": 60000, "BHARATPE": 14000, "JUSPAY": 8500, "KREDITBEE": 6000,
    "SLICE": 15000, "UNICARDS": 1800, "RAISE": 4500, "JUPITER": 5500,
    "FIMONEY": 3000, "FREO": 2200, "CASHFREE": 7500, "SETU": 1500,
    "PERFIOS": 8000, "SIGNZY": 1700, "YAP": 350,
    # EDTECH
    "MERITTO": 1200, "CLASSPLUS": 4000, "TEACHMINT": 1800,
    "SCALER": 6500, "LEVEDU": 1500, "PRACTICAL": 600, "SUNSTONE": 700, "INURTURE": 350,
    # HEALTHTECH
    "PRISTYN": 12000, "INNOVACR": 30000, "MFINE": 1200, "HLTHPLIX": 800,
    "MEDIKABZ": 2800, "WELLTHY": 450, "TRICOG": 700, "NIRAMAI": 500,
    "SIGTUPLE": 600, "PERIWKL": 400,
    # AGRITECH
    "DEHAAT": 6500, "NINJACART": 11000, "BIJAK": 2200, "AGROSTAR": 1900,
    "GRAMOPH": 900, "FARMART": 700, "ARYAAG": 2200, "WAYCOOL": 3500,
    "JAIKISAN": 1300, "SAMUNNATI": 2000,
    # LOGISTICS
    "SHIPRKT": 9500, "SHWFAX": 7000, "PICKRR": 1300, "ELASTRUN": 8000,
    "FAREYE": 4500, "LOCUS": 2800, "LOADSHARE": 1700, "ITHINKLOG": 450, "PROZO": 700,
    # SAAS / B2B
    "ZOHO": 105000, "DRWNBOX": 8500, "FACILIO": 1700, "UNIPHORE": 21000,
    "EXOTEL": 3500, "KAPTUREX": 1100, "LEADSQR": 4500, "ZENOTI": 13000,
    # CONSUMER / D2C
    "WAKEFIT": 4500, "LICIOUS": 7000, "CTRYDEL": 3500, "VAHDAM": 1500,
    "BOMBSHAV": 850, "PEESAFE": 1000, "USTRAA": 400, "HUFT": 2250, "MOKOBARA": 600,
    # EV / CLEANTECH
    "BOUNCE": 1800, "YULU": 2500, "EULERMOT": 1500, "LOG9MAT": 1500,
    "ZYPPEV": 1300, "OBENEV": 450, "CHARZER": 400, "STATIQ": 700,
    # GAMING / CREATOR
    "MPL": 16000, "WINZO": 4500, "BOMBPLAY": 500, "ROOTER": 700,
    "LOCO": 1300, "SHARECHAT": 17000, "KUTUMB": 1300,
    # SPACE / DEEPTECH
    "AGNIKUL": 2500, "SKYROOT": 4000, "PIXXEL": 2700, "SATTVA": 600, "BELLATRX": 850,
}

# Price factor calibrated so the largest company (Zoho ~₹1,05,000 cr)
# trades at ~₹21,000 — under the ₹30,000 max-per-share guardrail.
# Smallest (YAP / INURTURE ~₹350 cr) trades at ~₹70.
# Same uniform formula applied to every company via TOTAL_SHARES_PER_COMPANY.
PRICE_FACTOR = 0.20  # legacy alias, retained for any downstream callers

STOCK_MAP = {s["symbol"]: s for s in STOCKS}

# Every company has the same total share count — a uniform cap-table scale
# typical of unicorn-stage Indian startups (~50 million shares outstanding).
# Price per share is then a function of valuation alone:
#   price = (valuation_in_₹_crore × ₹1,00,00,000 per crore) / TOTAL_SHARES
# Example: Zoho ₹1,05,000 cr → ₹21,000/share. YAP ₹350 cr → ₹70/share.
TOTAL_SHARES_PER_COMPANY = 5_00_00_000  # 5 crore = 50 million


def base_price(symbol: str) -> float:
    """Supply/demand-neutral simulator price for a symbol — derived from a
    uniform 5-crore-shares cap table applied across every company."""
    val_cr = BASE_VALUATIONS.get(symbol, 0)
    if not val_cr:
        return 0.0
    return float(val_cr) * 1_00_00_000 / TOTAL_SHARES_PER_COMPANY
