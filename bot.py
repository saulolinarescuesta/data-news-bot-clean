import os
import feedparser
from slack_sdk import WebClient
from openai import OpenAI

# ========== CONFIG ==========
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

NEWS_FEEDS = {
    "Data & AI": [
        "https://www.dataversity.net/feed/",
        "https://towardsdatascience.com/feed",
        "https://techcrunch.com/tag/artificial-intelligence/feed"
    ],
    "Tech News": [
        "https://www.cnbc.com/id/19854910/device/rss/rss.html",
        "https://www.theverge.com/rss/index.xml",
        "https://www.wired.com/feed/rss"
    ],
    "Political & Economic": [
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://www.economist.com/sections/united-states/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
        "https://www.ft.com/world/us?format=rss"
    ]
}
LIMIT_PER_CATEGORY = 3

# ========== CLIENTS ==========
slack_client = WebClient(token=SLACK_BOT_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ========== FUNCTIONS ==========
def fetch_articles(feeds_by_category, limit_per_category=3):
    """Fetch RSS articles and limit to 3 per category"""
    all_articles = {}
    for category, feeds in feeds_by_category.items():
        articles = []
        for url in feeds:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                articles.append({"title": entry.title, "link": entry.link})
                if len(articles) >= limit_per_category:
                    break
            if len(articles) >= limit_per_category:
                break
        all_articles[category] = articles
    return all_articles


def create_summary_blocks(articles_by_category):
    """Generate Slack blocks: Mood of the Day, Summary, and Cuesta Relevance"""
    all_titles = [a["title"] for articles in articles_by_category.values() for a in articles]

    # Mood of the Day
    mood_prompt = (
        "Given these news headlines, write 1 line for 'Mood of the Day' "
        "and assign a priority (High/Medium/Low). Headlines:\n\n" + "\n".join(all_titles)
    )
    mood_text = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": mood_prompt}],
        max_tokens=60,
    ).choices[0].message.content.strip()

    # Summary for Analysts
    summary_prompt = (
        "Write 3 short bullet points summarizing what data/business analysts should focus on today:\n\n"
        + "\n".join(all_titles)
    )
    summary_text = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": summary_prompt}],
        max_tokens=120,
    ).choices[0].message.content.strip()

    # Cuesta Relevance
    cuesta_prompt = (
        "Based on these news headlines, how might this news be relevant to a consulting firm like "
        "Cuesta Partners that focuses on data/AI, private equity diligence, and digital transformation? "
        "Write 2-3 sentences.\n\n" + "\n".join(all_titles)
    )
    cuesta_relevance = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": cuesta_prompt}],
        max_tokens=100,
    ).choices[0].message.content.strip()

    # Format as Slack blocks
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "📰 DAILY DATA & AI DIGEST"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*🌟 Mood of the Day:*\n{mood_text}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*📊 Summary for Cuestans:*\n{summary_text}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*🏢 Cuesta Relevance:*\n{cuesta_relevance}"}},
        {"type": "divider"}
    ]
    return blocks


def summarize_articles_with_links(articles_by_category):
    """Return formatted text with clickable news links (3 per category)"""
    message = ""
    emojis = {
        "Data & AI": "🤖",
        "Tech News": "💻",
        "Political & Economic": "🌍"
    }
    for category, articles in articles_by_category.items():
        message += f"*{emojis.get(category, '')} {category}*\n"
        for art in articles:
            summary = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": f"Summarize this headline in 1 line for analysts:\n{art['title']}"
                    }
                ],
                max_tokens=50,
            )
            short_summary = summary.choices[0].message.content.strip()
            message += f"• <{art['link']}|{short_summary}>\n"
        message += "\n"
    return message


def post_to_slack(blocks, message):
    """Post top blocks and then news links in separate messages"""
    # Post summary blocks
    slack_client.chat_postMessage(channel=CHANNEL_ID, blocks=blocks)

    # Post news links in a separate clean message
    slack_client.chat_postMessage(channel=CHANNEL_ID, text=message)


# ========== MAIN ==========
if __name__ == "__main__":
    print("Fetching news...")
    articles_by_category = fetch_articles(NEWS_FEEDS, LIMIT_PER_CATEGORY)

    print("Creating top summary...")
    top_blocks = create_summary_blocks(articles_by_category)

    print("Building article list...")
    digest_message = summarize_articles_with_links(articles_by_category)

    print("Posting to Slack...")
    post_to_slack(top_blocks, digest_message)
    print("✅ Digest posted!")

