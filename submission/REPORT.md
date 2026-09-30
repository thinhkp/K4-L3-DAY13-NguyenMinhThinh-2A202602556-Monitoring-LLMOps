# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyen Minh Thinh
- **MSSV:** 2A202602556
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/thinhkp/K4-L3-DAY13-NguyenMinhThinh-2A202602556-Monitoring-LLMOps
- **Commit SHA cuối:** Chưa có; cập nhật sau khi commit các thay đổi cuối.
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-<MSSV>`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/pytest.txt` |
| Log validator | `evidence/log-validator.txt` |
| Dashboard validator | `evidence/dashboard-validator.txt` |
| Structured log + incident log | `evidence/01-incident-log.png` |
| Trace list | `evidence/02-trace-list.png` |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png` |
| Prompt versions + promote/rollback | `evidence/04-prompt-versioning.png` |
| Dashboard + incident metric | `evidence/05-dashboard-incident.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 (58 dòng log, 27 ID) | Không thiếu trường/enrichment; 0 PII bị phát hiện |
| `validate_dashboard.py` | 6/6 | 6/6 | Contract có đủ sáu panel |
| `pytest` | 22 passed (starter) | Full suite chưa xác nhận trong sandbox; 7 test CP1/CP2 liên quan đã pass | Full run bị Windows chặn quyền thư mục tạm |
| Số traces hợp lệ | Chưa xác nhận | Chưa xác nhận trace mới trên Langfuse | Kết nối Cloud bị từ chối từ môi trường chạy |
| Số PII leak | 0 trong baseline được kiểm tra | 0 | Log validator không phát hiện PII thô |
| Latency P95 / TTFT P95 | 1046 ms / 50 ms (baseline trước challenge) | 3504 ms / 50 ms (5 request challenge) | Challenge `rag_slow`; ngưỡng latency challenge 2000 ms |
| Retrieval success rate | 100% | 100% | Scenario làm chậm retrieval, không làm retrieval thất bại |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware nhận `x-request-id` dạng `req-<8-hex>` hoặc tự sinh ID, bind vào structlog context, đưa vào response header và truyền cùng ID vào trace metadata.
- **Các metadata được ghi vào structured log:** `user_id_hash`, `session_id`, `feature`, `model`, `env` cùng `correlation_id`.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` duyệt các chuỗi trong event (kể cả dict/list lồng nhau) trước JSONL writer và JSON renderer; email, số điện thoại VN, CCCD và thẻ được thay bằng marker `[REDACTED_...]`.
- **Cách kiểm chứng kết quả:** Log validator đạt 100/100; integration smoke check xác nhận ID/header/metadata và PII đã che.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Chưa thể xác nhận số trace mới; Langfuse Cloud API tại `us.cloud.langfuse.com` từ chối kết nối (`WinError 10061`) trong lần kiểm tra này.
- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run`; child `retrieval` dạng retriever và `generation` dạng generation. Capture input/output bị tắt; generation ghi model, token usage và cost.
- **Cách nối trace với log:** Cùng `correlation_id` được ghi trong structured log và metadata của root trace.
- **Prompt name:**
- **Version/label baseline:**
- **Version/label candidate:**
- **Trace ID của mỗi version:** Chưa thu được do Langfuse Cloud không kết nối được.
- **Cách promote và rollback `production`:** Chưa thực hiện trên project; cần tạo/kiểm tra `day13-chat` v1/v2 và đổi label trên Langfuse UI khi kết nối Cloud hoạt động.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Runtime dashboard đọc `data/logs.jsonl`, cập nhật 30 giây, cửa sổ 60 phút; gồm latency/TTFT, traffic, errors/retrieval success, cost, tokens và quality. Chạy `python scripts/dashboard.py`, mở `http://127.0.0.1:8050`.
- **SLO và lý do chọn:** 99.5% request trong 28 ngày phải thành công với latency ≤3000 ms.
- **Cách tính error budget:** 100%-99.5%=0.5%; với 10,000 request cho phép tối đa 50 request lỗi hoặc chậm hơn ngưỡng.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (>3000 ms/5m), `ElevatedRequestErrorRate` (>2%/5m), `LowRetrievalSuccess` (<90%/5m); runbook ở `docs/alerts.md`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (K4, seed 1312).
- **Khoảng thời gian điều tra:** 2026-09-30 16:07:57–16:08:08 UTC.
- **Triệu chứng từ metrics:** Năm request feature `monitoring` có latency 2859–3504 ms; P95=3504 ms, cao hơn ngưỡng challenge 2000 ms. Baseline P95 trước challenge là 1046 ms.
- **Log line và correlation ID liên quan:** `response_sent` có `correlation_id=req-a273b0de`, latency 3504 ms; các request challenge còn lại cũng trên 2850 ms.
- **Trace ID và span gây ảnh hưởng:** Span dự kiến là `retrieval`; trace ID chưa xác nhận do kết nối Langfuse Cloud bị từ chối. Không có trace ID giả được ghi vào báo cáo.
- **Root cause:** Challenge bật scenario `rag_slow`; `app/mock_rag.py` cố ý chờ 2.5 giây trong retrieval. Metric latency tăng khớp với triệu chứng này; tool vẫn thành công (retrieval success 100%).
- **Fix action:** Đã tắt incident sau khi thu workload; `/health` xác nhận `rag_slow=false`.
- **Preventive measure:** Alert P95 latency >3000 ms trong 5 phút; runbook nối metrics → log theo correlation ID → trace cùng ID. Cần xác minh span trên Langfuse khi kết nối được.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Không capture raw input/output trong trace; chỉ lưu metadata và preview đã scrub để tránh đưa PII vào telemetry.
- **Một lỗi/blocker đã gặp:** Windows sandbox chặn quyền thư mục tạm khi chạy toàn bộ pytest; kết nối outbound tới Langfuse Cloud bị từ chối.
- **Cách tìm nguyên nhân và xử lý:** Dùng Python trong `.venv`; chạy test PII/trace tập trung và smoke check trong ứng dụng. Ghi rõ phần Cloud cần xác nhận thủ công, không bịa trace/prompt evidence.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics phát hiện latency tăng; log chọn request bằng correlation ID; trace cần xác định retrieval là span chậm.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Version/label cho phép gắn hành vi và cost với prompt đã chạy; rollback khôi phục bản ổn định; SLO 99.5% đặt giới hạn lỗi/chậm chấp nhận được.
- **Điều quan trọng nhất đã học:** Phải nối metric, log và trace bằng cùng request ID để chứng minh nguyên nhân.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Chưa xác minh 10 trace mới, prompt v1/v2 và promote/rollback trên Langfuse; chưa có screenshot runtime; full pytest cần chạy lại ngoài sandbox.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
