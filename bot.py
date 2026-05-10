import json
import os
import sys

import nextcord
from dotenv import load_dotenv
from nextcord.ext import commands

load_dotenv(override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("ERROR: BOT_TOKEN is not set. Add it to your .env file.")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)
bot.config = config


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


bot.load_extension("cogs.detector")
bot.run(BOT_TOKEN)
