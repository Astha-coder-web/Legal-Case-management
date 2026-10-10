# LegalSmart

LegalSmart is a React/Vite frontend with a FastAPI authentication API backed by MongoDB.

## Local setup

Requirements: Node.js, Python 3.11+, and a reachable MongoDB instance (local MongoDB or MongoDB Atlas).

1. Configure the API environment:

   ```powershell
   Copy-Item backend\.env.example backend\.env
   ```

   Edit `backend\.env` and set `MONGODB_URI` to your MongoDB connection string. Replace `JWT_SECRET` with a random secret of at least 32 characters; for example:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

2. Install and start the API from the project root:

   ```powershell
   py -m venv backend\.venv
   backend\.venv\Scripts\Activate.ps1
   pip install -r backend\requirements.txt
   uvicorn backend.main:app --reload
   ```

3. In a second terminal, install and start the frontend:

   ```powershell
   npm install
   npm run dev
   ```

   Vite proxies `/api` to the local API on port 8000. Use the frontend URL printed by Vite. To use a different API URL, set `VITE_API_URL` in a frontend `.env` file.

## Authentication

- `POST /api/auth/signup` stores a normalized email, display name, and Argon2 password hash in MongoDB. Plain-text passwords are never stored.
- `POST /api/auth/login` verifies the password, signs a short-lived JWT, and stores a hash of that token as a MongoDB session.
- `GET /api/auth/me` verifies the JWT signature and expiry, then checks that its matching session is still active in MongoDB before returning the user.
- `POST /api/auth/logout` revokes the MongoDB session and clears the HTTP-only cookie.

The JWT is kept in an HTTP-only cookie rather than browser storage. Sessions expire after 30 minutes; expired session records are removed by MongoDB TTL cleanup. Do not use the example secret or disable secure cookies in production. Set `AUTH_COOKIE_SECURE=true` behind HTTPS and configure `FRONTEND_ORIGINS` for the deployed frontend origin.

## Checks

```powershell
npm run build
npm run lint
```

Backend tests use an in-memory MongoDB substitute and do not require a running database:

```powershell
pip install -r backend\requirements-dev.txt
pytest backend\tests
```
