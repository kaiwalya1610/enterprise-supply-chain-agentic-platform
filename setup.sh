#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV_DIR="$ROOT/.venv"
PYTHON_VERSION="${PYTHON_VERSION:-3.13}"

echo "==> Setting up enterprise-supply-chain-agentic-platform"

if ! command -v uv >/dev/null 2>&1; then
  echo "==> uv not found; installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is still unavailable. Install it from https://docs.astral.sh/uv/ and rerun."
  exit 1
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: Node.js and npm are required for the frontend."
  echo "Install Node.js 20+ from https://nodejs.org/ and rerun."
  exit 1
fi

echo "==> Creating Python virtual environment with uv (Python ${PYTHON_VERSION})"
if [[ -d "$VENV_DIR" ]]; then
  echo "    .venv already exists; reusing it"
else
  uv venv "$VENV_DIR" --python "$PYTHON_VERSION"
fi

echo "==> Installing Python dependencies from requirements.txt"
uv pip install --python "$VENV_DIR/bin/python" -r requirements.txt

echo "==> Installing frontend dependencies"
(
  cd "$ROOT/frontend"
  npm install
)

if [[ ! -f "$ROOT/.env" ]]; then
  echo
  echo "NOTE: No .env file found."
  echo "Create one with your OpenRouter credentials before running ./start.sh"
  echo "Example keys: OPENROUTER_API_KEY, OPENROUTER_CHAT_MODEL, OPENROUTER_GUARDRAIL_MODEL"
fi

echo
echo "Setup complete."
echo "Next: ./start.sh"
