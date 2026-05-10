from flask import Flask, request
import requests
import os

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    message = f"""
🟡 XAUUSD SIGNAL
Action : {data.get('action')}
Price  : {data.get('price')}
Time   : {data.get('time')}
"""
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": message}
    )
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
