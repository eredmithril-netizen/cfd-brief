# CFD Intraday Brief — Multi-Source Auto-Generator v2

Plně automatický systém generující CFD Intraday Brief **3× denně** z reálných dat.

## Architektura

```
Cenová data  ──► Twelve Data → Finnhub → AlphaVantage → Polygon → FMP  (fallback chain)
Makrodata    ──► FRED API (CPI, TIPS, M2, Fed Funds, yield curve)
Zprávy       ──► Finnhub + NewsAPI + Alpha Vantage News + Benzinga RSS + RSS záloha
Indikátory   ──► Alpha Vantage (RSI 14 pro S&P a Gold)
Doplňky      ──► CNN Fear & Greed + FMP Economic Calendar
                         │
                    GPT-4o analýza
                         │
                      data.json  ◄──  index.html čte při každém načtení stránky
```

## API klíče — kde získat (vše ZDARMA)

| Klíč (GitHub Secret) | Kde získat | Free limit |
|---|---|---|
| `OPENAI_API_KEY` | platform.openai.com | ~$5 = 2+ měsíce |
| `TWELVEDATA_API_KEY` | twelvedata.com | **800 req/den** |
| `FINNHUB_API_KEY` | finnhub.io | 60 req/min |
| `ALPHAVANTAGE_API_KEY` | alphavantage.co | 25 req/den |
| `POLYGON_API_KEY` | polygon.io | 5 req/min |
| `FMP_API_KEY` | financialmodelingprep.com | 250 req/den |
| `FRED_API_KEY` | fred.stlouisfed.org/docs/api | Neomezený |
| `NEWSAPI_KEY` | newsapi.org | 100 req/den |

> **Minimum pro spuštění:** `OPENAI_API_KEY` + `TWELVEDATA_API_KEY`.
> Ostatní klíče přidávají další vrstvu dat a zálohu — skript funguje i bez nich.

## Rychlé nastavení (10 minut)

1. **GitHub repozitář** — nahrajte všechny soubory do nového repo
2. **Secrets** — Settings → Secrets → Actions → přidejte každý klíč
3. **GitHub Pages** — Settings → Pages → Branch: main → root
4. **Hotovo** — web běží na `https://vasejmeno.github.io/nazev-repo/`

## Soubory

```
/
├── index.html              ← HTML šablona (nikdy neměnit)
├── data.json               ← Automaticky přepisováno 3× denně
├── generate_brief.py       ← Python skript
├── requirements.txt        ← Závislosti
└── .github/workflows/
    └── update-brief.yml    ← GitHub Actions plán
```

## Měsíční náklady

| Zdroj | Cena |
|---|---|
| GitHub Actions + Pages | Zdarma |
| Twelve Data, Finnhub, AV, Polygon, FMP, FRED, NewsAPI | Zdarma |
| OpenAI GPT-4o (66 běhů × ~4500 tokenů) | ~$1–2/měsíc |

## Ruční aktualizace

GitHub → **Actions** → **Update CFD Intraday Brief** → **Run workflow**
