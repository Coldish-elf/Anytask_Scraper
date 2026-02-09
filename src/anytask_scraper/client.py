"""HTTP client for anytask.org."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://anytask.org"
LOGIN_URL = f"{BASE_URL}/accounts/login/"

_CSRF_RE = re.compile(r"name=['\"]csrfmiddlewaretoken['\"] value=['\"]([^'\"]+)['\"]")
_COLAB_FILE_ID_RE = re.compile(r"(?:/drive/|/notebook/d/)([a-zA-Z0-9_-]+)")


@dataclass
class DownloadResult:
    """Result of a file download attempt."""

    success: bool
    path: str
    reason: str = ""


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
                "No credentials available. Provide username/password or credentials file"
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
                raise LoginError(
                    "Saved session expired and no credentials were provided"
                )
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
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

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
                course_id,
                csrf_token,
                start=start,
                length=page_size,
                filter_query=filter_query,
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

    def _download_to_file(self, url: str, dest: Path) -> httpx.Response:
        """Stream download to file, handling login redirects."""
        with self._client.stream("GET", url) as resp:
            if self._is_login_response(resp):
                self._authenticated = False
                if not self._has_credentials():
                    raise LoginError(
                        "Saved session expired and no credentials were provided"
                    )
                self.login()
                with self._client.stream("GET", url) as retried:
                    retried.raise_for_status()
                    with dest.open("wb") as f:
                        for chunk in retried.iter_bytes():
                            f.write(chunk)
                    return retried
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
            return resp

    @staticmethod
    def _validate_downloaded_file(
        path: Path, content_type: str, expected_suffix: str
    ) -> str:
        """Validate downloaded file. Returns empty string if OK, or reason if invalid."""
        if not path.exists() or path.stat().st_size == 0:
            return "empty_file"

        with path.open("rb") as f:
            head = f.read(1024)

        head_lower = head.lower().strip()
        is_html = (
            head_lower.startswith(b"<!doctype html")
            or head_lower.startswith(b"<html")
            or b"<head>" in head_lower[:500]
        )

        if is_html:
            if b"id_username" in head or b"/accounts/login/" in head:
                return "login_redirect"
            if b"Jupyter Server" in head or b"Jupyter Notebook" in head:
                return "jupyter_server_html"
            return "html_instead_of_file"

        if expected_suffix.lower() == ".ipynb" and not head_lower.lstrip().startswith(
            b"{"
        ):
            return "invalid_notebook_format"

        if (
            content_type
            and "text/html" in content_type.lower()
            and expected_suffix.lower() not in {".html", ".htm"}
        ):
            return "content_type_html_mismatch"

        return ""

    def download_file(self, url: str, output_path: str) -> DownloadResult:
        """Download file to local path with content validation."""
        if not self._authenticated and self._has_credentials():
            self.login()

        full_url = url if url.startswith("http") else f"{BASE_URL}{url}"
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output.with_suffix(output.suffix + ".tmp")

        try:
            resp = self._download_to_file(full_url, tmp_path)
        except LoginError:
            tmp_path.unlink(missing_ok=True)
            raise
        except Exception as e:
            tmp_path.unlink(missing_ok=True)
            return DownloadResult(
                success=False, path=output_path, reason=f"download_error: {e}"
            )

        content_type = resp.headers.get("content-type", "")
        problem = self._validate_downloaded_file(tmp_path, content_type, output.suffix)
        if problem:
            tmp_path.unlink(missing_ok=True)
            return DownloadResult(success=False, path=output_path, reason=problem)

        tmp_path.rename(output)
        return DownloadResult(success=True, path=output_path, reason="ok")

    def download_colab_notebook(
        self, colab_url: str, output_path: str
    ) -> DownloadResult:
        """Try downloading a Colab notebook as .ipynb."""
        m = _COLAB_FILE_ID_RE.search(colab_url) or re.search(
            r"drive/([a-zA-Z0-9_-]+)", colab_url
        )
        if m is None:
            return DownloadResult(
                success=False, path=output_path, reason="no_file_id_in_url"
            )

        file_id = m.group(1)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        download_urls = [
            f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
            f"https://docs.google.com/uc?export=download&id={file_id}",
            f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t",
        ]

        last_reason = "all_strategies_failed"
        for download_url in download_urls:
            try:
                with httpx.Client(follow_redirects=True, timeout=30.0) as gc:
                    resp = gc.get(download_url)
                    if resp.status_code != 200:
                        last_reason = f"http_{resp.status_code}"
                        continue

                    content = resp.content
                    content_lower = content[:1024].lower().strip()
                    if content_lower.startswith(
                        b"<!doctype html"
                    ) or content_lower.startswith(b"<html"):
                        confirm_match = re.search(rb"confirm=([a-zA-Z0-9_-]+)", content)
                        if confirm_match:
                            confirm_url = (
                                f"https://drive.usercontent.google.com/download?id={file_id}"
                                f"&export=download&confirm={confirm_match.group(1).decode()}"
                            )
                            resp2 = gc.get(confirm_url)
                            if (
                                resp2.status_code == 200
                                and resp2.content.strip().startswith(b"{")
                            ):
                                output.write_bytes(resp2.content)
                                return DownloadResult(
                                    success=True,
                                    path=output_path,
                                    reason="ok_after_confirm",
                                )
                        last_reason = "google_drive_html_page"
                        continue

                    if not content.strip().startswith(b"{"):
                        last_reason = "not_json_content"
                        continue

                    output.write_bytes(content)
                    return DownloadResult(success=True, path=output_path, reason="ok")
            except Exception as e:
                last_reason = f"error: {e}"
                continue

        return DownloadResult(success=False, path=output_path, reason=last_reason)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AnytaskClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
