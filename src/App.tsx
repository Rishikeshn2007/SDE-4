
import { useState } from 'react'
import './App.css'
import { getMockSession } from './api/sessionApi'
import SessionControls from './components/SessionControls'
import MicrophonePermission from './components/MicrophonePermission'
import TranscriptTimeline, { type TranscriptEvent } from './components/TranscriptTimeline'

type SessionStatus = 'Idle' | 'Running' | 'Paused' | 'Stopped'
type MicrophoneStatus = 'Prompt' | 'Granted' | 'Denied' | 'Unsupported'





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
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <main className="app" id="main-content">
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

      <SessionControls status={status} setStatus={setStatus} />
  
        

      <MicrophonePermission
  status={micStatus}
  message={micMessage}
  onRequest={requestMicrophone}
/>

      

<TranscriptTimeline
  events={transcriptEvents}
  apiError={apiError}
  onLoad={loadMockTranscript}
/>

  


         <footer>Team SDE 4 | Workstream W6 – Frontend and UX</footer>
      </main>
    </>
  ) 
 }

export default App
