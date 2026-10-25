import os
import asyncio
import io
import discord
import httpx
from discord import app_commands
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
        await self.tree.sync()

bot = TixlyBot(command_prefix="!", intents=intents)

async def get_config(guild_id: int) -> dict:
    if not API_KEY:
        return {}
    headers = {"X-Tixly-Key": API_KEY}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{API_URL}/guilds/{guild_id}/config", headers=headers)
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json()

@bot.event
async def on_ready():
    print(f"Tixly is online as {bot.user} (ID: {bot.user.id})")

@bot.tree.command(name="ping", description="Check whether Tixly is online.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Tixly is online!", ephemeral=True)

@bot.tree.command(name="ticket-panel", description="Post the ticket panel in this channel.")
@app_commands.checks.has_permissions(manage_guild=True)
async def ticket_panel(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Use this command in a server.", ephemeral=True)
        return
    config = await get_config(interaction.guild.id)
    title = config.get("panel_title") or "Contact Support"
    description = config.get("panel_description") or "Choose the button below to open a support ticket."
    embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed, view=TicketPanelView())

@bot.tree.command(name="close", description="Close the current ticket channel.")
async def close_ticket(interaction: discord.Interaction):
    if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This command can only be used in a ticket channel.", ephemeral=True)
        return
    topic = interaction.channel.topic or ""
    if not topic.startswith("tixly-ticket:"):
        await interaction.response.send_message("This channel is not marked as a Tixly ticket.", ephemeral=True)
        return
    config = await get_config(interaction.guild.id)
    support_role_id = config.get("support_role_id")
    member = interaction.user
    is_support = isinstance(member, discord.Member) and (
        member.guild_permissions.manage_channels or
        (support_role_id and any(role.id == int(support_role_id) for role in member.roles))
    )
    is_opener = topic == f"tixly-ticket:{member.id}"
    if not (is_support or is_opener):
        await interaction.response.send_message("Only the ticket opener or support team can close this ticket.", ephemeral=True)
        return
    await interaction.response.send_message("Closing this ticket…", ephemeral=True)
    await interaction.channel.delete(reason=f"Tixly ticket closed by {member}")

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.primary, custom_id="tixly:open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return
        config = await get_config(guild.id)
        category = guild.get_channel(int(config.get("category_id") or 0))
        if category is not None and not isinstance(category, discord.CategoryChannel):
            category = None
        existing = discord.utils.find(
            lambda ch: isinstance(ch, discord.TextChannel) and ch.topic == f"tixly-ticket:{interaction.user.id}",
            guild.text_channels
        )
        if existing:
            await interaction.response.send_message(f"You already have a ticket: {existing.mention}", ephemeral=True)
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True),
        }
        support_role_id = config.get("support_role_id")
        if support_role_id:
            role = guild.get_role(int(support_role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        safe_name = "".join(c.lower() if c.isalnum() else "-" for c in interaction.user.display_name).strip("-")
        channel = await guild.create_text_channel(
            name=f"ticket-{safe_name[:40] or interaction.user.id}",
            category=category,
            overwrites=overwrites,
            topic=f"tixly-ticket:{interaction.user.id}",
            reason=f"Tixly ticket opened by {interaction.user}"
        )
        await channel.send(f"{interaction.user.mention} Thanks for contacting support. A team member will be with you soon.")
        await interaction.response.send_message(f"Your ticket has been created: {channel.mention}", ephemeral=True)

@ticket_panel.error
async def ticket_panel_error(interaction: discord.Interaction, error):
    message = "You need the Manage Server permission to post a ticket panel."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing. Copy .env.example to .env and set it.")
bot.run(TOKEN)
 
