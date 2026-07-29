---
name: shell-testing-gate
description: >
  Правила запуска, создания и отладки Shell-скриптов верификации, гейтов и тестовых раннеров
  (scripts/verify-*.sh, scripts/test-*.sh и проектные end-to-end runners).
  Дисциплина set -euo pipefail, изоляции БД, LAN-биндингов, зачистки фоновых процессов и кодов возврата.
license: MIT
metadata:
  category: testing-gate
  complexity: intermediate
  author: gov-harness
  version: 1.0
---

# Shell Testing & Verification Gate

В целевом репозитории Shell-скрипты обычно выполняют роль оркестраторов
верификационных гейтов. Точные имена runners принадлежат локальному environment
и не зашиваются в этот скилл.

Этот скилл определяет обязательные стандарты для написания, отладки и запуска Bash/Shell скриптов верификации.

---

## Когда использовать этот скилл

Применяй `shell-testing-gate`, когда:
- Запускаешь, модифицируешь или создаешь Shell-скрипты проверки (`scripts/verify-*.sh`, `scripts/test-*.sh`, `scripts/check-*.sh`).
- Запускаешь проектный сквозной runner или общий documentation gate.
- Настраиваешь перезапуск баз данных, прогоны миграций или локальный стенд.

---

## 1. Режим строгой обработки ошибок (Strict Mode)

Каждый верификационный bash-скрипт **ОБЯЗАН** начинаться со строгой настройки упавшего завершения:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

- `-e`: Немедленный выход при ошибке любой команды.
- `-u`: Выход при обращении к необъявленной переменной.
- `-o pipefail`: Сохранение кода ошибки, если упала любая команда в конвейере (`cmd1 | cmd2`).

---

## 2. Изоляция баз данных и защитные переменные

1. **Защита от случайного сброса**: Для скриптов сброса или бутстрапа БД всегда требовать явное совпадение имени переменной разрешения:
   ```bash
   : "${POSTGRES_DB:?Set an isolated database name explicitly}"
   ALLOW_DESTRUCTIVE_DB_BOOTSTRAP="${ALLOW_DESTRUCTIVE_DB_BOOTSTRAP:-}"

   if [ "$ALLOW_DESTRUCTIVE_DB_BOOTSTRAP" != "$POSTGRES_DB" ]; then
     echo "ERROR: Destruction not allowed for DB $POSTGRES_DB" >&2
     exit 1
   fi
   ```
2. **Локальная migration policy**: DDL-first, migration bypass и dry-run
   применяются только когда их объявляет целевой проект.

---

## 3. Биндинг сетевых адресов (Network Binding Rules)

- **Слушатели (Listeners)**: Бэкенд, сервисы и БД настраиваются на слушивание `0.0.0.0` (для доступности в сети).
- **Клиентские вызовы (Curl / Psql / Netcat)**: Клиенты подключаются к конкретному адресу `127.0.0.1` или LAN IP. Передача `0.0.0.0` в клиентское соединение запрещена.

---

## 4. Зачистка фоновых процессов (Cleanup Traps)

Если скрипт запускает фоновые сервисы или веб-серверы (`&`), он должен гарантировать их остановку при завершении или сбое:

```bash
cleanup() {
  echo "Cleaning up background processes..."
  kill $(jobs -p) 2>/dev/null || true
}
trap cleanup EXIT INT TERM
```

---

## 5. Ожидание готовности сервисов (Health Polling)

Не используй слепые `sleep 10`. Используй цикл проверки готовности с ограничением попыток:

```bash
MAX_RETRIES=30
COUNT=0
until curl -s http://127.0.0.1:5000/health > /dev/null || [ $COUNT -eq $MAX_RETRIES ]; do
  sleep 1
  COUNT=$((COUNT + 1))
done

if [ $COUNT -eq $MAX_RETRIES ]; then
  echo "ERROR: Service failed to start within timeout" >&2
  exit 1
fi
```

---

## 6. Чек-лист проверки Shell-скрипта перед сдачей

- [ ] Установлен `set -euo pipefail`.
- [ ] Оформлена ловушка `trap cleanup EXIT` для фоновых процессов.
- [ ] Все вызовы внешних утилит завершаются с корректным кодом выхода.
- [ ] Скрипт проверен прогоном в реальном bash-окружении: `bash scripts/your-script.sh`.
