import { useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Sidebar } from '@/components/Sidebar'
import { HomePage } from '@/pages/HomePage'
import { MockInterviewPage } from '@/pages/MockInterviewPage'
import { HistoryPage } from '@/pages/HistoryPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { KnowledgePage } from '@/pages/KnowledgePage'
import { PredictedQuestionsPage } from '@/pages/PredictedQuestionsPage'
import { InterviewPage } from '@/pages/InterviewPage'
import { PersonalityPage } from '@/pages/PersonalityPage'
import { CompanyMatrixPage } from '@/pages/CompanyMatrixPage'
import { CareerAdvisorPage } from '@/pages/CareerAdvisorPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { SetupProgressPage } from '@/pages/SetupProgressPage'

export default function App() {
  const [setupReady, setSetupReady] = useState(false)

  if (!setupReady) {
    return <SetupProgressPage onComplete={() => setSetupReady(true)} />
  }

  return (
    <div className="flex min-h-screen bg-surface-50 font-sans">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/"               element={<HomePage />} />
          <Route path="/mock-interview" element={<MockInterviewPage />} />
          <Route path="/history"        element={<HistoryPage />} />
          <Route path="/dashboard"      element={<DashboardPage />} />
          <Route path="/knowledge"      element={<KnowledgePage />} />
          <Route path="/predicted-questions" element={<PredictedQuestionsPage />} />
          <Route path="/interview" element={<InterviewPage />} />
          <Route path="/personality" element={<PersonalityPage />} />
          <Route path="/company-matrix" element={<CompanyMatrixPage />} />
          <Route path="/career-advisor" element={<CareerAdvisorPage />} />
          <Route path="/settings"       element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}
