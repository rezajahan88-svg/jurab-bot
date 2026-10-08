from balethon import Client
from balethon.objects import InlineKeyboard
import json
import os
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---- Settings (set these on Render > Environment) ----
TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = os.environ.get("OWNER_ID")  # your own Bale chat id (get it by sending /myid to the bot)

bot = Client(TOKEN)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_FILE = os.path.join(BASE_DIR, "products.json")
WELCOME_IMAGE = os.path.join(BASE_DIR, "welcome.jpg")


def load_products():
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- Send a message to the owner (used by the website orders) ----------

def notify_owner(text):
    if not OWNER_ID:
        return False
    chat_id = int(OWNER_ID) if OWNER_ID.lstrip("-").isdigit() else OWNER_ID
    data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        f"https://tapi.bale.ai/bot{TOKEN}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


# ---------- Small web server: website talks to this ----------

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class Web(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", ctype="application/json; charset=utf-8"):
        self.send_response(code)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        if self.path.startswith("/products"):
            try:
                body = json.dumps(load_products(), ensure_ascii=False).encode("utf-8")
                self._send(200, body)
            except Exception:
                self._send(500, b'{"ok":false}')
        else:
            self._send(200, b"ok", "text/plain")

    def do_POST(self):
        if not self.path.startswith("/order"):
            self._send(404, b'{"ok":false}')
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0 or length > 10000:
                raise ValueError("bad size")
            data = json.loads(self.rfile.read(length).decode("utf-8"))

            name = str(data.get("name", "")).strip()[:80]
            phone = str(data.get("phone", "")).strip()[:20]
            address = str(data.get("address", "")).strip()[:400]
            if not name or not phone or not address:
                raise ValueError("missing fields")

            products = load_products()
            lines, total = [], 0
            for it in data.get("items", [])[:30]:
                cat, idx, qty = it.get("cat"), int(it.get("idx")), int(it.get("qty"))
                if cat not in products or qty < 1 or qty > 50:
                    continue
                p = products[cat][idx]  # price comes from OUR file, not the website
                lines.append(f"🧦 {p['name']} × {qty} = {p['price'] * qty:,} تومان")
                total += p["price"] * qty
            if not lines:
                raise ValueError("empty order")

            text = (
                "🛍️ سفارش جدید از سایت\n\n"
                + "\n".join(lines)
                + f"\n\n💰 جمع: {total:,} تومان\n\n"
                f"👤 {name}\n📞 {phone}\n📍 {address}"
            )
            ok = notify_owner(text)
            self._send(200 if ok else 500, json.dumps({"ok": ok}).encode())
        except Exception:
            self._send(400, b'{"ok":false}')

    def log_message(self, *args):
        pass


def run_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Web).serve_forever()


threading.Thread(target=run_server, daemon=True).start()


# ---------- Bot keyboards ----------

def main_menu():
    return InlineKeyboard(
        [("🧦 مردانه", "cat:male"), ("🌈 زنانه", "cat:female")]
    )


def product_menu(gender, items):
    rows = []
    for i, p in enumerate(items):
        rows.append([(f"🧦 {p['name']} - {p['price']} تومان", f"buy:{gender}:{i}")])
    rows.append([("🔙 بازگشت", "home")])
    return InlineKeyboard(*rows)


def back_menu():
    return InlineKeyboard([("🏠 بازگشت به منو", "home")])


async def send_welcome(chat_id):
    caption = "سلام! به فروشگاه جوراب خوش اومدی 🧦✨\nلطفا یکی از دسته‌ها رو انتخاب کن:"
    try:
        with open(WELCOME_IMAGE, "rb") as photo:
            await bot.send_photo(chat_id, photo, caption=caption, reply_markup=main_menu())
    except Exception:
        await bot.send_message(chat_id, caption, reply_markup=main_menu())


# ---------- Bot handlers ----------

@bot.on_message()
async def handle_message(message):
    # Send /myid to get your chat id (needed for OWNER_ID)
    if (message.text or "").strip() == "/myid":
        await bot.send_message(message.chat.id, f"Your chat id: {message.chat.id}")
        return
    await send_welcome(message.chat.id)


@bot.on_callback_query()
async def handle_buttons(callback_query):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    products = load_products()

    if data == "home":
        await send_welcome(chat_id)
        return

    if data.startswith("cat:"):
        gender = data.split(":")[1]
        items = products.get(gender, [])
        if not items:
            await bot.send_message(chat_id, "فعلا محصولی برای این دسته ثبت نشده.", reply_markup=back_menu())
            return
        title = "💙 جوراب‌های مردانه" if gender == "male" else "💖 جوراب‌های زنانه"
        await bot.send_message(chat_id, f"{title}\nیکی رو انتخاب کن:", reply_markup=product_menu(gender, items))
        return

    if data.startswith("buy:"):
        _, gender, idx = data.split(":")
        items = products.get(gender, [])
        try:
            chosen = items[int(idx)]
        except (ValueError, IndexError):
            await bot.send_message(chat_id, "این محصول پیدا نشد.", reply_markup=back_menu())
            return
        await bot.send_message(
            chat_id,
            f"🧦 انتخاب شما: {chosen['name']} - {chosen['price']} تومان\n"
            "✅ سفارش شما ثبت شد! به زودی باهاتون تماس می‌گیریم.",
            reply_markup=back_menu(),
        )
        return


bot.run()
