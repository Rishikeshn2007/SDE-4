
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import MicrophonePermission from './components/MicrophonePermission'

describe('MicrophonePermission', () => {
  it.each(['Prompt', 'Granted', 'Denied'] as const)(
    'displays the %s permission state',
    (status) => {
      render(
        <MicrophonePermission
          status={status}
          message={`Microphone permission: ${status}`}
          onRequest={vi.fn()}
        />,
      )

      expect(screen.getByText(status)).toBeInTheDocument()
    },
  )

  it('calls onRequest when the permission button is clicked', async () => {
    const user = userEvent.setup()
    const onRequest = vi.fn()

    render(
      <MicrophonePermission
        status="Prompt"
        message="Permission is required"
        onRequest={onRequest}
      />,
    )

    await user.click(
      screen.getByRole('button', {
        name: /request microphone permission/i,
      }),
    )

    expect(onRequest).toHaveBeenCalledTimes(1)
  })
})
