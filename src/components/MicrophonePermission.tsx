type MicrophoneStatus = 'Prompt' | 'Granted' | 'Denied' | 'Unsupported'

type MicrophonePermissionProps = {
  status: MicrophoneStatus
  message: string
  onRequest: () => void
}

function MicrophonePermission({
  status,
  message,
  onRequest,
}: MicrophonePermissionProps) {
  return (
    <section className="panel" aria-labelledby="microphone-heading">
      <h2 id="microphone-heading">Microphone Permission</h2>

      <p>
        Permission status: <strong>{status}</strong>
      </p>

      <p className="muted" role="status">
        {message}
      </p>

      <button onClick={onRequest}>
        Request Microphone Permission
      </button>
    </section>
  )
}

export default MicrophonePermission