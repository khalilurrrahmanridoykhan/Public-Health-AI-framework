# Production deployment

1. Set `environment: production` and `host: 0.0.0.0` in `phframe.yaml`.
2. Copy `.env.example` to `.env` and replace every secret.
3. Run `phframe doctor` and `phframe migrate --check`.
4. Start with `docker compose up -d --build` behind an HTTPS reverse proxy.
5. Check `/health` for liveness and `/ready` for database readiness.

Use `Authorization: Bearer $PHFRAME_API_TOKEN` for automated API writes. Run `phframe backup` for SQLite installations; use `pg_dump` and tested off-site retention for PostgreSQL. Run the web and worker processes separately. Never commit `.env`, connector tokens, database dumps, or health records.

Before upgrades: create a backup, test it, install the target version in staging, run `phframe migrate --check`, apply migrations, verify `/ready`, then promote. Roll back application containers only after confirming the database migration is backward-compatible.
