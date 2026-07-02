/**
 * utils/errorMessages.ts
 *
 * fetch/SSE などから投げられる生の例外を、ユーザー向けの
 * 分かりやすい日本語メッセージに変換する。
 *
 * 目的:
 *  - 「TypeError: Failed to fetch」のような技術的な英語の文言が
 *    そのまま画面に出ないようにする（Ollama未接続時の丁寧な文言と
 *    トーンを揃える）。
 *  - 原因の切り分けに役立つよう、状況ごとにメッセージを出し分ける。
 */

export interface FriendlyError {
  /** 画面に表示する短い日本語メッセージ */
  message: string
  /** ユーザーが取れる次のアクションのヒント（任意） */
  hint?: string
  /** リトライ（再送信）が意味を持つ種類のエラーかどうか */
  retryable: boolean
}

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError'
}

function isNetworkError(err: unknown): boolean {
  // ブラウザの fetch が接続確立前に失敗すると TypeError になる
  // (例: "Failed to fetch" / "NetworkError when attempting to fetch resource")
  return err instanceof TypeError
}

function isTimeoutLike(text: string): boolean {
  return /timeout|timed out|ETIMEDOUT/i.test(text)
}

function isHttpStatusError(text: string): number | null {
  const m = text.match(/HTTP (\d{3})/)
  return m ? Number(m[1]) : null
}

/**
 * 例外オブジェクトや HTTP レスポンスの文字列表現を受け取り、
 * ユーザー向けの日本語メッセージに変換する。
 */
export function toFriendlyError(err: unknown): FriendlyError {
  if (isAbortError(err)) {
    return {
      message: '通信を中断しました。',
      retryable: false,
    }
  }

  const raw = err instanceof Error ? err.message : String(err)

  if (isNetworkError(err)) {
    return {
      message: 'サーバーとの通信に失敗しました。',
      hint: 'ネットワーク接続、またはバックエンドが起動しているかをご確認のうえ、再送信してください。',
      retryable: true,
    }
  }

  if (isTimeoutLike(raw)) {
    return {
      message: 'AIモデルからの応答がタイムアウトしました。',
      hint: 'ローカルLLMは端末の性能によって応答に時間がかかることがあります。もう一度お試しください。',
      retryable: true,
    }
  }

  const status = isHttpStatusError(raw)
  if (status != null) {
    if (status === 503 || status === 502 || status === 504) {
      return {
        message: 'Ollama（AIモデル）に接続できませんでした。',
        hint: 'Ollama が起動しているかご確認のうえ、再送信してください。',
        retryable: true,
      }
    }
    if (status >= 500) {
      return {
        message: 'サーバー側でエラーが発生しました。',
        hint: 'しばらく待ってから再送信してください。',
        retryable: true,
      }
    }
    if (status === 404) {
      return {
        message: 'セッション情報が見つかりませんでした。',
        retryable: false,
      }
    }
    if (status >= 400) {
      return {
        message: 'リクエストの内容に問題があります。',
        retryable: false,
      }
    }
  }

  // それ以外の未分類のエラー。生の文字列は出さず、丁寧な文言に留める。
  return {
    message: '予期しないエラーが発生しました。',
    hint: '時間を置いて再送信するか、解決しない場合は最初からやり直してください。',
    retryable: true,
  }
}
