import discord
from discord.ext import commands
from discord import app_commands, ui
from datetime import datetime, timedelta
import asyncio
import os

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Cargar variables de entorno
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

giveaways = {}

class Giveaway:
    def __init__(self, message, prize, winners, host, end_time, claim_time):
        self.message = message
        self.prize = prize
        self.winners = winners
        self.host = host
        self.end_time = end_time
        self.claim_time = claim_time
        self.entries = set()

class GiveawayView(ui.View):
    def __init__(self, giveaway: Giveaway):
        super().__init__(timeout=None)
        self.giveaway = giveaway
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        self.add_item(EnterButton(self.giveaway))
        self.add_item(ParticipantsButton(self.giveaway))
        self.add_item(ExitButton(self.giveaway))

class EnterButton(ui.Button):
    def __init__(self, giveaway: Giveaway):
        super().__init__(label=f"🎉 {len(giveaway.entries)}", style=discord.ButtonStyle.primary)
        self.giveaway = giveaway

    async def callback(self, interaction: discord.Interaction):
        self.giveaway.entries.add(interaction.user.id)
        self.label = f"🎉 {len(self.giveaway.entries)}"
        await interaction.response.edit_message(view=self.view)

class ParticipantsButton(ui.Button):
    def __init__(self, giveaway: Giveaway):
        super().__init__(label="Participants", style=discord.ButtonStyle.secondary)
        self.giveaway = giveaway

    async def callback(self, interaction: discord.Interaction):
        users = [f"<@{uid}>" for uid in self.giveaway.entries]
        entries_text = ", ".join(users) if users else "No participants yet."
        await interaction.response.send_message(
            f"**Participants:**\n{entries_text}",
            ephemeral=True
        )

class ExitButton(ui.Button):
    def __init__(self, giveaway: Giveaway):
        super().__init__(label="🚪 Exit Giveaway", style=discord.ButtonStyle.danger)
        self.giveaway = giveaway

    async def callback(self, interaction: discord.Interaction):
        self.giveaway.entries.discard(interaction.user.id)
        self.view.children[0].label = f"🎉 {len(self.giveaway.entries)}"
        await interaction.response.edit_message(view=self.view)

@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Logged in as {bot.user}")

@bot.tree.command(guild=discord.Object(id=GUILD_ID), name="giveaway", description="Start a giveaway")
@app_commands.describe(
    channel="Channel where the giveaway will be hosted",
    prize="Prize name",
    duration_minutes="Duration in minutes",
    winners="Number of winners",
    claim_time_minutes="Time to claim prize in minutes"
)
async def giveaway(interaction: discord.Interaction, channel: discord.TextChannel, prize: str, duration_minutes: int, winners: int, claim_time_minutes: int):
    end_time = datetime.utcnow() + timedelta(minutes=duration_minutes)
    claim_time = datetime.utcnow() + timedelta(minutes=claim_time_minutes)

    embed = discord.Embed(
        title=f"🎉 **{prize} Giveaway!**",
        description="Click the 🎉 button to enter!",
        color=discord.Color.purple()
    )
    embed.add_field(name="Winners", value=f"**{winners}**", inline=False)
    embed.add_field(name="Participants", value=f"**0**", inline=False)
    embed.add_field(name="Hosted by", value=interaction.user.mention, inline=False)
    embed.add_field(name="Ends at", value=discord.utils.format_dt(end_time, style='F'), inline=False)

    giveaway_obj = Giveaway(None, prize, winners, interaction.user, end_time, claim_time)
    view = GiveawayView(giveaway_obj)

    message = await channel.send(embed=embed, view=view)
    giveaway_obj.message = message
    giveaways[message.id] = giveaway_obj

    await interaction.response.send_message("Giveaway started!", ephemeral=True)

    await asyncio.sleep(duration_minutes * 60)

    if not giveaway_obj.entries:
        await message.edit(content="🎉 **GIVEAWAY ENDED** 🎉\nNo participants.", view=None)
        return

    winner_ids = list(giveaway_obj.entries)[:winners]
    winners_mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)

    end_embed = discord.Embed(
        title=f"🎉 **{prize} Giveaway!**",
        description=f"Winner: {winners_mentions}\nHosted by: {interaction.user.mention}",
        color=discord.Color.red()
    )
    end_embed.set_footer(text=f"Ended at | {discord.utils.format_dt(datetime.utcnow(), style='F')}")

    await message.edit(content="🎉 **GIVEAWAY ENDED** 🎉", embed=end_embed, view=view)
    await message.channel.send(f"Congratulations {winners_mentions}! You won **{prize}**!")

# Ejecutar el bot
bot.run(TOKEN)
