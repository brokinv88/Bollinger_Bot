#!/bin/bash
# Crypto early-discovery weekly/daily scan — triggered by cron 08:00 hằng ngày.
# Chạy quy trình quét theo skill crypto-early-discovery và xuất báo cáo HTML.

set -uo pipefail

export PATH="/Users/brokinv/.npm-global/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
PROJ="/Users/brokinv/Desktop/AI Agent/Trading"
cd "$PROJ" || exit 1

mkdir -p reports/crypto

STAMP=$(date +%Y-%m-%d)
OUT="$PROJ/reports/crypto/crypto_scan_${STAMP}.html"
LOG="/tmp/crypto_scan_${STAMP}.log"

echo "[$(date '+%F %T')] bat dau scan" >> "$LOG"

# Đồng bộ repo trước khi chạy (giống các job cron khác của project)
git pull --rebase --autostash origin main >> "$LOG" 2>&1

# B1: Chuẩn bị dữ liệu DefiLlama bằng script (không để LLM tự scrape API).
# Public API của DefiLlama chỉ trả fees (revenue đã paywall) — script xuất digest
# kèm ghi chú proxy, LLM chỉ cần đọc file.
export DATAD="$PROJ/reports/crypto/_data_${STAMP}.md"
export DATAJ="$PROJ/reports/crypto/_data_${STAMP}.json"
if python3 "$PROJ/crypto_data.py" --top 40 --out-dir "$PROJ/reports/crypto" > "$LOG.data" 2>&1; then
  echo "[$(date '+%F %T')] du lieu DefiLlama san sang: $DATAD" >> "$LOG"
else
  echo "[$(date '+%F %T')] CANH BAO: crypto_data.py that bai — de LLM tu fetch, co the dung fees proxy" >> "$LOG"
  export DATAD=""
  export DATAJ=""
fi

PROMPT="Chạy quy trình quét thị trường crypto theo skill crypto-early-discovery cho tuần vừa qua (~7 ngày gần nhất).

DỮ LIỆU SỐ ĐÃ CHUẨN BỊ SẴN (đọc trước tiên, đừng tự gọi API DefiLlama thủ công):
- Dữ liệu fees + mcap + age: ${DATAD:-<không có — tự fetch API>}
- JSON đầy đủ: ${DATAJ:-<không có>}
Cả hai do script crypto_data.py sinh ra từ public API DefiLlama. Lưu ý quan trọng: public API không trả cột 'revenue' (đã paywall), nên cột doanh thu được tính từ FEES làm proxy; với take rate thật, ước lượng dựa trường 'methodology' trong JSON hoặc ghi rõ là fee proxy trong báo cáo. Nếu DATAD trống (script lỗi), hãy tự fetch https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true và https://api.llama.fi/protocols bằng curl/python.

Thực hiện đầy đủ theo skill:
- Kênh A1 + A2: từ file dữ liệu — protocol < 90 ngày tuổi trong top 20 fee24h, và mọi protocol có change_1m > 50% kèm fee30d > \$250K.
- Kênh B: DeFiLlama Chains theo % TVL 7d/30d — chain dưới 6 tháng tuổi đang tăng mạnh.
- Kênh C: mô hình đang thắng tuần này xuất hiện lại ở chain khác.
- Kênh F: fetch llms.txt của các candidate + chain mới, so tiêu đề trang mới.
- Kênh H: take rate (doanh thu ÷ phí) so các mốc — tụt khi phí tăng = nghi TGE sắp tới (dùng methodology trong JSON để ước take rate).
- Đối chiếu Kênh D (mindshare/ví smart money — dùng websearch), I (pool mạo danh), E (dấu vết mở rộng), K (gọi vốn lớn = TGE chậm).

Dùng websearch/webfetch để kiểm chứng và lấy tin/tình tiết, mọi số đều ghi nguồn + ngày. Báo cáo bằng tiếng Việt, giữ thuật ngữ tiếng Anh.

Xuất ra MỘT file HTML (tự render, có CSS inline đọc sạch, desktop + mobile) tại đường dẫn:
$OUT

BẮT BUỘC cấu trúc để báo cáo gộp chung hoạt động:
- Toàn bộ nội dung nằm trong <div class="wrap">...</div> (một khối duy nhất, close trước </body>).
- Giữ nguyên bộ class chuẩn khi có thể: card, kpi, note, warnbox, tier1/t2/t3 (badge), num,
  pos/neg/warn/blu/pur, pill, src, foot, h1/h2/h3, meta, table/th/td.
- Không dùng id trùng nhau và không đổi biến CSS màu nền body sang ảnh nền lớn (dashboard overlay sẽ xử lý nền).

File HTML phải tuân đúng định dạng output của skill:
1. Ngày quét + phạm vi đã quét (kênh nào, category nào)
2. Bảng ứng viên theo tầng (1/2/3), kèm số liệu MC, doanh thu ngày, MC÷DT, % doanh thu đời trong 7d, và nguồn
3. 1-3 cái đáng chú ý nhất (mỗi cái 3-5 dòng)
4. Cái đã loại và lý do
5. Bước tiếp theo (đề xuất cái nào nên chạy crypto-project-research)
6. Bảng nguồn
Cuối file ghi: 'Đây là tổng hợp dữ liệu, không phải lời khuyên đầu tư.'

Không thực hiện bất kỳ giao dịch mua/bán nào. Chỉ đọc dữ liệu và viết file báo cáo tại đúng đường dẫn $OUT."

opencode run --auto --dir "$PROJ" "$PROMPT" >> "$LOG" 2>&1
RC=$?

if [ $RC -ne 0 ]; then
  echo "[$(date '+%F %T')] scan LOI (rc=$RC). Log: $LOG" >> "$LOG"
  exit $RC
fi

echo "[$(date '+%F %T')] scan hoan tat: $OUT" >> "$LOG"

# B2: Gộp tất cả báo cáo theo ngày thành 1 dashboard HTML (reports/crypto/index.html)
if python3 "$PROJ/crypto_report_index.py" --dir "$PROJ/reports/crypto" --out index.html >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] dashboard cap nhat: reports/crypto/index.html" >> "$LOG"
else
  echo "[$(date '+%F %T')] CANH BAO: crypto_report_index.py that bai (mac dinh bo qua, van commit report)" >> "$LOG"
fi

# Auto-commit + push báo cáo (giữ lịch sử trên remote)
git add reports/crypto/ >> "$LOG" 2>&1
git diff --staged --quiet || {
  git commit -q -m "crypto scan report $STAMP [skip ci]" >> "$LOG" 2>&1
  git push origin main >> "$LOG" 2>&1
}