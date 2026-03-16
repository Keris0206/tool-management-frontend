import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import plotly.express as px
import pytz
import os

# -----------------------------
# 1️⃣ API base URL
# -----------------------------
API_URL = os.environ.get("API_URL", "https://tool-management-backend-lscs.onrender.com")

st.set_page_config(page_title="Tool Management Dashboard", layout="wide")
st.title("🛠 Tool Management Dashboard")

# ✅ Auto-refresh every 60 seconds
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=60_000, key="dashboard_refresh")  # 60 seconds

# -----------------------------
# 2️⃣ Fetch tools data
# -----------------------------
@st.cache_data(ttl=60)
def get_tools():
    try:
        response = requests.get(f"{API_URL}/tools")
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        else:
            st.error("Failed to fetch tools")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

tools_df = get_tools()

# -----------------------------
# 3️⃣ Fetch history data (cached)
# -----------------------------
@st.cache_data(ttl=60)
def get_history():
    try:
        response = requests.get(f"{API_URL}/export/history")
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        else:
            st.warning("Failed to fetch history from backend.")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching history: {e}")
        return pd.DataFrame()

history_df = get_history()

# -----------------------------
# 4️⃣ Filter Tools
# -----------------------------
st.subheader("🔍 Filter Tools")
status_filter = st.selectbox(
    "Filter by Status",
    ["All", "Available", "In Use", "Maintenance"]
)

# -----------------------------
# 5️⃣ Sync tool status with history
# -----------------------------
if not history_df.empty and not tools_df.empty:
    # Ensure datetime format
    history_df["checkout_time"] = pd.to_datetime(history_df["checkout_time"], errors="coerce", utc=True)
    history_df["return_time"] = pd.to_datetime(history_df["return_time"], errors="coerce", utc=True)

    # Compute current status for each tool
    def compute_status(tool_id):
        tool_history = history_df[history_df["tool_id"] == tool_id]
        if tool_history.empty:
            return "Available"
        if tool_history["return_time"].isnull().any():
            return "In Use"
        return "Available"

    tools_df["status"] = tools_df["tool_id"].apply(compute_status)

# Apply status filter
if status_filter != "All" and not tools_df.empty:
    filtered_tools_df = tools_df[tools_df["status"] == status_filter]
else:
    filtered_tools_df = tools_df.copy()

# -----------------------------
# 6️⃣ Display tools table
# -----------------------------
st.subheader("📋 All Tools")
if not filtered_tools_df.empty:
    st.dataframe(filtered_tools_df, use_container_width=True)
else:
    st.write("No tools data available.")

# -----------------------------
# 7️⃣ Tools Summary
# -----------------------------
summary = {
    "total": len(filtered_tools_df),
    "Available": len(filtered_tools_df[filtered_tools_df["status"]=="Available"]),
    "In Use": len(filtered_tools_df[filtered_tools_df["status"]=="In Use"]),
    "Maintenance": len(filtered_tools_df[filtered_tools_df["status"]=="Maintenance"])
}

st.subheader("📊 Tools Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Tools", summary["total"])
col2.metric("Available", summary["Available"])
col3.metric("In Use", summary["In Use"])
col4.metric("Maintenance", summary["Maintenance"])

# -----------------------------
# 8️⃣ Tool Usage Chart
# -----------------------------
st.subheader("📈 Tool Usage Over Time")
if not history_df.empty:
    sg_tz = pytz.timezone("Asia/Singapore")
    history_df["checkout_time"] = history_df["checkout_time"].dt.tz_convert(sg_tz)
    history_df["return_time"] = history_df["return_time"].dt.tz_convert(sg_tz)
    now_sg = datetime.now(sg_tz)

    history_df["duration_minutes"] = history_df.apply(
        lambda row: row["duration_minutes"] if pd.notnull(row["duration_minutes"])
        else (now_sg - row["checkout_time"]).total_seconds() / 60,
        axis=1
    )

    history_df["status"] = history_df["return_time"].apply(
        lambda x: "Completed" if pd.notnull(x) else "In Progress"
    )

    fig = px.bar(
        history_df,
        x="tool_name",
        y="duration_minutes",
        color="status",
        title="Tool Usage Duration (minutes)",
        hover_data=["user", "checkout_time", "return_time"]
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.write("No history data available.")

# -----------------------------
# 9️⃣ Live Tool Status
# -----------------------------
st.subheader("📡 Live Tool Status")
if not history_df.empty:
    sg_tz = pytz.timezone("Asia/Singapore")
    now_sg = datetime.now(sg_tz)
    history_df["checkout_time"] = history_df["checkout_time"].dt.tz_convert(sg_tz)
    history_df["return_time"] = history_df["return_time"].dt.tz_convert(sg_tz)
    history_df["user"] = history_df.get("user", "")
    history_df["returned_by"] = history_df.get("returned_by", "")

    latest_history = history_df.sort_values("checkout_time", ascending=False).groupby("tool_id").first().reset_index()

    in_use = latest_history[latest_history["return_time"].isnull()].copy()
    if not in_use.empty:
        in_use["current_duration"] = (now_sg - in_use["checkout_time"]).dt.total_seconds() / 60
        st.markdown("### 🔧 Tools Currently In Use")
        st.dataframe(
            in_use[["tool_id","tool_name","user","checkout_time","current_duration"]].rename(
                columns={
                    "tool_id": "Tool ID",
                    "tool_name": "Tool Name",
                    "user": "Checked Out By",
                    "checkout_time": "Checkout Time",
                    "current_duration": "Duration (minutes)"
                }
            ),
            use_container_width=True
        )
    else:
        st.write("No tools currently in use.")

    returned_recent = latest_history[latest_history["return_time"].notnull() &
                                     (latest_history["return_time"] > now_sg - pd.Timedelta(hours=24))].copy()
    if not returned_recent.empty:
        st.markdown("### 🔄 Recently Returned Tools")
        st.dataframe(
            returned_recent[["tool_id","tool_name","user","returned_by","checkout_time","return_time"]].rename(
                columns={
                    "tool_id": "Tool ID",
                    "tool_name": "Tool Name",
                    "user": "Checked Out By",
                    "returned_by": "Returned By",
                    "checkout_time": "Checkout Time",
                    "return_time": "Return Time"
                }
            ),
            use_container_width=True
        )
    else:
        st.write("No tools returned in the last 24 hours.")

# -----------------------------
# 10️⃣ Tool Status Distribution
# -----------------------------
st.subheader("📊 Tool Status Distribution")
if not tools_df.empty:
    status_counts = tools_df["status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    fig_status = px.pie(status_counts, names="status", values="count", title="Tool Status Distribution")
    st.plotly_chart(fig_status, use_container_width=True)
else:
    st.write("No tools data available for status chart.")

# -----------------------------
# 11️⃣ Tools by Process
# -----------------------------
st.subheader("🏭 Tools by Process")
if not filtered_tools_df.empty and "process" in filtered_tools_df.columns:
    process_count = filtered_tools_df.groupby("process").size().reset_index(name="count")
    fig_process = px.bar(process_count, x="process", y="count", title="Number of Tools per Process")
    st.plotly_chart(fig_process, use_container_width=True)
else:
    st.write("No process data available.")

# -----------------------------
# 12️⃣ Tools by Machine
# -----------------------------
st.subheader("🛠 Tools by Machine")
if not filtered_tools_df.empty and "machine" in filtered_tools_df.columns:
    machine_count = filtered_tools_df.groupby("machine").size().reset_index(name="count")
    fig_machine = px.bar(machine_count, x="machine", y="count", title="Number of Tools per Machine")
    st.plotly_chart(fig_machine, use_container_width=True)
else:
    st.write("No machine data available.")

# -----------------------------
# 13️⃣ Tool Activity Log
# -----------------------------
st.subheader("📝 Tool Activity Log")
if not history_df.empty:
    history_df["action"] = history_df["action"].replace({"CHECKOUT": "Checked Out", "RETURN": "Returned"})
    history_df["returned_by"] = history_df.get("returned_by", "")
    history_df["return_time"] = history_df.get("return_time", pd.NaT)
    sg_tz = pytz.timezone("Asia/Singapore")
    now_sg = datetime.now(sg_tz)
    history_df["duration_minutes"] = history_df.apply(
        lambda row: row["duration_minutes"] if pd.notnull(row["duration_minutes"])
        else (now_sg - row["checkout_time"].tz_convert(sg_tz)).total_seconds()/60,
        axis=1
    )
    history_df["display_return_time"] = history_df["return_time"].apply(lambda x: x if pd.notnull(x) else "In Progress")

    log_columns = ["tool_id","tool_name","user","returned_by","action","checkout_time","display_return_time","duration_minutes"]
    log_df = history_df[log_columns].sort_values(by="checkout_time", ascending=False)

    search_user = st.text_input("Search Operator")
    if search_user:
        log_df = log_df[
            log_df["user"].str.contains(search_user, case=False) |
            log_df["returned_by"].str.contains(search_user, case=False)
        ]

    st.dataframe(log_df, use_container_width=True)

    csv = log_df.rename(columns={"display_return_time": "return_time"}).to_csv(index=False).encode("utf-8")
    st.download_button("Download Logs", csv, "tool_logs.csv", "text/csv")
else:
    st.write("No tool logs available")