\# SDE-4 Backend



\## Project Overview



SDE-4 is a backend project developed using Python and FastAPI.



It provides session management, session state transitions, event handling, request correlation IDs, structured logging, and health monitoring.



\## Technologies Used



\- Python 3.12

\- FastAPI

\- Uvicorn

\- Pytest

\- HTTPX



\## Project Structure



```text

SDE-4/

│

├── backend/

│   ├── app/

│   │   ├── config.py

│   │   ├── errors.py

│   │   ├── events.py

│   │   ├── logging\_config.py

│   │   ├── main.py

│   │   ├── middleware.py

│   │   └── sessions.py

│   │

│   ├── tests/

│   │   └── test\_api.py

│   │

│   ├── requirements.txt

│   └── run\_mock.ps1

│

└── README.md
## Running the Backend in Mock Mode

Make sure Python 3.12 and the backend dependencies are installed.

From the project root directory, run:

```bash
python backend/run_mock.py