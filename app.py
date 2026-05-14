from flask import Flask, request
import requests
import os
import anthropic
import json
import time
from concurrent.futures import ThreadPoolExecutor

# ── Chart dependencies ──────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    from io import BytesIO
    CHART_OK = True
except ImportError:
    CHART_OK = False
    print("⚠️  matplotlib/numpy not installed — charts disabled")

app = Flask(__name__)

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
CLAUDE_API_KEY   = os.environ.get("CLAUDE_API_KEY")

_last_sent = {}
_executor  = ThreadPoolExecutor(max_workers=4)

# ══════════════════════════════════════════════════════
# DEDUP
# ══════════════════════════════════════════════════════
def is_duplicate(key, cooldown_sec=300):
    now = time.time()
    if key in _last_sent and now - _last_sent[key] < cooldown_sec:
        return True
    _last_sent[key] = now
    return False

# ══════════════════════════════════════════════════════
# TELEGRAM SENDERS
# ══════════════════════════════════════════════════════
def _token():
    t = TELEGRAM_TOKEN.strip()
    return t if t.startswith("bot") else "bot" + t

def send_telegram(text):
    url    = f"https://api.telegram.org/{_token()}/sendMessage"
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
    for chunk in chunks:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk}, timeout=10)

def send_telegram_photo(image_bytes, caption=""):
    url = f"https://api.telegram.org/{_token()}/sendPhoto"
    cap = caption[:1024]
    try:
        r = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": cap},
            files={"photo": ("chart.png", image_bytes, "image/png")},
            timeout=20,
        )
        if not r.ok:
            send_telegram(caption)
    except Exception as e:
        print(f"Photo send error: {e}")
        send_telegram(caption)

# ══════════════════════════════════════════════════════
# CHART GENERATOR  (OPP only)
# ══════════════════════════════════════════════════════
def generate_trade_chart(data, direction, entry_price):
    if not CHART_OK or not entry_price:
        return None
    try:
        m1_atr = float(data.get("m1_atr") or 1)
        m5_atr = float(data.get("m5_atr") or m1_atr)
        sl_p   = round(m1_atr * 1.5, 2)
        tp_p   = round(sl_p * 2.0, 2)

        if direction == "BULL":
            sl_price = round(entry_price - sl_p, 2)
            tp_price = round(entry_price + tp_p, 2)
        else:
            sl_price = round(entry_price + sl_p, 2)
            tp_price = round(entry_price - tp_p, 2)

        m5_res = float(data.get("m5_res") or 0)
        m5_sup = float(data.get("m5_sup") or 0)

        all_p = [entry_price, sl_price, tp_price]
        if m5_res > 0: all_p.append(m5_res)
        if m5_sup > 0: all_p.append(m5_sup)
        pad   = max(sl_p, tp_p) * 0.45
        p_min = min(all_p) - pad
        p_max = max(all_p) + pad

        BG     = "#131722"
        BULL_C = "#26a69a"
        BEAR_C = "#ef5350"

        fig, ax = plt.subplots(figsize=(6, 5), dpi=100)
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(BG)
        ax.set_xlim(0, 12)
        ax.set_ylim(p_min, p_max)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_xticks([]); ax.set_yticks([])

        for gi in range(6):
            gv = p_min + (p_max - p_min) * gi / 5
            ax.axhline(gv, color="#1e2535", linewidth=0.5, zorder=0)

        seed = int(abs(entry_price) * 7) % 9973
        np.random.seed(seed)
        walk = [entry_price]
        for _ in range(8):
            walk.insert(0, walk[0] + np.random.uniform(-m5_atr * 0.38, m5_atr * 0.38))

        xs = [0.3, 0.7, 1.1, 1.5, 1.9, 2.3, 2.7, 3.1]
        for j, cx in enumerate(xs):
            o = walk[j]; c = walk[j + 1]
            hi = max(o, c) + abs(float(np.random.uniform(0, m5_atr * 0.13)))
            lo = min(o, c) - abs(float(np.random.uniform(0, m5_atr * 0.13)))
            col = BULL_C if c >= o else BEAR_C
            ax.plot([cx, cx], [lo, hi], color=col, linewidth=0.9, zorder=2)
            bh = max(abs(c - o), m5_atr * 0.008)
            ax.add_patch(mpatches.Rectangle(
                (cx - 0.17, min(o, c)), 0.34, bh,
                color=col, zorder=3, linewidth=0))

        ax.axvline(3.55, color="#2a3150", linewidth=0.8, zorder=1)

        bx, bw = 3.6, 8.2
        if direction == "BULL":
            ax.add_patch(mpatches.Rectangle(
                (bx, entry_price), bw, tp_price - entry_price,
                color=BULL_C, alpha=0.20, zorder=2, linewidth=0))
            ax.add_patch(mpatches.Rectangle(
                (bx, sl_price), bw, entry_price - sl_price,
                color=BEAR_C, alpha=0.28, zorder=2, linewidth=0))
        else:
            ax.add_patch(mpatches.Rectangle(
                (bx, entry_price), bw, sl_price - entry_price,
                color=BEAR_C, alpha=0.28, zorder=2, linewidth=0))
            ax.add_patch(mpatches.Rectangle(
                (bx, tp_price), bw, entry_price - tp_price,
                color=BULL_C, alpha=0.20, zorder=2, linewidth=0))

        lx0, lx1 = 3.3, 11.8
        ax.plot([lx0, lx1], [entry_price]*2, color="#FFFFFF", lw=1.4, zorder=5)
        ax.plot([lx0, lx1], [sl_price]*2,    color=BEAR_C,    lw=1.0, ls="--", zorder=5)
        ax.plot([lx0, lx1], [tp_price]*2,    color=BULL_C,    lw=1.0, ls="--", zorder=5)

        for lvl, col, tag in [(m5_res, "#FF8888", "R"), (m5_sup, "#88FFBB", "S")]:
            if lvl > 0 and p_min < lvl < p_max:
                ax.plot([0, lx0], [lvl]*2, color=col, lw=0.7, ls=":", alpha=0.55, zorder=1)
                ax.text(0.1, lvl, tag, color=col, fontsize=6.5,
                        va="bottom", alpha=0.75, fontfamily="monospace")

        tx      = 11.7
        dir_sym = "▲" if direction == "BULL" else "▼"
        ax.text(tx, entry_price, f"{dir_sym} {entry_price:.2f}",
                color="#FFFFFF", fontsize=8.5, ha="right", va="center",
                fontfamily="monospace", fontweight="bold", zorder=6)
        ax.text(tx, sl_price, f"SL  {sl_price:.2f}",
                color=BEAR_C, fontsize=7.5, ha="right", va="center",
                fontfamily="monospace", zorder=6)
        ax.text(tx, tp_price, f"TP  {tp_price:.2f}",
                color=BULL_C, fontsize=7.5, ha="right", va="center",
                fontfamily="monospace", zorder=6)

        avg_key   = "bull_avg" if direction == "BULL" else "bear_avg"
        avg_val   = data.get(avg_key, "?")
        zone      = data.get("zone", "N/A")
        dir_label = "BUY" if direction == "BULL" else "SELL"
        ax.set_title(
            f"  XAUUSD · {dir_label}   Zone:{zone}   Conf:{avg_val}%  ",
            color="#9098b0", fontsize=8, pad=7,
            fontfamily="monospace", loc="left")

        plt.tight_layout(pad=0.3)
        buf = BytesIO()
        plt.savefig(buf, format="png", facecolor=BG, dpi=100, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()

    except Exception as e:
        print(f"Chart error: {e}")
        return None

# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════
def trend_e(s):
    return "🟢" if s == "BULL" else "🔴" if s == "BEAR" else "🟡"

def ev_line(name, tr, ev, evv, rsi, atr=""):
    valid = f"[{evv}]" if evv not in ("N/A", "") else ""
    atr_s = f" ATR:{atr}" if atr else ""
    return f"{name}: {tr} | {ev}{valid} RSI:{rsi}{atr_s}"

def ctx_line(data):
    return (
        f"Zone:{data.get('zone')}({data.get('zone_pct')}%) "
        f"FVG:{data.get('fvg')} "
        f"EQH:{data.get('eqh')} EQL:{data.get('eql')}"
    )

def struct_block(data):
    return "\n".join([
        ev_line("H4",  data.get("h4_tr"),  data.get("h4_ev"),  "N/A",               data.get("h4_rsi")),
        ev_line("H1",  data.get("h1_tr"),  data.get("h1_ev"),  data.get("h1_evv"),  data.get("h1_rsi"), data.get("h1_atr")),
        ev_line("M15", data.get("m15_tr"), data.get("m15_ev"), data.get("m15_evv"), data.get("m15_rsi"), data.get("m15_atr")),
        ev_line("M5",  data.get("m5_tr"),  data.get("m5_ev"),  data.get("m5_evv"),  data.get("m5_rsi"), data.get("m5_atr")),
        ev_line("M1",  data.get("m1_tr"),  data.get("m1_ev"),  data.get("m1_evv"),  data.get("m1_rsi"), data.get("m1_atr")),
    ])

# ══════════════════════════════════════════════════════
# CLAUDE CALLS
# ══════════════════════════════════════════════════════
def claude_call(prompt, max_tokens=80):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",   # ← เร็วกว่า Sonnet 3x ราคาถูกกว่า 5x
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()

def claude_opp_lines(data, direction):
    """Returns (insight, risk) — ใช้ใน OPP เท่านั้น ไม่ต้องเร็วมาก"""
    avg_key = "bull_avg" if direction == "BULL" else "bear_avg"
    prompt = (
        f"XAUUSD {direction} SMC setup:\n"
        f"{struct_block(data)}\n"
        f"{ctx_line(data)}\n"
        f"Conf: {data.get(avg_key,'?')}%\n\n"
        f"Reply EXACTLY 2 lines, English, no preamble:\n"
        f"Line1: confluence summary (max 65 chars)\n"
        f"Line2: main risk (max 55 chars)"
    )
    raw    = claude_call(prompt, max_tokens=90)
    lines  = raw.split("\n")
    insight = lines[0].strip()[:70] if lines          else "Structure aligned"
    risk    = lines[1].strip()[:60] if len(lines) > 1 else "Monitor spread"
    return insight, risk

def claude_zone_decision(data, direction):
    """
    Returns (enter: bool, entry: float, sl_p: float, tp_p: float, reason: str)
    เร็วที่สุด — Haiku + max_tokens น้อย
    """
    m1_atr = float(data.get("m1_atr") or 1)
    m1_c   = float(data.get("m1_close") or 0)

    prompt = (
        f"XAUUSD {direction} zone hit.\n"
        f"M1 close:{m1_c} ATR:{m1_atr}\n"
        f"M1 Event:{data.get('m1_ev','NONE')}[{data.get('m1_evv','N/A')}] "
        f"RSI:{data.get('m1_rsi','?')} Vol:{data.get('m1_vol','?')}\n"
        f"{struct_block(data)}\n\n"
        f"Reply EXACTLY 3 lines, no preamble:\n"
        f"Line1: YES or NO\n"
        f"Line2: reason (max 55 chars)\n"
        f"Line3: adjust entry price only if needed, else write KEEP"
    )
    raw   = claude_call(prompt, max_tokens=60)
    lines = [l.strip() for l in raw.split("\n") if l.strip()]

    enter  = "YES" in lines[0].upper() if lines         else False
    reason = lines[1][:60]             if len(lines) > 1 else "Check manually"

    # ถ้า Claude แนะนำ adjust entry
    adj_entry = m1_c
    if len(lines) > 2 and lines[2].upper() != "KEEP":
        try:
            adj_entry = float(lines[2].replace("ENTRY","").replace(":","").strip())
        except Exception:
            adj_entry = m1_c

    sl_p = round(m1_atr * 1.5, 2)
    tp_p = round(sl_p * 2.0,   2)
    return enter, round(adj_entry, 2), sl_p, tp_p, reason

# ══════════════════════════════════════════════════════
# MESSAGE FORMATTERS
# ══════════════════════════════════════════════════════
def format_opp_message(data, direction, conf, entry, sl_p, tp1, tp2, tp3, insight, risk):
    th      = data.get("thai_time", "N/A")
    avg_key = "bull_avg" if direction == "BULL" else "bear_avg"
    avg_val = data.get(avg_key, "?")
    med_rem = data.get("med_rem", "?")
    zone    = data.get("zone", "N/A")
    fvg     = data.get("fvg",  "N/A")

    dir_e  = "🟢 BUY"  if direction == "BULL" else "🔴 SELL"
    conf_e = "🔥 HIGH" if conf == "HIGH"      else f"⚡ MED · {med_rem}/3"

    tfs = (
        f"H4{trend_e(data.get('h4_tr',''))} "
        f"H1{trend_e(data.get('h1_tr',''))} "
        f"M15{trend_e(data.get('m15_tr',''))} "
        f"M5{trend_e(data.get('m5_tr',''))} "
        f"M1{trend_e(data.get('m1_tr',''))}"
    )
    wait = (
        "① M1 BOS/CHoCH ↑  ② wick SUP  ③ RSI > 50"
        if direction == "BULL" else
        "① M1 BOS/CHoCH ↓  ② wick RES  ③ RSI < 50"
    )
    return (
        f"✨ OPPORTUNITY · {th}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{dir_e} · {conf_e} · {avg_val}%\n"
        f"{tfs}\n"
        f"Zone {zone} · FVG {fvg}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📍 Entry  {entry}\n"
        f"🛑 SL     ~{sl_p} pts\n"
        f"🎯 TP1    ~{tp1} pts\n"
        f"🎯 TP2    ~{tp2} pts\n"
        f"🎯 TP3    ~{tp3} pts\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏳ {wait}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💬 {insight}\n"
        f"⚠️  {risk}"
    )

def format_zone_message(data, direction, zone_level,
                         enter, entry, sl_p, tp_p, reason):
    th     = data.get("thai_time", "N/A")
    m1_rsi = data.get("m1_rsi", "?")
    m1_vol = data.get("m1_vol", "?")
    m1_evv = data.get("m1_evv", "N/A")

    dir_e = "🟢 BUY" if direction == "BULL" else "🔴 SELL"

    try:
        rsi_ok = "✅" if (direction == "BULL" and float(m1_rsi) > 45) \
                          or (direction == "BEAR" and float(m1_rsi) < 55) else "❌"
    except Exception:
        rsi_ok = "?"
    vol_ok = "✅" if m1_vol in ("HIGH", "NORMAL") else "❌"
    evv_ok = "✅" if m1_evv == "REAL" else "⚠️"

    if enter:
        body = (
            f"✅ เข้า ORDER ทันที\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📍 Entry  {entry}\n"
            f"🛑 SL     ~{sl_p} pts\n"
            f"🎯 TP     ~{tp_p} pts  (1:2)\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💬 {reason}"
        )
    else:
        body = (
            f"❌ ยังไม่เข้า\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"⏳ รอ: {reason}"
        )

    return (
        f"🔔 ZONE HIT · {th}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{dir_e}  @ {zone_level}\n"
        f"RSI{rsi_ok}  Vol{vol_ok}  Evt{evv_ok}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{body}"
    )

# ══════════════════════════════════════════════════════
# WEBHOOK
# ══════════════════════════════════════════════════════
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

        # ── OPP ───────────────────────────────────────────
        if alert_type == "OPP":
            direction = data.get("dir", "?")
            conf      = data.get("conf", "MEDIUM")
            th_time   = data.get("thai_time", "0:00")
            dedup_key = f"OPP_{direction}_{conf}_{th_time}"
            cooldown  = 120 if conf == "HIGH" else 180
            if is_duplicate(dedup_key, cooldown):
                return "OK", 200

            entry  = float(data.get("m1_close") or 0)
            m1_atr = float(data.get("m1_atr")   or 1)
            sl_p   = round(m1_atr * 1.5, 2)
            tp1    = round(sl_p * 1.0,   2)
            tp2    = round(sl_p * 2.0,   2)
            tp3    = round(sl_p * 3.0,   2)

            # Claude + Chart รันพร้อมกัน (Thread)
            fut_claude = _executor.submit(claude_opp_lines, data, direction)
            fut_chart  = _executor.submit(generate_trade_chart, data, direction, entry)

            insight, risk = fut_claude.result()
            chart         = fut_chart.result()

            msg = format_opp_message(data, direction, conf,
                                     entry, sl_p, tp1, tp2, tp3,
                                     insight, risk)
            if chart:
                send_telegram_photo(chart, msg)
            else:
                send_telegram(msg)

        # ── ZONE HIT  (เร็วที่สุด — text only) ────────────
        elif alert_type == "ZONE_HIT":
            direction = data.get("dir", "?")
            th_time   = data.get("thai_time", "0:00")
            dedup_key = f"ZONE_{direction}_{th_time}"
            if is_duplicate(dedup_key, 90):
                return "OK", 200

            zone_level = data.get("m5_sup" if direction == "BULL" else "m5_res", "?")

            # Claude เดียว ส่ง text ทันที ไม่มี chart
            enter, entry, sl_p, tp_p, reason = claude_zone_decision(data, direction)

            msg = format_zone_message(data, direction, zone_level,
                                      enter, entry, sl_p, tp_p, reason)
            send_telegram(msg)   # ← text เท่านั้น เร็วสุด

        else:
            send_telegram(f"⚠️ Unknown type: {alert_type}")

    except Exception as e:
        print(f"Error: {e}")
        send_telegram(f"❌ Error: {e}")

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
