import { Link, Route, Routes } from 'react-router-dom'
import { Shell } from './components/Layout'
import { Home } from './pages/Home'
import { Workspace } from './pages/Workspace'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/r/:repoId" element={<Workspace />} />
      <Route
        path="*"
        element={
          <Shell>
            <p className="muted">
              Page not found. <Link to="/">Back to repositories</Link>
            </p>
          </Shell>
        }
      />
    </Routes>
  )
}
