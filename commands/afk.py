import discord
from discord.ext import commands
from database import db

class AFKButtonView(discord.ui.View):
    def __init__(self, user_id, shinyafk: bool, colafk: bool):
        super().__init__(timeout=None)
        self.user_id = user_id

        # Invert the logic here — red = AFK = True
        self.hunt_button = discord.ui.Button(
            label="Hunt Ping",
            style=discord.ButtonStyle.danger if shinyafk else discord.ButtonStyle.success,
            custom_id="afk_hunt"
        )
        self.collection_button = discord.ui.Button(
            label="Collection Ping",
            style=discord.ButtonStyle.danger if colafk else discord.ButtonStyle.success,
            custom_id="afk_collection"
        )

        self.add_item(self.hunt_button)
        self.add_item(self.collection_button)

        self.hunt_button.callback = self.toggle_hunt
        self.collection_button.callback = self.toggle_collection

    async def toggle_hunt(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Only you can use these buttons.", ephemeral=True)

        current = await db.fetchval("SELECT shinyafk FROM shusers WHERE userid = $1", self.user_id)
        new_val = not current
        await db.execute("UPDATE shusers SET shinyafk = $1 WHERE userid = $2", new_val, self.user_id)

        # Update style: red if AFK (True), green if not
        self.hunt_button.style = discord.ButtonStyle.danger if new_val else discord.ButtonStyle.success
        await interaction.response.edit_message(view=self)

    async def toggle_collection(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Only you can use these buttons.", ephemeral=True)

        current = await db.fetchval("SELECT colafk FROM shusers WHERE userid = $1", self.user_id)
        new_val = not current
        await db.execute("UPDATE shusers SET colafk = $1 WHERE userid = $2", new_val, self.user_id)

        self.collection_button.style = discord.ButtonStyle.danger if new_val else discord.ButtonStyle.success
        await interaction.response.edit_message(view=self)

class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="afk")
    async def afk(self, ctx):
        user_id = ctx.author.id

        # Ensure the user is in the database
        await db.execute("""
            INSERT INTO shusers (userid, shinyafk, colafk)
            VALUES ($1, false, false)
            ON CONFLICT (userid) DO NOTHING
        """, user_id)

        shinyafk = await db.fetchval("SELECT shinyafk FROM shusers WHERE userid = $1", user_id)
        colafk = await db.fetchval("SELECT colafk FROM shusers WHERE userid = $1", user_id)

        embed = discord.Embed(
            title="AFK Status",
            description="Shows your AFK status.\n\nRed = AFK ON\nGreen = AFK OFF",
            color=discord.Color.orange()
        )

        view = AFKButtonView(user_id, shinyafk, colafk)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(AFK(bot))
