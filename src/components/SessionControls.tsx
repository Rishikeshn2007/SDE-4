
type SessionStatus = 'Idle' | 'Running' | 'Paused' | 'Stopped'

type SessionControlsProps = {
  status: SessionStatus
  setStatus: (status: SessionStatus) => void
}

function SessionControls({ status, setStatus }: SessionControlsProps) {
  return (
    <section className="panel" aria-labelledby="session-heading">
      <h2 id="session-heading">Session Controls</h2>

      <p>
        Session status: <strong>{status}</strong>
      </p>

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
  )
}

export default SessionControls
