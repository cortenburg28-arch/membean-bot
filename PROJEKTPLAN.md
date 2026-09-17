# Membean-Automatisierung — Projektplan

Automatisches Durcharbeiten von Membean-Training-Sessions mit **lokaler KI** für alle Fragen, bei denen die richtige Antwort zählt.

---

## Ziel

Ein Python-Programm steuert den Browser (Playwright), erkennt den Seitentyp und:

| Seitentyp | Aktion | Richtige Antwort nötig? |
|-----------|--------|-------------------------|
| **Lernseite** (Wort + Erklärung) | Quiz auf der Seite beantworten → Next | ✅ Ja |
| **Multiple Choice** | Frage lesen → Option wählen | ✅ Ja |
| **Buchstabieren** | Gemerktes Wort eintippen | ✅ Ja (exakt) |
| **Zwischenfrage** | Frage lesen → Option wählen | ✅ Ja |
| **Session-Ende** | Stoppen | — |

Bei **allen Fragetypen** entscheidet die **lokale KI**, welche Option angeklickt wird — nicht zufällig.

---

## Architektur

```
┌─────────────────────────────────────────────────────────┐
│                      main.py                            │
│                   (Hauptschleife)                       │
└─────────────────────────┬───────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
  page_detector.py   extractors.py    actions.py
  (Seitentyp)        (Text lesen)     (Klick/Tippen)
                          │
                          ▼
                    ai_client.py
                  (Lokale KI-API)
                          │
                          ▼
                   browser.py
              (Playwright + Cookies)
```

### Ablauf pro Seitenwechsel

```
Seite laden
    → Seitentyp erkennen
    → Inhalt extrahieren
    → [Frage?] → Lokale KI → Buchstabe a/b/c/d
    → Aktion ausführen (klicken / tippen)
    → Kurz warten → nächste Seite
```

---

## Tech-Stack

| Komponente | Tool | Zweck |
|------------|------|--------|
| Sprache | Python 3.11+ | Hauptlogik |
| Browser | Playwright | Seite steuern, DOM lesen |
| KI | Ollama / LM Studio / OpenAI-kompatibel | Antworten für alle Fragetypen |
| Config | `.env` + `config.py` | Login, API-URL, Modell |
| Logging | `logging` + Datei | Debug & Erfolgskontrolle |

---

## Phase 0 — Vorbereitung

**Dauer:** ~1–2 Stunden

### Checkliste

- [ ] Python 3.11+ installiert
- [ ] Lokale KI läuft (Ollama/LM Studio)
- [ ] Modellname notiert (z.B. `llama3.2`, `mistral`)
- [ ] API-URL notiert (Standard Ollama: `http://localhost:11434`)
- [ ] KI mit Test-Prompt geprüft (siehe unten)

### KI-Schnelltest

Prompt an die lokale KI senden — Antwort muss **nur ein Buchstabe** sein:

```
Question: Someone who is contemplating something is:
a. Carefully considering or watching it
b. Taking it without permission
c. Confused about what to do with it
d. I'm not sure

Reply with ONLY one letter: a, b, c, or d.
```

Erwartete Antwort: `a`

### Projekt-Setup

```bash
cd "englsich worter"
python -m venv venv
source venv/bin/activate
pip install playwright python-dotenv requests openai
playwright install chromium
```

---

## Phase 1 — Browser & Login

**Dauer:** ~2–4 Stunden

### Ziele

1. Playwright startet Chromium (sichtbar zum Debuggen)
2. Einmal manuell bei Membean einloggen
3. Session-Cookies in `storage_state.json` speichern
4. Script öffnet Membean mit Cookies → landet in Training-Session

### Erfolgskriterium

Script navigiert ohne manuelles Login zur laufenden Training-URL.

### Dateien

- `browser.py` — Browser starten, Cookies laden/speichern
- `storage_state.json` — gespeicherte Session (nicht committen!)

---

## Phase 2 — Seitentyp erkennen

**Dauer:** ~3–5 Stunden

### Seitentypen

Reihenfolge beim Erkennen wichtig — **spezifischste zuerst**:

| Typ | ID | Erkennungsmerkmale |
|-----|----|--------------------|
| `spell` | Buchstabieren | Text „Spell the word" oder Unterstriche `_ _ _` |
| `mcq` | Multiple Choice | „Q:" + Optionen a./b./c./d. + Wort oben |
| `survey` | Zwischenfrage | Frage ohne Vokabel-Kontext (Schwierigkeit, Verständnis, etc.) |
| `learn` | Lernseite | Wort groß + „Next"-Button + Kontext/Quiz |
| `done` | Ende | Session abgeschlossen / kein bekannter Typ mehr |

### Zwischenfragen vs. Multiple Choice

**Unterschied:**

- **MCQ:** Bezieht sich auf ein **Vokabelwort** (z.B. „Someone who is *contemplating* something is:")
- **Zwischenfrage:** Meta-Fragen zur Session (z.B. „How well do you know this word?", „How difficult was this?", „Have you seen this word before?")

Erkennung: Kein Zielwort in der Überschrift + typische Formulierungen („How well", „How difficult", „rate", „familiar").

### Erfolgskriterium

Bei 20 manuell durchgeklickten Seiten erkennt das Script jeden Typ korrekt (Log-Ausgabe prüfen).

---

## Phase 3 — Inhalte von der Seite lesen

**Dauer:** ~3–4 Stunden

### Lernseite (`learn`)

Extrahieren und cachen:

```python
{
    "word": "contemplate",
    "context": "...",           # Context-Absatz
    "memory_hook": "...",       # optional
    "quiz_question": "...",     # falls Quiz sichtbar
    "quiz_options": ["a. ...", "b. ...", "c. ..."]
}
```

→ In `word_cache` speichern für spätere MCQ-/Spell-Schritte.

### Multiple Choice (`mcq`)

```python
{
    "word": "contemplate",      # falls angezeigt
    "question": "Q: Someone who is contemplating something is:",
    "options": {
        "a": "Carefully considering or watching it",
        "b": "Taking it without asking permission",
        "c": "Confused about what to do with it",
        "d": "I'm not sure"
    }
}
```

### Zwischenfrage (`survey`)

```python
{
    "question": "How well do you know this word?",
    "options": {
        "a": "I've never seen it before",
        "b": "I've seen it but don't know it",
        "c": "I kind of know it",
        "d": "I know it well"
    },
    "word_context": "contemplate"   # aus word_cache, falls hilfreich
}
```

### Buchstabieren (`spell`)

- Wortlänge aus Unterstrichen ableiten
- Wort aus `word_cache` (letztes gelerntes Wort)
- Kein KI-Aufruf nötig — exaktes Tippen

### Tipp: Selektoren dokumentieren

In DevTools (F12) die CSS-Selektoren für Wort, Frage und Optionen notieren und in `extractors.py` zentral halten — erleichtert Wartung wenn Membean das Layout ändert.

---

## Phase 4 — Lokale KI anbinden

**Dauer:** ~2–3 Stunden

### Eine Funktion für alle Fragetypen

```python
def ask_ai(question: str, options: dict, context: str = "") -> str:
    """
    Returns: "a", "b", "c", or "d"
    """
```

### Prompt-Vorlagen

#### Vokabel-Fragen (Learn-Quiz & MCQ)

```
You are answering a vocabulary quiz. Pick the ONE correct answer.

Word: {word}
Context from learning page: {context}

Question: {question}

Options:
a. {option_a}
b. {option_b}
c. {option_c}
d. {option_d}

Reply with ONLY a single letter: a, b, c, or d. Nothing else.
```

#### Zwischenfragen (Survey)

```
You are answering a question about your vocabulary learning progress.
Choose the most appropriate honest answer.

Question: {question}

Options:
a. {option_a}
b. {option_b}
c. {option_c}
d. {option_d}

Context: The user has been studying the word "{word}" and answered previous questions correctly.

Reply with ONLY a single letter: a, b, c, or d. Nothing else.
```

> **Hinweis zu Zwischenfragen:** Formulierungen wie „I kind of know it" oder „It was moderately difficult" sind oft die **mitteilsichere** Antwort — nicht zu extrem. Die KI soll realistisch antworten, damit es nicht auffällt.

### KI-Parameter

| Parameter | Wert | Grund |
|-----------|------|--------|
| `temperature` | 0.0 – 0.2 | Konsistente, fokussierte Antworten |
| Antwort parsen | Erstes `a`/`b`/`c`/`d` | Lokale Modelle geben manchmal Satz mit |
| Retry | 1× bei ungültiger Antwort | Robustheit |
| Fallback | `"c"` (Mitte) bei Survey, `"a"` bei MCQ | Letzter Ausweg |

### Ollama-Beispiel

```python
import requests

def ask_local_ai(prompt: str) -> str:
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        },
        timeout=30,
    )
    raw = response.json()["response"].strip().lower()
    for char in raw:
        if char in "abcd":
            return char
    return "a"  # Fallback
```

### Erfolgskriterium

- 10 MCQ-Fragen → ≥ 8/10 richtig
- 5 Zwischenfragen → sinnvolle, konsistente Antworten

---

## Phase 5 — Aktionen ausführen

**Dauer:** ~2–3 Stunden

| Seitentyp | Schritte |
|-----------|----------|
| `learn` | Inhalt extrahieren → cachen → Quiz (falls da) → KI → Option klicken → `sleep(0.6)` → **Next** |
| `mcq` | Frage + Optionen → KI (+ Kontext aus Cache) → Option klicken |
| `spell` | Wort aus Cache tippen → Enter |
| `survey` | Frage + Optionen → KI → Option klicken |
| `done` | Script beenden |

### Timing

Nicht instant klicken — wirkt unnatürlich:

```python
import random
time.sleep(random.uniform(0.5, 1.5))
```

---

## Phase 6 — Hauptschleife & Fehlerbehandlung

**Dauer:** ~3–5 Stunden

### Pseudocode

```python
def run_session(page):
    word_cache = {}

    while True:
        page_type = detect_page_type(page)
        log(f"→ {page_type}")

        if page_type == "done":
            break

        try:
            if page_type == "learn":
                data = extract_learn_page(page)
                word_cache[data["word"]] = data
                if data.get("quiz_question"):
                    letter = ask_ai(
                        data["quiz_question"],
                        data["quiz_options"],
                        context=data["context"],
                    )
                    click_option(page, letter)
                sleep(0.6)
                click_next(page)

            elif page_type == "mcq":
                data = extract_mcq_page(page)
                ctx = word_cache.get(data.get("word"), {})
                letter = ask_ai(
                    data["question"],
                    data["options"],
                    context=ctx.get("context", ""),
                )
                click_option(page, letter)

            elif page_type == "spell":
                word = get_last_word(word_cache)
                type_word(page, word)

            elif page_type == "survey":
                data = extract_survey_page(page)
                ctx = get_last_word_context(word_cache)
                letter = ask_ai(
                    data["question"],
                    data["options"],
                    context=ctx,
                )
                click_option(page, letter)

            sleep(random.uniform(0.3, 0.8))

        except Exception as e:
            log(f"Fehler: {e}")
            save_screenshot(page, "error")
            sleep(2)
            # retry same page
```

### Fehlerfälle

| Problem | Lösung |
|---------|--------|
| Unbekannter Seitentyp | Screenshot speichern, 2 s warten, retry |
| KI antwortet ungültig | Retry mit kürzerem Prompt |
| Seite lädt langsam | `page.wait_for_load_state("networkidle")` |
| Falsches Wort beim Spell | Immer letztes Wort aus `learn`-Schritt cachen |
| Session abgelaufen | Cookies erneuern (neu einloggen) |

---

## Phase 7 — Testen & Verfeinern

**Dauer:** ~4–8 Stunden

### Testplan

| # | Test | Erwartung |
|---|------|-----------|
| 1 | Ein Wort komplett (Learn → MCQ → Spell) | Durchlauf ohne Eingriff |
| 2 | Zwischenfrage erscheint | KI wählt sinnvolle Option |
| 3 | Volle Session (15+ Min.) | Kein Absturz |
| 4 | KI-Log prüfen | Frage → Antwort → Seite weitergemacht |
| 5 | Edge: „I'm not sure" als Option | KI wählt nie `d` wenn echte Antwort existiert |
| 6 | Edge: sehr langes Wort (12+ Buchstaben) | Spell korrekt |

### Log-Format (`logs/session.log`)

```
[12:01:03] LEARN  word=contemplate
[12:01:04] QUIZ   q="What happens when you contemplate..." → AI: a ✓
[12:01:06] MCQ    word=contemplate q="Someone who is..." → AI: a ✓
[12:01:08] SPELL  word=contemplate ✓
[12:01:10] SURVEY q="How well do you know this word?" → AI: c ✓
[12:01:12] LEARN  word=...
```

---

## Projektstruktur

```
englsich worter/
├── PROJEKTPLAN.md          ← diese Datei
├── main.py                 # Hauptschleife, Einstiegspunkt
├── browser.py              # Playwright, Login, Cookies
├── page_detector.py        # Seitentyp erkennen
├── extractors.py           # Text/DOM von Seite lesen
├── ai_client.py            # Lokale KI ansprechen
├── actions.py              # Klicken, Tippen, Next
├── config.py               # URLs, Modell, Delays
├── .env                    # API-URL, Modellname (optional Login)
├── .env.example            # Vorlage ohne Secrets
├── .gitignore              # venv/, .env, storage_state.json, logs/
├── requirements.txt
├── storage_state.json      # Browser-Session (gitignored)
└── logs/
    └── session.log
```

---

## Zeitplan

| Phase | Inhalt | Dauer | Kumuliert |
|-------|--------|-------|-----------|
| 0 | Vorbereitung, KI testen | 1–2 h | 2 h |
| 1 | Browser & Login | 2–4 h | 6 h |
| 2 | Seitentyp erkennen | 3–5 h | 11 h |
| 3 | Inhalte extrahieren | 3–4 h | 15 h |
| 4 | KI anbinden | 2–3 h | 18 h |
| 5 | Aktionen | 2–3 h | 21 h |
| 6 | Schleife & Fehler | 3–5 h | 26 h |
| 7 | Testen | 4–8 h | **~30–35 h** |

**Realistisch:** 4–5 Abende oder ein Wochenende.

---

## Empfohlene Reihenfolge

```
1. Phase 0 + 1     → Playwright läuft, Login funktioniert
2. Phase 2         → Seitentypen werden geloggt (manuell klicken, Script beobachtet)
3. Phase 4         → KI separat testen (ohne Browser)
4. Phase 3 + 5     → Extraktion + Klicks verbinden
5. Phase 6 + 7     → Schleife, volle Session testen
```

---

## Risiken & Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|--------|----------------|
| Membean ändert HTML-Layout | Selektoren zentral in `extractors.py` |
| KI wählt falsche MCQ-Antwort | Kontext von Lernseite mitgeben; Temperature niedrig |
| KI antwortet bei Survey zu extrem | Prompt: „moderate, realistic answer" |
| Session/Cookies abgelaufen | `storage_state.json` regelmäßig erneuern |
| Zu schnelles Klicken | Random-Delays (0.5–1.5 s) |
| Unbekannte neue Seitentypen | Screenshot + Log → manuell Selektor ergänzen |

---

## Konfiguration (`.env.example`)

```env
# Lokale KI
AI_API_URL=http://localhost:11434
AI_MODEL=llama3.2
AI_PROVIDER=ollama          # ollama | lmstudio | openai_compatible

# Membean (optional — sonst manueller Login)
MEMBEAN_URL=https://membean.com/training_sessions

# Timing (Sekunden)
DELAY_MIN=0.5
DELAY_MAX=1.5
LEARN_PAGE_WAIT=0.6
```

---

## Nächste Schritte

1. Lokale KI-Details eintragen (Provider, Modell, URL)
2. Phase 0 + 1 umsetzen: Projekt-Setup und Login-Script
3. Beim manuellen Durchklicken Screenshots + HTML für Selektoren sammeln

---

*Erstellt: September 2026*
