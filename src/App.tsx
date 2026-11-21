import { useEffect, useRef, useState } from 'react'
import './App.css'
import { getMockSession } from './api/sessionApi'
import SessionControls from './components/SessionControls'
import MicrophonePermission from './components/MicrophonePermission'
import TranscriptTimeline, {
  type TranscriptEvent,
} from './components/TranscriptTimeline'
import ContextPanel from './components/ContextPanel'
import ReasoningWorkflowPanel from './components/ReasoningWorkflowPanel'

type SessionStatus = 'Idle' | 'Running' | 'Paused' | 'Stopped'
type MicrophoneStatus = 'Prompt' | 'Granted' | 'Denied' | 'Unsupported'

type SpeechResult = {
  isFinal: boolean
  0: { transcript: string }
}

type SpeechEvent = {
  resultIndex: number
  results: ArrayLike<SpeechResult>
}

type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: SpeechEvent) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}

type SpeechWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike
  webkitSpeechRecognition?: new () => SpeechRecognitionLike
}

const BACKEND_URL = 'http://127.0.0.1:5000'

async function convertToWav(blob: Blob): Promise<Blob> {
  if (!blob || blob.size === 0) {
    throw new Error('No audio data was recorded.')
  }

  const audioContext = new AudioContext()

  try {
    const audioBuffer = await audioContext.decodeAudioData(
      await blob.arrayBuffer(),
    )

    const samples = new Float32Array(audioBuffer.length)

    for (let channel = 0; channel < audioBuffer.numberOfChannels; channel++) {
      const channelData = audioBuffer.getChannelData(channel)

      for (let i = 0; i < samples.length; i++) {
        samples[i] += channelData[i] / audioBuffer.numberOfChannels
      }
    }

    const buffer = new ArrayBuffer(44 + samples.length * 2)
    const view = new DataView(buffer)

    const writeString = (offset: number, value: string) => {
      for (let i = 0; i < value.length; i++) {
        view.setUint8(offset + i, value.charCodeAt(i))
      }
    }

    writeString(0, 'RIFF')
    view.setUint32(4, 36 + samples.length * 2, true)
    writeString(8, 'WAVE')
    writeString(12, 'fmt ')
    view.setUint32(16, 16, true)
    view.setUint16(20, 1, true)
    view.setUint16(22, 1, true)
    view.setUint32(24, audioBuffer.sampleRate, true)
    view.setUint32(28, audioBuffer.sampleRate * 2, true)
    view.setUint16(32, 2, true)
    view.setUint16(34, 16, true)
    writeString(36, 'data')
    view.setUint32(40, samples.length * 2, true)

    for (let i = 0; i < samples.length; i++) {
      const sample = Math.max(-1, Math.min(1, samples[i]))

      view.setInt16(
        44 + i * 2,
        sample < 0 ? sample * 32768 : sample * 32767,
        true,
      )
    }

    return new Blob([buffer], { type: 'audio/wav' })
  } catch {
    throw new Error(
      'The browser could not decode the recorded audio. Try recording again using Chrome or Edge.',
    )
  } finally {
    await audioContext.close()
  }
}

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
  const [isLoading, setIsLoading] = useState(false)

  // This now represents backend availability, not Wi-Fi availability.
  const [isOffline, setIsOffline] = useState(true)

  const [audioConsent, setAudioConsent] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [transcriptionMode, setTranscriptionMode] =
    useState('Not started')

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const onlineTranscriptRef = useRef('')
  const onlineFailedRef = useRef(false)
  const stopRequestedRef = useRef(false)

  // Check the local Flask backend directly.
  useEffect(() => {
    let active = true

    const checkBackend = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/api/health`, {
          method: 'GET',
          cache: 'no-store',
        })

        if (active) {
          setIsOffline(!response.ok)
        }
      } catch {
        if (active) {
          setIsOffline(true)
        }
      }
    }

    // Check immediately when the dashboard opens.
    void checkBackend()

    // Check again when network status changes.
    window.addEventListener('online', checkBackend)
    window.addEventListener('offline', checkBackend)

    // Periodically verify that the local backend is still available.
    const backendCheckInterval = window.setInterval(() => {
      void checkBackend()
    }, 5000)

    return () => {
      active = false
      window.clearInterval(backendCheckInterval)

      recognitionRef.current?.stop()
      streamRef.current?.getTracks().forEach((track) => track.stop())

      window.removeEventListener('online', checkBackend)
      window.removeEventListener('offline', checkBackend)
    }
  }, [])

  function addTranscript(text: string) {
    const cleanText = text.trim()
    if (!cleanText) return

    const id = Date.now()

    const event: TranscriptEvent = {
      id,
      segmentId: id,
      timestamp: new Date().toISOString(),
      text: cleanText,
      status: 'final',
      revision: 1,
      confidence: 0,
    }

    setTranscriptEvents((previous) => [...previous, event])
  }

  async function loadMockTranscript() {
    try {
      setIsLoading(true)
      setApiError('')

      const response = await getMockSession()
      setTranscriptEvents(response.events)
    } catch {
      setApiError('Could not load mock transcript. Check the backend.')
    } finally {
      setIsLoading(false)
    }
  }

  async function requestMicrophone() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicStatus('Unsupported')
      setMicMessage('Microphone is not supported in this browser.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      })

      stream.getTracks().forEach((track) => track.stop())

      setMicStatus('Granted')
      setMicMessage('Microphone permission granted.')
    } catch {
      setMicStatus('Denied')
      setMicMessage('Microphone permission denied. Check browser settings.')
    }
  }

  async function startRecording() {
    if (!audioConsent) {
      setApiError('Please give audio consent before recording.')
      return
    }

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setApiError('Audio recording is not supported in this browser.')
      return
    }

    try {
      setApiError('')
      onlineTranscriptRef.current = ''
      onlineFailedRef.current = false
      stopRequestedRef.current = false
      chunksRef.current = []

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      })

      streamRef.current = stream

      const mimeCandidates = [
        'audio/webm;codecs=opus',
        'audio/ogg;codecs=opus',
      ]

      const supportedMime = mimeCandidates.find((type) =>
        MediaRecorder.isTypeSupported(type),
      )

      const recorder = supportedMime
        ? new MediaRecorder(stream, { mimeType: supportedMime })
        : new MediaRecorder(stream)

      recorderRef.current = recorder

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data)
        }
      }

      recorder.onstop = async () => {
        try {
          setMicMessage('Processing your recording...')

          const onlineText = onlineTranscriptRef.current.trim()

          // Use browser recognition only if it produced valid results
          // and did not report an error.
          if (onlineText && !onlineFailedRef.current) {
            addTranscript(onlineText)
            setTranscriptionMode('Online speech recognition')
            setMicMessage('Online transcription completed.')
            return
          }

          // Otherwise use the local Vosk backend.
          setTranscriptionMode('Offline Vosk')
          setMicMessage('Trying local Vosk transcription...')

          const recordedBlob = new Blob(chunksRef.current, {
            type: recorder.mimeType || 'audio/webm',
          })

          const wavBlob = await convertToWav(recordedBlob)

          if (wavBlob.size > 1024 * 1024) {
            throw new Error(
              'Recording is too large. Please record a shorter clip.',
            )
          }

          const formData = new FormData()
          formData.append('audio', wavBlob, 'recording.wav')

          const response = await fetch(
            `${BACKEND_URL}/api/transcribe`,
            {
              method: 'POST',
              headers: {
                'X-Audio-Consent': 'true',
              },
              body: formData,
            },
          )

          const result = await response.json()

          if (!response.ok) {
            throw new Error(result.error || 'Vosk transcription failed.')
          }

          if (result.transcript?.trim()) {
            addTranscript(result.transcript)
            setMicMessage('Offline transcription completed.')
          } else {
            setMicMessage('No speech recognized. Please try again.')
          }
        } catch (error) {
          setApiError(
            error instanceof Error
              ? error.message
              : 'Transcription failed.',
          )
          setMicMessage('Transcription could not be completed.')
        } finally {
          stream.getTracks().forEach((track) => track.stop())
          streamRef.current = null
          recorderRef.current = null
          recognitionRef.current = null
          chunksRef.current = []
          setIsRecording(false)
        }
      }

      recorder.start(1000)

      setIsRecording(true)
      setMicStatus('Granted')
      setMicMessage('Recording is active. Speak clearly.')

      const browserWindow = window as SpeechWindow

      const Recognition =
        browserWindow.SpeechRecognition ||
        browserWindow.webkitSpeechRecognition

      // Online recognition is attempted only when the browser reports
      // an internet connection. Otherwise, recording is sent to local Vosk.
      if (Recognition && navigator.onLine) {
        try {
          const recognition = new Recognition()

          recognition.continuous = true
          recognition.interimResults = true
          recognition.lang = 'en-IN'

          recognition.onresult = (event) => {
            for (
              let i = event.resultIndex;
              i < event.results.length;
              i++
            ) {
              const result = event.results[i]

              if (result.isFinal) {
                onlineTranscriptRef.current +=
                  result[0].transcript + ' '
              }
            }
          }

          recognition.onerror = () => {
            onlineFailedRef.current = true
            setMicMessage(
              'Online recognition unavailable. Recording continues for offline transcription.',
            )
          }

          recognition.onend = () => {
            if (!stopRequestedRef.current) {
              onlineFailedRef.current = true
              setMicMessage(
                'Online recognition ended. Recording continues for offline transcription.',
              )
            } else {
              const activeRecorder = recorderRef.current

              if (activeRecorder?.state === 'recording') {
                activeRecorder.stop()
              }
            }
          }

          recognitionRef.current = recognition
          recognition.start()

          setTranscriptionMode('Online speech recognition')
        } catch {
          onlineFailedRef.current = true
          setTranscriptionMode('Offline Vosk')
          setMicMessage(
            'Online recognition unavailable. Recording continues for Vosk.',
          )
        }
      } else {
        onlineFailedRef.current = true
        setTranscriptionMode('Offline Vosk')
        setMicMessage('Offline recording active. Speak clearly.')
      }
    } catch {
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null

      setIsRecording(false)
      setMicStatus('Denied')
      setMicMessage('Could not start recording. Check microphone permission.')
      setApiError('Could not start microphone recording.')
    }
  }

  function stopRecording() {
    const recorder = recorderRef.current

    if (!recorder || recorder.state !== 'recording') return

    stopRequestedRef.current = true

    setMicMessage('Stopping recording and preparing transcription...')

    const recognition = recognitionRef.current

    if (recognition) {
      try {
        recognition.stop()
      } catch {
        // The recorder will still be stopped below.
      }
    }

    // Stop the recorder even if recognition.onend is not fired.
    window.setTimeout(() => {
      if (recorder.state === 'recording') {
        recorder.stop()
      }
    }, 500)
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

          <span className="badge">W3 + W6 Integration</span>
        </header>

        <section className="notice dashboard-notice" role="status">
          <strong>Session Studio:</strong> Mock transcripts and optional
          microphone transcription are available. Screen capture remains off.
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
                <span>Session Status</span>
                <strong>{status}</strong>
              </div>

              <div className="status-row">
                <span>Transcript Events</span>
                <strong>{transcriptEvents.length}</strong>
              </div>

              <div className="status-row">
                <span>Transcription Mode</span>
                <strong>{transcriptionMode}</strong>
              </div>

              <div className="status-row">
                <span>Local Backend</span>
                <strong>{isOffline ? 'Unavailable' : 'Connected'}</strong>
              </div>
            </section>

            <MicrophonePermission
              status={micStatus}
              message={micMessage}
              onRequest={requestMicrophone}
            />

            <section className="panel">
              <h2>Online / Offline Audio Transcription</h2>

              <label>
                <input
                  type="checkbox"
                  checked={audioConsent}
                  disabled={isRecording}
                  onChange={(event) => {
                    setAudioConsent(event.target.checked)
                    setApiError('')
                  }}
                />

                I consent to microphone recording and processing. Online
                recognition may send audio to the browser's speech service;
                offline recognition sends audio to my local backend.
              </label>

              <p className="muted">
                Online recognition is attempted when supported. Otherwise,
                local Vosk transcription is used. Audio is processed in memory.
              </p>

              <button
                type="button"
                onClick={startRecording}
                disabled={!audioConsent || isRecording || isLoading}
              >
                Start Recording
              </button>

              <button
                type="button"
                onClick={stopRecording}
                disabled={!isRecording}
              >
                Stop Recording
              </button>

              <p role="status" aria-live="polite">
                {isRecording ? 'Recording...' : 'Recording is off.'}
              </p>
            </section>
          </aside>
        </div>

        <ContextPanel />
        <ReasoningWorkflowPanel />

        <section className="accessibility-panel">
          <h2>Accessibility Features</h2>

          <div className="accessibility-grid">
            <div className="accessibility-item">
              <strong>Skip Link</strong>
              <span>Enabled</span>
            </div>

            <div className="accessibility-item">
              <strong>Focus Styles</strong>
              <span>Visible</span>
            </div>

            <div className="accessibility-item">
              <strong>Semantic Structure</strong>
              <span>Implemented</span>
            </div>

            <div className="accessibility-item">
              <strong>ARIA Live</strong>
              <span>Available</span>
            </div>

            <div className="accessibility-item">
              <strong>Keyboard Support</strong>
              <span>Enabled</span>
            </div>
          </div>
        </section>

        <footer>
          Team SDE 4 | Week 3 Context & Reasoning Integration
        </footer>
      </main>
    </>
  )
}

export default App