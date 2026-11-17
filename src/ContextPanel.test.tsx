
import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import ContextPanel from './components/ContextPanel'

function ContextPanelTestWrapper() {
  const [screenContextEnabled, setScreenContextEnabled] = useState(false)
  const [microphoneCaptureEnabled, setMicrophoneCaptureEnabled] = useState(false)

  return (
    <ContextPanel
      screenContextEnabled={screenContextEnabled}
      setScreenContextEnabled={setScreenContextEnabled}
      microphoneCaptureEnabled={microphoneCaptureEnabled}
      setMicrophoneCaptureEnabled={setMicrophoneCaptureEnabled}
    />
  )
}

describe('ContextPanel privacy settings', () => {
  it('keeps all capture settings OFF by default', () => {
    render(<ContextPanelTestWrapper />)

    const checkboxes = screen.getAllByRole('checkbox')

    expect(checkboxes).toHaveLength(2)
    checkboxes.forEach((checkbox) => {
      expect(checkbox).not.toBeChecked()
    })

    expect(screen.getAllByRole('status')).toHaveLength(2)
expect(screen.getAllByText('OFF')).toHaveLength(2)
  })

  it('allows screen context to be enabled and disabled', async () => {
    const user = userEvent.setup()
    render(<ContextPanelTestWrapper />)

    const checkbox = screen.getByRole('checkbox', {
      name: /enable screen context/i,
    })

    await user.click(checkbox)
    expect(checkbox).toBeChecked()
    expect(screen.getByText('ON')).toBeInTheDocument()

    await user.click(checkbox)
    expect(checkbox).not.toBeChecked()
    expect(screen.getAllByText('OFF')).toHaveLength(2)
  })

  it('allows the microphone capture preference to be changed', async () => {
    const user = userEvent.setup()
    render(<ContextPanelTestWrapper />)

    const checkbox = screen.getByRole('checkbox', {
      name: /allow microphone capture/i,
    })

    expect(checkbox).not.toBeChecked()

    await user.click(checkbox)

    expect(checkbox).toBeChecked()
    expect(screen.getByText('ON')).toBeInTheDocument()
  })
})
