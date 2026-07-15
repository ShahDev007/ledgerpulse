-- Runs once on first Postgres boot (docker-entrypoint-initdb.d).
-- Alembic owns the schema; this only guarantees required extensions exist.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
