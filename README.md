# anytask-scraper

`anytask-scraper` - CLI и Python-библиотека для сбора данных с [anytask.org](https://anytask.org).

## Возможности

- Авторизация через логин/пароль и/или сохраненную cookie-сессию.
- Парсинг страниц курса в student и teacher view.
- Сбор очереди на проверку с фильтрами.
- `deep`-режим для загрузки submission.
- Скачивание файлов и Colab-ноутбуков из комментариев submission.
- Экспорт в `json`, `markdown` и вывод в `table`.
- Сохранение CLI-настроек через `settings`.

## Установка

Требуется Python 3.10+.

```bash
git clone https://github.com/Coldish-elf/Anytask_Scraper
cd Anytask_Scraper
pip install -e .
```

Проверка:

```bash
anytask-scraper --help
```

## Быстрый старт CLI

### Рекомендуемый (через settings и default)

1. Создайте `credentials.json`:

```json
{
  "username": "your_login",
  "password": "your_password"
}
```

2. Инициализируйте настройки по умолчанию:

```bash
anytask-scraper settings init
```

3. Первый запуск(для сохранения сессии):

```bash
anytask-scraper course -c course_id
```

4. Следующие запуски:

```bash
anytask-scraper queue -c course_id
```

`settings init` уже выставляет:

- `credentials_file: ./credentials.json`
- `session_file: ./.anytask_session.json`
- `status_mode: errors`
- `default_output: ./output`
- `save_session: true`
- `refresh_session: false`

Если нужны другие пути/значения, измените только нужные поля:

```bash
anytask-scraper settings set --default-output ./reports
```

### Вариант 2. Без settings (ручной запуск)

```bash
anytask-scraper \
  --credentials-file ./credentials.json \
  --session-file ./.anytask_session.json \
  course -c course_id -f json -o ./output
```

Повторный запуск после сохранения сессии:

```bash
anytask-scraper --session-file ./.anytask_session.json queue -c course_id
```

### Вариант 3. Через `.env`

CLI не читает переменные окружения автоматически, но их можно подставить в `--username/--password`.

1. Создайте `.env`:

```dotenv
ANYTASK_USERNAME=your_login
ANYTASK_PASSWORD=your_password
```

2. Экспортируйте переменные и запустите:

```bash
set -a
source .env
set +a

anytask-scraper \
  -u "$ANYTASK_USERNAME" \
  -p "$ANYTASK_PASSWORD" \
  --session-file ./.anytask_session.json \
  course -c course_id
```

## Возможности CLI

Общий формат:

```bash
anytask-scraper [GLOBAL_OPTIONS] {course,queue,settings} ...
```

### Глобальные опции

- `-h, --help` - справка.
- `-u, --username USERNAME` - логин Anytask.
- `-p, --password PASSWORD` - пароль Anytask.
- `--credentials-file CREDENTIALS_FILE` - путь к credentials-файлу (`json` или `key=value`).
- `--session-file SESSION_FILE` - путь к файлу cookie-сессии.
- `--status-mode {all,errors}` - показывать все статусы или только ошибки.
- `--default-output DEFAULT_OUTPUT` - директория вывода по умолчанию для `course/queue`.
- `--save-session`, `--no-save-session` - сохранять/не сохранять сессию в конце.
- `--refresh-session`, `--no-refresh-session` - игнорировать сохраненную сессию и принудительно перелогиниться.
- `--settings-file SETTINGS_FILE` - путь к файлу настроек (по умолчанию `.anytask_scraper_settings.json`).

### Команда `course`

Синтаксис:

```bash
anytask-scraper [GLOBAL_OPTIONS] course -c COURSE_ID [COURSE_ID ...] [OPTIONS]
```

Опции:

- `-c, --course` - один или несколько ID курсов (обязательно).
- `-o, --output` - директория вывода (`--default-output` или `.` если не задано).
- `-f, --format {json,markdown,table}` - формат вывода (по умолчанию `json`).
- `--show` - дополнительно вывести rich-таблицу в терминал.
- `--fetch-descriptions` - догрузить описания задач (дополнительные запросы).

Примеры:

```bash
anytask-scraper course -c course_id
anytask-scraper course -c course_id 1001 -f markdown -o ./reports
anytask-scraper course -c course_id -f table
anytask-scraper course -c course_id --fetch-descriptions --show
```

### Команда `queue`

Синтаксис:

```bash
anytask-scraper [GLOBAL_OPTIONS] queue -c COURSE_ID [OPTIONS]
```

Опции:

- `-c, --course` - ID курса (обязательно).
- `-o, --output` - директория вывода (`--default-output` или `.` если не задано).
- `-f, --format {json,markdown,table}` - формат вывода (по умолчанию `json`).
- `--show` - дополнительно вывести rich-таблицу в терминал.
- `--deep` - загрузить полные страницы submission.
- `--download-files` - скачать файлы из submission (автоматически включает `--deep`).
- `--filter-task` - фильтр по названию задачи (substring).
- `--filter-reviewer` - фильтр по имени проверяющего (substring).
- `--filter-status` - фильтр по статусу (substring).

Примеры:

```bash
anytask-scraper queue -c course_id
anytask-scraper queue -c course_id -f markdown -o ./reports
anytask-scraper queue -c course_id --deep --show
anytask-scraper queue -c course_id --download-files -o ./downloads
anytask-scraper queue -c course_id --filter-task "HW1" --filter-status "Waiting"
```

### Команда `settings`

Синтаксис:

```bash
anytask-scraper settings {init,show,set,clear} [OPTIONS]
```

#### `settings init`

Создает файл настроек с рекомендованными значениями.

```bash
anytask-scraper settings init
```

#### `settings show`

Показывает текущие сохраненные настройки в JSON.

```bash
anytask-scraper settings show
```

#### `settings set`

Обновляет одну или несколько настроек.

Опции:

- `--credentials-file`
- `--session-file`
- `--status-mode {all,errors}`
- `--default-output`
- `--save-session`, `--no-save-session`
- `--refresh-session`, `--no-refresh-session`

Примеры:

```bash
anytask-scraper settings set --session-file ./.anytask_session.json --status-mode all
anytask-scraper settings set --no-save-session
```

#### `settings clear`

Сбрасывает выбранные ключи или все ключи сразу.

```bash
anytask-scraper settings clear [keys...]
```

Допустимые `keys`:

- `credentials_file`
- `session_file`
- `status_mode`
- `default_output`
- `save_session`
- `refresh_session`

Примеры:

```bash
anytask-scraper settings clear session_file status_mode
anytask-scraper settings clear
```

## Использование как Python-библиотеки

### Что импортировать

```python
from anytask_scraper import (
    AnytaskClient,
    LoginError,
    parse_course_page,
    parse_submission_page,
    extract_csrf_from_queue_page,
    extract_issue_id_from_breadcrumb,
    save_course_json,
    save_course_markdown,
    save_queue_json,
    save_queue_markdown,
    download_submission_files,
)
```

### Пример 1. Курс в JSON/Markdown

```python
from anytask_scraper import AnytaskClient, parse_course_page, save_course_json, save_course_markdown

course_id = course_id

with AnytaskClient("your_login", "your_password") as client:
    html = client.fetch_course_page(course_id)
    course = parse_course_page(html, course_id)
    save_course_json(course, "./output")
    save_course_markdown(course, "./output")
```

### Пример 2. Работа через сохраненную сессию

```python
from anytask_scraper import AnytaskClient, parse_course_page

course_id = course_id

with AnytaskClient() as client:
    if not client.load_session("./.anytask_session.json"):
        raise RuntimeError("Файл сессии не найден")

    html = client.fetch_course_page(course_id)
    course = parse_course_page(html, course_id)
    print(course.title, len(course.tasks))
```

### Пример 3. Очередь + deep + скачивание файлов

```python
from anytask_scraper import (
    AnytaskClient,
    extract_csrf_from_queue_page,
    extract_issue_id_from_breadcrumb,
    parse_submission_page,
    download_submission_files,
)

course_id = course_id

with AnytaskClient("your_login", "your_password") as client:
    queue_html = client.fetch_queue_page(course_id)
    csrf = extract_csrf_from_queue_page(queue_html)
    if not csrf:
        raise RuntimeError("Не удалось извлечь CSRF")

    rows = client.fetch_all_queue_entries(course_id, csrf)

    for row in rows:
        issue_url = str(row.get("issue_url", ""))
        has_access = bool(row.get("has_issue_access", False))
        if not issue_url or not has_access:
            continue

        sub_html = client.fetch_submission_page(issue_url)
        issue_id = extract_issue_id_from_breadcrumb(sub_html)
        if issue_id == 0:
            continue

        submission = parse_submission_page(sub_html, issue_id)
        downloaded = download_submission_files(client, submission, "./downloads")
        print(issue_id, len(downloaded))
```

- Клиент и ошибки: `AnytaskClient`, `LoginError`
- Парсеры: `parse_course_page`, `parse_submission_page`, `parse_queue_filters`, `parse_task_edit_page`, `extract_csrf_from_queue_page`, `extract_issue_id_from_breadcrumb`, `format_student_folder`, `strip_html`
- Сохранение/выгрузка: `save_course_json`, `save_course_markdown`, `save_queue_json`, `save_queue_markdown`, `download_submission_files`
- Отображение в терминале: `display_course`, `display_queue`, `display_submission`
- Модели: `Course`, `Task`, `ReviewQueue`, `QueueEntry`, `Submission`, `Comment`, `FileAttachment`, `QueueFilters`

## Ограничения и безопасность

- Доступны только те курсы, к которым есть доступ аккаунта.
- Доступ к очереди и submission зависит от прав пользователя в конкретном курсе.
- Если сессия истекла, клиент попытается перелогиниться при наличии логина/пароля.
- Не забывайте про безопаность и приятного использования :)
