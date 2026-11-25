import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

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

  it('shows the mock session notice', () => {
    render(<App />)

    expect(screen.getByText(/Session Studio:/i)).toBeInTheDocument()
    expect(
      screen.getByText(/Mock transcripts and optional microphone transcription/i),
    ).toBeInTheDocument()
  })
})
