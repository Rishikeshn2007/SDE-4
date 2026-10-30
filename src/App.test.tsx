
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

describe('Session Studio', () => {
  it('renders the application heading', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: /session studio/i })
    ).toBeInTheDocument()
  })

  it('shows the mock mode banner', () => {
    render(<App />)

    expect(
      screen.getByText('MOCK MODE ON')
    ).toBeInTheDocument()
  })
})
