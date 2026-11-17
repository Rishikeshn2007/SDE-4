
export type TranscriptEvent = {
  id: number
  segmentId: number
  timestamp: string
  text: string
  status: 'interim' | 'final'
  revision: number
  confidence: number
}

export type SessionResponse = {
  sessionId: string
  status: 'success'
  events: TranscriptEvent[]
}

export type StreamStatus = 'connected' | 'closed'

type MockEventStreamOptions = {
  afterEventId?: number
  intervalMs?: number
  onEvent: (event: TranscriptEvent) => void
  onStatusChange?: (status: StreamStatus) => void
}

const mockEvents: TranscriptEvent[] = [
  {
    id: 1,
    segmentId: 1,
    timestamp: '10:00:01',
    text: 'Welcome to the demo',
    status: 'interim',
    revision: 1,
    confidence: 72,
  },
  {
    id: 2,
    segmentId: 1,
    timestamp: '10:00:02',
    text: 'Welcome to the demo session.',
    status: 'final',
    revision: 2,
    confidence: 96,
  },
  {
    id: 3,
    segmentId: 2,
    timestamp: '10:00:03',
    text: 'The mock transcript is working.',
    status: 'final',
    revision: 1,
    confidence: 94,
  },
  {
    id: 4,
    segmentId: 3,
    timestamp: '10:00:05',
    text: 'Session completed successfully.',
    status: 'final',
    revision: 1,
    confidence: 98,
  },
]

export async function getMockSession(): Promise<SessionResponse> {
  return {
    sessionId: 'mock-session-001',
    status: 'success',
    events: [...mockEvents].sort((a, b) =>
      a.timestamp.localeCompare(b.timestamp),
    ),
  }
}

export function subscribeToMockEvents({
  afterEventId = 0,
  intervalMs = 1000,
  onEvent,
  onStatusChange,
}: MockEventStreamOptions) {
  let lastEventId = afterEventId
  let closed = false

  onStatusChange?.('connected')

  const timer = setInterval(() => {
    if (closed) return

    const nextEvent = mockEvents.find(
      (event) => event.id > lastEventId,
    )

    if (!nextEvent) {
      clearInterval(timer)
      onStatusChange?.('closed')
      return
    }

    lastEventId = nextEvent.id
    onEvent(nextEvent)
  }, intervalMs)

  return {
    close() {
      closed = true
      clearInterval(timer)
      onStatusChange?.('closed')
    },
  }
}

// Backend session API

export type BackendSession = {
  session_id: string
  state: string
  created_at: string
  updated_at: string
}

export type BackendEvent = {
  id: number
  session_id: string
  event_type: string
  data: Record<string, unknown>
  timestamp: string
}

export async function createBackendSession(): Promise<BackendSession> {
  const response = await fetch('/api/sessions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ mode: 'mock' }),
  })

  if (!response.ok) {
    throw new Error(`Session creation failed: ${response.status}`)
  }

  return response.json()
}

export async function processBackendSession(
  sessionId: string,
): Promise<void> {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/process`,
    { method: 'POST' },
  )

  if (!response.ok) {
    throw new Error(`Session processing failed: ${response.status}`)
  }
}

type BackendStreamOptions = {
  afterEventId?: number
  onEvent: (event: BackendEvent) => void
  onStatusChange?: (status: StreamStatus) => void
  onError?: (error: Error) => void
}

export function subscribeToBackendEvents(
  sessionId: string,
  {
    afterEventId = 0,
    onEvent,
    onStatusChange,
    onError,
  }: BackendStreamOptions,
) {
  const controller = new AbortController()
  let closed = false

  async function connect() {
    try {
      const response = await fetch(
        `/api/sessions/${encodeURIComponent(sessionId)}/events`,
        {
          headers: {
            'Last-Event-ID': String(afterEventId),
            Accept: 'text/event-stream',
          },
          signal: controller.signal,
        },
      )

      if (!response.ok || !response.body) {
        throw new Error(`Event stream failed: ${response.status}`)
      }

      onStatusChange?.('connected')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (!closed) {
        const { value, done } = await reader.read()

        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''

        for (const frame of frames) {
          const dataLine = frame
            .split('\n')
            .find((line) => line.startsWith('data:'))

          if (!dataLine) continue

          const json = dataLine.slice(5).trim()

          try {
            const event = JSON.parse(json) as BackendEvent
            onEvent(event)
          } catch {
            onError?.(new Error('Invalid event data received'))
          }
        }
      }

      onStatusChange?.('closed')
    } catch (error) {
      if (!closed) {
        onStatusChange?.('closed')
        onError?.(
          error instanceof Error
            ? error
            : new Error('Unable to connect to event stream'),
        )
      }
    }
  }

  void connect()

  return {
    close() {
      closed = true
      controller.abort()
      onStatusChange?.('closed')
    },
  }
}

