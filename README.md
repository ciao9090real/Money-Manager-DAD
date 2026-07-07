# Finlio

Full-stack personal finance manager with a FastAPI API and a responsive Next.js web client.

## Included

- Password registration/login with Argon2 hashing and JWT authentication
- User-owned banks, accounts, cards, transactions, settings, investments, and insurance
- Cards are strictly linked to an account in the same bank
- Finnhub live quotes for investment holdings
- Resend email reminders for subscriptions and recurring payments
- Manual-first tracking with a clean empty state for new users
- Account hierarchy fields ready for parent/child accounts, wallets, and payment methods
- Dashboard totals for liquidity, investments, insurance, debt, income, expenses, and savings rate
- Responsive desktop sidebar and mobile bottom navigation
- SQLite for local development and PostgreSQL support through `DATABASE_URL`
- Alembic migration configuration and system category seeding

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item ..\.env.example .env
python seed.py
uvicorn app.main:app --reload --port 8000
```

API documentation is available at `http://localhost:8000/docs`.

`python seed.py` creates shared system categories only. It does not create demo users or demo financial data.

For PostgreSQL, set:

```env
DATABASE_URL=postgresql+psycopg2://user:password@localhost/money_manager
SECRET_KEY=replace-with-a-long-random-value
```

External integrations are configured only on the backend:

```env
FINNHUB_API_KEY=your-key
RESEND_API_KEY=your-key
RESEND_FROM_EMAIL=Finlio <reminders@your-verified-domain.com>
```

Call `POST /recurring-payments/send-due` from a daily cron job to deliver reminders that have entered their notification window.

Create a migration after model changes:

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Frontend

```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_API_URL="http://localhost:8000"
npm run dev
```

Open `http://localhost:3000`.

## Tests

```powershell
cd backend
pytest
```

## Security notes

- Passwords are stored only as Argon2 hashes.
- Cards store only four digits in the `last4` field.
- All financial queries filter by the authenticated user.
- Change `SECRET_KEY` before deployment and serve the app over HTTPS.
