# Voter List Site
Flask + SQLite. Login is checked server-side; all voter data is served only via authenticated /api routes.
Deploy on Render: New > Blueprint > pick this repo (uses render.yaml, free Docker web service).
Note: Render free tier has no persistent disk; the bundled app/voters.db is the data source. Uploads/new constituencies added in the UI are lost when the free instance restarts or redeploys.
