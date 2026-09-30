from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Xóa dữ liệu context còn sót để request này không nhận nhầm ID của request trước.
        clear_contextvars()

        # Thử lấy ID do client gửi trong header x-request-id.
        supplied_id = request.headers.get("x-request-id", "")

        # Chỉ nhận ID theo định dạng req- cùng 8 ký tự hex; nếu thiếu hoặc sai,
        # tự tạo ID mới để request luôn có mã theo dõi hợp lệ.
        if re.fullmatch(r"req-[0-9a-fA-F]{8}", supplied_id):
            correlation_id = supplied_id.lower()
        else:
            correlation_id = f"req-{uuid.uuid4().hex[:8]}"

        # Bind ID vào context của structlog để các log trong request tự mang ID này.
        bind_contextvars(correlation_id=correlation_id)

        # Cho route truy cập ID để gắn cùng mã vào trace hoặc response body.
        request.state.correlation_id = correlation_id

        # Bắt đầu đo thời gian xử lý request.
        start = time.perf_counter()
        response = await call_next(request)

        # Tính thời gian đã trôi qua và trả ID/thời gian cho client qua response headers.
        response_time_ms = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = f"{response_time_ms:.2f}"

        return response
