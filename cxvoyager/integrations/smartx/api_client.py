# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of CXVoyager.
#
# CXVoyager is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CXVoyager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CXVoyager.  If not, see <https://www.gnu.org/licenses/>.

"""API 客户端占位与模拟实现。"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse

import requests

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
except ImportError as exc:  # pragma: no cover - environment issue, provide actionable hint
    raise ImportError(
        "缺少第三方依赖 'tenacity'，请先运行 'pip install tenacity' 或 'pip install -r requirements.txt'"
    ) from exc

logger = logging.getLogger(__name__)


_SENSITIVE_HEADER_KEYS = {"authorization", "cookie", "x-smartx-token", "token"}


def _mask_value(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def _sanitize_headers(headers: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not headers:
        return {}
    sanitized: Dict[str, Any] = {}
    for key, val in headers.items():
        if isinstance(val, str) and key.lower() in _SENSITIVE_HEADER_KEYS:
            sanitized[key] = _mask_value(val)
        else:
            sanitized[key] = val
    return sanitized


def _short_repr(value: Any, limit: int = 200) -> str:
    if value is None:
        return "None"
    try:
        rendered = str(value)
    except Exception:  # noqa: BLE001 - fallback for objects without str representation
        rendered = repr(value)
    if len(rendered) > limit:
        return f"{rendered[:limit]}...<trimmed>"
    return rendered

class APIError(RuntimeError):
    pass


class APIClient:
    """支持Mock与真实HTTP调用的API客户端。"""

    def __init__(
        self,
        base_url: str,
        mock: bool = True,
        timeout: int = 10,
        *,
        verify: Union[bool, str] = True,
    ):
        self.base_url = base_url.rstrip('/')
        self.mock = mock
        self.timeout = timeout
        self.session = requests.Session()
        self.verify = verify
        self._host_header: Optional[str] = None

        try:
            parsed = urlparse(self.base_url)
            host = parsed.hostname
            if host:
                if parsed.port and parsed.port not in (80, 443):
                    host = f"{host}:{parsed.port}"
                self._host_header = host
        except Exception:  # noqa: BLE001 - best-effort parsing
            self._host_header = None

        if self._host_header:
            self.session.headers.setdefault("host", self._host_header)

        # requests 会继承 session.verify，该参数支持 bool 或 CA 路径
        self.session.verify = verify
        if verify is False and not self.mock:
            logger.warning("APIClient 已禁用 SSL 证书校验")

    def _full_url(self, path: str) -> str:
        if path.startswith('http://') or path.startswith('https://'):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _prepare_headers(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        prepared: Dict[str, str] = dict(headers) if headers else {}
        if self._host_header is not None:
            has_host = any(key.lower() == "host" for key in prepared.keys())
            if not has_host:
                prepared["host"] = self._host_header
        return prepared

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5),
           retry=retry_if_exception_type((requests.RequestException, APIError)))
    def post(
        self,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if payload is None:
            payload = {}
        headers = self._prepare_headers(headers)
        if self.mock:
            logger.debug(
                "MOCK POST %s payload=%s params=%s files=%s", path, payload, params, bool(files)
            )
            return {
                "ok": True,
                "path": path,
                "echo": payload,
                "params": params or {},
                "files": bool(files),
                "headers": headers,
            }
        url = self._full_url(path)
        try:
            request_kwargs: Dict[str, Any] = {
                "timeout": self.timeout,
                "headers": headers,
                "params": params,
            }
            if files is not None:
                request_kwargs["files"] = files
                request_kwargs["data"] = data or {}
            elif data is not None:
                request_kwargs["data"] = data
            else:
                request_kwargs["json"] = payload
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "HTTP POST %s headers=%s params=%s payload=%s data=%s files=%s",
                    url,
                    _sanitize_headers(request_kwargs.get("headers")),
                    params,
                    _short_repr(payload),
                    _short_repr(data),
                    bool(files),
                )
            r = self.session.post(url, **request_kwargs)
            if logger.isEnabledFor(logging.DEBUG):
                body_preview = r.text[:300] if isinstance(r.text, str) else str(r.text)
                logger.debug(
                    "HTTP RESPONSE POST %s status=%s body=%s",
                    url,
                    r.status_code,
                    body_preview,
                )
            if r.status_code >= 400:
                raise APIError(f"POST {url} status={r.status_code} body={r.text[:200]}")
            return r.json()
        except requests.RequestException as e:
            logger.error("POST失败: %s", e)
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5),
           retry=retry_if_exception_type((requests.RequestException, APIError)))
    def get(self, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        headers = self._prepare_headers(headers)
        if self.mock:
            logger.debug("MOCK GET %s params=%s", path, params)
            return {"ok": True, "path": path, "params": params, "headers": headers}
        url = self._full_url(path)
        try:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "HTTP GET %s headers=%s params=%s",
                    url,
                    _sanitize_headers(headers),
                    params,
                )
            r = self.session.get(url, params=params, timeout=self.timeout, headers=headers)
            if logger.isEnabledFor(logging.DEBUG):
                body_preview = r.text[:200] if isinstance(r.text, str) else str(r.text)
                logger.debug(
                    "HTTP RESPONSE GET %s status=%s body=%s",
                    url,
                    r.status_code,
                    body_preview,
                )
            if r.status_code >= 400:
                raise APIError(f"GET {url} status={r.status_code} body={r.text[:200]}")
            return r.json()
        except requests.RequestException as e:
            logger.error("GET失败: %s", e)
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5),
           retry=retry_if_exception_type((requests.RequestException, APIError)))
    def put(self, path: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        headers = self._prepare_headers(headers)
        if self.mock:
            logger.debug("MOCK PUT %s payload=%s", path, payload)
            return {"ok": True, "path": path, "echo": payload, "headers": headers}
        url = self._full_url(path)
        try:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "HTTP PUT %s headers=%s payload=%s",
                    url,
                    _sanitize_headers(headers),
                    _short_repr(payload),
                )
            r = self.session.put(url, json=payload, timeout=self.timeout, headers=headers)
            if logger.isEnabledFor(logging.DEBUG):
                body_preview = r.text[:200] if isinstance(r.text, str) else str(r.text)
                logger.debug(
                    "HTTP RESPONSE PUT %s status=%s body=%s",
                    url,
                    r.status_code,
                    body_preview,
                )
            if r.status_code >= 400:
                raise APIError(f"PUT {url} status={r.status_code} body={r.text[:200]}")
            return r.json() if r.content else {}
        except requests.RequestException as e:
            logger.error("PUT失败: %s", e)
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5),
           retry=retry_if_exception_type((requests.RequestException, APIError)))
    def delete(
        self,
        path: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = self._prepare_headers(headers)
        if self.mock:
            logger.debug("MOCK DELETE %s params=%s", path, params)
            return {"ok": True, "path": path, "params": params or {}, "headers": headers}
        url = self._full_url(path)
        try:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "HTTP DELETE %s headers=%s params=%s",
                    url,
                    _sanitize_headers(headers),
                    params,
                )
            r = self.session.delete(url, timeout=self.timeout, headers=headers, params=params)
            if logger.isEnabledFor(logging.DEBUG):
                body_preview = r.text[:200] if isinstance(r.text, str) else str(r.text)
                logger.debug(
                    "HTTP RESPONSE DELETE %s status=%s body=%s",
                    url,
                    r.status_code,
                    body_preview,
                )
            if r.status_code >= 400:
                raise APIError(f"DELETE {url} status={r.status_code} body={r.text[:200]}")
            return r.json() if r.content else {}
        except requests.RequestException as e:
            logger.error("DELETE失败: %s", e)
            raise

