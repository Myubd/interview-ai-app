#!/usr/bin/env bash
# ローカル起動スクリプト（バックエンド + フロントエンド を同時起動）
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# ── 色付きログ ──────────────────────────────
log_info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
log_ok()    { echo -e "\033[1;32m[ OK ]\033[0m  $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }

# ── Ollama 起動確認 ──────────────────────────
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    log_warn "Ollama が起動していません。"
    log_warn "別ターミナルで 'ollama serve' を実行してから再試行してください。"
    log_warn "（このスクリプトは続行しますが、AI機能は動作しません）"
fi

# ── バックエンド ─────────────────────────────
log_info "バックエンドを起動中 (http://localhost:8000)..."
cd "$BACKEND"
if [ ! -d ".venv" ]; then
    log_info "仮想環境を作成中..."
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
log_ok "バックエンド PID: $BACKEND_PID"

# ── フロントエンド ────────────────────────────
log_info "フロントエンドを起動中 (http://localhost:5173)..."
cd "$FRONTEND"
if [ ! -d "node_modules" ]; then
    log_info "npm install 中..."
    npm install --silent
fi
npm run dev &
FRONTEND_PID=$!
log_ok "フロントエンド PID: $FRONTEND_PID"

# ── 終了ハンドラ ──────────────────────────────
cleanup() {
    log_info "終了中..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

log_ok "起動完了！"
echo ""
echo "  フロントエンド : http://localhost:5173"
echo "  API ドキュメント: http://localhost:8000/docs"
echo "  Streamlit 版  : http://localhost:8501  (別途起動が必要)"
echo ""
echo "  停止: Ctrl+C"
echo ""

wait
