"""
startup/page_config.py
----------------------
ページ設定（st.set_page_config）と
CSS / JS インジェクションを担う。

呼び出し順の制約:
  st.set_page_config() は Streamlit スクリプトの最初の st.* 呼び出しで
  なければならない。このモジュールを他の st.* より先に import すること。
"""

import streamlit as st


def configure_page() -> None:
    """ページタイトル・レイアウト設定と CSS/JS を注入する。"""
    st.set_page_config(page_title="就活インタビューAI", layout="centered")
    _inject_styles()


def _inject_styles() -> None:
    """グローバル CSS とエラーオーバーレイ JS を埋め込む。"""
    st.markdown(
        """
    <style>
    /* 1. 全体の文字描画をくっきりシャープにする設定（ぼやけ防止） */
    html, body, [data-testid="stAppViewContainer"] {
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        text-rendering: optimizeLegibility;
    }
    h1, h2, h3, h4, h5, h6, span, p {
        font-smooth: always;
    }

    /* 2. スマホ（画面幅が狭い端末）向けのレスポンシブ調整 */
    @media (max-width: 640px) {
        h1 {
            font-size: 1.8rem !important;
            line-height: 1.3 !important;
        }
        h2 {
            font-size: 1.4rem !important;
        }
        [data-testid="stHorizontalBlock"] {
            gap: 4px !important;
        }
        .stButton button {
            padding: 4px 8px !important;
            font-size: 13px !important;
        }
    }

    /* 3. 接続エラーオーバーレイ（JS で動的に追加される） */
    #custom-connection-error {
        display: none;
        position: fixed;
        inset: 0;
        z-index: 99999;
        background: rgba(15, 15, 15, 0.82);
        backdrop-filter: blur(4px);
        -webkit-backdrop-filter: blur(4px);
        align-items: center;
        justify-content: center;
    }
    #custom-connection-error.visible {
        display: flex;
    }
    #custom-connection-error .box {
        background: #1e1e2e;
        border: 1px solid #3a3a5c;
        border-radius: 16px;
        padding: 40px 48px;
        max-width: 420px;
        width: 90%;
        text-align: center;
        box-shadow: 0 24px 64px rgba(0,0,0,0.5);
        color: #e0e0f0;
        font-family: sans-serif;
    }
    #custom-connection-error .icon { font-size: 48px; margin-bottom: 16px; }
    #custom-connection-error h2 {
        font-size: 20px; font-weight: 600; margin: 0 0 12px; color: #ffffff;
    }
    #custom-connection-error p {
        font-size: 14px; line-height: 1.7; color: #a0a0c0; margin: 0 0 28px;
    }
    #custom-connection-error .reload-btn {
        display: inline-block; background: #5b5bd6; color: #fff;
        border: none; border-radius: 8px; padding: 12px 32px;
        font-size: 15px; font-weight: 600; cursor: pointer;
        text-decoration: none; transition: background 0.2s;
    }
    #custom-connection-error .reload-btn:hover { background: #4747c2; }
    </style>

    <!-- 接続エラー表示オーバーレイ -->
    <div id="custom-connection-error">
        <div class="box">
            <div class="icon">🔌</div>
            <h2>アプリへの接続が切れました</h2>
            <p>
                アプリが停止しているか、通信が途切れた可能性があります。<br>
                アプリを再起動してからページを再読み込みしてください。
            </p>
            <button class="reload-btn" onclick="location.reload()">ページを再読み込み</button>
        </div>
    </div>

    <script>
    (function () {
        // Streamlit の英語エラーダイアログを検知して日本語オーバーレイに差し替える
        const overlay = document.getElementById('custom-connection-error');
        const observer = new MutationObserver(() => {
            const dialogs = document.querySelectorAll('[role="dialog"]');
            let found = false;
            dialogs.forEach(dialog => {
                if (dialog.innerText && dialog.innerText.includes('Connection error')) {
                    dialog.style.display = 'none';
                    found = true;
                }
            });
            if (found) {
                overlay.classList.add('visible');
            } else if (overlay.classList.contains('visible')) {
                overlay.classList.remove('visible');
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });
    })();
    </script>
    """,
        unsafe_allow_html=True,
    )
