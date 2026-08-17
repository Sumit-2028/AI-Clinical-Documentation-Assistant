export interface LoginRequest {
  email: string
  password: string
}

export interface RefreshTokenRequest {
  refresh_token: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
}

export interface AuthUser {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
}
