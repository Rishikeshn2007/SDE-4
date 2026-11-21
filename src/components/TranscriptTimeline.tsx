
import type { TranscriptEvent } from '../api/sessionApi'

export type { TranscriptEvent } from '../api/sessionApi'

type TranscriptTimelineProps = {
  events: TranscriptEvent[]
  apiError: string
  onLoad: () => void
  isLoading?: boolean
  isOffline?: boolean
}

function TranscriptTimeline({
  events,
  apiError,
  onLoad,
  isLoading = false,
  isOffline = false,
}: TranscriptTimelineProps) {
  const groupedEvents = new Map<number, TranscriptEvent[]>()

  events.forEach((event) => {
    const existing = groupedEvents.get(event.segmentId) ?? []
    groupedEvents.set(event.segmentId, [...existing, event])
  })

  const segments = Array.from(groupedEvents.values()).map((revisions) => {
    const orderedRevisions = [...revisions].sort(
      (a, b) => a.revision - b.revision,
    )

    const finalVersions = orderedRevisions.filter(
      (event) => event.status === 'final',
    )

    const current =
      finalVersions[finalVersions.length - 1] ??
      orderedRevisions[orderedRevisions.length - 1]

    return { current, revisions: orderedRevisions }
  })

  return (
    <section className="panel" aria-labelledby="transcript-heading">
      <h2 id="transcript-heading">Transcript Timeline</h2>

      <p className="muted">
        View interim and final transcript segments, revisions, and confidence.
      </p>

      <button type="button" onClick={onLoad} disabled={isLoading}>
        {isLoading ? 'Loading Transcript...' : 'Load Mock Transcript'}
      </button>

      {isLoading && (
        <p role="status" aria-live="polite">
          Loading transcript. Please wait.
        </p>
      )}

      {isOffline && (
        <p role="status" aria-live="polite">
          You are offline. The backend cannot be reached. Check your internet
          connection and try again.
        </p>
      )}

      {apiError && (
        <p role="alert" aria-live="assertive">
          {apiError}
        </p>
      )}

      {events.length === 0 ? (
        <p className="muted">No transcript events loaded yet.</p>
      ) : (
        <ol className="timeline" aria-label="Transcript segments">
          {segments.map(({ current, revisions }) => (
            <li key={current.segmentId}>
              <time>{current.timestamp}</time>
              <p>{current.text}</p>

              <p>
                <strong>Status: </strong>
                <span>{current.status.toUpperCase()}</span>
              </p>

              <p>
                <strong>Confidence: </strong>
                {current.confidence}%
              </p>

              <div className="revision-history">
                <strong>Revision History</strong>
                <ul>
                  {revisions.map((revision) => (
                    <li key={revision.id}>
                      <span>
                        Revision {revision.revision} ({revision.status})
                      </span>
                      <p>{revision.text}</p>
                      <small>Confidence: {revision.confidence}%</small>
                    </li>
                  ))}
                </ul>
              </div>
            </li>
          ))}
        </ol>
      )}

      <div
        className="sr-only"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {events.length > 0
          ? `${segments.length} transcript segments loaded.`
          : ''}
      </div>
    </section>
  )
}

export default TranscriptTimeline
