import { useEffect, useState } from 'react'

const API_URL = '/api/consent'

function ContextPanel() {
  const [screenContextEnabled, setScreenContextEnabled] = useState(false)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function loadConsent() {
      try {
        const response = await fetch(API_URL)
        if (!response.ok) throw new Error('Could not load consent status.')

        const data = await response.json()
        if (active) setScreenContextEnabled(data.consent_enabled === true)
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Consent status unavailable.')
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    void loadConsent()

    return () => {
      active = false
    }
  }, [])

  async function handleConsentChange(enabled: boolean) {
    setLoading(true)
    setError('')
    setMessage('')

    try {
      const response = await fetch(
        `${API_URL}/${enabled ? 'enable' : 'withdraw'}`,
        { method: 'POST' },
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Could not update consent.')
      }

      setScreenContextEnabled(data.consent_enabled === true)
      setMessage(data.message || (enabled ? 'Consent enabled.' : 'Consent withdrawn.'))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update consent.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="panel" aria-labelledby="context-heading">
      <h2 id="context-heading">Context &amp; Sources</h2>

      <p className="muted">
        Manage session context and review available transcript sources.
      </p>

      <div className="context-card">
        <h3>Session Context</h3>
        <p><strong>Session ID:</strong> mock-session-001</p>
        <p><strong>Session Mode:</strong> Mock Mode</p>
        <p><strong>Source:</strong> Mock Transcript Fixture</p>
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
        <h3>Screen Context Consent</h3>

        <p>
          Synthetic capture consent is optional and disabled by default.
          No real screen screenshots are captured.
        </p>

        <label>
          <input
            type="checkbox"
            checked={screenContextEnabled}
            disabled={loading}
            onChange={(event) => {
              void handleConsentChange(event.target.checked)
            }}
          />
          Enable synthetic screen-context consent
        </label>

        <p role="status" aria-live="polite">
          {loading
            ? 'Loading consent status...'
            : `Consent is currently ${screenContextEnabled ? 'ON' : 'OFF'}.`}
        </p>

        {message && <p role="status">{message}</p>}
        {error && <p role="alert">{error}</p>}
      </div>
    </section>
  )
}

export default ContextPanel