
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
  if (!open) return null

  return (
    <div className="approval-overlay">
      <section
        className="approval-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="approval-title"
        aria-describedby="approval-description"
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
          <button type="button" onClick={onApprove}>
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
