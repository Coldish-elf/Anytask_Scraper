# Конфигурация

## Файл настроек

Проект использует файл настроек `.anytask_scraper_settings.json` для хранения путей и параметров по умолчанию. Этот файл обычно находится в текущей рабочей директории.

Пример содержимого:

```json
{
  "credentials_file": "./credentials.json",
  "session_file": "./.anytask_session.json",
  "status_mode": "errors",
  "default_output": "./output",
  "save_session": true,
  "refresh_session": false,
  "auto_login_session": true,
  "debug": false
}
```

### Описание параметров

| Ключ                 | Тип     | Описание                                                                 |
| -------------------- | ------- | ------------------------------------------------------------------------ |
| `credentials_file`   | string  | Путь к файлу с логином и паролем.                                        |
| `session_file`       | string  | Путь к файлу cookies (сессии).                                           |
| `status_mode`        | string  | Режим отображения статуса: `"all"` (все) или `"errors"` (только ошибки). |
| `default_output`     | string  | Папка по умолчанию для экспорта данных.                                  |
| `save_session`       | boolean | Автоматически сохранять сессию после команд.                             |
| `refresh_session`    | boolean | Принудительно обновлять сессию (игнорировать сохраненную).               |
| `auto_login_session` | boolean | Автоматически входить в TUI, используя сохраненную сессию.               |
| `debug`              | boolean | Включить режим отладки (расширенное логирование).                        |

## Управление настройками (CLI)

Вы можете управлять настройками через команду `settings`.

### Инициализация

Создать файл настроек с рекомендуемыми значениями и шаблон `credentials.json`:

```bash
anytask-scraper settings init
```

### Просмотр текущих настроек

```bash
anytask-scraper settings show
```

### Изменение настроек

Изменить один или несколько параметров:

```bash
anytask-scraper settings set --default-output ./my_data --status-mode all
anytask-scraper settings set --debug
```

### Очистка настроек

Вернуть дефолтное значение:

```bash
anytask-scraper settings clear session_file
```

Удалить вообще все настройки:

```bash
anytask-scraper settings clear
```

## Файл учетных данных (credentials)

Для автоматического входа создайте файл `credentials.json` (или `.env`).

**Формат JSON (рекомендуемый):**

```json
{
  "username": "ivanov",
  "password": "secret_password"
}
```

**Формат Key-Value:**

```text
username=ivanov
password=secret_password
```

**Простой текстовый формат:**

```text
ivanov
secret_password
```

## Использование переменных окружения

Приложение напрямую не считывает переменные окружения (env vars), но вы можете использовать их в командной строке (особенности вашего shell).

Пример запуска через `.env`:

1. Создайте файл `.env`:

   ```env
   ANYTASK_USERNAME=your_login
   ANYTASK_PASSWORD=your_password
   ```

2. Запустите с подстановкой переменных:

   ```bash
   export $(cat .env | xargs)
   # или
   # source .env

   anytask-scraper -u "$ANYTASK_USERNAME" -p "$ANYTASK_PASSWORD" course -c 12345
   ```
