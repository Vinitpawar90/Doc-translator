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
The frontend's feedback form posts ratings and optional comments to
`http://localhost:8000/feedback` by default. Set `FEEDBACK_API_URL` in the
frontend environment to the backend's reachable `/feedback` URL when they run
on different hosts or in separate containers. Feedback is saved in the shared
database.

`POST /feedback` accepts a required `message` of up to 1,000 characters and an
optional PNG or JPEG screenshot up to 5 MB. Messages are stored in
`feedback_messages` and screenshots in `feedback_attachments`. Successful
submissions return HTTP 201 with the saved feedback ID.

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
