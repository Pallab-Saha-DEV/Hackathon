import os
from dotenv import load_dotenv
from backend import db, scraper, gemini_client, analyzer

def run_tests():
    print("==========================================")
    print("STARTING BACKEND COMPONENT VERIFICATION")
    print("==========================================")
    
    # Load Environment
    load_dotenv()
    
    # 1. Database Initialization Test
    print("\n[1/4] Testing Database Initialization...")
    try:
        db.init_db()
        stats = db.get_db_stats()
        print(f" [OK] Database initialised successfully.")
        print(f"   Current Stats: {stats['articles']} articles, {stats['chunks']} chunks, {stats['analyses']} analyses.")
    except Exception as e:
        print(f" [FAIL] Database Init Failed: {e}")
        return False
        
    # 2. Scraper Test (yfinance)
    print("\n[2/4] Testing yfinance Index Data Scraper...")
    try:
        indices = scraper.fetch_market_indices()
        print(" [OK] yfinance fetch completed.")
        for name, info in indices.items():
            print(f"   Index: {name} | Price: {info.get('price')} | Change%: {info.get('pct_change')}%")
    except Exception as e:
        print(f" [FAIL] yfinance Index Scraper Failed: {e}")
        return False
        
    # 3. Scraper Test (Moneycontrol RSS)
    print("\n[3/4] Testing Moneycontrol RSS Feed Scraper...")
    try:
        # Just grab 1 article to verify RSS connectivity and HTML parsing
        print("   Fetching from 'Buzzing Stocks' RSS feed...")
        articles = scraper.fetch_moneycontrol_news_feed('Buzzing Stocks', limit=1)
        if articles:
            art = articles[0]
            print(" [OK] Moneycontrol RSS scraped and parsed successfully.")
            print(f"   Sample Title: '{art['title'][:60]}...'")
            print(f"   Sample Content Preview (first 100 chars): {art['content'][:100]}...")
        else:
            print(" [WARNING] RSS parsed but returned no articles (might be empty or rate-limited).")
    except Exception as e:
        print(f" [FAIL] Moneycontrol RSS Scraper Failed: {e}")
        return False
        
    # 4. Gemini API Embedding Test (Conditional)
    print("\n[4/4] Testing Gemini API integration...")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("your_gemini"):
        print(" [WARNING] GEMINI_API_KEY is not configured in .env. Skipping API test.")
        print("   (To test fully, configure the key in .env or run via the Streamlit UI Sidebar.)")
    else:
        try:
            gemini_client.configure_gemini()
            print("   Generating test embedding using 'text-embedding-004'...")
            emb = gemini_client.get_embedding("Testing vector embedding creation.")
            print(f" [OK] Embedding generated. Vector dimension: {len(emb)}")
            
            # Simple test chunk insertion and RAG search
            print("   Testing database chunk insertion and local similarity lookup...")
            test_art_id = db.insert_article("Test Title", "http://test.com", "Test summary", "Test full body text content.", "2026-06-09 00:00:00", "Test Source")
            db.insert_chunk(test_art_id, 0, "Test full body text content.", emb, {'title': 'Test Title'})
            
            # Retrieve
            retrieved = analyzer.retrieve_relevant_context("vector embedding creation", top_k=1)
            if retrieved:
                print(f" [OK] Retrieve context success. Found match: '{retrieved[0]['text_content']}'")
            else:
                print(" [FAIL] Retrieve context failed to return chunks.")
                
            # Cleanup test entries
            conn = db.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chunks WHERE article_id = ?", (test_art_id,))
            cursor.execute("DELETE FROM articles WHERE id = ?", (test_art_id,))
            conn.commit()
            conn.close()
            print(" [OK] Database test entries cleaned up.")
            
        except Exception as e:
            print(f" [FAIL] Gemini API Integration Failed: {e}")
            return False
            
    print("\n==========================================")
    print("VERIFICATION COMPLETED SUCCESSFULLY!")
    print("==========================================")
    return True

if __name__ == "__main__":
    run_tests()
