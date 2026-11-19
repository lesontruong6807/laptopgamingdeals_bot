#!/usr/bin/env python3
"""Báo deal laptop Lenovo/ASUS <= $1300 (US) từ gaminglaptop.deals qua Telegram."""
import html, json, os, sys, urllib.request, urllib.parse

API = "https://gaminglaptop.deals/api/deals/us"
MAX_PRICE = 1300.00
BRANDS = ("asus", "lenovo", "rog ", "tuf ", "legion", "loq", "zephyrus")
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
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


def send(text, dry):
    if dry:
        print(text, "\n" + "-" * 40)
        return
    tok, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data, timeout=30)


def main():
    dry = "--dry-run" in sys.argv
    src = sys.argv[sys.argv.index("--file") + 1] if "--file" in sys.argv else None
    seen = json.load(open(STATE)) if os.path.exists(STATE) else {}
    new_seen = {}
    for d in fetch(src):
        if not matches(d):
            continue
        key, price = str(d["id"]), d["currentPrice"]
        new_seen[key] = price
        # báo nếu máy mới lọt vào tầm giá, hoặc giá giảm thêm so với lần báo trước
        if key not in seen or price < seen[key]:
            send(fmt(d), dry)
        else:
            new_seen[key] = min(price, seen[key])
    if not dry:
        json.dump(new_seen, open(STATE, "w"))


if __name__ == "__main__":
    main()
