import { Routes, Route } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'

// Placeholder pages — implemented in STEP 11-12
const Analytics = () => (
  <div className="p-8 text-drs-muted font-sans">Analytics — STEP 11</div>
)
const SettingsPage = () => (
  <div className="p-8 text-drs-muted font-sans">Settings — STEP 12</div>
)

export default function App() {
  return (
    <Routes>
      <Route path="/analytics" element={<Analytics />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/*" element={<AppShell />} />
    </Routes>
  )
}
