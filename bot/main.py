
import os

import discord
import httpx
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
API_URL = os.getenv("BOT_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("TIXLY_API_KEY", "")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True


class TixlyBot(commands.Bot):
    async def setup_hook(self):
        await self.load_extension("bot.tickets")
        await self.load_extension("bot.events")
        await self.tree.sync()

    async def get_config(self, guild_id: int) -> dict:
        if not API_KEY:
            return {}

        headers = {"X-Tixly-Key": API_KEY}

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{API_URL}/guilds/{guild_id}/config",
                headers=headers
            )

            if response.status_code == 404:
                return {}

            response.raise_for_status()
            return response.json()


bot = TixlyBot(command_prefix="!", intents=intents)


@bot.tree.command(name="ping", description="Check whether Tixly is online.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Tixly is online!",
        ephemeral=True
    )


@bot.tree.command(
    name="close",
    description="Close the current ticket channel."
)
async def close_ticket(interaction: discord.Interaction):
    if (
        interaction.guild is None
        or not isinstance(interaction.channel, discord.TextChannel)
    ):
        await interaction.response.send_message(
            "This command can only be used in a ticket channel.",
            ephemeral=True
        )
        return

    topic = interaction.channel.topic or ""

    if not topic.startswith("tixly-ticket:"):
        await interaction.response.send_message(
            "This channel is not marked as a Tixly ticket.",
            ephemeral=True
        )
        return

    try:
        config = await bot.get_config(interaction.guild.id)
    except (httpx.HTTPError, ValueError):
        config = {}

    support_role_id = config.get("support_role_id")
    member = interaction.user

    is_support = isinstance(member, discord.Member) and (
        member.guild_permissions.manage_channels
        or (
            support_role_id
            and any(
                role.id == int(support_role_id)
                for role in member.roles
            )
        )
    )

    is_opener = topic == f"tixly-ticket:{member.id}"

    if not (is_support or is_opener):
        await interaction.response.send_message(
            "Only the ticket opener or support team can close this ticket.",
            ephemeral=True
        )
        return

    channel = interaction.channel

    await interaction.response.send_message(
        "Closing this ticket…",
        ephemeral=True
    )

    await channel.delete(reason=f"Tixly ticket closed by {member}")


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing.")

bot.run(TOKEN)
