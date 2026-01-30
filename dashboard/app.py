import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
import json
from config import settings

# Set the page layout to 'wide' to use more space
st.set_page_config(layout="wide")

DB_PATH = Path(settings.db_path).resolve()

st.title("RAG Observability Dashboard")

@st.cache_data(ttl=10)
def load_data():
    """Loads data from the SQLite database, joining logs and feedback."""
    if not DB_PATH.exists():
        st.warning(f"Database file not found at path: {DB_PATH}")
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH)
        # Query with LEFT JOIN to include feedback if it exists
        query = """
            SELECT 
                rl.*,
                rf.rating,
                rf.comment
            FROM requests_log rl
            LEFT JOIN request_feedback rf ON rl.request_id = rf.request_id
            ORDER BY rl.timestamp DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Convert numeric columns
        numeric_cols = [
            'latency_ms_total', 'latency_ms_retrieval', 'latency_ms_llm',
            'prompt_tokens', 'answer_tokens', 'rating'
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

# Load the data
data = load_data()

if data.empty:
    st.warning("No data found in the database. Run some queries on the API.")
else:
    # Main metrics
    st.header("General Metrics")
    total_requests = len(data)
    failed_requests = data['error'].notna().sum()
    success_rate = (total_requests - failed_requests) / total_requests * 100 if total_requests > 0 else 0
    avg_latency = data['latency_ms_total'].mean()
    avg_rating = data['rating'].mean()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Requests", total_requests)
    col2.metric("Failed Requests", failed_requests)
    col3.metric("Success Rate", f"{success_rate:.2f}%")
    col4.metric("Average Rating", f"{avg_rating:.2f}" if not pd.isna(avg_rating) else "N/A")


    # Distribution charts
    st.header("Distributions")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Latencies (ms)")
        latency_df = data[['latency_ms_retrieval', 'latency_ms_llm']].copy()
        latency_df.rename(columns={
            'latency_ms_retrieval': 'Data Retrieval',
            'latency_ms_llm': 'LLM Generation'
        }, inplace=True)
        st.bar_chart(latency_df)

    with col2:
        st.subheader("Rating Distribution")
        if 'rating' in data and not data['rating'].dropna().empty:
            rating_counts = data['rating'].value_counts().sort_index()
            st.bar_chart(rating_counts)
        else:
            st.write("No ratings yet.")


    # Table of the latest requests
    st.header("Latest Requests Details")
    
    display_cols = [
        'timestamp', 'trace_id', 'rating', 'question', 'answer', 'latency_ms_total', 
        'retrieved_distances', 'error', 'comment'
    ]
    display_cols = [col for col in display_cols if col in data.columns]
    
    display_df = data[display_cols].copy()
    
    # Formatting for better visualization
    display_df['answer'] = display_df['answer'].str.slice(0, 150) + '...'
    if 'retrieved_distances' in display_df:
        display_df['retrieved_distances'] = display_df['retrieved_distances'].apply(
            lambda x: [round(d, 2) for d in json.loads(x)] if x and x != 'null' else []
        )

    st.dataframe(display_df, use_container_width=True)

# Adds a button to manually refresh the data
if st.button('Refresh Data'):
    st.cache_data.clear()
    st.rerun()
