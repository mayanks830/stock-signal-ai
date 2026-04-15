import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL")  # Set if using Palantir AIP gateway
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "trading.db"))
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", 8000))

MIN_REVENUE = float(os.getenv("MIN_REVENUE_BILLION", 1)) * 1_000_000_000
TOP_N_STOCKS = int(os.getenv("TOP_N_STOCKS", 50))
SCAN_DAY = os.getenv("SCAN_DAY", "monday")
SCAN_HOUR = int(os.getenv("SCAN_HOUR", 16))  # 4PM ET market close

MIN_WOW_PCT = float(os.getenv("MIN_WOW_PCT", 3.0))       # Minimum WoW % change to qualify
MIN_PRICE = float(os.getenv("MIN_PRICE", 10.0))           # Filter out cheap stocks
MAX_PER_SECTOR = int(os.getenv("MAX_PER_SECTOR", 2))      # Max signals per sector
SIGNAL_COOLDOWN_DAYS = int(os.getenv("SIGNAL_COOLDOWN_DAYS", 7))  # Skip recent signals

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY is not set in .env")

if not DISCORD_WEBHOOK_URL:
    raise ValueError("DISCORD_WEBHOOK_URL is not set in .env")
