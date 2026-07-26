# Simular Gateway - Неофициальный мост к облачным моделям Simular Pro (Sai)

Минимальный локальный прокси, который открывает облачные модели Simular Pro (Sai) как Anthropic/Google-совместимый API для использования в OpenCode или подобных агентных клиентах.

> **Неофициальный проект.** Это реверс-инжиниринг моста, построенного на основе наблюдения за сетевыми вызовами десктоп-приложения Simular (v1.12.1). Проект не аффилирован с Simular, не одобрен и не поддерживается ей. Может сломаться без предупреждения при изменении API Simular.

## Как это работает

1. Вы входите в официальное **десктоп-приложение Simular** хотя бы раз — это сохраняет Firebase refresh-токен в `~/.simulang/credentials.json` на вашей машине.
2. Этот шлюз читает уже существующий файл credentials (он **не** реализует собственный вход) и автоматически обновляет короткоживущий Firebase idToken (~1 час) через эндпоинт Google `securetoken`.
3. Он проксирует входящие запросы в облако Simular, добавляя заголовки `Authorization: Bearer <idToken>` и обязательный `X-Goal`, слушая только на `127.0.0.1`.

## Доступные модели

| ID модели | Базовая модель |
|---|---|
| `simular-claude/claude-opus-4-8` | Claude 4.8 Opus |
| `simular-gemini/gemini-3.1-pro-preview` | Gemini 3.1 Pro |

Обе поддерживают полный tool-calling, поэтому работают как полноценные агенты в OpenCode (edit/bash/read и т.д.), как и любая другая модель.

## Быстрый старт

### Требования

- Python 3.10+ с `pythonw` в PATH (или отредактируйте `start.ps1`, указав свой путь к Python)
- Официальное десктоп-приложение Simular, установленное и хотя бы раз авторизованное (создаёт `~/.simulang/credentials.json`)

### Настройка

```bash
git clone https://github.com/susmnavorasem/Simular-Gateway.git
cd Simular-Gateway
pip install -r requirements.txt
```

### Запуск

Без окна (Windows, headless):
```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```
Идемпотентно — если уже запущен на порту 8799, ничего не делает.

Или напрямую (любая ОС):
```bash
python server.py
```

### Проверка здоровья

```bash
curl http://127.0.0.1:8799/health
# {"status":"ok","signed_in":true}
```

### Остановка (Windows)

```powershell
Get-NetTCPConnection -LocalPort 8799 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

## Конфигурация

| Файл | Роль |
|---|---|
| `server.py` | FastAPI passthrough-прокси (только пути Anthropic + Google) |
| `token_manager.py` | Читает `credentials.json`, обновляет idToken, single-flight (без гонок дублирующих обновлений) |
| `config.py` | Хост/порт/URL/пути, все переопределяемы через переменные окружения |
| `logs/gateway.log` | Рантайм-лог — проверено, что никогда не содержит токенов |

Порт, хост и upstream URL можно переопределить через переменные окружения — точные имена и значения по умолчанию см. в `config.py`.

## Замечание по безопасности: Firebase API-ключ

`config.py` содержит значение `FIREBASE_API_KEY` (`AIzaSy...`). Это **не секрет** — это стандартный "Web API key" Google Firebase, публичный клиентский идентификатор, извлечённый из бандла приложения Simular. Firebase Web API-ключи предназначены для встраивания в клиентские приложения; реальная граница безопасности — это серверные security rules Firebase и собственный refresh-токен пользователя (который никогда не покидает вашу машину и никогда не логируется). Это тот же ключ, с которым поставляется само официальное приложение Simular.

## Ограничения

- Нет менеджера аккаунтов, нет UI — это намеренно минимальный вариант (Variant C). Токен полностью берётся из сессии входа в приложение Simular.
- Если вы выйдете из приложения Simular, удалите `credentials.json`, или refresh-токен истечёт — шлюз вернёт HTTP 503, пока вы не войдёте обратно в приложение.
- Порт 8799 выбран, чтобы избежать типичных зарезервированных динамических диапазонов портов Windows.
- Пути эндпоинтов получены реверс-инжинирингом вызова `createModel()` приложения Simular v1.12.1 — будущее обновление приложения Simular может сломать это без предупреждения.

## Лицензия

Исходный код: [CC BY-NC 4.0](LICENSE) — свободно для некоммерческого использования. Коммерческое использование требует отдельной лицензии — см. [COMMERCIAL-LICENSING.md](COMMERCIAL-LICENSING.md).

Copyright (c) 2026 susmnavorasem.
