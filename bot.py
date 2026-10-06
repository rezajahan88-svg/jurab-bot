from balethon import Client
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Token is read from an environment variable (set it on Render, not in the code)
bot = Client(os.environ["BOT_TOKEN"])

PRODUCTS_FILE = "products.json"


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

user_state = {}


@bot.on_message()
async def handle_message(message):
    chat_id = message.chat.id
    text = (message.text or "").strip().lower()
    products = load_products()

    if text in ("/start", "start", "شروع"):
        user_state[chat_id] = {"step": "choose_gender"}
        await message.reply("سلام! به فروشگاه جوراب خوش اومدی 🧦\nلطفا انتخاب کن: مردانه یا زنانه؟")
        return

    state = user_state.get(chat_id, {"step": "choose_gender"})

    if state["step"] == "choose_gender":
        if "مرد" in text:
            gender = "male"
        elif "زن" in text:
            gender = "female"
        else:
            await message.reply("لطفا بنویس: مردانه یا زنانه")
            return

        items = products.get(gender, [])
        if not items:
            await message.reply("فعلا محصولی برای این دسته ثبت نشده.")
            return

        listing = "\n".join(f"{i+1}. {p['name']} - {p['price']} تومان" for i, p in enumerate(items))
        user_state[chat_id] = {"step": "choose_product", "gender": gender}
        await message.reply(f"محصولات موجود:\n{listing}\n\nلطفا شماره مورد نظر رو بفرست.")
        return

    if state["step"] == "choose_product":
        gender = state["gender"]
        items = products.get(gender, [])
        try:
            idx = int(text) - 1
            if idx < 0:
                raise IndexError
            chosen = items[idx]
        except (ValueError, IndexError):
            await message.reply("لطفا یک شماره معتبر از لیست بفرست.")
            return

        await message.reply(
            f"انتخاب شما: {chosen['name']} - {chosen['price']} تومان\nسفارش شما ثبت شد! به زودی باهاتون تماس می‌گیریم."
        )
        user_state[chat_id] = {"step": "choose_gender"}
        return


bot.run()
