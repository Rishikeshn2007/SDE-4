
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ApprovalDialog from './ApprovalDialog'

describe('ApprovalDialog', () => {
  it('shows the risk explanation', () => {
    render(
      <ApprovalDialog
        open={true}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    )

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(/risk explanation/i)).toBeInTheDocument()
    expect(screen.getByText(/rejecting cancels the request/i)).toBeInTheDocument()
  })

  it('calls the approve handler when Approve is clicked', () => {
    const onApprove = vi.fn()
    const onReject = vi.fn()

    render(
      <ApprovalDialog
        open={true}
        onApprove={onApprove}
        onReject={onReject}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /approve/i }))

    expect(onApprove).toHaveBeenCalledTimes(1)
    expect(onReject).not.toHaveBeenCalled()
  })

  it('calls only the reject handler when Reject is clicked', () => {
    const onApprove = vi.fn()
    const onReject = vi.fn()

    render(
      <ApprovalDialog
        open={true}
        onApprove={onApprove}
        onReject={onReject}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /reject/i }))

    expect(onReject).toHaveBeenCalledTimes(1)
    expect(onApprove).not.toHaveBeenCalled()
  })

  it('moves focus to Approve when the dialog opens', () => {
    render(
      <ApprovalDialog
        open={true}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: /approve/i }))
      .toHaveFocus()
  })

  it('keeps keyboard focus inside the dialog', () => {
    render(
      <ApprovalDialog
        open={true}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    )

    const approve = screen.getByRole('button', { name: /approve/i })
    const reject = screen.getByRole('button', { name: /reject/i })

    reject.focus()
    fireEvent.keyDown(reject, { key: 'Tab' })

    expect(approve).toHaveFocus()

    fireEvent.keyDown(approve, { key: 'Tab', shiftKey: true })

    expect(reject).toHaveFocus()
  })

  it('rejects the dialog when Escape is pressed', () => {
    const onReject = vi.fn()

    render(
      <ApprovalDialog
        open={true}
        onApprove={vi.fn()}
        onReject={onReject}
      />,
    )

    fireEvent.keyDown(screen.getByRole('dialog'), {
      key: 'Escape',
    })

    expect(onReject).toHaveBeenCalledTimes(1)
  })
})
