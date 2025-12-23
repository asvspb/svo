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
- TELEGRAM_BOT_TOKEN — токен бота (для будущего этапа)

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
