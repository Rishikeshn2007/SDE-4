import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest'
import ContextPanel from './components/ContextPanel'

describe('ContextPanel', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? 'GET'

        if (method === 'GET') {
          return {
            ok: true,
            json: async () => ({ consent_enabled: false }),
          }
        }

        const enabled = url.endsWith('/enable')
        return {
          ok: true,
          json: async () => ({
            consent_enabled: enabled,
            message: enabled ? 'Consent enabled.' : 'Consent withdrawn.',
          }),
        }
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows screen context OFF by default', async () => {
    render(<ContextPanel />)

    expect(screen.getByRole('checkbox')).not.toBeChecked()

    await waitFor(() => {
      expect(screen.getByText(/Consent is currently OFF/i)).toBeInTheDocument()
    })
  })

  it('enables screen context when selected', async () => {
    const user = userEvent.setup()
    render(<ContextPanel />)

    const checkbox = screen.getByRole('checkbox', {
      name: /enable synthetic screen-context consent/i,
    })

    await waitFor(() => expect(checkbox).toBeEnabled())
    await user.click(checkbox)

    await waitFor(() => {
      expect(checkbox).toBeChecked()
      expect(screen.getByText(/Consent is currently ON/i)).toBeInTheDocument()
    })
  })

  it('disables screen context when unchecked', async () => {
    const user = userEvent.setup()
    render(<ContextPanel />)

    const checkbox = screen.getByRole('checkbox')

    await waitFor(() => expect(checkbox).toBeEnabled())
    await user.click(checkbox)

    await waitFor(() => expect(checkbox).toBeChecked())
    await user.click(checkbox)

    await waitFor(() => {
      expect(checkbox).not.toBeChecked()
      expect(screen.getByText(/Consent is currently OFF/i)).toBeInTheDocument()
    })
  })
})
