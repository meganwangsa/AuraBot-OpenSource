import discord
from discord.ext import commands
from config import GUILD_ID  # Import your guild ID

class MoodLoggingMenu(commands.Cog):
    """Cog for displaying the mood logging menu."""

    def __init__(self, aurabot):
        self.aurabot = aurabot

    @discord.app_commands.command(name="moodlogging", description="Displays mood logging options.")
    async def moodlogging_menu(self, interaction: discord.Interaction):
        """Handles /moodloggingmenu command to display options."""
        embed = discord.Embed(
            title="Mood Logging Menu",
            description="Here are the commands you can use for mood logging:",
            color=discord.Color.yellow()
        )
        embed.add_field(name="/logmood", value="Log your mood for the day.", inline=False)
        embed.add_field(name="/viewmoods", value="View your logged moods.", inline=False)
        embed.add_field(name="/setmoodreminder", value="Set a daily mood logging reminder.", inline=False)
        embed.add_field(name="/stopmoodreminder", value="Stop receiving daily reminders.", inline=False)
        await interaction.response.send_message(embed=embed)

    async def cog_load(self):
        """Register commands when the cog is loaded."""
        guild = discord.Object(id=GUILD_ID)  # Ensure the guild ID is correct
        self.aurabot.tree.add_command(self.moodlogging_menu, guild=guild)

# Required setup function
async def setup(aurabot):
    await aurabot.add_cog(MoodLoggingMenu(aurabot))
