
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

  it('shows the mock mode banner', () => {
    render(<App />)

    expect(
      screen.getByText(/mock mode:/i),
    ).toBeInTheDocument()
  })
})
