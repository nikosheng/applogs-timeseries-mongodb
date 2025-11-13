# App Logs Time Series with MongoDB

This project generates Spring Boot–style application logs as time series data, stores them in a MongoDB time series collection, and provides a simple Flask web page to filter logs by timestamp and meta fields (app, host, env).

## Prerequisites
- Python 3.9+
- A MongoDB Atlas cluster (recommended) or local MongoDB


## Quick Start

1) Create a `.env` file from the example and set your connection details.

```bash
cp .env.example .env
# Edit .env with your Atlas connection string
```

2) Install dependencies.

```bash
python -m pip install -r requirements.txt
```

3) Generate sample logs into a time series collection.

```bash
# Single env (backward compatible)
python scripts/generate_logs.py --count 2000 --apps order-service payment-service auth-service --env prod

# Multiple envs
python scripts/generate_logs.py --count 5000 --apps order-service payment-service auth-service --envs dev staging prod
```

4) Run the web app.

```bash
python -m flask --app webapp.app run --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` and filter your logs by app/host/env and time range.

## Configuration
Set these in `.env`:

- `MONGODB_URI` – Atlas connection string (e.g., `mongodb+srv://user:pass@cluster.mongodb.net`)
- `DB_NAME` – Database name (default `applogs`)
- `COLL_NAME` – Collection name (default `logs`)
- `TIME_FIELD` – Time field name (default `timestamp`)
- `META_FIELD` – Meta field name (default `meta`)

### Indexes
- The generator script ensures indexes on `meta.app`, `meta.host`, `meta.env`, and `level` for efficient filtering.
  The time field is already optimized in time-series collections and does not need a separate index.

## Notes
- The web app filters by `meta.app`, `meta.host`, `meta.env`, `level`, and time range. No Atlas Search is required.
- Results are paginated at 50 items per page with Prev/Next navigation.
- The generator creates realistic Spring Boot–style logs across multiple services, levels, and endpoints.