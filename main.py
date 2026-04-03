import discord
from discord.ext import commands
import os
from database import Database
import asyncio


# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix=commands.when_mentioned_or("p!"),intents=intents,help_command=None)

# Initialize PostgreSQL Database
bot.db = Database(dsn="postgresql://postgres:pokedia2389@localhost:5432/pokedia")

# Function to load extensions
async def load_extensions():
    for filename in os.listdir("./commands"):
        if filename.endswith(".py"):
            await bot.load_extension(f"commands.{filename[:-3]}")


# Event for when bot is ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

# Main function to run the bot
async def main():
    async with bot:
        await bot.db.connect()  # ✅ Ensure database connection is established
        await load_extensions()
        await bot.start("MTMzMDA3NzU0MTA5MTc3MDQwOA.GOR0qL.CgTe2YiyLBKX2DjSvF957OIhtqt_9b6O2APu98")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot is shutting down gracefully.")
