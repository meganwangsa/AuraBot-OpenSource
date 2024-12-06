import asyncio
import discord
from discord.ext import tasks
from discord import Interaction
import logging
from datetime import datetime, timezone
from discord.ext import commands
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import pytz
from config import GUILD_ID

# Load environment variables
load_dotenv()

class MoodLogging(commands.Cog):
    """Cog for logging user moods."""

    def __init__(self, aurabot):
        self.aurabot = aurabot

        # MongoDB setup
        mongo_url = os.getenv("MONGO_URL")
        if not mongo_url:
            raise ValueError("MongoDB connection string is not set in .env")
        
        try:
            self.cluster = MongoClient(mongo_url, serverSelectionTimeOutMS=5000)
            # Test connection
            self.cluster.server_info()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MongoDB: {e}")
        
        # set up database and collections
        self.cluster = MongoClient(mongo_url)
        self.db = self.cluster["AuraBotDB"]
        self.user_collection = self.db["user_profiles"]
        self.mood_collection = self.db["mood_logging"]

        #Start the reminder task loop
        self.send_reminders.start()

    async def cog_load(self):
        """Register commands when the cog is loaded."""
        guild = discord.Object(id=GUILD_ID)  # Ensure GUILD_ID is correct
        self.aurabot.tree.add_command(self.log_mood, guild=guild)
        self.aurabot.tree.add_command(self.view_moods, guild=guild)
        self.aurabot.tree.add_command(self.set_reminder, guild=guild)
        self.aurabot.tree.add_command(self.stop_reminder, guild=guild)
        logging.info("Commands registered: logmood, viewmoods, setmoodreminder, stopmoodreminder")

    @discord.app_commands.command(name="logmood", description="Log your mood for the day.")
    async def log_mood(self, interaction: discord.Interaction, mood: str):
        """Log a mood for the current day."""

        user_id = interaction.user.id

        # Fetch the user's timezone from the profile collection
        user_profile = self.user_collection.find_one({"_id": user_id})
        if not user_profile:
            await interaction.response.send_message(
                "You don't have a profile yet! Use `/createprofile` to set up your profile and timezone."
            )
            return

        # Get the user's timezone, defaulting to UTC if not set
        user_timezone = user_profile.get("timezone", "UTC")
        tz = pytz.timezone(user_timezone)

        # Get the current time in the user's timezone
        now_local = datetime.now(tz)

        # Log the mood with the local time
        self.mood_collection.update_one(
            {"_id": user_id},
            {"$push": {"moods": {"mood": mood, "timestamp": now_local.strftime('%Y-%m-%d %H:%M:%S')}}},
            upsert=True
        )
        await interaction.response.send_message(
            f"Your mood `{mood}` has been logged at {now_local.strftime('%Y-%m-%d %H:%M:%S')} ({user_timezone})."
    )


    @discord.app_commands.command(name="viewmoods", description="View your logged moods.")
    async def view_moods(self, interaction: discord.Interaction):
        """Handles /viewmoods command."""
        user_id = interaction.user.id

        # Check if the user has a profile
        user_profile = self.user_collection.find_one({"_id": user_id})
        if not user_profile:
            await interaction.response.send_message(
                "You don't have a profile yet! Use `/createprofile` to set up your profile and timezone."
            )
            return

        try:
            # Retrieve mood data
            user_data = self.mood_collection.find_one({"_id": user_id})
            if not user_data or "moods" not in user_data or not user_data["moods"]:
                await interaction.response.send_message("You haven't logged any moods yet.")
                return

            # Format and display logged moods
            mood_list = "\n".join(
                [
                    f"- {entry['mood']} (logged at {entry['timestamp']})"
                    for entry in user_data["moods"]
                ]
            )
            await interaction.response.send_message(f"Your logged moods:\n{mood_list}")
        except Exception as e:
            logging.error(f"Error retrieving moods: {e}")
            await interaction.response.send_message("Failed to retrieve your moods. Please try again later.")




    @discord.app_commands.command(name="setmoodreminder", description="Set a daily mood logging reminder (format: HH:MM in 24-hour).")
    async def set_reminder(self, interaction: discord.Interaction, time: str):
        """Set daily reminders to log moods."""
        
        user_id = interaction.user.id

        # Check if the user has a profile
        user_profile = self.user_collection.find_one({"_id": user_id})
        if not user_profile:
            await interaction.response.send_message(
                "You don't have a profile yet! Use `/createprofile` to set up your profile and timezone."
            )
            return
        try:
            # Validate and parse the time
            hour, minute = map(int, time.split(":"))
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError("Invalid time range")

            user_id = interaction.user.id

            # Check if the user exists in the mood_logging database
            user_data = self.mood_collection.find_one({"_id": user_id})
            if not user_data:
                # Create an entry for the user if it doesn't exist
                self.mood_collection.insert_one({"_id": user_id, "reminder_time": None, "moods": []})

            # Get the user's timezone (default to UTC if not set)
            user_profile = self.user_collection.find_one({"_id": user_id})
            user_timezone = user_profile.get("timezone", "UTC") if user_profile else "UTC"
            tz = pytz.timezone(user_timezone)


            # Update the reminder time in the mood_logging database
            self.mood_collection.update_one(
                {"_id": user_id},
                {"$set": {"reminder_time": time}},
                upsert=True
            )

            # Inform the user
            await interaction.response.send_message(
                f"Mood reminder set for **{time} ({user_timezone})** daily. I'll DM you at the specified time!"
            )
        except ValueError:
            await interaction.response.send_message("Invalid time format! Use HH:MM in 24-hour format.")
        except Exception as e:
            logging.error(f"Error setting mood reminder: {e}")
            await interaction.response.send_message("Failed to set a reminder. Please try again later.")



    @discord.app_commands.command(name="stopmoodreminder", description="Stop receiving daily reminders.")
    async def stop_reminder(self, interaction: discord.Interaction):
        """Stop daily reminders."""
        user_id = interaction.user.id

        # Check if the user has a profile
        user_profile = self.user_collection.find_one({"_id": user_id})
        if not user_profile:
            await interaction.response.send_message(
                "You don't have a profile yet! Use `/createprofile` to set up your profile and timezone."
            )
            return
        # Check if the user exists in the mood_logging database
        user_data = self.mood_collection.find_one({"_id": user_id})
        if not user_data:
            # Create an entry for the user if it doesn't exist
            self.mood_collection.insert_one({"_id": user_id, "reminder_time": None, "moods": []})
        try:
            self.mood_collection.update_one(
                {"_id": user_id},
                {"$set": {"reminder_time": None}},
                upsert=True
            )
            # Inform the user
            await interaction.response.send_message(
                f"Mood reminder disabled."
            )
            
        except Exception as e:
            logging.error(f"Error stopping reminder: {e}")
            await interaction.response.send_message("Failed to stop reminders. Please try again later.")

    @tasks.loop(minutes=1)
    async def send_reminders(self):
        """Send reminders for mood logging at the specified times."""
        await self.aurabot.wait_until_ready()  # Ensure the bot is ready
        while not self.aurabot.is_closed():
            try:
                now_utc = datetime.now(pytz.utc)  # Current time in UTC

                # Find all users with a mood reminder set
                users_with_reminders = self.mood_collection.find({"reminder_time": {"$exists": True}})
                for user in users_with_reminders:
                    user_id = user["_id"]

                    # Get the user's timezone from the profile
                    user_profile = self.user_collection.find_one({"_id": user_id})
                    user_timezone = user_profile.get("timezone")
                    tz = pytz.timezone(user_timezone)

                    # Convert the current time to the user's timezone
                    now_local = now_utc.astimezone(tz).strftime("%H:%M")
        
                    # Compare the user's local time with their reminder time
                    if user.get("reminder_time") == now_local:
                        user_obj = await self.aurabot.fetch_user(user_id)
                        try:
                            # Send the DM
                            await user_obj.send("⏰ Don't forget to log your mood for today!")
                        except discord.Forbidden:
                            logging.warning(f"Failed to send reminder to user {user_id} (DMs may be disabled).")

                await asyncio.sleep(60)  # Wait before checking again
            except Exception as e:
                logging.error(f"Error in send_reminders task: {e}")

    @send_reminders.before_loop
    async def before_send_reminders(self):
        """Wait until the bot is ready before starting reminders."""
        await self.aurabot.wait_until_ready()


# Required setup function
async def setup(aurabot):
    await aurabot.add_cog(MoodLogging(aurabot))
    print("MoodLogging cog successfully added!")

