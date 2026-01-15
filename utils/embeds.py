import discord
from datetime import datetime

class Colors:
    PRIMARY = 0x00d4ff
    SUCCESS = 0x00ff64
    ERROR = 0xff6464
    WARNING = 0xffc800
    INFO = 0x7289da

def create_embed(title, description, color=Colors.PRIMARY, **kwargs):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow()
    )
    
    if kwargs.get('fields'):
        for field in kwargs['fields']:
            embed.add_field(
                name=field['name'],
                value=field['value'],
                inline=field.get('inline', False)
            )
    
    if kwargs.get('footer'):
        embed.set_footer(text=kwargs['footer'])
    else:
        embed.set_footer(text="Prometheus Deobfuscator V2")
    
    if kwargs.get('thumbnail'):
        embed.set_thumbnail(url=kwargs['thumbnail'])
    
    return embed

def success_embed(title, description, **kwargs):
    return create_embed(f"✅ {title}", description, Colors.SUCCESS, **kwargs)

def error_embed(title, description, **kwargs):
    return create_embed(f"❌ {title}", description, Colors.ERROR, **kwargs)

def warning_embed(title, description, **kwargs):
    return create_embed(f"⚠️ {title}", description, Colors.WARNING, **kwargs)

def info_embed(title, description, **kwargs):
    return create_embed(f"ℹ️ {title}", description, Colors.INFO, **kwargs)

def processing_embed():
    return create_embed(
        "🔄 Processing",
        "```\nDeobfuscating your code...\nThis may take a few moments.\n```",
        Colors.WARNING
    )

def help_embed():
    embed = discord.Embed(
        title="🔓 Prometheus Deobfuscator V2 - Help",
        description="Powerful Lua deobfuscation tool for Discord",
        color=Colors.PRIMARY,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(
        name="📝 Slash Commands",
        value="""
`/deobfuscate` - Deobfuscate Lua code (with options)
`/deob-file` - Deobfuscate from file upload
`/trace-info` - Show trace mode information
`/help` - Show this help message
`/stats` - Show bot statistics
        """,
        inline=False
    )
    
    embed.add_field(
        name="💬 Prefix Commands",
        value="""
`!deob <code>` - Quick deobfuscate
`!deob-file` - Deobfuscate attached file
`!trace <mode> <code>` - Deob with specific trace
`!help` - Show help
        """,
        inline=False
    )
    
    embed.add_field(
        name="📎 File Upload",
        value="Attach a `.lua` file with your command to deobfuscate it directly.",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Trace Modes",
        value="""
• `off` - Static analysis only (fastest)
• `prints` - Reconstruct print statements
• `calls` - Global function call reconstruction
• `api` - Roblox/API call logging
• `debug` - Full debug output
        """,
        inline=False
    )
    
    embed.set_footer(text="Prometheus Deobfuscator V2 | Made with ❤️")
    return embed

def stats_embed(stats):
    embed = discord.Embed(
        title="📊 Bot Statistics",
        color=Colors.INFO,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name="Total Deobfuscations", value=f"`{stats.get('total', 0)}`", inline=True)
    embed.add_field(name="Successful", value=f"`{stats.get('success', 0)}`", inline=True)
    embed.add_field(name="Failed", value=f"`{stats.get('failed', 0)}`", inline=True)
    embed.add_field(name="Servers", value=f"`{stats.get('servers', 0)}`", inline=True)
    embed.add_field(name="Users", value=f"`{stats.get('users', 0)}`", inline=True)
    embed.add_field(name="Uptime", value=f"`{stats.get('uptime', 'N/A')}`", inline=True)
    
    return embed
