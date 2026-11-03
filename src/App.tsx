
import { useState } from 'react'
import './App.css'
import { getMockSession } from './api/sessionApi'
import SessionControls from './components/SessionControls'
import MicrophonePermission from './components/MicrophonePermission'
import TranscriptTimeline, {
  type TranscriptEvent,
} from './components/TranscriptTimeline'

type SessionStatus = 'Idle' | 'Running' | 'Paused' | 'Stopped'
type MicrophoneStatus = 'Prompt' | 'Granted' | 'Denied' | 'Unsupported'

function App() {
  const [status, setStatus] = useState<SessionStatus>('Idle')
  const [micStatus, setMicStatus] =
    useState<MicrophoneStatus>('Prompt')
  const [micMessage, setMicMessage] = useState(
    'Permission has not been requested.',
  )
  const [transcriptEvents, setTranscriptEvents] =
    useState<TranscriptEvent[]>([])
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
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <main className="app dashboard" id="main-content">
        <header className="dashboard-header">
          <div className="brand">
            <span className="brand-icon" aria-hidden="true">🎙️</span>
            <h1>Session Studio</h1>
          </div>
          <span className="badge">W6 – Frontend &amp; UX</span>
        </header>

        <section className="notice dashboard-notice" role="status">
          <strong>ⓘ Mock Mode:</strong> Using simulated session data for demo
          purposes. No real audio is uploaded.
        </section>

        <SessionControls status={status} setStatus={setStatus} />

        <div className="dashboard-grid">
          <div className="dashboard-main">
            <TranscriptTimeline
              events={transcriptEvents}
              apiError={apiError}
              onLoad={loadMockTranscript}
            />
          </div>

          <aside className="dashboard-side" aria-label="Session status">
            <section className="panel status-panel">
              <h2>Session Status</h2>

              <div className={`permission-summary ${micStatus.toLowerCase()}`}>
                <strong>Microphone Permission: {micStatus}</strong>
                <p>{micMessage}</p>
              </div>

              <div className="status-row">
                <span>◷ Session Status</span>
                <strong>{status}</strong>
              </div>

              <div className="status-row">
                <span>▥ Transcript Events</span>
                <strong>{transcriptEvents.length}</strong>
              </div>

              <div className="status-row">
                <span>☷ Mode</span>
                <strong className="mode-label">Mock Mode</strong>
              </div>
            </section>

            <MicrophonePermission
              status={micStatus}
              message={micMessage}
              onRequest={requestMicrophone}
            />
          </aside>
        </div>

        <section className="accessibility-panel">
          <h2>♿ Accessibility Features</h2>

          <div className="accessibility-grid">
            <div className="accessibility-item">
              <strong>⌨ Skip Link</strong>
              <span>✓ Enabled</span>
            </div>

            <div className="accessibility-item">
              <strong>◎ Focus Styles</strong>
              <span>✓ Visible</span>
            </div>

            <div className="accessibility-item">
              <strong>♧ Semantic Structure</strong>
              <span>✓ Implemented</span>
            </div>

            <div className="accessibility-item">
              <strong>ARIA Live</strong>
              <span>✓ Available</span>
            </div>

            <div className="accessibility-item">
              <strong>⌨ Keyboard Support</strong>
              <span>✓ Working</span>
            </div>
          </div>
        </section>

        <footer>
          Team SDE 4 | Workstream W6 – Frontend and UX
        </footer>
      </main>
    </>
  )
}

export default App
