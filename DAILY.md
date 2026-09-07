# Checklist hằng ngày (hệ tự động — kiểm tra, không thao tác)

Ngày tạo: 08/09/2026. Nguyên tắc vận hành xe theo `Tamly/rules.md` (A07: kiểm tra lịch đã
chạy, dữ liệu không cũ; H04: kiểm soát chi phí).

## Khung giờ chạy

- Cron local mỗi móc `:40` của `0,4,8,12,16,20` (giờ máy): pull → `run_paper.py run`
  + `report` → push state lên GitHub. **Máy bật là nguồn chính.**
- GitHub Actions `c1-paper.yml` mỗi móc `:35`: backup khi máy tắt >7h (failover guard
  dựa trên `last_good_scan`); Binance geo-block runner (HTTP 451) nên thường không mở
  lệnh khi máy tắt — móc đó bỏ trống, guard chống backfill giữ số liệu sạch.

## Việc cần làm mỗi ngày

1. [ ] Giữ máy bật vào các móc `:40` (0,4,8,12,16,20) để local chạy + push.
2. [ ] Mở `http://127.0.0.1:8787` — xem Overview (equity/drawdown/vị thế), Trades,
      Universe. Nếu state cũ, nhấn "⟳ Đồng bộ từ GitHub".
3. [ ] Xác nhận lịch chạy (dưới 1 phút):
   ```
   tail -20 c1_paper.log                       # mỗi móc 4h phải có "=== PAPER C1 ==="
   gh run list --workflow=c1-paper.yml --limit 3   # khi máy tắt lâu
   ```
4. [ ] Không sửa tham số, không điều chỉnh giữa chừng. Forward test cần chạy sạch
      nhiều tuần mới có ý nghĩa.

## Lịch review tuần (không phải hằng ngày)

- Xem `C1_C2_strategies/reports/paper_report.txt` + `paper_metrics.csv`: kỳ vọng ròng,
  win rate, profit factor, max drawdown (T03, T08).
- Đối chiếu với phiên bản chuẩn; chỉ đổi quy tắc khi có giả thuyết + bằng chứng (T05, T06).
- Giao dịch thật: theo checklist mục 9 trong `Tamly/rules.md`.

## Khi có sự cố

- Log lỗi: `C1_C2_strategies/reports/paper_state.json` (`last_good_scan`, `last_update`),
  `c1_paper.log`, Actions runs.
- Nếu `last_good_scan` quá cũ mà máy vẫn bật: kiểm tra mạng Binance / cron; chạy thủ công
  `.venv/bin/python run_paper.py run` rồi xem log.
- Tách vận hành với nghiên cứu: không mở quyền mới cho agent khi chưa có quy trình riêng
  (A07, H07).