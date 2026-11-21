import { useEffect, useState } from 'react'
import {
  getGroundedAnswer,
  createWorkflowProposal,
  getPendingProposals,
  approveProposal,
  rejectProposal,
  type ContextItem,
  type WorkflowProposal,
} from '../api/week3Api'

const sampleContext: ContextItem[] = [
  {
    item_id: 'item_001',
    content: 'The project uses Python.',
    source: {
      source_id: 'source_001',
      source_type: 'synthetic',
      description: 'Synthetic project information',
    },
  },
  {
    item_id: 'item_002',
    content: 'The project includes automated unit tests.',
    source: {
      source_id: 'source_002',
      source_type: 'synthetic',
      description: 'Synthetic testing information',
    },
  },
]

function ReasoningWorkflowPanel() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [sourceIds, setSourceIds] = useState<string[]>([])
  const [actionType, setActionType] = useState('create_note')
  const [description, setDescription] = useState('')
  const [proposals, setProposals] = useState<WorkflowProposal[]>([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function loadProposals() {
    try {
      const result = await getPendingProposals()
      setProposals(result.proposals)
    } catch {
      setError('Could not load workflow proposals. Check the backend server.')
    }
  }

  useEffect(() => {
    void loadProposals()
  }, [])

  async function handleAskQuestion() {
    if (!question.trim()) {
      setError('Please enter a question.')
      return
    }

    setLoading(true)
    setError('')
    setMessage('')
    setAnswer('')
    setSourceIds([])

    try {
      const result = await getGroundedAnswer(question, sampleContext)
      setAnswer(result.answer)
      setSourceIds(result.source_ids)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not get an answer.')
    } finally {
      setLoading(false)
    }
  }

  async function handleCreateProposal() {
    if (!question.trim() || !description.trim()) {
      setError('Enter a question and a proposal description first.')
      return
    }

    setLoading(true)
    setError('')
    setMessage('')

    try {
      const result = await createWorkflowProposal(
        question,
        sampleContext,
        actionType,
        description,
      )

      if (result.handoff.accepted) {
        setMessage('Proposal created and submitted for approval.')
        setDescription('')
        await loadProposals()
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not create the proposal.',
      )
    } finally {
      setLoading(false)
    }
  }

  async function handleApprove(id: string) {
    setError('')
    setMessage('')

    try {
      const result = await approveProposal(id)
      setMessage(
        result.executed
          ? 'Proposal approved and executed.'
          : 'Proposal approved. No real-world action was executed (mock mode).',
      )
      await loadProposals()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approval failed.')
    }
  }

  async function handleReject(id: string) {
    setError('')
    setMessage('')

    try {
      await rejectProposal(id)
      setMessage('Proposal rejected.')
      await loadProposals()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rejection failed.')
    }
  }

  return (
    <section className="panel reasoning-panel">
      <h2>Grounded Answers &amp; Workflow</h2>

      <p className="muted">
        Ask questions using synthetic context and review source-linked answers.
      </p>

      <div className="week3-section">
        <h3>1. Grounded Question Answering</h3>

        <label htmlFor="week3-question">Your question</label>
        <textarea
          id="week3-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Example: Which programming language does the project use?"
          rows={3}
        />

        <button onClick={handleAskQuestion} disabled={loading}>
          {loading ? 'Processing...' : 'Get Grounded Answer'}
        </button>

        {answer && (
          <div className="week3-result" aria-live="polite">
            <h4>Answer</h4>
            <p>{answer}</p>

            <h4>Supporting Sources</h4>
            {sourceIds.length > 0 ? (
              <ul>
                {sourceIds.map((id) => (
                  <li key={id}>{id}</li>
                ))}
              </ul>
            ) : (
              <p>No supporting sources were returned.</p>
            )}
          </div>
        )}
      </div>

      <div className="week3-section">
        <h3>2. Workflow Proposal</h3>

        <label htmlFor="week3-action">Action type</label>
        <select
          id="week3-action"
          value={actionType}
          onChange={(event) => setActionType(event.target.value)}
        >
          <option value="summarize">Summarize</option>
          <option value="create_note">Create Note</option>
          <option value="draft_message">Draft Message</option>
          <option value="organize_task">Organize Task</option>
        </select>

        <label htmlFor="week3-description">Proposal description</label>
        <textarea
          id="week3-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Describe the proposed action..."
          rows={3}
        />

        <button onClick={handleCreateProposal} disabled={loading}>
          Create Workflow Proposal
        </button>

        <p className="muted">
          Proposals require your approval. Approval does not execute real
          actions in mock mode.
        </p>
      </div>

      <div className="week3-section">
        <h3>3. Pending Approval</h3>

        {proposals.length === 0 ? (
          <p className="muted">No pending proposals.</p>
        ) : (
          proposals.map((proposal) => (
            <div className="week3-proposal" key={proposal.proposal_id}>
              <h4>{proposal.action_type}</h4>
              <p>{proposal.description}</p>
              <p>
                <strong>Proposal ID:</strong> {proposal.proposal_id}
              </p>
              <p>
                <strong>Status:</strong> {proposal.status}
              </p>

              <div className="buttons">
                <button onClick={() => handleApprove(proposal.proposal_id)}>
                  Approve
                </button>
                <button
                  className="reject-button"
                  onClick={() => handleReject(proposal.proposal_id)}
                >
                  Reject
                </button>
              </div>
            </div>
          ))
        )}

        <button className="secondary-button" onClick={loadProposals}>
          Refresh Proposals
        </button>
      </div>

      {message && <p className="week3-message" role="status">{message}</p>}
      {error && <p className="week3-error" role="alert">{error}</p>}
    </section>
  )
}

export default ReasoningWorkflowPanel