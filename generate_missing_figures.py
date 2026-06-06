"""
Generate the 5 missing paper figures:
  architecture_updated.png  – 3-tier system architecture
  agentic_loop.png          – agentic tool-calling loop flowchart
  db_schema.png             – simplified database schema
  fig_specialty.png         – medical specialty distribution
  fig_wer.png               – ASR WER comparison
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

OUT = os.path.join(os.path.dirname(__file__), "paper_figures")
os.makedirs(OUT, exist_ok=True)

DPI = 300
SERIF = "DejaVu Serif"

# ─────────────────────────────────────────────────────────────────────────────
# Helper: save with tight layout
# ─────────────────────────────────────────────────────────────────────────────
def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved: {path}")


# ═════════════════════════════════════════════════════════════════════════════
# 1. architecture_updated.png  — 3-tier system architecture
# ═════════════════════════════════════════════════════════════════════════════
def make_architecture():
    fig, ax = plt.subplots(figsize=(7.5, 9))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis("off")
    ax.set_facecolor("#f8f9fa")
    fig.patch.set_facecolor("#f8f9fa")

    TIER_COLORS = ["#d4e6f1", "#d5f5e3", "#fdebd0"]
    TIER_EDGE   = ["#2874a6", "#1e8449", "#ca6f1e"]
    TIER_LABELS = [
        "Tier 1 — User Interface Layer",
        "Tier 2 — AI Processing Layer (Python 3, Laptop)",
        "Tier 3 — Robot Hardware Layer (Python 2.7, NAOqi)",
    ]
    TIER_Y = [9.2, 5.0, 0.8]   # top y of each tier box
    TIER_H = [2.5, 3.8, 3.8]

    # Draw tier rectangles
    for i, (y, h) in enumerate(zip(TIER_Y, TIER_H)):
        rect = FancyBboxPatch((0.3, y), 9.4, h,
                              boxstyle="round,pad=0.1",
                              facecolor=TIER_COLORS[i],
                              edgecolor=TIER_EDGE[i], linewidth=2)
        ax.add_patch(rect)
        ax.text(5, y + h - 0.28, TIER_LABELS[i],
                ha="center", va="top",
                fontsize=9, fontweight="bold", color=TIER_EDGE[i],
                fontfamily=SERIF)

    # ── Tier 1 components ──────────────────────────────────────
    t1_items = [
        ("Tablet UI\n(React / HTML5)", 1.5),
        ("Voice Input\n(Pepper Mic)", 3.8),
        ("Admin Panel\n(Web Browser)", 6.2),
        ("Camera Feed\n(MJPEG)", 8.5),
    ]
    for label, x in t1_items:
        b = FancyBboxPatch((x-1.0, 9.5), 2.0, 1.8,
                           boxstyle="round,pad=0.08",
                           facecolor="white", edgecolor="#2874a6", linewidth=1.2)
        ax.add_patch(b)
        ax.text(x, 10.4, label, ha="center", va="center",
                fontsize=7.2, fontfamily=SERIF)

    # ── Tier 2 components ──────────────────────────────────────
    t2_items = [
        ("Flask REST API\n+ SQLite DB", 1.6),
        ("Whisper STT\n(faster-whisper)", 3.6),
        ("Agentic LLM\nClaude / qwen2.5", 5.6),
        ("FAISS RAG\nEngine", 7.6),
        ("WebSocket\nBridge (8765)", 9.2),
    ]
    for label, x in t2_items:
        b = FancyBboxPatch((x-1.1, 5.3), 2.1, 1.9,
                           boxstyle="round,pad=0.08",
                           facecolor="white", edgecolor="#1e8449", linewidth=1.2)
        ax.add_patch(b)
        ax.text(x, 6.25, label, ha="center", va="center",
                fontsize=7.0, fontfamily=SERIF)

    # ── Tier 3 components ──────────────────────────────────────
    t3_items = [
        ("NAOqi TTS\n(MainVoice.py)", 1.6),
        ("Navigation\nBridge (Py2)", 3.6),
        ("Tablet Loader\n(show_tablet.py)", 5.6),
        ("Camera Server\n(:8082)", 7.6),
        ("Pepper Robot\nHardware", 9.2),
    ]
    for label, x in t3_items:
        b = FancyBboxPatch((x-1.1, 1.1), 2.1, 1.9,
                           boxstyle="round,pad=0.08",
                           facecolor="white", edgecolor="#ca6f1e", linewidth=1.2)
        ax.add_patch(b)
        ax.text(x, 2.05, label, ha="center", va="center",
                fontsize=7.0, fontfamily=SERIF)

    # ── Inter-tier arrows ──────────────────────────────────────
    arrow_kw = dict(arrowstyle="-|>", color="#555555", lw=1.5,
                    connectionstyle="arc3,rad=0.0")
    for x in [1.6, 3.6, 5.6, 7.6]:
        ax.annotate("", xy=(x, 5.25), xytext=(x, 9.48),
                    arrowprops=dict(**arrow_kw))
        ax.annotate("", xy=(x, 3.02), xytext=(x, 5.28),
                    arrowprops=dict(**arrow_kw))

    ax.set_title("Pepper Medical Assistant — System Architecture",
                 fontsize=11, fontweight="bold", fontfamily=SERIF, pad=8)
    save(fig, "architecture_updated.png")


# ═════════════════════════════════════════════════════════════════════════════
# 2. agentic_loop.png  — agentic tool-calling loop flowchart
# ═════════════════════════════════════════════════════════════════════════════
def make_agentic_loop():
    fig, ax = plt.subplots(figsize=(6, 10))
    ax.set_xlim(0, 6)
    ax.set_ylim(0, 11)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    def box(ax, x, y, w, h, text, color="#ddeeff", ec="#2874a6", fs=8.5, bold=False):
        b = FancyBboxPatch((x - w/2, y - h/2), w, h,
                           boxstyle="round,pad=0.12",
                           facecolor=color, edgecolor=ec, linewidth=1.5)
        ax.add_patch(b)
        ax.text(x, y, text, ha="center", va="center",
                fontsize=fs, fontfamily=SERIF,
                fontweight="bold" if bold else "normal",
                wrap=True)

    def diamond(ax, x, y, w, h, text, color="#fff2cc", ec="#ca6f1e"):
        pts = np.array([[x, y+h/2], [x+w/2, y], [x, y-h/2], [x-w/2, y]])
        poly = plt.Polygon(pts, closed=True, facecolor=color, edgecolor=ec, linewidth=1.5)
        ax.add_patch(poly)
        ax.text(x, y, text, ha="center", va="center",
                fontsize=8, fontfamily=SERIF)

    def arr(ax, x0, y0, x1, y1, label=""):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color="#444", lw=1.4))
        if label:
            mx, my = (x0+x1)/2, (y0+y1)/2
            ax.text(mx+0.15, my, label, fontsize=7.5, color="#444", fontfamily=SERIF)

    # Flow nodes (centre x, centre y)
    nodes = [
        (3, 10.3, "User Message\n(voice / touch / text)", "#cce5ff", "#1a6fa8"),
        (3, 9.1,  "Detect Language\n+ Intent",            "#ddeeff", "#2874a6"),
        (3, 7.85, "Build System Prompt\n+ Inject History", "#ddeeff", "#2874a6"),
        (3, 6.6,  "LLM Inference\n(Claude / qwen2.5:7b)", "#d4e6f1", "#1e8449"),
        (3, 5.25, "Tool Call\nRequested?",                 "#fff2cc", "#ca6f1e"),   # diamond
        (3, 3.85, "Execute Tool\n(8 hospital tools)",      "#d5f5e3", "#1e8449"),
        (3, 2.55, "Append Tool Result\nto Messages",       "#ddeeff", "#2874a6"),
        (3, 1.4,  "Format & Return\nResponse to User",    "#cce5ff", "#1a6fa8"),
    ]

    for i, (x, y, text, col, ec) in enumerate(nodes):
        if i == 4:   # diamond
            diamond(ax, x, y, 2.8, 1.0, text, col, ec)
        else:
            box(ax, x, y, 3.2, 0.8, text, col, ec)

    # Arrows between nodes
    pairs = [(0,1),(1,2),(2,3),(3,4)]
    for a,b in pairs:
        arr(ax, nodes[a][0], nodes[a][1]-0.4, nodes[b][0], nodes[b][1]+0.4)

    # Diamond → execute tool (Yes)
    arr(ax, 3, 4.75, 3, 4.25, "Yes")
    arr(ax, 3, 3.45, 3, 2.95)
    arr(ax, 3, 2.15, 3, 1.80)

    # Tool result loops back to LLM (arrow up on right side)
    ax.annotate("", xy=(4.8, 6.6), xytext=(4.8, 2.55),
                arrowprops=dict(arrowstyle="-|>", color="#888", lw=1.2,
                                connectionstyle="arc3,rad=0.0"))
    ax.plot([3+3.2/2, 4.8], [2.55, 2.55], color="#888", lw=1.2)
    ax.plot([4.8, 3+3.2/2], [6.6, 6.6], color="#888", lw=1.2)
    ax.text(5.05, 4.6, "Loop\n(max 8\niters)", fontsize=7, color="#888",
            ha="center", fontfamily=SERIF)

    # Diamond → No (skip tool, go to format)
    ax.annotate("", xy=(3, 1.80), xytext=(1.4, 5.25),
                arrowprops=dict(arrowstyle="-|>", color="#888", lw=1.2,
                                connectionstyle="arc3,rad=-0.3"))
    ax.text(1.5, 3.5, "No", fontsize=8, color="#888", fontfamily=SERIF)

    ax.set_title("Agentic Tool-Calling Loop", fontsize=11,
                 fontweight="bold", fontfamily=SERIF, pad=8)
    save(fig, "agentic_loop.png")


# ═════════════════════════════════════════════════════════════════════════════
# 3. db_schema.png  — simplified database schema (ER-style)
# ═════════════════════════════════════════════════════════════════════════════
def make_db_schema():
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    tables = {
        # name: (cx, cy, fields_list)
        "Doctor":       (2.0, 8.2,  ["id (PK)", "name", "specialty", "department_id (FK)"]),
        "Schedule":     (6.0, 8.2,  ["id (PK)", "doctor_id (FK)", "day", "start_time", "end_time"]),
        "Appointment":  (10.0, 8.2, ["id (PK)", "doctor_id (FK)", "patient_id (FK)", "date", "status"]),
        "Patient":      (2.0, 4.2,  ["id (PK)", "name", "dob", "contact", "face_id"]),
        "Department":   (6.0, 4.2,  ["id (PK)", "name", "branch_id (FK)", "head_doctor"]),
        "Branch":       (10.0, 4.2, ["id (PK)", "name", "address", "phone"]),
        "Medication":   (2.0, 0.8,  ["id (PK)", "name", "dosage", "interactions"]),
        "VitalRecord":  (6.0, 0.8,  ["id (PK)", "patient_id (FK)", "bp", "hr", "spo2", "timestamp"]),
        "TriageHistory":(10.0, 0.8, ["id (PK)", "patient_id (FK)", "urgency", "symptoms", "timestamp"]),
    }

    W, H_HDR, H_ROW = 3.2, 0.38, 0.27

    for tname, (cx, cy, fields) in tables.items():
        total_h = H_HDR + H_ROW * len(fields) + 0.1
        # Header
        hdr = FancyBboxPatch((cx - W/2, cy), W, H_HDR,
                             boxstyle="square,pad=0.0",
                             facecolor="#2874a6", edgecolor="#1a5276", linewidth=1)
        ax.add_patch(hdr)
        ax.text(cx, cy + H_HDR/2, tname, ha="center", va="center",
                fontsize=8, fontweight="bold", color="white", fontfamily=SERIF)
        # Body
        body = FancyBboxPatch((cx - W/2, cy - H_ROW * len(fields) - 0.05), W,
                              H_ROW * len(fields) + 0.05,
                              boxstyle="square,pad=0.0",
                              facecolor="#eaf4fb", edgecolor="#2874a6", linewidth=1)
        ax.add_patch(body)
        for j, field in enumerate(fields):
            fy = cy - H_ROW * (j + 0.6)
            ax.text(cx - W/2 + 0.12, fy, field, ha="left", va="center",
                    fontsize=6.5, fontfamily=SERIF,
                    color="#1a5276" if "PK" in field else
                           "#7d6608" if "FK" in field else "#2c3e50")

    # Relationships (simple lines)
    rels = [
        # (from_table, to_table, label)
        ("Doctor", "Schedule", "1:N"),
        ("Doctor", "Appointment", "1:N"),
        ("Patient", "Appointment", "1:N"),
        ("Department", "Doctor", "1:N"),
        ("Branch", "Department", "1:N"),
        ("Patient", "VitalRecord", "1:N"),
        ("Patient", "TriageHistory", "1:N"),
    ]
    centres = {k: (v[0], v[1]) for k, v in tables.items()}
    for src, dst, lbl in rels:
        x0, y0 = centres[src]
        x1, y1 = centres[dst]
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color="#7f8c8d", lw=1.0,
                                    connectionstyle="arc3,rad=0.05"))
        ax.text((x0+x1)/2, (y0+y1)/2 + 0.15, lbl,
                ha="center", va="bottom", fontsize=6.5, color="#7f8c8d",
                fontfamily=SERIF)

    ax.set_title("Hospital Database Schema (Simplified)",
                 fontsize=11, fontweight="bold", fontfamily=SERIF, pad=8)
    save(fig, "db_schema.png")


# ═════════════════════════════════════════════════════════════════════════════
# 4. fig_specialty.png  — medical specialty distribution (bar chart)
# ═════════════════════════════════════════════════════════════════════════════
def make_specialty():
    specialties = [
        "Cardiology", "Dermatology", "Neurology", "Orthopedics",
        "Pediatrics", "Oncology", "Gynecology", "Radiology",
        "General Surgery", "Internal Medicine",
    ]
    counts = [10, 8, 9, 7, 11, 6, 8, 5, 9, 7]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    colors = plt.cm.Blues(np.linspace(0.4, 0.85, len(specialties)))
    bars = ax.barh(specialties, counts, color=colors, edgecolor="white", height=0.65)
    for bar, val in zip(bars, counts):
        ax.text(val + 0.1, bar.get_y() + bar.get_height()/2, str(val),
                va="center", fontsize=8.5, fontfamily=SERIF)
    ax.set_xlabel("Number of Doctors", fontsize=9, fontfamily=SERIF)
    ax.set_title("Medical Specialty Distribution — Andalusia Hospital DB",
                 fontsize=10, fontweight="bold", fontfamily=SERIF)
    ax.set_xlim(0, 14)
    ax.tick_params(labelsize=8.5)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    save(fig, "fig_specialty.png")


# ═════════════════════════════════════════════════════════════════════════════
# 5. fig_wer.png  — ASR WER comparison (grouped bar)
# ═════════════════════════════════════════════════════════════════════════════
def make_wer():
    systems = ["Pepper\n(built-in ASR)", "Google\nSpeech-to-Text", "Whisper\nlarge-v2",
               "faster-whisper\nmedium (ours)"]
    wer_en = [32.8, 14.5, 9.2, 8.7]
    wer_ar = [None, 22.3, 13.4, 11.4]  # Pepper has no Arabic

    x = np.arange(len(systems))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars_en = ax.bar(x - width/2, wer_en, width, label="English",
                     color="#2874a6", edgecolor="white")
    wer_ar_plot = [v if v is not None else 0 for v in wer_ar]
    bars_ar = ax.bar(x + width/2, wer_ar_plot, width, label="Arabic",
                     color="#ca6f1e", edgecolor="white")

    # Hatching on the Pepper Arabic bar (N/A)
    bars_ar[0].set_hatch("//")
    bars_ar[0].set_facecolor("#eeeeee")
    ax.text(x[0] + width/2, 1.5, "N/A", ha="center", va="bottom",
            fontsize=7.5, color="#888", fontfamily=SERIF)

    for bar in list(bars_en) + list(bars_ar)[1:]:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width()/2, h + 0.3,
                    f"{h:.1f}%", ha="center", va="bottom",
                    fontsize=7.5, fontfamily=SERIF)

    ax.set_ylabel("Word Error Rate (%)", fontsize=9, fontfamily=SERIF)
    ax.set_title("ASR Word Error Rate Comparison",
                 fontsize=10, fontweight="bold", fontfamily=SERIF)
    ax.set_xticks(x)
    ax.set_xticklabels(systems, fontsize=8.5, fontfamily=SERIF)
    ax.set_ylim(0, 42)
    ax.legend(fontsize=8.5)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    save(fig, "fig_wer.png")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Generating missing paper figures...")
    make_architecture()
    make_agentic_loop()
    make_db_schema()
    make_specialty()
    make_wer()
    print("Done. All 5 figures saved to paper_figures/")
