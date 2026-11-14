
import { afterEach, describe, it, expect, vi } from 'vitest'
import {
  getMockSession,
  subscribeToMockEvents,
} from './sessionApi'

afterEach(() => {
  vi.useRealTimers()
})

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
      (event) => event.timestamp,
    )

    expect(timestamps).toEqual([...timestamps].sort())
  })
})

describe('subscribeToMockEvents', () => {
  it('delivers events one at a time in order', async () => {
    vi.useFakeTimers()

    const receivedIds: number[] = []

    const subscription = subscribeToMockEvents({
      intervalMs: 1000,
      onEvent: (event) => receivedIds.push(event.id),
    })

    await vi.advanceTimersByTimeAsync(3000)

    expect(receivedIds).toEqual([1, 2, 3])

    subscription.close()
  })

  it('replays only events after the last received event ID', async () => {
    vi.useFakeTimers()

    const receivedIds: number[] = []

    const subscription = subscribeToMockEvents({
      afterEventId: 2,
      intervalMs: 1000,
      onEvent: (event) => receivedIds.push(event.id),
    })

    await vi.advanceTimersByTimeAsync(2000)

    expect(receivedIds).toEqual([3, 4])

    subscription.close()
  })

  it('stops delivering events after close', async () => {
    vi.useFakeTimers()

    const receivedIds: number[] = []

    const subscription = subscribeToMockEvents({
      intervalMs: 1000,
      onEvent: (event) => receivedIds.push(event.id),
    })

    await vi.advanceTimersByTimeAsync(1000)
    subscription.close()
    await vi.advanceTimersByTimeAsync(3000)

    expect(receivedIds).toEqual([1])
  })
})
