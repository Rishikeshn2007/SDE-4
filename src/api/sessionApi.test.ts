
import { afterEach, describe, it, expect, vi } from 'vitest'
import {
  getMockSession,
  subscribeToMockEvents,
  subscribeToBackendEvents,
  type BackendEvent,
} from './sessionApi'

function createSseResponse(events: BackendEvent[]) {
  const encoder = new TextEncoder()

  const body = new ReadableStream({
    start(controller) {
      for (const event of events) {
        controller.enqueue(
          encoder.encode(
            `id: ${event.id}\nevent: ${event.event_type}\ndata: ${JSON.stringify(event)}\n\n`,
          ),
        )
      }

      controller.close()
    },
  })

  return new Response(body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
    },
  })
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
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

describe('subscribeToBackendEvents', () => {
  it('receives backend events and sends the Last-Event-ID header', async () => {
    const backendEvent: BackendEvent = {
      id: 3,
      session_id: 'test-session',
      event_type: 'gateway_processed',
      data: { status: 'success' },
      timestamp: '2026-11-18T09:00:00',
    }

    const fetchMock = vi.fn().mockResolvedValue(
      createSseResponse([backendEvent]),
    )

    vi.stubGlobal('fetch', fetchMock)

    const receivedEvent = new Promise<BackendEvent>((resolve) => {
      const subscription = subscribeToBackendEvents(
        'test-session',
        {
          afterEventId: 2,
          onEvent: (event) => {
            resolve(event)
            subscription.close()
          },
        },
      )
    })

    await expect(receivedEvent).resolves.toEqual(backendEvent)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/sessions/test-session/events',
      expect.objectContaining({
        headers: {
          'Last-Event-ID': '2',
          Accept: 'text/event-stream',
        },
      }),
    )
  })
    it('reconnects using the latest event ID and receives only new events', async () => {
    vi.useFakeTimers()

    const event1: BackendEvent = {
      id: 1,
      session_id: 'test-session',
      event_type: 'session_created',
      data: {},
      timestamp: '2026-11-18T09:00:00',
    }

    const event2: BackendEvent = {
      id: 2,
      session_id: 'test-session',
      event_type: 'gateway_processed',
      data: {},
      timestamp: '2026-11-18T09:00:01',
    }

    const event3: BackendEvent = {
      id: 3,
      session_id: 'test-session',
      event_type: 'gateway_processed',
      data: {},
      timestamp: '2026-11-18T09:00:02',
    }

    const fetchMock = vi.fn()
      .mockResolvedValueOnce(createSseResponse([event1, event2]))
      .mockResolvedValueOnce(createSseResponse([event3]))

    vi.stubGlobal('fetch', fetchMock)

    const receivedIds: number[] = []

    let subscription: ReturnType<typeof subscribeToBackendEvents>

    let resolveThirdEvent!: () => void

    const thirdEventReceived = new Promise<void>((resolve) => {
      resolveThirdEvent = resolve
    })

    subscription = subscribeToBackendEvents('test-session', {
      onEvent: (event) => {
        receivedIds.push(event.id)

        if (event.id === 3) {
          resolveThirdEvent()
          subscription.close()
        }
      },
    })

    await vi.waitFor(() => {
      expect(receivedIds).toEqual([1, 2])
    })

    await vi.advanceTimersByTimeAsync(1000)

    await thirdEventReceived

    expect(receivedIds).toEqual([1, 2, 3])
    expect(fetchMock).toHaveBeenCalledTimes(2)

    expect(fetchMock.mock.calls[1][1]).toEqual(
      expect.objectContaining({
        headers: {
          'Last-Event-ID': '2',
          Accept: 'text/event-stream',
        },
      }),
    )
  })
})
