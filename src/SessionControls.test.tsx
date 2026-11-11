import { useState } from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SessionControls from './components/SessionControls'


describe('SessionControls', () => {
  it('shows CAPTURING when session is running', () => {
    render(
      <SessionControls status="Running" setStatus={vi.fn()} />,
    )

    expect(screen.getByText('CAPTURING')).toBeInTheDocument()
  })

  it('pauses the session and updates the status', () => {
    const setStatus = vi.fn()

    render(
      <SessionControls status="Running" setStatus={setStatus} />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Pause session' }))

    expect(setStatus).toHaveBeenCalledWith('Paused')
  })

  it('shows PAUSED when session is paused', () => {
    render(
      <SessionControls status="Paused" setStatus={vi.fn()} />,
    )

    expect(screen.getByText('PAUSED')).toBeInTheDocument()
  })

  it('resumes the session and updates the status', () => {
    const setStatus = vi.fn()

    render(
      <SessionControls status="Paused" setStatus={setStatus} />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Resume session' }))

    expect(setStatus).toHaveBeenCalledWith('Running')
  })
    it('keeps the capture indicator in sync when pausing and resuming', () => {
    function TestSessionControls() {
      const [status, setStatus] = useState<
  'Idle' | 'Running' | 'Paused' | 'Stopped'
>('Running')

      return (
        <SessionControls status={status} setStatus={setStatus} />
      )
    }

    render(<TestSessionControls />)

    expect(screen.getByText('CAPTURING')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Pause session' }))

    expect(screen.getByText('PAUSED')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Resume session' }))

    expect(screen.getByText('CAPTURING')).toBeInTheDocument()
  })
})
