
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import TranscriptTimeline from './components/TranscriptTimeline'
import type { TranscriptEvent } from './api/sessionApi'

describe('TranscriptTimeline', () => {
  it('displays transcript events in the supplied order', () => {
    const events: TranscriptEvent[] = [
      {
        id: 1,
        segmentId: 1,
        timestamp: '10:00:01',
        text: 'First event',
        status: 'final',
        revision: 1,
        confidence: 95,
      },
      {
        id: 2,
        segmentId: 2,
        timestamp: '10:00:05',
        text: 'Second event',
        status: 'final',
        revision: 1,
        confidence: 94,
      },
      {
        id: 3,
        segmentId: 3,
        timestamp: '10:00:10',
        text: 'Third event',
        status: 'final',
        revision: 1,
        confidence: 98,
      },
    ]

    const { container } = render(
      <TranscriptTimeline
        events={events}
        apiError=""
        onLoad={vi.fn()}
      />,
    )

    const items = container.querySelectorAll('ol.timeline > li')

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
