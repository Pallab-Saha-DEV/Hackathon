from google import genai
from google.genai import types
import os
import hashlib
import numpy as np
from dotenv import load_dotenv

# Load env variables if present
load_dotenv()

def get_api_key(ui_api_key=None):
    """Returns API key — from UI input first, then environment variable."""
    if ui_api_key:
        return ui_api_key
    return os.getenv("GEMINI_API_KEY")

def is_gemini_configured(ui_api_key=None):
    api_key = get_api_key(ui_api_key)
    return bool(api_key and not api_key.startswith("your_gemini") and len(api_key) > 10)

def _get_client(ui_api_key=None):
    """Creates and returns a configured Gemini client."""
    api_key = get_api_key(ui_api_key)
    if not api_key:
        raise ValueError("Gemini API Key is missing. Set GEMINI_API_KEY in your .env file.")
    return genai.Client(api_key=api_key)

# ─────────────────────────────────────────────
# EMBEDDINGS
# ─────────────────────────────────────────────

def get_mock_embedding(text):
    """
    Deterministic unit-vector embedding (768-dim) derived from SHA256 of input.
    Used as fallback when no API key is configured so RAG similarity still works.
    """
    h = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(h[:4], byteorder="big")
    rng = np.random.default_rng(seed)
    vec = rng.normal(size=768)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()

def get_embedding(text, ui_api_key=None):
    """
    Generates vector embeddings using Gemini text-embedding-004.
    Falls back to deterministic mock embeddings if no API key is configured.
    """
    if not is_gemini_configured(ui_api_key):
        return get_mock_embedding(text)

    try:
        client = _get_client(ui_api_key)
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"Embedding error: {e}. Falling back to mock embedding.")
        return get_mock_embedding(text)

# ─────────────────────────────────────────────
# MOCK RESPONSES (no API key)
# ─────────────────────────────────────────────

def generate_mock_response(prompt, context_chunks):
    sources_str = ""
    for chunk in context_chunks:
        sources_str += (
            f"- **{chunk['article_title']}** "
            f"(Published: {chunk['article_date'] or 'Unknown'}) "
            f"| [Read Source]({chunk['article_url']})\n"
        )

    return f"""
*(Running in Demo Mock Mode — add your free Gemini API Key in the sidebar to enable live AI responses.)*

### Simulated Analyst Intelligence Report

Regarding your question **"{prompt}"**, we analysed our local Moneycontrol knowledge base
(retrieved **{len(context_chunks)}** related snippets):

1. **Market Summary**: Recent news indicates active institutional participation and trading focus on support/resistance zones.
2. **Key Context Insights**:
   - Institutional block deals and FII position shifts are influencing general sentiment.
   - Specific buzzing sectors include banking, infrastructure, and technology.
3. **Analytical Perspective**: Technical indexes reflect standard consolidation, with moving average guidelines remaining relevant for short-term support.

---

#### Retrieved Snippet References:
{sources_str if sources_str else "*No matching articles found. Trigger Daily Ingestion from the sidebar first.*"}

*Disclaimer: This is a simulated RAG response. Add your free Gemini API Key to enable live generative replies.*
"""

def generate_mock_daily_summary(news_articles):
    buzzing_str = "\n".join(
        f"- **{art['title']}**: Scraped from {art['source']}. [Link]({art['url']})"
        for art in news_articles[:5]
    ) or "*No articles scraped today. Click 'Trigger Daily Ingestion' in the sidebar.*"

    return f"""
*(Running in Demo Mock Mode — add your free Gemini API Key in the sidebar to enable live AI responses.)*

### Daily Market Outlook Briefing (Simulated)

#### 1. Key Market Themes
- **High Institutional Volume**: Bulk deals by major financial firms are driving price actions.
- **Corporate Restructuring & Earnings**: Markets are monitoring board updates and financial reporting.

#### 2. Buzzing News Headlines Today
{buzzing_str}

#### 3. Technical Sentiment Outlook
- **Sentiment**: **Neutral to Consolidating**
- **Support Zones**: Supported by moving averages at lower index boundaries.
- **Upside Target**: Upper consolidation ranges present minor selling pressure.
"""

# ─────────────────────────────────────────────
# LIVE AI RESPONSES
# ─────────────────────────────────────────────

def generate_response(prompt, context_chunks, ui_api_key=None):
    """
    Generates answers using RAG context via Gemini.
    Falls back to a structured mock response if no API key is configured.
    """
    if not is_gemini_configured(ui_api_key):
        return generate_mock_response(prompt, context_chunks)

    context_str = ""
    for i, chunk in enumerate(context_chunks):
        context_str += f"--- Source {i+1}: {chunk['article_title']} ({chunk['article_date'] or 'Unknown Date'}) ---\n"
        context_str += f"URL: {chunk['article_url']}\n"
        context_str += f"Content: {chunk['text_content']}\n\n"

    system_instruction = (
        "You are an expert share market analyst. Your task is to provide accurate stock predictions, analysis, "
        "and market insights based on the provided context retrieved from Moneycontrol feeds and historical daily reports. "
        "Strictly adhere to the following rules:\n"
        "1. If the provided context doesn't contain enough information to answer the question, state that clearly, "
        "   but still provide general professional market guidelines based on your knowledge.\n"
        "2. Provide clear, structural, and professional stock reports (bullish/bearish factors, price indicators).\n"
        "3. Include citations/sources (Article Title and URL) when citing specific news from the context.\n"
        "4. Clarify that your predictions are analytical and not financial advice."
    )

    full_prompt = f"""Here is the context retrieved from our market intelligence database:
{context_str}

User Question: {prompt}
"""

    try:
        client = _get_client(ui_api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
            ),
        )
        return response.text
    except Exception as e:
        return f"Failed to generate response: {e}"


def generate_daily_summary(news_articles, ui_api_key=None):
    """
    Generates a high-level daily market briefing from today's headlines.
    Falls back to mock summary if no API key is configured.
    """
    if not is_gemini_configured(ui_api_key):
        return generate_mock_daily_summary(news_articles)

    articles_summary = ""
    for i, art in enumerate(news_articles[:15]):
        articles_summary += f"[{i+1}] Title: {art['title']}\n"
        articles_summary += f"Summary: {art['summary']}\n\n"

    prompt = f"""Analyze the following list of today's financial news headlines and summaries:
{articles_summary}

Generate a concise, professional Market Overview report containing:
1. **Key Market Themes**: Summarize the dominant trends or events driving the market today.
2. **Buzzing Stocks**: List specific stocks mentioned with a short summary of why they are buzzing.
3. **Sentiment Outlook**: A brief outlook (Bullish, Bearish, or Neutral/Consolidating) for the upcoming sessions.
Format the output in clean Markdown.
"""
    try:
        client = _get_client(ui_api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Error generating daily summary: {e}"
