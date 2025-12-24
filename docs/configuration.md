# Конфигурация проекта

Файл `.env` (см. .env.example) используется для настройки поведения приложения.

Параметры:
- DATABASE_URL: SQLAlchemy DSN (опционально). Если задан, используется вместо MYSQL_* (удобно для SQLite: sqlite+pysqlite:///./deepstate.db)
- ENV: профиль окружения (dev/test/prod)
- HEADLESS: запуск браузера без UI (true/false)
- USER_AGENT: переопределение User-Agent (опционально)
- NAV_TIMEOUT_MS: таймаут навигации Playwright
- WAIT_NETWORK_IDLE_MS: ожидание тишины в сети после загрузки
- ENDPOINT_WHITELIST: список подстрок/regex через запятую для отбора нужных API-эндпоинтов
- ENDPOINT_BLACKLIST: исключающие подстроки/regex (имеют приоритет над whitelist)
- MIN_JSON_BYTES: минимальный размер JSON-ответа в байтах, меньше — игнорировать
- SAVE_RAW_JSON: сохранять сырые JSON-ответы для отладки (true/false)
- TELEGRAM_ADMIN_IDS: список админов через запятую (Telegram-бот сейчас отключён)

Файлы и каталоги:
- data/YYYY/MM/deepstate_data_YYYY_MM_DD.json — артефакты скрапера
- logs/ и artifacts/ — для логов и скриншотов/отчетов (при необходимости)
