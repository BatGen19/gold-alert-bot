from flask import Flask, request
import requests
import os
import anthropic
import json
import time

app = Flask(__name__)

TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
CLAUDE_API_KEY  = os.environ.get("CLAUDE_API_KEY")

_last_sent = {}

# ══════════════════════════════
# DUPLICATE GUARD
# ══════════════════════════════
def is_duplicate(key, cooldown_sec=120):
    now = time.time()
    if key in _last_sent and now - _last_sent[key] < cooldown_sec:
        return True
    _last_sent[key] = now
    return False

# ══════════════════════════════
# TELEGRAM
# ══════════════════════════════
def send_telegram(message):
    token = TELEGRAM_TOKEN.strip()
    if not token.startswith("bot"):
        token = "bot" + token
    url = f"https://api.telegram.org/{token}/sendMessage"
    if len(message) > 4096:
        for i in range(0, len(message), 4096):
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message[i:i+4096]})
    else:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})

# ══════════════════════════════
# CLAUDE AI ANALYSIS
# ══════════════════════════════
def analyze_with_claude(prompt):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text

# ══════════════════════════════
# PROMPTS
# ══════════════════════════════

def prompt_bos(data):
    direction = "🟢 BULL" if data.get("dir") == "bull" else "🔴 BEAR"
    return f"""คุณคือ SMC Analyst วิเคราะห์ XAUUSD กระชับ ตรงประเด็น

เกิด BOS (Break of Structure) {direction} บน XAUUSD
เวลา: {data.get("time","N/A")} | Timeframe: {data.get("tf","N/A")}
ราคาปัจจุบัน: {data.get("price","N/A")}
BSL: {data.get("bsl","N/A")} | SSL: {data.get("ssl","N/A")}
EQ (50%): {data.get("eq","N/A")}
Session: {data.get("session","N/A")}

ตอบในรูปแบบนี้:
━━━━━━━━━━━━━━━━━━
📊 BOS {direction} | {data.get("time","N/A")}
TF: {data.get("tf","N/A")} | Session: {data.get("session","N/A")}
━━━━━━━━━━━━━━━━━━
🔍 ความหมาย: [อธิบาย 1 บรรทัด]
🎯 Level สำคัญ: BSL {data.get("bsl","N/A")} / SSL {data.get("ssl","N/A")}
⚖️ EQ (50%): {data.get("eq","N/A")}
⏳ รอสัญญาณ: [สิ่งที่ต้องเกิดก่อนเข้าเทรด]
⚠️ Invalidate: [เงื่อนไขที่ยกเลิก setup]
━━━━━━━━━━━━━━━━━━"""

def prompt_mss(data):
    direction = "🟢 BULL" if data.get("dir") == "bull" else "🔴 BEAR"
    return f"""คุณคือ SMC Analyst วิเคราะห์ XAUUSD เน้นจุดเปลี่ยนเทรนด์

เกิด MSS (Market Structure Shift) ⚡ {direction} — สัญญาณเปลี่ยนเทรนด์!
เวลา: {data.get("time","N/A")} | Timeframe: {data.get("tf","N/A")}
ราคาปัจจุบัน: {data.get("price","N/A")}
BSL: {data.get("bsl","N/A")} | SSL: {data.get("ssl","N/A")}
EQ (50%): {data.get("eq","N/A")}
Session: {data.get("session","N/A")}

ตอบในรูปแบบนี้:
━━━━━━━━━━━━━━━━━━
⚡ MSS {direction} — เทรนด์เปลี่ยน! | {data.get("time","N/A")}
TF: {data.get("tf","N/A")} | Session: {data.get("session","N/A")}
━━━━━━━━━━━━━━━━━━
🔄 Shift จาก: [เทรนด์เดิม → เทรนด์ใหม่]
🎯 Target: [ระดับราคาเป้าหมายแรก]
📍 OB/FVG ที่น่าสนใจ: [ย่านที่ราคาอาจ Retest]
⏳ Entry Plan: [วิธีเข้าที่แม่นยำ]
⚠️ ระวัง: [Fakeout หรือความเสี่ยง]
━━━━━━━━━━━━━━━━━━"""

def prompt_fvg(data):
    direction = "🟢 Bullish" if data.get("dir") == "bull" else "🔴 Bearish"
    fvg_top = data.get("fvg_top","N/A")
    fvg_bot = data.get("fvg_bot","N/A")
    return f"""คุณคือ SMC Analyst วิเคราะห์ XAUUSD

เกิด FVG (Fair Value Gap) {direction} บน XAUUSD
เวลา: {data.get("time","N/A")} | Timeframe: {data.get("tf","N/A")}
ราคาปัจจุบัน: {data.get("price","N/A")}
Session: {data.get("session","N/A")}

⚠️ ข้อมูล FVG ZONE จากกราฟจริง (ใช้ค่านี้เท่านั้น):
FVG Bot (ขอบล่าง): {fvg_bot}
FVG Top (ขอบบน) : {fvg_top}
FVG Zone = {fvg_bot} – {fvg_top}

กฎเด็ดขาด: ห้ามใช้ราคาอื่นนอกจาก {fvg_bot} – {fvg_top} เป็น Entry Zone หรือ Fill Target

ตอบในรูปแบบนี้:
━━━━━━━━━━━━━━━━━━
📊 FVG {direction} | {data.get("time","N/A")}
Zone: {fvg_bot} – {fvg_top}
━━━━━━━━━━━━━━━━━━
🔍 ความหมาย: [ช่องว่างราคาที่เกิดจากการเคลื่อนตัวเร็ว — อธิบาย 1 บรรทัด]
🎯 Entry Zone: {fvg_bot} – {fvg_top} (รอราคากลับมา Fill)
⏳ รอสัญญาณ: [Rejection / ChoCh / Engulfing ใน Zone ก่อนเข้า]
⚠️ ระวัง: [ถ้าราคาทะลุ {fvg_bot} ลงไป = FVG ถูก Break]
━━━━━━━━━━━━━━━━━━"""

def prompt_killzone(data):
    kz_name = "🔥 London Kill Zone" if data.get("kz") == "london" else "🔥 NY Kill Zone"
    return f"""คุณคือ SMC Analyst แจ้งเตือน Kill Zone XAUUSD

{kz_name} เริ่มแล้ว!
เวลา: {data.get("time","N/A")}
ราคาปัจจุบัน: {data.get("price","N/A")}
BSL: {data.get("bsl","N/A")} | SSL: {data.get("ssl","N/A")}
Asia High: {data.get("asia_high","N/A")} | Asia Low: {data.get("asia_low","N/A")}
Session Trend: {data.get("trend","N/A")}

ตอบในรูปแบบนี้:
━━━━━━━━━━━━━━━━━━
{kz_name} | {data.get("time","N/A")}
━━━━━━━━━━━━━━━━━━
📍 Key Levels:
  Asia High: {data.get("asia_high","N/A")}
  Asia Low : {data.get("asia_low","N/A")}
  BSL      : {data.get("bsl","N/A")}
  SSL      : {data.get("ssl","N/A")}
🎯 Bias ช่วงนี้: [BULL/BEAR/WAIT — เหตุผลสั้น]
🔍 สิ่งที่จับตา: [Level หรือ Pattern ที่น่าสนใจ]
⏳ Setup ที่รอ: [สัญญาณก่อนเข้าเทรด]
━━━━━━━━━━━━━━━━━━"""

def prompt_session(data):
    sess_map = {
        "asia":   "🌏 Asia Session",
        "london": "🇬🇧 London Session",
        "ny":     "🗽 NY Session"
    }
    sess_name = sess_map.get(data.get("sess",""), "Session")
    return f"""{sess_name} เปิดแล้ว — {data.get("time","N/A")}
ราคา: {data.get("price","N/A")} | Trend: {data.get("trend","N/A")}
Asia H: {data.get("asia_high","N/A")} | Asia L: {data.get("asia_low","N/A")}
BSL: {data.get("bsl","N/A")} | SSL: {data.get("ssl","N/A")}"""

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

        alert_type = data.get("type", "UNKNOWN")
        tf    = data.get("tf", "?")
        price = data.get("price", "?")
        time_ = data.get("time", "?")

        # ── Dedup key ──
        dedup_map = {
            "BOS":      f"BOS_{data.get('dir')}_{tf}_{time_}",
            "MSS":      f"MSS_{data.get('dir')}_{tf}_{time_}",
            "FVG":      f"FVG_{data.get('dir')}_{tf}_{time_}",
            "KILLZONE": f"KZ_{data.get('kz')}_{time_}",
            "SESSION":  f"SESS_{data.get('sess')}_{time_}",
        }
        cooldown_map = {
            "BOS": 120, "MSS": 60, "FVG": 120,
            "KILLZONE": 300, "SESSION": 3600
        }

        key      = dedup_map.get(alert_type)
        cooldown = cooldown_map.get(alert_type, 120)

        if key and is_duplicate(key, cooldown):
            return "OK", 200

        # ── Route ──
        if alert_type == "BOS":
            prompt = prompt_bos(data)
            msg = analyze_with_claude(prompt)

        elif alert_type == "MSS":
            prompt = prompt_mss(data)
            msg = analyze_with_claude(prompt)

        elif alert_type == "FVG":
            prompt = prompt_fvg(data)
            msg = analyze_with_claude(prompt)

        elif alert_type == "KILLZONE":
            prompt = prompt_killzone(data)
            msg = analyze_with_claude(prompt)

        elif alert_type == "SESSION":
            # Session open — ส่งข้อความสั้น ไม่ต้องใช้ Claude
            msg = prompt_session(data)

        else:
            msg = f"⚠️ Unknown alert type: {alert_type}\n{raw[:200]}"

        send_telegram(msg)

    except Exception as e:
        print(f"Error: {str(e)}")
        send_telegram(f"❌ Error: {str(e)}")

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
