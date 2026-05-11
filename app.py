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
    if 0 <= hour < 7:
        return "Asia Session (ตลาดเงียบ)"
    elif 7 <= hour < 12:
        return "London Session (ตลาดแรง ⚡)"
    elif 12 <= hour < 17:
        return "London+NY Overlap (แรงที่สุด 🔥)"
    elif 17 <= hour < 21:
        return "NY Session (ตลาดแรง ⚡)"
    else:
        return "Late NY / Pre-Asia (ระวัง)"

def analyze_with_claude(data):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    session = get_session()

    prompt = f"""คุณคือ Professional XAUUSD Trader ระดับ Institutional ที่เชี่ยวชาญ SMC, ICT Concepts, Price Action และ Technical Analysis ระดับสูงสุด

===== SESSION =====
ตลาดตอนนี้: {session}
เวลา UTC: {datetime.utcnow().strftime('%H:%M')}

===== Multi-Timeframe Data =====

📊 M15 (แนวโน้มหลัก):
OHLC: {data.get('m15_open')} | {data.get('m15_high')} | {data.get('m15_low')} | {data.get('m15_close')}
EMA20: {data.get('m15_ema20')} | EMA50: {data.get('m15_ema50')} | EMA200: {data.get('m15_ema200')}
RSI14: {data.get('m15_rsi')} | ATR14: {data.get('m15_atr')}

📊 M5 (Setup):
OHLC: {data.get('m5_open')} | {data.get('m5_high')} | {data.get('m5_low')} | {data.get('m5_close')}
EMA20: {data.get('m5_ema20')} | EMA50: {data.get('m5_ema50')}
RSI14: {data.get('m5_rsi')} | ATR14: {data.get('m5_atr')}

📊 M1 (Entry):
OHLC: {data.get('m1_open')} | {data.get('m1_high')} | {data.get('m1_low')} | {data.get('m1_close')}
RSI14: {data.get('m1_rsi')} | ATR14: {data.get('m1_atr')}
Body: {data.get('m1_body')} | Upper Wick: {data.get('m1_upper_wick')} | Lower Wick: {data.get('m1_lower_wick')}

===== KEY LEVELS =====
Weekly High: {data.get('weekly_high')} | Weekly Low: {data.get('weekly_low')}
Daily High: {data.get('daily_high')} | Daily Low: {data.get('daily_low')}
Prev Day High: {data.get('prev_day_high')} | Prev Day Low: {data.get('prev_day_low')}
Resistance: {data.get('resistance')} | Support: {data.get('support')}
Pivot: {data.get('pivot')} | R1: {data.get('r1')} | R2: {data.get('r2')}
S1: {data.get('s1')} | S2: {data.get('s2')}
Fib 0.382: {data.get('fib_382')} | Fib 0.618: {data.get('fib_618')}

===== วิเคราะห์ =====
1. SESSION BIAS
2. MARKET STRUCTURE (M15→M5→M1)
3. SMC/ICT ZONES (SZ, DZ, FVG, OB, Liquidity)
4. PRICE ACTION & PATTERNS
5. FIBONACCI CONFLUENCE
6. INDICATORS CONFLUENCE
7. KILL ZONES & TIMING
8. ENTRY DECISION

ตอบในรูปแบบนี้:

━━━━━━━━━━━━━━━━━━━━━━
🏆 XAUUSD INSTITUTIONAL ANALYSIS
⏰ {session}
━━━━━━━━━━━━━━━━━━━━━━
🌍 SESSION BIAS
[วิเคราะห์]
📊 MARKET STRUCTURE
[วิเคราะห์]
🎯 SMC / ICT ZONES
[วิเคราะห์]
🕯 PRICE ACTION
[วิเคราะห์]
📐 FIBONACCI
[วิเคราะห์]
📈 INDICATORS
[วิเคราะห์]
⏱ TIMING
[วิเคราะห์]
━━━━━━━━━━━━━━━━━━━━━━
⚡ SIGNAL: [BUY / SELL / NO TRADE]
Entry    : [ราคา]
SL       : [ราคา] ([pips] pips)
TP1      : [ราคา] → RR 1:1
TP2      : [ราคา] → RR 1:2
TP3      : [ราคา] → RR 1:3
Confluence: [X/10 ปัจจัย]
Confidence: [%]
━━━━━━━━━━━━━━━━━━━━━━
💡 SUMMARY
[สรุปเหตุผลหลัก 3 บรรทัด]
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
    print(f"Token: {token[:20]}...")
    print(f"Chat ID: {TELEGRAM_CHAT_ID}")
    if len(message) > 4096:
        for i in range(0, len(message), 4096):
            r = requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message[i:i+4096]
            })
            print(f"Response: {r.status_code} {r.text[:200]}")
    else:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        })
        print(f"Response: {r.status_code} {r.text[:200]}")

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.get_data(as_text=True)
        print(f"Raw data: {raw[:200]}")
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
