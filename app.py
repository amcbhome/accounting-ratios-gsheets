# app.py
import time
from typing import Optional
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Accounting Ratios Dashboard", page_icon="📈")
st.title("📈 Current & Acid-Test (Quick) Ratios")
st.caption("Reads the latest single record from Google Sheets (row 2).")

REFRESH_SECONDS = 5

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

def read_latest() -> Optional[pd.DataFrame]:
    ws = _worksheet(_client())
    vals = ws.get_values("A1:D2")
    if len(vals) < 2 or len(vals[1]) < 4:
        return None
    return pd.DataFrame([vals[1]], columns=vals[0])

# --- Ratios -------------------------------------------------------------------
def compute_ratios(ca: float, cl: float, inv: float):
    if cl <= 0:
        return None, None
    return ca / cl, (ca - inv) / cl

# --- UI -----------------------------------------------------------------------
df = read_latest()
if df is None or df.empty:
    st.warning("No data yet. Open **🔁 Data Generator** to start emitting values.")
else:
    row = df.iloc[0]
    try:
        ca = float(row["current_assets"])
        cl = float(row["current_liabilities"])
        inv = float(row["inventory"])
    except Exception:
        st.error("Sheet has non-numeric values in row 2 (A2:D2).")
        st.stop()

    cr, qr = compute_ratios(ca, cl, inv)

    cols = st.columns(3)
    cols[0].metric("Current Assets (£)", f"{ca:,.2f}")
    cols[1].metric("Current Liabilities (£)", f"{cl:,.2f}")
    cols[2].metric("Inventory (£)", f"{inv:,.2f}")

    st.divider()
    r = st.columns(2)
    r[0].metric("Current Ratio", f"{cr:.2f}" if cr is not None else "—")
    r[1].metric("Acid-Test (Quick) Ratio", f"{qr:.2f}" if qr is not None else "—")

    if "timestamp_utc" in row and row["timestamp_utc"]:
        st.caption(f"Last updated (UTC): {row['timestamp_utc']}  •  Source: Google Sheets")

time.sleep(REFRESH_SECONDS)
st.rerun()
