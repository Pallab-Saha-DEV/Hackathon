import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime
from dotenv import load_dotenv

# Import our backend components
from backend import db, scraper, gemini_client, analyzer

# Page Configuration
st.set_page_config(
    page_title="Quantum Market Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load env file if any
load_dotenv()

# Initialize DB on start
db.init_db()

# ----------------- CUSTOM STYLE SHEET (CSS) -----------------
# Premium clean light theme with rich accent colors
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@300;500;700&display=swap');
    
    /* Global Overrides */
    .stApp {
        background: linear-gradient(160deg, #ffffff 0%, #f8fafc 50%, #f1f5f9 100%);
        color: #1e293b;
        font-family: 'Space Grotesk', sans-serif;
    }
    
    /* All paragraph and body text — deep charcoal for readability */
    .stApp p, .stApp li, .stApp span, .stApp div {
        color: #334155 !important;
    }
    
    /* Headers — deep indigo */
    h1, h2, h3, .stHeader {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: #1e1b4b !important;
    }
    
    /* Subheader text — vivid violet */
    .stApp h2, .stApp h3 {
        color: #6d28d9 !important;
    }
    
    /* Title Styling — bold indigo-to-teal gradient */
    .app-title {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 40%, #0891b2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0px;
        text-align: left;
    }
    
    .app-subtitle {
        color: #64748b !important;
        font-size: 1.15rem;
        margin-bottom: 2rem;
        letter-spacing: 0.3px;
    }
    
    /* Custom Cards — white glass with soft shadow */
    .metric-card {
        background: #ffffff;
        backdrop-filter: blur(8px);
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 22px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06), 0 1px 4px rgba(0, 0, 0, 0.04);
        transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-4px);
        border-color: #a78bfa;
        box-shadow: 0 8px 30px rgba(124, 58, 237, 0.1), 0 4px 12px rgba(0, 0, 0, 0.06);
    }
    
    /* Index name labels — muted slate */
    .metric-title {
        font-size: 0.85rem;
        color: #64748b !important;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 1.2px;
        margin-bottom: 6px;
    }
    
    /* Index price — dark navy */
    .metric-value {
        font-size: 1.9rem;
        font-weight: 800;
        color: #0f172a !important;
    }
    
    /* Stock change indicators */
    .metric-change-up {
        color: #16a34a !important;
        font-weight: 700;
        font-size: 1rem;
        display: inline-flex;
        align-items: center;
    }
    
    .metric-change-down {
        color: #dc2626 !important;
        font-weight: 700;
        font-size: 1rem;
        display: inline-flex;
        align-items: center;
    }
    
    /* Sidebar — soft cool gray with indigo accent */
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
        border-right: 1px solid #e0e7ff;
    }
    
    div[data-testid="stSidebar"] p,
    div[data-testid="stSidebar"] span,
    div[data-testid="stSidebar"] label,
    div[data-testid="stSidebar"] div {
        color: #475569 !important;
    }
    
    div[data-testid="stSidebar"] h1,
    div[data-testid="stSidebar"] h2,
    div[data-testid="stSidebar"] h3 {
        color: #312e81 !important;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: transparent;
        border-bottom: 2px solid #e2e8f0;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border: none;
        color: #94a3b8 !important;
        font-size: 1.1rem;
        font-weight: 600;
        transition: color 0.3s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: #475569 !important;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #7c3aed !important;
        border-bottom: 3px solid #7c3aed;
    }
    
    /* Streamlit buttons — indigo gradient */
    .stButton > button {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(79, 70, 229, 0.25) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 25px rgba(79, 70, 229, 0.4) !important;
    }
    
    /* Text inputs and selectboxes */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
    }
    
    /* Chat messages */
    div[data-testid="stChatMessage"] {
        background-color: #f8fafc !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
    }
    
    /* Markdown text — dark slate */
    .stMarkdown p {
        color: #334155 !important;
        line-height: 1.7;
    }
    
    /* Links — rich indigo */
    a {
        color: #4f46e5 !important;
        text-decoration: none;
    }
    
    a:hover {
        color: #7c3aed !important;
        text-decoration: underline;
    }
    
    /* Expander headers */
    details summary {
        color: #0891b2 !important;
        font-weight: 600;
    }
    
    /* Caption text */
    .stCaption, small {
        color: #94a3b8 !important;
    }
    
    /* Metrics in sidebar */
    div[data-testid="stMetricValue"] {
        color: #4f46e5 !important;
    }
    
    div[data-testid="stMetricLabel"] {
        color: #7c3aed !important;
    }
    
    /* Spinner text */
    .stSpinner > div > span {
        color: #6d28d9 !important;
    }
    
    /* Info/Success/Warning/Error boxes */
    div[data-testid="stAlert"] {
        border-radius: 10px !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.image("https://img.icons8.com/nolan/96/combo-chart.png", width=80)
    st.markdown("### Config Panel")
    
    # API Key management
    env_key = os.getenv("GEMINI_API_KEY")
    has_env_key = bool(env_key and not env_key.startswith("your_gemini") and len(env_key) > 10)
    
    if has_env_key:
        st.success("🔑 Gemini API Key loaded from environment")
        api_key = env_key
    else:
        api_key = None
            
    st.markdown("---")
    
    # DB stats
    st.markdown("#### Knowledge Repository Stats")
    stats = db.get_db_stats()
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.metric("Articles", stats['articles'])
    with col_s2:
        st.metric("Vector Chunks", stats['chunks'])
        
    st.markdown("---")
    
    # Actions
    st.markdown("#### Data Ingestion")
    st.info("Fetches daily market news from Moneycontrol RSS, chunks them, computes Gemini embeddings, and stores them in SQLite.")
    
    if st.button("🔄 Trigger Daily Ingestion", use_container_width=True):
        with st.spinner("Executing daily pipeline (scraping, embedding chunks, summarizing)..."):
            try:
                result = analyzer.run_daily_pipeline(ui_api_key=api_key)
                st.success(f"Success! Ingested {result['new_articles']} new articles and created {result['new_chunks']} vector chunks.")
                st.rerun()
            except Exception as e:
                st.error(f"Pipeline failed: {e}")
                    
    if st.button("🗑️ Reset Database", use_container_width=True, type="secondary"):
        db.clear_db()
        st.success("Database cleared successfully!")
        st.rerun()

# ----------------- MAIN PANEL -----------------
st.markdown('<div class="app-title">QUANTUM MARKET INTELLIGENCE</div>', unsafe_allow_html=True)
st.markdown('<div class="app-subtitle">Daily data fetching, automated technical analysis, and RAG-based stock prediction</div>', unsafe_allow_html=True)



# Fetch current index summaries
with st.spinner("Loading index parameters..."):
    market_indices = scraper.fetch_market_indices()

# Display Indices row in custom HTML design
col1, col2, col3 = st.columns(3)
indices_data = [
    ("Nifty 50", market_indices.get("Nifty 50")),
    ("BSE Sensex", market_indices.get("Sensex")),
    ("Nifty Bank", market_indices.get("Nifty Bank"))
]

for col, (name, data) in zip([col1, col2, col3], indices_data):
    with col:
        if data and data['price'] != 'N/A':
            price = f"{data['price']:,}"
            change_val = data['change']
            change_pct = data['pct_change']
            
            if change_val >= 0:
                change_style = "metric-change-up"
                change_str = f"▲ +{change_val} (+{change_pct}%)"
            else:
                change_style = "metric-change-down"
                change_str = f"▼ {change_val} ({change_pct}%)"
                
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">{name}</div>
                <div class="metric-value">{price}</div>
                <div class="{change_style}">{change_str}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">{name}</div>
                <div class="metric-value">Market Closed / N/A</div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Tabs
tab1, tab2 = st.tabs(["📊 Dashboard & Charting", "💬 RAG AI Market Advisor"])

# ----------------- TAB 1: DASHBOARD & CHARTING -----------------
with tab1:
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("📈 Interactive Stock Analyzer")
        
        # Load unique stock tickers detected from Moneycontrol ingestion
        db_tickers = db.get_all_analyzed_tickers()
        
        # Fallback to well-known NSE blue-chips if no ingestion has run yet
        if not db_tickers:
            dropdown_options = ["RELIANCE", "INFY", "TCS", "HDFCBANK", "ICICIBANK"]
            st.info("ℹ️ No stocks ingested yet. Showing default blue-chip tickers. Run **Trigger Daily Ingestion** in the sidebar to populate from Moneycontrol.")
        else:
            dropdown_options = db_tickers
            
        ticker_input = st.selectbox(
            "Select Stock (auto-populated from Moneycontrol data)",
            options=dropdown_options,
            index=0,
            help="Stocks are auto-detected from daily Moneycontrol RSS feeds. Run ingestion to refresh this list."
        )
            
        # Load stock history
        if ticker_input:
            # Normalize ticker input using backend helper (appends .NS and resolves common names)
            ticker = scraper.normalize_ticker(ticker_input)
                
            try:
                with st.spinner(f"Loading {ticker} history..."):
                    ticker_obj = yf.Ticker(ticker)
                    info = ticker_obj.info
                    stock_name = info.get('longName', ticker)
                    
                    df_history = ticker_obj.history(period="6mo")
                    
                if df_history.empty:
                    st.error(f"No historical price data found for '{ticker}'. Ensure the ticker symbol is correct.")
                else:
                    # Calculate Moving Averages, RSI, MACD
                    df_history = analyzer.calculate_technical_indicators(df_history)
                    
                    # Auto-save manual search to database to populate selectbox on next load
                    try:
                        latest_row = df_history.iloc[-1]
                        tech_val = {
                            'Close': round(latest_row['Close'], 2),
                            'SMA_20': round(latest_row['SMA_20'], 2) if 'SMA_20' in df_history.columns and not pd.isna(latest_row['SMA_20']) else None,
                            'SMA_50': round(latest_row['SMA_50'], 2) if 'SMA_50' in df_history.columns and not pd.isna(latest_row['SMA_50']) else None,
                            'RSI': round(latest_row['RSI'], 2) if 'RSI' in df_history.columns and not pd.isna(latest_row['RSI']) else None,
                            'MACD': round(latest_row['MACD'], 2) if 'MACD' in df_history.columns and not pd.isna(latest_row['MACD']) else None
                        }
                        # Save to db (remove .NS suffix for database listing)
                        clean_db_ticker = ticker.split(".")[0]
                        db.insert_analysis(
                            ticker=clean_db_ticker,
                            analysis_date=datetime.now().strftime("%Y-%m-%d"),
                            technical_data_dict=tech_val,
                            ai_report=f"Manual technical analysis generated for {clean_db_ticker}."
                        )
                    except Exception as db_err:
                        print(f"Could not auto-save manual analysis: {db_err}")
                    
                    # Construct interactive multi-chart plot using Plotly
                    fig = make_subplots(
                        rows=3, cols=1, 
                        shared_xaxes=True, 
                        vertical_spacing=0.03, 
                        row_heights=[0.5, 0.25, 0.25]
                    )
                    
                    # 1. Candlestick Chart with Moving Averages
                    fig.add_trace(
                        go.Candlestick(
                            x=df_history.index,
                            open=df_history['Open'],
                            high=df_history['High'],
                            low=df_history['Low'],
                            close=df_history['Close'],
                            name="Price"
                        ),
                        row=1, col=1
                    )
                    
                    # SMAs
                    if 'SMA_20' in df_history.columns:
                        fig.add_trace(go.Scatter(x=df_history.index, y=df_history['SMA_20'], line=dict(color='#ff9900', width=1.5), name="SMA 20"), row=1, col=1)
                    if 'SMA_50' in df_history.columns:
                        fig.add_trace(go.Scatter(x=df_history.index, y=df_history['SMA_50'], line=dict(color='#33cc33', width=1.5), name="SMA 50"), row=1, col=1)
                    if 'SMA_200' in df_history.columns:
                        fig.add_trace(go.Scatter(x=df_history.index, y=df_history['SMA_200'], line=dict(color='#ff3300', width=1.5), name="SMA 200"), row=1, col=1)
                        
                    # 2. RSI Chart
                    if 'RSI' in df_history.columns:
                        fig.add_trace(go.Scatter(x=df_history.index, y=df_history['RSI'], line=dict(color='#9b5de5', width=1.5), name="RSI"), row=2, col=1)
                        # Add horizontal reference lines
                        fig.add_hline(y=70, line_dash="dash", line_color="#ff595e", annotation_text="Overbought", row=2, col=1)
                        fig.add_hline(y=30, line_dash="dash", line_color="#8ac926", annotation_text="Oversold", row=2, col=1)
                        fig.update_yaxes(range=[0, 100], row=2, col=1)
                        
                    # 3. MACD Chart
                    if 'MACD' in df_history.columns:
                        fig.add_trace(go.Scatter(x=df_history.index, y=df_history['MACD'], line=dict(color='#00bbf9', width=1), name="MACD"), row=3, col=1)
                        fig.add_trace(go.Scatter(x=df_history.index, y=df_history['MACD_Signal'], line=dict(color='#f15bb5', width=1), name="Signal"), row=3, col=1)
                        
                        # Bar colors for Histogram
                        colors = ['#39d353' if val >= 0 else '#f85149' for val in df_history['MACD_Hist']]
                        fig.add_trace(go.Bar(x=df_history.index, y=df_history['MACD_Hist'], marker_color=colors, name="Hist"), row=3, col=1)
                        
                    # Update layout
                    fig.update_layout(
                        title=f"{stock_name} ({ticker}) - 6 Month Trend",
                        template="plotly_dark",
                        xaxis_rangeslider_visible=False,
                        height=600,
                        margin=dict(l=50, r=20, t=50, b=50),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Display profile summary below
                    st.subheader(f"About {stock_name}")
                    st.write(info.get('longBusinessSummary', 'No profile available.'))
                    
            except Exception as e:
                st.error(f"Error loading ticker data: {e}")
                
    with col_right:
        st.subheader("📰 Market Outlook Summary")
        
        # Load daily briefings
        analyses = db.get_latest_analyses(limit=1)
        if analyses:
            latest_ana = analyses[0]
            st.markdown(f"**Generated on:** {latest_ana['analysis_date']}")
            st.markdown(latest_ana['ai_report'])
        else:
            st.warning("⚠️ No AI Market Outlook reports found in database. Run the daily ingestion pipeline in the sidebar to populate.")
            
        st.markdown("---")
        st.subheader("🔥 Latest Scraped Headlines")
        latest_articles = db.get_latest_articles(limit=6)
        if latest_articles:
            for art in latest_articles:
                st.markdown(f"📎 **[{art['title']}]({art['url']})**")
                st.caption(f"Source: {art['source']} | Date: {art['published_date']}")
                st.markdown("---")
        else:
            st.write("No articles parsed yet. Trigger ingestion from the sidebar.")

# ----------------- TAB 2: AI ADVISOR (RAG) -----------------
with tab2:
    st.subheader("💬 AI Stock Advisor Chat")
    st.markdown("""
    Ask questions about **market summaries, news outlooks, stock predictions, or buzzing companies**.
    The chatbot retrieves relevant snippets from the daily scraped Moneycontrol reports and utilizes Gemini AI to construct structured answers with citations.
    """)
    
    # Pre-fill query suggestions
    st.write("💡 **Suggested Questions:**")
    s_col1, s_col2, s_col3 = st.columns(3)
    
    suggested_q = None
    with s_col1:
        if st.button("What are the key market themes today?", use_container_width=True):
            suggested_q = "What are the key market themes today?"
    with s_col2:
        if st.button("Which stocks are buzzing and why?", use_container_width=True):
            suggested_q = "Which stocks are buzzing and why?"
    with s_col3:
        if st.button("What is the general sentiment outlook?", use_container_width=True):
            suggested_q = "What is the general sentiment outlook for the next few sessions?"
            
    # Session state for messages
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! I am your Quantum AI Stock Advisor. Ask me anything about stock predictions, trends, or news based on our Moneycontrol intelligence archive!"}
        ]
        
    # Display previous messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    # Handle user query input
    user_query = st.chat_input("Enter stock prediction query...")
    
    # If suggestion clicked, overwrite query
    if suggested_q:
        user_query = suggested_q
        
    if user_query:
        # Display user message
        with st.chat_message("user"):
            st.write(user_query)
        st.session_state.messages.append({"role": "user", "content": user_query})
        
        # Generate AI answer using RAG context
        with st.chat_message("assistant"):
            with st.spinner("Searching knowledge base..."):
                try:
                    # 1. Retrieve top context
                    top_chunks = analyzer.retrieve_relevant_context(user_query, top_k=6, ui_api_key=api_key)
                    
                    # Show retrieved references in an expander for transparency
                    if top_chunks:
                        with st.expander("🔍 Retrieved database snippets for this query:"):
                            for chunk in top_chunks:
                                st.markdown(f"**Source:** [{chunk['article_title']}]({chunk['article_url']}) ({chunk['article_date']})")
                                st.write(chunk['text_content'])
                                st.markdown("---")
                    else:
                        st.caption("No snippets retrieved from database.")
                        
                    # 2. Query Gemini
                    response = gemini_client.generate_response(user_query, top_chunks, ui_api_key=api_key)
                    st.markdown(response)
                    
                    # Save assistant message
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    error_msg = f"Failed to get AI answer: {e}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
