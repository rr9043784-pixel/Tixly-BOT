
import discord
from discord.ext import commands


class EventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Tixly is online as {self.bot.user} (ID: {self.bot.user.id})")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        print(f"Tixly joined server: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        print(f"Tixly left server: {guild.name} (ID: {guild.id})")


async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))
 
