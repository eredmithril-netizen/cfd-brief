
import os, requests, json, logging
from datetime import datetime

# ─── IG LIVE API ───────────────────────────────────────────────────────────────

IG_API_KEY    = os.environ.get("IG_API_KEY", "")
IG_USERNAME   = os.environ.get("IG_USERNAME", "")
IG_PASSWORD   = os.environ.get("IG_PASSWORD", "")
IG_ACCOUNT_ID = os.environ.get("IG_ACCOUNT_ID", "")
IG_BASE_URL   = "https://api.ig.com/gateway/deal"

# IG EPIC codes for instruments visible in the screenshots
IG_EPICS = {
    # Indices
    "US500":    "IX.D.SPTRD.IFS.IP",       # US 500
    "USTECH":   "IX.D.NASDAQ.IFS.IP",      # US Tech 100
    "DE40":     "IX.D.DAX.IFS.IP",         # Germany 40
    "FTSE":     "IX.D.FTSE.IFS.IP",        # FTSE 100
    "EU50":     "IX.D.STXE.IFS.IP",        # EU Stocks 50
    "FR40":     "IX.D.CAC.IFS.IP",         # France 40
    "JP225":    "IX.D.NIKKEI.IFS.IP",      # Japan 225
    "RUS2K":    "IX.D.RUSSELL.IFS.IP",     # US Russell 2000

    # FX
    "EURUSD":   "CS.D.EURUSD.MINI.IP",
    "GBPUSD":   "CS.D.GBPUSD.MINI.IP",
    "USDJPY":   "CS.D.USDJPY.MINI.IP",
    "AUDUSD":   "CS.D.AUDUSD.MINI.IP",
    "USDCHF":   "CS.D.USDCHF.MINI.IP",
    "EURGBP":   "CS.D.EURGBP.MINI.IP",
    "GBPJPY":   "CS.D.GBPJPY.MINI.IP",
    "CADJPY":   "CS.D.CADJPY.MINI.IP",
    "GBPCAD":   "CS.D.GBPCAD.MINI.IP",
    "CHFJPY":   "CS.D.CHFJPY.MINI.IP",
    "EURCAD":   "CS.D.EURCAD.MINI.IP",

    # Metals
    "XAUUSD":   "CS.D.CFDGC.CFM.IP",      # Gold Spot
    "XAGUSD":   "CS.D.CFDSI.CFM.IP",      # Silver Spot
    "XPDUSD":   "CS.D.CFDPA.CFM.IP",      # Palladium
    "XPTUSD":   "CS.D.CFDPT.CFM.IP",      # Platinum

    # Energy & Commodities
    "USOIL":    "CF.D.CRUDEOIL.OCT.IP",   # WTI Crude Oil
    "COPPER":   "CF.D.COPPER.DEC.IP",     # Copper
    "ALUMINIUM":"MT.D.ALUMINIUM.MPLY.IP", # Aluminium
    "COFFEE":   "CF.D.COFFEE.DEC.IP",     # Coffee NY
    "COCOA":    "CF.D.COCOA.DEC.IP",      # Cocoa NY
}

def ig_login():
    """Login to IG LIVE API, return session headers."""
    if not all([IG_API_KEY, IG_USERNAME, IG_PASSWORD]):
        logging.warning("IG API credentials not set")
        return None
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json; charset=UTF-8",
        "X-IG-API-KEY": IG_API_KEY,
        "Version": "3",
    }
    payload = {
        "identifier": IG_USERNAME,
        "password": IG_PASSWORD,
        "encryptedPassword": False,
    }
    try:
        r = requests.post(f"{IG_BASE_URL}/session", headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        cst   = r.headers.get("CST")
        token = r.headers.get("X-SECURITY-TOKEN")
        account_id = IG_ACCOUNT_ID or r.json().get("accountId", "")
        if not cst or not token:
            logging.error("IG login: missing CST or X-SECURITY-TOKEN")
            return None
        session_headers = {
            "X-IG-API-KEY": IG_API_KEY,
            "CST": cst,
            "X-SECURITY-TOKEN": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "IG-ACCOUNT-ID": account_id,
        }
        logging.info("IG login successful")
        return session_headers
    except Exception as e:
        logging.error(f"IG login failed: {e}")
        return None


def ig_fetch_price(session_headers, epic):
    """Fetch current BID/ASK/MID for a single IG epic."""
    try:
        url = f"{IG_BASE_URL}/markets/{epic}"
        r = requests.get(url, headers={**session_headers, "Version": "1"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            snap = data.get("snapshot", {})
            bid  = snap.get("bid")
            ask  = snap.get("offer")
            net  = snap.get("netChange", 0)
            pct  = snap.get("percentageChange", 0)
            high = snap.get("high")
            low  = snap.get("low")
            if bid and ask:
                mid = round((float(bid) + float(ask)) / 2, 6)
                return {
                    "price": mid,
                    "bid":   float(bid),
                    "ask":   float(ask),
                    "change": float(net or 0),
                    "change_pct": float(pct or 0),
                    "high": float(high) if high else None,
                    "low":  float(low) if low else None,
                    "source": "IG_LIVE",
                }
    except Exception as e:
        logging.warning(f"IG price fetch failed for {epic}: {e}")
    return None


def fetch_ig_prices():
    """Fetch all instrument prices from IG LIVE API.
    Returns dict: symbol -> price_data"""
    session = ig_login()
    if not session:
        logging.warning("IG session failed, falling back to public APIs")
        return {}

    results = {}
    for symbol, epic in IG_EPICS.items():
        data = ig_fetch_price(session, epic)
        if data:
            results[symbol] = data
            logging.info(f"  IG {symbol}: {data['price']} ({data['change_pct']:+.2f}%)")
        else:
            logging.warning(f"  IG {symbol} ({epic}): no data")

    # Logout
    try:
        requests.delete(f"{IG_BASE_URL}/session", headers=session, timeout=5)
    except:
        pass

    logging.info(f"IG prices fetched: {len(results)}/{len(IG_EPICS)} instruments")
    return results

# ─── END IG LIVE API ───────────────────────────────────────────────────────────
#!/usr/bin/env python3
"""
CFD Intraday Brief — Multi-Source Auto-Generator v2.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cenová data (priorita / fallback):
  1. Twelve Data        — 800 req/den, forex + komodity + indexy
  2. Finnhub            — 60 req/min,  real-time quotes
  3. Alpha Vantage      — 25 req/den,  záloha + technické indikátory
  4. Polygon.io         — 5 req/min,   US ETF proxy (GLD, SPY, USO)
  5. Financial Modeling Prep — 250 req/den, quote + calendar

Makroekonomika:
  - FRED API            — CPI, TIPS reálné výnosy, M2, Fed Funds, yield curve

Zprávy + sentiment:
  1. Finnhub News       — real-time, sentiment skóre -1..+1
  2. NewsAPI            — 100 req/den, business headlines
  3. Alpha Vantage News — ticker-level sentiment
  4. Benzinga RSS       — institucionální zpravodajství (bez API klíče)
  5. RSS záloha         — BBC, Reuters, MarketWatch

Doplňky (bez API klíče):
  - CNN Fear & Greed Index
  - FMP Economic Calendar (dnešní makro události)
"""

import json, os, sys, re, time, logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pytz, requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("cfd-brief")

# ── API KLÍČE (z env proměnných / GitHub Secrets) ───────────────
K = {
    "openai":       os.getenv("OPENAI_API_KEY",       ""),
    "twelvedata":   os.getenv("TWELVEDATA_API_KEY",   ""),
    "finnhub":      os.getenv("FINNHUB_API_KEY",      ""),
    "alphavantage": os.getenv("ALPHAVANTAGE_API_KEY", ""),
    "polygon":      os.getenv("POLYGON_API_KEY",      ""),
    "fmp":          os.getenv("FMP_API_KEY",          ""),
    "fred":         os.getenv("FRED_API_KEY",         ""),
    "newsapi":      os.getenv("NEWSAPI_KEY",          ""),
}

CET = pytz.timezone("Europe/Prague")

# ── SYMBOLY PRO KAŽDOU API ───────────────────────────────────────
INSTRUMENTS: Dict[str, Dict] = {
    "gold":      {"label":"Gold (XAU/USD)",    "td":"XAU/USD",  "fh":"OANDA:XAU_USD",  "av":"XAU",   "poly":"C:XAUUSD",  "fmp":"XAUUSD",  "is_big":True},
    "wti":       {"label":"WTI Crude Oil",     "td":"WTI/USD",  "fh":"OANDA:WTICO_USD","av":"USO",   "poly":"USO",       "fmp":"USOIL",   "is_big":False},
    "sp500":     {"label":"S&P 500",           "td":"SPX",      "fh":"^GSPC",           "av":"SPY",   "poly":"SPY",       "fmp":"^GSPC",   "is_big":True},
    "eurusd":    {"label":"EUR/USD",           "td":"EUR/USD",  "fh":"OANDA:EUR_USD",  "av":"EUR",   "poly":"C:EURUSD",  "fmp":"EURUSD",  "is_big":False},
    "vix":       {"label":"VIX",               "td":"VIX",      "fh":"^VIX",            "av":"VXX",   "poly":"VXX",       "fmp":"^VIX",    "is_big":False},
    "dxy":       {"label":"DXY",               "td":"DXY",      "fh":"OANDA:USD_BASKET","av":"UUP",   "poly":"UUP",       "fmp":"DXY",     "is_big":False},
    "dax":       {"label":"DAX 40",            "td":"DAX",      "fh":"^GDAXI",          "av":"EWG",   "poly":"EWG",       "fmp":"^GDAXI",  "is_big":True},
    "usdjpy":    {"label":"USD/JPY",           "td":"USD/JPY",  "fh":"OANDA:USD_JPY",  "av":"JPY",   "poly":"C:USDJPY",  "fmp":"USDJPY",  "is_big":False},
    "nasdaq":    {"label":"NASDAQ 100",        "td":"NDX",      "fh":"^IXIC",           "av":"QQQ",   "poly":"QQQ",       "fmp":"^IXIC",   "is_big":True},
    "bonds10y":  {"label":"US 10Y Yield",      "td":"US10Y",    "fh":"^TNX",            "av":"TLT",   "poly":"TLT",       "fmp":"^TNX",    "is_big":False},
    "silver":    {"label":"Silver (XAG/USD)",  "td":"XAG/USD",  "fh":"OANDA:XAG_USD",  "av":"SLV",   "poly":"SLV",       "fmp":"XAGUSD",  "is_big":False},
    "palladium": {"label":"Palladium",         "td":"XPD/USD",  "fh":"OANDA:XPD_USD",  "av":"PALL",  "poly":"PALL",      "fmp":"XPDUSD",  "is_big":True},
}

def safe_float(v, default=0.0) -> float:
    try: return float(v)
    except: return default

def pct_change(cur, prev) -> float:
    if not prev or prev == 0: return 0.0
    return round((cur - prev) / abs(prev) * 100, 2)

def fmt_price(v: float, big: bool) -> str:
    if big: return f"${v:,.2f}"
    if abs(v) > 100: return f"{v:,.2f}"
    if abs(v) > 10:  return f"{v:.2f}"
    return f"{v:.4f}"

# ═══════════════════════════════════════════════════════════════
#  1. CENOVÁ DATA
# ═══════════════════════════════════════════════════════════════

# ── 1a. Twelve Data ─────────────────────────────────────────────
def fetch_twelve_data() -> Dict:
    if not K["twelvedata"]: return {}
    log.info("Twelve Data: fetching quotes…")
    symbols = ",".join(inst["td"] for inst in INSTRUMENTS.values())
    try:
        r = requests.get(
            "https://api.twelvedata.com/quote",
            params={"symbol": symbols, "apikey": K["twelvedata"]},
            timeout=20
        )
        raw = r.json()
        result = {}
        for key, inst in INSTRUMENTS.items():
            sym = inst["td"]
            d = raw.get(sym, {})
            if d.get("status") == "error" or "close" not in d:
                continue
            cur  = safe_float(d.get("close"))
            prev = safe_float(d.get("previous_close"))
            if cur == 0: continue
            result[key] = {
                "label": inst["label"],
                "price": cur,
                "prev":  prev,
                "change_pct": pct_change(cur, prev),
                "direction": "up" if cur >= prev else "down",
                "source": "TwelveData",
            }
        log.info(f"  ✓ {len(result)} instruments from Twelve Data")
        return result
    except Exception as e:
        log.warning(f"  Twelve Data error: {e}")
        return {}

# ── 1b. Finnhub ─────────────────────────────────────────────────
def fetch_finnhub_prices(missing_keys: List[str]) -> Dict:
    if not K["finnhub"] or not missing_keys: return {}
    log.info(f"Finnhub: filling {len(missing_keys)} missing instruments…")
    result = {}
    try:
        # Forex rates (covers XAU, XAG, EUR, JPY, WTI proxies)
        r = requests.get(
            "https://finnhub.io/api/v1/forex/rates",
            params={"base": "USD", "token": K["finnhub"]}, timeout=15
        )
        rates = r.json().get("quote", {})

        forex_map = {
            "eurusd": ("EUR", False),
            "usdjpy": ("JPY", False),
        }
        for key, (fh_sym, big) in forex_map.items():
            if key not in missing_keys: continue
            v = safe_float(rates.get(fh_sym))
            if v == 0: continue
            # Convert to USD/CUR: EUR → EURUSD = 1/rate, JPY = rate
            price = (1/v) if fh_sym == "EUR" else v
            result[key] = {
                "label": INSTRUMENTS[key]["label"],
                "price": price, "prev": price,
                "change_pct": 0.0, "direction": "up",
                "source": "Finnhub",
            }

        # Individual quotes for index / ETF
        for key in missing_keys:
            if key in result: continue
            sym = INSTRUMENTS[key]["fh"]
            try:
                r2 = requests.get(
                    "https://finnhub.io/api/v1/quote",
                    params={"symbol": sym, "token": K["finnhub"]}, timeout=10
                )
                q = r2.json()
                cur  = safe_float(q.get("c"))
                prev = safe_float(q.get("pc"))
                if cur == 0: continue
                result[key] = {
                    "label": INSTRUMENTS[key]["label"],
                    "price": cur, "prev": prev,
                    "change_pct": pct_change(cur, prev),
                    "direction": "up" if cur >= prev else "down",
                    "source": "Finnhub",
                }
                time.sleep(0.3)  # respect rate limit
            except: pass
    except Exception as e:
        log.warning(f"  Finnhub price error: {e}")
    log.info(f"  ✓ {len(result)} instruments from Finnhub")
    return result

# ── 1c. Alpha Vantage (záloha — šetříme kredity) ────────────────
def fetch_alphavantage_prices(missing_keys: List[str]) -> Dict:
    if not K["alphavantage"] or not missing_keys: return {}
    log.info(f"Alpha Vantage: filling {len(missing_keys)} missing…")
    result = {}
    # AV má 25 req/den — použijeme max 4 instrumenty jako záloha
    for key in missing_keys[:4]:
        sym = INSTRUMENTS[key]["av"]
        try:
            r = requests.get(
                "https://www.alphavantage.co/query",
                params={"function": "GLOBAL_QUOTE", "symbol": sym,
                        "apikey": K["alphavantage"]}, timeout=15
            )
            q = r.json().get("Global Quote", {})
            cur  = safe_float(q.get("05. price"))
            prev = safe_float(q.get("08. previous close"))
            if cur == 0: continue
            result[key] = {
                "label": INSTRUMENTS[key]["label"],
                "price": cur, "prev": prev,
                "change_pct": pct_change(cur, prev),
                "direction": "up" if cur >= prev else "down",
                "source": "AlphaVantage",
            }
            time.sleep(0.5)
        except: pass
    log.info(f"  ✓ {len(result)} instruments from Alpha Vantage")
    return result

# ── 1d. Polygon.io (US ETF proxy) ───────────────────────────────
def fetch_polygon_prices(missing_keys: List[str]) -> Dict:
    if not K["polygon"] or not missing_keys: return {}
    log.info(f"Polygon: filling {len(missing_keys)} via ETF proxy…")
    result = {}
    for key in missing_keys:
        sym = INSTRUMENTS[key]["poly"]
        if sym.startswith("C:") or sym.startswith("I:") or "/" in sym:
            continue  # polygon free tier = US stocks/ETF only
        try:
            r = requests.get(
                f"https://api.polygon.io/v2/aggs/ticker/{sym}/prev",
                params={"apiKey": K["polygon"]}, timeout=15
            )
            results = r.json().get("results", [])
            if not results: continue
            d = results[0]
            cur  = safe_float(d.get("c"))
            prev = safe_float(d.get("o"))  # use open as approximate prev
            if cur == 0: continue
            result[key] = {
                "label": INSTRUMENTS[key]["label"] + " (ETF proxy)",
                "price": cur, "prev": prev,
                "change_pct": pct_change(cur, prev),
                "direction": "up" if cur >= prev else "down",
                "source": "Polygon",
            }
            time.sleep(0.5)
        except: pass
    log.info(f"  ✓ {len(result)} instruments from Polygon")
    return result

# ── 1e. Financial Modeling Prep ─────────────────────────────────
def fetch_fmp_prices(missing_keys: List[str]) -> Dict:
    if not K["fmp"] or not missing_keys: return {}
    log.info(f"FMP: filling {len(missing_keys)} missing…")
    syms = ",".join(INSTRUMENTS[k]["fmp"] for k in missing_keys if "/" not in INSTRUMENTS[k]["fmp"])
    if not syms: return {}
    try:
        r = requests.get(
            f"https://financialmodelingprep.com/api/v3/quote/{syms}",
            params={"apikey": K["fmp"]}, timeout=15
        )
        data = r.json()
        if not isinstance(data, list): return {}
        fmp_sym_to_key = {INSTRUMENTS[k]["fmp"]: k for k in missing_keys}
        result = {}
        for d in data:
            key = fmp_sym_to_key.get(d.get("symbol", ""))
            if not key: continue
            cur  = safe_float(d.get("price"))
            prev = safe_float(d.get("previousClose"))
            if cur == 0: continue
            result[key] = {
                "label": INSTRUMENTS[key]["label"],
                "price": cur, "prev": prev,
                "change_pct": pct_change(cur, prev),
                "direction": "up" if cur >= prev else "down",
                "source": "FMP",
            }
        log.info(f"  ✓ {len(result)} instruments from FMP")
        return result
    except Exception as e:
        log.warning(f"  FMP error: {e}")
        return {}

# ── Agregátor cen (priorita + fallback) ─────────────────────────
def fetch_all_prices() -> Dict:
    prices = fetch_twelve_data()
    missing = [k for k in INSTRUMENTS if k not in prices]
    if missing:
        prices.update(fetch_finnhub_prices(missing))
        missing = [k for k in INSTRUMENTS if k not in prices]
    if missing:
        prices.update(fetch_alphavantage_prices(missing))
        missing = [k for k in INSTRUMENTS if k not in prices]
    if missing:
        prices.update(fetch_polygon_prices(missing))
        missing = [k for k in INSTRUMENTS if k not in prices]
    if missing:
        prices.update(fetch_fmp_prices(missing))
        missing = [k for k in INSTRUMENTS if k not in prices]
    if missing:
        log.warning(f"  ⚠ No data for: {missing}")
    return prices

# ═══════════════════════════════════════════════════════════════
#  2. TECHNICKÉ INDIKÁTORY (Alpha Vantage — šetříme kredity)
# ═══════════════════════════════════════════════════════════════
def fetch_technical_indicators() -> Dict:
    if not K["alphavantage"]: return {}
    log.info("Alpha Vantage: technical indicators (RSI, MACD)…")
    indicators = {}
    # 2 požadavky: RSI pro SPY (S&P proxy) a GLD (Gold proxy)
    for sym, label in [("SPY", "S&P 500"), ("GLD", "Gold")]:
        try:
            r = requests.get(
                "https://www.alphavantage.co/query",
                params={"function": "RSI", "symbol": sym, "interval": "daily",
                        "time_period": 14, "series_type": "close",
                        "apikey": K["alphavantage"]}, timeout=15
            )
            data = r.json().get("Technical Analysis: RSI", {})
            if data:
                latest_date = sorted(data.keys(), reverse=True)[0]
                rsi = safe_float(data[latest_date].get("RSI"))
                indicators[f"rsi_{sym.lower()}"] = {
                    "label": f"RSI(14) {label}",
                    "value": round(rsi, 1),
                    "note": "overbought>70 | neutral 45-55 | oversold<30",
                }
            time.sleep(0.5)
        except Exception as e:
            log.warning(f"  RSI {sym}: {e}")
    log.info(f"  ✓ {len(indicators)} indicators")
    return indicators

# ═══════════════════════════════════════════════════════════════
#  3. FRED — MAKROEKONOMICKÁ DATA
# ═══════════════════════════════════════════════════════════════
FRED_SERIES = {
    "cpi":          ("CPIAUCSL",  "CPI YoY Inflation (%)"),
    "real_yield":   ("DFII10",    "10Y TIPS Real Yield (%)"),
    "fed_funds":    ("DFF",       "Fed Funds Rate (%)"),
    "m2":           ("M2SL",      "M2 Money Supply ($B)"),
    "yield_curve":  ("T10Y2Y",    "10Y-2Y Yield Spread (%)"),
    "unemployment": ("UNRATE",    "Unemployment Rate (%)"),
    "pce":          ("PCEPI",     "PCE Inflation (%)"),
}

def fetch_fred_data() -> Dict:
    if not K["fred"]: return {}
    log.info("FRED: fetching macro series…")
    macro = {}
    try:
        from fredapi import Fred
        fred = Fred(api_key=K["fred"])
        for key, (series_id, label) in FRED_SERIES.items():
            try:
                s = fred.get_series(series_id, observation_start="2024-01-01")
                if s.empty: continue
                val = round(float(s.iloc[-1]), 2)
                prev = round(float(s.iloc[-2]), 2) if len(s) > 1 else val
                macro[key] = {
                    "label": label,
                    "value": val,
                    "prev": prev,
                    "change": round(val - prev, 2),
                    "date": str(s.index[-1].date()),
                }
            except Exception as e:
                log.warning(f"  FRED {series_id}: {e}")
    except ImportError:
        log.warning("  fredapi not installed — skipping FRED")
    log.info(f"  ✓ {len(macro)} FRED series")
    return macro

# ═══════════════════════════════════════════════════════════════
#  4. EKONOMICKÝ KALENDÁŘ — FMP
# ═══════════════════════════════════════════════════════════════
def fetch_economic_calendar() -> List[Dict]:
    today = date.today().isoformat()
    events = []

    # FMP calendar
    if K["fmp"]:
        try:
            r = requests.get(
                "https://financialmodelingprep.com/api/v3/economic_calendar",
                params={"from": today, "to": today, "apikey": K["fmp"]}, timeout=15
            )
            for e in r.json():
                imp = e.get("impact", "").lower()
                if imp in ("high", "medium"):
                    events.append({
                        "time":   e.get("date", "")[-8:-3],
                        "event":  e.get("event", ""),
                        "impact": imp.upper(),
                        "actual": e.get("actual"),
                        "forecast": e.get("estimate"),
                        "previous": e.get("previous"),
                        "country": e.get("country", ""),
                    })
        except Exception as e:
            log.warning(f"  FMP calendar: {e}")

    # Finnhub calendar fallback
    if not events and K["finnhub"]:
        try:
            r = requests.get(
                "https://finnhub.io/api/v1/calendar/economic",
                params={"token": K["finnhub"]}, timeout=15
            )
            for e in r.json().get("economicCalendar", []):
                if e.get("impact", 0) >= 2 and e.get("atTime", "")[:10] == today:
                    events.append({
                        "time":   e.get("atTime", "")[-8:-3],
                        "event":  e.get("event", ""),
                        "impact": "HIGH" if e.get("impact", 0) >= 3 else "MEDIUM",
                        "actual": e.get("actual"),
                        "forecast": e.get("estimate"),
                        "previous": e.get("prev"),
                        "country": e.get("country", ""),
                    })
        except Exception as e:
            log.warning(f"  Finnhub calendar: {e}")

    log.info(f"  ✓ {len(events)} economic events today")
    return events[:15]

# ═══════════════════════════════════════════════════════════════
#  5. CNN FEAR & GREED INDEX (bez API klíče)
# ═══════════════════════════════════════════════════════════════
def fetch_fear_greed() -> Optional[Dict]:
    try:
        r = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10
        )
        fg = r.json()["fear_and_greed"]
        score = round(float(fg["score"]), 1)
        rating = fg["rating"].title()
        prev_close = round(float(fg.get("previous_close", score)), 1)
        log.info(f"  ✓ Fear & Greed: {score} ({rating})")
        return {"score": score, "rating": rating, "previous": prev_close}
    except Exception as e:
        log.warning(f"  Fear & Greed: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
#  6. ZPRÁVY + SENTIMENT
# ═══════════════════════════════════════════════════════════════

# ── 6a. Finnhub News + Sentiment ────────────────────────────────
def fetch_finnhub_news() -> List[Dict]:
    if not K["finnhub"]: return []
    log.info("Finnhub: news + sentiment…")
    items = []
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/news",
            params={"category": "general", "token": K["finnhub"]}, timeout=15
        )
        for a in r.json()[:15]:
            items.append({
                "title":    a.get("headline", ""),
                "summary":  re.sub(r"<[^>]+>", "", a.get("summary", ""))[:200],
                "source":   a.get("source", "Finnhub"),
                "sentiment": None,
            })
    except Exception as e:
        log.warning(f"  Finnhub news: {e}")

    # Sentiment for key tickers
    for sym in ["AAPL", "SPY", "GLD"]:
        try:
            r2 = requests.get(
                "https://finnhub.io/api/v1/news-sentiment",
                params={"symbol": sym, "token": K["finnhub"]}, timeout=10
            )
            d = r2.json()
            score = safe_float(d.get("sentiment", {}).get("bullishPercent", 0.5))
            if d.get("buzz"):
                items.insert(0, {
                    "title": f"{sym} News Sentiment: {round(score*100)}% Bullish "
                             f"(buzz score {d['buzz'].get('buzz', 0):.2f})",
                    "summary": "",
                    "source": "Finnhub Sentiment",
                    "sentiment": round(score * 2 - 1, 2),  # normalize to -1..+1
                })
            time.sleep(0.3)
        except: pass

    log.info(f"  ✓ {len(items)} Finnhub items")
    return items

# ── 6b. NewsAPI ─────────────────────────────────────────────────
def fetch_newsapi() -> List[Dict]:
    if not K["newsapi"]: return []
    log.info("NewsAPI: business headlines…")
    items = []
    try:
        r = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={"category": "business", "language": "en",
                    "pageSize": 15, "apiKey": K["newsapi"]}, timeout=15
        )
        for a in r.json().get("articles", []):
            items.append({
                "title":   a.get("title", ""),
                "summary": (a.get("description") or "")[:200],
                "source":  a.get("source", {}).get("name", "NewsAPI"),
                "sentiment": None,
            })
    except Exception as e:
        log.warning(f"  NewsAPI: {e}")

    # Everything query for key topics
    try:
        r2 = requests.get(
            "https://newsapi.org/v2/everything",
            params={"q": 'gold OR "crude oil" OR "S&P 500" OR "Federal Reserve" OR inflation',
                    "language": "en", "sortBy": "publishedAt",
                    "pageSize": 10, "apiKey": K["newsapi"]}, timeout=15
        )
        for a in r2.json().get("articles", []):
            items.append({
                "title":   a.get("title", ""),
                "summary": (a.get("description") or "")[:200],
                "source":  a.get("source", {}).get("name", "NewsAPI"),
                "sentiment": None,
            })
    except: pass

    log.info(f"  ✓ {len(items)} NewsAPI items")
    return items

# ── 6c. Alpha Vantage News Sentiment ────────────────────────────
def fetch_av_news() -> List[Dict]:
    if not K["alphavantage"]: return []
    log.info("Alpha Vantage: news sentiment…")
    items = []
    try:
        r = requests.get(
            "https://www.alphavantage.co/query",
            params={"function": "NEWS_SENTIMENT",
                    "tickers": "SPY,GLD,USO,UUP,TLT",
                    "limit": 15,
                    "apikey": K["alphavantage"]}, timeout=15
        )
        for a in r.json().get("feed", []):
            # Overall sentiment score
            overall = safe_float(a.get("overall_sentiment_score"))
            items.append({
                "title":   a.get("title", ""),
                "summary": re.sub(r"<[^>]+>", "", a.get("summary", ""))[:200],
                "source":  a.get("source", "Alpha Vantage"),
                "sentiment": round(overall, 2) if overall else None,
                "label":   a.get("overall_sentiment_label", ""),
            })
    except Exception as e:
        log.warning(f"  AV news: {e}")
    log.info(f"  ✓ {len(items)} AV news items")
    return items

# ── 6d. Benzinga RSS (bez API klíče) ────────────────────────────
def fetch_benzinga_rss() -> List[Dict]:
    log.info("Benzinga: RSS feed…")
    items = []
    try:
        import feedparser
        feed = feedparser.parse("https://www.benzinga.com/feed")
        for e in feed.entries[:8]:
            title = e.get("title", "").strip()
            summary = re.sub(r"<[^>]+>", "", e.get("summary", ""))[:200].strip()
            if title:
                items.append({
                    "title": title,
                    "summary": summary,
                    "source": "Benzinga",
                    "sentiment": None,
                })
    except Exception as e:
        log.warning(f"  Benzinga RSS: {e}")
    return items

# ── 6e. RSS záloha ───────────────────────────────────────────────
RSS_BACKUP = [
    ("https://feeds.bbci.co.uk/news/business/rss.xml", "BBC Business"),
    ("https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best", "Reuters"),
    ("https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines", "MarketWatch"),
    ("https://www.ft.com/?format=rss", "Financial Times"),
]

def fetch_rss_backup() -> List[Dict]:
    import feedparser
    items = []
    for url, source in RSS_BACKUP:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:4]:
                t = e.get("title", "").strip()
                s = re.sub(r"<[^>]+>", "", e.get("summary", ""))[:180].strip()
                if t:
                    items.append({"title": t, "summary": s, "source": source, "sentiment": None})
        except: pass
    return items

# ── Agregátor zpráv ──────────────────────────────────────────────
def fetch_all_news() -> List[Dict]:
    all_items: List[Dict] = []
    seen_titles = set()

    sources = [
        fetch_finnhub_news,
        fetch_newsapi,
        fetch_av_news,
        fetch_benzinga_rss,
        fetch_rss_backup,
    ]
    for fn in sources:
        try:
            for item in fn():
                title_norm = item["title"].lower()[:80]
                if title_norm not in seen_titles and item["title"]:
                    seen_titles.add(title_norm)
                    all_items.append(item)
        except: pass

    # Sort: items with sentiment score first
    all_items.sort(key=lambda x: (x["sentiment"] is not None), reverse=True)
    log.info(f"  📰 Total unique headlines: {len(all_items)}")
    return all_items[:30]

# ═══════════════════════════════════════════════════════════════
#  7. SESTAVENÍ PROMPTU PRO GPT-4o
# ═══════════════════════════════════════════════════════════════
def build_prompt(prices, technicals, macro, calendar, fear_greed, news, now_cet) -> str:
    day   = now_cet.strftime("%A")
    dstr  = now_cet.strftime("%d %B %Y")
    hour  = now_cet.hour
    sess  = "morning" if hour < 11 else ("midday" if hour < 14 else "afternoon")

    # Prices block
    price_lines = []
    for k, d in prices.items():
        arrow = "▲" if d["direction"] == "up" else "▼"
        big   = INSTRUMENTS.get(k, {}).get("is_big", False)
        p_str = fmt_price(d["price"], big)
        price_lines.append(
            f"  {d['label']:22s}: {p_str:>12}  {arrow}{abs(d['change_pct']):.2f}%  [src:{d.get('source','?')}]"
        )

    # Technical indicators
    tech_lines = [f"  {v['label']}: {v['value']} ({v['note']})"
                  for v in technicals.values()]

    # FRED macro
    macro_lines = [
        f"  {v['label']}: {v['value']}  (prev: {v['prev']}, Δ{v['change']:+.2f}, as of {v['date']})"
        for v in macro.values()
    ]

    # Fear & Greed
    fg_line = ""
    if fear_greed:
        fg_line = (f"  CNN Fear & Greed Index: {fear_greed['score']}/100 "
                   f"— {fear_greed['rating']} (prev close: {fear_greed['previous']})")

    # Economic calendar
    cal_lines = []
    for e in calendar:
        imp_icon = "🔴" if e["impact"] == "HIGH" else "🟡"
        actual = f" actual={e['actual']}" if e.get("actual") is not None else ""
        fcst   = f" forecast={e['forecast']}" if e.get("forecast") is not None else ""
        prev   = f" prev={e['previous']}" if e.get("previous") is not None else ""
        cal_lines.append(
            f"  {imp_icon} {e.get('time','?')} CET — {e['event']} [{e.get('country','')}]{actual}{fcst}{prev}"
        )

    # News + sentiment
    news_lines = []
    for n in news[:22]:
        sent_tag = ""
        if n.get("sentiment") is not None:
            s = n["sentiment"]
            sent_tag = f" [{'BULLISH' if s>0.15 else 'BEARISH' if s<-0.15 else 'NEUTRAL'} {s:+.2f}]"
        summary = f": {n['summary'][:120]}" if n.get("summary") else ""
        news_lines.append(f"  [{n.get('source','?')}]{sent_tag} {n['title']}{summary}")

    sections = [
        f"TODAY: {day}, {dstr} — {sess} update (CEST)\n",
        "━━ LIVE MARKET DATA (use EXACT prices below) ━━",
        *price_lines,
        "",
        "━━ TECHNICAL INDICATORS ━━",
        *(tech_lines or ["  (not available — no AV key)"]),
        "",
        "━━ MACRO DATA (FRED) ━━",
        *(macro_lines or ["  (not available — no FRED key)"]),
        "",
        "━━ FEAR & GREED INDEX ━━",
        fg_line or "  (not available)",
        "",
        "━━ TODAY'S ECONOMIC CALENDAR (high/medium impact only) ━━",
        *(cal_lines or ["  No major events scheduled today"]),
        "",
        "━━ NEWS & SENTIMENT FEED ━━",
        *news_lines,
    ]
    context = "\n".join(sections)

    return f"""{context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK: Generate a CFD Intraday Brief JSON.
Use ALL the data above. Be specific — mention actual prices, RSI levels, macro numbers, and scheduled events.
Return ONLY valid JSON (no markdown fences). Exact structure:

{{
  "date": "{day} {dstr}",
  "macro": {{
    "badge": "emoji + concise regime label (max 12 words, reflect ACTUAL macro situation above)",
    "intro": "3–4 sentences. <strong> for key phrases. Reference actual numbers. Mention key calendar events."
  }},
  "snapshot": [
    {{ "name": "Gold (XAU/USD)", "value": "EXACT price from data", "change": "±X.XX% today", "dir": "up|down", "note": "key level, RSI context, or macro link" }},
    {{ "name": "WTI Crude Oil",  "value": "EXACT price", "change": "±X.XX% today", "dir": "up|down", "note": "key context" }},
    {{ "name": "S&P 500",        "value": "EXACT level", "change": "±X.XX% today", "dir": "up|down", "note": "RSI context" }},
    {{ "name": "EUR/USD",        "value": "EXACT rate",  "change": "±X.XXXX today","dir": "up|down", "note": "key level" }},
    {{ "name": "VIX",            "value": "EXACT level", "change": "±X.XX today",  "dir": "up|down", "note": "risk-on|risk-off context" }}
  ],
  "setups": [
    {{
      "rank": 1, "dir": "LONG|SHORT",
      "type": "Index|FX Pair|Gold|Commodity|Bond|ETF",
      "symbol": "TICKER / NAME",
      "name": "Full descriptive setup name",
      "conviction": "High|Moderate–High|Moderate",
      "conviction_pct": 78,
      "rationale": "3–4 sentences. Quote specific prices, RSI, FRED numbers, calendar events.",
      "entry": "specific price or zone", "entry_note": "timing or method",
      "target": "specific price",       "target_note": "resistance/level reason",
      "stop":   "specific price",       "stop_note":   "support/level reason",
      "metrics": [
        {{"label": "Specific indicator", "text": "what level triggers action and why"}},
        {{"label": "Specific indicator", "text": "details"}},
        {{"label": "Economic event", "text": "how today's calendar event affects this position"}},
        {{"label": "Specific indicator", "text": "details"}}
      ],
      "concerns": [
        {{"label": "Primary risk", "text": "specific description with price levels"}},
        {{"label": "Secondary risk", "text": "specific description"}}
      ],
      "hedge": "Specific hedge instruction with exact price levels."
    }},
    {{ /* setup 2 — DIFFERENT asset class */ }},
    {{ /* setup 3 — DIFFERENT asset class */ }}
  ],
  "contrarian": {{
    "symbol": "asset name", "dir": "SHORT|LONG",
    "entry": "price", "stop": "price", "target": "price", "rr": "1:X.X",
    "body": "2–3 sentences with exact prices, referencing FRED or Fear & Greed data.",
    "warning": "2 sentences on binary risk. <strong> for critical parts."
  }},
  "avoid": [
    {{"symbol": "emoji + name", "reason": "specific today-only reason referencing actual data above"}},
    {{"symbol": "emoji + name", "reason": "specific reason"}},
    {{"symbol": "emoji + name", "reason": "specific reason"}},
    {{"symbol": "emoji + name", "reason": "specific reason"}},
    {{"symbol": "emoji + name", "reason": "specific reason"}},
    {{"symbol": "emoji + name", "reason": "specific reason"}}
  ]
}}

Rules:
- 3 setups = 3 DIFFERENT asset classes
- conviction_pct 55–90 only
- ALL entry/target/stop must be derived from live prices above
- Mention Fear & Greed score in at least one rationale or concern
- If RSI > 70: flag as overbought risk. If RSI < 30: flag as potential reversal.
- Reference today's calendar events in the setup metrics or intro
- Avoid list must explain WHY specifically TODAY based on the data
"""


# ═══════════════════════════════════════════════════════════════
#  8. OPENAI GPT-4o CALL
# ═══════════════════════════════════════════════════════════════
SYSTEM = (
    "You are a senior CFD trading analyst at Goldman Sachs. "
    "Your briefs are specific, data-driven, and actionable. "
    "Never use generic language. Always reference exact prices, levels, and indicators. "
    "Return ONLY valid JSON — no markdown, no explanation."
)

def call_openai(prompt: str) -> Dict:
    from openai import OpenAI
    client = OpenAI(api_key=K["openai"])
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.2,
        max_tokens=4000,
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


# ═══════════════════════════════════════════════════════════════
#  9. MAIN
# ═══════════════════════════════════════════════════════════════
def main():

    # ── PRIMARY: IG LIVE API ──────────────────────────────────────
    ig_prices = {}
    try:
        ig_prices = fetch_ig_prices()
        if ig_prices:
            logging.info(f"IG LIVE API: {len(ig_prices)} prices loaded as primary source")
    except Exception as e:
        logging.warning(f"IG fetch error: {e}")

    def get_price(symbol, fallback=None):
        """Get price preferring IG LIVE, fallback to public API value."""
        if symbol in ig_prices:
            return ig_prices[symbol]
        return fallback

    now = datetime.now(CET)
    log.info(f"\n{'━'*55}")
    log.info(f"  CFD Brief Generator — {now.strftime('%Y-%m-%d %H:%M %Z')}")
    log.info(f"{'━'*55}")

    # Validate required key
    if not K["openai"]:
        log.error("OPENAI_API_KEY is not set. Aborting.")
        sys.exit(1)

    # Report available sources
    available = [name for name, key in K.items() if key and name != "openai"]
    log.info(f"Active sources: {', '.join(available) or 'none — OpenAI only'}")

    log.info("\n[1/6] Fetching market prices…")
    prices = fetch_all_prices()
    log.info(f"  → {len(prices)}/{len(INSTRUMENTS)} instruments loaded")

    log.info("\n[2/6] Fetching technical indicators…")
    technicals = fetch_technical_indicators()

    log.info("\n[3/6] Fetching FRED macro data…")
    macro = fetch_fred_data()

    log.info("\n[4/6] Fetching economic calendar + Fear & Greed…")
    calendar   = fetch_economic_calendar()
    fear_greed = fetch_fear_greed()

    log.info("\n[5/6] Fetching news & sentiment…")
    news = fetch_all_news()

    log.info("\n[6/6] Generating AI brief (GPT-4o)…")
    prompt = build_prompt(prices, technicals, macro, calendar, fear_greed, news, now)
    brief  = call_openai(prompt)
    log.info("  ✓ Brief generated")
    log.info(f"  Setups: {[s.get('symbol','?') for s in brief.get('setups', [])]}")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)

    log.info(f"\n✅  data.json saved — {brief.get('date', '')}")
    log.info(f"{'━'*55}\n")


if __name__ == "__main__":
    main()
