import { HashRouter, Routes, Route } from 'react-router-dom'
import { MainPage } from './pages/MainPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<MainPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </HashRouter>
  )
}
