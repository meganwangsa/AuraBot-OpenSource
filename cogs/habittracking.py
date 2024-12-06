import asyncio
from datetime import datetime
import discord
from discord.ui import View, Select
from discord.ext import commands
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from config import GUILD_ID

# Load environment variables
load_dotenv()

class HabitTracking(commands.Cog):
    """Cog for tracking and logging user habits with optional reminders."""

    def __init__(self, aurabot):
        self.aurabot = aurabot

        # MongoDB setup
        mongo_url = os.getenv("MONGO_URL")
        if not mongo_url:
            raise ValueError("MongoDB connection string is not set in .env")

        self.cluster = MongoClient(mongo_url)
        self.db = self.cluster["AuraBotDB"]
        self.collection = self.db["habit_tracking"]

        print("Connected to MongoDB for habit tracking!")

        # Start the reminder task
        self.reminder_task = self.aurabot.loop.create_task(self.send_reminders())

    async def cog_unload(self):
        """Stop the reminder task when the cog is unloaded."""
        self.reminder_task.cancel()

    async def cog_load(self):
        """Register commands when the cog is loaded."""
        guild = discord.Object(id=GUILD_ID)
        print(f"Registering commands in HabitTracking for guild {GUILD_ID}...")
        self.aurabot.tree.add_command(self.add_habit, guild=guild)
        self.aurabot.tree.add_command(self.log_habit, guild=guild)
        self.aurabot.tree.add_command(self.view_habits, guild=guild)
        self.aurabot.tree.add_command(self.clear_habit, guild=guild)

    async def send_reminders(self):
        """Background task to send reminders for unlogged habits with reminders."""
        await self.aurabot.wait_until_ready()
        while not self.aurabot.is_closed():
            now = datetime.utcnow()
            users = self.collection.find({"habits.reminder_time": {"$exists": True}})

            for user in users:
                for habit in user["habits"]:
                    reminder_time = datetime.strptime(habit["reminder_time"], "%H:%M").time()
                    if now.time() >= reminder_time and now.strftime("%Y-%m-%d") not in habit["logs"]:
                        user_obj = await self.aurabot.fetch_user(user["_id"])
                        try:
                            await user_obj.send(f"Reminder: Log your habit `{habit['habit']}` for today!")
                        except discord.Forbidden:
                            print(f"Failed to send reminder to user {user['_id']} (DMs disabled).")
            await asyncio.sleep(60)  # Check every minute

    @discord.app_commands.command(name="addhabit", description="Add a habit to track.")
    async def add_habit(self, interaction: discord.Interaction, habit: str, reminder_time: str = None):
        """
        Add a new habit to track with an optional daily reminder time.
        If `reminder_time` is not provided, no reminders will be set for this habit.
        """
        print(f"add_habit triggered with habit={habit}, reminder_time={reminder_time}")

        # Validate reminder_time format if provided
        if reminder_time:
            try:
                datetime.strptime(reminder_time, "%H:%M")
            except ValueError:
                await interaction.response.send_message(
                    "Invalid reminder time format. Use HH:MM (24-hour clock).", ephemeral=True
                )
                return

        user_id = interaction.user.id

        # Create the habit data
        habit_data = {
            "habit": habit,
            "logs": []
        }
        if reminder_time:
            habit_data["reminder_time"] = reminder_time

        try:
            # Add the habit to the database
            self.collection.update_one({"_id": user_id}, {"$addToSet": {"habits": habit_data}}, upsert=True)
            if reminder_time:
                await interaction.response.send_message(f"Habit `{habit}` added with reminder at {reminder_time}.")
            else:
                await interaction.response.send_message(f"Habit `{habit}` added without a reminder.")
        except Exception as e:
            print(f"Database error: {e}")
            await interaction.response.send_message("An error occurred while saving your habit. Please try again.")

    @discord.app_commands.command(name="loghabit", description="Log your habit for today.")
    async def log_habit(self, interaction: discord.Interaction):
        """Log a habit for the current day using a dropdown menu."""
        print("log_habit triggered")

        user_id = interaction.user.id
        user_data = self.collection.find_one({"_id": user_id})

        if not user_data or "habits" not in user_data or len(user_data["habits"]) == 0:
            await interaction.response.send_message("You don't have any tracked habits.", ephemeral=True)
            return

        # Extract habits for dropdown
        habit_options = [
            discord.SelectOption(label=habit["habit"], description="Click to log this habit")
            for habit in user_data["habits"]
        ]

        # Define the dropdown menu
        class HabitSelectView(View):
            def __init__(self, collection, user_data, user_id):
                super().__init__()
                self.collection = collection
                self.user_data = user_data
                self.user_id = user_id
                self.select = Select(
                    placeholder="Select a habit to log...",
                    options=habit_options,
                    custom_id="habit_select"
                )
                self.select.callback = self.select_callback  # Set callback for the select
                self.add_item(self.select)

            async def select_callback(self, select_interaction: discord.Interaction):
                selected_habit = self.select.values[0]  # Get the selected habit
                today = datetime.utcnow().strftime("%Y-%m-%d")

                # Update the database
                for habit in self.user_data["habits"]:
                    if habit["habit"] == selected_habit:
                        if today in habit.get("logs", []):
                            await select_interaction.response.send_message(
                                f"Habit `{selected_habit}` already logged today.", ephemeral=True
                            )
                            return
                        habit.setdefault("logs", []).append(today)
                        self.collection.update_one(
                            {"_id": self.user_id}, {"$set": {"habits": self.user_data["habits"]}}
                        )
                        await select_interaction.response.send_message(
                            f"Habit `{selected_habit}` logged for today.", ephemeral=True
                        )
                        return

                # If the habit isn't found (shouldn't happen)
                await select_interaction.response.send_message(
                    f"An error occurred while logging the habit `{selected_habit}`.", ephemeral=True
                )

        # Show the dropdown menu to the user
        view = HabitSelectView(self.collection, user_data, user_id)
        await interaction.response.send_message("Select a habit to log:", view=view, ephemeral=True)

    @discord.app_commands.command(name="viewhabits", description="View your tracked habits.")
    async def view_habits(self, interaction: discord.Interaction):
        """View the list of habits and their log status."""
        print("view_habits triggered")

        user_id = interaction.user.id
        user_data = self.collection.find_one({"_id": user_id})

        if not user_data or "habits" not in user_data:
            await interaction.response.send_message("You don't have any tracked habits.")
            return

        embed = discord.Embed(title="Your Habits", color=discord.Color.green())
        for habit in user_data["habits"]:
            logs = len(habit["logs"])
            reminder_time = habit.get("reminder_time", "No reminder")  # Use .get() to avoid KeyError
            embed.add_field(
                name=habit["habit"],
                value=f"Reminder: {reminder_time} | Days Logged: {logs}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="clearhabit", description="Clear all your tracked habits.")
    async def clear_habit(self, interaction: discord.Interaction):
        """Clear all habits for the user who invoked the command."""
        user_id = interaction.user.id

        try:
            result = self.collection.update_one({"_id": user_id}, {"$set": {"habits": []}})
            if result.matched_count > 0:
                await interaction.response.send_message("All your tracked habits have been cleared.")
            else:
                await interaction.response.send_message("You don't have any tracked habits to clear.")
        except Exception as e:
            print(f"Error clearing habits for user {user_id}: {e}")
            await interaction.response.send_message("An error occurred while clearing your habits.")

# Required setup function
async def setup(aurabot):
    await aurabot.add_cog(HabitTracking(aurabot))
    print("HabitTracking cog successfully added!")
