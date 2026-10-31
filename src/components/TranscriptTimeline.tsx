export type TranscriptEvent = {
  id: number
  timestamp: string
  text: string
}

type TranscriptTimelineProps = {
  events: TranscriptEvent[]
  apiError: string
  onLoad: () => void
}

function TranscriptTimeline({
  events,
  apiError,
  onLoad,
}: TranscriptTimelineProps) {
  return (
    <section className="panel" aria-labelledby="transcript-heading">
      <h2 id="transcript-heading">Transcript Timeline</h2>

      <p className="muted">
        Transcript events are loaded from mock fixture data.
      </p>

      <button onClick={onLoad}>
        Load Mock Transcript
      </button>

      {apiError && <p role="alert">{apiError}</p>}

      {events.length === 0 ? (
        <p className="muted">No transcript events loaded yet.</p>
      ) : (
        <ol className="timeline">
          {events.map((event) => (
            <li key={event.id}>
              <time>{event.timestamp}</time>
              <p>{event.text}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

export default TranscriptTimeline