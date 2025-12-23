# Конфигурация проекта

Файл `.env` (см. .env.example) используется для настройки поведения приложения.

Параметры:
- ENV: профиль окружения (dev/test/prod)
- HEADLESS: запуск браузера без UI (true/false)
- USER_AGENT: переопределение User-Agent (опционально)
- NAV_TIMEOUT_MS: таймаут навигации Playwright
- WAIT_NETWORK_IDLE_MS: ожидание тишины в сети после загрузки
- TELEGRAM_BOT_TOKEN: токен бота
- TELEGRAM_ADMIN_IDS: список админов через запятую

Файлы и каталоги:
- data/YYYY/MM/deepstate_data_YYYY_MM_DD.json — артефакты скрапера
- logs/ и artifacts/ — для логов и скриншотов/отчетов (при необходимости)
