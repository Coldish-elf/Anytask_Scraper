# API Библиотеки

`anytask-scraper` можно использовать как Python-библиотеку для написания своих скриптов автоматизации.

## Клиент AnytaskClient

Основной класс для взаимодействия с anytask.org.

```python
from anytask_scraper import AnytaskClient

# Использование с контекстным менеджером
with AnytaskClient(username="user", password="password") as client:
    client.login()
    # Ваши действия...

# Или создание экземпляра вручную
client = AnytaskClient()
client.login("user", "password")
```

### Основные методы

#### `login()`

Авторизуется на сайте с переданными `username` и `password`.

#### `load_session(path)`

Загружает cookies из файла. Возвращает `True`, если загрузка успешна.

```python
client.load_session(".anytask_session.json")
```

#### `fetch_course_page(course_id)`

Возвращает HTML-код страницы курса.

```python
html = client.fetch_course_page(12345)
```

#### `fetch_queue_page(course_id)`

Возвращает HTML-код страницы очереди проверки.

#### `download_file(url, output_path)`

Скачивает файл по ссылке. Поддерживает как прямые ссылки Anytask, так и Google Colab (сохраняет как `.ipynb`).

## Парсинг данных

Модуль `parser` содержит функции для извлечения данных из HTML.

```python
from anytask_scraper import parse_course_page

html = client.fetch_course_page(12345)
course = parse_course_page(html, 12345)

print(f"Курс: {course.title}")
for task in course.tasks:
    print(f"- {task.title}: {task.score} / {task.max_score}")
```

### Ключевые функции

- `parse_course_page(html, course_id) -> Course`
- `parse_gradebook_page(html, course_id) -> Gradebook`
- `parse_task_edit_page(html) -> str`
- `extract_issue_id_from_breadcrumb(html) -> int`

## Экспорт и сохранение

Функции для сохранения данных в файлы (JSON, Markdown, CSV).

```python
from anytask_scraper import (
    save_course_json, save_course_markdown, save_course_csv,
    save_queue_json, save_queue_markdown, save_queue_csv,
    save_gradebook_json, save_gradebook_markdown, save_gradebook_csv,
    download_submission_files
)

# Пример использования
save_course_json(course, "./output")
download_submission_files(client, submission, "./downloads")
```

## Модели данных

Все данные возвращаются в виде `dataclass`-объектов (модуль `models`).

### `Course`

- `id`: ID курса.
- `title`: Название.
- `tasks`: Список задач (`Task`).

### `Task`

- `id`: ID задачи.
- `title`: Название.
- `score`: Текущий балл (для студента).
- `max_score`: Максимальный балл.
- `deadline`: Срок сдачи.

### `Submission`

Описывает одно решение (issue) студента:

- `student_name`: Имя студента.
- `comments`: Список комментариев и файлов.

## Примеры

### Скачивание всех решений курса

```python
from anytask_scraper import AnytaskClient, parse_course_page

def main():
    with AnytaskClient(username="...", password="...") as client:
        client.login()

        # Получаем данные о курсе
        html = client.fetch_course_page(12345)
        course = parse_course_page(html, 12345)

        print(f"Курс: {course.title}, Задач: {len(course.tasks)}")
```
