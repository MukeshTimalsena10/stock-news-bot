import os
import discord
import asyncio
import requests

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

    try:
        channel = client.get_channel(CHANNEL_ID)

        if channel:
            await channel.send("✅ Bot is now running 24/7 on Render! 🚀")
            print("✅ Startup message sent successfully!")
        else:
            print("❌ Could not find the channel. Check CHANNEL_ID.")
    except Exception as e:
        print(f"❌ Error sending startup message: {e}")

    # Start news loop
    client.loop.create_task(news_loop())

async def news_loop():
    """Fetch and send stock news every 10 minutes"""
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    while not client.is_closed():
        try:
            news = get_stock_news()
            if news and channel:
                for n in news:
                    await channel.send(f"📰 **{n['title']}**\n{n['url']}")
        except Exception as e:
            print(f"❌ Error in news loop: {e}")

        await asyncio.sleep(600)  # Wait 10 minutes before next check

def get_stock_news():
    """Dummy example news fetcher - replace with real API"""
    try:
        # Example API (replace with your news API or yfinance logic)
        response = requests.get("https://finnhub.io/api/v1/news?category=general&token=YOUR_API_KEY")
        if response.status_code == 200:
            return [{"title": x["headline"], "url": x["url"]} for x in response.json()[:3]]
        else:
            print("❌ Failed to fetch news.")
            return []
    except Exception as e:
        print(f"❌ Error fetching news: {e}")
        return []

client.run(TOKEN)
