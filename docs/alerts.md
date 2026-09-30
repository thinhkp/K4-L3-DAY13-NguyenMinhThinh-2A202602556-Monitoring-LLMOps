# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: P95 latency, mục tiêu request tốt có latency không quá 3000 ms.
- Điều kiện và thời gian duy trì: P95 của `response_sent.latency_ms` lớn hơn 3000 ms liên tục 5 phút.
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn để nhận câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Xem panel latency và so P50/P95/P99, TTFT với baseline.
  2. Lọc `response_sent` trong `data/logs.jsonl` theo thời gian, lấy `correlation_id` có latency cao.
  3. Mở trace cùng `correlation_id` trên Langfuse và xác định span chậm.
- Mitigation tạm thời: nếu generation/prompt gây chậm, rollback label prompt về version ổn định; nếu retrieval chậm, tắt incident practice hoặc khôi phục dịch vụ retrieval.
- Owner: `NguyenMinhThinh-2A202602556`

## Alert 2

- Tên: `ElevatedRequestErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tỷ lệ request hoàn tất thành công.
- Điều kiện và thời gian duy trì: `request_failed / request_received` lớn hơn 2% liên tục 5 phút.
- Ảnh hưởng tới người dùng: một phần request không nhận được câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Xem panel errors để xác nhận error rate, loại lỗi và khoảng thời gian.
  2. Lọc event `request_failed` trong log, ghi `error_type` và `correlation_id`.
  3. Mở trace cùng ID để tìm span có trạng thái lỗi và xác định bước phát sinh.
- Mitigation tạm thời: khôi phục cấu hình/prompt ổn định hoặc tắt incident practice; nếu lỗi thuộc retrieval, khôi phục nguồn retrieval trước khi chạy lại workload.
- Owner: `NguyenMinhThinh-2A202602556`

## Alert 3

- Tên: `LowRetrievalSuccess`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: retrieval success tối thiểu 90%.
- Điều kiện và thời gian duy trì: tỷ lệ `tool_success == true` trên các event có `tool_success` nhỏ hơn 90% liên tục 5 phút.
- Ảnh hưởng tới người dùng: câu trả lời có thể thiếu tài liệu liên quan hoặc request có thể thất bại.
- Ba bước kiểm tra đầu tiên:
  1. Xem panel errors và retrieval success, so sánh với baseline.
  2. Lọc `request_failed` và `response_sent` có `tool_name=retrieval`; lấy correlation ID có `tool_success=false`.
  3. Mở trace cùng ID và kiểm tra retriever span, thời gian chạy và trạng thái.
- Mitigation tạm thời: khôi phục vector store hoặc cấu hình retrieval; nếu đang demo incident, tắt scenario sau khi đã lưu evidence.
- Owner: `NguyenMinhThinh-2A202602556`
