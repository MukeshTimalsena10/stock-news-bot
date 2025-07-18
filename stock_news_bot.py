import discord
import requests
import asyncio
import os
import yfinance as yf
import logging

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or "your_discord_token"
BENZINGA_API_KEY = os.getenv("BENZINGA_API_KEY") or "your_benzinga_api_key"
CHANNEL_ID = int(os.getenv("CHANNEL_ID") or 123456789012345678)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True  # Required for reading commands

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

    def get_news_for_ticker(self, ticker):
        """Fetch 5 latest news headlines for a specific ticker"""
        if not ticker:
            return []
        url = f"https://api.benzinga.com/api/v2/news?token={BENZINGA_API_KEY}&tickers={ticker}&pagesize=5"
        headers = {"Accept": "application/json"}
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"⚠ Error fetching news for {ticker}: {e}")
            return []

    def check_price_in_range(self, ticker):
        if not ticker:
            return False
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

    def get_current_price(self, ticker):
        if not ticker:
            return None
        try:
            stock = yf.Ticker(ticker)
            price = stock.info.get("regularMarketPrice")
            if price is None:
                hist = stock.history(period="1d")
                if not hist.empty:
                    price = hist["Close"][-1]
            return price
        except Exception as e:
            logger.warning(f"⚠ Error fetching price for {ticker}: {e}")
            return None

    async def news_loop(self):
        await self.wait_until_ready()
        self.channel = self.get_channel(CHANNEL_ID)
        if self.channel is None:
            logger.error(f"Channel ID {CHANNEL_ID} not found!")
            return
        while not self.is_closed():
            await self.fetch_and_send_news()
            await asyncio.sleep(120)  # every 2 minutes

    async def fetch_and_send_news(self):
        async with self.news_lock:
            news_items = self.get_latest_news()
            for news in news_items:
                tickers_data = news.get("stocks", [])

                # ✅ Skip invalid/empty tickers (fix for NoneType issue)
                tickers = [
                    (stock.get("symbol") if isinstance(stock, dict) else stock).upper()
                    for stock in tickers_data
                    if (isinstance(stock, dict) and stock.get("symbol")) or (isinstance(stock, str) and stock)
                ]

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
        if message.author.bot:
            return
        if message.channel.id != CHANNEL_ID:
            return

        content = message.content.strip().split()

        if content[0].lower() == "!status":
            await message.channel.send("✅ Bot is online and running!")

        elif content[0].lower() == "!refresh":
            if self.news_lock.locked():
                await message.channel.send("⏳ News refresh already in progress.")
            else:
                await message.channel.send("🔄 Fetching latest news now...")
                await self.fetch_and_send_news()
                await message.channel.send("✅ News refresh completed.")

        elif content[0].lower() == "!price" and len(content) > 1:
            ticker = content[1].upper()
            price = self.get_current_price(ticker)
            if price:
                await message.channel.send(f"💲 **${ticker}** is currently **${price:.2f}**")
            else:
                await message.channel.send(f"⚠ Could not fetch price for {ticker}.")

        elif content[0].lower() == "!news" and len(content) > 1:
            ticker = content[1].upper()
            news_list = self.get_news_for_ticker(ticker)
            if news_list:
                msg = f"📰 Latest news for **${ticker}**:\n"
                for item in news_list[:5]:
                    msg += f"- [{item.get('title')}]({item.get('url')})\n"
                await message.channel.send(msg)
            else:
                await message.channel.send(f"⚠ No recent news found for {ticker}.")

if __name__ == "__main__":
    bot = StockNewsBot(intents=intents)
    bot.run(DISCORD_TOKEN)
