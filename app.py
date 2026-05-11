from flask import Flask, request
import requests
import os
import anthropic
import json
from datetime import datetime

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")

def get_session():
    hour = datetime.utcnow().hour
    if 2 <= hour < 5:
        return "London Kill Zone ⚡ (09:00-12:00 ไทย)"
    elif 7 <= hour < 10:
        return "NY Kill Zone 🔥 (14:00-17:00 ไทย)"
    elif 0 <= hour < 7:
        return "Asia Session (ตลาดเงียบ)"
    else:
        return "Between Sessions"

def analyze_with_claude(data):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    session = get_session()
    signal = data.get('signal', 'NONE')
    h1_bias = data.get('h1_bias', 'UNKNOWN')

    prompt = f"""คุณคือ Professional XAUUSD Trader ที่ใช้ MMTC Setup วิเคราะห์ทองคำ
เน้น Winrate สูง RR 1:2 ขึ้นไป เทรด M1/M5 วิเคราะห์จาก H1/M15

===== SIGNAL DETECTED =====
Signal: {signal}
Session: {session}
H1 Bias: {h1_bias}
Time UTC: {datetime.utcnow().strftime('%H:%M')}

===== H1 DATA (Bias) =====
Close: {data.get('h1_close')} | EMA200: {data.get('h1_ema200')}
MACD Line: {data.get('h1_macd_line')} | Signal: {data.get('h1_macd_signal')}
Swing High: {data.get('h1_swing_high')} | Swing Low: {data.get('h1_swing_low')}

===== M15 DATA (Structure) =====
OHLC: {data.get('m15_open')} | {data.get('m15_high')} | {data.get('m15_low')} | {data.get('m15_close')}
EMA20: {data.get('m15_ema20')} | EMA50: {data.get('m15_ema50')} | EMA200: {data.get('m15_ema200')}
RSI: {data.get('m15_rsi')} | ATR: {data.get('m15_atr')}
MACD Line: {data.get('m15_macd_line')} | Signal: {data.get('m15_macd_signal')}
Swing High: {data.get('m15_swing_high')} | Swing Low: {data.get('m15_swing_low')}
Prev High: {data.get('m15_prev_high')} | Prev Low: {data.get('m15_prev_low')}

===== M5 DATA (Confirmation) =====
OHLC: {data.get('m5_open')} | {data.get('m5_high')} | {data.get('m5_low')} | {data.get('m5_close')}
EMA20: {data.get('m5_ema20')} | EMA50: {data.get('m5_ema50')}
RSI: {data.get('m5_rsi')} | ATR: {data.get('m5_atr')}
MACD Line: {data.get('m5_macd_line')} | Signal: {data.get('m5_macd_signal')}
Swing High: {data.get('m5_swing_high')} | Swing Low: {data.get('m5_swing_low')}

===== M1 DATA (Entry) =====
OHLC: {data.get('m1_open')} | {data.get('m1_high')} | {data.get('m1_low')} | {data.get('m1_close')}
RSI: {data.get('m1_rsi')} | ATR: {data.get('m1_atr')}
Body: {data.get('m1_body')} | Upper Wick: {data.get('m1_upper_wick')} | Lower Wick: {data.get('m1_lower_wick')}
MACD Line: {data.get('m1_macd_line')} | Signal: {data.get('m1_macd_signal')}

===== KEY LEVELS =====
Weekly High: {data.get('weekly_high')} | Weekly Low: {data.get('weekly_low')}
Daily High: {data.get('daily_high')} | Daily Low: {data.get('daily_low')}
Prev Day High: {data.get('prev_day_high')} | Prev Day Low: {data.get('prev_day_low')}
Pivot: {data.get('pivot')} | R1: {data.get('r1')} | R2: {data.get('r2')}
S1: {data.get('s1')} | S2: {data.get('s2')}
Fib 0.382: {data.get('fib_382')} | Fib 0.500: {data.get('fib_500')}
Fib 0.618: {data.get('fib_618')} | Fib 0.786: {data.get('fib_786')}

===== MMTC ANALYSIS =====
วิเคราะห์ตาม MMTC Setup ครบ 5 ขั้น:

1. H1 BIAS
- BOS เกิดทางไหน? ราคาอยู่เหนือ/ใต้ EMA200?
- MACD H1 ยืนยัน Bias ไหม?
- Bias ชัดเจนแค่ไหน? (Strong/Weak)

2. M15 STRUCTURE
- CHoCH เกิดไหม? ที่ระดับไหน?
- BOS M15 ยืนยันไหม?
- OB หรือ DZ/SZ น่าสนใจอยู่ที่ไหน?
- MACD M15 สอดคล้องกับ Bias ไหม?

3. LOCATION — ราคาอยู่ตรงไหน?
- อยู่ใน Discount (Buy) หรือ Premium Zone (Sell)?
- ใกล้ Fibo 50-61.8% ไหม?
- Liquidity ถูก Sweep แล้วหรือยัง?
- อยู่ใกล้ Key Level ไหน (PDH/PDL/Pivot/Weekly)?

4. M5 CONFIRMATION
- MACD M5 ตัดขึ้น/ลงไหม?
- BOS M5 เกิดไหม?
- RSI M5 เหมาะเข้าไหม? (ไม่ Extreme)

5. M1 ENTRY
- แท่งเทียน M1 บอกอะไร? (Rejection/Inside Bar/Engulfing)
- Wick บอกอะไร?
- MACD M1 ยืนยันไหม?

6. TRADE PLAN
- เข้าหรือ NO TRADE? เหตุผล?
- Entry ที่แม่นยำที่สุด
- SL อิง Structure (ใต้/เหนือ OB หรือ Swing)
- TP1 (RR 1:1), TP2 (RR 1:2), TP3 (RR 1:3)
- คำนวณ pips SL และ TP

ตอบในรูปแบบนี้:

━━━━━━━━━━━━━━━━━━
🏆 MMTC GOLD SETUP
{session}
━━━━━━━━━━━━━━━━━━
📊 H1 BIAS: {h1_bias}
[วิเคราะห์]

📐 M15 STRUCTURE
[วิเคราะห์]

📍 LOCATION
[วิเคราะห์]

✅ M5 CONFIRMATION
[วิเคราะห์]

🕯 M1 ENTRY
[วิเคราะห์]

━━━━━━━━━━━━━━━━━━
⚡ SIGNAL: [BUY / SELL / NO TRADE]
Entry  : [ราคา]
SL     : [ราคา] ([X] pips)
TP1    : [ราคา] → RR 1:1
TP2    : [ราคา] → RR 1:2
TP3    : [ราคา] → RR 1:3
━━━━━━━━━━━━━━━━━━
💡 [สรุปเหตุผล 2 บรรทัด]
⚠️ [ความเสี่ยงที่ต้องระวัง]"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

def send_telegram(message):
    token = TELEGRAM_TOKEN
    if not token.startswith("bot"):
        token = "bot" + token
    url = f"https://api.telegram.org/{token}/sendMessage"
    if len(message) > 4096:
        for i in range(0, len(message), 4096):
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message[i:i+4096]
            })
    else:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        })

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.get_data(as_text=True)
        try:
            data = json.loads(raw)
        except:
            data = {"raw": raw}
        analysis = analyze_with_claude(data)
        send_telegram(analysis)
    except Exception as e:
        print(f"Error: {str(e)}")
        send_telegram(f"❌ Error: {str(e)}")
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
