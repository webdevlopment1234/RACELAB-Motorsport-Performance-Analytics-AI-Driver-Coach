"""RACELAB skeuomorphic + parallax skin for the Streamlit dashboard.

Applies the pen.dev redesign (brushed metal, carbon fibre, chrome gauges,
LED indicators, parallax hero) to the Streamlit UI via injected CSS/HTML.
"""

from __future__ import annotations

import streamlit as st

THEME_CSS = """
<style>
/* ---------- global raceroom ---------- */
:root {
  --metal-dark: #23262b;
  --metal-light: #3a3f47;
  --metal-glow: #4d545e;
  --carbon: #14161a;
  --carbon-hi: #1f232a;
  --leather: #2a1e16;
  --leather-stitch: #8a5a3a;
  --chrome: #b8c0cc;
  --led-red: #ff3b30;
  --led-green: #34c759;
  --led-amber: #ff9f0a;
  --led-blue: #0a84ff;
  --arena: #0b0d10;
  --screen-text: #e8ebf0;
  --screen-dim: #8f95a0;
}

.stApp {
  background:
    radial-gradient(1200px 700px at 80% -10%, #1c2129 0%, rgba(12,14,17,0) 60%),
    radial-gradient(900px 600px at -10% 105%, #18201d 0%, rgba(12,14,17,0) 55%),
    repeating-linear-gradient(135deg, #0a0c0f 0px, #0a0c0f 2px, #0d0f13 2px, #0d0f13 4px),
    #07080a;
  color: var(--screen-text);
}
.stApp::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(transparent, transparent 35%,
      rgba(255,255,255,0.02) 35%, rgba(255,255,255,0.02) 36%);
  background-size: 100% 44px;
  animation: raceline 14s linear infinite;
  opacity: 0.35;
}
@keyframes raceline {
  from { background-position: 0 0; }
  to   { background-position: 0 44px; }
}

[data-testid="stHeader"] { background: transparent; }

/* scrollbar */
::-webkit-scrollbar { width: 12px; height: 12px; }
::-webkit-scrollbar-track {
  background: repeating-linear-gradient(135deg, #0b0d10 0, #0b0d10 2px, #11141a 2px, #11141a 4px);
}
::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, #3a3f47, #23262b);
  border-radius: 6px;
  border: 2px solid #0b0d10;
}

/* ---------- brushed-metal sidebar ---------- */
[data-testid="stSidebar"] {
  background:
    radial-gradient(220px 320px at 50% 0%, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0) 55%),
    repeating-linear-gradient(0deg,
      #3a3f47 0px, #31363d 1px, #2b2f36 2px, #373c43 3px, #3a3f47 4px),
    linear-gradient(180deg, #363b42, #22252a);
  border-right: 2px solid #000;
  box-shadow: inset -4px 0 8px rgba(0,0,0,0.55), inset 2px 0 2px rgba(255,255,255,0.08);
}
[data-testid="stSidebar"]::before {
  content: "RACELAB";
  display: block;
  padding: 18px 20px 10px;
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 26px;
  font-weight: 700;
  font-style: italic;
  letter-spacing: 3px;
  color: var(--screen-text);
  text-shadow: 1px 1px 0 #000, -1px -1px 0 rgba(255,255,255,0.15);
  border-bottom: 2px solid rgba(0,0,0,0.75);
  box-shadow: 0 1px 0 rgba(255,255,255,0.12);
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { font-family: "JetBrains Mono", Consolas, monospace; }

/* nav radio styled as LED channels */
[data-testid="stSidebar"] [role="radiogroup"] label {
  background: linear-gradient(180deg, #2b2f36, #20232a);
  border: 1px solid rgba(0,0,0,0.6);
  border-radius: 6px;
  padding: 8px 12px;
  margin: 3px 0;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 2px 3px rgba(0,0,0,0.5);
  transition: transform 0.08s ease;
  font-weight: 600;
  letter-spacing: 1px;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { transform: translateX(3px); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: linear-gradient(180deg, #e10600, #8a0d00);
  box-shadow: inset 0 1px 2px rgba(255,255,255,0.4), 0 0 14px rgba(225,6,0,0.45);
  color: #fff;
}
[data-testid="stSidebar"] [role="radiogroup"] label span { color: inherit; }

/* ---------- skeuomorphic panels ---------- */
.skeuo-panel {
  background: linear-gradient(180deg, #2b2f36, #23262b 55%, #1a1d22);
  border: 1px solid #4d545e;
  border-radius: 10px;
  padding: 14px 16px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.14), inset 0 -3px 8px rgba(0,0,0,0.5),
              0 4px 12px rgba(0,0,0,0.55);
  position: relative;
}
.skeuo-panel::before, .skeuo-panel::after {
  content: "";
  position: absolute;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #8f95a0, #23262b);
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.7);
}
.skeuo-panel::before { top: 5px; left: 5px; }
.skeuo-panel::after { bottom: 5px; right: 5px; }

.skeuo-label {
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 11px;
  letter-spacing: 2px;
  color: var(--screen-dim);
}
.skeuo-value {
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--screen-text);
  text-shadow: 0 1px 0 #000;
}

/* ---------- LED status pill ---------- */
.led {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  margin-right: 7px;
  vertical-align: middle;
  background: radial-gradient(circle at 35% 30%, #fff, var(--led-green) 40%, #0f6a20);
  box-shadow: 0 0 8px var(--led-green);
}
.led.red  { background: radial-gradient(circle at 35% 30%, #fff, var(--led-red) 40%, #6f0c04); box-shadow: 0 0 8px var(--led-red); }
.led.amber{ background: radial-gradient(circle at 35% 30%, #fff, var(--led-amber) 40%, #703f00); box-shadow: 0 0 8px var(--led-amber); }
.led.blue { background: radial-gradient(circle at 35% 30%, #fff, var(--led-blue) 40%, #0a3d7a); box-shadow: 0 0 8px var(--led-blue); }

/* ---------- chrome gauge ---------- */
.gauge-wrap { text-align: center; }
.gauge {
  --val: -270deg;
  width: 128px; height: 128px;
  margin: 0 auto;
  border-radius: 50%;
  position: relative;
  background: conic-gradient(from 225deg, #34c759 var(--val), #ff9f0a calc(var(--val) * 0.94), #ff3b30 0deg);
  padding: 11px;
  box-shadow: inset 0 2px 6px rgba(255,255,255,0.25), inset 0 -3px 8px rgba(0,0,0,0.6),
              0 6px 14px rgba(0,0,0,0.6);
}
.gauge::after {
  content: "";
  position: absolute;
  inset: 11px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #3a3f47, #14161a 75%);
  box-shadow: inset 0 0 12px rgba(0,0,0,0.9), inset 0 1px 2px rgba(255,255,255,0.25);
}
.gauge b {
  position: absolute; inset: 0 0 30% 0;
  margin: auto;
  z-index: 2;
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 26px;
  color: var(--screen-text);
  text-shadow: 0 1px 0 #000;
}
.gauge small {
  position: absolute; inset: 56% 0 0 0;
  margin: auto; z-index: 2;
  font-family: "JetBrains Mono", Consolas, monospace;
  letter-spacing: 2px; font-size: 10px;
  color: var(--screen-dim);
}

/* ---------- parallax hero ---------- */
.parallax-hero {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 18px;
  border: 1px solid #4d545e;
  background: linear-gradient(180deg, #0d0f13, #07080a);
  box-shadow: 0 10px 30px rgba(0,0,0,0.6);
}
.parallax-hero .band {
  position: absolute;
  height: 90px;
  filter: blur(1px);
}
.parallax-hero .band.b1 { top: 44px;  left: -10%; width: 130%; transform: rotate(-3deg); background: rgba(225,6,0,0.20); animation: drift 9s ease-in-out infinite alternate; }
.parallax-hero .band.b2 { top: 120px; left: -14%; width: 140%; transform: rotate(-3deg); background: rgba(255,159,10,0.15); animation: drift 12s ease-in-out infinite alternate-reverse; }
.parallax-hero .band.b3 { top: 200px; left: -20%; width: 150%; transform: rotate(-3deg); background: rgba(10,132,255,0.12); animation: drift 15s ease-in-out infinite alternate; }
@keyframes drift {
  from { left: -25%; } to { left: -5%; }
}
.parallax-hero .field { background-attachment: fixed; background-size: cover; }
.parallax-hero .hero-inner { position: relative; padding: 26px 30px 20px; z-index: 2; }
.hero-title {
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 40px; font-weight: 700; font-style: italic;
  letter-spacing: 4px; color: var(--screen-text);
  text-shadow: 0 0 24px rgba(225,6,0,0.35), 2px 2px 0 #000;
}
.hero-sub { color: var(--screen-dim); letter-spacing: 1px; font-size: 14px; margin-top: 2px; }
.hero-ticker {
  margin-top: 14px;
  border-top: 2px solid rgba(0,0,0,0.7);
  background: rgba(0,0,0,0.45);
  display: flex;
  gap: 22px;
  overflow: hidden;
  white-space: nowrap;
  padding: 9px 0 3px;
}
.hero-ticker span {
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 13px; color: var(--screen-text);
}
.hero-ticker .live { color: var(--led-red); font-weight: 700; }

/* ---------- parallax hero (with fixed background) ---------- */
.parallax-hero.fixed::before {
  content: "";
  position: absolute; inset: 0;
  background:
    linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.55) 100%),
    repeating-linear-gradient(-45deg, rgba(255,255,255,0.05) 0 2px, transparent 2px 10px);
}

/* ---------- race intelligence ---------- */
.intel-label {
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 3px;
  color: var(--screen-dim);
  text-transform: uppercase;
  border-bottom: 1px solid #3a3f47;
  padding-bottom: 6px;
  margin-bottom: 10px;
}
.intel-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  margin: 3px 0;
  border-radius: 6px;
  background: linear-gradient(180deg, #1f232a, #171a1f);
  border: 1px solid #2b2f36;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 2px 4px rgba(0,0,0,0.4);
}
.intel-pos {
  width: 34px;
  text-align: center;
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 18px;
  font-weight: 700;
  color: var(--screen-text);
  background: linear-gradient(180deg, #33383f, #20232a);
  border-radius: 5px;
  padding: 2px 0;
}
.intel-pos.p1 { color: #ffd700; }
.intel-pos.p2 { color: #c0c7d1; }
.intel-pos.p3 { color: #cd7f32; }
.intel-name {
  flex: 1;
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 1px;
}
.intel-colourbar { width: 6px; border-radius: 3px; align-self: stretch; }
.intel-gap {
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 12px;
  color: var(--screen-dim);
}
.intel-chip {
  display: inline-block;
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 11px;
  letter-spacing: 1px;
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid #4d545e;
  background: linear-gradient(180deg, #2b2f36, #1e2126);
  margin: 2px 4px 2px 0;
  color: var(--screen-text);
}

/* ---------- dataframes: dark carbon ---------- */
[data-testid="stDataFrame"], .stDataFrame {
  border: 1px solid #3a3f47;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 5px 14px rgba(0,0,0,0.5);
}
[data-testid="stDataFrame"] th {
  background: linear-gradient(180deg, #33383f, #23262b) !important;
  color: var(--screen-dim) !important;
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 11px !important;
  letter-spacing: 1px;
}
[data-testid="stDataFrame"] td {
  background: #0d0f13 !important;
  color: var(--screen-text) !important;
  font-family: "JetBrains Mono", Consolas, monospace;
}

/* ---------- inputs / buttons ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  background: linear-gradient(180deg, #3a3f47, #20232a);
  color: var(--screen-text);
  border: 1px solid #4d545e;
  border-radius: 6px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.18), 0 2px 4px rgba(0,0,0,0.5);
  font-weight: 600;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  background: linear-gradient(180deg, #e10600, #8a0d00) !important;
  color: #fff !important;
}
.stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"] > div {
  background: #0d0f13;
  color: var(--screen-text);
  border: 1px solid #3a3f47;
  border-radius: 6px;
}
.stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #3a3f47; }
.stTabs [data-baseweb="tab"] { color: var(--screen-dim); font-weight: 600; }
.stTabs [data-baseweb="tab"][aria-selected="true"] {
  color: var(--led-red);
  border-bottom: 2px solid var(--led-red);
}

/* metrics (native, kept minimal) */
[data-testid="stMetric"] {
  background: linear-gradient(180deg, #2b2f36, #1a1d22);
  border: 1px solid #4d545e;
  border-radius: 8px;
  padding: 10px 14px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.12), 0 3px 8px rgba(0,0,0,0.5);
}
[data-testid="stMetricLabel"] { color: var(--screen-dim) !important; letter-spacing: 1px; }
[data-testid="stMetricValue"] { color: var(--screen-text) !important; font-family: "JetBrains Mono", Consolas, monospace; }

blockquote {
  border-left: 3px solid var(--led-red);
  background: rgba(225,6,0,0.06);
}
.info, [data-testid="stAlert"] { border-radius: 6px; }
</style>
"""


def apply_skin() -> None:
    """Inject the RACELAB skin CSS (call once after set_page_config)."""
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str, ticker: list[str] | None = None,
         live: bool = False, fixed: bool = False) -> None:
    """Render a parallax hero banner with optional speed-band ticker."""
    bands = ""
    if fixed:
        bands = '<div class="band field"></div>'
    else:
        bands = ('<div class="band b1"></div><div class="band b2"></div>'
                 '<div class="band b3"></div>')
    ticker_html = ""
    if ticker:
        items = "".join(
            f'<span class="live">&#9679;</span><span>{t}</span>' if live else f"<span>{t}</span>"
            for t in ticker
        )
        ticker_html = f'<div class="hero-ticker">{items}</div>'
    st.markdown(
        f'<div class="parallax-hero {"fixed" if fixed else ""}">{bands}'
        f'<div class="hero-inner"><div class="hero-title">{title}</div>'
        f'<div class="hero-sub">{subtitle}</div>{ticker_html}</div></div>',
        unsafe_allow_html=True,
    )


def led(color: str = "green") -> str:
    """Return an LED status marker: green (default), red, or amber."""
    return f'<span class="led {color}"></span>'


def pod(label: str, value: str, led_colour: str = "green") -> str:
    """Return a skeuomorphic brushed-metal pod with LED + rivets."""
    return (
        f'<div class="skeuo-panel">{led(led_colour)}<div class="skeuo-label">{label}</div>'
        f'<div class="skeuo-value">{value}</div></div>'
    )


def gauge(value: str, label: str, pct: float = 0.75, colour: str = "54,199,89") -> str:
    """Return a chrome circular gauge. pct 0..1 maps arc sweep."""
    pct = max(0.0, min(1.0, pct))
    deg = int(-270 + 270 * pct)
    return (
        f'<div class="gauge-wrap"><div class="gauge" style="--val:{deg}deg;">'
        f"<b>{value}</b><small>{label}</small></div></div>"
    )


def intel_label(label: str) -> str:
    """Render a section heading label (TIMING / TRACK MAP / ...)."""
    return f'<div class="intel-label">{label}</div>'


def intel_row(position: str, name: str, gap: str = "",
              colour: str = "#3a3f47") -> str:
    """Render one timing row: position chip, team bar, name, gap."""
    medal = ""
    if position.lstrip("#") in ("1", "2", "3"):
        medal = f" p{position.lstrip('#')}"
    return (
        f'<div class="intel-row"><span class="intel-pos{medal}">{position}</span>'
        f'<span class="intel-colourbar" style="background:{colour}"></span>'
        f'<span class="intel-name">{name}</span>'
        f'<span class="intel-gap">{gap}</span></div>'
    )


def intel_chip(text: str) -> str:
    """Render a small pill label (e.g. compound MED/HARD/SOFT)."""
    return f'<span class="intel-chip">{text}</span>'


def stats_grid(columns: list, *pods: str) -> None:
    """Render pods into streamlit columns ('columns' object from st.columns)."""
    for col, pod_html in zip(columns, pods):
        with col:
            st.markdown(pod_html, unsafe_allow_html=True)