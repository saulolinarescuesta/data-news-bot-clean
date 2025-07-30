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
    # Mood of the Day
    all_titles = [a["title"] for articles in articles_by_category.values() for a in articles]
    mood_prompt = (
        "Given these news headlines, describe the overall 'Mood of the Day' in one concise line "
        "and give it a priority (High/Medium/Low):\n\n" + "\n".join(all_titles)
    )
    mood_result = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": mood_prompt}],
        max_tokens=50,
    )
    mood_text = mood_result.choices[0].message.content.strip()

    # Summary for Data Analysts
    summary_prompt = (
        "Given the following news headlines, write 3 bullet points summarizing what data analysts should focus on today:\n\n"
        + "\n".join(all_titles)
    )
    summary_result = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": summary_prompt}],
        max_tokens=120,
    )
    summary_text = summary_result.choices[0].message.content.strip()

    # What to Watch Today
    watch_prompt = (
        "From the headlines, suggest 3 'What to Watch Today' points with clear focus areas for analysts."
    )
    watch_result = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": watch_prompt}],
        max_tokens=100,
    )
    watch_text = watch_result.choices[0].message.content.strip()

    # Build Slack blocks
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "📰 DAILY DATA & AI DIGEST"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*🌟 Mood of the Day:* {mood_text}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*📊 Summary for Data Analysts:*\n{summary_text}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*👀 What to Watch Today:*\n{watch_text}"}},
        {"type": "divider"},
    ]

    return blocks

def create_category_blocks(articles_by_category):
    blocks = []
    for category, articles in articles_by_category.items():
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{category}*"}})
        for art in articles:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"• <{art['link']}|{art['title']}>"}
            })
        blocks.append({"type": "divider"})
    return blocks

def post_to_slack(blocks):
    slack_client.chat_postMessage(channel=CHANNEL_ID, blocks=blocks)

# ========== MAIN ==========
if __name__ == "__main__":
    print("Fetching news...")
    articles_by_category = fetch_articles(NEWS_FEEDS, LIMIT_PER_CATEGORY)

    print("Building summary blocks...")
    top_blocks = create_summary_blocks(articles_by_category)

    print("Building category blocks...")
    category_blocks = create_category_blocks(articles_by_category)

    print("Posting to Slack...")
    post_to_slack(top_blocks + category_blocks)
    print("✅ Digest posted with Block Kit!")


