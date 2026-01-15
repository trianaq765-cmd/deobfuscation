import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Discord Bot Settings
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    BOT_PREFIX = os.getenv('BOT_PREFIX', '!')
    
    # Application Settings
    DEOBFUSCATOR_PATH = '/app/deobfuscator'
    UPLOAD_FOLDER = '/app/uploads'
    OUTPUT_FOLDER = '/app/outputs'
    SNAPSHOT_FOLDER = '/app/snapshots'
    LOG_FOLDER = '/app/logs'
    
    # Limits
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_CODE_LENGTH = 500000  # 500k characters
    DEOB_TIMEOUT = 300  # 5 minutes
    COOLDOWN_SECONDS = 30
    
    # Web Server
    WEB_PORT = int(os.getenv('PORT', 10000))
    
    # Allowed Channels (empty = all channels allowed)
    ALLOWED_CHANNELS = os.getenv('ALLOWED_CHANNELS', '').split(',')
    
    # Admin User IDs
    ADMIN_IDS = os.getenv('ADMIN_IDS', '').split(',')
    
    # Trace mode descriptions
    TRACE_MODES = {
        'off': 'No dynamic tracing - Pure static passes only',
        'prints': 'Reconstruct print/io.write calls (clean output)',
        'calls': 'Reconstruct meaningful global function calls',
        'api': 'Log Roblox/global API calls as printable lines',
        'debug': 'Verbose debug hooks (calls, lines, locals)'
    }
