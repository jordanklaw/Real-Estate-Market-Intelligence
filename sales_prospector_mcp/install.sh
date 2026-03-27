#!/bin/bash
# Sales Prospector MCP - Installation Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"

echo "============================================"
echo "  Sales Prospector MCP - Installation"
echo "============================================"
echo ""

# Create virtual environment
echo "[1/3] Creating virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install requirements
echo "[2/3] Installing dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r "$SCRIPT_DIR/requirements.txt"

# Create briefs directory
mkdir -p "$SCRIPT_DIR/../briefs"

echo ""
echo "[3/3] Installation complete!"
echo ""
echo "============================================"
echo "  Claude Desktop Configuration"
echo "============================================"
echo ""
echo "Add this to your Claude Desktop config file:"
echo "(Linux: ~/.config/Claude/claude_desktop_config.json)"
echo "(macOS: ~/Library/Application Support/Claude/claude_desktop_config.json)"
echo "(Windows: %APPDATA%/Claude/claude_desktop_config.json)"
echo ""
echo "{"
echo "  \"mcpServers\": {"
echo "    \"sales_prospector\": {"
echo "      \"command\": \"${VENV_DIR}/bin/python\","
echo "      \"args\": [\"${SCRIPT_DIR}/server.py\"]"
echo "    }"
echo "  }"
echo "}"
echo ""
echo "============================================"
echo "  Quick Test"
echo "============================================"
echo ""
echo "To verify the server starts correctly:"
echo "  source ${VENV_DIR}/bin/activate"
echo "  python ${SCRIPT_DIR}/server.py"
echo ""
echo "To run the daily brief manually:"
echo "  source ${VENV_DIR}/bin/activate"
echo "  python ${SCRIPT_DIR}/../daily_brief.py"
echo ""
echo "Cron entry for daily brief (5:30 AM Pacific, Mon-Fri):"
echo "  30 12 * * 1-5 cd ${SCRIPT_DIR}/.. && ${VENV_DIR}/bin/python daily_brief.py"
echo ""
