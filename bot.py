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
    "Ryanair": "Ryanair Pilot",
    "Emirates": "Emirates Pilot",
    "Eurowings": "Eurowings Pilot",
    "KLM": "KLM Pilot",
    "Condor": "Condor Pilot"
}

AIRLINE_COLORS = {
    "Lufthansa": discord.Color.blue(),
    "TAP": discord.Color.green(),
    "EasyJet": discord.Color.red(),
    "Ryanair": discord.Color.yellow(),
    "Emirates": discord.Color.purple(),
    "Eurowings": discord.Color.from_str("#8F174F"),
    "KLM": discord.Color.from_str("#0052A1"),
    "Condor": discord.Color.from_str("#FFCC00")
}

AIRCRAFTS = {
    "Lufthansa": {"short": ["A319", "A320", "A321"], "long": ["A330", "A340", "A350", "B747", "B787"]},
    "TAP": {"short": ["A319", "A320"], "long": ["A330", "A321LR"]},
    "EasyJet": {"short": ["A319", "A320", "A321neo"], "long": []},
    "Ryanair": {"short": ["B737-800", "B737 MAX 8-200"], "long": []},
    "Emirates": {"short": [], "long": ["B777-300ER", "A380", "B787-9", "A350-900"]},
    "Eurowings": {"short": ["A319", "A320", "A321"], "long": []},
    "KLM": {"short": ["E175", "E190", "E195", "B737-700", "B737-800", "B737-900"], "long": ["B777-200", "B777-300", "B787-9", "B787-10", "A330-200", "A330-300"]},
    "Condor": {"short": ["A320", "A321"], "long": ["A330-900", "B767-300", "B757-300"]}
}

PHONETIC_LETTERS = list("ABCDEFGHJKLMNPQRSTUVWXYZ")  # exclude I/O

def maybe_add_phonetic_suffix(callsign):
    """Randomly add 1-2 phonetic letters to a callsign (30% chance)."""
    if random.random() < 0.3:
        letters = "".join(random.choices(PHONETIC_LETTERS, k=random.choice([1, 2])))
        return callsign + letters
    return callsign

# ----- Contracts -----
contracts = [
    # Your contracts here (I'll skip them as requested)
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
        try:
            hours = int(parts[0])
        except:
            hours = 0
        if "m" in parts[1]:
            try:
                minutes = int(parts[1].replace("m", ""))
            except:
                minutes = 0
    else:
        try:
            minutes = int(dur.replace("m", ""))
        except:
            minutes = 0
    total_minutes = hours * 60 + minutes
    airline = contract["airline"]
    shorts = AIRCRAFTS.get(airline, {}).get("short", [])
    longs = AIRCRAFTS.get(airline, {}).get("long", [])

    if total_minutes <= 180:
        # prefer short-haul fleet, fallback to long if none
        return random.choice(shorts) if shorts else (random.choice(longs) if longs else "Unknown")
    else:
        # prefer long-haul fleet, fallback to short if none
        return random.choice(longs) if longs else (random.choice(shorts) if shorts else "Unknown")

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
        footer = "Click the button to accept! Contract expires in 40 minutes."

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

        # ----- Enhanced DM with pre-filled SimBrief -----
        # Extract airport codes from the route
        route_parts = self.contract["route"].split(" ➡️ ")
        if len(route_parts) == 2:
            # Extract departure airport code (text between last space and closing parenthesis)
            dep_match = route_parts[0].split("(")[-1].replace(")", "")
            # Extract arrival airport code (text between last space and closing parenthesis)
            arr_match = route_parts[1].split("(")[-1].replace(")", "")
            
            # Define airline codes mapping
            airline_codes = {
                "Lufthansa": "DLH",
                "TAP": "TAP", 
                "EasyJet": "EZY",
                "Ryanair": "RYR",
                "Emirates": "UAE",
                "Eurowings": "EWG",
                "KLM": "KLM",
                "Condor": "CFG"
            }
            
            airline_code = airline_codes.get(self.contract["airline"], "")
            
            # Extract flight number (remove airline code from callsign)
            flight_number = self.contract["callsign"].replace(airline_code, "").strip()
            
            # Create the pre-filled SimBrief URL
            simbrief_url = f"https://dispatch.simbrief.com/options/custom?orig={dep_match}&dest={arr_match}&airline={airline_code}&fltnum={flight_number}"
        else:
            # Fallback to the generic link if route format is unexpected
            simbrief_url = "https://dispatch.simbrief.com/options/new"

        aircraft = self.contract.get("assigned_aircraft") or assign_aircraft(self.contract)
        embed_dm = discord.Embed(
            title=f"✈️ Contract Accepted: **{self.contract['callsign']}**",
            color=discord.Color.green()
        )
        embed_dm.add_field(name="🏢 Airline", value=f"**{self.contract['airline']}**", inline=False)
        embed_dm.add_field(name="🔢 Callsign", value=f"**{self.contract.get('display_callsign', self.contract['callsign'])}**", inline=True)
        embed_dm.add_field(name="🗺️ Route", value=f"**{self.contract['route']}**", inline=False)
        embed_dm.add_field(name="⏱️ Duration", value=f"**{self.contract['duration']}**", inline=True)
        embed_dm.add_field(name="🛫 Aircraft", value=f"**{aircraft}**", inline=True)
        embed_dm.add_field(
            name="📋 SimBrief",
            value=f"Create a flight plan here: [SimBrief Dispatch]({simbrief_url})\n"
                  "*Route and airline are pre-filled!*\n"
                  "If you don't have a SimBrief account, create one to use the link!",
            inline=False
        )

        try:
            await user.send(embed=embed_dm)
        except:
            await interaction.response.send_message("⚠️ Could not DM you the contract!", ephemeral=True)
            return

        await interaction.response.send_message("✅ You have accepted this contract!", ephemeral=True)

# ----- Expiration Handler -----
async def handle_contract_expiration(message_id, channel):
    await asyncio.sleep(40 * 60)  # Expire after 40 mins
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

    await asyncio.sleep(20 * 60)  # Delete 20 min later (total 1 hour)
    try:
        message = await channel.fetch_message(message_id)
        await message.delete()
        locked_contracts.pop(message_id, None)
        print(f"Contract {message_id} deleted after 1 hour.")
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

# ----- Background Loop (1-5 min) -----
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
    await asyncio.sleep(random.randint(60, 300))  # 1-5 minutes

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
