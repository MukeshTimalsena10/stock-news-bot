import discord
import requests
import asyncio
import yfinance as yf
from datetime import datetime as dt
import os

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
BENZINGA_API_KEY = os.getenv("BENZINGA_API_KEY")

intents = discord.Intents.default()
client = discord.Client(intents=intents)

last_posted = set()  # To avoid duplicates

def get_stock_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        price = stock.info.get("regularMarketPrice")
        return price
    except Exception:
        return None

def fetch_benzinga_news():
    url = "https://api.benzinga.com/api/v2/news"
    params = {
        "token": BENZINGA_API_KEY,
        "channels": "General",
        "limit": 20,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            print(f"❌ Benzinga API error: {response.status_code} | {response.text[:100]}")
            return []

        try:
            data = response.json()
        except Exception:
            print("❌ Benzinga returned non-JSON or empty response.")
            return []

    except Exception as e:
        print(f"❌ Error fetching Benzinga news: {e}")
        return []

    news_list = []
    for item in data:
        tickers = item.get("stocks", [])
        link = item.get("url")
        title = item.get("title", "")
        summary = item.get("teaser", "") or item.get("description", "")

        if not tickers or link in last_posted:
            continue

        for t in tickers:
            price = get_stock_price(t)
            if price and 1 <= price <= 10:
                headline = f"**[{t}] {title}**"
                time = dt.fromtimestamp(item["created"]).strftime("%Y-%m-%d %H:%M")
                news_list.append(f"{headline}\n{link}\n💲Price: ${price:.2f} | 🕒 {time}")
                last_posted.add(link)
                break

    return news_list

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

    channel = client.get_channel(CHANNEL_ID)
    try:
        await channel.send("✅ StockNewsBot is online! Monitoring news for $1-$10 stocks.")
        print("✅ Test message sent to Discord.")
    except Exception as e:
        print(f"❌ Failed to send test message: {e}")

    while True:
        news = fetch_benzinga_news()
        now = dt.now().strftime("%Y-%m-%d %H:%M:%S")
        if news:
            for n in news:
                await channel.send(n)
            print(f"{now} — Posted {len(news)} news item(s).")
        else:
            print(f"{now} — Checked Benzinga news — no new news found.")
        await asyncio.sleep(120)

client.run(DISCORD_TOKEN)
