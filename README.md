# Translation App

## Project layout

- `frontend/` contains the Streamlit translation UI and admin dashboard.
- `backend/` contains the FastAPI service, database models, and API-key helpers.
- `outputs/` stores translated documents.
- `.env` stores local secrets and connection strings. `translation.db` is the
  local SQLite fallback.

Run commands from the project root so `.env`, the database, and `outputs/`
resolve to their existing locations. The app reads `DATABASE_URL` from `.env`
for Neon/PostgreSQL and falls back to local SQLite when it is not configured.
Keep `.env` private; it contains database credentials.

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

The backend requires `DEEPL_API_KEY` in the root `.env` file. Neon CLI setup
stores the linked project's database connection variables there as well.

## Run the Streamlit frontend with Docker

Build the image from the project root:

```powershell
docker build -t translation-app .
```

Run it with your root `.env` file (which must define `DEEPL_API_KEY` and the
Neon `DATABASE_URL` when using PostgreSQL):

```powershell
docker run --rm -p 8501:8501 --env-file .env translation-app
```

Open [http://localhost:8501](http://localhost:8501). The image runs the
Streamlit frontend only; run the FastAPI backend separately if you need it.
Secrets and local database files are excluded from the build context.
