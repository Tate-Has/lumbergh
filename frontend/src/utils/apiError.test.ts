import { describe, it, expect } from 'vitest'
import { errorDetail } from './apiError'

describe('errorDetail', () => {
  it('prefers what the API said over the status code', async () => {
    const res = new Response(
      JSON.stringify({ detail: "This session's directory no longer exists" }),
      {
        status: 404,
      }
    )

    expect(await errorDetail(res)).toBe("This session's directory no longer exists")
  })

  it('falls back to the status when there is no detail to read', async () => {
    expect(await errorDetail(new Response('gateway blew up', { status: 502 }))).toBe('HTTP 502')
    expect(await errorDetail(new Response(JSON.stringify({}), { status: 500 }))).toBe('HTTP 500')
  })

  it('never throws while trying to describe a failure', async () => {
    const hostile = { status: 500, json: () => Promise.reject(new Error('nope')) } as Response

    expect(await errorDetail(hostile)).toBe('HTTP 500')
  })
})
