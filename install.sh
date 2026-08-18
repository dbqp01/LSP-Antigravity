#!/usr/bin/env bash
# Antigravity LSP Enforcement Kit - Automatic Installer for Linux & macOS

set -e

echo "============================================================"
echo " Antigravity LSP Enforcement Kit - Automatic Installer"
echo "============================================================"

echo ""
echo "[1/3] Checking base environment..."
if ! command -v python3 &> /dev/null; then
    echo "[FAIL] Python 3 not found. Please install Python 3.10+."
    exit 1
fi
echo "  [OK] Python detected: $(python3 --version)"

if command -v php &> /dev/null; then
    echo "  [OK] PHP detected: $(php -v | head -n 1)"
else
    echo "  [INFO] PHP CLI not found. Install php-cli if developing in PHP."
fi

echo ""
echo "[2/3] Installing recommended analysis tools..."
pip3 install --quiet --upgrade ruff pyright 2>/dev/null || echo "  [WARN] Pip install failed; using built-in AST/Symtable."

if command -v npm &> /dev/null; then
    npm install -g --silent @biomejs/biome typescript @astrojs/check astro 2>/dev/null || echo "  [WARN] NPM global install failed."
else
    echo "  [INFO] npm not found. TS/Biome tools skipped."
fi

echo ""
echo "[3/3] Deploying hooks..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/plugin/lsp-enforcement-kit"

mkdir -p .agents/hooks .agents/plugins/lsp-enforcement-kit "$HOME/.gemini/config/plugins/lsp-enforcement-kit"

cp -f "$SOURCE_DIR/nav_guard.py" .agents/hooks/
cp -f "$SOURCE_DIR/lsp_audit.py" .agents/hooks/
cp -f "$SOURCE_DIR/hooks.json" .agents/hooks.json
cp -rf "$SOURCE_DIR/"* .agents/plugins/lsp-enforcement-kit/
cp -rf "$SOURCE_DIR/"* "$HOME/.gemini/config/plugins/lsp-enforcement-kit/"

echo "  [OK] Deployed to workspace (.agents/) and globally (~/.gemini/config/plugins/)"

echo ""
python3 .agents/hooks/lsp_audit.py status
echo ""
echo "[DONE] Antigravity LSP Enforcement Kit successfully installed and active."
