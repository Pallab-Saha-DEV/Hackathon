import feedparser
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import re
from datetime import datetime

# Common User Agent to prevent getting blocked by websites
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

MONEYCONTROL_FEEDS = {
    'Latest News': 'https://www.moneycontrol.com/rss/latestnews.xml',
    'Market Outlook': 'https://www.moneycontrol.com/rss/marketoutlook.xml',
    'Buzzing Stocks': 'https://www.moneycontrol.com/rss/buzzingstocks.xml'
}

def clean_html(text):
    """Remove HTML tags and clean up whitespace."""
    if not text:
        return ""
    # Remove HTML tags
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    # Normalize spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def scrape_full_article(url):
    """
    Scrapes the full article body from a Moneycontrol URL.
    Returns full text or fallback if blocked/parsing fails.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to find the article body container. Moneycontrol uses several layout classes.
        body_selectors = [
            'div.content_wrapper',
            'div.contentdata',
            'div.arti-flow',
            'div.page_left_wrapper',
            'div#article-body',
            'div.story_details',
            'div.article_box',
            'div.normal_text'
        ]
        
        paragraphs = []
        body_found = False
        
        for selector in body_selectors:
            container = soup.select_one(selector)
            if container:
                # Find all paragraph tags inside this container
                p_tags = container.find_all('p')
                if p_tags:
                    for p in p_tags:
                        text = p.get_text().strip()
                        # Avoid adding short boilerplate/social sharing paragraphs
                        if len(text) > 40 and not text.startswith("Also Read:") and not text.startswith("Follow our live blog"):
                            paragraphs.append(text)
                    body_found = True
                    break
        
        # Fallback: if no container is found, get all paragraphs from the body
        if not body_found:
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if len(text) > 50 and not text.startswith("Also Read:") and not "Disclaimer" in text:
                    paragraphs.append(text)
                    
        if paragraphs:
            return "\n\n".join(paragraphs)
        return None
    except Exception as e:
        print(f"Error scraping article at {url}: {e}")
        return None

def fetch_moneycontrol_news_feed(feed_name, limit=10):
    """
    Fetches articles from a Moneycontrol RSS feed, including their full scraped text.
    """
    feed_url = MONEYCONTROL_FEEDS.get(feed_name)
    if not feed_url:
        raise ValueError(f"Feed name '{feed_name}' not found.")
        
    print(f"Parsing feed: {feed_name} from {feed_url}")
    feed = feedparser.parse(feed_url)
    
    articles = []
    for entry in feed.entries[:limit]:
        title = clean_html(getattr(entry, 'title', ''))
        link = getattr(entry, 'link', '')
        summary = clean_html(getattr(entry, 'summary', getattr(entry, 'description', '')))
        
        # Parse publication date
        pub_date_str = getattr(entry, 'published', '')
        # Try parsing it to standardize, otherwise store string
        try:
            pub_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pub_date = pub_date_str
            
        print(f"Scraping full text for: {title[:50]}...")
        full_content = scrape_full_article(link)
        
        # Fallback to summary if full content scraper failed
        if not full_content:
            full_content = summary
            
        articles.append({
            'title': title,
            'url': link,
            'summary': summary,
            'content': full_content,
            'published_date': pub_date,
            'source': f"Moneycontrol ({feed_name})"
        })
        
    return articles

def fetch_market_indices():
    """
    Fetches current data for major indices (Nifty 50, Sensex, Nifty Bank).
    """
    indices = {
        'Nifty 50': '^NSEI',
        'Sensex': '^BSESN',
        'Nifty Bank': '^NSEBANK'
    }
    
    summary = {}
    for name, ticker in indices.items():
        try:
            t = yf.Ticker(ticker)
            # Fetch 1 day data with small intervals (e.g. 5m) to get current and previous close
            history = t.history(period='2d')
            if not history.empty and len(history) >= 1:
                latest = history.iloc[-1]
                prev_close = history.iloc[-2]['Close'] if len(history) >= 2 else latest['Open']
                current_price = latest['Close']
                change = current_price - prev_close
                pct_change = (change / prev_close) * 100
                
                summary[name] = {
                    'price': round(current_price, 2),
                    'change': round(change, 2),
                    'pct_change': round(pct_change, 2),
                    'high': round(latest['High'], 2),
                    'low': round(latest['Low'], 2),
                    'volume': int(latest['Volume']),
                    'date': history.index[-1].strftime("%Y-%m-%d")
                }
            else:
                summary[name] = {'price': 'N/A', 'change': 'N/A', 'pct_change': 'N/A'}
        except Exception as e:
            print(f"Error fetching index {name}: {e}")
            summary[name] = {'price': 'N/A', 'change': 'N/A', 'pct_change': 'N/A'}
            
    return summary

COMMON_MAPPINGS = {
    # ── Reliance ──
    'RELIANCE INDUSTRIES': 'RELIANCE',
    'RELIANCE': 'RELIANCE',
    'RIL': 'RELIANCE',

    # ── TCS ──
    'TATA CONSULTANCY SERVICES': 'TCS',
    'TATA CONSULTANCY': 'TCS',
    'TCS': 'TCS',

    # ── Infosys ──
    'INFOSYS': 'INFY',
    'INFY': 'INFY',

    # ── HDFC Bank ──
    'HDFC BANK': 'HDFCBANK',
    'HDFCBANK': 'HDFCBANK',

    # ── ICICI Bank ──
    'ICICI BANK': 'ICICIBANK',
    'ICICI': 'ICICIBANK',

    # ── Bharti Airtel ──
    'BHARTI AIRTEL': 'BHARTIARTL',
    'AIRTEL': 'BHARTIARTL',
    'BHARTIARTL': 'BHARTIARTL',

    # ── SBI ──
    'STATE BANK OF INDIA': 'SBIN',
    'SBI': 'SBIN',

    # ── ITC ──
    'ITC': 'ITC',
    'ITC LTD': 'ITC',

    # ── L&T ──
    'LARSEN & TOUBRO': 'LT',
    'LARSEN AND TOUBRO': 'LT',
    'L&T': 'LT',

    # ── HUL ──
    'HINDUSTAN UNILEVER': 'HINDUNILVR',
    'HUL': 'HINDUNILVR',
    'HINDUNILVR': 'HINDUNILVR',

    # ── Axis Bank ──
    'AXIS BANK': 'AXISBANK',
    'AXISBANK': 'AXISBANK',

    # ── Kotak Mahindra ──
    'KOTAK MAHINDRA': 'KOTAKBANK',
    'KOTAK MAHINDRA BANK': 'KOTAKBANK',
    'KOTAK BANK': 'KOTAKBANK',
    'KOTAKBANK': 'KOTAKBANK',

    # ── Wipro ──
    'WIPRO': 'WIPRO',

    # ── HCL Tech ──
    'HCL TECHNOLOGIES': 'HCLTECH',
    'HCL TECH': 'HCLTECH',
    'HCLTECH': 'HCLTECH',

    # ── Tata Motors ──
    'TATA MOTORS': 'TATAMOTORS',
    'TATAMOTORS': 'TATAMOTORS',

    # ── Tata Steel ──
    'TATA STEEL': 'TATASTEEL',
    'TATASTEEL': 'TATASTEEL',

    # ── Sun Pharma ──
    'SUN PHARMACEUTICAL': 'SUNPHARMA',
    'SUN PHARMA': 'SUNPHARMA',
    'SUNPHARMA': 'SUNPHARMA',

    # ── Maruti ──
    'MARUTI SUZUKI': 'MARUTI',
    'MARUTI': 'MARUTI',

    # ── Adani Group ──
    'ADANI ENTERPRISES': 'ADANIENT',
    'ADANIENT': 'ADANIENT',
    'ADANI PORTS': 'ADANIPORTS',
    'ADANI PORT': 'ADANIPORTS',
    'ADANIPORTS': 'ADANIPORTS',
    'ADANI GREEN': 'ADANIGREEN',
    'ADANIGREEN': 'ADANIGREEN',
    'ADANI POWER': 'ADANIPOWER',
    'ADANIPOWER': 'ADANIPOWER',
    'ADANI TOTAL GAS': 'ATGL',
    'ATGL': 'ATGL',
    'ADANI WILMAR': 'AWL',

    # ── NTPC ──
    'NTPC': 'NTPC',
    'NTPC LTD': 'NTPC',

    # ── Power Grid ──
    'POWER GRID': 'POWERGRID',
    'POWERGRID': 'POWERGRID',
    'POWER GRID CORPORATION': 'POWERGRID',

    # ── ONGC ──
    'ONGC': 'ONGC',
    'OIL AND NATURAL GAS': 'ONGC',

    # ── JSW Steel ──
    'JSW STEEL': 'JSWSTEEL',
    'JSWSTEEL': 'JSWSTEEL',

    # ── Bajaj Finance ──
    'BAJAJ FINANCE': 'BAJFINANCE',
    'BAJFINANCE': 'BAJFINANCE',
    'BAJAJ FINSERV': 'BAJAJFINSV',
    'BAJAJFINSV': 'BAJAJFINSV',

    # ── Asian Paints ──
    'ASIAN PAINTS': 'ASIANPAINT',
    'ASIANPAINT': 'ASIANPAINT',

    # ── Ultratech Cement ──
    'ULTRATECH CEMENT': 'ULTRACEMCO',
    'ULTRACEMCO': 'ULTRACEMCO',

    # ── Titan ──
    'TITAN': 'TITAN',
    'TITAN COMPANY': 'TITAN',

    # ── Nestle ──
    'NESTLE INDIA': 'NESTLEIND',
    'NESTLE': 'NESTLEIND',
    'NESTLEIND': 'NESTLEIND',

    # ── Dr. Reddy's ──
    "DR REDDY'S": 'DRREDDY',
    'DR REDDYS': 'DRREDDY',
    'DRREDDY': 'DRREDDY',

    # ── Cipla ──
    'CIPLA': 'CIPLA',

    # ── Divis Labs ──
    'DIVIS LABORATORIES': 'DIVISLAB',
    'DIVIS LAB': 'DIVISLAB',
    'DIVISLAB': 'DIVISLAB',

    # ── Tech Mahindra ──
    'TECH MAHINDRA': 'TECHM',
    'TECHM': 'TECHM',

    # ── IndusInd Bank ──
    'INDUSIND BANK': 'INDUSINDBK',
    'INDUSIND': 'INDUSINDBK',
    'INDUSINDBK': 'INDUSINDBK',

    # ── M&M ──
    'MAHINDRA & MAHINDRA': 'M&M',
    'MAHINDRA AND MAHINDRA': 'M&M',
    'M&M': 'M&M',

    # ── Grasim ──
    'GRASIM': 'GRASIM',
    'GRASIM INDUSTRIES': 'GRASIM',

    # ── Apollo Hospitals ──
    'APOLLO HOSPITALS': 'APOLLOHOSP',
    'APOLLOHOSP': 'APOLLOHOSP',

    # ── Hindalco ──
    'HINDALCO': 'HINDALCO',
    'HINDALCO INDUSTRIES': 'HINDALCO',

    # ── Tata Consumer ──
    'TATA CONSUMER': 'TATACONSUM',
    'TATA CONSUMER PRODUCTS': 'TATACONSUM',
    'TATACONSUM': 'TATACONSUM',

    # ── Coal India ──
    'COAL INDIA': 'COALINDIA',
    'COALINDIA': 'COALINDIA',

    # ── BPCL ──
    'BHARAT PETROLEUM': 'BPCL',
    'BPCL': 'BPCL',

    # ── IOC ──
    'INDIAN OIL': 'IOC',
    'INDIAN OIL CORPORATION': 'IOC',
    'IOC': 'IOC',

    # ── Zomato / Eternal ──
    'ZOMATO': 'ZOMATO',
    'ETERNAL': 'ETERNAL',
    'ETERNAL LIMITED': 'ETERNAL',

    # ── Paytm ──
    'PAYTM': 'PAYTM',
    'ONE97 COMMUNICATIONS': 'PAYTM',

    # ── Nykaa ──
    'NYKAA': 'NYKAA',
    'FSN E-COMMERCE': 'NYKAA',

    # ── Dmart ──
    'DMART': 'DMART',
    'AVENUE SUPERMARTS': 'DMART',

    # ── Vedanta ──
    'VEDANTA': 'VEDL',
    'VEDL': 'VEDL',

    # ── Trent ──
    'TRENT': 'TRENT',

    # ── LTIMindtree ──
    'LTIMINDTREE': 'LTIM',
    'LTI MINDTREE': 'LTIM',
    'LTIM': 'LTIM',

    # ── Persistent Systems ──
    'PERSISTENT SYSTEMS': 'PERSISTENT',
    'PERSISTENT': 'PERSISTENT',

    # ── Mphasis ──
    'MPHASIS': 'MPHASIS',

    # ── HAL ──
    'HAL': 'HAL',
    'HINDUSTAN AERONAUTICS': 'HAL',

    # ── BEL ──
    'BEL': 'BEL',
    'BHARAT ELECTRONICS': 'BEL',

    # ── SBI Life ──
    'SBI LIFE': 'SBILIFE',
    'SBILIFE': 'SBILIFE',

    # ── HDFC Life ──
    'HDFC LIFE': 'HDFCLIFE',
    'HDFCLIFE': 'HDFCLIFE',

    # ── ICICI Prudential ──
    'ICICI PRUDENTIAL': 'ICICIPRULI',
    'ICICIPRULI': 'ICICIPRULI',

    # ── Bandhan Bank ──
    'BANDHAN BANK': 'BANDHANBNK',
    'BANDHAN': 'BANDHANBNK',
    'BANDHANBNK': 'BANDHANBNK',

    # ── Bank of Baroda ──
    'BANK OF BARODA': 'BANKBARODA',
    'BOB': 'BANKBARODA',
    'BANKBARODA': 'BANKBARODA',

    # ── Manappuram Finance ──
    'MANAPPURAM FINANCE': 'MANAPPURAM',
    'MANAPPURAM': 'MANAPPURAM',

    # ── Vodafone Idea ──
    'VODAFONE IDEA': 'IDEA',
    'VODAFONE': 'IDEA',
    'VI': 'IDEA',
    'IDEA': 'IDEA',

    # ── Gujarat State Petronet ──
    'GUJARAT STATE PETRONET': 'GSPL',
    'GSPL': 'GSPL',

    # ── PSP Projects ──
    'PSP PROJECTS': 'PSPPROJECT',
    'PSPPROJECT': 'PSPPROJECT',

    # ── PNB ──
    'PUNJAB NATIONAL BANK': 'PNB',
    'PNB': 'PNB',

    # ── Canara Bank ──
    'CANARA BANK': 'CANBK',
    'CANBK': 'CANBK',

    # ── Union Bank ──
    'UNION BANK OF INDIA': 'UNIONBANK',
    'UNION BANK': 'UNIONBANK',

    # ── Muthoot Finance ──
    'MUTHOOT FINANCE': 'MUTHOOTFIN',
    'MUTHOOTFIN': 'MUTHOOTFIN',

    # ── Motherson Sumi ──
    'MOTHERSON SUMI': 'MOTHERSON',
    'MOTHERSON': 'MOTHERSON',
    'SAMVARDHANA MOTHERSON': 'MOTHERSON',

    # ── Hero MotoCorp ──
    'HERO MOTOCORP': 'HEROMOTOCO',
    'HERO MOTO': 'HEROMOTOCO',
    'HEROMOTOCO': 'HEROMOTOCO',

    # ── Bajaj Auto ──
    'BAJAJ AUTO': 'BAJAJ-AUTO',
    'BAJAJ-AUTO': 'BAJAJ-AUTO',

    # ── Eicher Motors ──
    'EICHER MOTORS': 'EICHERMOT',
    'EICHERMOT': 'EICHERMOT',

    # ── Shriram Finance ──
    'SHRIRAM FINANCE': 'SHRIRAMFIN',
    'SHRIRAMFIN': 'SHRIRAMFIN',

    # ── Cholamandalam ──
    'CHOLAMANDALAM': 'CHOLAFIN',
    'CHOLA': 'CHOLAFIN',

    # ── Dixon Technologies ──
    'DIXON TECHNOLOGIES': 'DIXON',
    'DIXON': 'DIXON',

    # ── Polycab ──
    'POLYCAB': 'POLYCAB',
    'POLYCAB INDIA': 'POLYCAB',

    # ── Havells ──
    'HAVELLS': 'HAVELLS',
    'HAVELLS INDIA': 'HAVELLS',

    # ── Crompton ──
    'CROMPTON': 'CROMPTON',
    'CROMPTON GREAVES': 'CROMPTON',

    # ── ABB India ──
    'ABB INDIA': 'ABB',
    'ABB': 'ABB',

    # ── Siemens ──
    'SIEMENS': 'SIEMENS',
    'SIEMENS INDIA': 'SIEMENS',

    # ── Bharat Forge ──
    'BHARAT FORGE': 'BHARATFORG',
    'BHARATFORG': 'BHARATFORG',

    # ── Cummins ──
    'CUMMINS INDIA': 'CUMMINSIND',
    'CUMMINSIND': 'CUMMINSIND',

    # ── Torrent Power ──
    'TORRENT POWER': 'TORNTPOWER',
    'TORNTPOWER': 'TORNTPOWER',

    # ── Torrent Pharma ──
    'TORRENT PHARMA': 'TORNTPHARM',
    'TORNTPHARM': 'TORNTPHARM',

    # ── Lupin ──
    'LUPIN': 'LUPIN',

    # ── Aurobindo Pharma ──
    'AUROBINDO PHARMA': 'AUROPHARMA',
    'AUROBINDO': 'AUROPHARMA',
    'AUROPHARMA': 'AUROPHARMA',

    # ── Biocon ──
    'BIOCON': 'BIOCON',

    # ── Jubilant FoodWorks ──
    'JUBILANT FOODWORKS': 'JUBLFOOD',
    'JUBILANT FOOD': 'JUBLFOOD',
    'JUBLFOOD': 'JUBLFOOD',

    # ── Swiggy ──
    'SWIGGY': 'SWIGGY',

    # ── Ola Electric ──
    'OLA ELECTRIC': 'OLAELECTRIC',
    'OLA': 'OLAELECTRIC',

    # ── InterGlobe Aviation (IndiGo) ──
    'INTERGLOBE AVIATION': 'INDIGO',
    'INDIGO': 'INDIGO',
    'INDIGO AIRLINES': 'INDIGO',

    # ── Varun Beverages ──
    'VARUN BEVERAGES': 'VBL',
    'VBL': 'VBL',

    # ── Page Industries ──
    'PAGE INDUSTRIES': 'PAGEIND',
    'PAGEIND': 'PAGEIND',

    # ── Godrej Consumer ──
    'GODREJ CONSUMER': 'GODREJCP',
    'GODREJCP': 'GODREJCP',

    # ── Marico ──
    'MARICO': 'MARICO',

    # ── Colgate ──
    'COLGATE': 'COLPAL',
    'COLGATE PALMOLIVE': 'COLPAL',
    'COLPAL': 'COLPAL',

    # ── PI Industries ──
    'PI INDUSTRIES': 'PIIND',
    'PIIND': 'PIIND',

    # ── Coromandel ──
    'COROMANDEL INTERNATIONAL': 'COROMANDEL',
    'COROMANDEL': 'COROMANDEL',

    # ── Zee Entertainment ──
    'ZEE ENTERTAINMENT': 'ZEEL',
    'ZEEL': 'ZEEL',
    'ZEE': 'ZEEL',

    # ── PVR Inox ──
    'PVR INOX': 'PVRINOX',
    'PVR': 'PVRINOX',
    'PVRINOX': 'PVRINOX',
}

def normalize_ticker(ticker):
    """
    Normalises stock ticker names, appending .NS (NSE) by default if no exchange suffix is present.
    Also maps common company names to their correct stock ticker codes.
    """
    if not ticker:
        return ticker
    ticker = ticker.strip().upper()
    
    # Strip common suffixes
    clean_ticker = ticker.replace(" LTD", "").replace(" LIMITED", "").strip()
    
    # Map common names to tickers
    if clean_ticker in COMMON_MAPPINGS:
        ticker = COMMON_MAPPINGS[clean_ticker]
        
    if ticker.startswith('^'):
        return ticker
    if '.' in ticker:
        return ticker
    return f"{ticker}.NS"

def fetch_stock_financials(ticker):
    """
    Fetches financial metrics and profile data for a specific stock ticker using yfinance.
    Normalises the ticker to append .NS if needed.
    """
    ticker = normalize_ticker(ticker)
    try:
        t = yf.Ticker(ticker)
        info = t.info
        
        financials = {
            'name': info.get('longName', ticker),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'current_price': info.get('currentPrice', info.get('regularMarketPrice', 'N/A')),
            'market_cap': info.get('marketCap', 'N/A'),
            'pe_ratio': info.get('trailingPE', 'N/A'),
            'forward_pe': info.get('forwardPE', 'N/A'),
            'dividend_yield': info.get('dividendYield', 'N/A'),
            'fifty_two_week_high': info.get('fiftyTwoWeekHigh', 'N/A'),
            'fifty_two_week_low': info.get('fiftyTwoWeekLow', 'N/A'),
            'summary': info.get('longBusinessSummary', 'No description available.')
        }
        
        # Format dividend yield
        if isinstance(financials['dividend_yield'], (int, float)):
            financials['dividend_yield'] = f"{round(financials['dividend_yield'] * 100, 2)}%"
            
        return financials
    except Exception as e:
        print(f"Error fetching financials for {ticker}: {e}")
        return None

def fetch_stock_news(ticker):
    """
    Fetches news related to a stock using yfinance.
    Normalises the ticker to append .NS if needed.
    """
    ticker = normalize_ticker(ticker)
    try:
        t = yf.Ticker(ticker)
        news = t.news
        articles = []
        for item in news[:10]:
            articles.append({
                'title': item.get('title'),
                'url': item.get('link'),
                'summary': item.get('summary', item.get('title')),
                'content': item.get('summary', item.get('title')),
                'published_date': datetime.fromtimestamp(item.get('providerPublishTime', 0)).strftime("%Y-%m-%d %H:%M:%S"),
                'source': item.get('publisher', 'Finance News')
            })
        return articles
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")
        return []
