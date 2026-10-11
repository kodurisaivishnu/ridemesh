#!/usr/bin/env bash
# Runs once, on the first start of an empty Postgres volume (docker-entrypoint-initdb.d).
# For each service that owns data: its own database, an owner role that runs migrations,
# and an app role the running service uses, which can read and write rows but not change
# or drop tables. No role can connect to another service's database.
set -euo pipefail

SERVICES=(identity trips dispatch pricing payments)

for svc in "${SERVICES[@]}"; do
  echo "creating database and roles for ${svc}"

  # Roles and database, created from the maintenance database.
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    -v db="$svc" -v owner="${svc}_owner" -v app="${svc}_app" -v pw="$SERVICE_DB_PASSWORD" <<'SQL'
CREATE ROLE :"owner" LOGIN PASSWORD :'pw';
CREATE ROLE :"app" LOGIN PASSWORD :'pw';
CREATE DATABASE :"db" OWNER :"owner";
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO :"app";
SQL

  # Privileges inside the new database: tables the owner creates later are usable by the app.
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$svc" \
    -v owner="${svc}_owner" -v app="${svc}_app" <<'SQL'
GRANT USAGE ON SCHEMA public TO :"app";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"app";
SQL
done
