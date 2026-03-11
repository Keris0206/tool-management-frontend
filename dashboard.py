# ============================================================
# 1️⃣ Import Libraries
# ============================================================

import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import plotly.express as px
import pytz
import os
from streamlit_autorefresh import st_autorefresh


# ============================================================
# 2️⃣ API Base URL
# ============================================================

API_URL = os.environ.get(
    "API_URL",
    "https://tool-management-backend-lscs.onrender.com"
)


# ============================================================
# 3️⃣ Page Configuration
# ============================================================

st.set_page_config(
    page_title="Tool Management Dashboard",
    layout="wide"
)

st.title("🛠 Intelligent Tool Management Dashboard")


# ============================================================
# 4️⃣ Auto Refresh
# ============================================================

st_autorefresh(interval=10000, key="refresh")  # refresh every 10 seconds


# ============================================================
# 5️⃣ Fetch Tools Data
# ============================================================

@st.cache_data(ttl=30)
def get_tools():

    try:
        response = requests.get(f"{API_URL}/tools")

        if response.status_code == 200:
            data = response.json()

            if isinstance(data, list):
                return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Error fetching tools: {e}")

    return pd.DataFrame()


tools_df = get_tools()


# ============================================================
# 6️⃣ Fetch Tool History
# ============================================================

@st.cache_data(ttl=30)
def get_history():

    try:
        response = requests.get(f"{API_URL}/export/history")

        if response.status_code == 200:
            data = response.json()

            if isinstance(data, list):
                return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Error fetching history: {e}")

    return pd.DataFrame()


history_df = get_history()


# ============================================================
# 7️⃣ Process History Data
# ============================================================

sg_tz = pytz.timezone("Asia/Singapore")
latest_history = pd.DataFrame()

if not history_df.empty:

    # Ensure timestamp column exists
    if "timestamp" in history_df.columns:

        history_df["timestamp"] = pd.to_datetime(
            history_df["timestamp"],
            errors="coerce",
            utc=True
        ).dt.tz_convert(sg_tz)

        if "tool_id" in history_df.columns:

            latest_history = (
                history_df
                .sort_values("timestamp", ascending=False)
                .groupby("tool_id")
                .first()
                .reset_index()
            )

    else:
        st.warning("History data does not contain timestamp column.")


# ============================================================
# 8️⃣ Determine Current Tool Status
# ============================================================

if not latest_history.empty and not tools_df.empty:

    if "tool_id" in tools_df.columns:

        status_map = {}

        for _, row in latest_history.iterrows():

            if "action" in row and row["action"] == "CHECKOUT":
                status_map[row["tool_id"]] = "In Use"
            else:
                status_map[row["tool_id"]] = "Available"

        tools_df["status"] = tools_df["tool_id"].map(status_map).fillna("Available")

else:

    if not tools_df.empty:
        tools_df["status"] = "Available"


# ============================================================
# 9️⃣ Tool Summary
# ============================================================

st.subheader("📊 Tool Summary")

col1, col2, col3 = st.columns(3)

col1.metric("Total Tools", len(tools_df))

if "status" in tools_df.columns:

    col2.metric(
        "Available",
        len(tools_df[tools_df["status"] == "Available"])
    )

    col3.metric(
        "In Use",
        len(tools_df[tools_df["status"] == "In Use"])
    )

else:

    col2.metric("Available", 0)
    col3.metric("In Use", 0)


# ============================================================
# 🔟 Tool Inventory Table
# ============================================================

st.subheader("📋 Tool Inventory")

if not tools_df.empty:

    st.dataframe(
        tools_df,
        use_container_width=True
    )

else:

    st.write("No tools available.")


# ============================================================
# 1️⃣1️⃣ Tool Status Distribution
# ============================================================

st.subheader("📊 Tool Status Distribution")

if not tools_df.empty and "status" in tools_df.columns:

    status_counts = (
        tools_df["status"]
        .value_counts()
        .reset_index()
    )

    status_counts.columns = ["status", "count"]

    fig_status = px.pie(
        status_counts,
        names="status",
        values="count",
        title="Tool Status Distribution"
    )

    st.plotly_chart(fig_status, use_container_width=True)

else:

    st.write("No tool status data available.")


# ============================================================
# 1️⃣2️⃣ Tools Currently In Use
# ============================================================

st.subheader("📡 Tools Currently In Use")

if not latest_history.empty and "action" in latest_history.columns:

    in_use = latest_history[
        latest_history["action"] == "CHECKOUT"
    ].copy()

    now = datetime.now(sg_tz)

    if not in_use.empty and "timestamp" in in_use.columns:

        in_use["duration_minutes"] = (
            now - in_use["timestamp"]
        ).dt.total_seconds() / 60

        display_cols = [
            c for c in [
                "tool_id",
                "tool_name",
                "user",
                "timestamp",
                "duration_minutes"
            ] if c in in_use.columns
        ]

        st.dataframe(
            in_use[display_cols],
            use_container_width=True
        )

    else:

        st.write("No tools currently in use.")

else:

    st.write("No tool usage data available.")


# ============================================================
# 1️⃣3️⃣ Recently Returned Tools
# ============================================================

st.subheader("🔄 Recently Returned Tools")

if not latest_history.empty and "action" in latest_history.columns:

    returned = latest_history[
        latest_history["action"] == "RETURN"
    ]

    if not returned.empty and "timestamp" in returned.columns:

        recent = returned[
            returned["timestamp"] >
            datetime.now(sg_tz) - pd.Timedelta(hours=24)
        ]

        if not recent.empty:

            display_cols = [
                c for c in [
                    "tool_id",
                    "tool_name",
                    "user",
                    "timestamp"
                ] if c in recent.columns
            ]

            st.dataframe(
                recent[display_cols],
                use_container_width=True
            )

        else:
            st.write("No tools returned in the last 24 hours.")

else:

    st.write("No return history available.")


# ============================================================
# 1️⃣4️⃣ Tool Usage Over Time
# ============================================================

st.subheader("📈 Tool Usage Over Time")

if not history_df.empty and "timestamp" in history_df.columns:

    usage_df = history_df.copy()

    usage_df["date"] = usage_df["timestamp"].dt.date

    usage_chart = (
        usage_df
        .groupby("date")
        .size()
        .reset_index(name="checkouts")
    )

    fig_usage = px.line(
        usage_chart,
        x="date",
        y="checkouts",
        markers=True,
        title="Tool Checkouts Per Day"
    )

    st.plotly_chart(fig_usage, use_container_width=True)

else:

    st.write("No usage data available.")


# ============================================================
# 1️⃣5️⃣ Operator Usage Analytics
# ============================================================

st.subheader("👷 Operator Tool Usage")

if not history_df.empty and "user" in history_df.columns:

    operator_usage = (
        history_df
        .groupby("user")
        .size()
        .reset_index(name="checkouts")
        .sort_values("checkouts", ascending=False)
    )

    fig_operator = px.bar(
        operator_usage,
        x="user",
        y="checkouts",
        title="Tool Usage by Operator"
    )

    st.plotly_chart(fig_operator, use_container_width=True)

else:

    st.write("No operator usage data available.")


# ============================================================
# 1️⃣6️⃣ Longest Checked-Out Tools
# ============================================================

st.subheader("⏱ Longest Checked-Out Tools")

if not latest_history.empty and "action" in latest_history.columns:

    active_tools = latest_history[
        latest_history["action"] == "CHECKOUT"
    ].copy()

    now = datetime.now(sg_tz)

    if not active_tools.empty and "timestamp" in active_tools.columns:

        active_tools["duration_minutes"] = (
            now - active_tools["timestamp"]
        ).dt.total_seconds() / 60

        longest = active_tools.sort_values(
            "duration_minutes",
            ascending=False
        ).head(10)

        display_cols = [
            c for c in [
                "tool_id",
                "tool_name",
                "user",
                "timestamp",
                "duration_minutes"
            ] if c in longest.columns
        ]

        st.dataframe(
            longest[display_cols],
            use_container_width=True
        )

    else:

        st.write("No tools currently checked out.")

else:

    st.write("No active checkout data.")