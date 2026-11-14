
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
