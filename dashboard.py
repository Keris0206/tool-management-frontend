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

# -----------------------------
# 3️⃣ Fetch summary
# -----------------------------
@st.cache_data(ttl=60)
def get_summary():
    try:
        response = requests.get(f"{API_URL}/tools/summary")
        if response.status_code == 200:
            return response.json()
        else:
            return {}
    except Exception:
        return {}

# -----------------------------
# 4️⃣ Display tools table
# -----------------------------
st.subheader("📋 All Tools")
tools_df = get_tools()

if not tools_df.empty:
    st.dataframe(tools_df)
else:
    st.write("No tools data available.")

# -----------------------------
# 5️⃣ Display summary cards
# -----------------------------
st.subheader("📊 Tools Summary")

summary = get_summary()

if summary:
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Tools", summary.get("total", 0))
    col2.metric("Available", summary.get("Available", 0))
    col3.metric("In Use", summary.get("In Use", 0))
    col4.metric("Maintenance", summary.get("Maintenance", 0))
else:
    st.write("No summary data available.")

# -----------------------------
# 6️⃣ Tool check-in / check-out
# -----------------------------
st.subheader("🔄 Update Tool Status")

tool_id_input = st.text_input("Enter Tool ID to check-in/out")
operator_name = st.text_input("Operator Name")
action = st.radio("Action", ["checkout", "return"])

if st.button("Submit Action"):

    if not tool_id_input or not operator_name:
        st.warning("Please enter Tool ID and Operator Name")

    else:
        try:
            response = requests.post(
                f"{API_URL}/tool/{tool_id_input}/action",
                data={
                    "operator": operator_name,
                    "action": action
                }
            )

            if response.status_code == 200:
                st.success(f"Action '{action}' recorded successfully!")

                # refresh dashboard
                st.cache_data.clear()
                st.rerun()

            else:
                st.error(response.json().get("error", "Failed to update tool"))

        except Exception as e:
            st.error(f"Error: {e}")

# -----------------------------
# 7️⃣ Tool usage chart
# -----------------------------
st.subheader("📈 Tool Usage Over Time")

history_df = pd.DataFrame()

try:

    history_response = requests.get(f"{API_URL}/export/history")

    if history_response.status_code == 200:

        history_df = pd.DataFrame(history_response.json())

        if not history_df.empty:

            sg_tz = pytz.timezone("Asia/Singapore")

            history_df["checkout_time"] = pd.to_datetime(
                history_df["checkout_time"],
                errors="coerce",
                utc=True
            ).dt.tz_convert(sg_tz)

            history_df["return_time"] = pd.to_datetime(
                history_df["return_time"],
                errors="coerce",
                utc=True
            ).dt.tz_convert(sg_tz)

            now_sg = datetime.now(sg_tz)

            history_df["duration_minutes"] = history_df.apply(
                lambda row:
                row["duration_minutes"]
                if pd.notnull(row["duration_minutes"])
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

    else:
        st.write("Failed to fetch history from backend.")

except Exception as e:
    st.write(f"Error fetching history: {e}")

# -----------------------------
# 8️⃣ Tool Status Pie Chart
# -----------------------------
st.subheader("📊 Tool Status Distribution")

if not tools_df.empty and "status" in tools_df.columns:

    fig_status = px.pie(
        tools_df,
        names="status",
        title="Tool Status Distribution"
    )

    st.plotly_chart(fig_status, use_container_width=True)

else:
    st.write("No tools data available for status chart.")

# -----------------------------
# 9️⃣ Tools by Process
# -----------------------------
st.subheader("🏭 Tools by Process")

if not tools_df.empty and "process" in tools_df.columns:

    process_count = tools_df.groupby("process").size().reset_index(name="count")

    fig_process = px.bar(
        process_count,
        x="process",
        y="count",
        title="Number of Tools per Process"
    )

    st.plotly_chart(fig_process, use_container_width=True)

else:
    st.write("No process data available.")

# -----------------------------
# 🔟 Tools by Machine
# -----------------------------
st.subheader("🛠 Tools by Machine")

if not tools_df.empty and "machine" in tools_df.columns:

    machine_count = tools_df.groupby("machine").size().reset_index(name="count")

    fig_machine = px.bar(
        machine_count,
        x="machine",
        y="count",
        title="Number of Tools per Machine"
    )

    st.plotly_chart(fig_machine, use_container_width=True)

else:
    st.write("No machine data available.")

# -----------------------------
# 1️⃣1️⃣ Tool Activity Log
# -----------------------------
st.subheader("📝 Tool Activity Log")

if not history_df.empty:

    history_df["action"] = history_df["return_time"].apply(
        lambda x: "Returned" if pd.notnull(x) else "Checked Out"
    )

    log_df = history_df[
        [
            "tool_id",
            "tool_name",
            "user",
            "action",
            "checkout_time",
            "return_time",
            "duration_minutes"
        ]
    ]

    log_df = log_df.sort_values(
        by="checkout_time",
        ascending=False
    )

    # Search operator
    search_user = st.text_input("🔍 Search Operator")

    if search_user:
        log_df = log_df[
            log_df["user"].str.contains(search_user, case=False)
        ]

    st.dataframe(log_df, use_container_width=True)

    # Download logs
    csv = log_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="⬇ Download Logs",
        data=csv,
        file_name="tool_activity_logs.csv",
        mime="text/csv"
    )

else:
    st.write("No tool activity logs available.")

# -----------------------------
# 1️⃣2️⃣ Filter tools
# -----------------------------
st.subheader("🔍 Filter Tools")

status_filter = st.selectbox(
    "Filter by Status",
    ["All", "Available", "In Use", "Maintenance"]
)

if status_filter != "All":
    filtered_df = tools_df[tools_df["status"] == status_filter]
    st.dataframe(filtered_df)