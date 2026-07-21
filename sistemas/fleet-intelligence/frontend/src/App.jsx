import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import BoardsPage from './pages/Boards'
import BoardView from './pages/BoardView'
import AlertsPage from './pages/Alerts'
import UsersPage from './pages/Users'

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }
  // Se não há user, o AuthContext já redireciona ao Command Center (SSO).
  // Enquanto o redirect acontece, mostra spinner.
  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }
  return children
}

export default function App() {
  return (
    <Routes>
      {/* Login local removido — autenticação exclusivamente via SSO (Command Center) */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/boards" replace />} />
        <Route path="boards" element={<BoardsPage />} />
        <Route path="boards/:boardId" element={<BoardView />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="users" element={<UsersPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
