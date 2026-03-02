// App root — wraps with BrowserRouter.
// AppShell is always rendered; routing is handled inside MainArea.
import { BrowserRouter } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
