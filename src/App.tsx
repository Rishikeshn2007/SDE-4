import ApprovalDialog from './components/ApprovalDialog'
import { useEffect, useRef, useState } from 'react'
import './App.css'
import {
  subscribeToMockEvents,
  type TranscriptEvent,
} from './api/sessionApi'
import SessionControls from './components/SessionControls'
import MicrophonePermission from './components/MicrophonePermission'
import TranscriptTimeline from './components/TranscriptTimeline'
import ContextPanel from './components/ContextPanel'
import WorkflowProgress, {
  type WorkflowStep,
} from './components/WorkflowProgress'

type SessionStatus = 'Idle' | 'Running' | 'Paused' | 'Stopped'
type MicrophoneStatus = 'Prompt' | 'Granted' | 'Denied' | 'Unsupported'

function App() {
  const [status, setStatus] = useState<SessionStatus>('Idle')
  const [isApprovalOpen, setIsApprovalOpen] = useState(false)
  const [screenContextEnabled, setScreenContextEnabled] = useState(false)
const [approvalMessage, setApprovalMessage] = useState('')
function handleApprove() {
  setApprovalMessage('Approved. The workflow is ready to proceed.')
  setIsApprovalOpen(false)

  setWorkflowSteps((steps) =>
    steps.map((step) =>
      step.id === 4
        ? { ...step, status: 'completed' }
        : step,
    ),
  )
}

function handleReject() {
  setApprovalMessage('Rejected. No action was executed.')
  setIsApprovalOpen(false)

  setWorkflowSteps((steps) =>
    steps.map((step) =>
      step.id === 4
        ? { ...step, status: 'failed' }
        : step,
    ),
  )
}
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStep[]>([
  {
    id: 1,
    title: 'Session Started',
    description: 'Start the voice session',
    status: 'completed',
  },
  {
    id: 2,
    title: 'Audio Transcription',
    description: 'Convert audio into transcript text',
    status: 'in-progress',
  },
  {
    id: 3,
    title: 'Transcript Review',
    description: 'Review transcript segments',
    status: 'pending',
  },
  {
    id: 4,
    title: 'Approval',
    description: 'Wait for user approval',
    status: 'pending',
  },
])
  const [micStatus, setMicStatus] =
    useState<MicrophoneStatus>('Prompt')
  const [micMessage, setMicMessage] = useState(
    'Permission has not been requested.',
  )
  const [transcriptEvents, setTranscriptEvents] =
    useState<TranscriptEvent[]>([])
    const [streamStatus, setStreamStatus] =
  useState<'connected' | 'closed' | 'disconnected'>('closed')

const [, setLastEventId] = useState(0)
const lastEventIdRef = useRef(0)
const hasStartedStreamRef = useRef(false)
const subscriptionRef = useRef<ReturnType<typeof subscribeToMockEvents> | null>(null)

  const [apiError, setApiError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
const [isOffline, setIsOffline] = useState(!navigator.onLine)
  
  function startMockStream(afterEventId: number) {
    subscriptionRef.current?.close()

    subscriptionRef.current = subscribeToMockEvents({
      afterEventId,
      intervalMs: 3000,

      onEvent: (event) => {
        setTranscriptEvents((previousEvents) => {
          if (previousEvents.some((item) => item.id === event.id)) {
            return previousEvents
          }

          return [...previousEvents, event]
        })

        lastEventIdRef.current = event.id
        setLastEventId(event.id)
        setWorkflowSteps((steps) =>
  steps.map((step) => {
    if (step.id === 2) {
      return { ...step, status: 'completed' }
    }

    if (step.id === 3) {
      return { ...step, status: 'in-progress' }
    }

    return step
  }),
)
      },

      onStatusChange: (newStatus) => {
  setStreamStatus(newStatus)

  if (newStatus === 'closed' && lastEventIdRef.current >= 4) {
    setWorkflowSteps((steps) =>
      steps.map((step) => {
        if (step.id === 3) {
          return { ...step, status: 'completed' }
        }

        if (step.id === 4) {
          return { ...step, status: 'in-progress' }
        }

        return step
      }),
    )
  }
},
    })
  }

  useEffect(() => {
    function handleOnline() {
  setIsOffline(false)
  setApiError('')

  if (hasStartedStreamRef.current) {
    startMockStream(lastEventIdRef.current)
  }
}

  function handleOffline() {
  setIsOffline(true)

  subscriptionRef.current?.close()
  subscriptionRef.current = null

  setStreamStatus('disconnected')
}

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      subscriptionRef.current?.close()
      subscriptionRef.current = null
    }
  }, [])

    async function loadMockTranscript() {
    if (!navigator.onLine) {
      setIsOffline(true)
      setStreamStatus('disconnected')
      setApiError('You are offline. Please reconnect.')
      return
    }

    try {
      setIsLoading(true)
      setApiError('')
      setIsOffline(false)

      lastEventIdRef.current = 0
setLastEventId(0)
setTranscriptEvents([])
setWorkflowSteps((steps) =>
  steps.map((step) => {
    if (step.id === 1) {
      return { ...step, status: 'completed' }
    }

    if (step.id === 2) {
      return { ...step, status: 'in-progress' }
    }

    if (step.id === 3 || step.id === 4) {
      return { ...step, status: 'pending' }
    }

    return step
  }),
)
hasStartedStreamRef.current = true
startMockStream(0)
    } catch {
      setStreamStatus('disconnected')
      setApiError('Could not connect to the mock event stream.')
    } finally {
      setIsLoading(false)
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
  isLoading={isLoading}
  isOffline={isOffline}
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
              <div className="status-row">
  <span>Event Stream</span>
  <strong
    className="mode-label"
    role="status"
    aria-live="polite"
  >
    {streamStatus.toUpperCase()}
  </strong>
</div>
            </section>

            <MicrophonePermission
              status={micStatus}
              message={micMessage}
              onRequest={requestMicrophone}
            />
          </aside>
        </div>

              <WorkflowProgress steps={workflowSteps} />
              <section className="approval-section">
  <button
    type="button"
    onClick={() => setIsApprovalOpen(true)}
    disabled={workflowSteps[3].status !== 'in-progress'}
  >
    Review Approval
  </button>

  {approvalMessage && (
    <p role="status" aria-live="polite">
      {approvalMessage}
    </p>
  )}
</section>

<ApprovalDialog
  open={isApprovalOpen}
  onApprove={handleApprove}
  onReject={handleReject}
/>

        <ContextPanel
  screenContextEnabled={screenContextEnabled}
  setScreenContextEnabled={setScreenContextEnabled}
/>

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
