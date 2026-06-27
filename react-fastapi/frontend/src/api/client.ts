/**
 * api/client.ts
 * バックエンド REST API への型付きラッパー。
 * SSE は useMockInterview hook で直接 fetch する。
 */

const BASE = '/api/v1'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `HTTP ${res.status}`)
  }
  // 204 No Content
  if (res.status === 204) return undefined as unknown as T
  return res.json() as Promise<T>
}

// ── 型定義 ───────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok' | 'degraded'
  ollama: boolean
  models: string[]
}

/** list_sessions() が返すメタ情報 */
export interface SessionMeta {
  id: number
  company_name: string | null
  session_type: string | null
  status: string | null
  interview_complete: number   // SQLite の 0/1
  has_mock_evaluation: number
  created_at: string
  updated_at: string
}

/** get_session() が返す詳細（{session, messages}） */
export interface SessionDetail {
  session: Record<string, unknown>
  messages: Message[]
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  theme_index?: number | null
}

export interface MockEvaluation {
  overall_score: number
  axes: Record<string, number>
  strengths: string[]
  improvements: string[]
  next_steps: string[]
  ok: boolean
}

export interface KnowledgeBase {
  id: number
  name: string
  kb_type: 'resume' | 'company'
  is_active: boolean | number
  created_at: string
}

export interface PersonaInfo {
  key: string
  name: string
  description: string
}

export interface ThemeInfo {
  index: number
  key: string
  title: string
}

/** 設定キー名は既存 DB に合わせて chat_model / embed_model */
export interface AppSettings {
  chat_model: string
  embed_model: string
  ollama_host: string
}

// ── Health ───────────────────────────────────────────────────

export const apiHealth = (): Promise<HealthResponse> =>
  request('/health')

// ── Sessions ─────────────────────────────────────────────────

export const apiGetSessions = (): Promise<SessionMeta[]> =>
  request('/sessions/')

export const apiGetSession = (id: number): Promise<SessionDetail> =>
  request(`/sessions/${id}`)

export const apiCreateSession = (data: {
  company_name?: string
  profile_text?: string
  session_type?: string
}): Promise<{ id: number }> =>
  request('/sessions/', { method: 'POST', body: JSON.stringify(data) })

export const apiUpdateSession = (id: number, data: Record<string, unknown>): Promise<SessionDetail> =>
  request(`/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(data) })

export const apiDeleteSession = (id: number): Promise<void> =>
  request(`/sessions/${id}`, { method: 'DELETE' })

export const apiExportSession = (id: number): Promise<SessionDetail> =>
  request(`/sessions/${id}/export`)

export const apiImportSession = (data: Record<string, unknown>): Promise<{ id: number }> =>
  request('/sessions/import', { method: 'POST', body: JSON.stringify({ data }) })

// ── Knowledge Bases ──────────────────────────────────────────

export const apiGetKnowledgeBases = (kb_type?: 'resume' | 'company'): Promise<KnowledgeBase[]> =>
  request(`/knowledge-bases/${kb_type ? `?kb_type=${kb_type}` : ''}`)

export const apiCreateKnowledgeBaseText = (data: {
  name: string
  kb_type: string
  text: string
}): Promise<KnowledgeBase> =>
  request('/knowledge-bases/text', { method: 'POST', body: JSON.stringify(data) })

export const apiCreateKnowledgeBaseUpload = async (form: FormData): Promise<KnowledgeBase> => {
  const res = await fetch(`${BASE}/knowledge-bases/upload`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export const apiDeleteKnowledgeBase = (id: number): Promise<void> =>
  request(`/knowledge-bases/${id}`, { method: 'DELETE' })

export const apiToggleKnowledgeBaseActive = (id: number, is_active: boolean): Promise<KnowledgeBase> =>
  request(`/knowledge-bases/${id}/active`, {
    method: 'PATCH',
    body: JSON.stringify({ is_active }),
  })

// ── Mock Interview ────────────────────────────────────────────

export const apiGetPersonas = (): Promise<PersonaInfo[]> =>
  request('/mock-interview/personas')

export const apiGetThemes = (industry_key = 'general'): Promise<ThemeInfo[]> =>
  request(`/mock-interview/themes?industry_key=${industry_key}`)

export const apiStartMockInterview = (data: {
  industry_key: string
  persona_key: string
  profile_text: string
  rag_block?: string
  predicted_questions?: unknown[]
}): Promise<{ theme_index: number; theme_title: string; question: string }> =>
  request('/mock-interview/start', { method: 'POST', body: JSON.stringify(data) })

export const apiEvaluateMockInterview = (data: {
  messages: Message[]
  industry_key: string
  profile_text: string
  rag_block?: string
}): Promise<MockEvaluation> =>
  request('/mock-interview/evaluate', { method: 'POST', body: JSON.stringify(data) })

// ── Settings ──────────────────────────────────────────────────

export const apiGetSettings = (): Promise<AppSettings> =>
  request('/settings/')

export const apiUpdateSettings = (data: Partial<AppSettings>): Promise<AppSettings> =>
  request('/settings/', { method: 'PATCH', body: JSON.stringify(data) })
