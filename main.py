import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from config import GUILD_ID  # Import GUILD_ID

# Get AuraBot Token
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class AuraBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Allows AuraBot to read message content

        # Initialize the bot with a command prefix and intents
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Dynamically load all cogs from the 'cogs' folder
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                except Exception as e:
                    print(f"Failed to load cog {filename[:-3]}: {e}")

        # Sync slash commands
        try:
            guild = discord.Object(id=GUILD_ID)  # Use global GUILD_ID
            synced = await self.tree.sync(guild=guild)
            print(f'Synced {len(synced)} commands to guild {GUILD_ID}')
        except Exception as e:
            print(f'Error syncing commands: {e}')

    async def on_ready(self):
        print(f'{self.user} is logged in and active! Wassup! Wassup! Wassup!')

# Initialize and run the bot
if __name__ == '__main__':
    aurabot = AuraBot()
    aurabot.run(TOKEN)
