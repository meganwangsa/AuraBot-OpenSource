import discord
from discord.ext import commands
from config import GUILD_ID  # Import GUILD_ID

class Menu(commands.Cog):
    def __init__(self, aurabot):
        self.aurabot = aurabot

    @discord.app_commands.command(name="menu", description="Displays the list of available commands")
    async def menu(self, interaction: discord.Interaction):
        """Respond with a menu of commands."""
        embed = discord.Embed(
            title="Menu",
            description="Here are the commands currently available:",
            color=discord.Color.blue()
        )
        embed.add_field(name="/menu", value="Displays this menu of commands.", inline=False)
        embed.add_field(name="/createprofile", value="Creates a user profile.", inline=False)
        embed.add_field(name="/viewprofile", value="Displays a user's profile.", inline=False)
        embed.add_field(name="/habittracking", value="Displays list of habit tracking commands", inline=False)
        embed.add_field(name="/moodlogging", value="Displays list of mood logging commands", inline=False)
        embed.add_field(name="/goaltracking", value="Displays list of goal tracking commands.", inline=False)
        await interaction.response.send_message(embed=embed)

    async def cog_load(self):
        """Register the menu command when the cog is loaded."""
        guild = discord.Object(id=GUILD_ID)
        self.aurabot.tree.add_command(self.menu, guild=guild)

# Required setup function to add the cog
async def setup(aurabot):
    await aurabot.add_cog(Menu(aurabot))
