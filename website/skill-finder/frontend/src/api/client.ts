import axios, { AxiosError, type AxiosInstance } from 'axios'

export class ApiError extends Error {
  status: number | null
  userMessage: string
  cancelled: boolean

  constructor(status: number | null, userMessage: string, cancelled = false) {
    super(userMessage)
    this.name = 'ApiError'
    this.status = status
    this.userMessage = userMessage
    this.cancelled = cancelled
  }
}

function isAxiosError(err: unknown): err is AxiosError {
  return typeof err === 'object' && err !== null && (err as AxiosError).isAxiosError === true
}

export function fromAxiosError(err: unknown): ApiError {
  if (isAxiosError(err)) {
    if (err.code === 'ERR_CANCELED') {
      return new ApiError(null, '请求已取消', true)
    }
    if (err.response) {
      const status = err.response.status
      if (status >= 500) {
        return new ApiError(status, '服务器开小差了，请稍后重试')
      }
      const data = err.response.data as { message?: string } | undefined
      const message = data?.message
      if (message && status >= 400 && status < 500) {
        return new ApiError(status, message)
      }
      return new ApiError(status, '请求失败，请稍后重试')
    }
    return new ApiError(null, '网络连接失败，请检查网络')
  }
  return new ApiError(null, '发生未知错误')
}

export const http: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
})
