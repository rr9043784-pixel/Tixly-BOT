
import discord
from discord import app_commands
from discord.ext import commands


class TicketPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.primary,
        custom_id="tixly:open_ticket"
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        guild = interaction.guild

        if guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This can only be used in a server.",
                ephemeral=True
            )
            return

        config = await self.bot.get_config(guild.id)

        category_id = config.get("category_id")
        category = guild.get_channel(int(category_id)) if category_id else None

        if category is not None and not isinstance(category, discord.CategoryChannel):
            category = None

        existing = discord.utils.find(
            lambda channel: (
                isinstance(channel, discord.TextChannel)
                and channel.topic == f"tixly-ticket:{interaction.user.id}"
            ),
            guild.text_channels
        )

        if existing:
            await interaction.response.send_message(
                f"You already have a ticket: {existing.mention}",
                ephemeral=True
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        }

        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True
            )

        support_role_id = config.get("support_role_id")
        if support_role_id:
            role = guild.get_role(int(support_role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        safe_name = "".join(
            char.lower() if char.isalnum() else "-"
            for char in interaction.user.display_name
        ).strip("-")

        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{safe_name[:40] or interaction.user.id}",
                category=category,
                overwrites=overwrites,
                topic=f"tixly-ticket:{interaction.user.id}",
                reason=f"Tixly ticket opened by {interaction.user}"
            )

            await channel.send(
                f"{interaction.user.mention} Thanks for contacting support. "
                "A team member will be with you soon."
            )

            await interaction.response.send_message(
                f"Your ticket has been created: {channel.mention}",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to create ticket channels.",
                ephemeral=True
            )


class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ticket-panel",
        description="Post the ticket panel in this channel."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Use this command in a server.",
                ephemeral=True
            )
            return

        config = await self.bot.get_config(interaction.guild.id)

        embed = discord.Embed(
            title=config.get("panel_title") or "Contact Support",
            description=config.get("panel_description")
            or "Choose the button below to open a support ticket.",
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(
            embed=embed,
            view=TicketPanelView(self.bot)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
    bot.add_view(TicketPanelView(bot))
 
