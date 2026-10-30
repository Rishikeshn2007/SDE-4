
import { useState } from 'react'
import './App.css'
import { getMockSession } from './api/sessionApi'

type SessionStatus = 'Idle' | 'Running' | 'Paused' | 'Stopped'
type MicrophoneStatus = 'Prompt' | 'Granted' | 'Denied' | 'Unsupported'

type TranscriptEvent = {
  id: number
  timestamp: string
  text: string
}

const fixtureEvents: TranscriptEvent[] = [
  { id: 1, timestamp: '10:00:01', text: 'Welcome to the demo session.' },
  { id: 2, timestamp: '10:00:03', text: 'The mock transcript is working.' },
  { id: 3, timestamp: '10:00:05', text: 'Session completed successfully.' },
]


function App() {
  const [status, setStatus] = useState<SessionStatus>('Idle')
  const [micStatus, setMicStatus] =
    useState<MicrophoneStatus>('Prompt')
  const [micMessage, setMicMessage] = useState('Permission has not been requested.')
  const [transcriptEvents, setTranscriptEvents] = useState<TranscriptEvent[]>([])
const [apiError, setApiError] = useState('')

async function loadMockTranscript() {
  try {
    setApiError('')
    const response = await getMockSession()
    setTranscriptEvents(response.events)
  } catch {
    setApiError('Unable to load the mock transcript. Please try again.')
  }
}

  async function requestMicrophone() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicStatus('Unsupported')
      setMicMessage('Microphone permission is not supported in this browser.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      })

      // Stop the microphone immediately; this demo does not record audio.
      stream.getTracks().forEach((track) => track.stop())

      setMicStatus('Granted')
      setMicMessage('Permission granted. No audio was recorded or uploaded.')
    } catch (error) {
      if (error instanceof DOMException && error.name === 'NotAllowedError') {
        setMicStatus('Denied')
        setMicMessage('Permission denied. Check your browser permissions.')
      } else {
        setMicMessage('Could not access the microphone. Please try again.')
      }
    }
  }

  return (
    <main className="app">
      <header className="header">
        <div>
          <h1>Session Studio</h1>
          <p>Voice Session Dashboard</p>
        </div>
        <span className="badge">MOCK MODE ON</span>
      </header>

      <section className="notice" role="status">
        Mock mode is enabled. No real audio is uploaded.
      </section>

      <section className="panel">
        <h2>Session Controls</h2>
        <p>Session status: <strong>{status}</strong></p>
        <div className="buttons">
          <button
            onClick={() => setStatus('Running')}
            disabled={status === 'Running'}
          >
            Start Session
          </button>
          <button
            onClick={() => setStatus('Paused')}
            disabled={status !== 'Running'}
          >
            Pause Session
          </button>
          <button
            onClick={() => setStatus('Stopped')}
            disabled={status === 'Idle' || status === 'Stopped'}
          >
            Stop Session
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>Microphone Permission</h2>
        <p>
          Permission status: <strong>{micStatus}</strong>
        </p>
        <p className="muted" role="status">{micMessage}</p>
        <button onClick={requestMicrophone}>
          Request Microphone Permission
        </button>
      </section>

      

<section className="panel">
  <h2>Transcript Timeline</h2>
  <p className="muted">
    Mock session transcript events displayed in timestamp order.
  </p>

  <button type="button" onClick={loadMockTranscript}>
    Load Mock Transcript
  </button>

  {apiError && <p role="alert">{apiError}</p>}

  {transcriptEvents.length === 0 ? (
    <p>No transcript loaded yet. Click the button to load mock events.</p>
  ) : (
    <ol className="timeline">
      {transcriptEvents.map((event) => (
        <li key={event.id} className="timeline-event">
          <time>{event.timestamp}</time>
          <p>{event.text}</p>
        </li>
      ))}
    </ol>
  )}
</section>


      <footer>Team SDE 4 | Workstream W6 – Frontend and UX</footer>
    </main>
  )
}

export default App
