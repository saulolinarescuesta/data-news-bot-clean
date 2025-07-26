import os
import feedparser
from slack_sdk import WebClient
from openai import OpenAI

# ========== CONFIG ==========
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# News sources by category (we will only take 3 per category)
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
LIMIT_PER_CATEGORY = 3  # Only 3 news per categoryD
# ========== CLIENTS ==========
slack_client = WebClient(token=SLACK_BOT_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ========== FUNCTIONS ==========
def fetch_articles(feeds_by_category, limit_per_category=3):
    """Fetch RSS articles and limit to 3 total per category"""
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


def create_summary_for_analysts(articles_by_category):
    """Create a top summary for data analysts"""
    all_titles = []
    for articles in articles_by_category.values():
        all_titles.extend([a["title"] for a in articles])

    prompt = (
        "Given the following news headlines, write a concise summary (3-4 bullet points) "
        "about what data analysts should focus on today to improve their work:\n\n" 
        + "\n".join(all_titles)
    )

    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
    )
    return completion.choices[0].message.content.strip()


def summarize_articles_with_links(articles_by_category, top_summary):
    """Generate Slack-formatted digest with summary, categories, and clickable links"""
    message = ":newspaper: *Daily Data & AI Digest*\n\n"
    message += f"*Summary for Data Analysts*\n{top_summary}\n\n"

    for category, articles in articles_by_category.items():
        message += f"*{category}*\n"
        for art in articles:
            completion = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user", 
                        "content": (
                            f"Summarize this news headline in 1 line for data analysts:\n{art['title']}"
                        )
                    }
                ],
                max_tokens=50,
            )
            short_summary = completion.choices[0].message.content.strip()
            message += f"• <{art['link']}|{short_summary}>\n"
        message += "\n"
    return message


def post_to_slack(message):
    """Post message to Slack channel"""
    slack_client.chat_postMessage(channel=CHANNEL_ID, text=message)


# ========== MAIN ==========
if __name__ == "__main__":
    print("Fetching news...")
    articles_by_category = fetch_articles(NEWS_FEEDS, LIMIT_PER_CATEGORY)

    print("Creating top summary for data analysts...")
    top_summary = create_summary_for_analysts(articles_by_category)

    print("Building digest...")
    digest_message = summarize_articles_with_links(articles_by_category, top_summary)

    print("Posting to Slack...")
    post_to_slack(digest_message)
    print("✅ Digest posted!")
