#!/usr/bin/env bash
# PC Check - avvio con un comando su macOS e Linux:
#   curl -fsSL https://raw.githubusercontent.com/pezzaliapp/pc-check/main/run.sh | bash
# Con opzioni:  ... | bash -s -- --fast
set -e

main() {
  RAW="${PC_CHECK_RAW:-https://raw.githubusercontent.com/pezzaliapp/pc-check/main}"
  DIR="$HOME/.pc-check"
  mkdir -p "$DIR"

  if ! command -v python3 >/dev/null 2>&1; then
    echo "Serve Python 3 (gratuito)."
    if [ "$(uname)" = "Darwin" ]; then
      echo "Su Mac esegui:  xcode-select --install   poi rilancia questo comando."
    else
      echo "Su Linux esegui ad esempio:  sudo apt install python3 python3-venv   (o dnf / pacman)"
    fi
    exit 1
  fi

  echo "Scarico l'ultima versione di PC Check..."
  curl -fsSL "$RAW/pc_check.py" -o "$DIR/pc_check.py"

  # Ambiente Python separato: non tocca nulla del sistema
  if [ ! -x "$DIR/venv/bin/python" ]; then
    python3 -m venv "$DIR/venv" >/dev/null 2>&1 || rm -rf "$DIR/venv"
  fi

  if [ -x "$DIR/venv/bin/python" ]; then
    PY="$DIR/venv/bin/python"
    "$PY" -m pip install -q --disable-pip-version-check --upgrade psutil
  else
    PY="python3"
    if ! python3 -c "import psutil" >/dev/null 2>&1; then
      echo "Impossibile preparare l'ambiente. Installa uno di questi pacchetti e riprova:"
      echo "  sudo apt install python3-venv     oppure     sudo apt install python3-psutil"
      exit 1
    fi
  fi

  "$PY" "$DIR/pc_check.py" "$@" < /dev/null
}

main "$@"
