import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import ContextPanel from './components/ContextPanel'

describe('ContextPanel', () => {
  it('shows screen context OFF by default', () => {
    render(<ContextPanel />)

    expect(screen.getByRole('checkbox')).not.toBeChecked()
    expect(screen.getByRole('status')).toHaveTextContent('OFF')
  })

  it('enables screen context when selected', async () => {
    const user = userEvent.setup()

    render(<ContextPanel />)

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

    render(<ContextPanel />)

    const checkbox = screen.getByRole('checkbox')

    await user.click(checkbox)
    await user.click(checkbox)

    expect(checkbox).not.toBeChecked()
    expect(screen.getByRole('status')).toHaveTextContent('OFF')
  })
})