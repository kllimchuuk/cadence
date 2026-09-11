export interface UserPublic {
  id: string
  email: string
  first_name: string
  last_name: string
  nickname: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface RegisterPayload {
  email: string
  password: string
  first_name: string
  last_name: string
  nickname: string
}
