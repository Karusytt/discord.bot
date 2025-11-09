import os
import random
import asyncio
import time
import json
from dotenv import load_dotenv

import discord
from discord.ext import tasks, commands
from fastapi import FastAPI
import uvicorn

# ----- Load environment variables -----
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
GUILD_ID = int(os.getenv("GUILD_ID", 0))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", 2*60*60))

if not TOKEN or CHANNEL_ID == 0 or GUILD_ID == 0:
    print("ERROR: Missing environment variables!")
    exit(1)

# ----- FastAPI server -----
app = FastAPI()
@app.get("/")
def read_root():
    return {"status": "Bot is running!"}

# ----- Discord Bot Setup -----
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ----- Data -----
ROLE_NAMES = {
    "Lufthansa": "Lufthansa Pilot",
    "TAP": "TAP AirPortugal Pilot",
    "EasyJet": "EasyJet Pilot"
}

AIRLINE_COLORS = {
    "Lufthansa": discord.Color.blue(),
    "TAP": discord.Color.green(),
    "EasyJet": discord.Color.red()
}

AIRCRAFTS = {
    "Lufthansa": {"short": ["A319", "A320", "A321"], "long": ["A330", "A340", "A350", "B747", "B787"]},
    "TAP": {"short": ["A319", "A320"], "long": ["A330", "A321LR"]},
    "EasyJet": {"short": ["A319", "A320", "A321neo"], "long": []}
}

# ----- Full Contracts -----
contracts = [
    # Lufthansa
    {"airline": "Lufthansa", "callsign": "DLH145", "route": "Frankfurt (EDDF) ➡️ New York (KJFK)", "duration": "8h15m"},
    {"airline": "Lufthansa", "callsign": "DLH302", "route": "Munich (EDDM) ➡️ Los Angeles (KLAX)", "duration": "11h30m"},
    {"airline": "Lufthansa", "callsign": "DLH402", "route": "Munich (EDDM) ➡️ Vienna (LOWW)", "duration": "1h10m"},
    {"airline": "Lufthansa", "callsign": "DLH456", "route": "Frankfurt (EDDF) ➡️ Singapore (WSSS)", "duration": "12h30m"},
    {"airline": "Lufthansa", "callsign": "DLH716", "route": "Frankfurt (EDDF) ➡️ Tokyo (RJTT)", "duration": "11h30m"},
    {"airline": "Lufthansa", "callsign": "DLH506", "route": "Munich (EDDM) ➡️ Dubai (OMDB)", "duration": "6h"},
    {"airline": "Lufthansa", "callsign": "DLH902", "route": "Frankfurt (EDDF) ➡️ London (EGLL)", "duration": "1h30m"},
    {"airline": "Lufthansa", "callsign": "DLH234", "route": "Munich (EDDM) ➡️ Paris (LFPG)", "duration": "1h35m"},
    {"airline": "Lufthansa", "callsign": "DLH1358", "route": "Frankfurt (EDDF) ➡️ Barcelona (LEBL)", "duration": "2h10m"},
    {"airline": "Lufthansa", "callsign": "DLH678", "route": "Frankfurt (EDDF) ➡️ Chicago (KORD)", "duration": "9h"},
    {"airline": "Lufthansa", "callsign": "DLH722", "route": "Munich (EDDM) ➡️ Beijing (ZBAD)", "duration": "10h"},
    {"airline": "Lufthansa", "callsign": "DLH1524", "route": "Frankfurt (EDDF) ➡️ Rome (LIRF)", "duration": "1h50m"},
    {"airline": "Lufthansa", "callsign": "DLH332", "route": "Munich (EDDM) ➡️ Miami (KMIA)", "duration": "10h30m"},
    {"airline": "Lufthansa", "callsign": "DLH890", "route": "Frankfurt (EDDF) ➡️ Bangkok (VTBS)", "duration": "10h45m"},
    {"airline": "Lufthansa", "callsign": "DLH1166", "route": "Munich (EDDM) ➡️ Copenhagen (EKCH)", "duration": "1h30m"},

    # TAP
    {"airline": "TAP", "callsign": "TAP109", "route": "Lisbon (LPPT) ➡️ Sao Paulo (SBGR)", "duration": "10h15m"},
    {"airline": "TAP", "callsign": "TAP222", "route": "Lisbon (LPPT) ➡️ Boston (KBOS)", "duration": "7h"},
    {"airline": "TAP", "callsign": "TAP412", "route": "Lisbon (LPPT) ➡️ Porto (LPPR)", "duration": "55m"},
    {"airline": "TAP", "callsign": "TAP115", "route": "Lisbon (LPPT) ➡️ Rio de Janeiro (SBGL)", "duration": "9h45m"},
    {"airline": "TAP", "callsign": "TAP208", "route": "Lisbon (LPPT) ➡️ New York (KEWR)", "duration": "7h30m"},
    {"airline": "TAP", "callsign": "TAP931", "route": "Lisbon (LPPT) ➡️ London (EGLL)", "duration": "2h40m"},
    {"airline": "TAP", "callsign": "TAP558", "route": "Lisbon (LPPT) ➡️ Paris (LFPG)", "duration": "2h20m"},
    {"airline": "TAP", "callsign": "TAP1692", "route": "Porto (LPPR) ➡️ Amsterdam (EHAM)", "duration": "2h30m"},
    {"airline": "TAP", "callsign": "TAP501", "route": "Lisbon (LPPT) ➡️ Luanda (FNLU)", "duration": "7h15m"},
    {"airline": "TAP", "callsign": "TAP1446", "route": "Lisbon (LPPT) ➡️ Brussels (EBBR)", "duration": "2h35m"},
    {"airline": "TAP", "callsign": "TAP90", "route": "Lisbon (LPPT) ➡️ Miami (KMIA)", "duration": "9h30m"},
    {"airline": "TAP", "callsign": "TAP1936", "route": "Lisbon (LPPT) ➡️ Geneva (LSGG)", "duration": "2h25m"},
    {"airline": "TAP", "callsign": "TAP259", "route": "Lisbon (LPPT) ➡️ Toronto (CYYZ)", "duration": "7h45m"},
    {"airline": "TAP", "callsign": "TAP1520", "route": "Porto (LPPR) ➡️ Frankfurt (EDDF)", "duration": "2h40m"},
    {"airline": "TAP", "callsign": "TAP562", "route": "Lisbon (LPPT) ➡️ Praia (GVNP)", "duration": "4h"},

    # EasyJet
    {"airline": "EasyJet", "callsign": "EZY801", "route": "London Gatwick (EGKK) ➡️ Amsterdam (EHAM)", "duration": "1h10m"},
    {"airline": "EasyJet", "callsign": "EZY215", "route": "Berlin (EDDB) ➡️ Barcelona (LEBL)", "duration": "2h35m"},
    {"airline": "EasyJet", "callsign": "EZY711", "route": "London Gatwick (EGKK) ➡️ Marrakech (GMMX)", "duration": "3h30m"},
    {"airline": "EasyJet", "callsign": "EZY115", "route": "Amsterdam (EHAM) ➡️ Lisbon (LPPT)", "duration": "2h50m"},
    {"airline": "EasyJet", "callsign": "EZY503", "route": "Manchester (EGCC) ➡️ Geneva (LSGG)", "duration": "1h55m"},
    {"airline": "EasyJet", "callsign": "EZY402", "route": "Bristol (EGGD) ➡️ Rome (LIRF)", "duration": "2h45m"},
    {"airline": "EasyJet", "callsign": "EZY821", "route": "London Luton (EGGW) ➡️ Budapest (LHBP)", "duration": "2h30m"},
    {"airline": "EasyJet", "callsign": "EZY332", "route": "Paris Orly (LFPO) ➡️ Nice (LFMN)", "duration": "1h25m"},
    {"airline": "EasyJet", "callsign": "EZY925", "route": "London Gatwick (EGKK) ➡️ Berlin (EDDB)", "duration": "1h55m"},
    {"airline": "EasyJet", "callsign": "EZY2105", "route": "Milan Malpensa (LIMC) ➡️ Naples (LIRN)", "duration": "1h25m"},
    {"airline": "EasyJet", "callsign": "EZY704", "route": "Edinburgh (EGPH) ➡️ Geneva (LSGG)", "duration": "2h5m"},
    {"airline": "EasyJet", "callsign": "EZY8403", "route": "London Luton (EGGW) ➡️ Amsterdam (EHAM)", "duration": "1h15m"},
    {"airline": "EasyJet", "callsign": "EZY607", "route": "Lisbon (LPPT) ➡️ Basel (LFSB)", "duration": "2h30m"},
    {"airline": "EasyJet", "callsign": "EZY908", "route": "Belfast (EGAA) ➡️ Faro (LPFR)", "duration": "3h10m"},
    {"airline": "EasyJet", "callsign": "EZY452", "route": "London Gatwick (EGKK) ➡️ Zurich (LSZH)", "duration": "1h40m"},
]

# ----- Variables -----
locked_contracts = {}
user_cooldowns = {}
last_sent_contract = None
LOG_FILE = "pilot_logs.json"

# ----- Persistent Pilot Logs -----
def load_logs():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except:
            print("Warning: Could not read pilot_logs.json, starting fresh.")
    return {}

def save_logs():
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(pilot_logs, f, indent=4)
    except Exception as e:
        print(f"Error saving logs: {e}")

pilot_logs = load_logs()

# ----- Helper Functions -----
def assign_aircraft(contract):
    dur = contract["duration"]
    if "h" in dur:
        parts = dur.split("h")
        hours = int(parts[0])
        minutes = int(parts[1].replace("m","")) if "m" in parts[1] else 0
    else:
        hours = 0
        minutes = int(dur.replace("m",""))
    total_minutes = hours*60 + minutes
    airline = contract["airline"]
    if total_minutes <= 180:
        return random.choice(AIRCRAFTS[airline]["short"])
    else:
        return random.choice(AIRCRAFTS[airline]["long"]) if AIRCRAFTS[airline]["long"] else random.choice(AIRCRAFTS[airline]["short"])

def build_contract_embed(contract):
    airline = contract["airline"]
    color = AIRLINE_COLORS.get(airline, discord.Color.blue())
    aircraft = assign_aircraft(contract)
    embed = discord.Embed(
        title="✈️ New Contract Available!",
        color=color
    )
    embed.add_field(name="🏢 Airline", value=airline, inline=True)
    embed.add_field(name="🆔 Callsign", value=f"`{contract['callsign']}`", inline=True)
    embed.add_field(name="🗺️ Route", value=contract['route'], inline=False)
    embed.add_field(name="⏱️ Duration", value=f"`{contract['duration']}`", inline=True)
    embed.add_field(name="🛫 Aircraft", value=aircraft, inline=True)
    embed.set_footer(text="Click the button to accept! Contract expires in 40 minutes.")
    return embed

# ----- Accept Button -----
class AcceptButton(discord.ui.View):
    def __init__(self, contract, message):
        super().__init__(timeout=None)
        self.contract = contract
        self.locked = False
        self.message = message

    @discord.ui.button(label="Accept Contract ✅", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if self.locked:
            await interaction.response.send_message("❌ This contract is already taken!", ephemeral=True)
            return

        allowed_role_name = ROLE_NAMES.get(self.contract["airline"])
        user_roles = [r.name for r in user.roles]
        if allowed_role_name not in user_roles:
            await interaction.response.send_message(
                f"❌ You are not an {self.contract['airline']} pilot! You can only accept contracts for your airline.",
                ephemeral=True
            )
            return

        now = time.time()
        if user.id in user_cooldowns and now - user_cooldowns[user.id] < COOLDOWN_SECONDS:
            remaining = int((COOLDOWN_SECONDS - (now - user_cooldowns[user.id])) / 60)
            await interaction.response.send_message(
                f"⏳ You are on cooldown. Wait {remaining} more minutes.",
                ephemeral=True
            )
            return

        # Lock contract
        self.locked = True
        user_cooldowns[user.id] = now
        locked_contracts[self.message.id]["accepted_by"] = user.id

        # Log flight
        flight_entry = f"{self.contract['callsign']} {self.contract['route']}"
        pilot_logs.setdefault(str(user.id), []).append(flight_entry)
        save_logs()

        # Update channel embed
        embed_channel = build_contract_embed(self.contract)
        embed_channel.color = discord.Color.green()
        embed_channel.add_field(name="Accepted by", value=user.mention, inline=False)
        embed_channel.set_footer(text="Contract is taken!")
        await self.message.edit(embed=embed_channel, view=self)

        # DM user
        embed_dm = build_contract_embed(self.contract)
        embed_dm.color = discord.Color.green()
        embed_dm.add_field(name="Simbrief", value="Create a flight plan here: https://dispatch.simbrief.com/options/new", inline=False)
        embed_dm.set_footer(text="If you don't have a SimBrief account, create one to use the link!")
        try:
            await user.send(embed=embed_dm)
        except:
            await interaction.response.send_message("Could not DM you the contract!", ephemeral=True)
            return

        await interaction.response.send_message("✅ You have accepted this contract!", ephemeral=True)

# ----- Send Contract Function -----
async def send_contract_to_channel(channel, contract):
    guild = channel.guild
    role_name = ROLE_NAMES.get(contract['airline'])
    role_mention = ""
    if role_name:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            role_mention = role.mention

    embed = build_contract_embed(contract)
    message = await channel.send(content=role_mention, embed=embed)
    view = AcceptButton(contract, message)
    await message.edit(view=view)
    locked_contracts[message.id] = {"contract": contract, "accepted_by": None, "message": message}

    async def expire_and_delete(msg_id, msg):
        await asyncio.sleep(2400)
        if locked_contracts.get(msg_id) and locked_contracts[msg_id]["accepted_by"] is None:
            expire_embed = build_contract_embed(contract)
            expire_embed.color = discord.Color.red()
            expire_embed.set_footer(text="❌ This contract was not accepted in time.")
            try:
                await msg.edit(embed=expire_embed, view=None)
            except:
                pass
        await asyncio.sleep(1200)
        try:
            await msg.delete()
            locked_contracts.pop(msg_id, None)
        except:
            pass

    asyncio.create_task(expire_and_delete(message.id, message))

# ----- Contract Loop -----
@tasks.loop(seconds=1)
async def send_contract_loop():
    global last_sent_contract
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        available_contracts = [c for c in contracts if c != last_sent_contract]
        if not available_contracts:
            available_contracts = contracts
        contract = random.choice(available_contracts)
        last_sent_contract = contract
        await send_contract_to_channel(channel, contract)
    await asyncio.sleep(random.randint(60, 600))

# ----- Logbook Command -----
@bot.tree.command(name="logbook", description="Show your pilot logbook", guild=discord.Object(id=GUILD_ID))
async def logbook(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    logs = pilot_logs.get(user_id, [])
    if not logs:
        await interaction.response.send_message("You have no recorded flights yet.", ephemeral=True)
        return
    log_text = "\n".join(logs)
    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s Pilot Logbook",
        description=log_text,
        color=discord.Color.orange()
    )
    embed.set_footer(text=f"Total Flights: {len(logs)}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ----- Events -----
@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}!")
    if not send_contract_loop.is_running():
        send_contract_loop.start()
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print("Commands synced successfully!")

# ----- Run Bot & FastAPI -----
async def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)), log_level="info")
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
