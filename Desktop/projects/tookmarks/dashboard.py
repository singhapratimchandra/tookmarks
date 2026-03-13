import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from datetime import datetime
from collections import Counter

st.set_page_config(page_title="Tookmarks Dashboard", page_icon="🔖", layout="wide")

st.title("🔖 Tookmarks — Twitter Bookmarks Dashboard")
st.markdown("---")

# Load data
@st.cache_data
def load_data(file_path):
    with open(file_path) as f:
        bookmarks = json.load(f)

    rows = []
    for b in bookmarks:
        text = b.get('text', '')
        created = b.get('created_at', '')

        date_obj = None
        if created:
            try:
                date_obj = datetime.fromisoformat(created.replace('Z', '+00:00'))
            except:
                pass

        word_count = len(text.split()) if text else 0

        rows.append({
            'id': b.get('id', ''),
            'text': text,
            'author_name': b.get('author_name', ''),
            'author_handle': b.get('author_handle', ''),
            'created_at': date_obj,
            'url': b.get('url', ''),
            'word_count': word_count,
            'char_count': len(text) if text else 0,
        })

    df = pd.DataFrame(rows)
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at'], utc=True)
        df['date'] = df['created_at'].dt.date
        df['day_of_week'] = df['created_at'].dt.day_name()
        df['hour'] = df['created_at'].dt.hour
        df['month'] = df['created_at'].dt.to_period('M').astype(str)
    return df

# File uploader
st.sidebar.markdown("### Upload Your Bookmarks")
st.sidebar.markdown("Export your Twitter bookmarks as JSON, then upload here.")
uploaded_file = st.sidebar.file_uploader("Upload bookmarks JSON", type=['json'])

if uploaded_file:
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
    tmp.write(uploaded_file.read())
    tmp.close()
    df = load_data(tmp.name)
    os.unlink(tmp.name)
else:
    st.info("👈 Upload your Twitter bookmarks JSON file using the sidebar to get started!")
    st.stop()

# ========== KEY METRICS ==========
st.header("📊 Key Metrics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Bookmarks", len(df))
col2.metric("Unique Authors", df['author_handle'].nunique())
col3.metric("Avg Words/Tweet", round(df['word_count'].mean(), 1))
col4.metric("Date Range", f"{df['date'].min()} → {df['date'].max()}" if 'date' in df.columns else "N/A")

st.markdown("---")

# ========== KEY TAKEAWAYS ==========
st.header("💡 Key Takeaways")

top_author = df['author_name'].value_counts().head(1)
top_day = df['day_of_week'].value_counts().head(1) if 'day_of_week' in df.columns else None
top_hour = df['hour'].value_counts().head(1) if 'hour' in df.columns else None
avg_words = df['word_count'].mean()
long_tweets = len(df[df['word_count'] > 50])

takeaways = []
if len(top_author) > 0:
    takeaways.append(f"🏆 **Most bookmarked author:** {top_author.index[0]} ({top_author.values[0]} bookmarks)")
if top_day is not None and len(top_day) > 0:
    takeaways.append(f"📅 **Most active bookmark day:** {top_day.index[0]} ({top_day.values[0]} bookmarks)")
if top_hour is not None and len(top_hour) > 0:
    takeaways.append(f"🕐 **Peak bookmark hour:** {top_hour.index[0]}:00 ({top_hour.values[0]} bookmarks)")
takeaways.append(f"📝 **Average tweet length:** {avg_words:.0f} words")
takeaways.append(f"📚 **Long-form tweets (50+ words):** {long_tweets} ({long_tweets/len(df)*100:.1f}%)")

for t in takeaways:
    st.markdown(t)

st.markdown("---")

# ========== CHARTS ==========
col_left, col_right = st.columns(2)

# Top Authors
with col_left:
    st.subheader("🏆 Top 15 Bookmarked Authors")
    top_authors = df['author_name'].value_counts().head(15).reset_index()
    top_authors.columns = ['Author', 'Count']
    fig = px.bar(top_authors, x='Count', y='Author', orientation='h',
                 color='Count', color_continuous_scale='Blues')
    fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=500)
    st.plotly_chart(fig, use_container_width=True)

# Bookmarks by Day of Week
with col_right:
    st.subheader("📅 Bookmarks by Day of Week")
    if 'day_of_week' in df.columns:
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_counts = df['day_of_week'].value_counts().reindex(day_order).fillna(0).reset_index()
        day_counts.columns = ['Day', 'Count']
        fig = px.bar(day_counts, x='Day', y='Count', color='Count', color_continuous_scale='Greens')
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

col_left2, col_right2 = st.columns(2)

# Bookmarks by Hour
with col_left2:
    st.subheader("🕐 Bookmarks by Hour of Day")
    if 'hour' in df.columns:
        hour_counts = df['hour'].value_counts().sort_index().reset_index()
        hour_counts.columns = ['Hour', 'Count']
        fig = px.area(hour_counts, x='Hour', y='Count', markers=True)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

# Word Count Distribution
with col_right2:
    st.subheader("📝 Tweet Length Distribution")
    fig = px.histogram(df, x='word_count', nbins=30, labels={'word_count': 'Word Count'},
                       color_discrete_sequence=['#1DA1F2'])
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

# Monthly Trend
st.subheader("📈 Bookmarks Over Time")
if 'month' in df.columns:
    monthly = df.groupby('month').size().reset_index(name='Count')
    fig = px.line(monthly, x='month', y='Count', markers=True)
    fig.update_layout(height=400, xaxis_title='Month', yaxis_title='Bookmarks')
    st.plotly_chart(fig, use_container_width=True)

# Bookmarks Timeline (daily)
if 'date' in df.columns:
    st.subheader("📆 Daily Bookmarks Timeline")
    daily = df.groupby('date').size().reset_index(name='Count')
    fig = px.bar(daily, x='date', y='Count', color_discrete_sequence=['#1DA1F2'])
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

# ========== DATA TABLE ==========
st.markdown("---")
st.header("📋 All Bookmarks")
st.dataframe(
    df[['author_name', 'author_handle', 'text', 'created_at', 'word_count', 'url']].sort_values('created_at', ascending=False),
    use_container_width=True,
    height=500
)
