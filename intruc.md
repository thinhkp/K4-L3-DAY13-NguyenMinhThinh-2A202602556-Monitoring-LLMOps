# Hướng dẫn Lab 13 — Monitoring & LLMOps

> Tài liệu này tóm tắt bài lab cá nhân K4-L3B dựa trên brief và tài liệu trong repository. Thực hiện trong fork cá nhân; tự chạy workload, thu evidence và ghi kết quả thật của mình vào `submission/REPORT.md`.

## 1. Bài toán và mục tiêu

Một API trả HTTP 200 vẫn có thể hoạt động kém: phản hồi chậm, tiêu tốn nhiều token/chi phí, retrieval thất bại hoặc chất lượng câu trả lời giảm. Bài lab yêu cầu bổ sung khả năng quan sát để phát hiện vấn đề, tìm request bị ảnh hưởng và giải thích bước gây ra vấn đề.

Quy trình điều tra bắt buộc:

```text
Metrics → Logs → Traces → Root cause
```

1. **Metrics:** nhận biết triệu chứng, mức độ và khoảng thời gian.
2. **Logs:** chọn request cụ thể bằng `correlation_id`.
3. **Traces:** tìm bước chậm hoặc lỗi trong chính request đó, chẳng hạn retrieval hay generation.
4. **Root cause:** kết luận từ metric, log và trace khớp nhau; đề xuất cách xử lý và ngăn tái diễn.

Sau lab, bạn cần làm được structured JSON logging và che PII; theo dõi latency, TTFT, traffic, errors, tokens, cost, retrieval success và quality proxy; tạo ít nhất 10 traces; quản lý prompt v1/v2 và rollback; dựng dashboard sáu panel; định nghĩa SLO/error budget, ba alert có runbook; và viết báo cáo incident dựa trên bằng chứng.

## 2. Phạm vi và quy tắc

- Đây là bài **cá nhân**, dự kiến 240 phút (9:00–13:00). Dùng fork riêng từ starter K4-L3B và đặt tên `K4-L3-DAY13-HoVaTen-MSSV-Monitoring-LLMOps` (không dấu, không khoảng trắng).
- Không push bài lên starter, không dùng chung repository/project/key, không tạo pull request về starter.
- Mỗi học viên tự tạo project Langfuse `day13-k4-l3b-<MSSV>` và tự tạo traces/prompt evidence.
- Không commit `.env`, API key, secret, PII thô, log sinh ra hoặc `config/challenge.json` chính thức.
- Chỉ chạy challenge chính thức sau khi Lab Coach mở CP3 và phát hành file dành cho K4-L3B. Không tự tạo, sửa hay lấy challenge của lớp khác. Practice scenarios có thể dùng để thử trước.
- AI được phép hỗ trợ giải thích, phân tích lỗi và review; bạn phải hiểu, xác minh và tự bảo vệ được thay đổi. Không tạo số liệu hay evidence giả.
- Deadline mặc định: 23:59:59 ngày diễn ra lab theo Asia/Ho_Chi_Minh; làm theo thông báo mới nhất nếu có.

## 3. Chuẩn bị môi trường (CP0)

Yêu cầu: Python 3.11–3.13 (khuyến nghị 3.12; tránh 3.14), Git và tài khoản Langfuse Cloud riêng. Mở terminal tại thư mục gốc repository, nơi có `requirements.txt`.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Nếu đã cài đúng phiên bản Python, có thể thay `py -3.12` bằng `python`.

### macOS/Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Tạo project Langfuse cá nhân, rồi điền các giá trị của project đó vào `.env`:

```dotenv
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_PROMPT_NAME=day13-chat
LANGFUSE_PROMPT_LABEL=production
```

Dùng base URL khu vực US nếu project nằm ở US. Không chia sẻ hoặc commit `.env`; không chụp màn hình trang API Keys.

Mở hai terminal ở thư mục gốc và activate môi trường ảo ở cả hai.

**Terminal 1 — API:**

```bash
uvicorn app.main:app --reload --env-file .env
```

**Terminal 2 — baseline:**

```bash
python scripts/load_test.py
python scripts/validate_logs.py
python scripts/validate_dashboard.py
python -m pytest -q
```

CP0 đạt khi `/health` trả `ok: true`, log được tạo và trace xuất hiện trong project Langfuse cá nhân (nếu đã cấu hình key). Ghi các con số baseline thực tế vào báo cáo **trước khi sửa code**; validator log thấp ở baseline là điều có thể xảy ra vì starter còn TODO.

## 4. Lộ trình thực hiện

| Mốc | Thời gian | Công việc | Điều kiện hoàn thành |
|---|---:|---|---|
| CP0 | 9:00–9:30 | Cài đặt, chạy API và ghi baseline | Health check, log và baseline được ghi |
| CP1 | 9:30–10:20 | Correlation ID, structured log, PII | Log validator đạt ít nhất 80/100; response có ID hợp lệ |
| CP2 | 10:20–11:40 | Tracing, prompt, dashboard, SLO/alerts | Ít nhất 10 traces; dashboard validator 6/6; prompt v1/v2 và rollback |
| CP3 | 11:40–12:30 | Điều tra challenge K4-L3B | Metric, log và trace cùng chỉ về một incident |
| CP4 | 12:30–13:00 | Báo cáo, evidence và kiểm tra cuối | Report/evidence đầy đủ; kiểm tra trên commit cuối |

### CP1 — Logging và PII

Hoàn thiện các TODO liên quan trong `app/middleware.py`, `app/main.py`, `app/logging_config.py`, `app/pii.py` và tests:

- Nhận `x-request-id` hoặc sinh `req-<8-hex>`, xóa context cũ, bind ID cho request và trả ID cùng response time trong response headers.
- Trước log `request_received`, bind `user_id_hash`, `session_id`, `feature`, `model`, `env`.
- Scrub dữ liệu trước khi JSON được render/ghi file. Bao phủ email, số điện thoại Việt Nam, CCCD và số thẻ thanh toán.
- Không ghi nội dung nhạy cảm nguyên văn; kiểm tra cả log runtime lẫn test.

Sau khi lưu baseline, đưa log cũ ra ngoài repository, khởi động lại API, chạy `load_test.py` rồi `validate_logs.py`. Validator đọc toàn bộ `data/logs.jsonl`, nên log cũ có thể làm sai kết quả. CP1 đạt ở mức tối thiểu 80/100 và không để PII mẫu ở dạng thô.

### CP2 — Traces và prompt versioning

Tạo tối thiểu 10 traces của chính mình trong project Langfuse. Trace cần có cấu trúc root và child observations cho retrieval và generation. Generation cần ghi model, input/output token, cost và metadata prompt. Đưa `correlation_id` vào metadata để đối chiếu với log. Không capture raw input/output có thể chứa PII; chỉ lưu preview đã scrub nếu cần.

Quản lý prompt trong cùng tên `day13-chat`:

1. Tạo Text prompt v1 với đủ biến `{{feature}}`, `{{docs}}`, `{{message}}`; gắn `baseline` và `production`.
2. Tạo v2 với một thay đổi nhỏ và gắn `candidate`.
3. Chạy workload với label `baseline`, rồi `candidate`; lưu trace ID và xác nhận version tương ứng.
4. Promote label `production` sang v2, chạy request và xác nhận trace dùng v2.
5. Rollback `production` về v1. Restart API sau khi đổi label vì prompt có thể được cache.

Ghi hai trace ID v1/v2 vào report. Hướng dẫn chi tiết tại [`docs/PROMPT_VERSIONING.md`](docs/PROMPT_VERSIONING.md).

### CP2 — Dashboard, SLO và alerts

Dựng dashboard runtime từ `data/logs.jsonl`, theo contract [`config/dashboard.yaml`](config/dashboard.yaml). Có đúng sáu panel:

| Panel | Nội dung cần thể hiện |
|---|---|
| Latency | P50/P95/P99 và TTFT P95 |
| Traffic | Số request theo thời gian |
| Errors | Error rate, breakdown và retrieval success |
| Cost | Chi phí theo thời gian/cửa sổ |
| Tokens | Input/output token |
| Quality | Quality proxy |

Hiển thị time range, đơn vị và threshold/SLO phù hợp; mặc định contract dùng cửa sổ 60 phút và refresh 30 giây nếu công cụ hỗ trợ. Retrieval success cần tính trên các event có `tool_success`, gồm cả `response_sent` và `request_failed`, không chỉ lấy các dòng lỗi.

Hoàn thiện `config/slo.yaml` với mục tiêu và error budget có số cụ thể; hoàn thiện ba alert symptom-based trong `config/alert_rules.yaml` (condition, duration, severity, owner, Slack channel, runbook); viết bước kiểm tra và mitigation trong `docs/alerts.md`. Chạy `python scripts/validate_dashboard.py`: kết quả cần là 6/6. Validator chỉ kiểm tra cấu hình, nên vẫn cần dashboard runtime có dữ liệu thật.

### CP3 — Challenge và điều tra incident

Chỉ sau thông báo mở CP3, lấy challenge chính thức K4-L3B theo hướng dẫn của Lab Coach. Không chỉnh sửa hoặc commit file challenge. Chuẩn bị log mới, tắt practice incident, chạy baseline rồi thực hiện:

```bash
python scripts/inject_incident.py
python scripts/load_test.py --challenge --concurrency 5
```

Điều tra theo đúng thứ tự:

1. **Metrics:** xác định panel, giá trị bất thường, baseline so sánh và khoảng thời gian.
2. **Logs:** lọc request liên quan trong `data/logs.jsonl`; ghi event và `correlation_id`.
3. **Traces:** tìm trace có cùng ID; so sánh duration/status của retrieval và generation, xác định span gây ảnh hưởng.
4. **Kết luận:** ghi challenge ID, metric, thời gian, log/ID, trace ID, span, root cause, fix action và preventive measure vào report.

Không suy đoán trước khi xem dữ liệu. Challenge chính thức không có trong starter mặc định; thiếu file trước khi Lab Coach release là bình thường. Practice scenario chỉ dùng để luyện, không thay bằng chứng challenge chính thức.

### CP4 — Report và kiểm tra

Hoàn thiện duy nhất `submission/REPORT.md`: thông tin cá nhân/repo/commit, baseline và kết quả cuối, logging/PII, tracing/prompt, dashboard/SLO/alerts, điều tra incident, quyết định kỹ thuật, blocker/cách xử lý, bài học và hạn chế. Chỉ ghi số liệu, trace ID, root cause và kết quả bạn đã thực sự thu được.

## 5. Lệnh và lỗi thường gặp

Chạy lệnh từ thư mục gốc repository, trong môi trường ảo đã activate:

```bash
python scripts/load_test.py
python scripts/validate_logs.py
python scripts/validate_dashboard.py
python -m pytest -q
```

- `pip install` lỗi khi build hoặc nhắc Rust/Visual C++: thường đang dùng Python không tương thích; dùng Python 3.12.
- PowerShell chặn activate: chạy `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` rồi activate lại.
- `ModuleNotFoundError`: kiểm tra đã activate `.venv` và cài `requirements.txt`.
- Port 8000 đã dùng: tìm và dừng tiến trình cũ trước khi chạy API.
- `/health` báo tracing tắt hoặc Langfuse không có trace: kiểm tra ba biến Langfuse, project/region, restart API và chọn time range mới nhất.
- `prompt_source=local-fallback`: kiểm tra key, URL, prompt name/label và prompt Text; restart API sau khi sửa.
- Trace gửi nền: đợi vài giây sau request cuối trước khi dừng API.
- Chạy test khi đã nạp Langfuse key có thể tạo trace test không thuộc workload; không tính nhầm các trace đó vào 10 trace hợp lệ.

Xem thêm [`docs/SETUP.md`](docs/SETUP.md), [`docs/CHECKPOINTS.md`](docs/CHECKPOINTS.md), [`docs/GUIDE.md`](docs/GUIDE.md), [`docs/DASHBOARD_SETUP.md`](docs/DASHBOARD_SETUP.md) và [`docs/mock-debug-qa.md`](docs/mock-debug-qa.md).

## 6. Evidence và cấu trúc nộp

Đặt evidence trong `submission/evidence/`. Hướng dẫn nộp yêu cầu **3 file output text và 5 ảnh runtime**:

| File | Nội dung |
|---|---|
| `pytest.txt` | Kết quả `python -m pytest -q` trên commit cuối |
| `log-validator.txt` | Kết quả log validator; mục tiêu ít nhất 80/100 |
| `dashboard-validator.txt` | Kết quả dashboard validator; mục tiêu 6/6 |
| `01-incident-log.png` | Log request incident với correlation ID và metadata |
| `02-trace-list.png` | Project Langfuse cá nhân với ít nhất 10 trace |
| `03-incident-trace.png` | Waterfall/metadata của trace cùng ID với log incident |
| `04-prompt-versioning.png` | Bằng chứng v1/v2, production v2 và rollback về v1 |
| `05-dashboard-incident.png` | Dashboard đủ sáu panel và metric incident |

Trong báo cáo dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`. Không dùng đường dẫn máy cá nhân. Ảnh phải đọc được và không lộ key/secret/PII. Incident log và trace phải có cùng `correlation_id`; thời gian Langfuse có thể hiển thị theo giờ địa phương trong khi log lưu UTC.

Lưu ba output text bằng PowerShell:

```powershell
python -m pytest -q 2>&1 | Tee-Object -FilePath submission/evidence/pytest.txt
python scripts/validate_logs.py 2>&1 | Tee-Object -FilePath submission/evidence/log-validator.txt
python scripts/validate_dashboard.py 2>&1 | Tee-Object -FilePath submission/evidence/dashboard-validator.txt
```

## 7. Kiểm tra cuối và nộp

Trên commit cuối chạy:

```bash
python -m pytest -q
python scripts/validate_logs.py
python scripts/validate_dashboard.py
git status --short
git log -1 --oneline
```

Trước khi push, xác nhận source/TODO đã hoàn thành, report/evidence đầy đủ, có ít nhất 10 trace cá nhân, prompt promote/rollback, dashboard sáu panel, SLO/error budget và ba runbook; incident có chuỗi metric → log → trace; không có `.env`, challenge, log thô hoặc cache bị đưa vào commit. Stage các thư mục/file cần nộp cụ thể; tránh `git add ..`.

Nộp trên VLearn LMS/Codelabs URL fork cá nhân và commit SHA cuối có chứa source, config, report và evidence. Tham khảo [`docs/SUBMISSION.md`](docs/SUBMISSION.md), [`docs/RULES.md`](docs/RULES.md) và [`docs/RUBRIC.md`](docs/RUBRIC.md) nếu cần kiểm tra chi tiết.
