import discord
from discord.ext import tasks, commands
from discord import app_commands, ui
from datetime import datetime, timedelta
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

class Giveaway:
    def __init__(self, prize, end_time, winner_count, host, claim_time):
        self.prize = prize
        self.end_time = end_time
        self.winner_count = winner_count
        self.host = host
        self.claim_time = claim_time
        self.entries = set()
        self.message = None

    def has_ended(self):
        return datetime.utcnow() >= self.end_time

giveaways = {}

class GiveawayView(ui.View):
    def __init__(self, giveaway):
        super().__init__(timeout=None)
        self.giveaway = giveaway

    @ui.button(label="🎉 0", style=discord.ButtonStyle.primary, custom_id="join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.giveaway.entries:
            await interaction.response.send_message("You already entered!", ephemeral=True)
        else:
            self.giveaway.entries.add(interaction.user.id)
            button.label = f"🎉 {len(self.giveaway.entries)}"
            await interaction.response.edit_message(view=self)

    @ui.button(label="🚪 Exit Giveaway", style=discord.ButtonStyle.danger, custom_id="exit")
    async def exit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.giveaway.entries:
            self.giveaway.entries.remove(interaction.user.id)
            self.join.label = f"🎉 {len(self.giveaway.entries)}"
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("You haven't entered!", ephemeral=True)

    @ui.button(label="🧍 Participants", style=discord.ButtonStyle.secondary, custom_id="participants")
    async def participants(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.giveaway.entries:
            await interaction.response.send_message("No participants yet.", ephemeral=True)
        else:
            users = [f"<@{uid}>" for uid in self.giveaway.entries]
            await interaction.response.send_message("**Participants:**\n" + "\n".join(users), ephemeral=True)

def build_embed(giveaway: Giveaway):
    now = datetime.utcnow()
    remaining = int((giveaway.end_time - now).total_seconds())
    minutes = remaining // 60
    seconds = remaining % 60
    embed = discord.Embed(
        title=f"🎉 **{giveaway.prize} Giveaway!**",
        color=0x00ffcc,
        description=f"**Hosted by:** {giveaway.host.mention}"
    )
    embed.add_field(name="Winners:", value=str(giveaway.winner_count), inline=False)
    embed.add_field(name="Participants", value=f"**{len(giveaway.entries)}**", inline=False)
    embed.add_field(name="Ends in", value=f"`{minutes:02d}:{seconds:02d}` minutes", inline=False)
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1371213195674390558/1372631772600467556/IMG_9097.png")
    return embed

@tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(
    channel="Channel to host the giveaway",
    prize="Prize of the giveaway",
    duration="Duration in minutes",
    winners="Number of winners",
    claim_time="Time in minutes to claim the prize"
)
async def giveaway(interaction: discord.Interaction, channel: discord.TextChannel, prize: str, duration: int, winners: int, claim_time: int):
    end_time = datetime.utcnow() + timedelta(minutes=duration)
    g = Giveaway(prize, end_time, winners, interaction.user, claim_time)
    view = GiveawayView(g)
    embed = build_embed(g)
    msg = await channel.send(embed=embed, view=view)
    g.message = msg
    giveaways[msg.id] = g
    await interaction.response.send_message(f"Giveaway started in {channel.mention}!", ephemeral=True)
    update_embed.start(msg.id)

@tasks.loop(seconds=5)
async def update_embed(message_id):
    giveaway = giveaways.get(message_id)
    if giveaway and not giveaway.has_ended():
        embed = build_embed(giveaway)
        await giveaway.message.edit(embed=embed, view=GiveawayView(giveaway))
    elif giveaway:
        winners = list(giveaway.entries)
        if not winners:
            content = "No one entered the giveaway."
        else:
            selected = [f"<@{uid}>" for uid in winners[:giveaway.winner_count]]
            content = f"🎉 Congratulations {' '.join(selected)}! You won **{giveaway.prize}**!\n\n"
            content += f"🎟️ Make a ticket in support with the reason giveaway claim before **{giveaway.claim_time} minutes** or the giveaway will be rerolled."
        await giveaway.message.channel.send(content)
        update_embed.stop()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

bot.run(TOKEN)
