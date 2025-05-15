import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

class Giveaway:
    def _init_(self, channel, prize, duration, winner, host, end_time, claim_time):
        self.channel = channel
        self.prize = prize
        self.duration = duration
        self.winner = winner
        self.host = host
        self.end_time = end_time
        self.claim_time = claim_time
        self.entries = set()
        self.message = None

    async def start(self):
        view = GiveawayView(self)
        embed = self.get_embed()
        self.message = await self.channel.send(embed=embed, view=view)
        self.update_loop.start()
        await asyncio.sleep(self.duration.total_seconds())
        self.update_loop.cancel()
        await self.end_giveaway()

    def get_embed(self):
        timestamp = int(self.end_time.timestamp())
        embed = discord.Embed(
            title=f"{self.prize} Giveaway!",
            color=discord.Color.purple()
        )
        embed.add_field(name="Host", value=self.host.mention, inline=False)
        embed.add_field(name="Entries & Winners", value=f"{len(self.entries)} entries | 1 winner", inline=False)
        embed.add_field(name="Ends At", value=f"<t:{timestamp}:F>", inline=False)
        embed.add_field(name="\u200b", value="Click the button below to enter!", inline=False)
        embed.set_footer(text="Good luck!")
        return embed

    @tasks.loop(seconds=5)
    async def update_loop(self):
        embed = self.get_embed()
        await self.message.edit(embed=embed)

    async def end_giveaway(self):
        embed = self.get_embed()
        embed.set_field_at(2, name="Ended At", value="Giveaway ended", inline=False)
        embed.add_field(name="Winner", value=self.winner.mention, inline=False)
        await self.message.edit(embed=embed, view=None)
        await self.message.reply(
            f"🎁 The {self.prize} Giveaway has ended!\n"
            f"🏆 The winner is {self.winner.mention}!\n"
            f"🎟 Make a ticket in support with the reason giveaway claim before {self.claim_time} or the giveaway will be rerolled."
        )

class GiveawayView(discord.ui.View):
    def _init_(self, giveaway):
        super()._init_(timeout=None)
        self.giveaway = giveaway
        self.add_item(JoinButton(giveaway))
        self.add_item(ExitButton(giveaway))
        self.add_item(ParticipantsButton(giveaway))

class JoinButton(discord.ui.Button):
    def _init_(self, giveaway):
        super()._init_(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success)
        self.giveaway = giveaway

    async def callback(self, interaction: discord.Interaction):
        if interaction.user in self.giveaway.entries:
            await interaction.response.send_message("You already entered this giveaway!", ephemeral=True)
        else:
            self.giveaway.entries.add(interaction.user)
            await interaction.response.send_message("You have entered the giveaway!", ephemeral=True)

class ExitButton(discord.ui.Button):
    def _init_(self, giveaway):
        super()._init_(label="🚪 Exit Giveaway", style=discord.ButtonStyle.danger)
        self.giveaway = giveaway

    async def callback(self, interaction: discord.Interaction):
        if interaction.user in self.giveaway.entries:
            self.giveaway.entries.remove(interaction.user)
            await interaction.response.send_message("You have exited the giveaway.", ephemeral=True)
        else:
            await interaction.response.send_message("You are not participating in this giveaway.", ephemeral=True)

class ParticipantsButton(discord.ui.Button):
    def _init_(self, giveaway):
        super()._init_(label="🧍 Participants", style=discord.ButtonStyle.secondary)
        self.giveaway = giveaway

    async def callback(self, interaction: discord.Interaction):
        if not self.giveaway.entries:
            await interaction.response.send_message("No participants yet.", ephemeral=True)
        else:
            participants = "\n".join(
                f"- {i + 1}. {user.mention}" for i, user in enumerate(self.giveaway.entries)
            )
            await interaction.response.send_message(f"Participants:\n{participants}", ephemeral=True)

@tree.command(name="giveaway", description="Create a giveaway!", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    prize="Prize of the giveaway",
    duration="Duration (e.g. 10s, 5m, 1h, 1d)",
    winner="The person who will win",
    host="The person hosting the giveaway",
    channel_id="ID of the channel to post the giveaway in",
    claim_time="Claim time (e.g. 30m, 2h)"
)
async def giveaway(interaction: discord.Interaction, prize: str, duration: str, winner: discord.Member, host: discord.Member, channel_id: str, claim_time: str):
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("Only the server owner can use this command.", ephemeral=True)
        return

    try:
        channel = await bot.fetch_channel(int(channel_id))
    except:
        await interaction.response.send_message("Invalid channel ID.", ephemeral=True)
        return

    multiplier = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    try:
        time_value = int(duration[:-1])
        time_unit = duration[-1]
        total_seconds = time_value * multiplier[time_unit]
        end_time = datetime.utcnow() + timedelta(seconds=total_seconds)
    except:
        await interaction.response.send_message("Invalid duration format. Use s, m, h, or d.", ephemeral=True)
        return

    try:
        ct_value = int(claim_time[:-1])
        ct_unit = claim_time[-1]
        if ct_unit not in ['m', 'h']:
            raise ValueError
    except:
        await interaction.response.send_message("Invalid claim_time format. Use m or h.", ephemeral=True)
        return

    g = Giveaway(channel, prize, timedelta(seconds=total_seconds), winner, host, end_time, claim_time)
    await interaction.response.send_message("Giveaway created!", ephemeral=True)
    await g.start()

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Bot is ready as {bot.user}")

bot.run(TOKEN)
