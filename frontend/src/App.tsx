import { Navigate, Route, Routes } from 'react-router-dom'
import { Landing } from './pages/Landing'
import { Workspace } from './pages/Workspace'

/**
 * Two pages. `/` is the signed-out landing (it forwards a signed-in visitor to `/app`).
 * `/app` is the signed-in workspace with Documents, Graph (`/app/graph`) and Ask
 * (`/app/ask`). Any other path goes back to `/`.
 */
function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/app/*" element={<Workspace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
