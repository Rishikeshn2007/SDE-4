
import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import ContextPanel from './components/ContextPanel'

function ContextPanelTestWrapper() {
  const [screenContextEnabled, setScreenContextEnabled] = useState(false)

  return (
    <ContextPanel
      screenContextEnabled={screenContextEnabled}
      setScreenContextEnabled={setScreenContextEnabled}
    />
  )
}

describe('ContextPanel', () => {
  it('shows screen context OFF by default', () => {
    render(<ContextPanelTestWrapper />)

    expect(screen.getByRole('checkbox')).not.toBeChecked()
    expect(screen.getByRole('status')).toHaveTextContent('OFF')
  })

  it('enables screen context when selected', async () => {
    const user = userEvent.setup()

    render(<ContextPanelTestWrapper />)

    await user.click(
      screen.getByRole('checkbox', {
        name: /enable screen context/i,
      }),
    )

    expect(screen.getByRole('checkbox')).toBeChecked()
    expect(screen.getByRole('status')).toHaveTextContent('ON')
  })

  it('disables screen context when unchecked', async () => {
    const user = userEvent.setup()

    render(<ContextPanelTestWrapper />)

    const checkbox = screen.getByRole('checkbox')

    await user.click(checkbox)
    await user.click(checkbox)

    expect(checkbox).not.toBeChecked()
    expect(screen.getByRole('status')).toHaveTextContent('OFF')
  })
})
