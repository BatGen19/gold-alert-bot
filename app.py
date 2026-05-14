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

# ══════════════════════════════
# DEDUP
# ══════════════════════════════
def is_duplicate(key, cooldown_sec=300):
    now = time.time()
    if key in _last_sent and now - _last_sent[key] < cooldown_sec:
        return True
    _last_sent[key] = now
    return False

# ══════════════════════════════
# TELEGRAM  (parse_mode HTML เพื่อให้ <pre> render monospace)
# ══════════════════════════════
def send_telegram(message):
    token = TELEGRAM_TOKEN.strip()
    if not token.startswith("bot"):
        token = "bot" + token
    url    = f"https://api.telegram.org/{token}/sendMessage"
    chunks = [message[i:i+4096] for i in range(0, len(message), 4096)]
    for chunk in chunks:
        try:
            r = requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "parse_mode": "HTML"
            }, timeout=10)
            if not r.ok:                                    # fallback ไม่มี parse_mode
                requests.post(url, json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": chunk
                }, timeout=10)
        except Exception as e:
            print(f"Telegram error: {e}")

# ══════════════════════════════════════════════════════
# ASCII CANDLESTICK CHART
# ▓ = แท่งลง (bearish)   ░ = แท่งขึ้น (bullish)   │ = wick
# Schematic chart แสดงแนวโน้ม + mark SL / ENTRY / TP
# ══════════════════════════════════════════════════════
def ascii_chart(direction, entry_price, sl_price, tp_price):
    try:
        is_bear = (direction == "BEAR")
        COLS = 10
        ROWS = 12   # index 0 (top) … 12 (bottom)

        if is_bear:
            # SL บน, ENTRY กลาง, TP ล่าง
            SL_R, EN_R, TP_R = 2, 5, 11
            cdef = [
                (1, 2, 0, 3, '░'),
                (1, 3, 0, 4, '▓'),
                (2, 3, 1, 4, '░'),
                (3, 5, 2, 6, '▓'),
                (4, 6, 3, 7, '▓'),
                (5, 6, 4, 7, '░'),
                (6, 8, 5, 9, '▓'),
                (7, 9, 6,10, '▓'),
                (8, 9, 7,10, '░'),
                (9,11, 8,12, '▓'),
            ]
        else:
            # SL ล่าง, ENTRY กลาง, TP บน
            SL_R, EN_R, TP_R = 10, 7, 1
            cdef = [
                (10,11, 9,12, '▓'),
                ( 9,10, 8,11, '▓'),
                ( 8,10, 7,11, '░'),
                ( 8, 9, 7,10, '▓'),
                ( 7, 8, 6, 9, '░'),
                ( 6, 7, 5, 8, '░'),
                ( 6, 8, 5, 9, '▓'),
                ( 4, 6, 3, 7, '░'),
                ( 3, 5, 2, 6, '░'),
                ( 1, 3, 0, 4, '░'),
            ]

        grid = [[' '] * COLS for _ in range(ROWS + 1)]
        for ci, (bt, bb, wt, wb, ch) in enumerate(cdef):
            if ci >= COLS:
                break
            rlo, rhi = min(wt, wb), max(wt, wb)
            blo, bhi = min(bt, bb), max(bt, bb)
            for r in range(ROWS + 1):
                if rlo <= r <= rhi:
                    grid[r][ci] = ch if blo <= r <= bhi else '│'

        lines = []
        for r in range(ROWS + 1):
            cells = ''.join(grid[r])
            if r == TP_R:
                cells = '·' * COLS
                ann   = f'  ◄ TP    {tp_price:.2f}'
            elif r == EN_R:
                ann   = f'  ◄ ENTRY {entry_price:.2f}'
            elif r == SL_R:
                ann   = f'  ◄ SL    {sl_price:.2f}'
            else:
                ann   = ''
            lines.append(cells + ann)

        header = '▓=DOWN  ░=UP  │=wick'
        return header + '\n' + '\n'.join(lines)

    except Exception as e:
        print(f"ascii_chart error: {e}")
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
        f"SR → Bull {data.get('sr_bull')}% Bear {data.get('sr_bear')}% (M1+M5)\n"
        f"Avg→ Bull {data.get('bull_avg','?')}% / Bear {data.get('bear_avg','?')}%"
    )

def ctx_line(data):
    return (
        f"Zone:{data.get('zone')}({data.get('zone_pct')}%) "
        f"FVG:{data.get('fvg')} "
        f"EQH:{data.get('eqh')} EQL:{data.get('eql')}"
    )

def struct_block(data):
    return "\n".join([
        ev_line("H4",  data.get("h4_tr"),  data.get("h4_ev"),  "N/A",               data.get("h4_rsi")),
        ev_line("H1",  data.get("h1_tr"),  data.get("h1_ev"),  data.get("h1_evv"),  data.get("h1_rsi"),  data.get("h1_atr")),
        ev_line("M15", data.get("m15_tr"), data.get("m15_ev"), data.get("m15_evv"), data.get("m15_rsi"), data.get("m15_atr")),
        ev_line("M5",  data.get("m5_tr"),  data.get("m5_ev"),  data.get("m5_evv"),  data.get("m5_rsi"),  data.get("m5_atr")),
        ev_line("M1",  data.get("m1_tr"),  data.get("m1_ev"),  data.get("m1_evv"),  data.get("m1_rsi"),  data.get("m1_atr")),
    ])

def calc_levels(direction, entry, m1_atr):
    """คืนค่า (sl_pips, tp1, tp2, tp3, sl_price, tp2_price)"""
    try:
        atr_val  = float(m1_atr)
        entry_f  = float(entry)
        sl_p     = round(atr_val * 1.5, 2)
        tp1      = round(sl_p * 1.0,   2)
        tp2      = round(sl_p * 2.0,   2)
        tp3      = round(sl_p * 3.0,   2)
        if direction == "BEAR":
            sl_price = round(entry_f + sl_p, 2)
            tp_price = round(entry_f - tp2,  2)
        else:
            sl_price = round(entry_f - sl_p, 2)
            tp_price = round(entry_f + tp2,  2)
        return sl_p, tp1, tp2, tp3, sl_price, tp_price
    except:
        return "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"

# ══════════════════════════════
# OPP PROMPT
# ══════════════════════════════
def get_opportunity_prompt(data):
    th        = data.get("thai_time", "N/A")
    direction = data.get("dir", "?")
    conf      = data.get("conf", "MEDIUM")
    remaining = data.get("med_rem", 0)
    m1_close  = data.get("m1_close", "N/A")
    m1_atr    = data.get("m1_atr", 1)
    bull_avg  = data.get("bull_avg", "?")
    bear_avg  = data.get("bear_avg", "?")

    dir_e  = "🟢 BUY" if direction == "BULL" else "🔴 SELL"
    conf_e = "🔥 HIGH (ไม่มีลิมิต)" if conf == "HIGH" else f"⚡ MEDIUM (เหลือ {remaining}/3)"
    avg_s  = f"Bull {bull_avg}%" if direction == "BULL" else f"Bear {bear_avg}%"

    sl_p, tp1, tp2, tp3, sl_price, tp_price = calc_levels(direction, m1_close, m1_atr)

    wait = (
        "① M1 CHoCH/BOS ขึ้น + candle ปิดเหนือ swing high\n"
        "② wick ล่างยาว rejection ที่ SUP/FVG\n"
        "③ M1 RSI > 50 หรือ MACD ตัดขึ้น"
    ) if direction == "BULL" else (
        "① M1 CHoCH/BOS ลง + candle ปิดใต้ swing low\n"
        "② wick บนยาว rejection ที่ RES\n"
        "③ M1 RSI < 50 หรือ MACD ตัดลง"
    )

    return f"""คุณคือ SMC Trader วิเคราะห์ XAUUSD เน้นเทรด M1/M5 Winrate สูง RR 1:2+

DIRECTION:{direction} | CONF:{conf} ({avg_s}) | TIME:{th}

STRUCTURE:
{struct_block(data)}
{run_lines(data)}
{ctx_line(data)}

ตอบในรูปแบบนี้ (ห้ามเปลี่ยนโครงสร้าง):

━━━━━━━━━━━━━━━━━━
{dir_e} {conf_e} | {th}
━━━━━━━━━━━━━━━━━━
📊 CONFLUENCE
H4+H1 : [Bias + BOS/CHoCH REAL/FAKE]
M15   : [Structure confirm?]
M5    : [Pattern + Event valid?]
M1    : [Entry signal + Vol]

📈 Confidence: {avg_s}

⏳ รอเข้า:
{wait}

━━━━━━━━━━━━━━━━━━
{dir_e}
Entry : {m1_close}
SL    : ~{sl_p} pips ({sl_price})
TP1   : ~{tp1} pips
TP2   : ~{tp2} pips ({tp_price})
TP3   : ~{tp3} pips
━━━━━━━━━━━━━━━━━━
💡 [สรุป 2 บรรทัด]
⚠️ [ความเสี่ยง 1 บรรทัด]
🎯 Confidence: {conf} ({avg_s})"""

# ══════════════════════════════
# ZONE HIT PROMPT
# ══════════════════════════════
def get_zone_hit_prompt(data):
    th        = data.get("thai_time", "N/A")
    direction = data.get("dir", "?")
    m1_close  = data.get("m1_close", "N/A")
    m1_atr    = data.get("m1_atr", 1)
    m1_ev     = data.get("m1_ev", "NONE")
    m1_evv    = data.get("m1_evv", "N/A")
    m1_rsi    = data.get("m1_rsi", "?")
    m1_vol    = data.get("m1_vol", "?")
    m5_sup    = data.get("m5_sup", "?")
    m5_res    = data.get("m5_res", "?")
    bull_avg  = data.get("bull_avg", "?")
    bear_avg  = data.get("bear_avg", "?")

    dir_e      = "🟢 BUY" if direction == "BULL" else "🔴 SELL"
    zone_level = m5_sup if direction == "BULL" else m5_res
    avg_s      = f"Bull {bull_avg}%" if direction == "BULL" else f"Bear {bear_avg}%"

    sl_p, _, tp2, _, sl_price, tp_price = calc_levels(direction, m1_close, m1_atr)

    try:
        rsi_val = float(m1_rsi)
        rsi_ok  = "✅" if (direction == "BULL" and rsi_val > 45) or \
                          (direction == "BEAR" and rsi_val < 55) else "❌"
    except:
        rsi_ok = "?"

    vol_ok = "✅" if m1_vol in ("HIGH", "NORMAL") else "❌"
    evv_ok = "✅" if m1_evv == "REAL" else "⚠️" if m1_evv == "FAKE" else "?"

    return f"""คุณคือ SMC Trader ตัดสินใจออก order ในเวลา 5 วินาที ตอบสั้นมาก

ZONE HIT {direction} — ราคาถึงโซน {zone_level} แล้ว
Price Now : {m1_close}
M1 Event  : {m1_ev} [{m1_evv}] {evv_ok}
RSI M1    : {m1_rsi} {rsi_ok}
Volume    : {m1_vol} {vol_ok}
Confidence: {avg_s}

STRUCTURE:
{struct_block(data)}
{ctx_line(data)}

ตอบในรูปแบบนี้เท่านั้น (ห้ามเพิ่มเติม):

━━━━━━━━━━━━━━━━━━
🎯 ZONE HIT {dir_e} | {th}
📍 Zone: {zone_level}  Now: {m1_close}
━━━━━━━━━━━━━━━━━━
[✅ ออก ORDER หรือ ❌ ยังไม่ออก — เลือกอันเดียว]
เหตุผล: [1 บรรทัด]

[ถ้าออก ORDER]
Entry : {m1_close}
SL    : ~{sl_p} pips ({sl_price})
TP    : ~{tp2} pips ({tp_price}) 1:2
Risk  : [ต่ำ / กลาง / สูง]

[ถ้าไม่ออก]
รอ: [สัญญาณที่ต้องรอ 1 บรรทัด]
━━━━━━━━━━━━━━━━━━"""

# ══════════════════════════════
# CLAUDE  (Haiku — เร็ว + ถูก เหมาะ real-time alert)
# ══════════════════════════════
def analyze_with_claude(prompt, max_tokens=800):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
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
        except Exception:
            send_telegram(f"⚠️ Parse Error:\n{raw[:300]}")
            return "OK", 200

        alert_type = data.get("type", "UNKNOWN")

        # ── OPP ──────────────────────────────────────
        if alert_type == "OPP":
            direction = data.get("dir", "?")
            conf      = data.get("conf", "MEDIUM")
            th_time   = data.get("thai_time", "0:00")
            dedup_key = f"OPP_{direction}_{conf}_{th_time}"
            cooldown  = 120 if conf == "HIGH" else 180
            if is_duplicate(dedup_key, cooldown):
                return "OK", 200

            # คำนวณราคาจริงเพื่อวาด chart
            m1_close = data.get("m1_close", 0)
            m1_atr   = data.get("m1_atr", 1)
            sl_p, _, tp2, _, sl_price, tp_price = calc_levels(direction, m1_close, m1_atr)

            chart_str = ""
            if sl_price != "N/A":
                chart_str = ascii_chart(
                    direction,
                    float(m1_close or 0),
                    float(sl_price),
                    float(tp_price)
                )

            analysis = analyze_with_claude(get_opportunity_prompt(data), max_tokens=900)

            # Chart block อยู่บน, Claude analysis อยู่ล่าง
            final_msg = (f"<pre>{chart_str}</pre>\n{analysis}") if chart_str else analysis
            send_telegram(final_msg)

        # ── ZONE HIT ─────────────────────────────────
        elif alert_type == "ZONE_HIT":
            direction = data.get("dir", "?")
            th_time   = data.get("thai_time", "0:00")
            dedup_key = f"ZONE_{direction}_{th_time}"
            if is_duplicate(dedup_key, 90):
                return "OK", 200

            m1_close = data.get("m1_close", 0)
            m1_atr   = data.get("m1_atr", 1)
            sl_p, _, tp2, _, sl_price, tp_price = calc_levels(direction, m1_close, m1_atr)

            chart_str = ""
            if sl_price != "N/A":
                chart_str = ascii_chart(
                    direction,
                    float(m1_close or 0),
                    float(sl_price),
                    float(tp_price)
                )

            analysis = analyze_with_claude(get_zone_hit_prompt(data), max_tokens=400)

            final_msg = (f"<pre>{chart_str}</pre>\n{analysis}") if chart_str else analysis
            send_telegram(final_msg)

        else:
            send_telegram(f"⚠️ Unknown alert type: {alert_type}")

    except Exception as e:
        print(f"Error: {str(e)}")
        send_telegram(f"❌ Error: {str(e)}")

    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
