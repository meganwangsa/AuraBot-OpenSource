import asyncio
from datetime import datetime, timedelta
import discord
from discord.ui import View, Select
from discord.ext import commands
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from config import GUILD_ID

# Load environment variables
load_dotenv()

class GoalTracking(commands.Cog):
    """Cog for tracking and logging user goals with optional deadlines and progress updates."""

    def __init__(self, aurabot):
        self.aurabot = aurabot

        # MongoDB setup
        mongo_url = os.getenv("MONGO_URL")
        if not mongo_url:
            raise ValueError("MongoDB connection string is not set in .env")

        self.cluster = MongoClient(mongo_url)
        self.db = self.cluster["AuraBotDB"]
        self.collection = self.db["goal_tracking"]

        print("Connected to MongoDB for goal tracking!")

        # Start the reminder task
        self.reminder_task = self.aurabot.loop.create_task(self.send_goal_reminders())

    async def cog_unload(self):
        """Stop the reminder task when the cog is unloaded."""
        self.reminder_task.cancel()

    async def cog_load(self):
        """Register commands when the cog is loaded."""
        guild = discord.Object(id=GUILD_ID)
        print(f"Registering commands in GoalTracking for guild {GUILD_ID}...")
        self.aurabot.tree.add_command(self.create_goal, guild=guild)
        self.aurabot.tree.add_command(self.update_goal, guild=guild)
        self.aurabot.tree.add_command(self.view_goal, guild=guild)
        self.aurabot.tree.add_command(self.clear_goal, guild=guild)
        self.aurabot.tree.add_command(self.delete_goal, guild=guild)
        self.aurabot.tree.add_command(self.view_points, guild=guild)


    async def send_goal_reminders(self):
        """Background task to send reminders for goals with upcoming deadlines and manage points."""
        await self.aurabot.wait_until_ready()
        while not self.aurabot.is_closed():
            now = datetime.utcnow()
            users = self.collection.find()

            for user in users:
                updated = False  # Track if the user's data was updated
                for goal in user["goals"]:
                    deadline = goal.get("deadline")
                    last_update = goal.get("last_update")

                    # Check for upcoming deadlines
                    if deadline:
                        deadline_date = datetime.strptime(deadline, "%Y-%m-%d")
                        if now.date() >= (deadline_date - timedelta(days=1)).date() and not goal.get("reminded", False):
                            user_obj = await self.aurabot.fetch_user(user["_id"])
                            try:
                                await user_obj.send(
                                    f"Reminder: Your goal `{goal['goal']}` has a deadline on {goal['deadline']}!"
                                )
                                goal["reminded"] = True
                                updated = True
                            except discord.Forbidden:
                                print(f"Failed to send reminder to user {user['_id']} (DMs disabled).")

                    # Handle point deduction for no progress
                    if last_update:
                        last_update_date = datetime.strptime(last_update, "%Y-%m-%d").date()
                        if (now.date() - last_update_date).days >= 1:
                            # Deduct points for inactivity
                            user["points"] = user.get("points", 0) - 1
                            if user["points"] < 0:
                                user["points"] = 0  # Ensure points don't go negative
                            updated = True

                # Save changes to the database
                if updated:
                    self.collection.update_one({"_id": user["_id"]}, {"$set": user})
            await asyncio.sleep(3600)  # Check every hour

    @discord.app_commands.command(name="creategoal", description="Create a goal with an optional deadline.")
    async def create_goal(self, interaction: discord.Interaction, goal: str, deadline: str = None):
        """
        Create a new goal to track with an optional deadline.
        If `deadline` is not provided, the goal will not have a deadline.
        """
        print(f"create_goal triggered with goal={goal}, deadline={deadline}")

        # Validate deadline format if provided
        if deadline:
            try:
                datetime.strptime(deadline, "%Y-%m-%d")
            except ValueError:
                await interaction.response.send_message(
                    "Invalid deadline format. Use YYYY-MM-DD.", ephemeral=True
                )
                return

        user_id = interaction.user.id

        # Create the goal data
        goal_data = {
            "goal": goal,
            "progress": [],
            "completed": False
        }
        if deadline:
            goal_data["deadline"] = deadline
            goal_data["reminded"] = False  # Track if the reminder was sent

        try:
            # Add the goal to the database
            self.collection.update_one({"_id": user_id}, {"$addToSet": {"goals": goal_data}}, upsert=True)
            if deadline:
                await interaction.response.send_message(f"Goal `{goal}` added with a deadline on {deadline}.")
            else:
                await interaction.response.send_message(f"Goal `{goal}` added without a deadline.")
        except Exception as e:
            print(f"Database error: {e}")
            await interaction.response.send_message("An error occurred while saving your goal. Please try again.")

    @discord.app_commands.command(name="updategoal", description="Update progress for a goal.")
    async def update_goal(self, interaction: discord.Interaction):
        """Update progress for a goal using a dropdown menu."""
        print("update_goal triggered")

        user_id = interaction.user.id
        user_data = self.collection.find_one({"_id": user_id})

        if not user_data or "goals" not in user_data or len(user_data["goals"]) == 0:
            await interaction.response.send_message("You don't have any tracked goals.", ephemeral=True)
            return

        # Extract goals for dropdown
        goal_options = [
            discord.SelectOption(label=goal["goal"], description="Click to log progress for this goal")
            for goal in user_data["goals"] if not goal.get("completed", False)
        ]

        # Define the dropdown menu
        class GoalSelectView(View):
            def __init__(self, collection, user_data, user_id):
                super().__init__()
                self.collection = collection
                self.user_data = user_data
                self.user_id = user_id
                self.select = Select(
                    placeholder="Select a goal to log progress...",
                    options=goal_options,
                    custom_id="goal_select"
                )
                self.select.callback = self.select_callback  # Set callback for the select
                self.add_item(self.select)

            async def select_callback(self, select_interaction: discord.Interaction):
                selected_goal = self.select.values[0]  # Get the selected goal

                # Update the database
                for goal in self.user_data["goals"]:
                    if goal["goal"] == selected_goal:
                        today = datetime.utcnow().strftime("%Y-%m-%d")
                        if today in goal.get("progress", []):
                            await select_interaction.response.send_message(
                                f"Progress for goal `{selected_goal}` already logged today.", ephemeral=True
                            )
                            return
                        goal.setdefault("progress", []).append(today)
                        goal["last_update"] = today

                        # Award points for progress
                        self.user_data["points"] = self.user_data.get("points", 0) + 5

                        self.collection.update_one(
                            {"_id": self.user_id}, {"$set": {"goals": self.user_data["goals"], "points": self.user_data["points"]}}
                        )
                        await select_interaction.response.send_message(
                            f"Progress for goal `{selected_goal}` logged for today. You earned 5 points! 🎉\n"
                            f"Your total points: {self.user_data['points']}", ephemeral=True
                        )
                        return

                # If the goal isn't found (shouldn't happen)
                await select_interaction.response.send_message(
                    f"An error occurred while logging progress for the goal `{selected_goal}`.", ephemeral=True
                )

        # Show the dropdown menu to the user
        view = GoalSelectView(self.collection, user_data, user_id)
        await interaction.response.send_message("Select a goal to log progress:", view=view, ephemeral=True)

    @discord.app_commands.command(name="viewpoints", description="View your current points.")
    async def view_points(self, interaction: discord.Interaction):
        """Display the user's current points."""
        user_id = interaction.user.id
        user_data = self.collection.find_one({"_id": user_id})

        points = user_data.get("points", 0) if user_data else 0
        await interaction.response.send_message(f"You currently have {points} points. Keep up the great work! 🌟")

    @discord.app_commands.command(name="viewgoal", description="View your tracked goals.")
    async def view_goal(self, interaction: discord.Interaction):
        """View the list of goals and their progress."""
        print("view_goal triggered")

        user_id = interaction.user.id
        user_data = self.collection.find_one({"_id": user_id})

        if not user_data or "goals" not in user_data:
            await interaction.response.send_message("You don't have any tracked goals.")
            return

        embed = discord.Embed(title="Your Goals", color=discord.Color.blue())
        for goal in user_data["goals"]:
            progress = len(goal["progress"])
            deadline = goal.get("deadline", "No deadline")
            completed = "✅" if goal.get("completed", False) else "❌"
            embed.add_field(
                name=goal["goal"],
                value=f"Deadline: {deadline} | Progress Days: {progress} | Completed: {completed}",
                inline=False
            )

        points = user_data.get("points", 0)
        embed.add_field(name="Your Points", value=f"{points} points", inline=False)

        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="deletegoal", description="Delete a specific goal.")
    async def delete_goal(self, interaction: discord.Interaction, goal: str):
        """Delete a specific goal for the user."""
        user_id = interaction.user.id

        # Try to find the user's data
        user_data = self.collection.find_one({"_id": user_id})

        if not user_data or "goals" not in user_data or len(user_data["goals"]) == 0:
            await interaction.response.send_message("You don't have any tracked goals.", ephemeral=True)
            return

        # Find the goal to delete
        goal_to_delete = None
        for g in user_data["goals"]:
            if g["goal"] == goal:
                goal_to_delete = g
                break

        if not goal_to_delete:
            await interaction.response.send_message(f"Goal `{goal}` not found.", ephemeral=True)
            return

        # Remove the goal from the database
        try:
            self.collection.update_one(
                {"_id": user_id},
                {"$pull": {"goals": {"goal": goal}}}
            )
            await interaction.response.send_message(f"Goal `{goal}` has been deleted.", ephemeral=True)
        except Exception as e:
            print(f"Error deleting goal for user {user_id}: {e}")
            await interaction.response.send_message("An error occurred while deleting your goal.")


    @discord.app_commands.command(name="cleargoal", description="Clear completed goals.")
    async def clear_goal(self, interaction: discord.Interaction):
        """Clear all completed goals for the user who invoked the command."""
        user_id = interaction.user.id

        try:
            result = self.collection.update_one(
                {"_id": user_id},
                {"$pull": {"goals": {"completed": True}}}
            )
            if result.modified_count > 0:
                await interaction.response.send_message("All completed goals have been cleared.")
            else:
                await interaction.response.send_message("You don't have any completed goals to clear.")
        except Exception as e:
            print(f"Error clearing goals for user {user_id}: {e}")
            await interaction.response.send_message("An error occurred while clearing your goals.")

# Required setup function
async def setup(aurabot):
    await aurabot.add_cog(GoalTracking(aurabot))
    print("GoalTracking cog successfully added!")
