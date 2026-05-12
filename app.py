from flask import Flask, request
import requests
import os
import anthropic
import json

app = Flask(__name__)

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
CLAUDE_API_KEY   = os.environ.get("CLAUDE_API_KEY")

# ══════════════════════════════
# TELEGRAM
# ══════════════════════════════
def send_telegram(message):
    token = TELEGRAM_TOKEN
    if not token.startswith("bot"):
        token = "bot" + token
    url = f"https://api.telegram.org/{token}/sendMessage"
    if len(message) > 4096:
        for i in range(0, len(message), 4096):
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message[i:i+4096]})
    else:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})

# ══════════════════════════════
# HELPER
# ══════════════════════════════
def struct_lines(data):
    lines = []
    for name, key in [("H4","h4"),("H1","h1"),("M15","m15"),("M5","m5"),("M1","m1")]:
        lines.append(
            f"{name}: {data.get(f'{key}_trend','?')} | "
            f"{data.get(f'{key}_event','?')} | "
            f"RSI:{data.get(f'{key}_rsi','?')} | "
            f"ATR:{data.get(f'{key}_atr','?')}"
        )
    return "\n".join(lines)

def run_label(data):
    return (
        f"Long Run  → Bull {data.get('lr_bull_pct')}% / Bear {data.get('lr_bear_pct')}%  (H1+M15 Structure)\n"
        f"Short Run → Bull {data.get('sr_bull_pct')}% / Bear {data.get('sr_bear_pct')}%  (M1+M5 Structure)"
    )

def context_line(data):
    return (
        f"Zone: {data.get('zone')} ({data.get('zone_pct')}%) | "
        f"FVG: {data.get('fvg')} | "
        f"EQH: {data.get('eqh')} | "
        f"EQL: {data.get('eql')}"
    )

# ══════════════════════════════
# FIXED PROMPT
# ══════════════════════════════
def get_fixed_prompt(data, label):
    th_time = data.get("thai_time","N/A")
    title_map = {
        "06:00_MORNING": "🌅 Morning Bias",
        "09:00_LONDON":  "⚡ London Open",
        "14:00_NY":      "🔥 NY Open",
        "23:00_NIGHT":   "🌙 Night Summary"
    }
    title = title_map.get(label, label)

    return f"""คุณคือ SMC Analyst วิเคราะห์ XAUUSD กระชับ ตรงประเด็น

STRUCTURE:
{struct_lines(data)}

{run_label(data)}
{context_line(data)}

ตอบในรูปแบบนี้:

━━━━━━━━━━━━━━━━━━
{title} | {th_time}
━━━━━━━━━━━━━━━━━━
📊 STRUCTURE
H4 : [1 บรรทัด]
H1 : [1 บรรทัด]
M15: [1 บรรทัด]

📈 Long Run  Bull {data.get('lr_bull_pct')}% / Bear {data.get('lr_bear_pct')}%
📉 Short Run Bull {data.get('sr_bull_pct')}% / Bear {data.get('sr_bear_pct')}%

🎯 BIAS: [BULL / BEAR / MIXED]
[เหตุผล 1-2 บรรทัด]

📍 จับตา: [Zone/Level]
⚠️ ระวัง: [1 บรรทัด]
━━━━━━━━━━━━━━━━━━"""

# ══════════════════════════════
# OPPORTUNITY PROMPT
# ══════════════════════════════
def get_opportunity_prompt(data):
    th_time   = data.get("thai_time","N/A")
    direction = data.get("direction","?")
    remaining = data.get("opp_remaining", 0)
    m1_close  = data.get("m1_close","N/A")
    m1_atr    = data.get("m1_atr", 1)
    dir_label = "🟢 BUY" if direction == "BULL" else "🔴 SELL"

    # Entry wait condition
    if direction == "BULL":
        wait = (
            "1. รอ M1 CHoCH หรือ BOS ขึ้น\n"
            "2. candle ปิดเหนือ swing high + wick ล่างยาว\n"
            "3. MACD M1 ตัดขึ้น หรือ RSI M1 > 50"
        )
    else:
        wait = (
            "1. รอ M1 CHoCH หรือ BOS ลง\n"
            "2. candle ปิดใต้ swing low + wick บนยาว\n"
            "3. MACD M1 ตัดลง หรือ RSI M1 < 50"
        )

    try:
        atr_val = float(m1_atr)
        sl_pips = round(atr_val * 1.5, 2)
        tp1     = round(sl_pips * 1, 2)
        tp2     = round(sl_pips * 2, 2)
        tp3     = round(sl_pips * 3, 2)
    except:
        sl_pips = tp1 = tp2 = tp3 = "N/A"

    return f"""คุณคือ SMC Trader วิเคราะห์ XAUUSD เน้น Winrate สูง RR 1:2+

DIRECTION: {direction} | TIME: {th_time} | Remaining: {remaining}/3

STRUCTURE:
{struct_lines(data)}

{run_label(data)}
{context_line(data)}
M1 Price: {m1_close} | ATR: {m1_atr}

ตอบในรูปแบบนี้:

━━━━━━━━━━━━━━━━━━
⚡ {dir_label} SETUP | {th_time}
━━━━━━━━━━━━━━━━━━
📊 CONFLUENCE
H4+H1 : [Bias ชัดเจนไหม + เหตุผล]
M15   : [Structure ยืนยันไหม]
Zone  : {data.get('zone')} | FVG: {data.get('fvg')}

📈 Long Run  Bull {data.get('lr_bull_pct')}% / Bear {data.get('lr_bear_pct')}%
📉 Short Run Bull {data.get('sr_bull_pct')}% / Bear {data.get('sr_bear_pct')}%

⏳ รอก่อนเข้า:
{wait}
[เพิ่มเงื่อนไขเฉพาะจาก structure ที่เห็น]

━━━━━━━━━━━━━━━━━━
{dir_label}
Entry : {m1_close}
SL    : ~{sl_pips} pips (อิง ATR x1.5)
TP1   : ~{tp1} pips → RR 1:1
TP2   : ~{tp2} pips → RR 1:2
TP3   : ~{tp3} pips → RR 1:3
━━━━━━━━━━━━━━━━━━
💡 [สรุป 1-2 บรรทัด]
⚠️ [ความเสี่ยง 1 บรรทัด]
🎯 Confidence: [High/Medium/Low]"""

# ══════════════════════════════
# CLAUDE
# ══════════════════════════════
def analyze_with_claude(prompt):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

# ══════════════════════════════
# WEBHOOK
# ══════════════════════════════
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.get_data(as_text=True)
        try:
            data = json.loads(raw)
        except:
            send_telegram(f"⚠️ Parse Error:\n{raw[:300]}")
            return "OK", 200

        alert_type = data.get("alert_type","UNKNOWN")

        if alert_type == "FIXED":
            prompt = get_fixed_prompt(data, data.get("label","UPDATE"))
        elif alert_type == "OPPORTUNITY":
            prompt = get_opportunity_prompt(data)
        else:
            send_telegram(f"⚠️ Unknown alert_type: {alert_type}")
            return "OK", 200

        analysis = analyze_with_claude(prompt)
        send_telegram(analysis)

    except Exception as e:
        print(f"Error: {str(e)}")
        send_telegram(f"❌ Error: {str(e)}")

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
