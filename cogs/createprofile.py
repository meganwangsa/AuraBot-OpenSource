import discord
from discord.ext import commands
from pymongo import MongoClient
from dotenv import load_dotenv
import pytz
import os
from config import GUILD_ID

# Load environment variables
load_dotenv()

class TimezoneDropdown(discord.ui.Select):
    def __init__(self, user_id, profile_collection):
        self.user_id = user_id
        self.profile_collection = profile_collection

        # Commonly used timezones (you can expand this list)
        timezones = [
            "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
            "US/Alaska", "US/Hawaii"
        ]

        options = [
            discord.SelectOption(label=tz, description=f"Timezone: {tz}")
            for tz in timezones
        ]
        super().__init__(placeholder="Select your timezone...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_timezone = self.values[0]
        self.profile_collection.update_one(
            {"_id": self.user_id},
            {"$set": {"timezone": selected_timezone}},
            upsert=True
        )
        await interaction.response.send_message(
            f"Your timezone has been set to **{selected_timezone}**."
        )

class TimezoneDropdownView(discord.ui.View):
    def __init__(self, user_id, profile_collection):
        super().__init__()
        self.add_item(TimezoneDropdown(user_id, profile_collection))

class CreateProfile(commands.Cog):
    """Cog for creating user profiles with timezone selection."""

    def __init__(self, aurabot):
        self.aurabot = aurabot

        # MongoDB setup
        mongo_url = os.getenv("MONGO_URL")
        if not mongo_url:
            raise ValueError("MongoDB connection string is not set in .env")

        self.cluster = MongoClient(mongo_url)
        self.db = self.cluster["AuraBotDB"]
        self.profile_collection = self.db["user_profiles"]

    async def cog_load(self):
        """Register commands when the cog is loaded."""
        guild = discord.Object(id=GUILD_ID)
        self.aurabot.tree.add_command(self.create_profile, guild=guild)

    @discord.app_commands.command(name="createprofile", description="Create your profile with your Discord username and timezone.")
    async def create_profile(self, interaction: discord.Interaction):
        """Handles the /createprofile command."""
        user_id = interaction.user.id
        username = interaction.user.name  # Use Discord username

        # Check if the user already has a profile
        existing_profile = self.profile_collection.find_one({"_id": user_id})

        if existing_profile:
            existing_username = existing_profile.get("username", "No username set.")
            existing_timezone = existing_profile.get("timezone", "No timezone set.")
            await interaction.response.send_message(
                f"You already have a profile:\n- **Username**: {existing_username}\n- **Timezone**: {existing_timezone}"
            )
        else:
            # Create a new profile with the username
            self.profile_collection.insert_one({"_id": user_id, "username": username})
            await interaction.response.send_message(
                f"Your profile has been created with the username: **{username}**.\nNow, select your timezone:"
            )

            # Show the timezone dropdown menu
            view = TimezoneDropdownView(user_id, self.profile_collection)
            await interaction.followup.send(view=view)

# Required setup function
async def setup(aurabot):
    await aurabot.add_cog(CreateProfile(aurabot))
