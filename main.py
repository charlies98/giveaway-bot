import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import uuid
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

giveaways = {}

class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success, custom_id="enter")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = giveaways.get(self.giveaway_id)
        if not giveaway:
            await interaction.response.send_message("This giveaway no longer exists.", ephemeral=True)
            return

        if interaction.user.id in giveaway["entrants"]:
            await interaction.response.send_message("You already entered the giveaway.", ephemeral=True)
            return

        # Entradas extra por rol
        entries = 1
        for role_id, extra in giveaway["extra_roles"].items():
            if discord.utils.get(interaction.user.roles, id=role_id):
                entries += extra

        giveaway["entrants"][interaction.user.id] = entries
        await interaction.response.send_message("✅ You have successfully entered the giveaway!", ephemeral=True)
        await update_giveaway_panel(interaction.guild, giveaway)

    @discord.ui.button(label="🚪 Exit Giveaway", style=discord.ButtonStyle.danger, custom_id="exit")
    async def exit(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = giveaways.get(self.giveaway_id)
        if not giveaway or interaction.user.id not in giveaway["entrants"]:
            await interaction.response.send_message("You are not in the giveaway.", ephemeral=True)
            return

        del giveaway["entrants"][interaction.user.id]
        await interaction.response.send_message("❌ You have successfully left the giveaway.", ephemeral=True)
        await update_giveaway_panel(interaction.guild, giveaway)

    @discord.ui.button(label="🧍 Participants", style=discord.ButtonStyle.secondary, custom_id="participants")
    async def participants(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = giveaways.get(self.giveaway_id)
        if not giveaway:
            await interaction.response.send_message("This giveaway no longer exists.", ephemeral=True)
            return

        if not giveaway["entrants"]:
            await interaction.response.send_message("No participants yet.", ephemeral=True)
            return

        guild = interaction.guild
        msg = "\n".join(f"{i+1}. {guild.get_member(uid).mention}" for i, uid in enumerate(giveaway["entrants"]))
        await interaction.response.send_message(msg, ephemeral=True)

async def update_giveaway_panel(guild, giveaway):
    remaining = giveaway["end_time"] - datetime.utcnow()
    months, days = divmod(remaining.days, 30)
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    countdown = f"Ends in: {months}mo, {days}d, {hours}h, {minutes}m, {seconds}s"

    embed = discord.Embed(
        title=f"🎉 **{giveaway['prize']} Giveaway!**",
        description="Click the button below to enter!",
        color=discord.Color.purple()
    )
    embed.set_image(url=giveaway["image"])
    embed.add_field(name="Hosted by", value=giveaway["host"].mention, inline=True)
    embed.add_field(name="Winners", value=str(giveaway["winners"]), inline=True)
    embed.add_field(name="**Participants**", value=f"**{len(giveaway['entrants'])}**", inline=True)
    embed.add_field(name="Ends at", value=countdown, inline=False)

    try:
        channel = guild.get_channel(giveaway["channel_id"])
        message = await channel.fetch_message(giveaway["message_id"])
        await message.edit(embed=embed, view=GiveawayView(giveaway["id"]))
    except:
        pass

@tree.command(name="giveaway", description="Create a new giveaway")
@app_commands.describe(prize="Prize", duration="Duration (minutes)", winners="Number of winners", image="Image URL", extra_entries="Extra entries: role_id=entries,...")
async def giveaway_command(interaction: discord.Interaction, prize: str, duration: int, winners: int, image: str, extra_entries: str = ""):
    await interaction.response.defer(ephemeral=True)

    end_time = datetime.utcnow() + timedelta(minutes=duration)
    giveaway_id = str(uuid.uuid4())

    # Parse extra roles
    extra_roles = {}
    if extra_entries:
        for part in extra_entries.split(","):
            try:
                role_id, bonus = map(str.strip, part.split("="))
                extra_roles[int(role_id)] = int(bonus)
            except:
                continue

    embed = discord.Embed(
        title=f"🎉 **{prize} Giveaway!**",
        description="Click the button below to enter!",
        color=discord.Color.purple()
    )
    embed.set_image(url=image)
    embed.add_field(name="Hosted by", value=interaction.user.mention, inline=True)
    embed.add_field(name="Winners", value=str(winners), inline=True)
    embed.add_field(name="**Participants**", value="**0**", inline=True)
    embed.add_field(name="Ends at", value="Calculating...", inline=False)

    message = await interaction.channel.send(embed=embed, view=GiveawayView(giveaway_id))

    giveaways[giveaway_id] = {
        "id": giveaway_id,
        "prize": prize,
        "host": interaction.user,
        "winners": winners,
        "entrants": {},
        "end_time": end_time,
        "message_id": message.id,
        "channel_id": interaction.channel.id,
        "image": image,
        "extra_roles": extra_roles
    }

    @tasks.loop(seconds=5)
    async def countdown():
        if datetime.utcnow() >= end_time:
            await finish_giveaway(interaction.guild, giveaways[giveaway_id])
            countdown.stop()
            return
        await update_giveaway_panel(interaction.guild, giveaways[giveaway_id])

    countdown.start()
    await interaction.followup.send("🎉 Giveaway created successfully!", ephemeral=True)

async def finish_giveaway(guild, giveaway):
    entrants = list(giveaway["entrants"].items())
    if not entrants:
        winner_mentions = "No one entered the giveaway."
    else:
        weighted = [uid for uid, entries in entrants for _ in range(entries)]
        winners = set()
        while len(winners) < min(len(weighted), giveaway["winners"]):
            winners.add(guild.get_member(weighted.pop(0)))
        winner_mentions = ", ".join(w.mention for w in winners if w)

    channel = guild.get_channel(giveaway["channel_id"])
    try:
        message = await channel.fetch_message(giveaway["message_id"])
        embed = message.embeds[0]
        embed.set_field_at(1, name="Winners", value=winner_mentions or "None", inline=True)
        await message.edit(embed=embed, view=None)
    except:
        pass

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot is ready. Logged in as {bot.user}.")

bot.run(os.environ["DISCORD_BOT_TOKEN"])
