# Membean Bot

Python-Automatisierung für Membean-Training-Sessions. Playwright steuert den Browser, Groq (oder LM Studio) beantwortet Quiz-Fragen — mit menschlichem Timing und Mausbewegungen.

---

## Schnellstart

### Windows

1. **Einmal:** Doppelklick auf `setup.bat` (Python 3.9+ muss installiert sein, „Add to PATH“ ankreuzen)
2. `.env` öffnen und `AI_API_KEY` eintragen
3. **Täglich:** Doppelklick auf `start.bat`

Oder in der Eingabeaufforderung:

```bat
cd %USERPROFILE%\Desktop\"englisch word widows"
setup.bat
start.bat
```

### Mac

```bash
cd "englisch word widows"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# AI_API_KEY in .env eintragen (Groq: https://console.groq.com)

python main.py login    # manuell einloggen, Session speichern
python main.py verify   # Session prüfen
python main.py test-ai  # KI-Verbindung testen
python main.py run      # Dashboard → Start Training → Session (voll automatisch)
```

**Mac Doppelklick:** `start.command`

**Ctrl+C** stoppt die Session jederzeit.

### Einstellungen (Web-UI)

```bash
python main.py settings
```

Öffnet `http://127.0.0.1:8765` — dort kannst du Pausen, Survey-Prozent, KI-Key, Browser-Optionen usw. anpassen. **Speichern** schreibt direkt in `.env`. Bot danach neu starten.

Presets: **Schnell**, **Normal**, **Menschlich**, **Sehr langsam**

---

## Befehle

| Befehl | Beschreibung |
|--------|--------------|
| `python main.py setup` | Setup-Status und nächste Schritte |
| `python main.py login` | Browser öffnen, manuell einloggen, Cookies speichern |
| `python main.py verify` | Gespeicherte Session testen |
| `python main.py test-ai` | Groq / LM Studio mit Beispiel-Frage testen |
| `python main.py describe` | Aktuellen Seitentyp + extrahierte Daten anzeigen |
| `python main.py watch` | Seitentypen live loggen (manuell klicken) |
| `python main.py run` | **Hauptmodus** — volle Session automatisieren |
| `python main.py -v run` | Wie `run`, mit Debug-Logging |
| `python main.py settings` | **Einstellungsseite** im Browser (Pausen, %, KI, …) |

---

## Was der Bot macht

**Start (automatisch):**
1. Dashboard öffnen → ggf. Banner schließen
2. **Start Training** klicken
3. Dauer wählen (Standard: 10 min) → **Proceed**
4. Interstitials („Let's continue" usw.) wegklicken
5. Training-Schleife starten

| Seitentyp | Erkennung | Aktion |
|-----------|-----------|--------|
| **Learn** | Wort + Erklärung + Quiz | Quiz beantworten → 2 s warten → **Next** |
| **MCQ** | Multiple Choice mit Vokabel | KI wählt Option → klicken |
| **Spell** | „Spell the word" / Unterstriche | Wort aus Cache eintippen → Enter |
| **Survey** | Meta-Fragen (Schwierigkeit, Verständnis) | 95 % realistische Antwort → klicken |
| **Continue** | „Let's continue" | Automatisch wegklicken |
| **Done** | „Take a break" / Session-Ende | Bot stoppt |

Warn-Popups (OK, Got it, Close) werden automatisch geschlossen.

---

## Menschliches Verhalten (Anti-Bot)

Der Bot imitiert absichtlich **unregelmäßiges** Verhalten — keine perfekte Linie, keine roboterhaften Intervalle.

| # | Feature | Umsetzung |
|---|---------|-----------|
| 1 | Breitere Pausen | Zufällige Delays zwischen Aktionen (`DELAY_MIN` / `DELAY_MAX`) |
| 2 | Variable Tippgeschwindigkeit | Pro Zeichen unterschiedliche Verzögerung, längere Wörter langsamer |
| 3 | Denk-Pause | 1–3 s Pause vor MCQ- und Learn-Quiz-Antworten |
| 4 | Survey 95 % | Meist mittlere/realistische Antwort (nur Zwischenfragen) |
| 5 | Sichtbarer Browser | `HEADLESS=false` — kein Headless-Modus |
| — | Quiz-Zielgenauigkeit | `QUIZ_TARGET_ACCURACY` — z. B. 87 % richtig bei MCQ/Learn |
| 9 | Seitenwechsel-Pause | Kurze Pause (aus bei Zeitlimit-Aufgaben) |
| 10 | Gebogene Mausbewegung | Bezier-Kurve mit Jitter — **keine gerade Linie** |

Relevante `.env`-Werte:

```env
DELAY_MIN=0.8
DELAY_MAX=2.5
THINK_PAUSE_MIN=1.0
THINK_PAUSE_MAX=3.0
PAGE_TRANSITION_MIN=0.5
PAGE_TRANSITION_MAX=1.5
QUIZ_TARGET_ACCURACY=100
TYPE_DELAY_MIN_MS=90
TYPE_DELAY_MAX_MS=220
SURVEY_REALISTIC_RATE=0.95
HEADLESS=false
```

---

## KI-Provider

### Groq (Standard)

```env
AI_PROVIDER=groq
AI_API_URL=https://api.groq.com/openai/v1
AI_MODEL=allam-2-7b
AI_API_KEY=gsk_...
ANSWER_MODE=ai
```

### LM Studio (lokal)

```env
AI_PROVIDER=lmstudio
AI_API_URL=http://localhost:1234/v1
AI_MODEL=qwen3-8b
AI_API_KEY=lm-studio
ANSWER_MODE=ai
```

LM Studio muss laufen, bevor `test-ai` oder `run` startet.

---

## Login & Session

1. `python main.py login` — Browser öffnet Membean
2. Manuell einloggen und auf der **Training-Seite** bleiben
3. Im Terminal **Enter** drücken → Cookies landen in `storage_state.json`
4. Optional: Training-URL in `.env` als `MEMBEAN_TRAINING_URL` speichern

Session läuft ab? Einfach `login` erneut ausführen.

---

## Projektstruktur

```
englisch word widows/
├── start.bat              ← Windows: Doppelklick starten
├── setup.bat              ← Windows: Einmal-Setup
├── start.command          ← Mac: Doppelklick starten
├── README.md              ← diese Datei
├── PROJEKTPLAN.md         ← ursprünglicher Entwicklungsplan
├── main.py                ← CLI-Einstiegspunkt
├── runner.py              ← Hauptschleife
├── browser.py             ← Playwright, Login, Cookies
├── page_detector.py       ← Seitentyp erkennen
├── extractors.py          ← Text/DOM extrahieren
├── answer_engine.py       ← Antwort-Logik (KI + Survey)
├── ai_client.py           ← Groq / LM Studio API
├── actions.py             ← Klicks, Tippen, Mausbewegung
├── config.py              ← .env laden
├── .env                   ← Secrets & Timing (nicht committen)
├── .env.example           ← Vorlage
├── storage_state.json     ← Browser-Session (nicht committen)
├── session_meta.json      ← letzte URL / Metadaten
├── logs/session.log       ← Laufzeit-Log
└── screenshots/           ← Debug-Screenshots bei Fehlern
```

---

## Ablauf (vereinfacht)

```
Session starten
    ↓
Seitentyp erkennen
    ↓
┌─────────┬─────────┬─────────┬─────────┐
│  Learn  │   MCQ   │  Spell  │ Survey  │
│ KI+Next │   KI    │  Tippen │ 95% KI  │
└─────────┴─────────┴─────────┴─────────┘
    ↓
Menschliche Pause → nächste Seite
    ↓
„Take a break" → Ende
```

---

## Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| `No saved session` | `python main.py login` |
| Verify schlägt fehl | Auf Training-Seite bleiben beim Login; `MEMBEAN_TRAINING_URL` setzen |
| KI antwortet nicht | `python main.py test-ai`; API-Key prüfen |
| Quiz wird übersprungen | `QUIZ_LOAD_WAIT_MIN/MAX` erhöhen |
| Spell tippt ins Leere | `-v run` für Debug; ggf. manuell auf Spell-Seite testen mit `describe` |
| Warn-Popup blockiert | Sollte auto-dismissed werden — Screenshot in `screenshots/` prüfen |

Logs: `logs/session.log`  
Verbose: `python main.py -v run`

---

## Sicherheit

- `.env`, `storage_state.json` und `session_meta.json` **nicht** committen oder teilen
- Groq API-Key regelmäßig rotieren, wenn er exponiert wurde

---

## Lizenz / Hinweis

Nur für persönliche Nutzung. Membean-Nutzungsbedingungen beachten.
