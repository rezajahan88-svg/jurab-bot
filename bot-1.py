from balethon import Client
from balethon.objects import InlineKeyboard
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Token is read from an environment variable (set it on Render, not in the code)
bot = Client(os.environ["BOT_TOKEN"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_FILE = os.path.join(BASE_DIR, "products.json")
WELCOME_IMAGE = os.path.join(BASE_DIR, "welcome.jpg")


def load_products():
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# Tiny web page so Render's free plan stays happy
class Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def run_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Ping).serve_forever()


threading.Thread(target=run_server, daemon=True).start()


# ---------- Keyboards ----------

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


# ---------- Screens ----------

async def send_welcome(chat_id):
    caption = "سلام! به فروشگاه جوراب خوش اومدی 🧦✨\nلطفا یکی از دسته‌ها رو انتخاب کن:"
    try:
        with open(WELCOME_IMAGE, "rb") as photo:
            await bot.send_photo(chat_id, photo, caption=caption, reply_markup=main_menu())
    except Exception:
        # If the image can't be sent for any reason, still show the menu
        await bot.send_message(chat_id, caption, reply_markup=main_menu())


# ---------- Handlers ----------

# Any message the user types just brings back the welcome picture + buttons
@bot.on_message()
async def handle_message(message):
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
        await bot.send_message(
            chat_id,
            f"{title}\nیکی رو انتخاب کن:",
            reply_markup=product_menu(gender, items),
        )
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
