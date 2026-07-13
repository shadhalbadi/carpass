# CarPass Oman

Car import aggregator for Oman: **landed-cost calculator**, **multi-source search**, **live shipment tracking**, **clearing-agent desk**, and **document vault**.

## Stack

- Backend: FastAPI + SQLAlchemy (SQLite by default) + Celery tasks
- Frontend: Next.js 14 (App Router) + Tailwind, Arabic RTL toggle

## Quick start

### Backend

```bash
cd carpass/backend
python -m venv venv
# Windows:
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\uvicorn app.main:app --reload --port 8001
```

API docs: http://127.0.0.1:8001/docs

### Frontend

```bash
cd carpass/frontend
npm install
npm run dev
```

App: http://localhost:3000

## Demo accounts

| Email | Password | Role |
|-------|----------|------|
| buyer@carpass.om | buyer123 | Buyer |
| agent@carpass.om | agent123 | Clearing agent |
| admin@carpass.om | admin123 | Admin |

## Features mapped to plan

1. **Calculator** (`/`) — paste car URL → extract → OMR landed-cost breakdown + import vs local verdict  
2. **Search** (`/search`) — aggregated listings with freshness + landed prices  
3. **Watches** (`/watches`) — saved searches / alerts  
4. **Shipments** (`/shipments`) — create import, milestones, document upload + completeness  
5. **Track** (`/track`) — public tracking code + vessel map + pipeline  
6. **Agent** (`/agent`) — claim shipments, update customs status, share track links  
7. **Admin** (`/admin`) — fee tables, routes, trigger crawl  

## Data notes

- Listing crawl seeds demo Gulf-relevant inventory (Copart, IAAI, BE FORWARD, Dubizzle UAE, OpenSooq).  
- Live page fetch is attempted; when blocked, demo HTML fixtures are used so the calculator still works.  
- Set `OPENAI_API_KEY` for LLM extraction / document OCR.  
- Set `AIS_API_KEY` for real vessel AIS; otherwise vessel position is simulated toward Sohar.  
- Set `SCRAPING_PROXY_URL` for production crawling.  

## Celery (optional)

Requires Redis:

```bash
celery -A app.celery_app.celery_app worker -l info
celery -A app.celery_app.celery_app beat -l info
```
