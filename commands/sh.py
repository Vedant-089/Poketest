import json
import logging
from pathlib import Path

import discord
from discord.ext import commands

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s:%(lineno)d — %(message)s",
)
log = logging.getLogger("ShinyHunt")

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

JSON_PATH = Path("class.json")  # valid Pokémon names
TABLE_SQL = """
CREATE TABLE IF NOT EXISTS shusers (
    userid       BIGINT PRIMARY KEY,
    shiny_hunt   TEXT,
    collection   TEXT,
    shinyafk     BOOLEAN DEFAULT FALSE,
    colafk       BOOLEAN DEFAULT FALSE
);
"""

# ---------------------------------------------------------------------------
# UTILS
# ---------------------------------------------------------------------------

def load_valid_pokemon():
    """Return a cached, case‑insensitive Pokémon whitelist."""
    try:
        with JSON_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        pokemon_set = {name.lower().strip() for name in data}
        log.info("Loaded %d Pokémon names from class.json", len(pokemon_set))
        return pokemon_set
    except FileNotFoundError:
        log.warning("class.json missing – accepting no Pokémon names.")
        return set()


VALID_POKEMON = load_valid_pokemon()

# ---------------------------------------------------------------------------
# COG
# ---------------------------------------------------------------------------

class ShinyHunt(commands.Cog):
    """`!sh <pokemon>` — set your shiny hunt (validated via class.json)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------------------
    # DB helpers
    # ---------------------------------------------------------------------

    async def ensure_table(self):
        """Create `shusers` table if it does not exist."""
        log.debug("Ensuring shusers table exists …")
        await self.bot.db.execute(TABLE_SQL)

    async def set_shiny_hunt(self, user_id: int, pokemon: str):
        """Insert or update shiny_hunt column for a user and log status."""
        query = (
            """
            INSERT INTO shusers (userid, shiny_hunt)
            VALUES ($1, $2)
            ON CONFLICT (userid) DO UPDATE
            SET shiny_hunt = EXCLUDED.shiny_hunt;
            """
        )
        status = await self.bot.db.execute(query, user_id, pokemon)
        log.info("DB status after setting hunt for %s → %s: %s", user_id, pokemon, status)

    # ---------------------------------------------------------------------
    # Command
    # ---------------------------------------------------------------------

    @commands.command(name="sh", aliases=["shinyhunt"])
    async def shiny_hunt(self, ctx: commands.Context, *, pokemon=None):
        """Register a shiny hunt if *pokemon* is on the official list, or show current hunt."""
        log.debug("Command invoked by %s (%s) with arg: %s", ctx.author, ctx.author.id, pokemon)

        # ------------------------------------------------------------
        # Case 1 — user typed just p!sh → show current hunt
        # ------------------------------------------------------------
        if pokemon is None:
            query = "SELECT shiny_hunt FROM shusers WHERE userid = $1;"
            row = await self.bot.db.fetchrow(query, ctx.author.id)

            if row and row['shiny_hunt']:
                await ctx.reply(f"🔍 You're currently hunting **{row['shiny_hunt'].title()}**!")
            else:
                await ctx.reply("❌ You are not hunting any Pokémon currently.")
            return

        # ------------------------------------------------------------
        # Case 2 — user typed p!sh none/reset → clear shiny hunt
        # ------------------------------------------------------------
        key = str(pokemon).lower().strip()

        if key in ["none", "reset", "null", "nothing"]:
            reset_query = """
                INSERT INTO shusers (userid, shiny_hunt)
                VALUES ($1, NULL)
                ON CONFLICT (userid) DO UPDATE
                SET shiny_hunt = NULL;
            """

            await self.bot.db.execute(reset_query, ctx.author.id)
            await ctx.reply("🧹 Your shiny hunt has been **reset**. You're now hunting nothing.")
            return

        # ------------------------------------------------------------
        # Case 3 — normal shiny hunt set (validate Pokémon)
        # ------------------------------------------------------------
        if key not in VALID_POKEMON:
            log.debug("%s is not in whitelist", key)
            await ctx.reply(f"❌ **{pokemon}** isn't on the recognised Pokémon list.")
            return

        try:
            await self.set_shiny_hunt(ctx.author.id, key)
            await ctx.reply(f"✅ Shiny hunt updated to **{pokemon.title()}**!")
        except Exception as e:
            log.exception("Failed to set shiny hunt for %s → %s", ctx.author.id, key)
            await ctx.reply("⚠️ An error occurred while saving your shiny hunt. Please try again later.")

    # ---------------------------------------------------------------------
    # Listeners
    # ---------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        # Ensure table exists once the bot is logged in and DB is ready
        await self.ensure_table()
        log.info("[ShinyHunt] table checked/created and cog ready.")

# ---------------------------------------------------------------------------
# COG SETUP (called by main.py)
# ---------------------------------------------------------------------------

async def setup(bot: commands.Bot):
    await bot.add_cog(ShinyHunt(bot))