
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import TranscriptTimeline from './components/TranscriptTimeline'

describe('TranscriptTimeline', () => {
  it('displays transcript events in the supplied order', () => {
    const events = [
      { id: 1, timestamp: '10:00:01', text: 'First event' },
      { id: 2, timestamp: '10:00:05', text: 'Second event' },
      { id: 3, timestamp: '10:00:10', text: 'Third event' },
    ]

    render(
      <TranscriptTimeline
        events={events}
        apiError=""
        onLoad={vi.fn()}
      />,
    )

    const items = screen.getAllByRole('listitem')

    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent('First event')
    expect(items[1]).toHaveTextContent('Second event')
    expect(items[2]).toHaveTextContent('Third event')
  })

  it('displays an API error message', () => {
    render(
      <TranscriptTimeline
        events={[]}
        apiError="Failed to load transcript"
        onLoad={vi.fn()}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Failed to load transcript',
    )
  })

  it('calls onLoad when the load button is clicked', async () => {
    const user = userEvent.setup()
    const onLoad = vi.fn()

    render(
      <TranscriptTimeline
        events={[]}
        apiError=""
        onLoad={onLoad}
      />,
    )

    await user.click(
      screen.getByRole('button', {
        name: /load mock transcript/i,
      }),
    )

    expect(onLoad).toHaveBeenCalledTimes(1)
  })
})
