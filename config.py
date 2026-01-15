import os

class Config:
    # Discord Bot
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    BOT_PREFIX = os.getenv('BOT_PREFIX', '!')
    
    # Path - sesuai dengan Dockerfile
    DEOBFUSCATOR_PATH = '/app/deobfuscator'
    
    # Folders
    UPLOAD_FOLDER = '/app/uploads'
    OUTPUT_FOLDER = '/app/outputs'
    SNAPSHOT_FOLDER = '/app/snapshots'
    
    # Limits
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_CODE_LENGTH = 500000  # 500k chars
    DEOB_TIMEOUT = 300  # 5 minutes
    COOLDOWN_SECONDS = 30
    
    # Web
    WEB_PORT = int(os.getenv('PORT', 10000))
    
    # Admin IDs (untuk skip cooldown)
    ADMIN_IDS = [x.strip() for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
