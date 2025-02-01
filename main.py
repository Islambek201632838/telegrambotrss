import logging
from datetime import datetime, timedelta

import feedparser
from bs4 import BeautifulSoup
from dotenv import dotenv_values
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    JobQueue,
)

env = dotenv_values(".env")
BOT_TOKEN = env["BOT_TOKEN"]
GROUP_CHAT_ID = env["GROUP_CHAT_ID"]
RSS_URL = env["RSS_URL"]

# Track the newest article + a queue of items to post
latest_published = None
pending_entries = []

# Track the time we last actually posted
last_post_time = None
COOLDOWN = timedelta(minutes=1)  # Wait at least 3 min between messages

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def check_and_post(context: ContextTypes.DEFAULT_TYPE):
    """
    1) Parse the feed frequently to detect new items quickly.
    2) If 3 minutes have passed since the last post, post exactly one item from the queue.
    """
    global latest_published, pending_entries, last_post_time

    # 1) Parse feed to find new items
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        logging.info("No entries found in RSS feed.")
    else:
        new_entries = []
        for entry in feed.entries:
            # Evaluate published/updated time
            pub_time = None
            if getattr(entry, 'published_parsed', None):
                pub_time = datetime(*entry.published_parsed[:6])
            elif getattr(entry, 'updated_parsed', None):
                pub_time = datetime(*entry.updated_parsed[:6])

            # If it's a brand-new article, queue it
            if pub_time and (latest_published is None or pub_time > latest_published):
                new_entries.append(entry)

        if new_entries:
            # Sort older -> newer
            new_entries.sort(key=lambda x: x.published_parsed)
            # Add to the pending queue
            pending_entries.extend(new_entries)

            # Update latest_published to the newest
            newest_pub = max(
                (datetime(*e.published_parsed[:6]) if e.published_parsed else datetime.min)
                for e in new_entries
            )
            if latest_published is None or newest_pub > latest_published:
                latest_published = newest_pub

    # 2) If enough time has passed since the last post, post ONE item
    now = datetime.utcnow()
    if last_post_time is None or (now - last_post_time) >= COOLDOWN:
        if pending_entries:
            entry_to_post = pending_entries.pop(0)  # Oldest from the queue
            title = getattr(entry_to_post, 'title', 'Untitled')
            link = getattr(entry_to_post, 'link', '')
            raw_html = getattr(entry_to_post, 'summary', '')

            # Clean and escape the raw HTML content
            soup = BeautifulSoup(raw_html, "html.parser")
            clean_text = soup.get_text(separator="\n").strip()

            # Escape special characters for HTML
            def escape_html(text):
                return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            escaped_title = escape_html(title)
            escaped_text = escape_html(clean_text)

            # Build the message text with proper HTML formatting
            message_text = (
                f"<b>{escaped_title}</b>\n\n"  # Bold the title
                f"{escaped_text}\n\n"  # Cleaned-up text
                f"<a href='{link}'>Еще</a>"  # Hyperlink
            )

            # Send the message using HTML parse mode
            await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=message_text,
                parse_mode="HTML",
                disable_web_page_preview=False
            )
            logging.info(f"Posted 1 item: {title}")

            # Update last_post_time
            last_post_time = now
        else:
            logging.info("No items in queue to post.")
    else:
        # If still cooling down, do nothing
        pass

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Run check_and_post every 30 seconds so we quickly detect new posts
    job_queue: JobQueue = application.job_queue
    job_queue.run_repeating(
        callback=check_and_post,
        interval=30,   # check feed every 30s
        first=10       # start after 10s
    )

    # Start the bot (polling + job queue)
    application.run_polling()

if __name__ == "__main__":
    main()
