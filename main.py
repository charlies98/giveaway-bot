import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import os

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

giveaways = {}

class GiveawayView(discord.ui.View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success, custom_id="enter_button")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = giveaways.get(self.message_id)
        if giveaway:
            if interaction.user.id not in giveaway["entrants"]:
                giveaway["entrants"].append(interaction.user.id)
                await interaction.response.send_message("You have entered the giveaway!", ephemeral=True)
            else:
                await interaction.response.send_message("You are already entered.", ephemeral=True)

    @discord.ui.button(label="🚪 Exit Giveaway", style=discord.ButtonStyle.danger, custom_id="exit_button")
    async def exit(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = giveaways.get(self.message_id)
        if giveaway:
            if interaction.user.id in giveaway["entrants"]:
                giveaway["entrants"].remove(interaction.user.id)
                await interaction.response.send_message("You have left the giveaway.", ephemeral=True)
            else:
                await interaction.response.send_message("You are not in the giveaway.", ephemeral=True)

    @discord.ui.button(label="🧍 Participants", style=discord.ButtonStyle.secondary, custom_id="participants_button")
    async def participants(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = giveaways.get(self.message_id)
        if giveaway:
            users = [f"<@{user_id}>" for user_id in giveaway["entrants"]]
            participants_list = "\n".join(users) if users else "No participants yet."
            await interaction.response.send_message(f"**Participants:**\n{participants_list}", ephemeral=True)

@tree.command(name="giveaway", description="Create a giveaway")
@app_commands.describe(channel="Channel to send the giveaway",
                       duration="Duration (e.g., 10m, 2h, 1d)",
                       prize="Giveaway prize",
                       winners="Number of winners",
                       claim_time="Claim time (e.g., 10m, 1h)")
async def giveaway(interaction: discord.Interaction, channel: discord.TextChannel, duration: str, prize: str, winners: int, claim_time: str):
    await interaction.response.send_message("Creating giveaway...", ephemeral=True)

    def parse_duration(duration_str):
        unit = duration_str[-1]
        amount = int(duration_str[:-1])
        if unit == 's':
            return timedelta(seconds=amount)
        elif unit == 'm':
            return timedelta(minutes=amount)
        elif unit == 'h':
            return timedelta(hours=amount)
        elif unit == 'd':
            return timedelta(days=amount)

    duration_delta = parse_duration(duration)
    claim_delta = parse_duration(claim_time)
    end_time = datetime.utcnow() + duration_delta

    embed = discord.Embed(
        title=f"🎉 **{prize} Giveaway!**",
        description="",
        color=discord.Color.purple()
    )
    embed.add_field(name="Hosted by", value=interaction.user.mention, inline=False)
    embed.add_field(name="Winners", value=str(winners), inline=False)
    embed.add_field(name="Participants", value="0", inline=False)
    embed.add_field(name="Ends at", value=discord.utils.format_dt(end_time, style='F'), inline=False)
    embed.set_footer(text="Click the button below to enter!")

    message = await channel.send(embed=embed, view=GiveawayView(None))
    giveaways[message.id] = {
        "entrants": [],
        "end_time": end_time,
        "channel": channel,
        "message": message,
        "prize": prize,
        "winners": winners,
        "host": interaction.user,
        "claim_delta": claim_delta
    }

    view = GiveawayView(message.id)
    await message.edit(embed=embed, view=view)

    async def update_panel():
        while datetime.utcnow() < end_time:
            embed.set_field_at(2, name="Participants", value=str(len(giveaways[message.id]["entrants"])), inline=False)
            await message.edit(embed=embed, view=view)
            await asyncio.sleep(5)
        await finalize_giveaway(message.id)

    bot.loop.create_task(update_panel())

async def finalize_giveaway(message_id):
    giveaway = giveaways.get(message_id)
    if not giveaway:
        return

    entrants = giveaway["entrants"]
    winners_count = giveaway["winners"]
    channel = giveaway["channel"]
    prize = giveaway["prize"]
    host = giveaway["host"]
    claim_time = giveaway["claim_delta"]
    message = giveaway["message"]

    if not entrants:
        await channel.send("No valid entries, no winners can be chosen.")
        return

    selected_winners = []
    while len(selected_winners) < winners_count and entrants:
        winner = entrants.pop(0)
        selected_winners.append(winner)

    winner_mentions = ", ".join(f"<@{uid}>" for uid in selected_winners)

    new_embed = message.embeds[0]
    new_embed.clear_fields()
    new_embed.add_field(name="Hosted by", value=host.mention, inline=False)
    new_embed.add_field(name="Winners", value=winner_mentions, inline=False)
    new_embed.add_field(name="Participants", value=str(len(giveaway["entrants"]) + len(selected_winners)), inline=False)
    new_embed.add_field(name="Ended at", value=discord.utils.format_dt(datetime.utcnow(), style='F'), inline=False)
    new_embed.set_footer(text="The giveaway has ended.")

    await message.edit(embed=new_embed, view=None)
    await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{prize}**!\n"
                       f"🎟️ Make a ticket in support with the reason giveaway claim before <t:{int((datetime.utcnow() + claim_time).timestamp())}:F> or the giveaway will be rerolled.")

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Bot ready: {bot.user}")

bot.run(TOKEN)
