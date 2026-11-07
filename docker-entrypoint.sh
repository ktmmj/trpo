#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${DATABASE_URL#sqlite:///}"
DB_PATH="${DB_PATH#/}"       # убираем ведущий слэш для относительных путей

# если БД SQLite и файла нет — применяем schema.sql + seed.sql
if [[ "${DATABASE_URL}" == sqlite* ]]; then
  # абсолютный путь вида /data/servicedesk.db → проверим его
  ABS_PATH="/${DB_PATH}"
  if [[ ! -f "${ABS_PATH}" ]]; then
    echo "[entrypoint] initializing SQLite at ${ABS_PATH}"
    mkdir -p "$(dirname "${ABS_PATH}")"
    python - <<'PY'
import os, sqlite3, pathlib
db_path = os.environ["DATABASE_URL"].replace("sqlite:///", "")
db_path = "/" + db_path.lstrip("/")
pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(db_path)
for f in ("schema.sql", "seed.sql"):
    conn.executescript(pathlib.Path(f).read_text())
conn.commit()
conn.close()
print("schema+seed applied")
PY
  fi

  # при необходимости проставляем пароли seed-пользователям
  if [[ "${SEED_PASSWORDS:-false}" == "true" ]]; then
    echo "[entrypoint] seeding passwords for demo users"
    python - <<'PY'
import os, sqlite3
from app.security import hash_password

db_path = os.environ["DATABASE_URL"].replace("sqlite:///", "")
db_path = "/" + db_path.lstrip("/")
conn = sqlite3.connect(db_path)
pairs = {
    "ivanov@company.ru":    os.environ.get("SEED_CLIENT_PASSWORD", "client123"),
    "sidorov@company.ru":   os.environ.get("SEED_CLIENT_PASSWORD", "client123"),
    "petrova@company.ru":   os.environ.get("SEED_OPERATOR_PASSWORD", "operator123"),
    "kuznetsova@company.ru":os.environ.get("SEED_OPERATOR_PASSWORD", "operator123"),
}
for email, pwd in pairs.items():
    conn.execute("UPDATE users SET password_hash=? WHERE email=?", (hash_password(pwd), email))
conn.commit()
conn.close()
print("passwords seeded")
PY
  fi
fi

exec "$@"