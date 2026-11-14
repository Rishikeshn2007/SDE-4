
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => {
  vi.useRealTimers()
})

describe('Session Studio', () => {
  it('renders the application heading', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /session studio/i,
      }),
    ).toBeInTheDocument()
  })

  it('shows the mock mode banner', () => {
    render(<App />)

    expect(screen.getByText(/mock mode:/i)).toBeInTheDocument()
  })

  it('reconnects and replays missed events without duplicates', () => {
    vi.useFakeTimers()
    render(<App />)

    fireEvent.click(
      screen.getByRole('button', {
        name: /load mock transcript/i,
      }),
    )

    act(() => {
      vi.advanceTimersByTime(3000)
    })

    act(() => {
      window.dispatchEvent(new Event('offline'))
    })

    expect(screen.getByText('DISCONNECTED')).toBeInTheDocument()

    act(() => {
      window.dispatchEvent(new Event('online'))
    })

    expect(screen.getByText('CONNECTED')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(12000)
    })

    expect(screen.getByText('CLOSED')).toBeInTheDocument()

    const eventLabel = screen.getByText('▥ Transcript Events')
    const eventCount = eventLabel.parentElement?.querySelector('strong')

    expect(eventCount).toHaveTextContent('4')
    expect(
      screen.getByText(/3 transcript segments loaded/i),
    ).toBeInTheDocument()
  })

  it('completes the workflow and rejects approval without execution', () => {
    vi.useFakeTimers()
    render(<App />)

    fireEvent.click(
      screen.getByRole('button', {
        name: /load mock transcript/i,
      }),
    )

    // Allow all mock events to arrive and the stream to close.
    act(() => {
      vi.advanceTimersByTime(15000)
    })

    // Approval should now be available.
    const reviewButton = screen.getByRole('button', {
      name: /review approval/i,
    })

    expect(reviewButton).toBeEnabled()

    fireEvent.click(reviewButton)

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(
      screen.getByText(/risk explanation/i),
    ).toBeInTheDocument()

    // Reject the proposed action.
    fireEvent.click(
      screen.getByRole('button', {
        name: /reject/i,
      }),
    )

    expect(
      screen.getByText(/rejected\. no action was executed/i),
    ).toBeInTheDocument()

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('FAILED')).toBeInTheDocument()
  })
})
