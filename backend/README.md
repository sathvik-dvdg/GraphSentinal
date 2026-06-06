# GraphSentinel Backend

Sairaj-owned FastAPI backend for GraphSentinel.

## Run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
```

## Smoke Test

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/graph
curl http://localhost:8000/api/v1/stats
curl "http://localhost:8000/api/v1/timeline?last=60min"
```

Mutating endpoints require:

```http
X-API-Key: change-me-for-demo
```

