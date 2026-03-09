import { HashRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from '@/components/ui/sonner'
import { AppShell } from './components/layout/AppShell'
import { MainPage } from './pages/MainPage'
import { GlossaryReviewPage } from './pages/GlossaryReviewPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return (
    <HashRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<MainPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/jobs/:id/review/glossary" element={<GlossaryReviewPage />} />
        </Routes>
      </AppShell>
      <Toaster />
    </HashRouter>
  )
}
