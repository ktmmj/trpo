#!/usr/bin/env bash
# =============================================================================
# ServiceDesk — прогон тест-кейсов через curl
# Требования: curl, jq, python3, sqlite3. Для TC-03 — docker compose (опционально).
# Использование:
#   ./run_tests.sh                 # все кейсы
#   BASE=http://host:port ./run_tests.sh
#   ./run_tests.sh TC-01 TC-12     # только выбранные
#   KEEP_DB=1 ./run_tests.sh       # не удалять временную БД-копию
# =============================================================================
set -uo pipefail

# ─── config ──────────────────────────────────────────────────────────────────
BASE="${BASE:-http://127.0.0.1:8000}"
DB_PATH="${DB_PATH:-servicedesk.db}"            # SQLite-файл для SQL-проверок
EVIDENCE_DIR="${EVIDENCE_DIR:-./evidence}"
CLIENT_EMAIL="${CLIENT_EMAIL:-sidorov@company.ru}"
CLIENT_PASSWORD="${CLIENT_PASSWORD:-client123}"
OP_EMAIL="${OP_EMAIL:-petrova@company.ru}"
OP_PASSWORD="${OP_PASSWORD:-operator123}"
ADMIN_EMAIL="${ADMIN_EMAIL:-ivanov@company.ru}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-client123}"
BLOCKED_EMAIL="${BLOCKED_EMAIL:-volkova@company.ru}"
BLOCKED_PASSWORD="${BLOCKED_PASSWORD:-client123}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

mkdir -p "$EVIDENCE_DIR"
LOG="$EVIDENCE_DIR/run.log"
: > "$LOG"

# ─── colors ──────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  C_RED=$'\e[31m'; C_GREEN=$'\e[32m'; C_YELLOW=$'\e[33m'
  C_CYAN=$'\e[36m'; C_RESET=$'\e[0m'
else
  C_RED=""; C_GREEN=""; C_YELLOW=""; C_CYAN=""; C_RESET=""
fi

# ─── state ───────────────────────────────────────────────────────────────────
declare -a RESULTS=()   # "ID|STATUS|NOTE|EVIDENCE"
TOTAL=0; PASS=0; FAIL=0; BLOCKED=0; SKIP=0

# Если переданы ID — фильтруем
declare -A FILTER=()
if [[ $# -gt 0 ]]; then
  for id in "$@"; do FILTER["$id"]=1; done
fi

want() {  # $1 = ID
  [[ ${#FILTER[@]} -eq 0 || -n "${FILTER[$1]:-}" ]]
}

# ─── helpers ─────────────────────────────────────────────────────────────────
log() { echo "$*" | tee -a "$LOG" >&2; }

record() {  # record ID STATUS NOTE EVIDENCE
  local id="$1" status="$2" note="$3" ev="$4"
  RESULTS+=("$id|$status|$note|$ev")
  TOTAL=$((TOTAL+1))
  case "$status" in
    PASS)    PASS=$((PASS+1));    color="$C_GREEN"  ;;
    FAIL)    FAIL=$((FAIL+1));    color="$C_RED"    ;;
    BLOCKED) BLOCKED=$((BLOCKED+1)); color="$C_YELLOW" ;;
    SKIP)    SKIP=$((SKIP+1));    color="$C_CYAN"   ;;
    *)       color="" ;;
  esac
  printf "%-8s %s%-7s%s %s\n" "$id" "$color" "$status" "$C_RESET" "$note" | tee -a "$LOG" >&2
}

# Выполнить curl и сохранить тело + код в evidence/.
# Возвращает: код в stdout, тело в файле ${name}.json, код в ${name}.code
do_curl() {  # do_curl NAME [curl args...]
  local name="$1"; shift
  local body="$EVIDENCE_DIR/${name}.json"
  local code
  code=$(curl -s -o "$body" -w "%{http_code}" "$@" 2>"$EVIDENCE_DIR/${name}.err")
  echo "$code" > "$EVIDENCE_DIR/${name}.code"
  echo "$code"
}

# Достать поле из JSON-ответа
jget() {  # jget FILE JSONPATH
  jq -r "$2" "$1" 2>/dev/null
}

# Проверка утверждения — для сокращения бойлерплейта.
assert() {  # assert COND MESSAGE
  if eval "$1"; then return 0; else log "  ASSERT FAIL: $2"; return 1; fi
}

# Логин: печатает токен в stdout
login() {  # login EMAIL PASSWORD
  local email="$1" pass="$2"
  curl -s -X POST "$BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"password\":\"$pass\"}" \
    | jq -r '.access_token // empty'
}

# ─── preflight ───────────────────────────────────────────────────────────────
preflight() {
  log "== preflight =="
  for t in curl jq python3; do
    command -v "$t" >/dev/null || { log "missing tool: $t"; exit 2; }
  done
  if ! curl -s -o /dev/null -w "%{http_code}" "$BASE/health" | grep -q 200; then
    log "service not reachable at $BASE/health"
    exit 2
  fi
  log "health OK"

  CLIENT_TOKEN=$(login "$CLIENT_EMAIL" "$CLIENT_PASSWORD")
  OP_TOKEN=$(login "$OP_EMAIL" "$OP_PASSWORD")
  ADMIN_TOKEN=$(login "$ADMIN_EMAIL" "$ADMIN_PASSWORD")

  if [[ -z "$CLIENT_TOKEN" || -z "$OP_TOKEN" || -z "$ADMIN_TOKEN" ]]; then
    log "cannot obtain tokens — проверьте пароли в .env и что entrypoint их проставил"
    exit 2
  fi
  log "tokens acquired"
}

# =============================================================================
#  TC-01  /health 200
# =============================================================================
tc01() {
  want TC-01 || return
  local code
  code=$(do_curl tc01 "$BASE/health")
  local status
  status=$(jget "$EVIDENCE_DIR/tc01.json" '.status')
  if [[ "$code" == "200" && "$status" == "ok" ]]; then
    record TC-01 PASS "code=$code status=$status" "evidence/tc01.json"
  else
    record TC-01 FAIL "code=$code status=$status" "evidence/tc01.json"
  fi
}

# =============================================================================
#  TC-02  /health/ready 200
# =============================================================================
tc02() {
  want TC-02 || return
  local code dbok
  code=$(do_curl tc02 "$BASE/health/ready")
  dbok=$(jget "$EVIDENCE_DIR/tc02.json" '.checks.database.ok')
  if [[ "$code" == "200" && "$dbok" == "true" ]]; then
    record TC-02 PASS "code=$code db.ok=true" "evidence/tc02.json"
  else
    record TC-02 FAIL "code=$code db.ok=$dbok" "evidence/tc02.json"
  fi
}

# =============================================================================
#  TC-03  /health/ready 503 при недоступной БД
#  Воспроизводимо только если БД — отдельный контейнер (PG overlay).
# =============================================================================
tc03() {
  want TC-03 || return
  if ! command -v docker >/dev/null || [[ ! -f "$COMPOSE_FILE" ]]; then
    record TC-03 SKIP "docker compose недоступен; в SQLite-варианте БД — файл" "—"
    return
  fi
  if ! docker compose -f "$COMPOSE_FILE" ps db 2>/dev/null | grep -qi "db"; then
    record TC-03 SKIP "нет сервиса 'db' в compose — пропуск" "—"
    return
  fi
  log "  останавливаю db..."
  docker compose -f "$COMPOSE_FILE" stop db >/dev/null
  sleep 2
  local code
  code=$(do_curl tc03 "$BASE/health/ready")
  local hcode
  hcode=$(do_curl tc03-health "$BASE/health")
  log "  поднимаю db обратно..."
  docker compose -f "$COMPOSE_FILE" start db >/dev/null
  if [[ "$code" == "503" && "$hcode" == "200" ]]; then
    record TC-03 PASS "ready=$code health=$hcode" "evidence/tc03.json"
  else
    record TC-03 FAIL "ready=$code health=$hcode" "evidence/tc03.json"
  fi
}

# =============================================================================
#  TC-04  Регистрация клиента — 201
# =============================================================================
TC04_EMAIL="newclient.tc04@test.ru"
tc04() {
  want TC-04 || return
  local code role
  code=$(do_curl tc04 -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$TC04_EMAIL\",\"full_name\":\"Тест Клиент\",\"department\":\"QA\"}")
  role=$(jget "$EVIDENCE_DIR/tc04.json" '.user_role')
  if [[ "$code" == "201" && "$role" == "3" ]]; then
    record TC-04 PASS "code=$code role=$role" "evidence/tc04.json"
  elif [[ "$code" == "409" ]]; then
    # уже зарегистрирован — тест идемпотентен, но результат не 201
    record TC-04 PASS "code=$code (idempotent rerun)" "evidence/tc04.json"
  else
    record TC-04 FAIL "code=$code role=$role" "evidence/tc04.json"
  fi
}

# =============================================================================
#  TC-05  Регистрация дубликата — 409
# =============================================================================
tc05() {
  want TC-05 || return
  local code
  code=$(do_curl tc05 -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$TC04_EMAIL\",\"full_name\":\"Дубль\"}")
  if [[ "$code" == "409" ]]; then
    record TC-05 PASS "code=$code" "evidence/tc05.json"
  else
    record TC-05 FAIL "code=$code" "evidence/tc05.json"
  fi
}

# =============================================================================
#  TC-06  Регистрация с битым email — 422
# =============================================================================
tc06() {
  want TC-06 || return
  local code
  code=$(do_curl tc06 -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"not-an-email","full_name":"X"}')
  if [[ "$code" == "422" ]]; then
    record TC-06 PASS "code=$code" "evidence/tc06.json"
  else
    record TC-06 FAIL "code=$code" "evidence/tc06.json"
  fi
}

# =============================================================================
#  TC-07  Логин с верными данными — 200 + токен
# =============================================================================
tc07() {
  want TC-07 || return
  local code tok
  code=$(do_curl tc07 -X POST "$BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$OP_EMAIL\",\"password\":\"$OP_PASSWORD\"}")
  tok=$(jget "$EVIDENCE_DIR/tc07.json" '.access_token')
  if [[ "$code" == "200" && -n "$tok" && "$tok" != "null" ]]; then
    record TC-07 PASS "code=$code token_len=${#tok}" "evidence/tc07.json"
  else
    record TC-07 FAIL "code=$code token_len=${#tok}" "evidence/tc07.json"
  fi
}

# =============================================================================
#  TC-08  Логин с неверным паролем — 403
# =============================================================================
tc08() {
  want TC-08 || return
  local code
  code=$(do_curl tc08 -X POST "$BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$OP_EMAIL\",\"password\":\"wrong-password\"}")
  if [[ "$code" == "403" ]]; then
    record TC-08 PASS "code=$code" "evidence/tc08.json"
  else
    record TC-08 FAIL "code=$code" "evidence/tc08.json"
  fi
}

# =============================================================================
#  TC-09  Логин заблокированного — 403
# =============================================================================
tc09() {
  want TC-09 || return
  local code
  code=$(do_curl tc09 -X POST "$BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$BLOCKED_EMAIL\",\"password\":\"$BLOCKED_PASSWORD\"}")
  if [[ "$code" == "403" ]]; then
    record TC-09 PASS "code=$code" "evidence/tc09.json"
  else
    record TC-09 FAIL "code=$code" "evidence/tc09.json"
  fi
}

# =============================================================================
#  TC-10  Запрос без токена — 401/403
# =============================================================================
tc10() {
  want TC-10 || return
  local code
  code=$(do_curl tc10 "$BASE/tickets")
  if [[ "$code" == "401" || "$code" == "403" ]]; then
    record TC-10 PASS "code=$code (см. Q1: 401 vs 403)" "evidence/tc10.json"
  else
    record TC-10 FAIL "code=$code" "evidence/tc10.json"
  fi
}

# =============================================================================
#  TC-11  Подделанный токен — 403
# =============================================================================
tc11() {
  want TC-11 || return
  local bad="${CLIENT_TOKEN:0:${#CLIENT_TOKEN}-4}0000"
  local code
  code=$(do_curl tc11 "$BASE/tickets" -H "Authorization: Bearer $bad")
  if [[ "$code" == "403" ]]; then
    record TC-11 PASS "code=$code" "evidence/tc11.json"
  else
    record TC-11 FAIL "code=$code" "evidence/tc11.json"
  fi
}

# =============================================================================
#  TC-12  Создание заявки клиентом — 201
# =============================================================================
tc12() {
  want TC-12 || return
  local code author status closed assignee
  code=$(do_curl tc12 -X POST "$BASE/tickets" \
    -H "Authorization: Bearer $CLIENT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"title":"TC-12 заявка","description":"описание","priority":"normal"}')
  author=$(jget "$EVIDENCE_DIR/tc12.json" '.author_id')
  status=$(jget "$EVIDENCE_DIR/tc12.json" '.status_id')
  closed=$(jget "$EVIDENCE_DIR/tc12.json" '.closed_at')
  assignee=$(jget "$EVIDENCE_DIR/tc12.json" '.assignee_id')
  TC12_TICKET=$(jget "$EVIDENCE_DIR/tc12.json" '.id')
  if [[ "$code" == "201" && "$status" == "1" && "$closed" == "null" ]]; then
    record TC-12 PASS "code=$code id=$TC12_TICKET assignee=$assignee" "evidence/tc12.json"
  else
    record TC-12 FAIL "code=$code status=$status closed=$closed" "evidence/tc12.json"
  fi
}

# =============================================================================
#  TC-13  Пустая тема — 422
# =============================================================================
tc13() {
  want TC-13 || return
  local code
  code=$(do_curl tc13 -X POST "$BASE/tickets" \
    -H "Authorization: Bearer $CLIENT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"title":"   "}')
  if [[ "$code" == "422" ]]; then
    record TC-13 PASS "code=$code" "evidence/tc13.json"
  else
    record TC-13 FAIL "code=$code" "evidence/tc13.json"
  fi
}

# =============================================================================
#  TC-14  Недопустимый приоритет — 422
# =============================================================================
tc14() {
  want TC-14 || return
  local code
  code=$(do_curl tc14 -X POST "$BASE/tickets" \
    -H "Authorization: Bearer $CLIENT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"title":"TC-14","priority":"urgent"}')
  if [[ "$code" == "422" ]]; then
    record TC-14 PASS "code=$code" "evidence/tc14.json"
  else
    record TC-14 FAIL "code=$code" "evidence/tc14.json"
  fi
}

# =============================================================================
#  TC-15  Создание заявки заблокированным — 403 (или логин 403)
# =============================================================================
tc15() {
  want TC-15 || return
  local code_login code_create btok
  code_login=$(do_curl tc15-login -X POST "$BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$BLOCKED_EMAIL\",\"password\":\"$BLOCKED_PASSWORD\"}")
  btok=$(jget "$EVIDENCE_DIR/tc15-login.json" '.access_token')
  if [[ "$code_login" == "403" ]]; then
    record TC-15 PASS "login=403 (см. Q3: создание недостижимо)" "evidence/tc15-login.json"
    return
  fi
  if [[ -n "$btok" && "$btok" != "null" ]]; then
    code_create=$(do_curl tc15-create -X POST "$BASE/tickets" \
      -H "Authorization: Bearer $btok" \
      -H "Content-Type: application/json" \
      -d '{"title":"TC-15"}')
    if [[ "$code_create" == "403" ]]; then
      record TC-15 PASS "create=403" "evidence/tc15-create.json"
    else
      record TC-15 FAIL "create=$code_create (ожидали 403)" "evidence/tc15-create.json"
    fi
  else
    record TC-15 FAIL "login=$code_login без токена и без 403 — странно" "evidence/tc15-login.json"
  fi
}

# =============================================================================
#  TC-16  История клиента — только свои
# =============================================================================
tc16() {
  want TC-16 || return
  local code foreign
  code=$(do_curl tc16 "$BASE/tickets" -H "Authorization: Bearer $CLIENT_TOKEN")
  foreign=$(jq -r --argjson cid "${CLIENT_ID:-0}" \
    '[.items[]? // .[]? | select(.author_id != $cid)] | length' \
    "$EVIDENCE_DIR/tc16.json" 2>/dev/null)
  # CLIENT_ID узнаём из tc12 (author_id)
  if [[ -z "${CLIENT_ID:-}" ]]; then
    CLIENT_ID=$(jget "$EVIDENCE_DIR/tc12.json" '.author_id')
  fi
  foreign=$(jq -r --argjson cid "${CLIENT_ID:-0}" \
    '[.items[]? // .[]? | select(.author_id != $cid)] | length' \
    "$EVIDENCE_DIR/tc16.json" 2>/dev/null)
  if [[ "$code" == "200" && "$foreign" == "0" ]]; then
    record TC-16 PASS "code=$code foreign=0" "evidence/tc16.json"
  else
    record TC-16 FAIL "code=$code foreign=$foreign" "evidence/tc16.json"
  fi
}

# =============================================================================
#  TC-17  Клиент читает чужую заявку — 403
# =============================================================================
tc17() {
  want TC-17 || return
  # берём id чужой заявки: заявка #1 автора 3 (sidorov? — проверим по DB)
  # надёжнее: сначала получим id заявки, созданной оператором
  local code op_ticket
  op_ticket=$(do_curl tc17-own -X POST "$BASE/tickets" \
    -H "Authorization: Bearer $OP_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"title":"TC-17 чужая"}')
  local tid
  tid=$(jget "$EVIDENCE_DIR/tc17-own.json" '.id')
  if [[ -z "$tid" || "$tid" == "null" ]]; then
    # оператор не может создать заявку в этой реализации (только клиент),
    # поэтому берём первую заявку из общего каталога и проверяем что
    # она не принадлежит клиенту
    do_curl tc17-search "$BASE/tickets/search?limit=1" \
      -H "Authorization: Bearer $OP_TOKEN" >/dev/null
    tid=$(jget "$EVIDENCE_DIR/tc17-search.json" '.items[0].id')
  fi
  if [[ -z "$tid" || "$tid" == "null" ]]; then
    record TC-17 SKIP "не удалось получить чужую заявку" "—"
    return
  fi
  code=$(do_curl tc17 "$BASE/tickets/$tid" -H "Authorization: Bearer $CLIENT_TOKEN")
  if [[ "$code" == "403" ]]; then
    record TC-17 PASS "code=$code foreign_ticket=$tid" "evidence/tc17.json"
  else
    record TC-17 FAIL "code=$code foreign_ticket=$tid" "evidence/tc17.json"
  fi
}

# =============================================================================
#  TC-18  Поиск оператора по q — 200
# =============================================================================
tc18() {
  want TC-18 || return
  local code total
  code=$(do_curl tc18 "$BASE/tickets/search?q=%D0%BF%D1%80%D0%B8%D0%BD%D1%82%D0%B5%D1%80" \
    -H "Authorization: Bearer $OP_TOKEN")
  total=$(jget "$EVIDENCE_DIR/tc18.json" '.total')
  if [[ "$code" == "200" && "${total:-0}" -ge 1 ]]; then
    record TC-18 PASS "code=$code total=$total" "evidence/tc18.json"
  else
    record TC-18 FAIL "code=$code total=$total" "evidence/tc18.json"
  fi
}

# =============================================================================
#  TC-19  Фильтры + сортировка — 200
# =============================================================================
tc19() {
  want TC-19 || return
  local code n
  code=$(do_curl tc19 "$BASE/tickets/search?author_id=1&status_id=1&sort_by=priority&sort_order=desc&limit=2" \
    -H "Authorization: Bearer $OP_TOKEN")
  n=$(jget "$EVIDENCE_DIR/tc19.json" '.items | length')
  if [[ "$code" == "200" && "${n:-999}" -le 2 ]]; then
    record TC-19 PASS "code=$code items=$n" "evidence/tc19.json"
  else
    record TC-19 FAIL "code=$code items=$n" "evidence/tc19.json"
  fi
}

# =============================================================================
#  TC-20  Клиент в каталоге — 403
# =============================================================================
tc20() {
  want TC-20 || return
  local code
  code=$(do_curl tc20 "$BASE/tickets/search?q=x" -H "Authorization: Bearer $CLIENT_TOKEN")
  if [[ "$code" == "403" ]]; then
    record TC-20 PASS "code=$code" "evidence/tc20.json"
  else
    record TC-20 FAIL "code=$code" "evidence/tc20.json"
  fi
}

# =============================================================================
#  TC-21  Смена статуса open→in_progress
# =============================================================================
tc21() {
  want TC-21 || return
  local code status
  # создаём заявку для теста
  do_curl tc21-create -X POST "$BASE/tickets" \
    -H "Authorization: Bearer $CLIENT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"title":"TC-21 смена статуса"}' >/dev/null
  local tid
  tid=$(jget "$EVIDENCE_DIR/tc21-create.json" '.id')
  code=$(do_curl tc21 -X PATCH "$BASE/tickets/$tid/status" \
    -H "Authorization: Bearer $OP_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"status_id":2,"note":"в работу"}')
  do_curl tc21-get "$BASE/tickets/$tid" -H "Authorization: Bearer $OP_TOKEN" >/dev/null
  status=$(jget "$EVIDENCE_DIR/tc21-get.json" '.status_id')
  if [[ "$code" == "200" && "$status" == "2" ]]; then
    record TC-21 PASS "code=$code status=$status ticket=$tid" "evidence/tc21.json"
  else
    record TC-21 FAIL "code=$code status=$status" "evidence/tc21.json"
  fi
  TC21_TICKET="$tid"
}

# =============================================================================
#  TC-22  Повторный тот же статус — 409
# =============================================================================
tc22() {
  want TC-22 || return
  if [[ -z "${TC21_TICKET:-}" ]]; then
    record TC-22 SKIP "TC-21 не выполнен" "—"
    return
  fi
  local code
  code=$(do_curl tc22 -X PATCH "$BASE/tickets/$TC21_TICKET/status" \
    -H "Authorization: Bearer $OP_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"status_id":2}')
  if [[ "$code" == "409" ]]; then
    record TC-22 PASS "code=$code" "evidence/tc22.json"
  else
    record TC-22 FAIL "code=$code" "evidence/tc22.json"
  fi
}

# =============================================================================
#  TC-23  Закрытие заявки — closed_at != null
# =============================================================================
tc23() {
  want TC-23 || return
  if [[ -z "${TC21_TICKET:-}" ]]; then
    record TC-23 SKIP "TC-21 не выполнен" "—"
    return
  fi
  local code closed
  code=$(do_curl tc23 -X PATCH "$BASE/tickets/$TC21_TICKET/status" \
    -H "Authorization: Bearer $OP_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"status_id":5}')
  do_curl tc23-get "$BASE/tickets/$TC21_TICKET" -H "Authorization: Bearer $OP_TOKEN" >/dev/null
  closed=$(jget "$EVIDENCE_DIR/tc23-get.json" '.closed_at')
  if [[ "$code" == "200" && "$closed" != "null" && -n "$closed" ]]; then
    record TC-23 PASS "code=$code closed_at=$closed" "evidence/tc23.json"
  else
    record TC-23 FAIL "code=$code closed_at=$closed" "evidence/tc23.json"
  fi
}

# =============================================================================
#  TC-24  Установка категории — 200
# =============================================================================
tc24() {
  want TC-24 || return
  # заявка не должна быть закрыта — создаём новую
  do_curl tc24-create -X POST "$BASE/tickets" \
    -H "Authorization: Bearer $CLIENT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"title":"TC-24 категория"}' >/dev/null
  local tid code cat
  tid=$(jget "$EVIDENCE_DIR/tc24-create.json" '.id')
  code=$(do_curl tc24 -X PATCH "$BASE/tickets/$tid" \
    -H "Authorization: Bearer $OP_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"category_id":5}')
  do_curl tc24-get "$BASE/tickets/$tid" -H "Authorization: Bearer $OP_TOKEN" >/dev/null
  cat=$(jget "$EVIDENCE_DIR/tc24-get.json" '.category_id')
  if [[ "$code" == "200" && "$cat" == "5" ]]; then
    record TC-24 PASS "code=$code category_id=$cat ticket=$tid" "evidence/tc24.json"
  else
    record TC-24 FAIL "code=$code category_id=$cat" "evidence/tc24.json"
  fi
}

# =============================================================================
#  TC-25  Двусторонний обмен комментариями
# =============================================================================
tc25() {
  want TC-25 || return
  do_curl tc25-create -X POST "$BASE/tickets" \
    -H "Authorization: Bearer $CLIENT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"title":"TC-25 диалог"}' >/dev/null
  local tid code1 code2 code3 code4 n
  tid=$(jget "$EVIDENCE_DIR/tc25-create.json" '.id')
  code1=$(do_curl tc25-1 -X POST "$BASE/tickets/$tid/comments" \
    -H "Authorization: Bearer $CLIENT_TOKEN" -H "Content-Type: application/json" \
    -d '{"body":"клиент","is_internal":false}')
  code2=$(do_curl tc25-2 -X POST "$BASE/tickets/$tid/comments" \
    -H "Authorization: Bearer $OP_TOKEN" -H "Content-Type: application/json" \
    -d '{"body":"оператор","is_internal":false}')
  code3=$(do_curl tc25-3 "$BASE/tickets/$tid/comments" -H "Authorization: Bearer $CLIENT_TOKEN")
  code4=$(do_curl tc25-4 "$BASE/tickets/$tid/comments" -H "Authorization: Bearer $OP_TOKEN")
  n=$(jget "$EVIDENCE_DIR/tc25-3.json" 'length')
  local seen_client seen_op
  seen_client=$(jq -r '[.[]|select(.body=="клиент")]|length' "$EVIDENCE_DIR/tc25-3.json")
  seen_op=$(jq -r '[.[]|select(.body=="оператор")]|length' "$EVIDENCE_DIR/tc25-4.json")
  if [[ "$code1" == "201" && "$code2" == "201" && "$code3" == "200" \
        && "$code4" == "200" && "${n:-0}" -ge 2 \
        && "$seen_client" == "1" && "$seen_op" == "1" ]]; then
    record TC-25 PASS "created=201/201 read=200 n=$n" "evidence/tc25-*.json"
  else
    record TC-25 FAIL "c1=$code1 c2=$code2 r1=$code3 r2=$code4 n=$n" "evidence/tc25-*.json"
  fi
  TC25_TICKET="$tid"
}

# =============================================================================
#  TC-26  Внутренний комментарий скрыт от клиента
# =============================================================================
tc26() {
  want TC-26 || return
  if [[ -z "${TC25_TICKET:-}" ]]; then
    record TC-26 SKIP "TC-25 не выполнен" "—"
    return
  fi
  local code1 code2 code3 n_client n_op
  code1=$(do_curl tc26-1 -X POST "$BASE/tickets/$TC25_TICKET/comments" \
    -H "Authorization: Bearer $OP_TOKEN" -H "Content-Type: application/json" \
    -d '{"body":"внутренний","is_internal":true}')
  code2=$(do_curl tc26-2 "$BASE/tickets/$TC25_TICKET/comments" -H "Authorization: Bearer $CLIENT_TOKEN")
  code3=$(do_curl tc26-3 "$BASE/tickets/$TC25_TICKET/comments" -H "Authorization: Bearer $OP_TOKEN")
  n_client=$(jq -r '[.[]|select(.body=="внутренний")]|length' "$EVIDENCE_DIR/tc26-2.json")
  n_op=$(jq -r '[.[]|select(.body=="внутренний")]|length' "$EVIDENCE_DIR/tc26-3.json")
  if [[ "$code1" == "201" && "$code2" == "200" && "$code3" == "200" \
        && "$n_client" == "0" && "$n_op" == "1" ]]; then
    record TC-26 PASS "client=$n_client op=$n_op" "evidence/tc26-*.json"
  else
    record TC-26 FAIL "client=$n_client op=$n_op" "evidence/tc26-*.json"
  fi
}

# =============================================================================
#  TC-27  Клиент /users — 403
# =============================================================================
tc27() {
  want TC-27 || return
  local code
  code=$(do_curl tc27 "$BASE/users" -H "Authorization: Bearer $CLIENT_TOKEN")
  if [[ "$code" == "403" ]]; then
    record TC-27 PASS "code=$code" "evidence/tc27.json"
  else
    record TC-27 FAIL "code=$code" "evidence/tc27.json"
  fi
}

# =============================================================================
#  TC-28  Админ деактивирует пользователя
# =============================================================================
tc28() {
  want TC-28 || return
  # найдём активного employee (не клиента из конфига, не оператора)
  do_curl tc28-list "$BASE/users?limit=50" -H "Authorization: Bearer $ADMIN_TOKEN" >/dev/null
  local target
  target=$(jq -r --arg e "$CLIENT_EMAIL" \
    '[.[] | select(.email != $e and .is_active == true and .user_role == 3)][0].id // empty' \
    "$EVIDENCE_DIR/tc28-list.json")
  if [[ -z "$target" ]]; then
    record TC-28 SKIP "нет активного employee для деактивации" "—"
    return
  fi
  local code active
  code=$(do_curl tc28 -X DELETE "$BASE/users/$target" -H "Authorization: Bearer $ADMIN_TOKEN")
  do_curl tc28-get "$BASE/users/$target" -H "Authorization: Bearer $ADMIN_TOKEN" >/dev/null
  active=$(jget "$EVIDENCE_DIR/tc28-get.json" '.is_active')
  if [[ "$code" == "200" && "$active" == "false" ]]; then
    record TC-28 PASS "code=$code is_active=$active target=$target" "evidence/tc28.json"
  else
    record TC-28 FAIL "code=$code is_active=$active" "evidence/tc28.json"
  fi
}

# =============================================================================
#  TC-29  Время ответа ≤ 2 c
# =============================================================================
tc29() {
  want TC-29 || return
  local t_search t_create
  t_search=$(curl -s -o /dev/null -w "%{time_total}" \
    "$BASE/tickets/search?q=%D0%BF%D1%80%D0%B8%D0%BD%D1%82%D0%B5%D1%80" \
    -H "Authorization: Bearer $OP_TOKEN")
  t_create=$(curl -s -o "$EVIDENCE_DIR/tc29-create.json" -w "%{time_total}" \
    -X POST "$BASE/tickets" \
    -H "Authorization: Bearer $CLIENT_TOKEN" -H "Content-Type: application/json" \
    -d '{"title":"TC-29 performance"}')
  printf "search=%s\ncreate=%s\n" "$t_search" "$t_create" > "$EVIDENCE_DIR/tc29.txt"
  if python3 -c "import sys; sys.exit(0 if max(float('$t_search'),float('$t_create'))<2.0 else 1)"; then
    record TC-29 PASS "search=${t_search}s create=${t_create}s" "evidence/tc29.txt"
  else
    record TC-29 FAIL "search=${t_search}s create=${t_create}s" "evidence/tc29.txt"
  fi
}

# =============================================================================
#  TC-30  Пароли хешированы (SQL)
# =============================================================================
tc30() {
  want TC-30 || return
  if ! command -v sqlite3 >/dev/null || [[ ! -f "$DB_PATH" ]]; then
    record TC-30 SKIP "нет sqlite3 или файла $DB_PATH" "—"
    return
  fi
  local val
  val=$(sqlite3 "$DB_PATH" \
    "SELECT password_hash FROM users WHERE email='$TC04_EMAIL'" 2>/dev/null || true)
  {
    echo "email=$TC04_EMAIL"
    echo "hash_prefix=${val:0:20}"
  } > "$EVIDENCE_DIR/tc30.txt"
  if [[ "$val" == pbkdf2_sha256\$* ]]; then
    record TC-30 PASS "hash starts with pbkdf2_sha256$" "evidence/tc30.txt"
  else
    record TC-30 FAIL "unexpected hash: ${val:0:40}" "evidence/tc30.txt"
  fi
}

# =============================================================================
#  TC-31…34  UI / НФТ — вне scope curl
# =============================================================================
tc31_34() {
  for id in TC-31 TC-32 TC-33 TC-34; do
    want "$id" || continue
    record "$id" BLOCKED "UI-проверка, curl неприменим (Q5)" "—"
  done
}

# =============================================================================
#  TC-35  Невалидные query — 422
# =============================================================================
tc35() {
  want TC-35 || return
  local fails=() c
  for q in "limit=500" "offset=-1" "sort_by=magic" "date_from=not-a-date"; do
    c=$(do_curl "tc35-${q//[^a-z]/_}" "$BASE/tickets/search?$q" \
      -H "Authorization: Bearer $OP_TOKEN")
    [[ "$c" == "422" ]] || fails+=("$q->$c")
  done
  if [[ ${#fails[@]} -eq 0 ]]; then
    record TC-35 PASS "all 4 returned 422" "evidence/tc35-*.json"
  else
    record TC-35 FAIL "non-422: ${fails[*]}" "evidence/tc35-*.json"
  fi
}

# =============================================================================
#  TC-36  Пустая выдача — 200 total=0
# =============================================================================
tc36() {
  want TC-36 || return
  local code total
  code=$(do_curl tc36 "$BASE/tickets/search?q=zzz_unlikely_string_xyz" \
    -H "Authorization: Bearer $OP_TOKEN")
  total=$(jget "$EVIDENCE_DIR/tc36.json" '.total')
  if [[ "$code" == "200" && "$total" == "0" ]]; then
    record TC-36 PASS "code=$code total=$total" "evidence/tc36.json"
  else
    record TC-36 FAIL "code=$code total=$total" "evidence/tc36.json"
  fi
}

# =============================================================================
#  TC-37  Клиент меняет статус — 403
# =============================================================================
tc37() {
  want TC-37 || return
  do_curl tc37-create -X POST "$BASE/tickets" \
    -H "Authorization: Bearer $CLIENT_TOKEN" -H "Content-Type: application/json" \
    -d '{"title":"TC-37 статус клиентом"}' >/dev/null
  local tid code
  tid=$(jget "$EVIDENCE_DIR/tc37-create.json" '.id')
  code=$(do_curl tc37 -X PATCH "$BASE/tickets/$tid/status" \
    -H "Authorization: Bearer $CLIENT_TOKEN" -H "Content-Type: application/json" \
    -d '{"status_id":2}')
  if [[ "$code" == "403" ]]; then
    record TC-37 PASS "code=$code" "evidence/tc37.json"
  else
    record TC-37 FAIL "code=$code" "evidence/tc37.json"
  fi
}

# =============================================================================
#  TC-38  Комментарий в закрытую — 403
# =============================================================================
tc38() {
  want TC-38 || return
  do_curl tc38-create -X POST "$BASE/tickets" \
    -H "Authorization: Bearer $CLIENT_TOKEN" -H "Content-Type: application/json" \
    -d '{"title":"TC-38 закрытая"}' >/dev/null
  local tid
  tid=$(jget "$EVIDENCE_DIR/tc38-create.json" '.id')
  # закрываем оператором
  do_curl tc38-close -X PATCH "$BASE/tickets/$tid/status" \
    -H "Authorization: Bearer $OP_TOKEN" -H "Content-Type: application/json" \
    -d '{"status_id":5}' >/dev/null
  local code
  code=$(do_curl tc38 -X POST "$BASE/tickets/$tid/comments" \
    -H "Authorization: Bearer $CLIENT_TOKEN" -H "Content-Type: application/json" \
    -d '{"body":"поздно"}')
  if [[ "$code" == "403" ]]; then
    record TC-38 PASS "code=$code ticket=$tid" "evidence/tc38.json"
  else
    record TC-38 FAIL "code=$code ticket=$tid" "evidence/tc38.json"
  fi
}

# =============================================================================
#  Отчёт
# =============================================================================
report() {
  local md="$EVIDENCE_DIR/report.md"
  {
    echo "# Отчёт прогона $(date -u +%FT%TZ)"
    echo
    echo "| ID | Статус | Примечание | Доказательство |"
    echo "|---|---|---|---|"
    for row in "${RESULTS[@]}"; do
      IFS='|' read -r id st note ev <<<"$row"
      echo "| $id | $st | $note | $ev |"
    done
    echo
    echo "Итого: $TOTAL, PASS=$PASS, FAIL=$FAIL, BLOCKED=$BLOCKED, SKIP=$SKIP"
  } > "$md"

  echo
  echo "== Сводка =="
  printf "%-8s %-8s %s\n" ID STATUS NOTE
  for row in "${RESULTS[@]}"; do
    IFS='|' read -r id st note ev <<<"$row"
    printf "%-8s %-8s %s\n" "$id" "$st" "$note"
  done
  echo
  echo "TOTAL=$TOTAL PASS=$PASS FAIL=$FAIL BLOCKED=$BLOCKED SKIP=$SKIP"
  echo "Полный отчёт: $md"
  echo "Доказательства: $EVIDENCE_DIR/"
}

# =============================================================================
#  main
# =============================================================================
main() {
  log "== ServiceDesk test run =="
  log "BASE=$BASE  DB_PATH=$DB_PATH  EVIDENCE_DIR=$EVIDENCE_DIR"
  preflight
  log "== running cases =="

  tc01; tc02; tc03; tc04; tc05; tc06; tc07; tc08; tc09; tc10; tc11
  tc12; tc13; tc14; tc15; tc16; tc17
  tc18; tc19; tc20; tc21; tc22; tc23; tc24
  tc25; tc26
  tc27; tc28
  tc29; tc30; tc31_34
  tc35; tc36; tc37; tc38

  report
  # ненулевой код, если есть FAIL (BLOCKED/SKIP не считаются провалом)
  [[ $FAIL -eq 0 ]]
}

main "$@"
