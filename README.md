# Eco Monitoring: каркас сервиса

FastAPI + PostgreSQL в docker compose. Есть: миграции, ручки просмотра, middleware логов и готовая точка подключения парсеров. Очередей (RabbitMQ/Celery) нет, их можно добавить позже.

## Запуск

```bash
cp .env.example .env
docker compose up --build
```

- Swagger: http://localhost:8000/docs
- Postgres снаружи: `localhost:5432` (порт меняется через `DB_PORT` в `.env`)
- pgAdmin: http://localhost:5050, вход `admin@example.com` / `admin` (из `.env`). Сервер «eco (docker)» уже добавлен, при первом подключении введите пароль БД (по умолчанию `eco`) и отметьте «Save password»
- Порядок старта: `db` → `migrate` (Alembic, одноразово) → `api`

Проверить, что всё работает, на демо-данных:

```bash
docker compose exec api python -m app.cli collect demo
```

Затем откройте `GET /api/v1/measurements`: появятся 3 тестовые записи. Повторный запуск дублей не создаёт.

## Как подключить парсер

1. Создайте `app/sources/<имя>.py` с классом, у которого есть `code` и `fetch() -> list[MeasurementIn]`. За образец возьмите `app/sources/demo.py`.
2. Добавьте класс в `REGISTRY` в `app/sources/registry.py`.
3. Нужные библиотеки (`httpx`, `beautifulsoup4` и т.п.) допишите в `requirements.txt` и пересоберите: `docker compose up --build`.
4. Запуск: `docker compose exec api python -m app.cli collect <code>` или `POST /api/v1/sources/<code>/collect` (синхронно, ждёт завершения).

Что делает парсер, а что каркас:

| Парсер (адаптер) | Каркас (`services/ingest.py`) |
|---|---|
| достаёт данные, разбирает, приводит к `MeasurementIn` | создаёт станции и параметры, если их нет |
| приводит единицы к каноническим | отклоняет записи с единицей, не совпавшей со справочником |
| пропускает и логирует битые записи | пишет в БД пачками, не создаёт дублей |

Формат полей и правила для каждого источника: `docs/data-contract.md`. Модели данных: `app/contract.py`. Там же готовые хелперы для orsha-ecokarta: `parse_ru_coords`, `parse_ru_period`, `normalize_unit`.

Периодический сбор пока можно делать cron'ом на сервере: `docker compose exec -T api python -m app.cli collect <code>`.

## Ручки (`/api/v1`)

| Метод и путь | Что делает |
|---|---|
| `GET /health`, `GET /ready` | liveness; readiness (проверяет БД); лежат вне `/api/v1` |
| `GET /sources` | источники, число станций и измерений, диапазон дат |
| `POST /sources/{code}/collect` | запустить сбор источника из реестра |
| `GET /parameters` | справочник параметров с единицами |
| `GET /stations` | станции; фильтры `source`, `kind`, `bbox`, `q`; `limit`, `offset` |
| `GET /stations/geojson` | то же как GeoJSON для карты (координаты `[lon, lat]`) |
| `GET /stations/{id}` | одна станция |
| `GET /measurements` | измерения; фильтры `source`, `station_id`, `parameter`, `kind`, `sub_point`, `date_from`, `date_to`; `limit` (до 1000), `offset`, `order` |

Фильтры-списки принимают несколько значений: `?parameter=air_co&parameter=air_no2`. Даты без часового пояса считаются минскими. Время в ответах выводится с `+03:00`.

## Логи

Одна строка JSON на запрос (`LOG_JSON=false` включает читаемый текст):

```json
{"ts":"...","level":"INFO","logger":"app.request","msg":"request","request_id":"9b8c05e9...","method":"GET","path":"/api/v1/measurements","query":"parameter=air_co","status":200,"duration_ms":12.4,"client":"172.18.0.1","user_agent":"..."}
```

- `X-Request-ID` берётся из запроса (если он безопасный) или генерируется, возвращается в ответе и попадает во все логи этого запроса.
- 4xx пишутся как WARNING, 5xx как ERROR (необработанное исключение со стеком), `/health` и `/ready` на DEBUG.
- Смотреть: `docker compose logs -f api`.

## Структура

```
app/
  main.py              сборка приложения, middleware, роутеры
  cli.py               python -m app.cli collect <code>
  contract.py          контракт данных (Pydantic) + хелперы разбора
  models.py            ORM-модели (совпадают с docs/data-contract.md)
  core/                config, db (сессии), logging
  api/                 middleware, deps (фильтры из query), schemas, routers/
  services/
    filters.py         фильтры выборок (пригодятся и для экспорта CSV)
    ingest.py          запись измерений в БД + collect(code)
  sources/             адаптеры источников: demo.py (шаблон), registry.py
docker/pgadmin/        servers.json: автоподключение pgAdmin к БД
alembic/               миграции (0001: таблицы + справочник параметров)
docs/data-contract.md  контракт данных для всей команды
```

## Что не проверено

Код писался без возможности установить зависимости: проверены синтаксис Python и YAML, а логика middleware прогнана на заглушке ASGI. Сам стек (`docker compose up`, миграции, запросы к БД, `ingest`) ещё не запускался. Первый запуск может потребовать мелких правок.
