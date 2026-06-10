import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
from backend import db, scraper, gemini_client

def chunk_text(text, chunk_size=800, overlap=150):
    """
    Split text into chunks of roughly chunk_size characters with overlap.
    Splits along sentence boundaries to preserve readability.
    """
    if not text:
        return []
        
    sentences = text.replace('\n', ' ').split('. ')
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        sentence += "."
        sentence_len = len(sentence)
        
        # If adding this sentence exceeds chunk size, save current chunk
        if current_length + sentence_len > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            # Keep overlap: keep last few sentences that fit inside overlap limit
            overlap_chunk = []
            overlap_len = 0
            for s in reversed(current_chunk):
                if overlap_len + len(s) < overlap:
                    overlap_chunk.insert(0, s)
                    overlap_len += len(s) + 1
                else:
                    break
            current_chunk = overlap_chunk
            current_length = overlap_len
            
        current_chunk.append(sentence)
        current_length += sentence_len + 1
        
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks

def calculate_technical_indicators(df):
    """
    Calculates key technical indicators (SMA, EMA, RSI, MACD) on a stock price dataframe.
    """
    if df.empty or len(df) < 15:
        return df
        
    # Moving Averages
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    
    # EMAs
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    
    # MACD
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    # RSI (Relative Strength Index)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    
    # Avoid division by zero
    rs = gain / np.where(loss == 0, 0.00001, loss)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df

def run_daily_pipeline(ui_api_key=None):
    """
    Executes the complete daily ingestion and indexing pipeline:
    1. Initialises SQLite.
    2. Scrapes news feeds from Moneycontrol.
    3. Chunks, embeds, and saves articles.
    4. Auto-detects stocks mentioned in the articles, fetches prices,
       runs technical indicators analysis, and saves them.
    5. Generates and stores daily AI market summary.
    """
    print("Starting daily ingestion pipeline...")
    db.init_db()
    
    all_articles = []
    feeds_scraped = 0
    new_articles_count = 0
    new_chunks_count = 0
    
    for feed_name in scraper.MONEYCONTROL_FEEDS.keys():
        try:
            articles = scraper.fetch_moneycontrol_news_feed(feed_name, limit=8)
            all_articles.extend(articles)
            feeds_scraped += 1
        except Exception as e:
            print(f"Error scraping feed {feed_name}: {e}")
            
    # De-duplicate articles by URL
    seen_urls = set()
    unique_articles = []
    for art in all_articles:
        if art['url'] not in seen_urls:
            seen_urls.add(art['url'])
            unique_articles.append(art)
            
    print(f"Scraped {len(unique_articles)} unique articles across {feeds_scraped} feeds.")
    
    # Track which tickers are mentioned in these articles
    detected_tickers = set()
    
    for art in unique_articles:
        # Save article (returns ID of newly inserted or existing article)
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM articles WHERE url = ?", (art['url'],))
        exists = cursor.fetchone()
        conn.close()
        
        art_id = db.insert_article(
            title=art['title'],
            url=art['url'],
            summary=art['summary'],
            content=art['content'],
            published_date=art['published_date'],
            source=art['source']
        )
        
        # Scan title + summary + full content for company keywords (more coverage)
        text_to_scan = (art['title'] + " " + art['summary'] + " " + (art['content'] or "")).upper()
        for kw, ticker in scraper.COMMON_MAPPINGS.items():
            if kw in text_to_scan:
                detected_tickers.add(ticker)
        
        # Only chunk and embed if the article wasn't already processed
        if not exists:
            new_articles_count += 1
            chunks = chunk_text(art['content'])
            for idx, chunk in enumerate(chunks):
                emb = gemini_client.get_embedding(chunk, ui_api_key)
                metadata = {
                    'title': art['title'],
                    'published_date': art['published_date'],
                    'source': art['source']
                }
                db.insert_chunk(
                    article_id=art_id,
                    chunk_index=idx,
                    text_content=chunk,
                    embedding_vector=emb,
                    metadata_dict=metadata
                )
                new_chunks_count += 1
                
    # Also scan ALL articles already in the DB so that expanding COMMON_MAPPINGS
    # retroactively detects tickers from previously ingested articles
    print("Scanning existing DB articles for ticker mentions...")
    all_db_articles = db.get_latest_articles(limit=200)
    for art in all_db_articles:
        text_to_scan = (
            (art.get('title') or '') + " " +
            (art.get('summary') or '')
        ).upper()
        for kw, ticker in scraper.COMMON_MAPPINGS.items():
            if kw in text_to_scan:
                detected_tickers.add(ticker)

    print(f"Ingested {new_articles_count} new articles resulting in {new_chunks_count} vector chunks.")
    print(f"Auto-detected {len(detected_tickers)} stock tickers in news feed: {list(detected_tickers)}")
    
    # For each detected stock, automatically fetch market history, calculate metrics, and save to SQLite
    today_date = datetime.now().strftime("%Y-%m-%d")
    for ticker in list(detected_tickers)[:15]: # Analyze up to 15 stocks per pipeline run
        try:
            yf_ticker = ticker
            if not yf_ticker.startswith('^') and '.' not in yf_ticker:
                yf_ticker = f"{yf_ticker}.NS"
                
            t = yf.Ticker(yf_ticker)
            df = t.history(period='3mo')
            if not df.empty and len(df) >= 15:
                df = calculate_technical_indicators(df)
                latest_row = df.iloc[-1]
                
                tech_data = {
                    'Close': round(latest_row['Close'], 2),
                    'SMA_20': round(latest_row['SMA_20'], 2) if not pd.isna(latest_row['SMA_20']) else None,
                    'SMA_50': round(latest_row['SMA_50'], 2) if not pd.isna(latest_row['SMA_50']) else None,
                    'RSI': round(latest_row['RSI'], 2) if not pd.isna(latest_row['RSI']) else None,
                    'MACD': round(latest_row['MACD'], 2) if not pd.isna(latest_row['MACD']) else None
                }
                
                # Generate a brief AI stock analysis using technical values
                prompt = (
                    f"Perform a brief technical analysis on {ticker}. "
                    f"Current price is {tech_data['Close']}, RSI is {tech_data['RSI']}, and SMA 20 is {tech_data['SMA_20']}. "
                    f"Give a professional evaluation of the trend and support/resistance zones."
                )
                stock_analysis = gemini_client.generate_response(prompt, [], ui_api_key)
                
                db.insert_analysis(
                    ticker=ticker,
                    analysis_date=today_date,
                    technical_data_dict=tech_data,
                    ai_report=stock_analysis
                )
                print(f"Auto-analyzed and saved stock database record for: {ticker}")
        except Exception as ex:
            print(f"Could not auto-analyze stock {ticker}: {ex}")
            
    # Generate daily market AI analysis
    daily_summary_text = "No summary generated."
    if unique_articles:
        print("Generating daily market summary via Gemini...")
        daily_summary_text = gemini_client.generate_daily_summary(unique_articles, ui_api_key)
        
        # Store in analysis table
        db.insert_analysis(
            ticker="MARKET",
            analysis_date=today_date,
            technical_data_dict={'articles_processed': len(unique_articles), 'stocks_detected': len(detected_tickers)},
            ai_report=daily_summary_text
        )
        print("Daily summary saved.")
        
    return {
        'feeds_processed': feeds_scraped,
        'new_articles': new_articles_count,
        'new_chunks': new_chunks_count,
        'daily_summary': daily_summary_text
    }

def retrieve_relevant_context(query, top_k=5, ui_api_key=None):
    """
    Computes cosine similarity between user query and DB chunks.
    Since text-embedding-004 returns L2-normalised vectors,
    cosine similarity is mathematically equivalent to the dot product.
    """
    query_emb = gemini_client.get_embedding(query, ui_api_key)
    query_vector = np.array(query_emb, dtype=np.float32)
    
    # Fetch all chunks
    all_chunks = db.get_all_chunks()
    if not all_chunks:
        return []
        
    scored_chunks = []
    for chunk in all_chunks:
        chunk_vector = np.array(chunk['embedding'], dtype=np.float32)
        
        # Cosine similarity is simple dot product if vectors are L2 normalised
        similarity = np.dot(query_vector, chunk_vector)
        
        scored_chunks.append({
            'chunk': chunk,
            'score': float(similarity)
        })
        
    # Sort descending by score
    scored_chunks.sort(key=lambda x: x['score'], reverse=True)
    
    # Return top K chunks
    top_chunks = [item['chunk'] for item in scored_chunks[:top_k]]
    return top_chunks
