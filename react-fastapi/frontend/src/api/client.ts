/**
 * api/client.ts
 * バックエンド REST API への型付きラッパー。
 * SSE は useMockInterview hook と useSetupProgress hook で直接 fetch する。
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
  if (res.status === 204) return undefined as unknown as T
  return res.json() as Promise<T>
}

/** undefined を除外してクエリ文字列を組み立てる（数値・文字列どちらの値もOK）。 */
function qs(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined) as [string, string | number][]
  return new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString()
}

// ── 型定義 ───────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok' | 'degraded'
  ollama: boolean
  models: string[]
}

export interface VersionResponse {
  version: string
}

export interface SetupStatus {
  done: boolean
  error: boolean
}

export interface SetupLogEntry {
  level: 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR'
  message: string
  ts: string
  group?: string | null
}

/** list_sessions() が返すメタ情報 */
export interface SessionMeta {
  id: number
  company_name: string | null
  session_type: string | null
  status: string | null
  interview_complete: number
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
  overall_summary?: string
  model_answers?: { question: string; model_answer: string }[]
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

export interface ScoreTrendEntry {
  session_id: number
  company_name: string | null
  created_at: string
  overall_score: number
  axes: Record<string, number>
}

export interface DashboardData {
  total_sessions: number
  evaluated_sessions: number
  avg_overall_score: number
  best_overall_score: number
  score_trend: ScoreTrendEntry[]
  axes_avg: Record<string, number>
  axes_keys: string[]
}

// ── Health ───────────────────────────────────────────────────

export const apiHealth = (): Promise<HealthResponse> =>
  request('/health')

// ── Version ──────────────────────────────────────────────────

export const apiGetVersion = (): Promise<VersionResponse> =>
  request('/version')

// ── Setup ────────────────────────────────────────────────────

export const apiGetSetupStatus = (): Promise<SetupStatus> =>
  request('/setup/status')

/**
 * Ollama セットアップ進捗を SSE でストリーミング受信する。
 *
 * @param onLog     ログ行を受け取るコールバック
 * @param onDone    完了時のコールバック
 * @param onError   エラー時のコールバック
 * @returns         接続を閉じる関数
 */
export function subscribeSetupProgress(
  onLog: (entry: SetupLogEntry) => void,
  onDone: () => void,
  onError: () => void,
): () => void {
  let es: EventSource | null = null
  let closed = false
  let retryCount = 0
  const MAX_RETRIES = 20      // 最大20回リトライ（≒10秒）
  const RETRY_DELAY_MS = 500  // 500ms間隔

  function connect() {
    if (closed) return

    es = new EventSource(`${BASE}/setup/progress`)

    es.addEventListener('log', (e: MessageEvent) => {
      retryCount = 0  // 接続が確立して届いたらリトライカウントをリセット
      try {
        const entry: SetupLogEntry = JSON.parse(e.data)
        onLog(entry)
      } catch {
        // ignore parse errors
      }
    })

    es.addEventListener('done', () => {
      closed = true
      es?.close()
      onDone()
    })

    es.addEventListener('error_event', () => {
      closed = true
      es?.close()
      onError()
    })

    // onerror: サーバー未起動など接続レベルのエラー → リトライ
    es.onerror = () => {
      es?.close()
      es = null
      if (closed) return
      if (retryCount < MAX_RETRIES) {
        retryCount++
        setTimeout(connect, RETRY_DELAY_MS)
      } else {
        // リトライ上限を超えたら本当のエラーとして扱う
        onError()
      }
    }
  }

  connect()

  return () => {
    closed = true
    es?.close()
  }
}

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

export const apiGetDashboard = (): Promise<DashboardData> =>
  request('/sessions/dashboard')

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

// ── Favorites ────────────────────────────────────────────────

export interface Favorite {
  id: number
  item_type: string
  item_id: number | null
  session_id: number | null
  company_name: string | null
  session_type: string | null
  label: string | null
  content_snapshot: unknown
  saved_at: string
}

export interface FavoritesMeta {
  item_type_labels: Record<string, string>
  companies: string[]
  session_types: string[]
  count: number
}

export const apiListFavorites = (params?: {
  item_type?: string
  company_name?: string
  session_type?: string
}): Promise<Favorite[]> => {
  const q = params ? qs(params) : ''
  return request(`/favorites${q ? `?${q}` : ''}`)
}

export const apiGetFavoritesMeta = (): Promise<FavoritesMeta> =>
  request('/favorites/meta')

export const apiIsFavorited = (
  item_type: string,
  params?: { item_id?: number; session_id?: number },
): Promise<{ favorited: boolean; favorite_id: number | null }> =>
  request(`/favorites/is-favorited?${qs({ item_type, ...params })}`)

export const apiCreateFavorite = (data: {
  item_type: string
  item_id?: number
  session_id?: number
  company_name?: string
  session_type?: string
  label?: string
  content_snapshot?: unknown
}): Promise<{ id: number }> =>
  request('/favorites', { method: 'POST', body: JSON.stringify(data) })

export const apiDeleteFavorite = (favoriteId: number): Promise<void> =>
  request(`/favorites/${favoriteId}`, { method: 'DELETE' })

export const apiDeleteFavoriteByItem = (
  item_type: string,
  params?: { item_id?: number; session_id?: number },
): Promise<void> =>
  request(`/favorites/by-item?${qs({ item_type, ...params })}`, { method: 'DELETE' })

// ── Predicted Questions ─────────────────────────────────────────

export interface PredictedQuestion {
  category: string
  category_label: string
  question: string
  model_answer: string
}

export const apiGeneratePredictedQuestions = (
  company_kb_id: number,
): Promise<{ questions: PredictedQuestion[] }> =>
  request('/predicted-questions/generate', {
    method: 'POST',
    body: JSON.stringify({ company_kb_id }),
  })

export const apiSavePredictedQuestionsAndFavorite = (data: {
  company_kb_id: number
  company_name: string
  questions: PredictedQuestion[]
}): Promise<{ session_id: number; favorite_id: number }> =>
  request('/predicted-questions/save-and-favorite', {
    method: 'POST',
    body: JSON.stringify(data),
  })

/** 想定質問（自己PR＋会話履歴ベース版）。動的インタビューフローの⑥から使う。 */
export const apiGeneratePredictedQuestionsFromPr = (data: {
  pr_text: string
  profile_text?: string
  messages?: Message[]
}): Promise<{ questions: PredictedQuestion[] }> =>
  request('/predicted-questions/generate-from-pr', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const apiSavePredictedQuestionsPrBased = (data: {
  questions: PredictedQuestion[]
  company_name?: string | null
}): Promise<{ session_id: number; favorite_id: number }> =>
  request('/predicted-questions/save-and-favorite-pr-based', {
    method: 'POST',
    body: JSON.stringify(data),
  })

// ── Interview（自己PR引き出しインタビュー）───────────────────────
// streamlit版 page_modules/interview/ 一式に相当。

export interface InterviewQuestionResponse {
  status: 'question' | 'awaiting_category_choice' | 'complete'
  theme_index: number
  theme_title: string
  question: string
  questions_asked_in_theme: number
  category_options: string[]
}

export const apiInterviewStart = (profile_text: string): Promise<InterviewQuestionResponse> =>
  request('/interview/start', { method: 'POST', body: JSON.stringify({ profile_text }) })

export const apiInterviewNext = (data: {
  theme_index: number
  theme_messages: Message[]
  questions_asked_in_theme: number
  selected_category?: string | null
  profile_text?: string
  messages?: Message[]
}): Promise<InterviewQuestionResponse> =>
  request('/interview/next', { method: 'POST', body: JSON.stringify(data) })

export const apiInterviewChooseCategory = (data: {
  theme_index: number
  category: string
  profile_text?: string
  messages?: Message[]
}): Promise<InterviewQuestionResponse> =>
  request('/interview/choose-category', { method: 'POST', body: JSON.stringify(data) })

export interface InterviewSummary {
  ok: boolean
  strengths: { point: string; evidence?: string }[]
  weaknesses: { point: string; evidence?: string }[]
  fit_roles: string
  industry_fit: Record<string, { score: number; reason: string }>
  overall_comment: string
  error_msg?: string | null
}

export const apiInterviewSummary = (data: {
  profile_text?: string
  messages: Message[]
}): Promise<InterviewSummary> =>
  request('/interview/summary', { method: 'POST', body: JSON.stringify(data) })

export interface PrVariant {
  type: string
  label: string
  content: string
}

export const apiInterviewPrVariants = (data: {
  profile_text?: string
  messages: Message[]
}): Promise<PrVariant[]> =>
  request('/interview/pr/variants', { method: 'POST', body: JSON.stringify(data) })

export interface PrEvaluation {
  scores: Record<string, number>
  summary: string
  improvements: string[]
}

export const apiInterviewPrEvaluate = (pr_text: string): Promise<PrEvaluation> =>
  request('/interview/pr/evaluate', { method: 'POST', body: JSON.stringify({ pr_text }) })

export interface PrRefineResult {
  pr_text: string
  ok: boolean
  error_msg?: string | null
}

export const apiInterviewPrRefine = (data: {
  pr_text: string
  instruction: string
  profile_text?: string
  messages?: Message[]
}): Promise<PrRefineResult> =>
  request('/interview/pr/refine', { method: 'POST', body: JSON.stringify(data) })

export const apiInterviewRefinePresets = (): Promise<Record<string, string>> =>
  request('/interview/pr/refine-presets')

export interface CompanyPrResult {
  company_name: string
  pr_text: string
  points: string[]
  ok: boolean
  error_msg?: string | null
}

export const apiInterviewCompanyPrs = (data: {
  base_pr: string
  companies: { name: string; info: string }[]
  profile_text?: string
  messages?: Message[]
}): Promise<CompanyPrResult[]> =>
  request('/interview/pr/company', { method: 'POST', body: JSON.stringify(data) })

// ── Personality（性格診断・適性検査）─────────────────────────────
// streamlit版 page_modules/personality_page.py が相当する。

export interface PersonalityQuestion {
  id: number
  axis: string
  text: string
  reverse: boolean
}

export interface PersonalityQuestionsResponse {
  axes: Record<string, string>
  questions: PersonalityQuestion[]
  scale_labels: Record<number, string>
  total_questions: number
}

export const apiGetPersonalityQuestions = (): Promise<PersonalityQuestionsResponse> =>
  request('/personality/questions')

export interface PersonalityStrength { point: string; detail?: string }
export interface PersonalityCaution { point: string; hint?: string }
export interface PersonalityRole { role: string; score: number }
export interface PersonalityIndustryFitEntry { score: number; reason?: string }

export interface PersonalityResult {
  axis_scores: Record<string, number>
  consistency_score: number
  personality_summary: string
  strengths: PersonalityStrength[]
  cautions: PersonalityCaution[]
  fit_environments: string
  industry_fit: Record<string, PersonalityIndustryFitEntry>
  recommended_roles: PersonalityRole[]
  interview_strengths: string[]
  interview_risks: string[]
  interview_tips: string
}

export const apiSubmitPersonality = (
  answers: Record<number, number>,
): Promise<PersonalityResult> =>
  request('/personality/submit', { method: 'POST', body: JSON.stringify({ answers }) })

export const apiSavePersonalityAndFavorite = (data: {
  answers: Record<number, number>
  axis_scores: Record<string, number>
  result: PersonalityResult
  session_id?: number | null
  company_name?: string | null
}): Promise<{ session_id: number; favorite_id: number }> =>
  request('/personality/save-and-favorite', { method: 'POST', body: JSON.stringify(data) })

// ── Company Matrix（企業比較マトリクス）─────────────────────────
// streamlit版 page_modules/company_matrix_page.py が相当する。

export interface CompanyMatrixConstants {
  max_companies: number
  matrix_axes_fixed: string[]
  value_fit_axis_key: string
  value_fit_note: string
}

export const apiGetCompanyMatrixConstants = (): Promise<CompanyMatrixConstants> =>
  request('/company-matrix/constants')

export const apiGetCompanyMatrixCompanies = (): Promise<KnowledgeBase[]> =>
  request('/company-matrix/companies')

export interface MotivationResult {
  company_name: string
  motivation_text: string
  key_points: string[]
  ok: boolean
  error_msg?: string | null
}

export const apiGenerateMotivations = (data: {
  company_kb_ids: number[]
  pr_text?: string
  profile_text?: string
  messages?: Message[]
}): Promise<MotivationResult[]> =>
  request('/company-matrix/motivations', { method: 'POST', body: JSON.stringify(data) })

export interface MatrixCell { score: number; comment: string }

export interface MatrixResult {
  axes: string[]
  companies: string[]
  matrix: Record<string, Record<string, MatrixCell>>
  overall_recommendation: string
  ok: boolean
  error_msg?: string | null
}

export const apiGenerateMatrix = (data: {
  company_kb_ids: number[]
  pr_text?: string
  additional_axes?: string[]
}): Promise<MatrixResult> =>
  request('/company-matrix/matrix', { method: 'POST', body: JSON.stringify(data) })

export const apiExportMatrixCsv = async (result: MatrixResult): Promise<string> => {
  const res = await fetch(`${BASE}/company-matrix/matrix/export-csv`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(result),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.text()
}

export interface Differentiator { point: string; vs_others?: string }

export interface WhyNotResult {
  target_name: string
  differentiators: Differentiator[]
  answer_template: string
  ok: boolean
  error_msg?: string | null
}

export const apiGenerateWhyNotOthers = (data: {
  target_kb_id: number
  other_kb_ids: number[]
  pr_text?: string
  profile_text?: string
  messages?: Message[]
}): Promise<WhyNotResult> =>
  request('/company-matrix/why-not-others', { method: 'POST', body: JSON.stringify(data) })

// ── Career Advisor（AIキャリアアドバイザー）──────────────────────
// streamlit版 page_modules/career_page.py が相当する。

export interface CareerAdvisorSessionSummary {
  id: number
  company_name: string | null
  session_type: string | null
  status: string
  interview_complete: number
  created_at: string
  updated_at: string
  has_mock_evaluation: number
}

export const apiGetCareerAdvisorSessions = (): Promise<CareerAdvisorSessionSummary[]> =>
  request('/career-advisor/sessions')

export const apiCareerAdvisorChat = (data: {
  messages: Message[]
  session_id?: number | null
}): Promise<{ reply: string; ok: boolean; error_msg?: string | null }> =>
  request('/career-advisor/chat', { method: 'POST', body: JSON.stringify(data) })


