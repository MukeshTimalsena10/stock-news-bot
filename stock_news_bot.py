import discord
import requests
import asyncio
import os
import yfinance as yf
import logging
import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Config - replace or set env vars
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or "your_discord_token_here"
BENZINGA_API_KEY = os.getenv("BENZINGA_API_KEY") or "your_benzinga_api_key_here"
CHANNEL_ID = int(os.getenv("CHANNEL_ID") or 123456789012345678)  # Discord channel ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True

class StockNewsBot(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sent_titles = set()
        self.channel = None
        self.news_lock = asyncio.Lock()
        self.analyzer = SentimentIntensityAnalyzer()
        self.latest_gainers = set()
        self.gainer_timestamps = {}  # ticker -> datetime last detected
        self.news_task = None
        self.gainer_task = None

    async def setup_hook(self):
        self.news_task = self.loop.create_task(self.news_loop())
        self.gainer_task = self.loop.create_task(self.gainer_alert_loop())

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
            return 0.1 <= price <= 10
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

    def analyze_sentiment(self, text):
        scores = self.analyzer.polarity_scores(text)
        if scores["compound"] >= 0.05:
            return "✅ Positive"
        elif scores["compound"] <= -0.05:
            return "❌ Negative"
        else:
            return "➖ Neutral"

    def has_increased_10_percent_intraday(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d", interval="5m")
            if hist.empty or len(hist) < 2:
                return False
            open_price = hist['Open'][0]
            latest_price = hist['Close'][-1]
            if open_price == 0:
                return False
            percent_change = ((latest_price - open_price) / open_price) * 100
            return percent_change >= 10
        except Exception as e:
            logger.warning(f"Error checking intraday increase for {ticker}: {e}")
            return False

    async def news_loop(self):
        await self.wait_until_ready()
        self.channel = self.get_channel(CHANNEL_ID)
        if self.channel is None:
            logger.error(f"Channel ID {CHANNEL_ID} not found!")
            return
        while not self.is_closed():
            await self.fetch_and_send_news()
            await asyncio.sleep(120)  # every 2 minutes

    async def gainer_alert_loop(self):
        await self.wait_until_ready()
        while not self.is_closed():
            await asyncio.sleep(600)  # every 10 minutes
            if self.latest_gainers and self.channel:
                gainers_msg = "🚀 **Gainer Alert!** The following stocks moved up 10% or more in the last 30 minutes:\n"
                gainers_msg += ", ".join(f"${t}" for t in sorted(self.latest_gainers))
                try:
                    await self.channel.send(gainers_msg)
                except Exception as e:
                    logger.warning(f"⚠ Failed to send gainer alert: {e}")

    async def fetch_and_send_news(self):
        async with self.news_lock:
            news_items = self.get_latest_news()
            now = datetime.datetime.utcnow()
            gainer_tickers = set()

            for news in news_items:
                tickers_data = news.get("stocks", [])
                tickers = []
                for stock in tickers_data:
                    if isinstance(stock, dict) and stock.get("symbol"):
                        tickers.append(stock["symbol"].upper())
                    elif isinstance(stock, str):
                        tickers.append(stock.upper())

                title = news.get("title", "")
                url = news.get("url", "")
                sentiment = self.analyze_sentiment(title)

                for ticker in tickers:
                    if ticker not in self.sent_titles and self.check_price_in_range(ticker):
                        msg = f"{sentiment} **${ticker}**: {title}\n{url}"
                        try:
                            await self.channel.send(msg)
                        except Exception as e:
                            logger.warning(f"⚠ Failed to send message: {e}")
                        self.sent_titles.add(ticker)
                        await asyncio.sleep(1)
                        break  # Send one message per news only

                # Update gainers timestamps for intraday +10%
                for ticker in tickers:
                    if self.has_increased_10_percent_intraday(ticker):
                        self.gainer_timestamps[ticker] = now

            # Clean old gainers (older than 30 min)
            threshold = now - datetime.timedelta(minutes=30)
            self.gainer_timestamps = {t: ts for t, ts in self.gainer_timestamps.items() if ts > threshold}
            self.latest_gainers = set(self.gainer_timestamps.keys())

    async def on_ready(self):
        logger.info(f"✅ Logged in as {self.user}")

    async def on_message(self, message):
        if message.author.bot or message.channel.id != CHANNEL_ID:
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
            news_list = [n for n in self.get_latest_news() if ticker in [s['symbol'].upper() if isinstance(s, dict) else s.upper() for s in n.get("stocks", [])]]
            if news_list:
                msg = f"📰 Latest news for **${ticker}**:\n"
                for item in news_list[:5]:
                    sentiment = self.analyze_sentiment(item.get("title", ""))
                    msg += f"- {sentiment} [{item.get('title')}]({item.get('url')})\n"
                await message.channel.send(msg)
            else:
                await message.channel.send(f"⚠ No recent news found for {ticker}.")

        elif content[0].lower() == "!latestgainers":
            if self.latest_gainers:
                await message.channel.send(f"🚀 Latest gainers:\n" + ", ".join(f"${t}" for t in sorted(self.latest_gainers)))
            else:
                await message.channel.send("No gainers found in the last 30 minutes.")

if __name__ == "__main__":
    bot = StockNewsBot(intents=intents)
    bot.run(DISCORD_TOKEN)
