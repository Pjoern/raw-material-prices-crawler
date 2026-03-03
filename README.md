# Rohstoffpreise Stahl — Crawler

Täglicher automatischer Abruf von Rohstoffpreisen für die Stahlherstellung via GitHub Actions.

## Rohstoffe

| Rohstoff | Einheit | Quelle |
|----------|---------|--------|
| Nickel | USD/T | Trading Economics |
| Eisenerz 62% Fe | USD/T | Trading Economics |
| Kokskohle (Premium Hard) | USD/T | Trading Economics |
| Kobalt | USD/T | Trading Economics |
| Mangan (Erz) | CNY/mtu | Trading Economics |
| Silizium | CNY/T | Trading Economics |
| Stahl HRC | CNY/T | Trading Economics |
| Kupfer | USD/MT | Yahoo Finance (HG=F) |
| Aluminium | USD/MT | Yahoo Finance (ALI=F) |
| Zink | USD/MT | Yahoo Finance (ZNC=F) |
| Blei | USD/MT | Yahoo Finance (LE=F) |

## Daten

- `data/prices_history.csv` — Vollständige Preishistorie (wächst täglich)
- `reports/YYYY-MM-DD.md` — Tagesbericht pro Tag

## Ausführung

### Automatisch
GitHub Actions läuft jeden Werktag um **07:30 UTC** (08:30 MEZ / 09:30 MESZ).
Ergebnisse werden automatisch committed.

Manueller Start: GitHub → Actions → "Rohstoffpreise täglich crawlen" → Run workflow

### Lokal
```bash
pip install -r requirements.txt
python crawler.py
```

## Setup (einmalig)

1. Neues GitHub-Repo erstellen
2. Diesen Ordner pushen:
   ```bash
   git init
   git add .
   git commit -m "initial"
   git remote add origin https://github.com/DEIN-USER/REPO-NAME.git
   git push -u origin main
   ```
3. **GitHub Secrets** einrichten (Repo → Settings → Secrets → Actions):

   | Secret | Inhalt |
   |--------|--------|
   | `MAIL_USERNAME` | Absender-E-Mail (z.B. `name@gmail.com`) |
   | `MAIL_PASSWORD` | Gmail: App-Passwort (nicht dein Login-Passwort!) |

   Die Empfänger-Adresse ist direkt im Workflow hinterlegt (`huneke-bds@stahlhandel.com`).

   > **Gmail App-Passwort erstellen:**
   > Google-Konto → Sicherheit → 2-Schritt-Verifizierung aktivieren →
   > App-Passwörter → App: "E-Mail", Gerät: "Windows" → Generieren

4. GitHub Actions läuft automatisch jeden Werktag um 07:30 UTC

## Hinweise

- Preise sind **tagesaktuell** (kein Echtzeit-Ticker)
- CNY-Preise (Mangan, Silizium, HRC) sind nicht in EUR umgerechnet
- Bei Marktschluss (Wochenende/Feiertage) werden letztverfügbare Preise geliefert
- Alle Angaben ohne Gewähr
