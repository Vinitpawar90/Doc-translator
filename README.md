# Translation App

## Project layout

- `frontend/` contains the Streamlit translation UI and admin dashboard.
- `backend/` contains the FastAPI service, database models, and API-key helpers.
- `outputs/` stores translated documents.
- `.env` and `translation.db` remain in the project root.

Run commands from the project root so `.env`, the database, and `outputs/`
resolve to their existing locations.

## Run the frontend

```powershell
streamlit run frontend\main.py
```

To open the admin dashboard:

```powershell
streamlit run frontend\admin_dashboard.py
```

## Run the backend

```powershell
uvicorn backend.api:app --reload
```

The backend requires `DEEPL_API_KEY` in the root `.env` file.

## Run the Streamlit frontend with Docker

Build the image from the project root:

```powershell
docker build -t translation-app .
```

Run it with your root `.env` file (which must define `DEEPL_API_KEY`):

```powershell
docker run --rm -p 8501:8501 --env-file .env translation-app
```

Open [http://localhost:8501](http://localhost:8501). The image runs the
Streamlit frontend only; run the FastAPI backend separately if you need it.
Secrets and local database files are excluded from the build context.
