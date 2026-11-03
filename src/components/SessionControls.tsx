
type SessionStatus = 'Idle' | 'Running' | 'Paused' | 'Stopped'

type SessionControlsProps = {
  status: SessionStatus
  setStatus: (status: SessionStatus) => void
}

function SessionControls({ status, setStatus }: SessionControlsProps) {
  const isRunning = status === 'Running'
  const isPaused = status === 'Paused'

  function handleMainAction() {
    if (isRunning) {
      setStatus('Paused')
    } else {
      setStatus('Running')
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

      <div className="session-indicator" role="status">
        <span className={isRunning ? 'status-dot active' : 'status-dot'} />
        <strong>
          {isRunning
            ? 'Session Active'
            : isPaused
              ? 'Session Paused'
              : status === 'Stopped'
                ? 'Session Ended'
                : 'Session Idle'}
        </strong>
      </div>

      <div className="session-actions">
        <button
          className="pause-button"
          onClick={handleMainAction}
        >
          {isRunning
            ? 'Ⅱ Pause'
            : isPaused
              ? '▶ Resume'
              : '▶ Start Session'}
        </button>

        <button
          className="stop-button"
          onClick={() => setStatus('Stopped')}
          disabled={!isRunning && !isPaused}
        >
          ■ Stop Session
        </button>
      </div>
    </section>
  )
}

export default SessionControls
