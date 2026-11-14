
export type WorkflowStepStatus =
  | 'pending'
  | 'in-progress'
  | 'completed'
  | 'failed'

export type WorkflowStep = {
  id: number
  title: string
  description: string
  status: WorkflowStepStatus
}

type WorkflowProgressProps = {
  steps: WorkflowStep[]
}

function WorkflowProgress({ steps }: WorkflowProgressProps) {
  return (
    <section aria-labelledby="workflow-heading">
      <h2 id="workflow-heading">Workflow Progress</h2>

      <ol className="workflow-list" aria-live="polite">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={`workflow-step ${step.status}`}
          >
            <span className="workflow-step-number">
              {index + 1}
            </span>

            <div className="workflow-step-content">
              <h3>{step.title}</h3>
              <p>{step.description}</p>

              <span className="workflow-step-status">
                {step.status.replace('-', ' ').toUpperCase()}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

export default WorkflowProgress
