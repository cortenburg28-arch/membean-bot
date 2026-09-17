#!/bin/bash
# Doppelklick auf dem Mac → Menü öffnet sich

resolve_project_dir() {
    local dir
    dir="$(cd "$(dirname "$0")" && pwd)"

    # Schon im richtigen Ordner?
    if [ -f "$dir/main.py" ] && [ -d "$dir/venv" ]; then
        echo "$dir"
        return 0
    fi

    # Google Drive / iCloud führt oft eine Kopie aus .tmp.driveupload aus
    local fallback="$HOME/Desktop/englisch word widows"
    if [ -f "$fallback/main.py" ] && [ -d "$fallback/venv" ]; then
        echo "$fallback"
        return 0
    fi

    # Nach oben suchen (z. B. wenn Skript woanders liegt)
    local current="$dir"
    while [ "$current" != "/" ]; do
        if [ -f "$current/main.py" ]; then
            echo "$current"
            return 0
        fi
        current="$(dirname "$current")"
    done

    echo "$dir"
}

PROJECT_DIR="$(resolve_project_dir)"
cd "$PROJECT_DIR" || exit 1

if [ ! -d "venv" ]; then
    echo "Erstes Mal? Bitte README lesen — venv fehlt noch."
    echo "Ordner: $PROJECT_DIR"
    echo ""
    echo "Einmal in Terminal ausführen:"
    echo '  cd ~/Desktop/"englisch word widows"'
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo "  playwright install chromium"
    read -r -p "Enter drücken zum Beenden…"
    exit 1
fi

source venv/bin/activate
python main.py start
