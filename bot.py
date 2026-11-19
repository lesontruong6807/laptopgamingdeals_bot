#!/usr/bin/env python3
"""Báo deal laptop Lenovo/ASUS <= $1300 (US) từ gaminglaptop.deals qua Telegram."""
import html, json, os, sys, time, urllib.error, urllib.request, urllib.parse

API = "https://gaminglaptop.deals/api/deals/us"
MAX_PRICE = 1300.00
BRANDS = ("asus", "lenovo", "rog ", "tuf ", "legion", "loq", "zephyrus")
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
STATUS = os.path.join(HERE, "status.json")  # trạng thái hoạt động của bot
HEARTBEAT_DAYS = 7
ERROR_COOLDOWN_H = 24
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept": "application/json"}


def fetch(src):
    if src:  # test offline: --file sample.json
        return json.load(open(src))
    req = urllib.request.Request(API, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def matches(d):
    t = d["title"].lower()
    return (d.get("state") == "live" and d.get("inStock")
            and any(b in t for b in BRANDS)
            and d["currentPrice"] / 100 <= MAX_PRICE)


def fmt(d):
    cur, orig = d["currentPrice"] / 100, d["originalPrice"] / 100
    pct = round((1 - cur / orig) * 100) if orig > cur else 0
    s = d.get("specs") or {}
    e = html.escape
    badge = " 🔥 <b>Giá thấp kỷ lục</b>" if d.get("priceTier") == "record_low" else ""
    lines = [
        f"💻 <b>{e(d['title'])}</b>{badge}",
        f"💰 <b>${cur:,.2f}</b>  <s>${orig:,.2f}</s>  (giảm <b>{pct}%</b>, tiết kiệm ${orig-cur:,.0f})",
        f"🏪 {e(d.get('retailer',''))}",
        f"• CPU: {e(s.get('cpu','?'))}",
        f"• GPU: {e(s.get('gpu','?'))}",
        f"• RAM: {e(s.get('ram','?'))}",
        f"• Màn hình: {e(s.get('screen','?'))}",
        f"• Ổ cứng: {e(s.get('storage','?'))}",
    ]
    if d.get("notes"):
        lines.append(f"• Ghi chú: {e(d['notes'])}")
    lines.append(f"🔗 {d.get('directUrl') or d.get('retailerUrl')}")
    return "\n".join(lines)


def send(text, dry, image=None):
    if dry:
        print(("[ảnh: %s]\n" % image if image else "") + text, "\n" + "-" * 40)
        return
    tok, chat = os.environ["TELEGRAM_BOT_TOKEN"].strip(), os.environ["TELEGRAM_CHAT_ID"].strip()
    base = f"https://api.telegram.org/bot{tok}/"
    if image and len(text) <= 1024:  # giới hạn caption của Telegram
        try:
            data = urllib.parse.urlencode({"chat_id": chat, "photo": image, "caption": text,
                                           "parse_mode": "HTML"}).encode()
            urllib.request.urlopen(base + "sendPhoto", data, timeout=30)
            return
        except Exception as ex:  # ảnh lỗi -> gửi tin chữ
            print("sendPhoto lỗi, chuyển sang tin chữ:", ex)
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    urllib.request.urlopen(base + "sendMessage", data, timeout=30)


def load(path):
    return json.load(open(path)) if os.path.exists(path) else {}


def run(dry, src, status):
    seen = load(STATE)
    new_seen, in_budget = {}, []
    for d in fetch(src):
        if not matches(d):
            continue
        key, price = str(d["id"]), d["currentPrice"]
        new_seen[key] = price
        in_budget.append(d)
        # báo nếu máy mới lọt vào tầm giá, hoặc giá giảm thêm so với lần báo trước
        if key not in seen or price < seen[key]:
            send(fmt(d), dry, d.get("imageUrl"))
        else:
            new_seen[key] = min(price, seen[key])
    if not dry:
        json.dump(new_seen, open(STATE, "w"))
    return in_budget


def explain(ex):
    if isinstance(ex, urllib.error.HTTPError) and ex.code in (403, 429):
        return f"Trang gaminglaptop.deals từ chối truy cập (HTTP {ex.code})."
    if isinstance(ex, urllib.error.HTTPError):
        return f"Máy chủ phản hồi lỗi HTTP {ex.code}."
    if isinstance(ex, (json.JSONDecodeError, KeyError, TypeError)):
        return "Dữ liệu từ trang có định dạng không như dự kiến. Có thể trang đã thay đổi cấu trúc."
    return f"Lỗi kết nối hoặc lỗi không xác định ({type(ex).__name__})."


def main():
    dry = "--dry-run" in sys.argv
    src = sys.argv[sys.argv.index("--file") + 1] if "--file" in sys.argv else None
    status, now = load(STATUS), time.time()
    changed = False
    try:
        in_budget = run(dry, src, status)
    except Exception as ex:
        last = status.get("last_error_sent", 0)
        if now - last >= ERROR_COOLDOWN_H * 3600:
            try:
                send("<b>Cảnh báo hệ thống</b>\n\n"
                     "Bot chưa kiểm tra được deal trong lần chạy này.\n"
                     f"Nguyên nhân: {html.escape(explain(ex))}\n\n"
                     "Bot sẽ tự thử lại ở lần chạy kế tiếp. Nếu lỗi kéo dài, "
                     "vui lòng kiểm tra tab Actions của repository để xem chi tiết.", dry)
                status["last_error_sent"] = now
            except Exception:
                pass
        status["in_error"] = True
        if not dry:
            json.dump(status, open(STATUS, "w"))
        raise
    if status.pop("in_error", False):
        send("<b>Thông báo hệ thống</b>\n\nBot đã hoạt động trở lại bình thường.", dry)
        changed = True
    if now - status.get("last_heartbeat", 0) >= HEARTBEAT_DAYS * 86400:
        if in_budget:
            low = min(in_budget, key=lambda x: x["currentPrice"])
            extra = (f"Hiện có {len(in_budget)} máy Lenovo/ASUS trong ngân sách "
                     f"(thấp nhất: {html.escape(low['title'])} ở ${low['currentPrice']/100:,.2f}).")
        else:
            extra = "Hiện chưa có máy Lenovo/ASUS nào trong ngân sách."
        send("<b>Báo cáo định kỳ</b>\n\nBot đang hoạt động bình thường. " + extra, dry)
        status["last_heartbeat"] = now
        changed = True
    if changed and not dry:
        json.dump(status, open(STATUS, "w"))


if __name__ == "__main__":
    main()
