from flask import Flask, request
import requests
import os
import anthropic
import json
import time

app = Flask(__name__)

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
CLAUDE_API_KEY   = os.environ.get("CLAUDE_API_KEY")

_last_sent = {}

def is_duplicate(key, cooldown_sec=300):
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
# ASCII CHART GENERATOR
# ══════════════════════════════
def ascii_chart(data):
    try:
        m5_res   = float(data.get("m5_res", 0))
        m5_sup   = float(data.get("m5_sup", 0))
        m1_res   = float(data.get("m1_res", 0))
        m1_sup   = float(data.get("m1_sup", 0))
        price    = float(data.get("m1_close", 0))
        m5_pat   = data.get("m5_pat", "NONE")
        m1_pat   = data.get("m1_pat", "NONE")
        m5_tl    = data.get("m5_tl", "MIXED")
        m1_tl    = data.get("m1_tl", "MIXED")

        if m5_res == 0 or m5_sup == 0 or price == 0:
            return ""

        top = max(m5_res, m1_res, price) + 1
        bot = min(m5_sup, m1_sup, price) - 1
        rng = top - bot
        if rng <= 0:
            return ""

        rows = 7
        step = rng / rows
        lines = ["📐 KEY LEVELS"]

        for i in range(rows + 1):
            lvl = top - i * step
            bar = "──────"
            tag = ""
            if abs(lvl - m5_res) < step * 0.5:
                bar = "━━━━━━"
                tag = "◀ RES(M5)"
            elif abs(lvl - m5_sup) < step * 0.5:
                bar = "━━━━━━"
                tag = "◀ SUP(M5)"
            elif abs(lvl - m1_res) < step * 0.5:
                bar = "┄┄┄┄┄┄"
                tag = "◀ res(M1)"
            elif abs(lvl - m1_sup) < step * 0.5:
                bar = "┄┄┄┄┄┄"
                tag = "◀ sup(M1)"
            if abs(lvl - price) < step * 0.6:
                tag = "◄ NOW " + tag
            lines.append(f"{round(lvl,1):>8} {bar}{tag}")

        tl_m5 = "↗" if m5_tl == "UP" else "↘" if m5_tl == "DOWN" else "↔"
        tl_m1 = "↗" if m1_tl == "UP" else "↘" if m1_tl == "DOWN" else "↔"
        lines.append(f"TL M5:{tl_m5} M1:{tl_m1}")
        if m5_pat != "NONE":
            pat_map = {
                "DBL_TOP":"Double Top 🔴","DBL_BOT":"Double Bottom 🟢",
                "ASC_TRI":"Ascending Triangle ↗","DESC_TRI":"Descending Triangle ↘",
                "SYM_TRI":"Symmetrical Triangle ↔","RISE_CH":"Rising Channel 📈",
                "FALL_CH":"Falling Channel 📉"
            }
            lines.append(f"Pattern M5: {pat_map.get(m5_pat, m5_pat)}")
        if m1_pat != "NONE":
            pat_map = {
                "DBL_TOP":"Double Top 🔴","DBL_BOT":"Double Bottom 🟢",
                "ASC_TRI":"Ascending Triangle ↗","DESC_TRI":"Descending Triangle ↘",
                "SYM_TRI":"Symmetrical Triangle ↔","RISE_CH":"Rising Channel 📈",
                "FALL_CH":"Falling Channel 📉"
            }
            lines.append(f"Pattern M1: {pat_map.get(m1_pat, m1_pat)}")
        return "\n".join(lines)
    except:
        return ""

# ══════════════════════════════
# HELPERS
# ══════════════════════════════
def ev_line(name, tr, ev, evv, rsi, atr=""):
    valid = f"[{evv}]" if evv not in ("N/A","") else ""
    atr_s = f" ATR:{atr}" if atr else ""
    return f"{name}: {tr} | {ev}{valid} RSI:{rsi}{atr_s}"

def run_lines(data):
    return (
        f"LR → Bull {data.get('lr_bull')}% Bear {data.get('lr_bear')}% (H1+M15)\n"
        f"SR → Bull {data.get('sr_bull')}% Bear {data.get('sr_bear')}% (M1+M5)"
    )

def ctx_line(data):
    return (
        f"Zone:{data.get('zone')}({data.get('zone_pct')}%) "
        f"FVG:{data.get('fvg')} "
        f"EQH:{data.get('eqh')} EQL:{data.get('eql')}"
    )

def struct_block(data):
    lines = [
        ev_line("H4",  data.get("h4_tr"),  data.get("h4_ev"),  "N/A",         data.get("h4_rsi")),
        ev_line("H1",  data.get("h1_tr"),  data.get("h1_ev"),  data.get("h1_evv"),  data.get("h1_rsi"),  data.get("h1_atr")),
        ev_line("M15", data.get("m15_tr"), data.get("m15_ev"), data.get("m15_evv"), data.get("m15_rsi"), data.get("m15_atr")),
        ev_line("M5",  data.get("m5_tr"),  data.get("m5_ev"),  data.get("m5_evv"),  data.get("m5_rsi"),  data.get("m5_atr")),
        ev_line("M1",  data.get("m1_tr"),  data.get("m1_ev"),  data.get("m1_evv"),  data.get("m1_rsi"),  data.get("m1_atr")),
    ]
    return "\n".join(lines)

# ══════════════════════════════
# FIXED PROMPT
# ══════════════════════════════
def get_fixed_prompt(data, label):
    th   = data.get("thai_time","N/A")
    title_map = {
        "06:00_MORNING": "🌅 Morning Bias",
        "09:00_LONDON":  "⚡ London Open",
        "14:00_NY":      "🔥 NY Open",
        "23:00_NIGHT":   "🌙 Night Summary"
    }
    title = title_map.get(label, label)
    chart = ascii_chart(data)

    return f"""คุณคือ SMC Analyst วิเคราะห์ XAUUSD กระชับ ตรงประเด็น

STRUCTURE:
{struct_block(data)}
{run_lines(data)}
{ctx_line(data)}

{chart}

ตอบในรูปแบบนี้:

━━━━━━━━━━━━━━━━━━
{title} | {th}
━━━━━━━━━━━━━━━━━━
📊 STRUCTURE
H4 : [1 บรรทัด — Bias หลัก]
H1 : [1 บรรทัด — BOS/CHoCH + REAL/FAKE]
M15: [1 บรรทัด — Structure]
M5 : [1 บรรทัด — Pattern ถ้ามี]
M1 : [1 บรรทัด — M1 Trend]

📈 LR Bull {data.get('lr_bull')}% / Bear {data.get('lr_bear')}%
📉 SR Bull {data.get('sr_bull')}% / Bear {data.get('sr_bear')}%

🎯 BIAS: [BULL/BEAR/MIXED + เหตุผล 1 บรรทัด]
📍 จับตา: [Zone/Level ที่สำคัญ]
⚠️ ระวัง: [1 บรรทัด]
━━━━━━━━━━━━━━━━━━"""

# ══════════════════════════════
# OPPORTUNITY PROMPT
# ══════════════════════════════
def get_opportunity_prompt(data):
    th        = data.get("thai_time","N/A")
    direction = data.get("dir","?")
    conf      = data.get("conf","MEDIUM")
    remaining = data.get("opp_rem", 0)
    m1_close  = data.get("m1_close","N/A")
    m1_atr    = data.get("m1_atr", 1)
    m5_evv    = data.get("m5_evv","N/A")
    m1_evv    = data.get("m1_evv","N/A")
    dir_e     = "🟢 BUY" if direction == "BULL" else "🔴 SELL"
    conf_e    = "🔥 HIGH" if conf == "HIGH" else "⚡ MEDIUM"
    chart     = ascii_chart(data)

    try:
        atr_val = float(m1_atr)
        sl_p    = round(atr_val * 1.5, 2)
        tp1     = round(sl_p * 1.0, 2)
        tp2     = round(sl_p * 2.0, 2)
        tp3     = round(sl_p * 3.0, 2)
    except:
        sl_p = tp1 = tp2 = tp3 = "N/A"

    if direction == "BULL":
        wait = (
            "① M1 CHoCH/BOS ขึ้น + candle ปิดเหนือ swing high\n"
            "② wick ล่างยาว rejection ที่ SUP หรือ FVG\n"
            "③ M1 RSI > 50 หรือ MACD ตัดขึ้น"
        )
    else:
        wait = (
            "① M1 CHoCH/BOS ลง + candle ปิดใต้ swing low\n"
            "② wick บนยาว rejection ที่ RES\n"
            "③ M1 RSI < 50 หรือ MACD ตัดลง"
        )

    return f"""คุณคือ SMC Trader วิเคราะห์ XAUUSD เน้นเทรด M1/M5 Winrate สูง RR 1:2+

DIRECTION:{direction} CONF:{conf} TIME:{th} Rem:{remaining}/3
M5 Event Valid:{m5_evv} | M1 Event Valid:{m1_evv}

STRUCTURE:
{struct_block(data)}
{run_lines(data)}
{ctx_line(data)}

{chart}

ตอบในรูปแบบนี้:

━━━━━━━━━━━━━━━━━━
{dir_e} {conf_e} | {th}
━━━━━━━━━━━━━━━━━━
📊 CONFLUENCE
H4+H1 : [Bias + BOS/CHoCH REAL/FAKE]
M15   : [Structure confirm?]
M5    : [Pattern + Event valid?]
M1    : [Entry signal + Vol]

📈 LR {data.get('lr_bull')}%Bull / SR {data.get('sr_bull')}%Bull

⏳ รอเข้า:
{wait}

━━━━━━━━━━━━━━━━━━
{dir_e}
Entry : {m1_close}
SL    : ~{sl_p} pips (ATR×1.5)
TP1   : ~{tp1} pips → 1:1
TP2   : ~{tp2} pips → 1:2
TP3   : ~{tp3} pips → 1:3
━━━━━━━━━━━━━━━━━━
💡 [สรุป 2 บรรทัด]
⚠️ [ความเสี่ยง 1 บรรทัด]
🎯 Confidence: {conf}"""

# ══════════════════════════════
# CLAUDE
# ══════════════════════════════
def analyze_with_claude(prompt):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        messages=[{"role":"user","content":prompt}]
    )
    return msg.content[0].text

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

        alert_type = data.get("type","UNKNOWN")

        if alert_type == "FIXED":
            label     = data.get("label","UPDATE")
            dedup_key = f"FIXED_{label}"
            if is_duplicate(dedup_key, 300):
                return "OK", 200
            prompt = get_fixed_prompt(data, label)

        elif alert_type == "OPP":
            direction = data.get("dir","?")
            th_time   = data.get("thai_time","0:00")
            dedup_key = f"OPP_{direction}_{th_time}"
            if is_duplicate(dedup_key, 120):
                return "OK", 200
            prompt = get_opportunity_prompt(data)

        else:
            send_telegram(f"⚠️ Unknown type: {alert_type}")
            return "OK", 200

        analysis = analyze_with_claude(prompt)
        send_telegram(analysis)

    except Exception as e:
        print(f"Error: {str(e)}")
        send_telegram(f"❌ Error: {str(e)}")

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
