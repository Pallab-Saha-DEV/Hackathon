import sqlite3
import os
import json
import numpy as np
from datetime import datetime

# On Railway, mount a persistent volume at /data and set DATABASE_PATH=/data/market_knowledge.db
# Locally, defaults to market_knowledge.db in the project root
def _resolve_db_path():
    explicit = os.getenv("DATABASE_PATH")
    if explicit:
        return explicit
    # Auto-detect Railway persistent volume mount
    if os.path.isdir("/data"):
        return "/data/market_knowledge.db"
    return "market_knowledge.db"

DEFAULT_DB_PATH = _resolve_db_path()

def get_db_connection():
    db_path = _resolve_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(db_path) else None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create articles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            summary TEXT,
            content TEXT,
            published_date TEXT,
            source TEXT,
            ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. Create analysis table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            analysis_date TEXT NOT NULL,
            technical_data TEXT,
            ai_report TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 3. Create chunks table for RAG
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER,
            chunk_index INTEGER,
            text_content TEXT NOT NULL,
            embedding BLOB NOT NULL,
            metadata TEXT,
            FOREIGN KEY (article_id) REFERENCES articles (id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

def insert_article(title, url, summary, content, published_date, source):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if article already exists
        cursor.execute("SELECT id FROM articles WHERE url = ?", (url,))
        row = cursor.fetchone()
        if row:
            return row['id']
            
        cursor.execute("""
            INSERT INTO articles (title, url, summary, content, published_date, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, url, summary, content, published_date, source))
        conn.commit()
        article_id = cursor.lastrowid
        return article_id
    except sqlite3.IntegrityError:
        # Fallback if racing happened
        cursor.execute("SELECT id FROM articles WHERE url = ?", (url,))
        row = cursor.fetchone()
        return row['id'] if row else None
    finally:
        conn.close()

def insert_chunk(article_id, chunk_index, text_content, embedding_vector, metadata_dict=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Convert list/np.array of floats to raw bytes (float32)
        embedding_blob = np.array(embedding_vector, dtype=np.float32).tobytes()
        metadata_str = json.dumps(metadata_dict) if metadata_dict else "{}"
        
        cursor.execute("""
            INSERT INTO chunks (article_id, chunk_index, text_content, embedding, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (article_id, chunk_index, text_content, embedding_blob, metadata_str))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def insert_analysis(ticker, analysis_date, technical_data_dict, ai_report):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        tech_data_str = json.dumps(technical_data_dict)
        cursor.execute("""
            INSERT INTO analysis (ticker, analysis_date, technical_data, ai_report)
            VALUES (?, ?, ?, ?)
        """, (ticker, analysis_date, tech_data_str, ai_report))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def get_all_chunks():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT chunks.id, chunks.article_id, chunks.text_content, chunks.embedding, chunks.metadata,
                   articles.title, articles.url, articles.published_date
            FROM chunks
            LEFT JOIN articles ON chunks.article_id = articles.id
        """)
        rows = cursor.fetchall()
        
        chunks = []
        for row in rows:
            # Reconstruct float32 array from bytes
            emb_bytes = row['embedding']
            emb_vector = np.frombuffer(emb_bytes, dtype=np.float32).tolist()
            
            chunks.append({
                'id': row['id'],
                'article_id': row['article_id'],
                'text_content': row['text_content'],
                'embedding': emb_vector,
                'metadata': json.loads(row['metadata'] or '{}'),
                'article_title': row['title'],
                'article_url': row['url'],
                'article_date': row['published_date']
            })
        return chunks
    finally:
        conn.close()

def get_latest_articles(limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, title, url, summary, published_date, source, ingested_at
            FROM articles
            ORDER BY ingested_at DESC, published_date DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_latest_analyses(limit=5):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, ticker, analysis_date, technical_data, ai_report, created_at
            FROM analysis
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        results = []
        for row in cursor.fetchall():
            res = dict(row)
            res['technical_data'] = json.loads(res['technical_data'] or '{}')
            results.append(res)
        return results
    finally:
        conn.close()

def get_db_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM articles")
        articles_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunks_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM analysis")
        analysis_count = cursor.fetchone()[0]
        
        return {
            'articles': articles_count,
            'chunks': chunks_count,
            'analyses': analysis_count
        }
    finally:
        conn.close()

def clear_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM chunks")
        cursor.execute("DELETE FROM analysis")
        cursor.execute("DELETE FROM articles")
        conn.commit()
    finally:
        conn.close()

def get_all_analyzed_tickers():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT ticker FROM analysis ORDER BY ticker ASC")
        tickers = [row['ticker'] for row in cursor.fetchall() if row['ticker'] != 'MARKET']
        return tickers
    finally:
        conn.close()
