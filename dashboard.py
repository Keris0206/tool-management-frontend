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

st_autorefresh(interval=10000, key="refresh")  # refresh every 10s


# ============================================================
# 5️⃣ Fetch Tools Data
# ============================================================

@st.cache_data(ttl=30)
def get_tools():

    try:
        response = requests.get(f"{API_URL}/tools")

        if response.status_code == 200:
            return pd.DataFrame(response.json())

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
            return pd.DataFrame(response.json())

    except Exception as e:
        st.error(f"Error fetching history: {e}")

    return pd.DataFrame()


history_df = get_history()


# ============================================================
# 7️⃣ Process History Data
# ============================================================

sg_tz = pytz.timezone("Asia/Singapore")

if not history_df.empty:

    history_df["timestamp"] = pd.to_datetime(
        history_df["timestamp"],
        errors="coerce",
        utc=True
    ).dt.tz_convert(sg_tz)

    latest_history = (
        history_df
        .sort_values("timestamp", ascending=False)
        .groupby("tool_id")
        .first()
        .reset_index()
    )

else:

    latest_history = pd.DataFrame()


# ============================================================
# 8️⃣ Determine Current Tool Status
# ============================================================

if not latest_history.empty and not tools_df.empty:

    status_map = {}

    for _, row in latest_history.iterrows():

        if row["action"] == "CHECKOUT":
            status_map[row["tool_id"]] = "In Use"
        else:
            status_map[row["tool_id"]] = "Available"

    tools_df["status"] = tools_df["tool_id"].map(status_map).fillna("Available")


# ============================================================
# 9️⃣ Tool Summary
# ============================================================

st.subheader("📊 Tool Summary")

col1, col2, col3 = st.columns(3)

col1.metric("Total Tools", len(tools_df))

col2.metric(
    "Available",
    len(tools_df[tools_df["status"] == "Available"])
)

col3.metric(
    "In Use",
    len(tools_df[tools_df["status"] == "In Use"])
)


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

if not tools_df.empty:

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

    st.plotly_chart(
        fig_status,
        use_container_width=True
    )


# ============================================================
# 1️⃣2️⃣ Tools Currently In Use
# ============================================================

st.subheader("📡 Tools Currently In Use")

if not latest_history.empty:

    in_use = latest_history[
        latest_history["action"] == "CHECKOUT"
    ].copy()

    now = datetime.now(sg_tz)

    if not in_use.empty:

        in_use["duration_minutes"] = (
            now - in_use["timestamp"]
        ).dt.total_seconds() / 60

        st.dataframe(

            in_use[
                [
                    "tool_id",
                    "tool_name",
                    "user",
                    "timestamp",
                    "duration_minutes"
                ]
            ].rename(
                columns={
                    "tool_id": "Tool ID",
                    "tool_name": "Tool Name",
                    "user": "Operator",
                    "timestamp": "Checkout Time",
                    "duration_minutes": "Duration (minutes)"
                }
            ),

            use_container_width=True
        )

    else:

        st.write("No tools currently in use.")


# ============================================================
# 1️⃣3️⃣ Recently Returned Tools
# ============================================================

st.subheader("🔄 Recently Returned Tools")

if not latest_history.empty:

    returned = latest_history[
        latest_history["action"] == "RETURN"
    ]

    recent = returned[
        returned["timestamp"] >
        datetime.now(sg_tz) - pd.Timedelta(hours=24)
    ]

    if not recent.empty:

        st.dataframe(

            recent[
                [
                    "tool_id",
                    "tool_name",
                    "user",
                    "timestamp"
                ]
            ].rename(
                columns={
                    "tool_id": "Tool ID",
                    "tool_name": "Tool Name",
                    "user": "Returned By",
                    "timestamp": "Return Time"
                }
            ),

            use_container_width=True
        )

    else:

        st.write("No tools returned in the last 24 hours.")


# ============================================================
# 1️⃣4️⃣ Tool Usage Over Time
# ============================================================

st.subheader("📈 Tool Usage Over Time")

if not history_df.empty:

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

    st.plotly_chart(
        fig_usage,
        use_container_width=True
    )

else:

    st.write("No usage data available.")


# ============================================================
# 1️⃣5️⃣ Operator Usage Analytics
# ============================================================

st.subheader("👷 Operator Tool Usage")

if not history_df.empty:

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

    st.plotly_chart(
        fig_operator,
        use_container_width=True
    )

else:

    st.write("No operator data available.")


# ============================================================
# 1️⃣6️⃣ Longest Checked-Out Tools
# ============================================================

st.subheader("⏱ Longest Checked-Out Tools")

if not latest_history.empty:

    active_tools = latest_history[
        latest_history["action"] == "CHECKOUT"
    ].copy()

    now = datetime.now(sg_tz)

    if not active_tools.empty:

        active_tools["duration_minutes"] = (
            now - active_tools["timestamp"]
        ).dt.total_seconds() / 60

        longest = active_tools.sort_values(
            "duration_minutes",
            ascending=False
        ).head(10)

        st.dataframe(

            longest[
                [
                    "tool_id",
                    "tool_name",
                    "user",
                    "timestamp",
                    "duration_minutes"
                ]
            ].rename(
                columns={
                    "tool_id": "Tool ID",
                    "tool_name": "Tool Name",
                    "user": "Operator",
                    "timestamp": "Checkout Time",
                    "duration_minutes": "Duration (minutes)"
                }
            ),

            use_container_width=True
        )

    else:

        st.write("No tools currently checked out.")