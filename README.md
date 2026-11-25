# SDE-4 – Agentic Workflow and Session Studio

## W4 – Agentic Workflow

### Project Overview

A Python project demonstrating an agentic workflow.

### Features

- Workflow plan and step definitions
- Workflow state management
- Plan validation
- Mock calculator
- Mock note preview
- Human approval for consequential steps
- Safe mock-only execution

### Technologies

- Python
- Pytest

### Run the Demo

```bash
py demo.py
```

### Run Tests

```bash
py -m pytest tests -v
```

### Safety

Only mock tools are used. Consequential steps require explicit approval.

---

## W6 – Session Studio

**Team SDE 4 – Workstream W6: Frontend and UX**

### Project Overview

Session Studio is an accessible frontend dashboard for managing voice sessions in mock mode. It demonstrates session controls, microphone permission states, and a transcript timeline using mock fixture data.

Mock mode is enabled by default. No real audio is recorded or uploaded.

### Features

- Accessible application layout with a skip link.
- Mock-mode status banner.
- Session controls: Start, Pause, and Stop.
- Microphone permission states.
- Mock transcript timeline.
- Typed API client with mock responses.
- API error handling.
- Backend mock session and event stream integration.
- Privacy settings for screen context and microphone capture.
- Component-based React architecture.

### Technologies Used

- React
- TypeScript
- Vite
- Vitest
- React Testing Library
- CSS
- FastAPI mock backend

### Project Setup

Install dependencies:

```bash
npm.cmd install
```

Start the development server:

```bash
npm.cmd run dev
```

### Running Tests

```bash
npm.cmd test
```

### Production Build

```bash
npm.cmd run build
```

### Testing

The project includes tests for:

- Mock session API responses.
- Transcript event timestamp ordering.
- Application heading.
- Mock-mode banner.
- Privacy settings.
- Approval rejection without execution.

### Important Note

This is a frontend mock-mode demonstration. Microphone permission is requested only through a separate user action, and the microphone stream is stopped immediately. No audio is recorded or uploaded.

The screen context setting is a user preference; screen capture is not implemented. The backend mock session integration uses the FastAPI development server.
## Troubleshooting

For help with microphone permissions, backend connection issues, event stream reconnection, and demo mode, see the [Troubleshooting Guide](./TROUBLESHOOTING.md).
