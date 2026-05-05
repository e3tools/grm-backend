# Deploy GRM on Vercel (web) plus Celery (containers)

Vercel runs Django as a single serverless function. Celery workers and beat are long-lived processes and must run elsewhere (this repo includes `docker-compose.celery.yml` for any host that runs Docker).

**Production URL** (after a successful deploy): https://grm-web-app-benin.vercel.app

## 1. Vercel project

1. Create a project and set **Root Directory** to `src` (Vercel reads `src/vercel.json` from that root; do not put `rootDirectory` inside `vercel.json` — the dashboard owns that setting).
2. Add **Postgres**: e.g. `vercel integration accept-terms neon` then `vercel integration add neon --plan free_v3 -m region=iad1 -e production` (see `vercel integration add neon --help`). That wires `DATABASE_URL` (and related `POSTGRES_*` vars) into the project. Or attach any other Postgres and set `DATABASE_URL` manually.
3. Add **Redis** (for example [Upstash Redis](https://vercel.com/marketplace/upstash)) and set both:
   - `CELERY_BROKER_URL` — e.g. `rediss://default:TOKEN@HOST:6379`
   - `CELERY_RESULT_BACKEND` — same URL with a different logical DB if your provider supports it, or the same URL.

Every deploy runs `migrate` then `set_benin_demo`. The demo command only seeds when the database is still empty; existing data is left unchanged.

**Bundle size:** `sentence-transformers` was removed from `requirements.txt` because it pulls PyTorch and exceeds Vercel’s ~500 MB function limit. Embeddings use the Hugging Face Inference API (`HUGGINGFACE_*` settings), not local models.

## 2. Required environment variables

Mirror `src/grm/example.env` for your deployment. At minimum you need everything `django-environ` reads in `grm/settings.py` without a default (including `SECRET_KEY`, `ALLOWED_HOSTS`, CouchDB, Celery, Mapbox, Twilio, email, OpenAI, and any keys referenced by `local_settings`).

For Benin map defaults you can start from `example.env` and set `DIAGNOSTIC_MAP_ISO_CODE` and bounds to Benin if you use that screen.

## 3. Celery worker and beat

At the repository root, create `.env.celery` (gitignored) with the **same** key/value pairs as the Vercel project environment, especially `DATABASE_URL`, `SECRET_KEY`, all CouchDB variables, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND`.

Then start worker and beat:

```bash
docker compose -f docker-compose.celery.yml up -d --build
```

Beat uses `django_celery_beat.schedulers:DatabaseScheduler`. Ensure periodic tasks exist in the database (Django admin or migrations) so schedules match what you expect in production.

## 4. Production `local_settings`

When you add `src/grm/local_settings.py`, extend `CSRF_TRUSTED_ORIGINS` with your real production domain. The template already includes `https://*.vercel.app` for preview and production `*.vercel.app` hosts.
