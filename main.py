import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = discord.Object(id=int(os.getenv("GUILD_ID")))

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

giveaways = {}

@bot.event
async def on_ready():
    await tree.sync(guild=GUILD_ID)
    print(f"Bot connected as {bot.user}")

def format_time_remaining(end_time):
    now = datetime.utcnow()
    delta = end_time - now
    months, remainder = divmod(delta.days, 30)
    days = remainder
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"**Ends in:** {months}m, {days}d, {hours}h, {minutes}m, {seconds}s"

@tree.command(name="giveaway", description="Start a giveaway", guild=GUILD_ID)
@app_commands.describe(
    channel="Channel to host the giveaway",
    prize="Prize name",
    duration="Duration in minutes",
    winners="Number of winners",
    extra_role="Role that grants extra entries (mention)",
    winner_user="Manually select winner (optional)"
)
async def giveaway(interaction: discord.Interaction, channel: discord.TextChannel, prize: str, duration: int, winners: int, extra_role: discord.Role = None, winner_user: discord.Member = None):
    end_time = datetime.utcnow() + timedelta(minutes=duration)
    participants = set()
    extra_entries = {}

    class GiveawayView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.message = None

        @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success, custom_id="enter")
        async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
            user_id = interaction.user.id
            if user_id in participants:
                await interaction.response.send_message("❌ You have already entered this giveaway. The entry has been saved.", ephemeral=True)
                return

            participants.add(user_id)

            if extra_role and extra_role in interaction.user.roles:
                extra_entries[user_id] = 1

            await update_embed()
            await interaction.response.send_message("✅ You have successfully entered the giveaway!", ephemeral=True)

        @discord.ui.button(label="🚪 Exit Giveaway", style=discord.ButtonStyle.danger, custom_id="exit")
        async def exit(self, interaction: discord.Interaction, button: discord.ui.Button):
            user_id = interaction.user.id
            if user_id in participants:
                participants.remove(user_id)
                if user_id in extra_entries:
                    del extra_entries[user_id]
                await update_embed()
                await interaction.response.send_message("✅ You have successfully left the giveaway.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ You are not in this giveaway.", ephemeral=True)

        @discord.ui.button(label="🧍 Participants", style=discord.ButtonStyle.secondary, custom_id="participants")
        async def show_participants(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not participants:
                await interaction.response.send_message("❌ No participants yet.", ephemeral=True)
                return

            participants_list = [f"{idx+1}. <@{uid}>" for idx, uid in enumerate(participants)]
            await interaction.response.send_message(
                f"These are the current participants for the **{prize}** giveaway:\n\n" + "\n".join(participants_list),
                ephemeral=True
            )

    async def update_embed():
        remaining_time = format_time_remaining(end_time)
        embed = discord.Embed(
            title=f"🎉 **{prize} Giveaway!**",
            color=discord.Color.purple()
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1371213195674390558/1372631772600467556/IMG_9097.png")
        embed.add_field(name="Hosted by", value=interaction.user.mention, inline=False)
        embed.add_field(name="Winners", value=f"{winners}", inline=False)
        embed.add_field(name="Participants", value=f"**{len(participants)}**", inline=False)
        embed.add_field(name="Ends at", value=remaining_time, inline=False)
        embed.set_footer(text="Click the button below to enter!")

        if view.message:
            await view.message.edit(embed=embed, view=view)

    view = GiveawayView()
    embed = discord.Embed(
        title=f"🎉 **{prize} Giveaway!**",
        color=discord.Color.purple()
    )
    embed.set_image(url="https://cdn.discordapp.com/attachments/1371213195674390558/1372631772600467556/IMG_9097.png")
    embed.add_field(name="Hosted by", value=interaction.user.mention, inline=False)
    embed.add_field(name="Winners", value=f"{winners}", inline=False)
    embed.add_field(name="Participants", value=f"**0**", inline=False)
    embed.add_field(name="Ends at", value=format_time_remaining(end_time), inline=False)
    embed.set_footer(text="Click the button below to enter!")

    message = await channel.send(embed=embed, view=view)
    view.message = message

    giveaways[message.id] = {
        "end_time": end_time,
        "participants": participants,
        "extra_entries": extra_entries,
        "winners": winners,
        "winner_user": winner_user,
        "prize": prize,
        "message": message,
        "view": view
    }

    await interaction.response.send_message(f"Giveaway started in {channel.mention}", ephemeral=True)

    @tasks.loop(seconds=5)
    async def countdown():
        if datetime.utcnow() >= end_time:
            await end_giveaway()
            countdown.cancel()
        else:
            await update_embed()

    countdown.start()

    async def end_giveaway():
        all_entries = []
        for uid in participants:
            all_entries.append(uid)
            if uid in extra_entries:
                all_entries.append(uid)

        if not all_entries:
            await channel.send(f"No valid entries for the **{prize}** giveaway.")
            return

        if winner_user:
            winners_list = [winner_user]
        else:
            winners_list = random.sample(list(set(all_entries)), min(winners, len(all_entries)))
            winners_list = [await bot.fetch_user(w) for w in winners_list]

        await message.edit(view=None)
        await channel.send(
            f"🎉 **GIVEAWAY ENDED!**\n**Prize:** {prize}\n**Winners:** {', '.join(w.mention for w in winners_list)}\n🎟️ Make a ticket in support with the reason giveaway claim before 1 hour or the giveaway will be rerolled."
        )

bot.run(TOKEN)
