import { apiUrl, httpClient } from '../../lib/httpClient'
import type { LoginPayload, RegisterPayload, UserPublic } from './types'

export const authApi = {
  register: (payload: RegisterPayload) =>
    httpClient.post<UserPublic>('/auth/register', payload),
  login: (payload: LoginPayload) =>
    httpClient.post<UserPublic>('/auth/login', payload),
  logout: () => httpClient.post<void>('/auth/logout'),
  fetchMe: () => httpClient.get<UserPublic>('/auth/me'),
  googleLoginUrl: () => apiUrl('/auth/google/login'),
}
