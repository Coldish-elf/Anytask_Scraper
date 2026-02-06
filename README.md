# anytask-scrapper

CLI-инструмент на Python для сбора данных с [anytask.org](https://anytask.org):

- задач курса,
- дедлайнов,
- статусов и оценок,
- очереди на проверку,
- деталей сабмишнов (issue) и файлов из комментариев.

## Основные возможности

- Авторизация в anytask через сессию и CSRF.
- Парсинг страниц курсов в двух режимах:
  - student view (оценки, статус, дедлайн, описание, ссылка на отправку),
  - teacher view (секции/группы, max score, дедлайн, ссылка на редактирование задачи).
- Дополнительная загрузка описаний задач для teacher view (`--fetch-descriptions`).
- Работа с очередью проверки (`queue`):
  - выгрузка всех записей,
  - локальные фильтры по задаче/проверяющему/статусу,
  - deep-режим с загрузкой страниц сабмишнов,
  - скачивание файлов из комментариев (`--download-files`).
- Экспорт в `json` и `markdown`.
- Вывод цветных таблиц в терминал (`rich`).
- Использование как библиотеки Python (импорт функций и моделей из пакета).

## Установка

Требуется Python 3.10+.

```bash
git clone <repo-url>
cd anytask-scrapper
pip install -e .
```

После установки:

```bash
anytask-scrapper --help
```

## Быстрый старт

### 1) Выгрузить задачи курса

```bash
anytask-scrapper -u 'USERNAME' -p 'PASSWORD' course -c COURSE_ID
```

Результат: `./course_<COURSE_ID>.json`.

### 2) Показать курс таблицей без сохранения

```bash
anytask-scrapper -u 'USERNAME' -p 'PASSWORD' course -c COURSE_ID -f table
```

### 3) Выгрузить очередь курса

```bash
anytask-scrapper -u 'USERNAME' -p 'PASSWORD' queue -c COURSE_ID
```

Результат: `./queue_<COURSE_ID>.json`.

### 4) Очередь + детали сабмишнов + скачивание файлов

```bash
anytask-scrapper -u 'USERNAME' -p 'PASSWORD' queue -c COURSE_ID --deep --download-files -o ./output
```

## CLI

Общий формат:

```bash
anytask-scrapper -u 'USERNAME' -p 'PASSWORD' {course|queue} [options]
```

### Подкоманда `course`

```bash
anytask-scrapper -u 'USERNAME' -p 'PASSWORD' course -c COURSE_ID [COURSE_ID ...]
```

Опции:

- `-c, --course` — один или несколько ID курсов.
- `-o, --output` — папка для файлов (по умолчанию `.`).
- `-f, --format` — `json | markdown | table` (по умолчанию `json`).
- `--show` — дополнительно показать таблицу в терминале.
- `--fetch-descriptions` — догрузить описания задач из `/task/edit/{id}` (актуально для teacher view).

### Подкоманда `queue`

```bash
anytask-scrapper -u 'USERNAME' -p 'PASSWORD' queue -c COURSE_ID
```

Опции:

- `-c, --course` — ID курса.
- `-o, --output` — папка для файлов (по умолчанию `.`).
- `-f, --format` — `json | markdown | table`.
- `--show` — дополнительно показать таблицу в терминале.
- `--deep` — загрузить полные страницы сабмишнов для доступных issue.
- `--download-files` — скачать вложения и colab-ноутбуки (автоматически включает `--deep`).
- `--filter-task` — фильтр по названию задачи (substring).
- `--filter-reviewer` — фильтр по имени проверяющего (substring).
- `--filter-status` — фильтр по статусу (substring).

## Форматы вывода

- `json` — структурированные данные для автоматической обработки.
- `markdown` — человекочитаемый отчёт.
- `table` — вывод в терминал без записи файла.

## Примеры

### Несколько курсов за один запуск

```bash
anytask-scrapper -u 'USERNAME' -p 'PASSWORD' course -c COURSE_ID_A COURSE_ID_B -o ./data
```

### Очередь только по конкретному статусу

```bash
anytask-scrapper -u 'USERNAME' -p 'PASSWORD' queue -c COURSE_ID --filter-status "На проверке" --show
```

### Курс в markdown + показ в терминале

```bash
anytask-scrapper -u 'USERNAME' -p 'PASSWORD' course -c COURSE_ID -f markdown --show
```

## Использование как Python-библиотеки

```python
from anytask_scrapper import AnytaskClient, parse_course_page, save_course_json

with AnytaskClient("username", "password") as client:
    client.login()
    html = client.fetch_course_page(1234)
    course = parse_course_page(html, 1234)
    save_course_json(course, "./output")
```

Полезные импорты:

- `AnytaskClient`, `LoginError`
- `parse_course_page`, `parse_submission_page`, `parse_queue_filters`
- `save_course_json`, `save_course_markdown`, `save_queue_json`, `save_queue_markdown`
- `download_submission_files`
- модели: `Course`, `Task`, `ReviewQueue`, `QueueEntry`, `Submission`, `Comment`

## Ограничения и безопасность

- Доступ к очереди/issue зависит от прав пользователя в курсе.
- Логин/пароль передаются через аргументы CLI, учитывайте shell history и безопасность окружения.
