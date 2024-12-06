import discord
from discord.ext import commands
from config import GUILD_ID  # Import your guild ID

class GoalTrackingMenu(commands.Cog):
    """Cog for displaying the goal tracking menu."""

    def __init__(self, aurabot):
        self.aurabot = aurabot

    @discord.app_commands.command(name="goaltracking", description="Displays goal tracking options.")
    async def goaltracking_menu(self, interaction: discord.Interaction):
        """Handles /goaltracking command to display options."""
        embed = discord.Embed(
            title="Goal Tracking Menu",
            description="Here are the commands you can use for goal tracking:",
            color=discord.Color.purple()
        )
        embed.add_field(name="/creategoal", value="Create a new goal. Input format: goal: 'Your Goal', deadline: 'YYYY-MM-DD'.", inline=False)
        embed.add_field(name="/updategoal", value="Update progress on your goal. Input format: goal: 'Your Goal', progress: percentage.", inline=False)
        embed.add_field(name="/viewgoal", value="View your current goals and progress. No input required.", inline=False)
        embed.add_field(name="/deletegoal", value="Delete a specific goal. Input format: goal: 'Your Goal'.", inline=False)
        embed.add_field(name="/cleargoal", value="Clear all completed goals for the user.", inline=False)
        embed.add_field(name="/viewPoints", value="Check current points.", inline=False)


        await interaction.response.send_message(embed=embed)

    async def cog_load(self):
        """Register commands when the cog is loaded."""
        guild = discord.Object(id=GUILD_ID)  # Ensure the guild ID is correct
        self.aurabot.tree.add_command(self.goaltracking_menu, guild=guild)

# Required setup function
async def setup(aurabot):
    await aurabot.add_cog(GoalTrackingMenu(aurabot))
