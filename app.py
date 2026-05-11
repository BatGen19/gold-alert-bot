from flask import Flask, request
import requests
import os
import anthropic
import json

app = Flask(__name__)

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
CLAUDE_API_KEY   = os.environ.get("CLAUDE_API_KEY")

# ══════════════════════════════════════════
# TELEGRAM
# ══════════════════════════════════════════
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

# ══════════════════════════════════════════
# PROMPT — FIXED REPORT
# ══════════════════════════════════════════
def get_fixed_prompt(data, label):
    th_time = data.get("thai_time", "N/A")

    label_map = {
        "06:00_MORNING": "🌅 Morning Bias — เปิดวัน",
        "09:00_LONDON":  "⚡ London Open",
        "14:00_NY":      "🔥 NY Open",
        "23:00_NIGHT":   "🌙 Night Summary"
    }
    title = label_map.get(label, label)

    structs = ""
    for name, key in [("H4","h4"),("H1","h1"),("M15","m15"),("M5","m5"),("M1","m1")]:
        structs += (f"\n{name}: Trend={data.get(f'{key}_trend')} | "
                    f"Event={data.get(f'{key}_event')} | "
                    f"Ind={data.get(f'{key}_ind')} | "
                    f"Close={data.get(f'{key}_close')} | "
                    f"ATR={data.get(f'{key}_atr')}")

    return f"""คุณคือ SMC Analyst วิเคราะห์ทองคำ XAUUSD เน้น Price Structure

===== MARKET UPDATE {th_time} =====
{structs}

ตอบในรูปแบบนี้:

━━━━━━━━━━━━━━━━━━━━━
{title}
⏰ เวลาไทย {th_time}
━━━━━━━━━━━━━━━━━━━━━

📊 MARKET STRUCTURE
H4 : [Trend + Event + ความหมาย]
H1 : [Trend + Event + ความหมาย]
M15: [Trend + Event + ความหมาย]
M5 : [Trend + Event + ความหมาย]
M1 : [Trend + Event + ความหมาย]

🎯 OVERALL BIAS
[Bull / Bear / Mixed]
[เหตุผล 2 บรรทัด อิงโครงสร้างเป็นหลัก]

📍 ZONES TO WATCH
[โซนหรือระดับที่น่าจับตา]

⚠️ CAUTION
[ข้อควรระวังสำหรับช่วงเวลานี้]
━━━━━━━━━━━━━━━━━━━━━"""

# ══════════════════════════════════════════
# PROMPT — OPPORTUNITY ALERT
# ══════════════════════════════════════════
def get_opportunity_prompt(data):
    th_time   = data.get("thai_time", "N/A")
    direction = data.get("direction", "UNKNOWN")
    remaining = data.get("opp_remaining", 0)
    m1_close  = data.get("m1_close", "N/A")
    dir_label = "🟢 BUY" if direction == "BULL" else "🔴 SELL"

    structs = ""
    for name, key in [("H4","h4"),("H1","h1"),("M15","m15"),("M5","m5"),("M1","m1")]:
        structs += (f"\n{name}: Trend={data.get(f'{key}_trend')} | "
                    f"Event={data.get(f'{key}_event')} | "
                    f"Ind={data.get(f'{key}_ind')} | "
                    f"Close={data.get(f'{key}_close')} | "
                    f"ATR={data.get(f'{key}_atr')}")

    return f"""คุณคือ Professional SMC Trader เทรดทองคำ XAUUSD
เน้น Price Structure เป็นหลัก Indicator เป็นแค่ context
เน้น Winrate สูง RR อย่างน้อย 1:2

===== OPPORTUNITY DETECTED =====
Direction : {direction}
Time      : {th_time} (Thai)
Remaining : {remaining}/3 alerts today

===== STRUCTURE DATA =====
{structs}

วิเคราะห์เชิงลึกและตอบในรูปแบบนี้:

━━━━━━━━━━━━━━━━━━━━━
⚡ SETUP ALERT — {dir_label}
⏰ เวลาไทย {th_time}
━━━━━━━━━━━━━━━━━━━━━

🏗 STRUCTURE ANALYSIS
H4 : [Bias ใหญ่]
H1 : [Trend + ยืนยัน Bias]
M15: [CHoCH/BOS ที่เห็น + ความหมาย]
M5 : [ยืนยันโครงสร้าง]
M1 : [Entry Signal]

📐 CONFLUENCE
✅ [จุดที่สอดคล้องกัน]
❌ [จุดที่ยังไม่ชัดหรือต้องระวัง]

━━━━━━━━━━━━━━━━━━━━━
{dir_label} SETUP
Entry  : {m1_close} (แนะนำ)
SL     : [อิง M5/M15 Structure] ([X] pips)
TP1    : [ราคา] → RR 1:1
TP2    : [ราคา] → RR 1:2
TP3    : [ราคา] → RR 1:3
━━━━━━━━━━━━━━━━━━━━━
💡 [สรุป 2 บรรทัด]
⚠️ [ความเสี่ยงที่ต้องระวัง]
🎯 Confidence: [High/Medium/Low] — [เหตุผล]"""

# ══════════════════════════════════════════
# CLAUDE
# ══════════════════════════════════════════
def analyze_with_claude(prompt):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

# ══════════════════════════════════════════
# WEBHOOK
# ══════════════════════════════════════════
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.get_data(as_text=True)
        try:
            data = json.loads(raw)
        except:
            send_telegram(f"⚠️ JSON Parse Error:\n{raw[:500]}")
            return "OK", 200

        alert_type = data.get("alert_type", "UNKNOWN")

        if alert_type == "FIXED":
            label  = data.get("label", "UPDATE")
            prompt = get_fixed_prompt(data, label)
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
