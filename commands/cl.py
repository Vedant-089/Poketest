import discord
from discord.ext import commands
from database import db
import json

with open("class.json", "r") as f:
    VALID_POKEMON = set(name.lower() for name in json.load(f).keys())

class CollectionCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="cl", invoke_without_command=True)
    async def cl(self, ctx):
        await ctx.send("Usage: `p!cl add/remove/clear <pokemon>`")

    @cl.command(name="add")
    async def add(self, ctx, *, names: str):
        user_id = ctx.author.id
        input_names = [n.strip().lower() for n in names.split(",")]
        valid_names = [n for n in input_names if n in VALID_POKEMON]
        invalid = [n for n in input_names if n not in VALID_POKEMON]

        if not valid_names:
            return await ctx.send("❌ No valid Pokémon provided.")

        row = await db.fetchrow("SELECT collection FROM shusers WHERE userid = $1", user_id)
        existing = set(row["collection"].split(",")) if row and row["collection"] else set()

        updated = existing.union(valid_names)
        updated_str = ",".join(sorted(updated))

        await db.execute(
            "UPDATE shusers SET collection = $1 WHERE userid = $2",
            updated_str, user_id
        )

        response = f"✅ Added: {', '.join(valid_names)}"
        if invalid:
            response += f"\n❌ Invalid: {', '.join(invalid)}"
        await ctx.send(response)

    @cl.command(name="remove")
    async def remove(self, ctx, *, names: str):
        user_id = ctx.author.id
        input_names = [n.strip().lower() for n in names.split(",")]

        row = await db.fetchrow("SELECT collection FROM shusers WHERE userid = $1", user_id)
        if not row or not row["collection"]:
            return await ctx.send("ℹ️ Your collection is already empty.")

        current = set(row["collection"].split(","))
        updated = current - set(input_names)
        updated_str = ",".join(sorted(updated))

        await db.execute(
            "UPDATE shusers SET collection = $1 WHERE userid = $2",
            updated_str, user_id
        )

        await ctx.send(f"🗑️ Removed: {', '.join(input_names)}")

    @cl.command(name="clear")
    async def clear(self, ctx):
        user_id = ctx.author.id
        await db.execute("UPDATE shusers SET collection = NULL WHERE userid = $1", user_id)
        await ctx.send("🧹 Your collection has been cleared.")

    @cl.command(name="list")
    async def list_collection(self, ctx):
        user_id = ctx.author.id

        row = await db.fetchrow("SELECT collection FROM shusers WHERE userid = $1", user_id)
        if not row or not row["collection"]:
            return await ctx.send("📭 You don't have any Pokémon in your collection.")

        collection = sorted(row["collection"].split(","))
        embed = discord.Embed(
            title="📦 Pokémon Collection",
            description="\n".join(collection),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"{ctx.author.display_name}'s collection")

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CollectionCommands(bot))
