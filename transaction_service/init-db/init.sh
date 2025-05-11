#!/bin/bash
set -e

echo "Создание баз данных transactions и transactions_test..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  CREATE DATABASE transactions;
  CREATE DATABASE transactions_test;
EOSQL

echo "Применение схемы к обеим базам..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname transactions < /docker-entrypoint-initdb.d/schema.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname transactions_test < /docker-entrypoint-initdb.d/schema.sql

echo "Вставка тестовых данных в transactions_test..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname transactions_test < /docker-entrypoint-initdb.d/test-data.sql