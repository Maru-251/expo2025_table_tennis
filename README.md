# Expo 2025 Table Tennis Notes

This project is a small demo application built with **FastAPI**, **SQLModel** and **Jinja2**. It was created to experiment with a travel memo site for the 2025 Osaka/Kansai Expo. Users can register, log in and manage personal notes.

## Requirements

- Python 3.11 or later
- The following Python packages:
  - `fastapi`
  - `uvicorn`
  - `sqlmodel`
  - `python-multipart`
  - `passlib[bcrypt]`
  - `python-jose[cryptography]`
  - `jinja2`

Create and activate a virtual environment, then install the dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sqlmodel python-multipart passlib[bcrypt] python-jose[cryptography] jinja2
```

## Database initialization

The app uses SQLite (`database.db`). Tables are created automatically on startup. If the schema changes, delete `database.db` before running the server so that a fresh database is generated.

## Running the server

Launch the development server with auto-reload enabled:

```bash
uvicorn main:app --reload
```

Visit `http://localhost:8000` in your browser to access the site.

