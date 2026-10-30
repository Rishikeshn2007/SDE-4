
export type TranscriptEvent = {
  id: number
  timestamp: string
  text: string
}

export type SessionResponse = {
  sessionId: string
  status: 'success'
  events: TranscriptEvent[]
}

const mockEvents: TranscriptEvent[] = [
  {
    id: 1,
    timestamp: '10:00:01',
    text: 'Welcome to the demo session.',
  },
  {
    id: 2,
    timestamp: '10:00:03',
    text: 'The mock transcript is working.',
  },
  {
    id: 3,
    timestamp: '10:00:05',
    text: 'Session completed successfully.',
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
