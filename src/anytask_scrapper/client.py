"""HTTP client for anytask.org."""

from __future__ import annotations

import re

import httpx

BASE_URL = "https://anytask.org"
LOGIN_URL = f"{BASE_URL}/accounts/login/"

_CSRF_RE = re.compile(r"name=['\"]csrfmiddlewaretoken['\"] value=['\"]([^'\"]+)['\"]")


class LoginError(Exception):
    """Auth failed."""


class AnytaskClient:
    """Authenticated anytask client."""

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self._client = httpx.Client(follow_redirects=True, timeout=30.0)
        self._authenticated = False

    def login(self) -> None:
        """Log in with Django form auth."""
        resp = self._client.get(LOGIN_URL)
        resp.raise_for_status()

        csrf_match = _CSRF_RE.search(resp.text)
        if csrf_match is None:
            raise LoginError("Could not find CSRF token on login page")

        csrf_token = csrf_match.group(1)

        resp = self._client.post(
            LOGIN_URL,
            data={
                "csrfmiddlewaretoken": csrf_token,
                "username": self.username,
                "password": self.password,
                "next": "",
            },
            headers={"Referer": LOGIN_URL},
        )
        resp.raise_for_status()

        if "/accounts/login/" in str(resp.url) and "id_username" in resp.text:
            raise LoginError("Login failed — check username and password")

        self._authenticated = True

    def fetch_course_page(self, course_id: int) -> str:
        """Return course page HTML."""
        if not self._authenticated:
            self.login()
        resp = self._client.get(f"{BASE_URL}/course/{course_id}")
        resp.raise_for_status()
        return resp.text

    def fetch_task_description(self, task_id: int) -> str:
        """Return task description from /task/edit/{id}."""
        if not self._authenticated:
            self.login()

        from anytask_scrapper.parser import parse_task_edit_page

        resp = self._client.get(f"{BASE_URL}/task/edit/{task_id}")
        resp.raise_for_status()
        return parse_task_edit_page(resp.text)

    def fetch_queue_page(self, course_id: int) -> str:
        """Return queue page HTML."""
        if not self._authenticated:
            self.login()
        resp = self._client.get(f"{BASE_URL}/course/{course_id}/queue?update_time=")
        resp.raise_for_status()
        return resp.text

    def fetch_queue_ajax(
        self,
        course_id: int,
        csrf_token: str,
        start: int = 0,
        length: int = 50,
        filter_query: str = "",
    ) -> dict[str, object]:
        """Return one queue page from AJAX API."""
        if not self._authenticated:
            self.login()
        data = {
            "csrfmiddlewaretoken": csrf_token,
            "lang": "ru",
            "timezone": "Europe/Moscow",
            "course_id": str(course_id),
            "draw": "1",
            "start": str(start),
            "length": str(length),
            "filter": filter_query,
            "order": '[{"column":3,"dir":"desc"}]',
        }
        resp = self._client.post(
            f"{BASE_URL}/course/ajax_get_queue",
            data=data,
            headers={"Referer": f"{BASE_URL}/course/{course_id}/queue"},
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def fetch_all_queue_entries(
        self,
        course_id: int,
        csrf_token: str,
        filter_query: str = "",
    ) -> list[dict[str, object]]:
        """Return all queue rows via pagination."""
        all_entries: list[dict[str, object]] = []
        start = 0
        page_size = 100
        while True:
            result = self.fetch_queue_ajax(
                course_id, csrf_token, start=start, length=page_size, filter_query=filter_query
            )
            data = result.get("data", [])
            if not isinstance(data, list):
                break
            all_entries.extend(data)
            total = int(str(result.get("recordsTotal", 0)))
            start += page_size
            if start >= total or len(data) < page_size:
                break
        return all_entries

    def fetch_submission_page(self, issue_url: str) -> str:
        """Return issue page HTML."""
        if not self._authenticated:
            self.login()
        url = issue_url if issue_url.startswith("http") else f"{BASE_URL}{issue_url}"
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.text

    def download_file(self, url: str, output_path: str) -> None:
        """Download file to local path."""
        if not self._authenticated:
            self.login()
        full_url = url if url.startswith("http") else f"{BASE_URL}{url}"
        from pathlib import Path

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with self._client.stream("GET", full_url) as resp:
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)

    def download_colab_notebook(self, colab_url: str, output_path: str) -> bool:
        """Try downloading a Colab notebook as .ipynb."""
        import re
        from pathlib import Path

        m = re.search(r"drive/([a-zA-Z0-9_-]+)", colab_url)
        if m is None:
            return False
        file_id = m.group(1)
        export_url = f"https://docs.google.com/uc?export=download&id={file_id}"
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with httpx.Client(follow_redirects=True, timeout=30.0) as gc:
                resp = gc.get(export_url)
                if resp.status_code != 200:
                    return False
                content = resp.content
                if not content.strip().startswith(b"{"):
                    return False
                with open(output_path, "wb") as f:
                    f.write(content)
                return True
        except Exception:
            return False

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AnytaskClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
