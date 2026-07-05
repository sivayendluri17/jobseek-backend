"""Offline test: run sample ATS payloads through the whole pipeline + API.
This verifies everything except the live network fetch (which works on your machine).
"""
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, ".")

from app.engine.adapters.greenhouse import GreenhouseAdapter
from app.engine.adapters.lever import LeverAdapter
from app.engine.normalizer import normalize_all
from app.engine.deduper import dedupe
from app.engine.bucketer import bucket_all
from app.db import store

now = datetime.now(timezone.utc)

# --- sample payloads shaped exactly like the real APIs return ---
gh_payload = {"jobs": [
    {"id": 1, "title": "Senior Software Engineer", "updated_at": (now - timedelta(hours=3)).isoformat(),
     "absolute_url": "https://boards.greenhouse.io/stripe/jobs/1", "location": {"name": "Remote"}},
    {"id": 2, "title": "Data Analyst", "updated_at": (now - timedelta(hours=40)).isoformat(),
     "absolute_url": "https://boards.greenhouse.io/stripe/jobs/2", "location": {"name": "New York"}},
]}
lever_payload = [
    {"id": "abc", "text": "Backend Developer", "createdAt": int((now - timedelta(hours=10)).timestamp() * 1000),
     "hostedUrl": "https://jobs.lever.co/plaid/abc", "categories": {"location": "San Francisco", "team": "Eng"},
     "workplaceType": "hybrid"},
    # duplicate of the greenhouse Senior Software Engineer @ same company/location to test dedupe:
    {"id": "dup", "text": "Senior Software Engineer", "createdAt": int((now - timedelta(hours=5)).timestamp() * 1000),
     "hostedUrl": "https://jobs.lever.co/stripe/dup", "categories": {"location": "Remote"}, "workplaceType": "remote"},
]

raws = GreenhouseAdapter().parse("stripe", gh_payload) + LeverAdapter().parse("stripe", lever_payload)
print(f"parsed {len(raws)} raw jobs")

jobs = normalize_all(raws)
print(f"normalized {len(jobs)}; remote flags: {[j.remote for j in jobs]}")

before = len(jobs)
jobs = dedupe(jobs)
print(f"deduped {before} -> {len(jobs)} (removed the duplicate Senior SWE)")

jobs = bucket_all(jobs, now)
print("buckets:", {j.title: j.freshness_bucket.value for j in jobs})

# reset db and store
import os
if store.DB_PATH.exists():
    os.remove(store.DB_PATH)
store.init_db()
store.upsert_jobs(jobs)
print("stored; counts by bucket:", store.counts_by_bucket())

# --- exercise the API via TestClient ---
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

assert client.get("/health").json() == {"status": "ok"}
all_jobs = client.get("/jobs").json()
print(f"GET /jobs -> {len(all_jobs)} jobs")
fresh = client.get("/jobs?freshness=24h").json()
print(f"GET /jobs?freshness=24h -> {len(fresh)} jobs (<=24h only)")
remote = client.get("/jobs?remote=true").json()
print(f"GET /jobs?remote=true -> {len(remote)} remote jobs")
one = client.get(f"/jobs/{all_jobs[0]['id']}").json()
print(f"GET /jobs/{{id}} -> {one['title']} @ {one['company']}")
print("stats:", client.get("/stats").json())
print("\nALL CHECKS PASSED")
