# pages/1_🔁_Data_Generator.py
import time
from datetime import datetime, timezone
from typing import Optional
import numpy as np
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Data Generator • Current vs Quick Ratio", page_icon="🔁")
st.title("🔁 Synthetic Data Generator")
st.caption("Writes one fresh record every 30 seconds to Google Sheets (row 2): current assets, current liabilities, and inventory.")

INTERVAL_SECONDS = 30

# --- Google Sheets helpers ----------------------------------------------------
def _client() -> gspread.Client:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

def _worksheet(cli: gspread.Client) -> gspread.Worksheet:
    ss = cli.open_by_key(st.secrets["gsheet_id"])
    ws_name = st.secrets.get("gsheet_worksheet", "latest")
    try:
        return ss.worksheet(ws_name)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=ws_name, rows=10, cols=6)
        ws.update("A1:D1", [["timestamp_utc", "current_assets", "current_liabilities", "inventory"]])
        return ws

def write_row(record: dict) -> None:
    ws = _worksheet(_client())
    ws.update("A1:D1", [["timestamp_utc", "current_assets", "current_liabilities", "inventory"]])
    ws.update("A2:D2", [[
        record["timestamp_utc"],
        record["current_assets"],
        record["current_liabilities"],
        record["inventory"],
    ]])

def read_latest() -> Optional[pd.DataFrame]:
    ws = _worksheet(_client())
    vals = ws.get_values("A1:D2")
    if len(vals) < 2 or len(vals[1]) < 4:
        return None
    return pd.DataFrame([vals[1]], columns=vals[0])

# --- Synthetic snapshot -------------------------------------------------------
def generate_values(rng: np.random.Generator) -> dict:
    ca = float(rng.lognormal(mean=11.0, sigma=0.35))
    ca = float(np.clip(ca, 50_000, 250_000))
    inv = float(rng.uniform(0.10, 0.60) * ca)
    cl  = float(rng.uniform(0.30, 1.10) * ca)
    inv = min(inv, ca)
    cl  = max(cl, 1.0)
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "current_assets": round(ca, 2),
        "current_liabilities": round(cl, 2),
        "inventory": round(inv, 2),
    }

# --- Timing -------------------------------------------------------------------
if "last_generate_ts" not in st.session_state:
    st.session_state.last_generate_ts = 0.0

def due(now: float) -> bool:
    return (now - st.session_state.last_generate_ts) >= INTERVAL_SECONDS

# --- UI -----------------------------------------------------------------------
c1, _ = st.columns([1, 3])
manual = c1.button("🔄 Generate now")

rng = np.random.default_rng()
now = time.time()

if manual or due(now):
    write_row(generate_values(rng))
    st.session_state.last_generate_ts = now

df = read_latest()

st.subheader("Latest Emission")
if df is not None and not df.empty:
    row = df.iloc[0]
    ca = float(row["current_assets"]); cl = float(row["current_liabilities"]); inv = float(row["inventory"])
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Assets (£)", f"{ca:,.2f}")
    m2.metric("Current Liabilities (£)", f"{cl:,.2f}")
    m3.metric("Inventory (£)", f"{inv:,.2f}")
    st.caption(f"Last updated: {row['timestamp_utc']} (UTC)")
else:
    st.info("No data yet — generating the first record...")

elapsed = time.time() - st.session_state.last_generate_ts
remaining = max(0, INTERVAL_SECONDS - int(elapsed))
st.write(f"Next auto-generate in **{remaining}s**.")
st.progress(1.0 - (remaining / INTERVAL_SECONDS) if INTERVAL_SECONDS else 1.0)

time.sleep(1)
st.rerun()
