import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../features/auth/useAuth'

export function ProtectedRoute() {
  const { status } = useAuth()

  if (status === 'loading') {
    return <p>Loading...</p>
  }

  if (status === 'anonymous') {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
