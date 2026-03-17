# F1 Data Pipeline

Data pipeline that ingests Formula 1 race telemetry, timing, and results data from the Ergast and OpenF1 APIs into a normalised PostgreSQL database, primarily used to help me with my F1 fantasy teams :)

Ergast API used for historical data
OpenF1 used for more precise data (from 2023)


Note that Ergast API is deprecated, but still used for historical data, this is fine as there is a drop in replacement api.jolpica.com/ergast/v1

## To-Do 
- Link Data Pipeline directly to predictive model for F1 fantasy

## Architecture

```
Ergast/OpenF1 API -> Data Wrangling -> Unit Test Validators -> PostgreSQL database
```

## Database schema

Normalised into dimension and fact tables:

- **Dimensions**: `seasons`, `circuits`, `drivers`, `constructors`
- **Facts**: `races`, `race_results`, `lap_times`, `pit_stops`
- **Telemetry**: `sessions`, `telemetry_samples`

All fact tables use composite unique constraints for idempotent upserts.

## Configuration

Set via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://f1user:f1pass@localhost:5432/f1data` | PostgreSQL connection string |
| `BATCH_SIZE` | `500` | Rows per upsert batch |
| `MAX_RETRIES` | `3` | HTTP retry attempts |
| `RETRY_BACKOFF` | `2.0` | Exponential backoff multiplier |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
