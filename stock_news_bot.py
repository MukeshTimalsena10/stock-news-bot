import os
import discord
import asyncio
from datetime import datetime

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("✅ Bot is now running 24/7 on Render! 🚀\nStarting test news feed...")
        print("✅ Startup message sent successfully!")
    else:
        print("❌ Could not find the channel. Check CHANNEL_ID.")

    # Start test news loop
    client.loop.create_task(news_loop())

async def news_loop():
    """Send fake stock news every 1 minute for testing"""
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    while not client.is_closed():
        try:
            if channel:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await channel.send(f"📰 **TEST NEWS** - Stock XYZ is up 5%! ({now})")
                print(f"✅ Sent test news at {now}")
        except Exception as e:
            print(f"❌ Error in news loop: {e}")

        await asyncio.sleep(60)  # every 1 minute for testing

client.run(TOKEN)
