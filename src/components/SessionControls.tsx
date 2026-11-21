
type SessionStatus = 'Idle' | 'Running' | 'Paused' | 'Stopped'

type SessionControlsProps = {
  status: SessionStatus
  setStatus: (status: SessionStatus) => void
}

function SessionControls({ status, setStatus }: SessionControlsProps) {
  const isRunning = status === 'Running'
  const isPaused = status === 'Paused'
  const isActive = isRunning || isPaused

  const captureLabel = isRunning
    ? 'CAPTURING'
    : isPaused
      ? 'PAUSED'
      : 'INACTIVE'

  function handleMainAction() {
    if (isRunning) {
      setStatus('Paused')
    } else if (status === 'Idle' || isPaused) {
      setStatus('Running')
    }
  }

  function handleStop() {
    if (isActive) {
      setStatus('Stopped')
    }
  }

  return (
    <section className="session-bar" aria-labelledby="session-heading">
      <div className="session-info">
        <div className="session-icon" aria-hidden="true">
          🎙️
        </div>

        <div>
          <h2 id="session-heading">Session Studio</h2>
          <p>Record • Transcribe • Review</p>
        </div>
      </div>

      <div
        className={`session-indicator ${isRunning ? 'capturing' : isPaused ? 'paused' : 'inactive'}`}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <span
          className={`status-dot ${isRunning ? 'active' : isPaused ? 'paused' : ''}`}
          aria-hidden="true"
        />

        <strong>{captureLabel}</strong>
      </div>

      <div className="session-actions">
        <button
          type="button"
          className="pause-button"
          onClick={handleMainAction}
          disabled={status === 'Stopped'}
          aria-label={
            isRunning
              ? 'Pause session'
              : isPaused
                ? 'Resume session'
                : status === 'Idle'
                  ? 'Start session'
                  : 'Session stopped'
          }
        >
          {isRunning
            ? 'Ⅱ Pause'
            : isPaused
              ? '▶ Resume'
              : status === 'Idle'
                ? '▶ Start Session'
                : 'Session Stopped'}
        </button>

        <button
          type="button"
          className="stop-button"
          onClick={handleStop}
          disabled={!isActive}
          aria-label="Stop session"
        >
          ■ Stop Session
        </button>
      </div>
    </section>
  )
}

export default SessionControls
