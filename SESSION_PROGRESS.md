# Session Progress — Hệ C1 Paper Forward Test (hybrid local + GitHub Actions)

Cập nhật: 08/09/2026. File này để nắm nhanh bối cảnh và việc cần làm tiếp khi quay lại.

## Mục tiêu

Forward test **paper C1** ($1000 ảo, 20 cặp Binance USD-M futures, TF 4h, risk 0.5%)
chạy tự động mỗi 4h, **không phụ thuộc máy bật/tắt**, kèm dashboard local xem state.

## Kiến trúc cuối (đã chốt — hybrid)

| Nguồn | Lịch | Vai trò |
|---|---|---|
| Cron local (máy bật) | `:40` của `0,4,8,12,16,20` — pull → `run_paper.py run` + `report` → commit + push | **Nguồn chính** (fetch Binance OK) |
| GitHub Actions `c1-paper.yml` | `:35` mỗi 4h | **Backup** — tiếp quản khi máy tắt >7h |

- **Failover guard**: `paper_state.json.last_good_scan` = mốc lần quét *CÓ DỮ LIỆU thành công*
  gần nhất (chỉ ghi khi fetch được ≥1 cặp). Actions **SKIP** nếu `last_good_scan` ≤7h tuổi
  (local vừa lo rồi → tránh race/double-open); >7h thì Actions chạy. Code: step "Failover Guard" trong workflow.
- **Guard chống backfill** (trong runner): chỉ MỞ lệnh khi tín hiệu mới có `entry_time` ≤
  `MAX_SIGNAL_AGE_H=12`; tín hiệu cũ hơn chỉ cập nhật marker. Giữ forward test "sạch" khi
  hệ bị gián đoạn.
- **Rào cản thực tế**: Binance **geo-block GitHub runner (HTTP 451)** → khi máy tắt,
  Actions thường không lấy được dữ liệu → **không mở lệnh mới, không sinh lỗi**; móc đó bỏ
  trống. Khi máy bật lại, hệ tiếp tục từ điểm dừng (guard giữ số liệu sạch).
  - Đã kiểm tra: `data-api.binance.vision` không phục vụ futures (404 `/fapi/v1/*`),
    `api.binance.vision` (spot) từ local cũng bị chặn (HTTP 000). **Không có mirror công khai
    nào chạy được từ GH runner.** Nếu muốn 24/7 thật sự, cần VPS self-host runner
    (Oracle Cloud free / Hetzner ~4€) — chưa làm, để trong "Chưa làm".

## Việc đã hoàn thành

1. Sửa `IndentationError` `dashboard.py` (`api_watchlist` docstring); đổi default port
   **5000 → 8787** (5000 bị macOS ControlCenter/AirPlay chiếm → 403) tại `run_dashboard.py`,
   `dashboard.py`, `Tamly/spec-C1-C2.md`. Test 6 endpoint + 11 request liên tiếp đều 200.
2. `paper_account.py` + `paper_runner.py`: guard chống backfill (`MAX_SIGNAL_AGE_H=12`) +
   field `last_good_scan` (chỉ ghi khi fetch OK).
3. Dashboard chuyển sang **chế độ chỉ xem**: `/api/run` = `git pull --rebase --autostash`
   (không chạy engine local); UI nút "⟳ Đồng bộ từ GitHub".
4. `.github/workflows/c1-paper.yml`: schedule `:35` mỗi 4h, concurrency group
   `trading-git-push`, cài deps → **Failover Guard** → run/report (skip khi guard=skip) → commit+push state.
5. Cron local thêm dòng `:40` mỗi 4h: pull → run → report → `git add/commit/push` state
   (máy bật = nguồn chính). Các cron futures cũ giữ nguyên.
6. `.gitignore`: thêm `C1_C2_strategies/data/` (cache OHLCV không push).
7. launchd `com.c1paper.dashboard` (KeepAlive, RunAtLoad) đang chạy → `http://127.0.0.1:8787`.
8. `Tamly/spec-C1-C2.md`: mô tả lịch hybrid + giới hạn 451. `DAILY.md`: checklist hằng ngày.
9. **Verify Actions**: run `34147500796` → `Failover guard = skip` → bước run/report bị bỏ →
   job ✓. Guard hoạt động đúng.

## Trạng thái forward test hiện tại

- Paper start: `2026-09-07T09:39:58+00:00`; equity $1000; 0 lệnh; 20 cặp đã ghi marker.
- `last_good_scan` đang được local cập nhật mỗi móc 4h (khi máy bật).
- Commit liên quan: `dabac72`, `414f93f`, `247a988`, `2390bcd`, `bd0f301`, `95e7d7a`.

## Việc chưa làm / ý tưởng

- [ ] Cho forward test chạy vài tuần sạch (không can thiệp) → review `paper_report.txt` + `paper_metrics.csv` (kỳ vọng ròng, max DD, win rate).
- [ ] Nếu muốn 24/7 thật khi máy tắt: cài VPS + GH self-host runner (hoặc tự-host engine + nguồn dữ liệu); hiện tại Actions bị Binance 451 nên chỉ best-effort.
- [ ] Tìm mirror dữ liệu Binance futures chạy được từ GH runner (bài toán mở — hiện chưa có).
- [ ] Dashboard HTML còn đơn giản (SVG equity thủ công) — có thể nâng cấp nếu cần xem chi tiết.
- [ ] Alert (Telegram/email) khi Actions 451 kéo dài hoặc `last_good_scan` quá cũ — để không phải mở Actions tab.

## Cách chạy nhanh (nhắc lại)

```
.venv/bin/python run_paper.py run       # engine (local, sẽ tự ghi last_good_scan)
.venv/bin/python run_paper.py report    # báo cáo tuần
.venv/bin/python run_paper.py reset     # reset $1000 (chỉ dùng có chủ đích)
.venv/bin/python run_dashboard.py       # dashboard http://127.0.0.1:8787
tail -20 c1_paper.log                    # xác nhận cron 4h đã chạy
gh run list --workflow=c1-paper.yml --limit 3
```

File quan trọng:

- `C1_C2_strategies/paper/paper_config.py` — universe, risk, TF, `MAX_SIGNAL_AGE_H`, đường file state.
- `C1_C2_strategies/paper/paper_account.py` / `paper_runner.py` — PaperAccount, guard.
- `C1_C2_strategies/paper/dashboard.py`, `run_dashboard.py` — dashboard port 8787, `/api/run` = git pull.
- `.github/workflows/c1-paper.yml` — workflow backup + failover guard.
- `.github/workflows/futures.yml` — pattern chuẩn local-primary + Actions-failover.
- `Tamly/spec-C1-C2.md`, `Tamly/rules.md` (A07/H07), `DAILY.md`.