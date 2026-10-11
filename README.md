# LegalSmart

LegalSmart is a React/Vite frontend with a FastAPI authentication API backed by MongoDB.

## Local setup

Requirements: Node.js, Python 3.11+, and a reachable MongoDB instance (local MongoDB or MongoDB Atlas).

1. Configure the API environment:

   ```powershell
   Copy-Item backend\.env.example backend\.env
   ```

   Edit `backend\.env` and set `MONGODB_URI` to your MongoDB connection string. Set `MONGODB_DATABASE=LegalCases` for cases, clients, payments, and accounts, and `MONGODB_REMINDERS_DATABASE=AllRemainders` for scheduled reminders. MongoDB database names are case-insensitive on Windows, so `ALLRemainders` and `AllRemainders` refer to the same existing database and cannot be created separately by case alone. Replace `JWT_SECRET` with a random secret of at least 32 characters; for example:

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

- `POST /api/auth/signup` stores a normalized email, display name, and Argon2 password hash in the `users` collection in the `LegalCases` database. Plain-text passwords are never stored.
- `POST /api/auth/login` verifies the password, signs a short-lived JWT, and stores a hash of that token as a MongoDB session.
- `GET /api/auth/me` verifies the JWT signature and expiry, then checks that its matching session is still active in MongoDB before returning the user.
- `POST /api/auth/logout` revokes the MongoDB session and clears the HTTP-only cookie.
- Cases, clients, and payment-ledger entries are saved in user-scoped collections in `LegalCases`. Cases include an optional case number, case type, court, status, and hearing date. The overview calendar colors active upcoming cases green, missed unresolved hearings red, and pending or closed matters yellow; selecting a case opens its details. Case hearing reminders are saved in `AllRemainders.reminders` with the case and client names, user identity, notes, UTC hearing timestamp, local date/time/weekday, and timezone. Only future hearings on non-closed cases are scheduled. APScheduler marks them due every five seconds. Enable browser notifications in the dashboard and keep the dashboard open to receive them. The browser Notifications API cannot deliver while the site is closed; background delivery requires a push service.
- Users can edit or delete their own cases. Case images are streamed in chunks to the `case_attachments` GridFS bucket in `LegalCases` and are removed when the case is deleted. There is no application-level image size limit; actual uploads are limited by available storage and any MongoDB, network, or hosting limits.
- The payment ledger records amounts and statuses only; it does not collect card details or process payments.

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
