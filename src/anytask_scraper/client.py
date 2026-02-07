"""HTTP client for anytask.org."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://anytask.org"
LOGIN_URL = f"{BASE_URL}/accounts/login/"

_CSRF_RE = re.compile(r"name=['\"]csrfmiddlewaretoken['\"] value=['\"]([^'\"]+)['\"]")


class LoginError(Exception):
    """Auth failed."""


class AnytaskClient:
    """Authenticated anytask client."""

    def __init__(self, username: str = "", password: str = "") -> None:
        self.username = username
        self.password = password
        self._client = httpx.Client(follow_redirects=True, timeout=30.0)
        self._authenticated = False

    def _has_credentials(self) -> bool:
        return bool(self.username and self.password)

    @staticmethod
    def _is_login_response(resp: httpx.Response) -> bool:
        return "/accounts/login/" in str(resp.url) and "id_username" in resp.text

    def login(self) -> None:
        """Log in with Django form auth."""
        if not self._has_credentials():
            raise LoginError(
                "No credentials available. "
                "Provide username/password or credentials file"
            )

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

        if self._is_login_response(resp):
            raise LoginError("Login failed: check username and password")

        self._authenticated = True

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if not self._authenticated and self._has_credentials():
            self.login()

        resp = self._client.request(method, url, **kwargs)

        if self._is_login_response(resp):
            self._authenticated = False
            if not self._has_credentials():
                raise LoginError("Saved session expired and no credentials were provided")
            self.login()
            resp = self._client.request(method, url, **kwargs)

        resp.raise_for_status()
        return resp

    def load_session(self, session_path: Path | str) -> bool:
        """Load cookie session from file."""
        path = Path(session_path)
        if not path.exists():
            return False

        raw = json.loads(path.read_text(encoding="utf-8"))
        cookies = raw.get("cookies", [])
        if not isinstance(cookies, list):
            return False

        self._client.cookies.clear()
        for item in cookies:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            value = str(item.get("value", ""))
            domain = str(item.get("domain", ""))
            cookie_path = str(item.get("path", "/"))
            if not name:
                continue
            if domain:
                self._client.cookies.set(name, value, domain=domain, path=cookie_path)
            else:
                self._client.cookies.set(name, value, path=cookie_path)

        saved_username = str(raw.get("username", ""))
        if not self.username and saved_username:
            self.username = saved_username

        self._authenticated = True
        return True

    def save_session(self, session_path: Path | str) -> None:
        """Save cookie session to file."""
        path = Path(session_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        cookies: list[dict[str, str]] = []
        for cookie in self._client.cookies.jar:
            cookies.append(
                {
                    "name": cookie.name or "",
                    "value": cookie.value or "",
                    "domain": cookie.domain or "",
                    "path": cookie.path or "/",
                }
            )

        payload = {
            "username": self.username,
            "cookies": cookies,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def fetch_course_page(self, course_id: int) -> str:
        """Return course page HTML."""
        resp = self._request("GET", f"{BASE_URL}/course/{course_id}")
        return resp.text

    def fetch_task_description(self, task_id: int) -> str:
        """Return task description from /task/edit/{id}."""
        from anytask_scraper.parser import parse_task_edit_page

        resp = self._request("GET", f"{BASE_URL}/task/edit/{task_id}")
        return parse_task_edit_page(resp.text)

    def fetch_queue_page(self, course_id: int) -> str:
        """Return queue page HTML."""
        resp = self._request("GET", f"{BASE_URL}/course/{course_id}/queue?update_time=")
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
        resp = self._request(
            "POST",
            f"{BASE_URL}/course/ajax_get_queue",
            data=data,
            headers={"Referer": f"{BASE_URL}/course/{course_id}/queue"},
        )
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
        url = issue_url if issue_url.startswith("http") else f"{BASE_URL}{issue_url}"
        resp = self._request("GET", url)
        return resp.text

    def download_file(self, url: str, output_path: str) -> None:
        """Download file to local path."""
        if not self._authenticated and self._has_credentials():
            self.login()

        full_url = url if url.startswith("http") else f"{BASE_URL}{url}"
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with self._client.stream("GET", full_url) as resp:
            if self._is_login_response(resp):
                self._authenticated = False
                if not self._has_credentials():
                    raise LoginError("Saved session expired and no credentials were provided")
                self.login()
                with self._client.stream("GET", full_url) as retried:
                    retried.raise_for_status()
                    with output.open("wb") as f:
                        for chunk in retried.iter_bytes():
                            f.write(chunk)
                return

            resp.raise_for_status()
            with output.open("wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)

    def download_colab_notebook(self, colab_url: str, output_path: str) -> bool:
        """Try downloading a Colab notebook as .ipynb."""
        m = re.search(r"drive/([a-zA-Z0-9_-]+)", colab_url)
        if m is None:
            return False

        file_id = m.group(1)
        export_url = f"https://docs.google.com/uc?export=download&id={file_id}"
        try:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            with httpx.Client(follow_redirects=True, timeout=30.0) as gc:
                resp = gc.get(export_url)
                if resp.status_code != 200:
                    return False
                content = resp.content
                if not content.strip().startswith(b"{"):
                    return False
                output.write_bytes(content)
                return True
        except Exception:
            return False

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AnytaskClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
