#!/usr/bin/env bash
# ローカル起動スクリプト（バックエンド + フロントエンド を同時起動）
#
# [変更点]
# - 初回起動時に必要な Ollama モデルを自動ダウンロードするよう改善。
#   モデルがすでにダウンロード済みの場合はスキップする。
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# アプリで使用するモデル（settings.py の DEFAULTS と合わせる）
CHAT_MODEL="qwen3:8b"
EMBED_MODEL="nomic-embed-text"

# ── 色付きログ ──────────────────────────────
log_info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
log_ok()    { echo -e "\033[1;32m[ OK ]\033[0m  $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
log_error() { echo -e "\033[1;31m[ERR ]\033[0m  $*"; }

# ── Ollama 起動確認 ──────────────────────────
log_info "Ollama の起動を確認中..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    log_warn "Ollama が起動していません。バックグラウンドで起動を試みます..."
    ollama serve > /dev/null 2>&1 &
    OLLAMA_PID=$!

    # 最大15秒待機
    for i in $(seq 1 15); do
        sleep 1
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            log_ok "Ollama が起動しました。"
            break
        fi
        if [ "$i" -eq 15 ]; then
            log_error "Ollama の起動がタイムアウトしました。"
            log_error "'ollama serve' を別ターミナルで起動してから再試行してください。"
            exit 1
        fi
    done
else
    log_ok "Ollama は起動済みです。"
fi

# ── モデルの自動ダウンロード ──────────────────
pull_model_if_missing() {
    local model="$1"
    # ollama list の出力にモデル名が含まれているか確認
    if ollama list 2>/dev/null | grep -q "^${model}"; then
        log_ok "モデル '${model}' はダウンロード済みです。スキップします。"
    else
        log_info "モデル '${model}' をダウンロード中... (初回のみ・数分かかります)"
        if ollama pull "${model}"; then
            log_ok "モデル '${model}' のダウンロードが完了しました。"
        else
            log_error "モデル '${model}' のダウンロードに失敗しました。"
            log_error "ネットワーク接続を確認して再試行してください。"
            exit 1
        fi
    fi
}

pull_model_if_missing "$CHAT_MODEL"
pull_model_if_missing "$EMBED_MODEL"

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
    # このスクリプトで Ollama を起動した場合のみ停止する
    if [ -n "${OLLAMA_PID:-}" ]; then
        kill $OLLAMA_PID 2>/dev/null || true
    fi
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
