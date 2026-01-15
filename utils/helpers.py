import os
import uuid
import aiofiles
import asyncio
from config import Config

async def save_code_to_file(code: str) -> str:
    """Save code to a temporary file and return the path"""
    filename = f"{uuid.uuid4()}.lua"
    filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    
    async with aiofiles.open(filepath, 'w') as f:
        await f.write(code)
    
    return filepath

async def read_file(filepath: str) -> str:
    """Read content from a file"""
    async with aiofiles.open(filepath, 'r') as f:
        return await f.read()

async def cleanup_files(*filepaths):
    """Delete temporary files"""
    for filepath in filepaths:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

def truncate_output(text: str, max_length: int = 1900) -> tuple:
    """Truncate text for Discord message limits"""
    if len(text) <= max_length:
        return text, False
    return text[:max_length] + "\n... [truncated]", True

def format_code_block(code: str, language: str = "lua") -> str:
    """Format code in a Discord code block"""
    return f"```{language}\n{code}\n```"

def validate_lua_code(code: str) -> tuple:
    """Basic validation of Lua code"""
    if not code or not code.strip():
        return False, "No code provided"
    
    if len(code) > Config.MAX_CODE_LENGTH:
        return False, f"Code exceeds maximum length ({Config.MAX_CODE_LENGTH} characters)"
    
    return True, None

async def download_attachment(attachment) -> tuple:
    """Download Discord attachment and return content"""
    if attachment.size > Config.MAX_FILE_SIZE:
        return None, f"File too large (max {Config.MAX_FILE_SIZE // 1024 // 1024}MB)"
    
    if not attachment.filename.endswith(('.lua', '.txt')):
        return None, "Invalid file type. Please upload .lua or .txt files"
    
    try:
        content = await attachment.read()
        return content.decode('utf-8'), None
    except Exception as e:
        return None, f"Failed to read file: {str(e)}"
