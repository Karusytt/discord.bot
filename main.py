import os
import random
import asyncio
import time
import json
import threading
from dotenv import load_dotenv

import discord
from discord.ext import tasks, commands

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Log what Uvicorn is doing
logger.info("About to start Uvicorn...")

# ----- FastAPI Web Server for UptimeRobot -----
from fastapi import FastAPI
import uvicorn

# ----- Load Environment Variables -----
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
GUILD_ID = int(os.getenv("GUILD_ID", 0))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", 2 * 60 * 60))
PORT = int(os.getenv("PORT", 8080))

if not TOKEN or CHANNEL_ID == 0 or GUILD_ID == 0:
    print("❌ ERROR: Missing environment variables (DISCORD_TOKEN / CHANNEL_ID / GUILD_ID)")
    exit(1)

print("🚀 Starting Flight Dispatcher Bot...")

# ----- FastAPI App -----
app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Flight Dispatcher Bot is running!"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": time.time()}

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
    "Condor": "Condor Pilot",
    "Wizz Air": "WizzAir Pilot"
}

AIRLINE_COLORS = {
    "Lufthansa": discord.Color.blue(),
    "TAP": discord.Color.green(),
    "EasyJet": discord.Color.red(),
    "Ryanair": discord.Color.yellow(),
    "Emirates": discord.Color.purple(),
    "Eurowings": discord.Color.from_str("#8F174F"),
    "KLM": discord.Color.from_str("#0052A1"),
    "Condor": discord.Color.from_str("#FFCC00"),
    "Wizz Air": discord.Color.from_str("#DA291C")
}

AIRCRAFTS = {
    "Lufthansa": {"short": ["A319", "A320", "A321"], "long": ["A330", "A340", "A350", "B747", "B787"]},
    "TAP": {"short": ["A319", "A320"], "long": ["A330", "A321LR"]},
    "EasyJet": {"short": ["A319", "A320", "A321neo"], "long": []},
    "Ryanair": {"short": ["B737-800", "B737 MAX 8-200"], "long": []},
    "Emirates": {"short": [], "long": ["B777-300ER", "A380", "B787-9", "A350-900"]},
    "Eurowings": {"short": ["A319", "A320", "A321"], "long": []},
    "KLM": {"short": ["E175", "E190", "E195", "B737-700", "B737-800", "B737-900"], "long": ["B777-200", "B777-300", "B787-9", "B787-10", "A330-200", "A330-300"]},
    "Condor": {"short": ["A320", "A321"], "long": ["A330-900", "B767-300", "B757-300"]},
    "Wizz Air": {"short": ["A320", "A321", "A320neo", "A321neo"], "long": []}
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
    # Lufthansa (15 routes)
    {"airline": "Lufthansa", "callsign": "DLH145", "route": "Frankfurt (EDDF) ➡️ New York (KJFK)", "duration": "8h15m"},
    {"airline": "Lufthansa", "callsign": "DLH302", "route": "Munich (EDDM) ➡️ Los Angeles (KLAX)", "duration": "11h30m"},
    {"airline": "Lufthansa", "callsign": "DLH456", "route": "Frankfurt (EDDF) ➡️ Singapore (WSSS)", "duration": "12h30m"},
    {"airline": "Lufthansa", "callsign": "DLH716", "route": "Frankfurt (EDDF) ➡️ Tokyo (RJTT)", "duration": "11h30m"},
    {"airline": "Lufthansa", "callsign": "DLH506", "route": "Munich (EDDM) ➡️ Dubai (OMDB)", "duration": "6h"},
    {"airline": "Lufthansa", "callsign": "DLH332", "route": "Munich (EDDM) ➡️ Vienna (LOWW)", "duration": "1h10m"},
    {"airline": "Lufthansa", "callsign": "DLH902", "route": "Frankfurt (EDDF) ➡️ London Heathrow (EGLL)", "duration": "1h30m"},
    {"airline": "Lufthansa", "callsign": "DLH234", "route": "Munich (EDDM) ➡️ Paris (LFPG)", "duration": "1h35m"},
    {"airline": "Lufthansa", "callsign": "DLH1358", "route": "Frankfurt (EDDF) ➡️ Barcelona (LEBL)", "duration": "2h10m"},
    {"airline": "Lufthansa", "callsign": "DLH1166", "route": "Munich (EDDM) ➡️ Copenhagen (EKCH)", "duration": "1h30m"},
    {"airline": "Lufthansa", "callsign": "DLH1524", "route": "Frankfurt (EDDF) ➡️ Rome (LIRF)", "duration": "1h50m"},
    {"airline": "Lufthansa", "callsign": "DLH722", "route": "Munich (EDDM) ➡️ Zurich (LSZH)", "duration": "1h15m"},
    {"airline": "Lufthansa", "callsign": "DLH890", "route": "Frankfurt (EDDF) ➡️ Brussels (EBBR)", "duration": "1h05m"},
    {"airline": "Lufthansa", "callsign": "DLH840", "route": "Munich (EDDM) ➡️ Milan Malpensa (LIMC)", "duration": "1h20m"},
    {"airline": "Lufthansa", "callsign": "DLH768", "route": "Frankfurt (EDDF) ➡️ Amsterdam (EHAM)", "duration": "1h15m"},

    # TAP Air Portugal (15 routes)
    {"airline": "TAP", "callsign": "TAP109", "route": "Lisbon (LPPT) ➡️ São Paulo (SBGR)", "duration": "10h15m"},
    {"airline": "TAP", "callsign": "TAP115", "route": "Lisbon (LPPT) ➡️ Rio de Janeiro (SBGL)", "duration": "9h45m"},
    {"airline": "TAP", "callsign": "TAP90", "route": "Lisbon (LPPT) ➡️ Miami (KMIA)", "duration": "9h30m"},
    {"airline": "TAP", "callsign": "TAP259", "route": "Lisbon (LPPT) ➡️ Toronto (CYYZ)", "duration": "7h45m"},
    {"airline": "TAP", "callsign": "TAP501", "route": "Lisbon (LPPT) ➡️ Luanda (FNLU)", "duration": "7h15m"},
    {"airline": "TAP", "callsign": "TAP222", "route": "Lisbon (LPPT) ➡️ Boston (KBOS)", "duration": "7h"},
    {"airline": "TAP", "callsign": "TAP208", "route": "Lisbon (LPPT) ➡️ Newark (KEWR)", "duration": "7h30m"},
    {"airline": "TAP", "callsign": "TAP1446", "route": "Lisbon (LPPT) ➡️ Brussels (EBBR)", "duration": "2h35m"},
    {"airline": "TAP", "callsign": "TAP1936", "route": "Lisbon (LPPT) ➡️ Geneva (LSGG)", "duration": "2h25m"},
    {"airline": "TAP", "callsign": "TAP1520", "route": "Porto (LPPR) ➡️ Amsterdam (EHAM)", "duration": "2h30m"},
    {"airline": "TAP", "callsign": "TAP412", "route": "Lisbon (LPPT) ➡️ Porto (LPPR)", "duration": "55m"},
    {"airline": "TAP", "callsign": "TAP562", "route": "Lisbon (LPPT) ➡️ Praia (GVNP)", "duration": "4h"},
    {"airline": "TAP", "callsign": "TAP558", "route": "Lisbon (LPPT) ➡️ Paris (LFPG)", "duration": "2h20m"},
    {"airline": "TAP", "callsign": "TAP931", "route": "Lisbon (LPPT) ➡️ London Heathrow (EGLL)", "duration": "2h40m"},
    {"airline": "TAP", "callsign": "TAP1522", "route": "Porto (LPPR) ➡️ Frankfurt (EDDF)", "duration": "2h40m"},

    # EasyJet (15 routes)
    {"airline": "EasyJet", "callsign": "EZY801", "route": "London Gatwick (EGKK) ➡️ Berlin (EDDB)", "duration": "1h55m"},
    {"airline": "EasyJet", "callsign": "EZY802", "route": "London Gatwick (EGKK) ➡️ Amsterdam (EHAM)", "duration": "1h10m"},
    {"airline": "EasyJet", "callsign": "EZY711", "route": "London Luton (EGGW) ➡️ Budapest (LHBP)", "duration": "2h30m"},
    {"airline": "EasyJet", "callsign": "EZY115", "route": "Paris Orly (LFPO) ➡️ Lisbon (LPPT)", "duration": "2h50m"},
    {"airline": "EasyJet", "callsign": "EZY503", "route": "Paris Orly (LFPO) ➡️ Nice (LFMN)", "duration": "1h25m"},
    {"airline": "EasyJet", "callsign": "EZY332", "route": "London Gatwick (EGKK) ➡️ Naples (LIRN)", "duration": "2h10m"},
    {"airline": "EasyJet", "callsign": "EZY607", "route": "London Luton (EGGW) ➡️ Faro (LPFR)", "duration": "3h10m"},
    {"airline": "EasyJet", "callsign": "EZY2105", "route": "Milan Malpensa (LIMC) ➡️ Lisbon (LPPT)", "duration": "2h45m"},
    {"airline": "EasyJet", "callsign": "EZY402", "route": "Manchester (EGCC) ➡️ Geneva (LSGG)", "duration": "1h55m"},
    {"airline": "EasyJet", "callsign": "EZY452", "route": "Bristol (EGGD) ➡️ Rome (LIRF)", "duration": "2h45m"},
    {"airline": "EasyJet", "callsign": "EZY704", "route": "Edinburgh (EGPH) ➡️ Geneva (LSGG)", "duration": "2h05m"},
    {"airline": "EasyJet", "callsign": "EZY8403", "route": "London Gatwick (EGKK) ➡️ Zurich (LSZH)", "duration": "1h40m"},
    {"airline": "EasyJet", "callsign": "EZY3321", "route": "London Luton (EGGW) ➡️ Amsterdam (EHAM)", "duration": "1h15m"},
    {"airline": "EasyJet", "callsign": "EZY908", "route": "Basel (LFSB) ➡️ Palma de Mallorca (LEPA)", "duration": "2h10m"},
    {"airline": "EasyJet", "callsign": "EZY2100", "route": "London Luton (EGGW) ➡️ Paris Orly (LFPO)", "duration": "1h20m"},

    # Ryanair (15 routes)
    {"airline": "Ryanair", "callsign": "RYR1234", "route": "Dublin (EIDW) ➡️ Milan Bergamo (LIME)", "duration": "2h10m"},
    {"airline": "Ryanair", "callsign": "RYR2456", "route": "Berlin Brandenburg (EDDB) ➡️ Rome Ciampino (LIRA)", "duration": "2h05m"},
    {"airline": "Ryanair", "callsign": "RYR4758", "route": "Vienna (LOWW) ➡️ Athens (LGAV)", "duration": "2h15m"},
    {"airline": "Ryanair", "callsign": "RYR6104", "route": "Lisbon (LPPT) ➡️ Brussels Charleroi (EBCI)", "duration": "2h50m"},
    {"airline": "Ryanair", "callsign": "RYR8316", "route": "Madrid (LEMD) ➡️ Dublin (EIDW)", "duration": "2h20m"},
    {"airline": "Ryanair", "callsign": "RYR3310", "route": "London Stansted (EGSS) ➡️ Barcelona (LEBL)", "duration": "2h10m"},
    {"airline": "Ryanair", "callsign": "RYR4112", "route": "Manchester (EGCC) ➡️ Madrid (LEMD)", "duration": "2h30m"},
    {"airline": "Ryanair", "callsign": "RYR1008", "route": "Munich (EDDM) ➡️ Malta (LMML)", "duration": "2h25m"},
    {"airline": "Ryanair", "callsign": "RYR1190", "route": "Dublin (EIDW) ➡️ Frankfurt (EDDF)", "duration": "1h50m"},
    {"airline": "Ryanair", "callsign": "RYR2102", "route": "Naples (LIRN) ➡️ Barcelona (LEBL)", "duration": "1h40m"},
    {"airline": "Ryanair", "callsign": "RYR1235", "route": "Dublin (EIDW) ➡️ London Stansted (EGSS)", "duration": "1h15m"},
    {"airline": "Ryanair", "callsign": "RYR5230", "route": "Dublin (EIDW) ➡️ Amsterdam (EHAM)", "duration": "1h55m"},
    {"airline": "Ryanair", "callsign": "RYR7452", "route": "Edinburgh (EGPH) ➡️ London Stansted (EGSS)", "duration": "1h20m"},
    {"airline": "Ryanair", "callsign": "RYR9022", "route": "Stockholm Skavsta (ESKN) ➡️ Copenhagen (EKCH)", "duration": "1h05m"},
    {"airline": "Ryanair", "callsign": "RYR2788", "route": "Warsaw Modlin (EPMO) ➡️ Dublin (EIDW)", "duration": "2h55m"},

    # Emirates (15 routes)
    {"airline": "Emirates", "callsign": "UAE25", "route": "Dubai (OMDB) ➡️ London Heathrow (EGLL)", "duration": "7h30m"},
    {"airline": "Emirates", "callsign": "UAE26", "route": "London Heathrow (EGLL) ➡️ Dubai (OMDB)", "duration": "7h15m"},
    {"airline": "Emirates", "callsign": "UAE203", "route": "Dubai (OMDB) ➡️ New York JFK (KJFK)", "duration": "14h0m"},
    {"airline": "Emirates", "callsign": "UAE204", "route": "New York JFK (KJFK) ➡️ Dubai (OMDB)", "duration": "13h50m"},
    {"airline": "Emirates", "callsign": "UAE215", "route": "Dubai (OMDB) ➡️ Los Angeles (KLAX)", "duration": "16h0m"},
    {"airline": "Emirates", "callsign": "UAE412", "route": "Dubai (OMDB) ➡️ Sydney (YSSY)", "duration": "14h30m"},
    {"airline": "Emirates", "callsign": "UAE413", "route": "Sydney (YSSY) ➡️ Dubai (OMDB)", "duration": "14h15m"},
    {"airline": "Emirates", "callsign": "UAE354", "route": "Dubai (OMDB) ➡️ Singapore (WSSS)", "duration": "7h10m"},
    {"airline": "Emirates", "callsign": "UAE355", "route": "Singapore (WSSS) ➡️ Dubai (OMDB)", "duration": "7h0m"},
    {"airline": "Emirates", "callsign": "UAE49", "route": "Dubai (OMDB) ➡️ Frankfurt (EDDF)", "duration": "6h45m"},
    {"airline": "Emirates", "callsign": "UAE50", "route": "Frankfurt (EDDF) ➡️ Dubai (OMDB)", "duration": "6h30m"},
    {"airline": "Emirates", "callsign": "UAE763", "route": "Dubai (OMDB) ➡️ Johannesburg (FAOR)", "duration": "8h0m"},
    {"airline": "Emirates", "callsign": "UAE764", "route": "Johannesburg (FAOR) ➡️ Dubai (OMDB)", "duration": "8h10m"},
    {"airline": "Emirates", "callsign": "UAE318", "route": "Dubai (OMDB) ➡️ Tokyo Haneda (RJTT)", "duration": "9h0m"},
    {"airline": "Emirates", "callsign": "UAE319", "route": "Tokyo Haneda (RJTT) ➡️ Dubai (OMDB)", "duration": "9h10m"},

    # Eurowings (15 routes, mix of one-way + some return flights)
    {"airline": "Eurowings", "callsign": "EWG12", "route": "Cologne (EDDK) ➡️ Berlin Brandenburg (EDDB)", "duration": "1h10m"},
    {"airline": "Eurowings", "callsign": "EWG45", "route": "Düsseldorf (EDDL) ➡️ Vienna (LOWW)", "duration": "1h35m"},
    {"airline": "Eurowings", "callsign": "EWG84", "route": "Hamburg (EDDH) ➡️ Munich (EDDM)", "duration": "1h10m"},
    {"airline": "Eurowings", "callsign": "EWG152", "route": "Stuttgart (EDDS) ➡️ Palma de Mallorca (LEPA)", "duration": "2h05m"},
    {"airline": "Eurowings", "callsign": "EWG153", "route": "Palma de Mallorca (LEPA) ➡️ Stuttgart (EDDS)", "duration": "2h05m"},  # return
    {"airline": "Eurowings", "callsign": "EWG203", "route": "Cologne (EDDK) ➡️ Barcelona (LEBL)", "duration": "2h15m"},
    {"airline": "Eurowings", "callsign": "EWG266", "route": "Hamburg (EDDH) ➡️ Rome Fiumicino (LIRF)", "duration": "2h20m"},
    {"airline": "Eurowings", "callsign": "EWG311", "route": "Düsseldorf (EDDL) ➡️ Athens (LGAV)", "duration": "3h00m"},
    {"airline": "Eurowings", "callsign": "EWG334", "route": "Stuttgart (EDDS) ➡️ Lisbon (LPPT)", "duration": "3h00m"},
    {"airline": "Eurowings", "callsign": "EWG335", "route": "Lisbon (LPPT) ➡️ Stuttgart (EDDS)", "duration": "3h00m"},  # return
    {"airline": "Eurowings", "callsign": "EWG402", "route": "Cologne (EDDK) ➡️ Prague (LKPR)", "duration": "1h20m"},
    {"airline": "Eurowings", "callsign": "EWG431", "route": "Hamburg (EDDH) ➡️ London Heathrow (EGLL)", "duration": "1h45m"},
    {"airline": "Eurowings", "callsign": "EWG520", "route": "Düsseldorf (EDDL) ➡️ Zurich (LSZH)", "duration": "1h10m"},
    {"airline": "Eurowings", "callsign": "EWG855", "route": "Hamburg (EDDH) ➡️ Malaga (LEMG)", "duration": "3h00m"},
    {"airline": "Eurowings", "callsign": "EWG920", "route": "Düsseldorf (EDDL) ➡️ Tenerife South (GCTS)", "duration": "4h40m"},

    # KLM (15 routes)
    {"airline": "KLM", "callsign": "KLM101", "route": "Amsterdam (EHAM) ➡️ London Heathrow (EGLL)", "duration": "1h05m"},
    {"airline": "KLM", "callsign": "KLM735", "route": "Amsterdam (EHAM) ➡️ Frankfurt (EDDF)", "duration": "1h00m"},
    {"airline": "KLM", "callsign": "KLM1363", "route": "Amsterdam (EHAM) ➡️ Paris Charles de Gaulle (LFPG)", "duration": "1h15m"},
    {"airline": "KLM", "callsign": "KLM857", "route": "Amsterdam (EHAM) ➡️ Madrid (LEMD)", "duration": "2h25m"},
    {"airline": "KLM", "callsign": "KLM1691", "route": "Amsterdam (EHAM) ➡️ Rome Fiumicino (LIRF)", "duration": "2h15m"},
    {"airline": "KLM", "callsign": "KLM933", "route": "Amsterdam (EHAM) ➡️ Stockholm Arlanda (ESSA)", "duration": "1h55m"},
    {"airline": "KLM", "callsign": "KLM601", "route": "Amsterdam (EHAM) ➡️ Warsaw (EPWA)", "duration": "1h50m"},
    {"airline": "KLM", "callsign": "KLM641", "route": "Amsterdam (EHAM) ➡️ Budapest (LHBP)", "duration": "1h55m"},
    {"airline": "KLM", "callsign": "KLM1507", "route": "Amsterdam (EHAM) ➡️ Lisbon (LPPT)", "duration": "2h50m"},
    {"airline": "KLM", "callsign": "KLM785", "route": "Amsterdam (EHAM) ➡️ Helsinki (EFHK)", "duration": "2h20m"},
    {"airline": "KLM", "callsign": "KLM2043", "route": "Amsterdam (EHAM) ➡️ Istanbul (LTFM)", "duration": "3h25m"},
    {"airline": "KLM", "callsign": "KLM6011", "route": "Amsterdam (EHAM) ➡️ New York JFK (KJFK)", "duration": "8h05m"},
    {"airline": "KLM", "callsign": "KLM589", "route": "Amsterdam (EHAM) ➡️ Dubai (OMDB)", "duration": "6h30m"},
    {"airline": "KLM", "callsign": "KLM887", "route": "Amsterdam (EHAM) ➡️ Tokyo Narita (RJAA)", "duration": "11h20m"},
    {"airline": "KLM", "callsign": "KLM563", "route": "Amsterdam (EHAM) ➡️ São Paulo Guarulhos (SBGR)", "duration": "11h40m"},

    # Condor (15 routes)
    {"airline": "Condor", "callsign": "CFG2256", "route": "Frankfurt (EDDF) ➡️ Punta Cana (MDPC)", "duration": "10h30m"},
    {"airline": "Condor", "callsign": "CFG2578", "route": "Frankfurt (EDDF) ➡️ Phuket (VTSP)", "duration": "11h15m"},
    {"airline": "Condor", "callsign": "CFG2314", "route": "Frankfurt (EDDF) ➡️ Male (VRMM)", "duration": "9h45m"},
    {"airline": "Condor", "callsign": "CFG2112", "route": "Frankfurt (EDDF) ➡️ Las Vegas (KLAS)", "duration": "11h30m"},
    {"airline": "Condor", "callsign": "CFG2450", "route": "Frankfurt (EDDF) ➡️ Windhoek (FYWH)", "duration": "10h15m"},
    {"airline": "Condor", "callsign": "CFG1854", "route": "Munich (EDDM) ➡️ Cancun (MMUN)", "duration": "12h00m"},
    {"airline": "Condor", "callsign": "CFG2076", "route": "Munich (EDDM) ➡️ Seattle (KSEA)", "duration": "11h00m"},
    {"airline": "Condor", "callsign": "CFG2789", "route": "Munich (EDDM) ➡️ Mauritius (FIMP)", "duration": "11h30m"},
    {"airline": "Condor", "callsign": "CFG1923", "route": "Frankfurt (EDDF) ➡️ Whitehorse (CYXY)", "duration": "9h45m"},
    {"airline": "Condor", "callsign": "CFG2156", "route": "Frankfurt (EDDF) ➡️ Anchorage (PANC)", "duration": "10h15m"},
    {"airline": "Condor", "callsign": "CFG1789", "route": "Frankfurt (EDDF) ➡️ Vancouver (CYVR)", "duration": "10h00m"},
    {"airline": "Condor", "callsign": "CFG2341", "route": "Munich (EDDM) ➡️ Denver (KDEN)", "duration": "11h15m"},
    {"airline": "Condor", "callsign": "CFG1987", "route": "Frankfurt (EDDF) ➡️ San Diego (KSAN)", "duration": "12h15m"},
    {"airline": "Condor", "callsign": "CFG2233", "route": "Munich (EDDM) ➡️ Portland (KPDX)", "duration": "11h30m"},
    {"airline": "Condor", "callsign": "CFG2654", "route": "Frankfurt (EDDF) ➡️ Halifax (CYHZ)", "duration": "7h30m"},

    # Wizz Air (15 routes) - Added as requested
    {"airline": "Wizz Air", "callsign": "WZZ1234", "route": "London Luton (EGGW) ➡️ Budapest (LHBP)", "duration": "2h20m"},
    {"airline": "Wizz Air", "callsign": "WZZ4567", "route": "Warsaw Chopin (EPWA) ➡️ Barcelona (LEBL)", "duration": "2h50m"},
    {"airline": "Wizz Air", "callsign": "WZZ7890", "route": "Budapest (LHBP) ➡️ Dubai Al Maktoum (OMDW)", "duration": "5h15m"},
    {"airline": "Wizz Air", "callsign": "WZZ2345", "route": "Rome Fiumicino (LIRF) ➡️ Warsaw Modlin (EPMO)", "duration": "2h10m"},
    {"airline": "Wizz Air", "callsign": "WZZ6789", "route": "Vienna (LOWW) ➡️ London Gatwick (EGKK)", "duration": "2h15m"},
    {"airline": "Wizz Air", "callsign": "WZZ3456", "route": "Kyiv (UKKK) ➡️ Milan Bergamo (LIME)", "duration": "2h40m"},
    {"airline": "Wizz Air", "callsign": "WZZ8901", "route": "Abu Dhabi (OMAA) ➡️ Athens (LGAV)", "duration": "4h45m"},
    {"airline": "Wizz Air", "callsign": "WZZ1122", "route": "Bucharest (LROP) ➡️ London Luton (EGGW)", "duration": "3h10m"},
    {"airline": "Wizz Air", "callsign": "WZZ3344", "route": "Sofia (LBSF) ➡️ Dortmund (EDLW)", "duration": "2h30m"},
    {"airline": "Wizz Air", "callsign": "WZZ5566", "route": "Tel Aviv (LLBG) ➡️ Prague (LKPR)", "duration": "3h55m"},
    {"airline": "Wizz Air", "callsign": "WZZ7788", "route": "Katowice (EPKT) ➡️ Reykjavik (BIKF)", "duration": "3h50m"},
    {"airline": "Wizz Air", "callsign": "WZZ9900", "route": "Lisbon (LPPT) ➡️ Warsaw Chopin (EPWA)", "duration": "3h20m"},
    {"airline": "Wizz Air", "callsign": "WZZ2233", "route": "Istanbul Sabiha (LTFJ) ➡️ Berlin Brandenburg (EDDB)", "duration": "2h55m"},
    {"airline": "Wizz Air", "callsign": "WZZ4455", "route": "Tirana (LATI) ➡️ Memmingen (EDJA)", "duration": "1h45m"},
    {"airline": "Wizz Air", "callsign": "WZZ6677", "route": "Malta (LMML) ➡️ Milan Malpensa (LIMC)", "duration": "1h50m"}
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
        return random.choice(shorts) if shorts else (random.choice(longs) if longs else "Unknown")
    else:
        return random.choice(longs) if longs else (random.choice(shorts) if shorts else "Unknown")

def build_contract_embed(contract, status="available", user=None):
    airline = contract["airline"]
    color = AIRLINE_COLORS.get(airline, discord.Color.blue())
    aircraft = assign_aircraft(contract)
    callsign = maybe_add_phonetic_suffix(contract["callsign"])

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

        # Create SimBrief URL
        route_parts = self.contract["route"].split(" ➡️ ")
        if len(route_parts) == 2:
            dep_match = route_parts[0].split("(")[-1].replace(")", "")
            arr_match = route_parts[1].split("(")[-1].replace(")", "")
            
            airline_codes = {
                "Lufthansa": "DLH",
                "TAP": "TAP", 
                "EasyJet": "EZY",
                "Ryanair": "RYR",
                "Emirates": "UAE",
                "Eurowings": "EWG",
                "KLM": "KLM",
                "Condor": "CFG",
                "Wizz Air": "WZZ"
            }
            
            airline_code = airline_codes.get(self.contract["airline"], "")
            flight_number = self.contract["callsign"].replace(airline_code, "").strip()
            simbrief_url = f"https://dispatch.simbrief.com/options/custom?orig={dep_match}&dest={arr_match}&airline={airline_code}&fltnum={flight_number}"
        else:
            simbrief_url = "https://dispatch.simbrief.com/options/new"

        aircraft = assign_aircraft(self.contract)
        
        embed_dm = discord.Embed(
            title=f"✈️ Contract Accepted: **{self.contract['callsign']}**",
            color=discord.Color.green()
        )
        embed_dm.add_field(name="🏢 Airline", value=f"**{self.contract['airline']}**", inline=False)
        embed_dm.add_field(name="🔢 Callsign", value=f"**{maybe_add_phonetic_suffix(self.contract['callsign'])}**", inline=True)
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

# ----- Run Bot -----
if __name__ == "__main__":
    # Start the web server in a separate process
    def run_server():
        uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
    
    # Start web server in background thread
    import multiprocessing
    server_process = multiprocessing.Process(target=run_server)
    server_process.daemon = True
    server_process.start()
    print(f"🌐 Web server started on port {PORT}")
    
    # Give web server a moment to start
    time.sleep(2)
    
    # Start Discord bot in main process
    print("🤖 Starting Discord bot...")
