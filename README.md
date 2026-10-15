# Voter List Site
Flask + SQLite. Login is checked server-side; all voter data is served only via authenticated /api routes.
Deploy on Render: New > Blueprint > pick this repo (uses render.yaml, free Docker web service).
Data lives in Postgres (e.g. free Neon) via DATABASE_URL; set it in Render. Without it the app falls back to local SQLite (app/voters.db, not committed). Load parsed data with: DATABASE_URL=... python3 load.py
