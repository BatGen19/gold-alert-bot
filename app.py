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
# ASCII CHART
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

        # ✅ เพิ่ม SL/TP levels ใน chart
        bull_sl  = float(data.get("bull_sl", 0))
        bull_tp1 = float(data.get("bull_tp1", 0))
        bear_sl  = float(data.get("bear_sl", 0))
        bear_tp1 = float(data.get("bear_tp1", 0))

        if m5_res == 0 or m5_sup == 0 or price == 0:
            return ""

        all_levels = [x for x in [m5_res, m5_sup, m1_res, m1_sup, price,
                                   bull_sl, bull_tp1, bear_sl, bear_tp1] if x > 0]
        top = max(all_levels) + 0.5
        bot = min(all_levels) - 0.5
        rng = top - bot
        if rng <= 0:
            return ""

        rows = 9
        step = rng / rows
        lines = ["📐 KEY LEVELS"]

        for i in range(rows + 1):
            lvl = top - i * step
            bar = "──────"
            tag = ""
            if   abs(lvl - m5_res)   < step * 0.5: bar = "━━━━━━"; tag = "◀ RES(M5)"
            elif abs(lvl - m5_sup)   < step * 0.5: bar = "━━━━━━"; tag = "◀ SUP(M5)"
            elif abs(lvl - m1_res)   < step * 0.5: bar = "┄┄┄┄┄┄"; tag = "◀ res(M1)"
            elif abs(lvl - m1_sup)   < step * 0.5: bar = "┄┄┄┄┄┄"; tag = "◀ sup(M1)"
            elif abs(lvl - bull_tp1) < step * 0.5: bar = "╌╌╌╌╌╌"; tag = "◀ TP1(B)"
            elif abs(lvl - bull_sl)  < step * 0.5: bar = "╌╌╌╌╌╌"; tag = "◀ SL(B)"
            elif abs(lvl - bear_tp1) < step * 0.5: bar = "╌╌╌╌╌╌"; tag = "◀ TP1(S)"
            elif abs(lvl - bear_sl)  < step * 0.5: bar = "╌╌╌╌╌╌"; tag = "◀ SL(S)"
            if abs(lvl - price) < step * 0.6:
                tag = "◄ NOW " + tag
            lines.append(f"{round(lvl,1):>8} {bar}{tag}")

        tl_m5 = "↗" if m5_tl == "UP" else "↘" if m5_tl == "DOWN" else "↔"
        tl_m1 = "↗" if m1_tl == "UP" else "↘" if m1_tl == "DOWN" else "↔"
        lines.append(f"TL M5:{tl_m5} M1:{tl_m1}")

        pat_map = {
            "DBL_TOP":"Double Top 🔴","DBL_BOT":"Double Bottom 🟢",
            "ASC_TRI":"Ascending Triangle ↗","DESC_TRI":"Descending Triangle ↘",
            "SYM_TRI":"Symmetrical Triangle ↔","RISE_CH":"Rising Channel 📈",
            "FALL_CH":"Falling Channel 📉"
        }
        if m5_pat != "NONE":
            lines.append(f"Pattern M5: {pat_map.get(m5_pat, m5_pat)}")
        if m1_pat != "NONE":
            lines.append(f"Pattern M1: {pat_map.get(m1_pat, m1_pat)}")
        return "\n".join(lines)
    except:
        return ""

# ══════════════════════════════
# HELPERS
# ══════════════════════════════
def ev_line(name, tr, ev, evv, rsi, atr=""):
    valid = f"[{evv}]" if evv not in ("N/A", "") else ""
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
        f"EQH:{data.get('eqh')} EQL:{data.get('eql')}\n"
        f"Retest:{data.get('retest','NONE')} "
        f"Trending:{data.get('trending','?')} "
        f"Session:{data.get('session','?')}"
    )

def struct_block(data):
    lines = [
        ev_line("H4",  data.get("h4_tr"),  data.get("h4_ev"),  "N/A",               data.get("h4_rsi")),
        ev_line("H1",  data.get("h1_tr"),  data.get("h1_ev"),  data.get("h1_evv"),  data.get("h1_rsi"),  data.get("h1_atr")),
        ev_line("M15", data.get("m15_tr"), data.get("m15_ev"), data.get("m15_evv"), data.get("m15_rsi"), data.get("m15_atr")),
        ev_line("M5",  data.get("m5_tr"),  data.get("m5_ev"),  data.get("m5_evv"),  data.get("m5_rsi"),  data.get("m5_atr")),
        ev_line("M1",  data.get("m1_tr"),  data.get("m1_ev"),  data.get("m1_evv"),  data.get("m1_rsi"),  data.get("m1_atr")),
    ]
    return "\n".join(lines)

def sltp_block(data, direction):
    """✅ SL/TP จาก Swing Structure จริง ไม่ใช่แค่ ATR คูณ"""
    price = data.get("m1_close", "N/A")
    try:
        if direction == "BULL":
            sl   = data.get("bull_sl",  "N/A")
            tp1  = data.get("bull_tp1", "N/A")
            tp2  = data.get("bull_tp2", "N/A")
            tp3  = data.get("bull_tp3", "N/A")
            sl_d = float(data.get("bull_sl_d", 0))
            icon = "🟢"
            side = "BUY"
        else:
            sl   = data.get("bear_sl",  "N/A")
            tp1  = data.get("bear_tp1", "N/A")
            tp2  = data.get("bear_tp2", "N/A")
            tp3  = data.get("bear_tp3", "N/A")
            sl_d = float(data.get("bear_sl_d", 0))
            icon = "🔴"
            side = "SELL"

        return (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{icon} {side} LEVELS\n"
            f"Entry  : ~{price}  (รอ Retest + Confirm M1)\n"
            f"SL     : {sl}  (ห่าง {sl_d:.2f}$ — ใต้/เหนือ Swing Structure)\n"
            f"TP1    : {tp1}  → 1:1.5R  (Partial Close 50%)\n"
            f"TP2    : {tp2}  → 1:2.5R  (Partial Close 30%)\n"
            f"TP3    : {tp3}  → 1:3.5R  (Runner 20% ปล่อยวิ่ง)\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
    except:
        return ""

# ══════════════════════════════
# FIXED PROMPT
# ══════════════════════════════
def get_fixed_prompt(data, label):
    th    = data.get("thai_time", "N/A")
    sess  = data.get("session", "OFF_PEAK")
    trend = data.get("trending", "?")
    title_map = {
        "09:00_LONDON": "⚡ London Open Bias",
        "14:00_NY":     "🔥 NY Open Bias",
    }
    title = title_map.get(label, label)
    chart = ascii_chart(data)

    return f"""คุณคือ SMC Analyst วิเคราะห์ XAUUSD กระชับ ตรงประเด็น
Session: {sess} | Trending Market: {trend}

STRUCTURE DATA:
{struct_block(data)}
{run_lines(data)}
{ctx_line(data)}

{chart}

ตอบในรูปแบบนี้เท่านั้น ห้ามเพิ่มหัวข้ออื่น:

━━━━━━━━━━━━━━━━━━
{title} | {th}
━━━━━━━━━━━━━━━━━━
📊 STRUCTURE
H4 : [Bias + BOS/CHoCH ล่าสุด]
H1 : [Trend + Event REAL/FAKE + ATR]
M15: [Zone + Structure]
M5 : [Pattern ถ้ามี + Trending:{trend}]
M1 : [Trend + Event ล่าสุด + Vol]

📈 LR Bull {data.get('lr_bull')}% / Bear {data.get('lr_bear')}%
📉 SR Bull {data.get('sr_bull')}% / Bear {data.get('sr_bear')}%

🎯 BIAS: [BULL/BEAR/MIXED — เหตุผล 1 บรรทัด]
📍 Level สำคัญ: [ราคาที่ต้องจับตา]
⏳ รอสัญญาณ: [สิ่งที่ต้องเกิดก่อนเข้าเทรด]
⚠️ ระวัง: [Risk หรือสิ่งที่จะ Invalidate Setup]
━━━━━━━━━━━━━━━━━━"""

# ══════════════════════════════
# ✅ STANDING BY PROMPT
# ══════════════════════════════
def get_standby_prompt(data):
    th        = data.get("thai_time", "N/A")
    direction = data.get("dir", "?")
    sess      = data.get("session", "?")
    trend     = data.get("trending", "?")
    retest    = data.get("retest", "NONE")
    chart     = ascii_chart(data)

    dir_e = "🟢 BULL" if direction == "BULL" else "🔴 BEAR"
    sltp  = sltp_block(data, direction)

    if direction == "BULL":
        lr_pct   = data.get("lr_bull", 0)
        sr_pct   = data.get("sr_bull", 0)
        missing  = (
            f"M1/M5 ยังไม่ยืนยัน Bullish — SR Bull เพียง {sr_pct}% (ต้องการ ≥50%)\n"
            f"รอ: M1 CHoCH/BOS ขึ้น + Volume REAL [1.3x avg] + Retest Zone\n"
            f"Level ที่จับตา SUP: {data.get('m1_sup','N/A')} (M1) / {data.get('m5_sup','N/A')} (M5)"
        )
        cancel   = f"ถ้า H4 หรือ H1 เกิด BOS BEAR = ยกเลิก Setup นี้ทันที"
    else:
        lr_pct   = data.get("lr_bear", 0)
        sr_pct   = data.get("sr_bear", 0)
        missing  = (
            f"M1/M5 ยังไม่ยืนยัน Bearish — SR Bear เพียง {sr_pct}% (ต้องการ ≥50%)\n"
            f"รอ: M1 CHoCH/BOS ลง + Volume REAL [1.3x avg] + Retest Zone\n"
            f"Level ที่จับตา RES: {data.get('m1_res','N/A')} (M1) / {data.get('m5_res','N/A')} (M5)"
        )
        cancel   = f"ถ้า H4 หรือ H1 เกิด BOS BULL = ยกเลิก Setup นี้ทันที"

    return f"""คุณคือ SMC Analyst วิเคราะห์ XAUUSD
สถานะ: STANDING BY — H4+H1 Aligned {direction} แต่รอ M1/M5 ยืนยัน
Session: {sess} | Trending: {trend} | Retest: {retest}

STRUCTURE DATA:
{struct_block(data)}
{run_lines(data)}
{ctx_line(data)}

{chart}

{sltp}

ตอบในรูปแบบนี้เท่านั้น:

━━━━━━━━━━━━━━━━━━
⏸ STANDING BY {dir_e} | {th}
━━━━━━━━━━━━━━━━━━
📊 Setup ที่เห็น:
H4+H1 : [Aligned {direction} — รายละเอียด BOS/CHoCH + Valid?]
M15   : [LR {lr_pct}% — Structure ยืนยันไหม?]
M5/M1 : [ยังไม่มาถึง — SR {sr_pct}% เท่านั้น]

⚠️ ขาดอยู่:
{missing}

{sltp}

🔔 เฝ้าดู: [Signal ที่จะทำให้ OPP Alert ออก — ระบุชัดเจน]
❌ ยกเลิก: {cancel}
━━━━━━━━━━━━━━━━━━"""

# ══════════════════════════════
# OPPORTUNITY PROMPT
# ══════════════════════════════
def get_opportunity_prompt(data):
    th        = data.get("thai_time", "N/A")
    direction = data.get("dir", "?")
    conf      = data.get("conf", "MEDIUM")
    remaining = data.get("opp_rem", 0)
    m5_evv    = data.get("m5_evv", "N/A")
    m1_evv    = data.get("m1_evv", "N/A")
    retest    = data.get("retest", "NONE")
    trending  = data.get("trending", "?")
    session   = data.get("session", "?")
    chart     = ascii_chart(data)

    dir_e  = "🟢 BUY" if direction == "BULL" else "🔴 SELL"
    conf_e = "🔥 HIGH" if conf == "HIGH" else "⚡ MEDIUM"
    sltp   = sltp_block(data, direction)

    # ✅ Entry Checklist — เฉพาะเจาะจง รอ Retest + Confirm
    if direction == "BULL":
        checklist = (
            "① ราคาอยู่ในโซน Retest (เหนือ BOS Level เดิม ± 0.5 ATR)\n"
            "② M1 แท่งเทียน Rejection ชัด — wick ล่างยาว หรือ Bullish Engulfing\n"
            "③ M1 Volume ≥ 1.3× avg ขณะ Rejection เกิด\n"
            "④ RSI M1 > 50 + MACD Line ตัดขึ้น Signal Line\n"
            "⑤ เข้า Market Order หลังแท่ง M1 Confirm ปิดแล้วเท่านั้น\n"
            "⑥ ตั้ง SL ทันทีก่อนขยับ Position"
        )
        cancel = (
            f"ราคาทะลุ Swing Low {data.get('m1_sup','N/A')} ลงไปก่อนเข้า = ยกเลิก\n"
            f"Volume ขณะ Breakout เป็น FAKE = รอรอบใหม่"
        )
    else:
        checklist = (
            "① ราคาอยู่ในโซน Retest (ใต้ BOS Level เดิม ± 0.5 ATR)\n"
            "② M1 แท่งเทียน Rejection ชัด — wick บนยาว หรือ Bearish Engulfing\n"
            "③ M1 Volume ≥ 1.3× avg ขณะ Rejection เกิด\n"
            "④ RSI M1 < 50 + MACD Line ตัดลง Signal Line\n"
            "⑤ เข้า Market Order หลังแท่ง M1 Confirm ปิดแล้วเท่านั้น\n"
            "⑥ ตั้ง SL ทันทีก่อนขยับ Position"
        )
        cancel = (
            f"ราคาทะลุ Swing High {data.get('m1_res','N/A')} ขึ้นไปก่อนเข้า = ยกเลิก\n"
            f"Volume ขณะ Breakout เป็น FAKE = รอรอบใหม่"
        )

    return f"""คุณคือ SMC Trader วิเคราะห์ XAUUSD เน้น M1/M5 Entry แม่นยำ
Session: {session} | Trending: {trending} | Retest Zone: {retest}

DIRECTION:{direction} CONF:{conf} TIME:{th} Rem:{remaining}/4
Volume Valid — M5:{m5_evv} | M1:{m1_evv}

STRUCTURE DATA:
{struct_block(data)}
{run_lines(data)}
{ctx_line(data)}

{chart}

{sltp}

ตอบในรูปแบบนี้เท่านั้น:

━━━━━━━━━━━━━━━━━━
{dir_e} {conf_e} | {th}
━━━━━━━━━━━━━━━━━━
📊 CONFLUENCE
H4+H1 : [Bias + BOS REAL/FAKE + ATR]
M15   : [Zone + Structure ยืนยัน?]
M5    : [Pattern + FVG + Trending:{trending}?]
M1    : [Entry Signal + Volume {m1_evv}]
Retest: [{retest}]

⏳ Entry Checklist (ครบทุกข้อถึงเข้า):
{checklist}

{sltp}

❌ ยกเลิก Setup ถ้า:
{cancel}

💡 [วิเคราะห์ความน่าเชื่อถือ Setup นี้ 2 บรรทัด]
🎯 Confidence: {conf} | Session: {session} | R:R เป้าหมาย 1:2.5
━━━━━━━━━━━━━━━━━━"""

# ══════════════════════════════
# CLAUDE API
# ══════════════════════════════
def analyze_with_claude(prompt):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
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

        alert_type = data.get("type", "UNKNOWN")

        if alert_type == "FIXED":
            label     = data.get("label", "UPDATE")
            dedup_key = f"FIXED_{label}"
            if is_duplicate(dedup_key, 300):
                return "OK", 200
            prompt = get_fixed_prompt(data, label)

        elif alert_type == "OPP":
            direction = data.get("dir", "?")
            th_time   = data.get("thai_time", "0:00")
            dedup_key = f"OPP_{direction}_{th_time}"
            if is_duplicate(dedup_key, 120):
                return "OK", 200
            prompt = get_opportunity_prompt(data)

        elif alert_type == "STANDBY":
            direction = data.get("dir", "?")
            th_time   = data.get("thai_time", "0:00")
            dedup_key = f"STANDBY_{direction}_{th_time}"
            if is_duplicate(dedup_key, 600):  # 10 min cooldown
                return "OK", 200
            prompt = get_standby_prompt(data)

        else:
            send_telegram(f"⚠️ Unknown alert type: {alert_type}")
            return "OK", 200

        analysis = analyze_with_claude(prompt)
        send_telegram(analysis)

    except Exception as e:
        print(f"Error: {str(e)}")
        send_telegram(f"❌ Error: {str(e)}")

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
