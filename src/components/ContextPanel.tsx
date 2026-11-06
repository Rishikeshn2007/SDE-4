
import { useState } from 'react'

function ContextPanel() {
  const [screenContextEnabled, setScreenContextEnabled] = useState(false)

  return (
    <section className="panel" aria-labelledby="context-heading">
      <h2 id="context-heading">Context &amp; Sources</h2>

      <p className="muted">
        Manage session context and review available transcript sources.
      </p>

      <div className="context-card">
        <h3>Session Context</h3>

        <p>
          <strong>Session ID:</strong> mock-session-001
        </p>

        <p>
          <strong>Session Mode:</strong> Mock Mode
        </p>

        <p>
          <strong>Source:</strong> Mock Transcript Fixture
        </p>
      </div>

      <div className="context-card">
        <h3>Transcript Sources</h3>

        <ul>
          <li>Mock transcript events</li>
          <li>Session timeline</li>
          <li>Simulated recognition data</li>
        </ul>
      </div>

      <div className="context-toggle">
        <h3>Screen Context</h3>

        <p>
          Screen context is optional and remains disabled unless you
          explicitly enable it.
        </p>

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
          <strong>
            {screenContextEnabled ? 'ON' : 'OFF'}
          </strong>
        </p>
      </div>
    </section>
  )
}

export default ContextPanel
