import { describe, expect, it } from 'vitest'

import { ApiError, fromAxiosError } from '@/api/client'

describe('ApiError normalization', () => {
  it('maps 422 to ApiError with server message', () => {
    const err = {
      isAxiosError: true,
      response: {
        status: 422,
        data: { message: 'Invalid sort parameter', code: 'VALIDATION_ERROR' },
      },
    }
    const result = fromAxiosError(err)
    expect(result).toBeInstanceOf(ApiError)
    expect((result as ApiError).status).toBe(422)
    expect((result as ApiError).userMessage).toContain('Invalid sort parameter')
  })

  it('maps 500 to generic user message, not raw internals', () => {
    const err = {
      isAxiosError: true,
      response: {
        status: 500,
        data: { message: 'Traceback: secret stack', code: 'INTERNAL_ERROR' },
      },
    }
    const result = fromAxiosError(err)
    expect(result).toBeInstanceOf(ApiError)
    expect((result as ApiError).status).toBe(500)
    expect((result as ApiError).userMessage).not.toContain('Traceback')
  })

  it('maps network error to ApiError with network message', () => {
    const err = { isAxiosError: true, message: 'Network Error', response: undefined }
    const result = fromAxiosError(err)
    expect(result).toBeInstanceOf(ApiError)
    expect((result as ApiError).status).toBeNull()
    expect((result as ApiError).userMessage).toContain('网络')
  })

  it('maps request cancelled to ApiError marked cancelled', () => {
    const err = {
      isAxiosError: true,
      message: 'Request canceled',
      code: 'ERR_CANCELED',
      response: undefined,
    }
    const result = fromAxiosError(err)
    expect(result).toBeInstanceOf(ApiError)
    expect((result as ApiError).cancelled).toBe(true)
  })
})
