import discord
import requests
import asyncio
import os
import yfinance as yf
import logging

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") 
BENZINGA_API_KEY = os.getenv("BENZINGA_API_KEY") 
CHANNEL_ID = int(os.getenv("CHANNEL_ID") )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True  # Enable reading message content for commands

class StockNewsBot(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sent_titles = set()
        self.channel = None
        self.news_task = None
        self.news_lock = asyncio.Lock()

    async def setup_hook(self):
        self.news_task = self.loop.create_task(self.news_loop())

    def get_latest_news(self):
        url = f"https://api.benzinga.com/api/v2/news?token={BENZINGA_API_KEY}&channels=stock&pagesize=30"
        headers = {"Accept": "application/json"}
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"⚠ Error fetching Benzinga news: {e}")
            return []

    def check_price_in_range(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            price = stock.info.get("regularMarketPrice")
            if price is None:
                hist = stock.history(period="1d")
                if not hist.empty:
                    price = hist["Close"][-1]
                else:
                    return False
            return 1 <= price <= 10
        except Exception as e:
            logger.warning(f"⚠ Error fetching price for {ticker}: {e}")
            return False

    async def news_loop(self):
        await self.wait_until_ready()
        self.channel = self.get_channel(CHANNEL_ID)
        if self.channel is None:
            logger.error(f"Channel ID {CHANNEL_ID} not found!")
            return
        while not self.is_closed():
            await self.fetch_and_send_news()
            await asyncio.sleep(120)  # 2 minutes interval

    async def fetch_and_send_news(self):
        async with self.news_lock:
            news_items = self.get_latest_news()
            for news in news_items:
                tickers_data = news.get("stocks", [])
                tickers = []
                for stock in tickers_data:
                    symbol = stock.get("symbol") if isinstance(stock, dict) else stock
                    if symbol:
                        tickers.append(symbol)
                title = news.get("title", "")
                url = news.get("url", "")
                for ticker in tickers:
                    if ticker not in self.sent_titles and self.check_price_in_range(ticker):
                        msg = f"**${ticker}**: {title}\n{url}"
                        try:
                            await self.channel.send(msg)
                        except Exception as e:
                            logger.warning(f"⚠ Failed to send message: {e}")
                        self.sent_titles.add(ticker)
                        await asyncio.sleep(1)
                        break

    async def on_ready(self):
        logger.info(f"✅ Logged in as {self.user}")

    async def on_message(self, message):
        # Ignore bots (including itself)
        if message.author.bot:
            return

        # Only respond in the configured channel
        if message.channel.id != CHANNEL_ID:
            return

        content = message.content.lower()

        if content == "!status":
            await message.channel.send("✅ Bot is online and running!")
        elif content == "!refresh":
            if self.news_lock.locked():
                await message.channel.send("⏳ News refresh is already in progress, please wait.")
            else:
                await message.channel.send("🔄 Fetching latest news now...")
                await self.fetch_and_send_news()
                await message.channel.send("✅ News refresh completed.")

if __name__ == "__main__":
    bot = StockNewsBot(intents=intents)
    bot.run(DISCORD_TOKEN)
