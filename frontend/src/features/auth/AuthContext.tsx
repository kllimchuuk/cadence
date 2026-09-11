import { useEffect, useState, type ReactNode } from 'react'
import { authApi } from './api'
import { AuthContext, type AuthStatus } from './context'
import type { LoginPayload, RegisterPayload, UserPublic } from './types'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')

  useEffect(() => {
    authApi
      .fetchMe()
      .then((currentUser) => {
        setUser(currentUser)
        setStatus('authenticated')
      })
      .catch(() => {
        setStatus('anonymous')
      })
  }, [])

  async function login(payload: LoginPayload) {
    const loggedInUser = await authApi.login(payload)
    setUser(loggedInUser)
    setStatus('authenticated')
  }

  async function register(payload: RegisterPayload) {
    const registeredUser = await authApi.register(payload)
    setUser(registeredUser)
    setStatus('authenticated')
  }

  async function logout() {
    await authApi.logout()
    setUser(null)
    setStatus('anonymous')
  }

  return (
    <AuthContext.Provider value={{ user, status, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
