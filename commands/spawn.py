import discord
from discord.ext import commands
import torch
import timm
from torchvision import transforms
from PIL import Image
import aiohttp
import io
import json
import urllib.request
import os

from database import db
from functions import get_users_hunting, get_users_collecting

POKETWO_BOT_ID = 716390085896962058
MODEL_PATH = "pokemon_model.pt"
MODEL_NAME = "convnext_tiny.fb_in22k"
IMG_SIZE = 224
CONF_THRESHOLD = 0.30  # 30%

if not os.path.exists(MODEL_PATH):
    print("Downloading model from HuggingFace...")
    urllib.request.urlretrieve(
        "https://huggingface.co/veduxd/pokemon_model/resolve/main/pokemon_model.pt",
        MODEL_PATH
    )
    print("Model downloaded.")


def preprocess_image(img: Image.Image):
    transform = transforms.Compose(
        [
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize([0.5] * 3, [0.5] * 3),
        ]
    )
    return transform(img).unsqueeze(0)


class SpawnPredictor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.ensure_db_connected())

        # Load class.json
        with open("class.json", "r") as f:
            idx_map = json.load(f)

        self.idx_to_name = [None] * len(idx_map)
        for name, idx in idx_map.items():
            self.idx_to_name[idx] = name

        # Load typing.json
        with open("typing.json", "r", encoding="utf-8") as f:
            self.typing_data = json.load(f)

        # Load region.json
        with open("region.json", "r", encoding="utf-8") as f:
            self.region_data = json.load(f)

        # Load PyTorch model
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = timm.create_model(
            MODEL_NAME, pretrained=False, num_classes=len(self.idx_to_name)
        )
        self.model.load_state_dict(torch.load(MODEL_PATH, map_location=self.device))
        self.model.eval().to(self.device)

        self.session = aiohttp.ClientSession()

    async def ensure_db_connected(self):
        if not db.pool:
            await db.connect()

    async def cog_unload(self):
        await self.session.close()

    def get_pokemon_types(self, name: str):
        types = []
        for t, names in self.typing_data.items():
            if name.lower() in [n.lower() for n in names]:
                types.append(t)
        return types

    def get_pokemon_regions(self, name: str):
        regions = []
        for r, names in self.region_data.items():
            if name.lower() in [n.lower() for n in names]:
                regions.append(r)
        return regions

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            message.author.id != POKETWO_BOT_ID
            or not message.embeds
            or not (message.embeds[0].image and message.embeds[0].image.url)
        ):
            return

        try:
            # 1. Download image
            async with self.session.get(message.embeds[0].image.url) as resp:
                if resp.status != 200:
                    return
                img_bytes = await resp.read()

            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            tensor = preprocess_image(img).to(self.device)

            # 2. Run PyTorch prediction
            with torch.no_grad():
                probs = torch.softmax(self.model(tensor), dim=1)[0]

            top_idx = int(torch.argmax(probs))
            confidence = float(probs[top_idx])
            name = self.idx_to_name[top_idx]

            if confidence < CONF_THRESHOLD:
                await message.channel.send("❌ Not confident enough to guess this Pokémon.")
                return

            hunters = await get_users_hunting(name, db)
            collectors = await get_users_collecting(name, db)

            types = self.get_pokemon_types(name)
            regions = self.get_pokemon_regions(name)

            # Role/find mentions
            type_role_mentions = []
            for t in types:
                role = discord.utils.get(message.guild.roles, name=t.lower())
                if role:
                    type_role_mentions.append(role.mention)

            region_role_mentions = []
            for r in regions:
                role = discord.utils.get(message.guild.roles, name=r.lower())
                if role:
                    region_role_mentions.append(role.mention)

            reply_lines = [
                f"{name}: {confidence:.3%}",
                f"Best Name: **{name}**",
            ]

            if type_role_mentions:
                reply_lines.append("Type Pings: " + ", ".join(type_role_mentions))
            if types:
                reply_lines.append("Types: " + ", ".join(types))

            if region_role_mentions:
                reply_lines.append("Region Pings: " + ", ".join(region_role_mentions))
            if regions:
                reply_lines.append("Regions: " + ", ".join(regions))

            if hunters:
                reply_lines.append("Hunt Pings: " + ", ".join(f"<@{uid}>" for uid in hunters))
            if collectors:
                reply_lines.append("Col Pings: " + ", ".join(f"<@{uid}>" for uid in collectors))

            await message.channel.send("\n".join(reply_lines))

        except Exception as e:
            print("⚠️ Prediction error:", e)


async def setup(bot):
    await bot.add_cog(SpawnPredictor(bot))