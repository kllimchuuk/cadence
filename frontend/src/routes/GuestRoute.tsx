import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../features/auth/useAuth'

export function GuestRoute() {
  const { status } = useAuth()

  if (status === 'authenticated') {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
