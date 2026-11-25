# Troubleshooting Guide – Session Studio

## 1. Microphone Permission Problems

**Problem:** Microphone permission is denied or unavailable.

**What to do:**
1. Open the application in a supported browser.
2. Select **Request Microphone Permission**.
3. If permission is denied, open your browser's site permissions.
4. Allow microphone access for the application.
5. Return to the application and try again.

**Possible messages:**
- `Permission has not been requested.`
- `Permission denied. Check your browser permissions.`
- `Microphone permission is not supported in this browser.`

**Privacy note:** Microphone permission is requested only through a separate user action. The application does not record or upload audio.

## 2. Backend Offline or Unavailable

**Problem:** The application cannot connect to the FastAPI mock backend.

**What to do:**
1. Check that your internet or local network connection is working.
2. Make sure the FastAPI development server is running.
3. Open `http://127.0.0.1:8000/docs` to check whether the backend is available.
4. Return to Session Studio.
5. Try **Start Backend Mock Session** again.

If the backend is unavailable, the application may display:
- `You are offline. Please reconnect.`
- `Could not connect to the backend.`

## 3. Event Stream Disconnection and Reconnection

**Problem:** The event stream disconnects or stops receiving events.

**What to do:**
1. Check your network connection.
2. Wait for the connection to recover.
3. The application listens for browser online and offline events.
4. When the connection returns, the mock event stream resumes from the last received event.
5. Check the Backend Event Stream section for updated events and connection status.

For backend event streaming, the API client supports reconnection and uses the `Last-Event-ID` header to request events after the last received event.

## 4. Using Mock/Demo Mode

**Problem:** You want to demonstrate the application without a running backend.

**What to do:**
1. Start the frontend development server.
2. Open the application in your browser.
3. Check the Mock Mode banner.
4. Use the session controls to Start, Pause, Resume and Stop.
5. Select **Load Mock Transcript** to demonstrate the transcript and workflow.
6. Review the approval step and demonstrate both approval and rejection.

Mock mode is enabled by default. It uses simulated session data and does not require backend keys.

## 5. Privacy and Data Safety

- Screen context is OFF by default.
- Microphone capture is OFF by default.
- Changing the microphone capture preference does not request microphone permission or start recording.
- Microphone permission is requested separately.
- No real audio is recorded or uploaded in this mock-mode demonstration.

## 6. Still Having Problems?

If the problem continues:

1. Check the terminal for frontend or backend errors.
2. Confirm that the frontend and backend development servers are running.
3. Refresh the application.
4. Review the error message displayed in the application.
5. Restart the development servers if necessary.