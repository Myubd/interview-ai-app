import { Routes, Route } from 'react-router-dom'
import { Sidebar } from '@/components/Sidebar'
import { HomePage } from '@/pages/HomePage'
import { MockInterviewPage } from '@/pages/MockInterviewPage'
import { HistoryPage } from '@/pages/HistoryPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { KnowledgePage } from '@/pages/KnowledgePage'
import { SettingsPage } from '@/pages/SettingsPage'

export default function App() {
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
          <Route path="/settings"       element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}
