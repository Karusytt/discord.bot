import os
import random
import asyncio
import time
import json
import threading
from dotenv import load_dotenv

import discord
from discord.ext import tasks, commands
from fastapi import FastAPI
import uvicorn

# ----- Load Environment Variables -----
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
GUILD_ID = int(os.getenv("GUILD_ID", 0))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", 2 * 60 * 60))  # 2 hours default

if not TOKEN or CHANNEL_ID == 0 or GUILD_ID == 0:
    print("❌ ERROR: Missing environment variables (DISCORD_TOKEN / CHANNEL_ID / GUILD_ID)")
    exit(1)

# ----- FastAPI Web Server -----
app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Bot is running!"}

def run_webserver():
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)), log_level="info")

# ----- Discord Setup -----
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ----- Role + Airline Config -----
ROLE_NAMES = {
    "Lufthansa": "Lufthansa Pilot",
    "TAP": "TAP AirPortugal Pilot",
    "EasyJet": "EasyJet Pilot",
    "Ryanair": "Ryanair Pilot"
}

AIRLINE_COLORS = {
    "Lufthansa": discord.Color.blue(),
    "TAP": discord.Color.green(),
    "EasyJet": discord.Color.red(),
    "Ryanair": discord.Color.yellow()
}

AIRCRAFTS = {
    "Lufthansa": {"short": ["A319", "A320", "A321"], "long": ["A330", "A340", "A350", "B747", "B787"]},
    "TAP": {"short": ["A319", "A320"], "long": ["A330", "A321LR"]},
    "EasyJet": {"short": ["A319", "A320", "A321neo"], "long": []},
    "Ryanair": {"short": ["B737-800", "B737 MAX 8-200"], "long": []}
}

# Phonetic letters for callsign suffixes
PHONETIC_LETTERS = list("ABCDEFGHJKLMNPQRSTUVWXYZ")  # exclude I/O

def maybe_add_phonetic_suffix(callsign):
    """Randomly add 1-2 phonetic letters to a callsign."""
    if random.random() < 0.3:  # 30% chance
        letters = "".join(random.choices(PHONETIC_LETTERS, k=random.choice([1,2])))
        return callsign + letters
    return callsign

# ----- Contracts -----
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

    # Ryanair
    {"airline": "Ryanair", "callsign": "RYR1234", "route": "Dublin (EIDW) ➡️ London Stansted (EGSS)", "duration": "1h15m"},
    {"airline": "Ryanair", "callsign": "RYR2456", "route": "London Stansted (EGSS) ➡️ Barcelona (LEBL)", "duration": "2h10m"},
    {"airline": "Ryanair", "callsign": "RYR3310", "route": "Dublin (EIDW) ➡️ Amsterdam (EHAM)", "duration": "1h55m"},
    {"airline": "Ryanair", "callsign": "RYR4112", "route": "Manchester (EGCC) ➡️ Madrid (LEMD)", "duration": "2h30m"},
    {"airline": "Ryanair", "callsign": "RYR4758", "route": "Dublin (EIDW) ➡️ Milan Bergamo (LIME)", "duration": "2h10m"},
    {"airline": "Ryanair", "callsign": "RYR5230", "route": "Berlin Brandenburg (EDDB) ➡️ Rome Fiumicino (LIRF)", "duration": "2h05m"},
    {"airline": "Ryanair", "callsign": "RYR6104", "route": "Lisbon (LPPT) ➡️ Brussels Charleroi (EBCI)", "duration": "2h50m"},
    {"airline": "Ryanair", "callsign": "RYR7452", "route": "Vienna (LOWW) ➡️ Athens (LGAV)", "duration": "2h15m"},
    {"airline": "Ryanair", "callsign": "RYR8316", "route": "Madrid (LEMD) ➡️ Dublin (EIDW)", "duration": "2h20m"},
    {"airline": "Ryanair", "callsign": "RYR9022", "route": "Stockholm Arlanda (ESSA) ➡️ Copenhagen (EKCH)", "duration": "1h05m"},
    {"airline": "Ryanair", "callsign": "RYR1008", "route": "Munich (EDDM) ➡️ Malta (LMML)", "duration": "2h25m"},
    {"airline": "Ryanair", "callsign": "RYR1190", "route": "Dublin (EIDW) ➡️ Frankfurt (EDDF)", "duration": "1h50m"},
    {"airline": "Ryanair", "callsign": "RYR1456", "route": "Edinburgh (EGPH) ➡️ London Luton (EGGW)", "duration": "1h20m"},
    {"airline": "Ryanair", "callsign": "RYR2102", "route": "Naples (LIRN) ➡️ Barcelona (LEBL)", "duration": "1h40m"},
    {"airline": "Ryanair", "callsign": "RYR2788", "route": "Warsaw Modlin (EPMO) ➡️ Dublin (EIDW)", "duration": "2h55m"},
]

# ----- Persistent Data -----
locked_contracts = {}
user_cooldowns = {}
last_sent_contract = None

LOGS_DIR = "data"
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, "pilot_logs.json")

def load_logs():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except:
            print("⚠️ Could not read pilot_logs.json, starting fresh.")
    return {}

def save_logs():
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(pilot_logs, f, indent=4)
    except Exception as e:
        print(f"Error saving logs: {e}")

pilot_logs = load_logs()

# ----- Helpers -----
def assign_aircraft(contract):
    dur = contract["duration"]
    hours = minutes = 0
    if "h" in dur:
        parts = dur.split("h")
        hours = int(parts[0])
        if "m" in parts[1]:
            minutes = int(parts[1].replace("m", ""))
    else:
        minutes = int(dur.replace("m", ""))
    total_minutes = hours * 60 + minutes
    airline = contract["airline"]
    if total_minutes <= 180:
        return random.choice(AIRCRAFTS[airline]["short"])
    else:
        return random.choice(AIRCRAFTS[airline]["long"] or AIRCRAFTS[airline]["short"])

def build_contract_embed(contract, status="available", user=None):
    airline = contract["airline"]
    color = AIRLINE_COLORS.get(airline, discord.Color.blue())
    aircraft = contract.get("assigned_aircraft") or assign_aircraft(contract)
    callsign = contract.get("display_callsign", contract["callsign"])

    if status == "expired":
        title = "❌ Contract Expired"
        color = discord.Color.dark_grey()
        footer = "This contract has expired and is no longer available."
    elif status == "accepted":
        title = f"✅ Contract Accepted by {user.display_name}"
        color = discord.Color.green()
        footer = "This contract has been taken."
    else:
        title = "✈️ New Contract Available!"
        footer = "Click the button to accept! Contract expires soon."

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🏢 Airline", value=airline, inline=True)
    embed.add_field(name="🔢 Callsign", value=f"`{callsign}`", inline=True)
    embed.add_field(name="🗺️ Route", value=contract["route"], inline=False)
    embed.add_field(name="⏱️ Duration", value=f"`{contract['duration']}`", inline=True)
    embed.add_field(name="🛫 Aircraft", value=aircraft, inline=True)
    embed.set_footer(text=footer)
    return embed

# ----- Button -----
class AcceptButton(discord.ui.View):
    def __init__(self, contract):
        super().__init__(timeout=None)
        self.contract = contract
        self.locked = False

    @discord.ui.button(label="Accept Contract ✅", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if self.locked:
            await interaction.response.send_message("❌ This contract is already taken!", ephemeral=True)
            return

        role_name = ROLE_NAMES.get(self.contract["airline"])
        if role_name not in [r.name for r in user.roles]:
            await interaction.response.send_message(f"❌ You are not a {self.contract['airline']} pilot!", ephemeral=True)
            return

        now = time.time()
        if user.id in user_cooldowns and now - user_cooldowns[user.id] < COOLDOWN_SECONDS:
            remaining = int((COOLDOWN_SECONDS - (now - user_cooldowns[user.id])) / 60)
            await interaction.response.send_message(f"⏳ You are on cooldown. Wait {remaining} more minutes.", ephemeral=True)
            return

        self.locked = True
        user_cooldowns[user.id] = now
        locked_contracts[interaction.message.id]["accepted_by"] = user.id

        user_id = str(user.id)
        entry = f"{self.contract['callsign']} - {self.contract['airline']} - {self.contract['route']} ({self.contract['duration']})"
        pilot_logs.setdefault(user_id, []).append(entry)
        save_logs()

        embed = build_contract_embed(self.contract, "accepted", user)
        await interaction.message.edit(embed=embed, view=None)

        aircraft = self.contract.get("assigned_aircraft") or assign_aircraft(self.contract)
        embed_dm = discord.Embed(
            title=f"✈️ Contract Accepted: {self.contract['callsign']}",
            color=discord.Color.green()
        )
        embed_dm.add_field(name="🏢 Airline", value=self.contract["airline"], inline=False)
        embed_dm.add_field(name="🔢 Callsign", value=self.contract["display_callsign"], inline=True)
        embed_dm.add_field(name="🗺️ Route", value=self.contract["route"], inline=False)
        embed_dm.add_field(name="⏱️ Duration", value=self.contract["duration"], inline=True)
        embed_dm.add_field(name="🛫 Aircraft", value=aircraft, inline=True)
        embed_dm.add_field(
            name="📋 SimBrief",
            value="[SimBrief Dispatch](https://dispatch.simbrief.com/options/new)",
            inline=False
        )

        try:
            await user.send(embed=embed_dm)
        except:
            await interaction.response.send_message("⚠️ Could not DM you the contract!", ephemeral=True)
            return

        await interaction.response.send_message("✅ You have accepted this contract!", ephemeral=True)

# ----- Expiration Handler (Testing: 10 seconds) -----
async def handle_contract_expiration(message_id, channel):
    await asyncio.sleep(10)  # expire after 10 seconds for testing
    data = locked_contracts.get(message_id)
    if not data:
        return

    if data["accepted_by"] is None:
        try:
            message = await channel.fetch_message(message_id)
            expired_embed = build_contract_embed(data["contract"], "expired")
            await message.edit(embed=expired_embed, view=None)
            print(f"Contract {message_id} expired.")
        except Exception as e:
            print(f"Error expiring contract: {e}")

    await asyncio.sleep(5)  # delete 5 seconds later (total 15s for testing)
    try:
        message = await channel.fetch_message(message_id)
        await message.delete()
        locked_contracts.pop(message_id, None)
        print(f"Contract {message_id} deleted after testing.")
    except Exception as e:
        print(f"Error deleting contract: {e}")

# ----- Contract Sending -----
async def send_contract_to_channel(channel, contract):
    contract["assigned_aircraft"] = assign_aircraft(contract)
    contract["display_callsign"] = maybe_add_phonetic_suffix(contract["callsign"])
    
    guild = channel.guild
    role = discord.utils.get(guild.roles, name=ROLE_NAMES.get(contract["airline"]))
    role_mention = role.mention if role else ""

    embed = build_contract_embed(contract)
    msg = await channel.send(content=role_mention, embed=embed, view=AcceptButton(contract))
    locked_contracts[msg.id] = {"contract": contract, "accepted_by": None}
    asyncio.create_task(handle_contract_expiration(msg.id, channel))

# ----- Background Loop (Testing: 10 seconds) -----
@tasks.loop(seconds=1)
async def send_contract_loop():
    global last_sent_contract
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    available_contracts = [c for c in contracts if c != last_sent_contract]
    contract = random.choice(available_contracts or contracts)
    last_sent_contract = contract
    await send_contract_to_channel(channel, contract)
    await asyncio.sleep(10)  # 10 seconds for testing

# ----- Logbook Command -----
@bot.tree.command(name="logbook", description="Show your pilot logbook", guild=discord.Object(id=GUILD_ID))
async def logbook(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    logs = pilot_logs.get(user_id, [])
    if not logs:
        await interaction.response.send_message("🪶 You have no recorded flights yet.", ephemeral=True)
        return

    log_text = "\n".join(logs[-20:])
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
    print(f"✅ Bot is online as {bot.user}!")

    if not send_contract_loop.is_running():
        send_contract_loop.start()

    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print("✅ Commands synced successfully!")

# ----- Run Bot + Webserver -----
if __name__ == "__main__":
    threading.Thread(target=run_webserver, daemon=True).start()
    bot.run(TOKEN)
