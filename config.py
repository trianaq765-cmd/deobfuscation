import os

class Config:
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    BOT_PREFIX = os.getenv('BOT_PREFIX', '!')
    DEOBFUSCATOR_PATH = '/app/deobfuscator'
    UPLOAD_FOLDER = '/app/uploads'
    OUTPUT_FOLDER = '/app/outputs'
    SNAPSHOT_FOLDER = '/app/snapshots'
    MAX_FILE_SIZE = 5 * 1024 * 1024
    MAX_CODE_LENGTH = 500000
    DEOB_TIMEOUT = 300
    COOLDOWN_SECONDS = 30
    WEB_PORT = int(os.getenv('PORT', 10000))
    ADMIN_IDS = [x.strip() for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
