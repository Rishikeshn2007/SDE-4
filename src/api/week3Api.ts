export type ContextItem = {
  item_id: string
  content: string
  source: {
    source_id: string
    source_type: string
    description: string
  }
}

export type AnswerResponse = {
  status: string
  request_id: string
  answer: string
  source_ids: string[]
}

export type WorkflowProposal = {
  proposal_id: string
  action_type: string
  description: string
  source_ids: string[]
  requires_confirmation: boolean
  status: string
}

export type ProposalResponse = {
  handoff: {
    accepted: boolean
    executed: boolean
  }
  proposal: WorkflowProposal
}

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.error || data.message || 'Backend request failed')
  }

  return data as T
}

function createContextPayload(context: ContextItem[]) {
  return {
    context_id: 'frontend_synthetic_context',
    items: context,
  }
}

export function getGroundedAnswer(
  question: string,
  context: ContextItem[],
): Promise<AnswerResponse> {
  return apiRequest<AnswerResponse>('/context/answer', {
    method: 'POST',
    body: JSON.stringify({
      request_id: `request_${Date.now()}`,
      question,
      context: createContextPayload(context),
    }),
  })
}

export function createWorkflowProposal(
  question: string,
  context: ContextItem[],
  actionType: string,
  description: string,
): Promise<ProposalResponse> {
  return apiRequest<ProposalResponse>('/workflow/proposals', {
    method: 'POST',
    body: JSON.stringify({
      request_id: `workflow_${Date.now()}`,
      question,
      context: createContextPayload(context),
      action_type: actionType,
      description,
      source_ids: [...new Set(
        context.map((item) => item.source.source_id),
      )],
    }),
  })
}

export function getPendingProposals(): Promise<{
  proposals: WorkflowProposal[]
}> {
  return apiRequest('/workflow/proposals')
}

export function approveProposal(
  proposalId: string,
): Promise<{ approved: boolean; executed: boolean; status: string }> {
  return apiRequest(
    `/workflow/proposals/${encodeURIComponent(proposalId)}/approve`,
    { method: 'POST' },
  )
}

export function rejectProposal(
  proposalId: string,
): Promise<{ rejected: boolean; executed: boolean; status: string }> {
  return apiRequest(
    `/workflow/proposals/${encodeURIComponent(proposalId)}/reject`,
    { method: 'POST' },
  )
}