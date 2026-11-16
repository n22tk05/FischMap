"""Script gửi HTTP request đến một trang web và chỉ lấy phần <body> HTML."""

from __future__ import annotations

import gzip
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# === CẤU HÌNH REQUEST ===
URL = "https://fischipedia.org/wiki/Fishing_Rods"  # Thay bằng URL cần lấy, hoặc để "" để nhập khi chạy
METHOD = "GET"
HEADERS: dict[str, str] = {}
DATA: str | None = None
TIMEOUT = 15.0
OUTPUT_FILE: str | None = None  # Ví dụ: "body.html" nếu muốn lưu phần body ra file
INCLUDE_BODY_TAG = True  # True: giữ cả thẻ <body>...</body>, False: chỉ lấy nội dung bên trong
MAX_CHARS = 0  # 0: lấy toàn bộ body; đặt > 0 nếu muốn giới hạn ký tự in ra màn hình

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_BODY_PATTERN = re.compile(r"<body\b[^>]*>(.*?)</body>", flags=re.DOTALL | re.IGNORECASE)


@dataclass
class HttpResponseData:
    """Chứa kết quả trả về từ một HTTP request."""

    url: str
    status: int
    headers: dict[str, str]
    body_bytes: bytes

    @property
    def content_type(self) -> str:
        """Lấy giá trị Content-Type (không phân biệt hoa thường)."""
        for key, value in self.headers.items():
            if key.lower() == "content-type":
                return value
        return ""

    def decode_text(self) -> str:
        """Giải mã body bytes sang chuỗi theo charset trong header (mặc định utf-8)."""
        charset = "utf-8"
        for part in self.content_type.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                charset = part.split("=", 1)[1].strip().strip("\"'")
                break
        return self.body_bytes.decode(charset, errors="replace")


def normalize_url(raw_url: str) -> str:
    """Đảm bảo URL có scheme hợp lệ (mặc định https:// nếu thiếu)."""
    url = raw_url.strip()
    if not url:
        raise ValueError("URL không được để trống.")
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme:
        return f"https://{url}"
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Scheme không được hỗ trợ: {parsed.scheme}")
    return url


def _decompress_if_needed(raw_bytes: bytes, headers: dict[str, str]) -> bytes:
    """Giải nén nội dung gzip nếu server trả về Content-Encoding: gzip."""
    if not raw_bytes:
        return raw_bytes
    encoding = next(
        (v.lower() for k, v in headers.items() if k.lower() == "content-encoding"),
        "",
    )
    if "gzip" in encoding:
        try:
            return gzip.decompress(raw_bytes)
        except OSError:
            return raw_bytes
    return raw_bytes


def fetch_url(
    url: str,
    *,
    method: str = "GET",
    timeout: float = 15.0,
    extra_headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> HttpResponseData:
    """Gửi HTTP request tới URL và trả về status, headers, body."""
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Encoding": "gzip",
    }
    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_headers = dict(resp.headers.items())
            raw_bytes = _decompress_if_needed(resp.read(), resp_headers)
            return HttpResponseData(
                url=resp.geturl(),
                status=resp.status,
                headers=resp_headers,
                body_bytes=raw_bytes,
            )
    except urllib.error.HTTPError as err:
        resp_headers = dict(err.headers.items()) if err.headers else {}
        raw_bytes = _decompress_if_needed(err.read(), resp_headers)
        return HttpResponseData(
            url=err.geturl(),
            status=err.code,
            headers=resp_headers,
            body_bytes=raw_bytes,
        )


def extract_html_body(html: str, *, include_tag: bool = True) -> str:
    """Trích xuất phần <body> từ chuỗi HTML (trả về nguyên bản nếu không có thẻ <body>)."""
    match = _BODY_PATTERN.search(html)
    if not match:
        return html
    return match.group(0) if include_tag else match.group(1).strip()


def main() -> int:
    """Điểm vào chính khi chạy trực tiếp file."""
    raw_url = URL.strip() or input("Nhập URL trang web cần lấy: ")
    try:
        target_url = normalize_url(raw_url)
    except ValueError as err:
        print(f"Lỗi URL: {err}", file=sys.stderr)
        return 1

    payload = DATA.encode("utf-8") if DATA is not None else None

    try:
        response = fetch_url(
            target_url,
            method=METHOD,
            timeout=TIMEOUT,
            extra_headers=HEADERS,
            data=payload,
        )
    except urllib.error.URLError as err:
        print(f"Không thể kết nối tới {target_url}: {err.reason}", file=sys.stderr)
        return 1

    body_html = extract_html_body(response.decode_text(), include_tag=INCLUDE_BODY_TAG)

    if OUTPUT_FILE:
        Path(OUTPUT_FILE).write_text(body_html, encoding="utf-8")

    if MAX_CHARS > 0 and len(body_html) > MAX_CHARS:
        print(body_html[:MAX_CHARS])
    else:
        print(body_html)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
