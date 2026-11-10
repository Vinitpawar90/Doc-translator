
import os
import hmac
import requests
import pandas as pd
import streamlit as st
import altair as alt

from dotenv import load_dotenv
from sqlalchemy import func

from backend.database import SessionLocal, Base, engine
from backend.models import (
    APIKey,
    TranslationHistory,
    DeepLUsageSnapshot
)

load_dotenv()

Base.metadata.create_all(bind=engine)

st.set_page_config(
    page_title="Translation API Admin",
    page_icon="🌐",
    layout="wide"
)

# ----------------------------------
# ADMIN LOGIN
# ----------------------------------

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

if not ADMIN_PASSWORD:
    st.error("ADMIN_PASSWORD is not configured.")
    st.stop()

if not st.session_state.get("authenticated", False):

    st.space(40)
    _, login_column, _ = st.columns([1, 1.8, 1])
    with login_column:
        with st.container(horizontal=True, horizontal_alignment="center", wrap=False):
            st.html("""
                <style>
                .st-key-admin_login_card [data-testid="stWidgetLabel"] {
                    font-size: 1.15rem;
                }
                .st-key-admin_login_card input {
                    min-height: 3.25rem;
                    font-size: 1.1rem;
                }
                .st-key-admin_login_card button {
                    min-height: 3.25rem;
                    font-size: 1.15rem;
                    font-weight: 600;
                }
                </style>
            """)
            with st.container(
                width=800,
                height=800,
                border=True,
                key="admin_login_card",
            ):
                st.space("medium")
                st.markdown(":green-badge[ADMIN ACCESS]")
                st.markdown(":material/lock:")
                st.html("""
                    <h1 style="font-size: 2.6rem; margin: 0.3rem 0;">
                        Welcome back
                    </h1>
                    <p style="font-size: 1.15rem; margin-top: 0.4rem;">
                        Sign in to monitor your translation service.
                    </p>
                """)

                with st.form("admin_login"):
                    password = st.text_input(
                        "Admin password",
                        type="password",
                        placeholder="Enter your password",
                    )
                    st.space("small")
                    submitted = st.form_submit_button(
                        "Sign in",
                        type="primary",
                        width="stretch",
                    )

                if submitted:
                    if hmac.compare_digest(password, ADMIN_PASSWORD):
                        st.session_state["authenticated"] = True
                        st.rerun()
                    else:
                        st.error("Incorrect password. Please try again.")

    st.stop()


# ----------------------------------
# DASHBOARD HEADER
# ----------------------------------

if st.sidebar.button("Logout"):
    st.session_state["authenticated"] = False
    st.rerun()

header_column, refresh_column = st.columns([0.88, 0.12])
with header_column:
    st.title("Translation operations")
with refresh_column:
    if st.button(
        "Refresh",
        icon=":material/refresh:",
        help="Reload dashboard data",
    ):
        st.rerun()

st.caption("A live overview of document activity, translation quality, and account usage.")


# ----------------------------------
# DATABASE CONNECTION AND OVERVIEW
# ----------------------------------

db = SessionLocal()

try:
    records = (
        db.query(TranslationHistory, APIKey.name)
        .join(APIKey, TranslationHistory.api_key_id == APIKey.id)
        .order_by(TranslationHistory.created_at.desc())
        .all()
    )

    data = [
        {
            "Client": client_name,
            "Filename": item.filename,
            "Document Type": item.document_type,
            "Source Language": item.source_language or "Auto",
            "Target Language": item.target_language,
            "File Size (MB)": round((item.file_size or 0) / (1024 * 1024), 2),
            "Status": item.status or "Pending",
            "Duration (seconds)": item.duration_seconds,
            "Date": item.created_at,
        }
        for item, client_name in records
    ]
    df = pd.DataFrame(
        data,
        columns=[
            "Client",
            "Filename",
            "Document Type",
            "Source Language",
            "Target Language",
            "File Size (MB)",
            "Status",
            "Duration (seconds)",
            "Date",
        ],
    )

    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True)
        df["Date"] = df["Date"].dt.tz_convert(None)

    with st.sidebar:
        st.subheader("Dashboard filters")
        date_window = st.selectbox(
            "Reporting period",
            ["Last 7 days", "Last 30 days", "Last 90 days", "All time"],
            index=1,
        )
        clients = sorted(df["Client"].dropna().unique().tolist()) if not df.empty else []
        selected_clients = st.multiselect("Clients", clients, default=clients)

    filtered_df = df.copy()
    if date_window != "All time" and not filtered_df.empty:
        days = {
            "Last 7 days": 7,
            "Last 30 days": 30,
            "Last 90 days": 90,
        }[date_window]
        start_date = (
            pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
            - pd.Timedelta(days=days - 1)
        )
        filtered_df = filtered_df[filtered_df["Date"] >= start_date]

    if not filtered_df.empty:
        filtered_df = filtered_df[filtered_df["Client"].isin(selected_clients)]

    statuses = filtered_df["Status"].fillna("Pending").str.strip().str.lower()
    successful = int(statuses.eq("success").sum())
    failed = int(statuses.eq("failed").sum())
    total_requests = len(filtered_df)
    success_rate = (successful / total_requests * 100) if total_requests else 0
    durations = pd.to_numeric(
        filtered_df["Duration (seconds)"], errors="coerce"
    ).dropna() if not filtered_df.empty else pd.Series(dtype=float)
    avg_duration = f"{durations.mean():.1f}s" if not durations.empty else "—"

    st.caption(f"Showing {date_window.lower()} · {total_requests:,} requests")
    metric_columns = st.columns(4)
    metric_columns[0].metric("Total requests", f"{total_requests:,}", border=True)
    metric_columns[1].metric("Success rate", f"{success_rate:.1f}%", border=True)
    metric_columns[2].metric("Failed requests", f"{failed:,}", border=True)
    metric_columns[3].metric("Avg. processing time", avg_duration, border=True)

    st.subheader("Translation statistics")
    if filtered_df.empty:
        st.info("No translation activity in this reporting period. Charts will fill in as requests arrive.")
    else:
        language_column, format_column = st.columns(2, gap="medium")
        with language_column:
            with st.container(border=True):
                st.markdown("**Popular target languages**")
                language_stats = (
                    filtered_df["Target Language"]
                    .value_counts()
                    .head(5)
                    .rename("Requests")
                    .rename_axis("Language")
                    .reset_index()
                )
                st.caption(
                    f"{int(language_stats['Requests'].sum()):,} translations across "
                    f"{len(language_stats)} languages"
                )
                language_chart = (
                    alt.Chart(language_stats)
                    .mark_bar(color="#3B82F6", cornerRadiusEnd=4)
                    .encode(
                        x=alt.X("Requests:Q", title="Translations"),
                        y=alt.Y("Language:N", sort="-x", title=None),
                        tooltip=["Language:N", "Requests:Q"],
                    )
                    .properties(height=340)
                )
                st.altair_chart(language_chart, width="stretch")

        with format_column:
            with st.container(border=True):
                st.markdown("**Most-used document types**")
                format_stats = (
                    filtered_df["Document Type"]
                    .value_counts()
                    .head(5)
                    .rename("Requests")
                    .rename_axis("Format")
                    .reset_index()
                )
                st.caption(
                    f"{int(format_stats['Requests'].sum()):,} translations across "
                    f"{len(format_stats)} document types"
                )
                format_chart = (
                    alt.Chart(format_stats)
                    .mark_bar(color="#F59E0B", cornerRadiusEnd=4)
                    .encode(
                        x=alt.X("Requests:Q", title="Translations"),
                        y=alt.Y("Format:N", sort="-x", title=None),
                        tooltip=["Format:N", "Requests:Q"],
                    )
                    .properties(height=340)
                )
                st.altair_chart(format_chart, width="stretch")

    st.subheader("DeepL account usage")

    deepl_key = os.getenv("DEEPL_API_KEY")

    deepl_url = os.getenv(
        "DEEPL_API_URL",
        "https://api-free.deepl.com"
    ).rstrip("/")

    if st.button("Refresh DeepL Usage"):

        if not deepl_key:
            st.error("DeepL API key is missing.")

        else:

            try:

                response = requests.get(
                    f"{deepl_url}/v2/usage",
                    headers={
                        "Authorization":
                        f"DeepL-Auth-Key {deepl_key}"
                    },
                    timeout=30
                )

                response.raise_for_status()

                usage = response.json()

                snapshot = DeepLUsageSnapshot(
                    character_count=usage.get(
                        "character_count", 0
                    ),
                    character_limit=usage.get(
                        "character_limit", 0
                    ),
                    document_count=usage.get(
                        "document_count"
                    ),
                    document_limit=usage.get(
                        "document_limit"
                    )
                )

                db.add(snapshot)
                db.commit()

                st.success("DeepL usage updated!")

            except requests.RequestException:
                st.error(
                    "Could not retrieve DeepL usage. "
                    "Check your API credentials and server logs."
                )

    latest_usage = (
        db.query(DeepLUsageSnapshot)
        .order_by(
            DeepLUsageSnapshot.captured_at.desc()
        )
        .first()
    )

    if latest_usage:

        used = latest_usage.character_count
        limit = latest_usage.character_limit

        usage_col1, usage_col2 = st.columns(2)

        usage_col1.metric(
            "Characters Used",
            f"{used:,}"
        )

        usage_col2.metric(
            "Character Limit",
            f"{limit:,}"
        )

        if limit > 0:

            percentage = min(used / limit, 1.0)

            st.progress(percentage)

            st.caption(
                f"{percentage * 100:.2f}% of character quota used"
            )

        if latest_usage.document_count is not None:
            st.metric(
                "DeepL Documents Used",
                latest_usage.document_count
            )

        st.caption(
            f"Last updated: {latest_usage.captured_at}"
        )

    else:
        st.info(
            "Click Refresh DeepL Usage to retrieve "
            "your account's usage."
        )


    st.divider()


    # ----------------------------------
    # COMPLETE TRANSLATION HISTORY
    # ----------------------------------

    st.subheader("Complete translation history")

    if not df.empty:

        st.dataframe(
            df,
            hide_index=True
        )

        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download translation history CSV",
            data=csv,
            file_name="translation_history.csv",
            mime="text/csv"
        )

    else:
        st.info("No translation history available.")

finally:
    db.close()
