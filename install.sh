#!/usr/bin/env bash
# =============================================================================
# MedEcho — One-Click Installer  (Linux / macOS)
# =============================================================================
# Usage:
#   chmod +x install.sh && ./install.sh
#
# What this script does:
#   1. Checks for Python 3.10+
#   2. Creates an isolated virtual environment (.venv)
#   3. Installs all Python dependencies from requirements.txt
#   4. Creates a template .env file for your API keys
#   5. Creates a launch shortcut (run.sh)
# =============================================================================

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; exit 1; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "${BOLD}${CYAN}"
cat << 'EOF'
  __  __          _ _____      _
 |  \/  | ___  __| | ____|___| |__   ___
 | |\/| |/ _ \/ _` |  _| / __| '_ \ / _ \
 | |  | |  __/ (_| | |__| (__| | | | (_) |
 |_|  |_|\___|\__,_|_____\___|_| |_|\___/

  AI Radiology & Clinical Scribe  —  Installer v1.0
EOF
echo -e "${RESET}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Step 1 — Python version check ─────────────────────────────────────────────
info "Checking Python version..."
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON_CMD="$cmd"
            success "Found $cmd $VER"
            break
        fi
    fi
done
[ -z "$PYTHON_CMD" ] && error "Python 3.10+ is required. Download from https://python.org/downloads/"

# ── Step 2 — Virtual environment ──────────────────────────────────────────────
VENV_DIR="$SCRIPT_DIR/.venv"
if [ -d "$VENV_DIR" ]; then
    warn "Virtual environment already exists at .venv — skipping creation."
else
    info "Creating virtual environment at .venv ..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    success "Virtual environment created."
fi

# Activate venv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── Step 3 — Upgrade pip ──────────────────────────────────────────────────────
info "Upgrading pip..."
pip install --quiet --upgrade pip
success "pip is up to date."

# ── Step 4 — Install dependencies ─────────────────────────────────────────────
info "Installing Python dependencies (this may take a few minutes)..."
pip install --quiet -r requirements.txt
success "All dependencies installed."

# ── Step 5 — Create .env template ─────────────────────────────────────────────
ENV_FILE="$SCRIPT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    warn ".env file already exists — skipping."
else
    info "Creating .env template..."
    cat > "$ENV_FILE" << 'ENVEOF'
# ─────────────────────────────────────────────────────────────────────────────
# MedEcho — Environment Variables
# ─────────────────────────────────────────────────────────────────────────────
# You can enter API keys here OR directly in the MedEcho sidebar at runtime.
# Keys entered in the app sidebar take precedence over these values.

# Google Gemini API Key (required for cloud AI features)
# Get yours at: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=

# Hugging Face Token (required to download MedGemma / MedSigLIP local weights)
# Get yours at: https://huggingface.co/settings/tokens
HF_TOKEN=

# Google Cloud API Key (optional — enables MedASR cloud transcription)
# Get yours at: https://console.cloud.google.com/apis/credentials
GOOGLE_CLOUD_API_KEY=
ENVEOF
    success ".env template created. Edit it with your API keys if desired."
fi

# ── Step 6 — Create run script ────────────────────────────────────────────────
RUN_SCRIPT="$SCRIPT_DIR/run.sh"
cat > "$RUN_SCRIPT" << RUNEOF
#!/usr/bin/env bash
# MedEcho — Launch Script
set -euo pipefail
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
cd "\$SCRIPT_DIR"

# Load .env if it exists
[ -f "\$SCRIPT_DIR/.env" ] && export \$(grep -v '^#' "\$SCRIPT_DIR/.env" | xargs)

# Activate virtual environment
source "\$SCRIPT_DIR/.venv/bin/activate"

echo "Starting MedEcho..."
streamlit run app.py --server.headless false --browser.gatherUsageStats false
RUNEOF
chmod +x "$RUN_SCRIPT"
success "Launch script created: run.sh"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  Installation complete!${RESET}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${BOLD}To launch MedEcho:${RESET}"
echo -e "    ${CYAN}./run.sh${RESET}"
echo ""
echo -e "  ${BOLD}Or manually:${RESET}"
echo -e "    ${CYAN}source .venv/bin/activate && streamlit run app.py${RESET}"
echo ""
echo -e "  ${BOLD}API keys can be entered:${RESET}"
echo -e "    • In the ${CYAN}.env${RESET} file (persistent)"
echo -e "    • In the MedEcho sidebar at runtime (session-only)"
echo ""
