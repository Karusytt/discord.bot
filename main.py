import os
import threading
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn

# Load environment variables
load_dotenv()

# Create FastAPI app (MUST BE AT TOP LEVEL)
app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Bot is running!", "service": "Flight Dispatcher Bot"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Run web server
def run_webserver():
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

# Import and start bot in background
def start_bot():
    try:
        # Import bot here to avoid circular imports
        from bot import run_discord_bot
        print("🚀 Starting Discord bot...")
        run_discord_bot()
    except Exception as e:
        print(f"❌ Error starting bot: {e}")

if __name__ == "__main__":
    # Start bot in background thread
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # Start web server in main thread
    print("🌐 Starting web server...")
    run_webserver()
