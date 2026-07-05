# JobSeek — Backend (Phase 1: Job Engine)

The fetch-and-bucket core of JobSeek. It sweeps public ATS job boards
(Greenhouse, Lever), normalizes and de-duplicates the listings, buckets them
by how recently they were posted (24h / 48h / 72h), stores them, and serves
them over a FastAPI API for the frontend to display.

No API keys, no logins, no scraping of private sites — only public endpoints.

## Run it

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. Start the API
uvicorn app.main:app --reload
#    -> API at http://localhost:8000
#    -> Interactive docs at http://localhost:8000/docs

# 2. In another terminal, run a sweep to pull real jobs into the database
curl -X POST http://localhost:8000/engine/run
#    (or run once without the server:  python -m app.engine.runner )

# 3. See the fresh jobs
curl "http://localhost:8000/jobs?freshness=24h"
```

## The endpoints

| Endpoint | What it does |
|---|---|
| `GET /jobs?freshness=24h&remote=true&company=stripe` | List jobs, newest first, with filters |
| `GET /jobs/{id}` | One job's details |
| `GET /companies` | Your tracked company list |
| `GET /stats` | Counts per freshness bucket |
| `POST /engine/run` | Trigger a sweep now |
| `GET /health` | Liveness check |

## Your company list

Edit `app/companies.yaml` — that's the list of employers JobSeek sweeps.
Each entry is the company's slug on that ATS (the name in its careers URL,
e.g. `boards.greenhouse.io/<slug>` or `jobs.lever.co/<slug>`). The examples
in the file are placeholders — replace them with your candidates' real target
employers. Any slug that fails is skipped, so a wrong one won't break a sweep.

## How the code maps to the design

```
app/engine/
  adapters/greenhouse.py, lever.py   one file per source (add more here)
  normalizer.py                      RawJob -> common Job shape
  deduper.py                         collapse repeats, keep the freshest
  bucketer.py                        label 24h / 48h / 72h / older
  runner.py                          orchestrates a full sweep
app/db/store.py                      SQLite storage (swap for Postgres later)
app/api/jobs.py                      the endpoints the frontend calls
app/models/job.py                    the Job model (Pydantic)
```

`test_pipeline.py` runs the whole pipeline on sample data (no network) so you
can verify everything end to end:  `python test_pipeline.py`

## Notes

- **Storage:** starts on SQLite so it runs with zero setup. The design targets
  PostgreSQL for production; `app/db/store.py` is the only file to reimplement.
- **Scheduling:** for now, sweeps run on demand via `POST /engine/run`. A timed
  scheduler (e.g. cron or APScheduler) is the small next addition.
- **More sources:** add public APIs (Adzuna, USAJobs, Remotive) or more ATSs by
  writing a new adapter in `app/engine/adapters/` and registering it in
  `runner.py`.
```
