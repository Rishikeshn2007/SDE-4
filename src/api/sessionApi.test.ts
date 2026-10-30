import { describe, it, expect } from 'vitest'
import { getMockSession } from './sessionApi'

describe('getMockSession', () => {
  it('returns a successful mock session', async () => {
    const session = await getMockSession()

    expect(session.status).toBe('success')
    expect(session.sessionId).toBe('mock-session-001')
    expect(session.events.length).toBeGreaterThan(0)
  })

  it('returns events in timestamp order', async () => {
    const session = await getMockSession()

    const timestamps = session.events.map(
      (event) => event.timestamp
    )

    expect(timestamps).toEqual(
      [...timestamps].sort()
    )
  })
})