
import { useEffect, useRef } from 'react'

type ApprovalDialogProps = {
  open: boolean
  onApprove: () => void
  onReject: () => void
}

function ApprovalDialog({
  open,
  onApprove,
  onReject,
}: ApprovalDialogProps) {
  const dialogRef = useRef<HTMLElement>(null)
  const approveButtonRef = useRef<HTMLButtonElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return

    previousFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null

    approveButtonRef.current?.focus()

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onReject()
        return
      }

      if (event.key !== 'Tab') return

      const dialog = dialogRef.current
      if (!dialog) return

      const focusableElements = dialog.querySelectorAll<HTMLElement>(
        'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
      )

      if (focusableElements.length === 0) {
        event.preventDefault()
        return
      }

      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]

      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault()
        lastElement.focus()
      } else if (
        !event.shiftKey &&
        document.activeElement === lastElement
      ) {
        event.preventDefault()
        firstElement.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      previousFocusRef.current?.focus()
    }
  }, [open, onReject])

  if (!open) return null

  return (
    <div className="approval-overlay">
      <section
        ref={dialogRef}
        className="approval-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="approval-title"
        aria-describedby="approval-description"
        tabIndex={-1}
      >
        <h2 id="approval-title">Workflow Approval Required</h2>

        <p id="approval-description">
          Review this action before proceeding.
        </p>

        <div className="approval-risk">
          <strong>Risk Explanation</strong>
          <p>
            Approving allows the workflow to proceed.
            Rejecting cancels the request and must not execute
            the proposed action.
          </p>
        </div>

        <div className="approval-actions">
          <button
            ref={approveButtonRef}
            type="button"
            onClick={onApprove}
          >
            Approve
          </button>

          <button type="button" onClick={onReject}>
            Reject
          </button>
        </div>
      </section>
    </div>
  )
}

export default ApprovalDialog
