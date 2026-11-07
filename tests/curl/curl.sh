#!/bin/bash

# Подготовка: токены

BASE=http://127.0.0.1:8000

# оператор
OP_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"petrova@company.ru","password":"operator123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# клиент
CLIENT_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sidorov@company.ru","password":"client123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

echo "OP=$OP_TOKEN"
echo "CLIENT=$CLIENT_TOKEN"



# Полнотекстовый поиск (тема + тело)

# по слову "принтер"
curl -s "$BASE/tickets/search?q=принтер" \
  -H "Authorization: Bearer $OP_TOKEN" | python -m json.tool

# по фрагменту с wildcard-семантикой (ILIKE %...%)
curl -s "$BASE/tickets/search?q=Outlook" \
  -H "Authorization: Bearer $OP_TOKEN" | python -m json.tool



# Фильтры по полям

# по автору
curl -s "$BASE/tickets/search?author_id=1" \
  -H "Authorization: Bearer $OP_TOKEN" | python -m json.tool

# по исполнителю
curl -s "$BASE/tickets/search?assignee_id=4" \
  -H "Authorization: Bearer $OP_TOKEN" | python -m json.tool

# по статусу (1=open, 2=in_progress, 3=pending, 4=resolved, 5=closed)
curl -s "$BASE/tickets/search?status_id=1" \
  -H "Authorization: Bearer $OP_TOKEN" | python -m json.tool

# по категории
curl -s "$BASE/tickets/search?category_id=5" \
  -H "Authorization: Bearer $OP_TOKEN" | python -m json.tool

# комбинация: открытые заявки автора 1 в категории 4
curl -s "$BASE/tickets/search?author_id=1&status_id=1&category_id=4" \
  -H "Authorization: Bearer $OP_TOKEN" | python -m json.tool



# Диапазон дат

# за ноябрь 2026
curl -s "$BASE/tickets/search?date_from=2026-11-01T00:00:00&date_to=2026-11-30T23:59:59" \
  -H "Authorization: Bearer $OP_TOKEN" | python -m json.tool

# только date_from — «с такого-то момента»
curl -s "$BASE/tickets/search?date_from=2026-11-05T00:00:00" \
  -H "Authorization: Bearer $OP_TOKEN" | python -m json.tool



# Сортировка

# по дате создания, новые сверху (дефолт)
curl -s "$BASE/tickets/search?sort_by=created_at&sort_order=desc" \
  -H "Authorization: Bearer $OP_TOKEN"

# по приоритету, критичные сверху (лексикографически: critical > high > normal > low)
curl -s "$BASE/tickets/search?sort_by=priority&sort_order=desc" \
  -H "Authorization: Bearer $OP_TOKEN"

# по имени статуса, A→Z
curl -s "$BASE/tickets/search?sort_by=status&sort_order=asc" \
  -H "Authorization: Bearer $OP_TOKEN"

# по дате последнего изменения
curl -s "$BASE/tickets/search?sort_by=updated_at&sort_order=desc" \
  -H "Authorization: Bearer $OP_TOKEN"



# Пагинация

# первая страница: 2 записи
curl -s "$BASE/tickets/search?limit=2&offset=0" \
  -H "Authorization: Bearer $OP_TOKEN" | python -m json.tool

# вторая страница: 2 записи
curl -s "$BASE/tickets/search?limit=2&offset=2" \
  -H "Authorization: Bearer $OP_TOKEN" | python -m json.tool

# total одинаковый на обеих страницах, items — разные



# Комбинированный «реалистичный» запрос

# Открытые и в работе заявки по оборудованию за последнюю неделю,
# отсортированные по приоритету, вторая страница по 5
curl -s "$BASE/tickets/search?q=принтер&status_id=1&category_id=5&date_from=2026-11-01T00:00:00&sort_by=priority&sort_order=desc&limit=5&offset=0" \
  -H "Authorization: Bearer $OP_TOKEN" | python -m json.tool



# Поиск клиента — только свои

# клиент ищет по своим заявкам
curl -s "$BASE/tickets/search/own?q=1С" \
  -H "Authorization: Bearer $CLIENT_TOKEN" | python -m json.tool

# клиент пытается подставить чужой author_id — сервис перезапишет на его id
curl -s "$BASE/tickets/search/own?author_id=1" \
  -H "Authorization: Bearer $CLIENT_TOKEN" | python -m json.tool
# в выдаче только заявки текущего клиента, несмотря на author_id=1



# Негативные проверки

# клиент в общий каталог — 403
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/tickets/search?q=x" \
  -H "Authorization: Bearer $CLIENT_TOKEN"          # 403

# без токена — 403
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/tickets/search?q=x"   # 403

# limit > 100 — 422
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/tickets/search?limit=500" \
  -H "Authorization: Bearer $OP_TOKEN"              # 422

# кривой sort_by — 422 (Enum)
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/tickets/search?sort_by=magic" \
  -H "Authorization: Bearer $OP_TOKEN"              # 422

# невалидная дата — 422
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/tickets/search?date_from=not-a-date" \
  -H "Authorization: Bearer $OP_TOKEN"              # 422

# offset < 0 — 422
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/tickets/search?offset=-1" \
  -H "Authorization: Bearer $OP_TOKEN"              # 422



# Проверка формы ответа

curl -s "$BASE/tickets/search?q=принтер&limit=1" \
  -H "Authorization: Bearer $OP_TOKEN" \
  | python -c "import sys,json; d=json.load(sys.stdin); print('total=',d['total'],'limit=',d['limit'],'offset=',d['offset'],'items_len=',len(d['items'])); print(d['items'][0] if d['items'] else 'no items')"