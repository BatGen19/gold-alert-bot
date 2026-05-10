from flask import Flask, request
import requests
import os
import anthropic
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
RSI14: {data.get('m15_rsi')} | ATR14: {data.get('m15_atr')} | Volume: {data.get('m15_volume')}
Prev 3 Candles High: {data.get('m15_prev3_high')} | Low: {data.get('m15_prev3_low')}

📊 M5 (Setup):
OHLC: {data.get('m5_open')} | {data.get('m5_high')} | {data.get('m5_low')} | {data.get('m5_close')}
EMA20: {data.get('m5_ema20')} | EMA50: {data.get('m5_ema50')}
RSI14: {data.get('m5_rsi')} | ATR14: {data.get('m5_atr')} | Volume: {data.get('m5_volume')}
Prev 3 Candles High: {data.get('m5_prev3_high')} | Low: {data.get('m5_prev3_low')}

📊 M1 (Entry):
OHLC: {data.get('m1_open')} | {data.get('m1_high')} | {data.get('m1_low')} | {data.get('m1_close')}
RSI14: {data.get('m1_rsi')} | ATR14: {data.get('m1_atr')} | Volume: {data.get('m1_volume')}
Body Size: {data.get('m1_body')} | Upper Wick: {data.get('m1_upper_wick')} | Lower Wick: {data.get('m1_lower_wick')}

===== KEY LEVELS =====
Weekly High: {data.get('weekly_high')} | Weekly Low: {data.get('weekly_low')}
Daily High: {data.get('daily_high')} | Daily Low: {data.get('daily_low')}
Previous Day High: {data.get('prev_day_high')} | Previous Day Low: {data.get('prev_day_low')}
Resistance: {data.get('resistance')} | Support: {data.get('support')}

Pivot Points (Daily):
PP: {data.get('pivot')}
R1: {data.get('r1')} | R2: {data.get('r2')} | R3: {data.get('r3')}
S1: {data.get('s1')} | S2: {data.get('s2')} | S3: {data.get('s3')}

Fibonacci:
0.236: {data.get('fib_236')} | 0.382: {data.get('fib_382')} | 0.500: {data.get('fib_500')}
0.618: {data.get('fib_618')} | 0.786: {data.get('fib_786')}

===== วิเคราะห์ครอบคลุมทุกหัวข้อ =====

1. SESSION BIAS
- Session นี้เหมาะเทรดไหม
- Smart Money มักทำอะไรใน session นี้กับทอง

2. MARKET STRUCTURE (M15 → M5 → M1)
- แนวโน้มหลัก Bullish/Bearish/Sideways
- BOS หรือ CHoCH เกิดที่ระดับไหน
- HH/HL หรือ LH/LL
- Structure shift มีไหม

3. SMC / ICT ANALYSIS
- Supply Zone (SZ) ที่แข็งแกร่ง
- Demand Zone (DZ) ที่แข็งแกร่ง  
- Fair Value Gap (FVG) ที่ยังไม่ถูก fill
- Order Block (OB) Bullish/Bearish
- Breaker Block มีไหม
- Liquidity Pool (Buy-side/Sell-side) อยู่ที่ไหน
- Equal Highs/Lows (EQH/EQL) มีไหม
- Imbalance / Gap มีไหม

4. PRICE ACTION & PATTERNS
- รูปแบบแท่งเทียนปัจจุบัน (Engulfing, Pin Bar, Doji, Hammer, Shooting Star, Inside Bar, Marubozu)
- Chart Pattern (Double Top/Bottom, H&S, Wedge, Triangle, Flag, Channel)
- Trendline Break มีไหม
- Wick Rejection แข็งแค่ไหน

5. FIBONACCI CONFLUENCE
- ราคาอยู่ใกล้ Fib level ไหน
- Golden Zone (0.618-0.786) มี confluence กับ OB หรือ FVG ไหม
- Extension targets ที่ไหน

6. INDICATORS CONFLUENCE
- EMA alignment (20/50/200) บอกอะไร
- RSI: Overbought/Oversold/Divergence
- ATR: ความผันผวนเหมาะเทรดไหม
- Volume: Spike หรือ Dry

7. KILL ZONES & TIMING
- อยู่ใน Kill Zone ไหม (London Open 07-09, NY Open 12-14 UTC)
- ควรรอ Kill Zone ไหม

8. ENTRY DECISION
- เทรดหรือ NO TRADE พร้อมเหตุผล
- Confluence score (กี่ปัจจัยที่ตรงกัน)
- BUY หรือ SELL
- Entry zone ที่แม่นยำ
- SL อิง Structure + ATR
- TP1 (1:1), TP2 (1:2), TP3 (1:3+)
- Position size recommendation (ความเสี่ยง)

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
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # แบ่งข้อความถ้ายาวเกิน 4096 ตัวอักษร
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
    data = request.json
    analysis = analyze_with_claude(data)
    send_telegram(analysis)
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
