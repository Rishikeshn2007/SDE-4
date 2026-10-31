# Session Studio

**Team SDE 4 – Workstream W6: Frontend and UX**

## Project Overview

Session Studio is an accessible frontend dashboard for managing voice sessions in mock mode. It demonstrates session controls, microphone permission states, and a transcript timeline using mock fixture data.

Mock mode is enabled by default. No real audio is recorded or uploaded.

## Features

- Accessible application layout with a skip link.
- Mock-mode status banner.
- Session controls: Start, Pause, and Stop.
- Microphone permission states.
- Mock transcript timeline.
- Typed API client with mock responses.
- API error handling.
- Component-based React architecture.

## Technologies Used

- React
- TypeScript
- Vite
- Vitest
- React Testing Library
- CSS

## Project Setup

Install dependencies:

```bash
npm.cmd install
```

Start the development server:

```bash
npm.cmd run dev
```

## Running Tests

```bash
npm.cmd test
```

## Production Build

```bash
npm.cmd run build
```

## Testing

The project includes tests for:

- Mock session API responses.
- Transcript event timestamp ordering.
- Application heading.
- Mock-mode banner.

## Important Note

This is a frontend mock-mode demonstration. Microphone permission is requested only to demonstrate browser permission states. The microphone stream is stopped immediately, and no audio is recorded or uploaded.