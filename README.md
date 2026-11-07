# Лабораторные работы по ТРПО

## Инструкция по запуску

```shell
git clone https://github.com/ktmmj/trpo
cd trpo
python3.15 -m venv .venv
./.venv/bin/pip install -r requirements.txt
# Структура БД
sqlite3 servicedesk.db < docs/db/schema.sql
# Тестовые данные
sqlite3 servicedesk.db < docs/db/seed.sql
./.venv/bin/uvicorn app.main:app --reload
```

## Тестирование

```shell
PYTHONPATH=. ./.venv/bin/pytest -q
```
