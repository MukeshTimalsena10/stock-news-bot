import discord
import requests
import asyncio
import time
import os
import yfinance as yf

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or "your_discord_token"
BENZINGA_API_KEY = os.getenv("BENZINGA_API_KEY") or "your_benzinga_api_key"
CHANNEL_ID = int(os.getenv("CHANNEL_ID") or 123456789012345678)

intents = discord.Intents.default()

class StockNewsBot(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sent_titles = set()

    async def setup_hook(self):
        self.loop.create_task(self.news_loop())

    def get_latest_news(self):
        url = f"https://api.benzinga.com/api/v2/news?token={BENZINGA_API_KEY}&channels=stock&pagesize=30"
        headers = {
            "Accept": "application/json"
        }
        try:
            r = requests.get(url, headers=headers, timeout=10)
            print(f"Benzinga status: {r.status_code}")
            print(f"Benzinga response text (first 300 chars):\n{r.text[:300]}")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"⚠ Error fetching Benzinga news: {e}")
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
            print(f"⚠ Error fetching price for {ticker}: {e}")
            return False

    async def news_loop(self):
        await self.wait_until_ready()
        channel = self.get_channel(CHANNEL_ID)

        while not self.is_closed():
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
                        await channel.send(msg)
                        self.sent_titles.add(ticker)
                        await asyncio.sleep(1)
                        break

            await asyncio.sleep(120)  # Wait 2 minutes before checking again

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")

bot = StockNewsBot(intents=intents)
bot.run(DISCORD_TOKEN)
