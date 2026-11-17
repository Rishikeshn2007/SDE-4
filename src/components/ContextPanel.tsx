
type ContextPanelProps = {
  screenContextEnabled: boolean
  setScreenContextEnabled: (enabled: boolean) => void
  microphoneCaptureEnabled: boolean
  setMicrophoneCaptureEnabled: (enabled: boolean) => void
}

function ContextPanel({
  screenContextEnabled,
  setScreenContextEnabled,
  microphoneCaptureEnabled,
  setMicrophoneCaptureEnabled,
}: ContextPanelProps) {
  return (
    <section className="panel" aria-labelledby="context-heading">
      <h2 id="context-heading">Privacy &amp; Context Settings</h2>

      <p className="muted">
        Choose what session information may be used. All capture options
        are disabled by default.
      </p>

      <div className="context-card">
        <h3>Session Context</h3>
        <p><strong>Session Mode:</strong> Mock Mode</p>
        <p><strong>Source:</strong> Mock Transcript Fixture</p>
      </div>

      <div className="context-toggle">
        <h3>Screen Context</h3>
        <p>Allow screen information to be included in session context.</p>
        <label>
          <input
            type="checkbox"
            checked={screenContextEnabled}
            onChange={(event) =>
              setScreenContextEnabled(event.target.checked)
            }
          />
          Enable screen context
        </label>
        <p role="status" aria-live="polite">
          Screen context is currently{' '}
          <strong>{screenContextEnabled ? 'ON' : 'OFF'}</strong>
        </p>
      </div>

      <div className="context-toggle">
        <h3>Microphone Capture</h3>
        <p>
          This preference does not request microphone permission or start
          recording. Microphone access still requires a separate action.
        </p>
        <label>
          <input
            type="checkbox"
            checked={microphoneCaptureEnabled}
            onChange={(event) =>
              setMicrophoneCaptureEnabled(event.target.checked)
            }
          />
          Allow microphone capture
        </label>
        <p role="status" aria-live="polite">
          Microphone capture is currently{' '}
          <strong>{microphoneCaptureEnabled ? 'ON' : 'OFF'}</strong>
        </p>
      </div>
    </section>
  )
}

export default ContextPanel
