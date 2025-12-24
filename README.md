# DeepState Reports

Пайплайн: Playwright-скрапер → гео-анализ → отчёты для Telegram.

## Быстрый старт (Docker)

1) Соберите/запустите локально через docker-compose:
```
docker compose build
docker compose run --rm scraper
```
Артефакты данных сохраняются в ./data

2) Запуск готового образа из GHCR (после публикации):
```
# Замените OWNER и REPO на ваши значения, а TAG на нужный тег (например, main или v0.1.0)
docker run --rm \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/artifacts:/app/artifacts \
  ghcr.io/OWNER/REPO:TAG
```

Ссылка на образ: https://ghcr.io/OWNER/REPO

## Конфигурация
Используется файл .env (см. .env.example). Подробнее: docs/configuration.md

Основные параметры:
- HEADLESS — режим браузера (true/false)
- NAV_TIMEOUT_MS, WAIT_NETWORK_IDLE_MS — тайминги Playwright
## Загрузка истории в БД (backfill)

1) Поднимите БД и примените миграции (или создайте таблицы):
- MySQL через Docker: `docker compose up -d mysql`
- Миграции: `python scripts/db_upgrade.py`

2) Загрузите слои за период в таблицу `layers`:
```bash
# пример: период (формат YYYY_MM_DD)
python scripts/backfill_layers.py --from 2024_01_01 --to 2024_01_31 --create-tables --skip-existing

# пример: последние 7 дней
python scripts/backfill_layers.py --days 7 --create-tables --skip-existing

# пример: только occupied/gray
python scripts/backfill_layers.py --days 30 --classes occupied,gray --create-tables --skip-existing
```

3) Постройте отчёт за две даты, читая слои из БД (без файлов/первоисточника):
```bash
python scripts/generate_report_db.py --from 2024_01_01 --to 2024_01_02 --classes occupied,gray

# сохранить текст отчёта в таблицу reports (для конечной даты)
python scripts/generate_report_db.py --from 2024_01_01 --to 2024_01_02 --classes occupied,gray --store
```

4) Постройте отчёт за период (день-за-днём + итог):
```bash
python scripts/generate_period_report_db.py --from 2024_01_01 --to 2024_01_31 --classes occupied,gray --top-n 10
```

Примечание: периодный отчёт использует только те даты, которые реально присутствуют в таблице `layers`.

Подключение к БД:
- по умолчанию используется MySQL из переменных `MYSQL_*`
- либо можно указать `DATABASE_URL` (например, SQLite):
  `DATABASE_URL=sqlite+pysqlite:///./deepstate.db python scripts/backfill_layers.py --days 30 --create-tables`

## Разработка
- Установка pre-commit: `pip install pre-commit && pre-commit install`
- Запуск проверок: `pre-commit run --all-files`
- Тесты: `pytest`

## Структура
- src/data_io/scraper.py — структурированный скрапер (Playwright)
- src/domain/geo_changes.py — вычисление изменений (скелет)
- src/reporting/report_generator.py — генерация текста отчёта
- src/bot/app.py — каркас бота
- docs/ — гайды по стилю, тестам и CI/CD

## CI/CD
- .github/workflows/ci.yml — линт, типы, тесты
- .github/workflows/e2e_playwright.yml — e2e (опционально, по расписанию/ручной запуск)
- .github/workflows/docker-publish.yml — публикация образа в GHCR

## Telegram-бот
- Команды: /start (подписка), /stop (отписка), /report (получить отчёт сейчас)
- Запуск локально: `python scripts/run_bot.py`
- Docker: `docker compose up -d bot` (в текущей версии Telegram-бот отключён)
