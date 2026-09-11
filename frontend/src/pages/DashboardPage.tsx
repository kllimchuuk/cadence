import { Button } from '@/components/ui/button'
import { useAuth } from '../features/auth/useAuth'

export function DashboardPage() {
  const { user, logout } = useAuth()

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4 p-4">
      <h1 className="text-2xl font-medium">Welcome, {user?.nickname}</h1>
      <Button variant="outline" onClick={() => logout()}>
        Log out
      </Button>
    </main>
  )
}
