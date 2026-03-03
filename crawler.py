"""
Rohstoffpreise Crawler fuer die Stahlherstellung.

Datenquellen:
  - Trading Economics (Web-Scraping): Nickel, Eisenerz, Kokskohle, Kobalt,
    Mangan, Silizium, HRC Stahl
  - Yahoo Finance (yfinance API): Kupfer, Aluminium, Zink, Blei
  - Waehrungskurse: USD/EUR, CNY/USD, JPY/USD via Yahoo Finance

Ausgabe:
  - data/prices_history.csv  (wird taeglich erganzt)
  - reports/YYYY-MM-DD.md    (tagesaktuelle Uebersicht)
  - docs/index.html          (GitHub Pages Webseite)

Aufruf:
  python crawler.py
"""

from datetime import date, datetime
from pathlib import Path
import csv
import re
import time

try:
    import requests
    from bs4 import BeautifulSoup
    import yfinance as yf
except ImportError:
    raise SystemExit(
        "FEHLER: Abhaengigkeiten fehlen. Bitte ausfuehren:\n"
        "  pip install requests beautifulsoup4 yfinance"
    )

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"
DOCS_DIR = BASE_DIR / "docs"
HISTORY_CSV = DATA_DIR / "prices_history.csv"

DATA_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Regex fuer Meta-Description: "... to/at VALUE UNIT on DATE ..."
PRICE_RE = re.compile(
    r"(?:to|at)\s+([\d,\.]+)\s+([A-Z]{3}/[A-Za-z]+)", re.IGNORECASE
)

# -------------------------------------------------------- Quell-Definitionen ---

# Trading Economics: (slug, anzeigename, kategorie, notiz)
TRADING_ECONOMICS = [
    ("nickel",       "Nickel",       "Basismetalle",  "LME"),
    ("iron-ore",     "Eisenerz",     "Rohstoffe",     "62% Fe, CFR China"),
    ("coking-coal",  "Kokskohle",    "Energietraeger","Premium Hard"),
    ("cobalt",       "Kobalt",       "Basismetalle",  ""),
    ("manganese",    "Mangan",       "Legierungen",   "Erz, CNY/mtu"),
    ("silicon",      "Silizium",     "Legierungen",   "CNY/T"),
    ("steel",        "Stahl HRC",    "Stahlpreise",   "Hot-Rolled Coil, CNY/T"),
]

# Yahoo Finance: (symbol, anzeigename, kategorie, einheit, umrechnung_auf_usd_mt)
# umrechnung_auf_usd_mt: Faktor, um Rohwert in USD/MT zu bringen
# None = keine Umrechnung (Preis bereits in USD/MT)
YAHOO_FINANCE = [
    ("HG=F",   "Kupfer",    "Basismetalle",  "USD/lb",  2204.62),   # lb -> MT
    ("ALI=F",  "Aluminium", "Basismetalle",  "USD/MT",  1.0),
    ("ZNC=F",  "Zink",      "Basismetalle",  "USD/MT",  1.0),
    ("LE=F",   "Blei",      "Basismetalle",  "USX/lb",  22.0462),   # Cent/lb -> USD/MT
]

# Waehrungspaare fuer spaetere Umrechnung
FX_PAIRS = {
    "EURUSD=X": "EUR/USD",
    "CNYUSD=X": "CNY/USD",
    "JPYUSD=X": "JPY/USD",
}


# -------------------------------------------------------------- Datenabruf ---

def fetch_trading_economics(slug: str) -> tuple[float | None, str]:
    """Liest Preis und Einheit von Trading Economics via Meta-Description."""
    url = f"https://tradingeconomics.com/commodity/{slug}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        desc = soup.find("meta", {"name": "description"})
        content = desc.get("content", "") if desc else ""
        m = PRICE_RE.search(content)
        if m:
            price = float(m.group(1).replace(",", ""))
            unit = m.group(2)
            return price, unit
    except Exception:
        pass
    return None, ""


def fetch_yahoo(symbol: str) -> float | None:
    """Liest den letzten Schlusskurs von Yahoo Finance."""
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="3d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def fetch_fx_rates() -> dict[str, float]:
    """Liest Waehrungskurse (alle gegen USD)."""
    rates = {}
    for symbol, name in FX_PAIRS.items():
        val = fetch_yahoo(symbol)
        if val:
            rates[name] = round(val, 6)
        time.sleep(0.3)
    return rates


# -------------------------------------------------------------- Hauptlogik ---

def crawl() -> list[dict]:
    """Crawlt alle Quellen und gibt eine Liste von Preiseintraegen zurueck."""
    today = date.today().isoformat()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = []

    # Waehrungskurse zuerst (fuer spaetere Ausgabe)
    print("Lade Waehrungskurse...")
    fx = fetch_fx_rates()
    eur_usd = fx.get("EUR/USD", None)
    print(f"  EUR/USD: {eur_usd}  CNY/USD: {fx.get('CNY/USD')}  JPY/USD: {fx.get('JPY/USD')}")
    print()

    # Trading Economics
    print("Lade Trading Economics...")
    for slug, name, kategorie, notiz in TRADING_ECONOMICS:
        price, unit = fetch_trading_economics(slug)
        status = "OK" if price is not None else "FEHLER"

        # EUR-Aequivalent berechnen falls USD-Preis und Kurs vorhanden
        eur_price = None
        if price and eur_usd and unit.startswith("USD"):
            eur_price = round(price / eur_usd, 2)

        print(
            f"  {'OK ' if status == 'OK' else 'ERR'} {name:20s}: "
            f"{f'{price:,.2f}' if price else '—':>12s}  {unit or '—'}"
        )

        results.append({
            "datum": today,
            "zeitstempel": now,
            "rohstoff": name,
            "kategorie": kategorie,
            "preis": price,
            "einheit": unit,
            "preis_eur": eur_price,
            "quelle": "Trading Economics",
            "symbol": slug,
            "notiz": notiz,
            "status": status,
        })
        time.sleep(1.0)  # Rate-Limiting

    print()
    print("Lade Yahoo Finance...")

    # Yahoo Finance
    for symbol, name, kategorie, einheit, faktor in YAHOO_FINANCE:
        raw = fetch_yahoo(symbol)
        price = round(raw * faktor, 2) if raw is not None else None
        unit = "USD/MT" if faktor != 1.0 else einheit
        status = "OK" if price is not None else "FEHLER"

        eur_price = round(price / eur_usd, 2) if price and eur_usd else None

        print(
            f"  {'OK ' if status == 'OK' else 'ERR'} {name:20s}: "
            f"{f'{price:,.2f}' if price else '—':>12s}  {unit}"
        )

        results.append({
            "datum": today,
            "zeitstempel": now,
            "rohstoff": name,
            "kategorie": kategorie,
            "preis": price,
            "einheit": unit,
            "preis_eur": eur_price,
            "quelle": "Yahoo Finance",
            "symbol": symbol,
            "notiz": f"Originalwert: {f'{raw:.4f}' if raw else '—'} {einheit}",
            "status": status,
        })
        time.sleep(0.5)

    # Waehrungskurse als eigene Eintraege
    for name, val in fx.items():
        results.append({
            "datum": today,
            "zeitstempel": now,
            "rohstoff": f"Kurs {name}",
            "kategorie": "Waehrung",
            "preis": val,
            "einheit": name,
            "preis_eur": None,
            "quelle": "Yahoo Finance",
            "symbol": [k for k, v in FX_PAIRS.items() if v == name][0],
            "notiz": "",
            "status": "OK",
        })

    return results


# ----------------------------------------------------------------- Exports ---

CSV_FIELDS = [
    "datum", "zeitstempel", "rohstoff", "kategorie",
    "preis", "einheit", "preis_eur", "quelle", "symbol", "notiz", "status",
]


def save_csv(results: list[dict]):
    """Haengt Ergebnisse an die History-CSV an (erstellt Header wenn noetig)."""
    write_header = not HISTORY_CSV.exists() or HISTORY_CSV.stat().st_size == 0

    with open(HISTORY_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, delimiter=";")
        if write_header:
            writer.writeheader()
        writer.writerows(results)


def save_markdown(results: list[dict], today: str, fx: dict[str, float]):
    """Erstellt einen tagesaktuellen Markdown-Report."""
    md_path = REPORT_DIR / f"{today}.md"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Gruppierung nach Kategorie
    by_cat: dict[str, list[dict]] = {}
    for r in results:
        if r["kategorie"] == "Waehrung":
            continue
        by_cat.setdefault(r["kategorie"], []).append(r)

    ok_count = sum(1 for r in results if r["status"] == "OK" and r["kategorie"] != "Waehrung")
    err_count = sum(1 for r in results if r["status"] == "FEHLER" and r["kategorie"] != "Waehrung")

    eur_usd = fx.get("EUR/USD", "—")
    cny_usd = fx.get("CNY/USD", "—")

    lines = [
        f"# Rohstoffpreise Stahl — {today}",
        "",
        f"*Abgerufen: {ts}*",
        "",
        "## Waehrungskurse",
        "",
        f"| Kurs | Wert |",
        f"|------|-----:|",
        f"| EUR/USD | {eur_usd} |",
        f"| CNY/USD | {cny_usd} |",
        f"| JPY/USD | {fx.get('JPY/USD', '—')} |",
        "",
        f"## Preise ({ok_count} OK, {err_count} Fehler)",
        "",
    ]

    cat_order = ["Basismetalle", "Rohstoffe", "Energietraeger", "Legierungen", "Stahlpreise"]
    all_cats = cat_order + [c for c in by_cat if c not in cat_order]

    for cat in all_cats:
        rows = by_cat.get(cat)
        if not rows:
            continue

        lines += [
            f"### {cat}",
            "",
            "| Rohstoff | Preis | Einheit | EUR-Aequiv. | Quelle | Notiz |",
            "|----------|------:|---------|------------:|--------|-------|",
        ]

        for r in rows:
            preis = f"{r['preis']:,.2f}" if r["preis"] is not None else "—"
            eur = f"{r['preis_eur']:,.2f}" if r["preis_eur"] else "—"
            status_icon = "" if r["status"] == "OK" else " ⚠️"
            lines.append(
                f"| {r['rohstoff']}{status_icon} "
                f"| {preis} "
                f"| {r['einheit'] or '—'} "
                f"| {eur} "
                f"| {r['quelle']} "
                f"| {r['notiz']} |"
            )

        lines.append("")

    lines += [
        "---",
        "*Quellen: Trading Economics, Yahoo Finance*  ",
        "*Alle Angaben ohne Gewaehr. Preise koennen verzögert sein.*",
        "",
    ]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def save_html(_results=None, _today=None, _fx=None):
    """Erstellt docs/index.html als dynamische Seite, die Daten live von GitHub laedt.

    Die Seite benoetigt keine eingebetteten Preisdaten — JavaScript laedt beim Oeffnen
    die aktuelle prices_history.csv von raw.githubusercontent.com und rendert die Tabellen.
    Funktioniert sowohl als GitHub Pages als auch lokal (Internetverbindung erforderlich).
    """
    html_path = DOCS_DIR / "index.html"

    GITHUB_RAW_CSV = (
        "https://raw.githubusercontent.com/Pjoern/raw-material-prices-crawler"
        "/main/data/prices_history.csv"
    )

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rohstoffpreise Stahl</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f6fa;
      color: #222;
      padding: 24px 16px;
      max-width: 1100px;
      margin: 0 auto;
    }}
    header {{ margin-bottom: 24px; }}
    h1 {{ font-size: 1.6rem; font-weight: 700; color: #1a2a3a; }}
    .meta {{ margin-top: 6px; font-size: 0.85rem; color: #666; }}
    .fx-bar {{
      display: flex;
      gap: 20px;
      flex-wrap: wrap;
      background: #fff;
      border: 1px solid #e0e4ea;
      border-radius: 8px;
      padding: 12px 18px;
      margin-bottom: 28px;
      font-size: 0.9rem;
    }}
    .fx-bar span {{ color: #888; margin-right: 4px; }}
    .fx-bar strong {{ color: #1a2a3a; }}
    h2 {{
      font-size: 1rem;
      font-weight: 600;
      color: #1a2a3a;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin: 28px 0 10px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 1px 4px rgba(0,0,0,.06);
      font-size: 0.9rem;
    }}
    thead tr {{ background: #1a2a3a; color: #fff; }}
    thead th {{
      padding: 10px 14px;
      text-align: left;
      font-weight: 600;
      font-size: 0.8rem;
      letter-spacing: 0.04em;
    }}
    tbody tr:nth-child(even) {{ background: #f9fafb; }}
    tbody tr:hover {{ background: #eef3fa; }}
    td {{ padding: 9px 14px; border-bottom: 1px solid #eee; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 500; }}
    .unit {{ color: #666; font-size: 0.82rem; }}
    .src  {{ color: #888; font-size: 0.82rem; }}
    .note {{ color: #999; font-size: 0.78rem; }}
    .na   {{ color: #bbb; }}
    .warn {{ color: #e07b00; }}
    #loading {{
      text-align: center;
      padding: 60px 20px;
      color: #888;
    }}
    .spinner {{
      display: inline-block;
      width: 32px; height: 32px;
      border: 3px solid #e0e4ea;
      border-top-color: #1a2a3a;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin-bottom: 12px;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    #error {{
      display: none;
      background: #fff3cd;
      border: 1px solid #ffc107;
      padding: 16px 20px;
      border-radius: 8px;
      color: #856404;
      margin-top: 16px;
      line-height: 1.6;
    }}
    footer {{
      margin-top: 40px;
      font-size: 0.78rem;
      color: #aaa;
      text-align: center;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Rohstoffpreise Stahl</h1>
    <p class="meta" id="meta-ts">Lade Daten von GitHub...</p>
  </header>

  <div class="fx-bar" id="fx-bar" style="display:none"></div>

  <div id="loading">
    <div class="spinner"></div><br>
    Preise werden von GitHub geladen...
  </div>
  <div id="error"></div>
  <div id="content"></div>

  <footer>
    Quellen: Trading Economics, Yahoo Finance &nbsp;&middot;&nbsp;
    Alle Angaben ohne Gew&auml;hr. Preise k&ouml;nnen verz&ouml;gert sein.
  </footer>

  <script>
    var CSV_URL = '{GITHUB_RAW_CSV}';
    var CAT_ORDER = ['Basismetalle','Rohstoffe','Energietraeger','Legierungen','Stahlpreise'];
    var CAT_LABELS = {{
      'Basismetalle':  'Basismetalle',
      'Rohstoffe':     'Rohstoffe',
      'Energietraeger':'Energietr&auml;ger',
      'Legierungen':   'Legierungen',
      'Stahlpreise':   'Stahlpreise'
    }};

    function parseCSV(text) {{
      var lines = text.trim().split('\\n');
      var headers = lines[0].split(';').map(function(h) {{
        return h.trim().replace(/^\\uFEFF/, '');
      }});
      return lines.slice(1).filter(function(l) {{ return l.trim(); }}).map(function(line) {{
        var vals = line.split(';');
        var obj = {{}};
        headers.forEach(function(h, i) {{ obj[h] = (vals[i] || '').trim(); }});
        return obj;
      }});
    }}

    function fmtNum(val) {{
      if (!val || val === '') return '<span class="na">&mdash;</span>';
      var num = parseFloat(val.replace(',', '.'));
      if (isNaN(num)) return '<span class="na">&mdash;</span>';
      return num.toLocaleString('de-DE', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
    }}

    function fmtDate(isoDate) {{
      if (!isoDate) return '&mdash;';
      var parts = isoDate.split('-');
      return parts.length === 3 ? parts[2] + '.' + parts[1] + '.' + parts[0] : isoDate;
    }}

    function renderFX(fx, latestDate, zeitstempel) {{
      var bar = document.getElementById('fx-bar');
      var html = '';
      Object.keys(fx).forEach(function(k) {{
        html += '<div><span>' + k + '</span><strong>' + fmtNum(fx[k]) + '</strong></div>';
      }});
      bar.innerHTML = html;
      bar.style.display = 'flex';

      var tsDisplay = zeitstempel ? zeitstempel.replace('T', ' ') : fmtDate(latestDate);
      document.getElementById('meta-ts').innerHTML =
        'Stand: ' + tsDisplay + ' &nbsp;&middot;&nbsp; Datum: ' + fmtDate(latestDate);
    }}

    function renderTables(byCat) {{
      var content = document.getElementById('content');
      var allCats = CAT_ORDER.slice();
      Object.keys(byCat).forEach(function(c) {{
        if (CAT_ORDER.indexOf(c) === -1) allCats.push(c);
      }});

      var html = '';
      allCats.forEach(function(cat) {{
        var rows = byCat[cat];
        if (!rows || rows.length === 0) return;
        var label = CAT_LABELS[cat] || cat;

        var rowsHtml = rows.map(function(r) {{
          var warn = r.status !== 'OK' ? ' <span class="warn">&#9888;</span>' : '';
          return '<tr>'
            + '<td>' + r.rohstoff + warn + '</td>'
            + '<td class="num">' + fmtNum(r.preis) + '</td>'
            + '<td class="unit">' + (r.einheit || '&mdash;') + '</td>'
            + '<td class="num">' + fmtNum(r.preis_eur) + '</td>'
            + '<td class="src">' + r.quelle + '</td>'
            + '<td class="note">' + r.notiz + '</td>'
            + '</tr>';
        }}).join('');

        html += '<h2>' + label + '</h2>'
          + '<table><thead><tr>'
          + '<th>Rohstoff</th><th>Preis</th><th>Einheit</th>'
          + '<th>EUR-&Auml;quiv.</th><th>Quelle</th><th>Notiz</th>'
          + '</tr></thead><tbody>' + rowsHtml + '</tbody></table>';
      }});

      content.innerHTML = html;
    }}

    function loadData() {{
      fetch(CSV_URL + '?t=' + Date.now())
        .then(function(resp) {{
          if (!resp.ok) throw new Error('HTTP ' + resp.status);
          return resp.text();
        }})
        .then(function(text) {{
          var rows = parseCSV(text);

          // Neuesten Zeitstempel bestimmen (eindeutiger pro Crawler-Lauf)
          var tsSet = {{}};
          rows.forEach(function(r) {{ if (r.zeitstempel) tsSet[r.zeitstempel] = true; }});
          var timestamps = Object.keys(tsSet).sort();
          var latestTs = timestamps[timestamps.length - 1];
          var latestDate = latestTs ? latestTs.split(' ')[0] : '';
          var latest = rows.filter(function(r) {{ return r.zeitstempel === latestTs; }});

          // Wechselkurse
          var fx = {{}};
          latest.filter(function(r) {{ return r.kategorie === 'Waehrung'; }})
            .forEach(function(r) {{ fx[r.einheit] = r.preis; }});

          // Preiszeilen nach Kategorie gruppieren
          var byCat = {{}};
          latest.filter(function(r) {{ return r.kategorie !== 'Waehrung'; }})
            .forEach(function(r) {{
              if (!byCat[r.kategorie]) byCat[r.kategorie] = [];
              byCat[r.kategorie].push(r);
            }});

          renderFX(fx, latestDate, latest.length > 0 ? latest[0].zeitstempel : '');
          renderTables(byCat);
          document.getElementById('loading').style.display = 'none';
        }})
        .catch(function(e) {{
          document.getElementById('loading').style.display = 'none';
          var errDiv = document.getElementById('error');
          errDiv.innerHTML = '<strong>Daten konnten nicht geladen werden.</strong><br>'
            + e.message + '<br><br>'
            + '<small>Die Preise werden von GitHub abgerufen. '
            + 'Bitte stelle sicher, dass eine Internetverbindung besteht.</small>';
          errDiv.style.display = 'block';
          document.getElementById('meta-ts').textContent = 'Keine Verbindung zu GitHub';
        }});
    }}

    loadData();
  </script>
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")
    return html_path


# ------------------------------------------------------------------- Main ---

if __name__ == "__main__":
    today = date.today().isoformat()
    print("=" * 60)
    print(f"ROHSTOFFPREISE CRAWLER — {today}")
    print("=" * 60)
    print()

    results = crawl()

    # Waehrungskurse fuer Report separieren
    fx = {
        r["rohstoff"].replace("Kurs ", ""): r["preis"]
        for r in results
        if r["kategorie"] == "Waehrung" and r["preis"]
    }

    print()
    print("Speichere Daten...")
    save_csv(results)
    md_path = save_markdown(results, today, fx)
    html_path = save_html(results, today, fx)

    ok = sum(1 for r in results if r["status"] == "OK")
    total = sum(1 for r in results if r["kategorie"] != "Waehrung")

    print(f"\nErgebnis:  {ok}/{total + len(fx)} Werte abgerufen")
    print(f"History:   {HISTORY_CSV}")
    print(f"Report:    {md_path}")
    print(f"Website:   {html_path}")
