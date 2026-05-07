# SCALE India Investment

Dockerized local setup for the frontend, backend, and MongoDB.

## Run with Docker

1. Review `backend/.env` for local defaults, or use `backend/.env.example` as a clean template. Add real values for any optional integrations you want, especially `OPENAI_API_KEY` and `BREVO_API_KEY`.
2. Start the stack:

```bash
docker compose up --build
```

3. Open:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8001/api/`
- MongoDB: `mongodb://localhost:27017`

## Notes

- The backend now works without any hosted third-party scaffolding dependency.
- If `OPENAI_API_KEY` is empty, MarketBot falls back to offline deterministic responses so the app still boots cleanly.
- The frontend is served by Nginx and is prebuilt against `http://localhost:8001`.
