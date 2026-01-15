import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import subprocess
import os
import uuid
import io
from datetime import datetime
from config import Config

intents = discord.Intents.default()
intents.message_content = True

class DeobBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=Config.BOT_PREFIX, intents=intents, help_command=None)
        self.start_time = datetime.utcnow()
        self.stats = {'total': 0, 'success': 0, 'failed': 0}
        self.cooldowns = {}
    
    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced!")
    
    async def on_ready(self):
        print(f'Bot ready: {self.user} | Servers: {len(self.guilds)}')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="/help | Deobfuscator"))

bot = DeobBot()

# ============ DEOBFUSCATOR FUNCTION ============

async def run_deobfuscator(code: str, trace: str = 'off', pretty: bool = True) -> dict:
    """Run the Lua deobfuscator"""
    req_id = str(uuid.uuid4())
    input_file = os.path.join(Config.UPLOAD_FOLDER, f'{req_id}.lua')
    output_file = os.path.join(Config.OUTPUT_FOLDER, f'{req_id}.deob.lua')
    
    try:
        # Ensure directories exist
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)
        
        # Write input code
        with open(input_file, 'w') as f:
            f.write(code)
        
        # Build command
        cmd = [
            'lua', 'src/deob/cli.lua', input_file,
            '--out', output_file,
            '--trace', trace
        ]
        cmd.append('--pretty' if pretty else '--no-pretty')
        
        # Run deobfuscator
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=Config.DEOBFUSCATOR_PATH,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=Config.DEOB_TIMEOUT)
        
        # Check result
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                output = f.read()
            return {'success': True, 'output': output}
        else:
            error_msg = stderr.decode() if stderr else stdout.decode() if stdout else 'Unknown error'
            return {'success': False, 'error': error_msg}
    
    except asyncio.TimeoutError:
        return {'success': False, 'error': 'Timeout (5 min limit)'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        # Cleanup
        for f in [input_file, output_file]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

# ============ HELPER FUNCTIONS ============

def create_embed(title: str, desc: str, color: int = 0x00d4ff) -> discord.Embed:
    embed = discord.Embed(title=title, description=desc, color=color, timestamp=datetime.utcnow())
    embed.set_footer(text="Prometheus Deobfuscator V2")
    return embed

def check_cooldown(user_id: int) -> tuple:
    if str(user_id) in Config.ADMIN_IDS:
        return False, 0
    now = datetime.utcnow()
    if user_id in bot.cooldowns:
        diff = (now - bot.cooldowns[user_id]).total_seconds()
        if diff < Config.COOLDOWN_SECONDS:
            return True, int(Config.COOLDOWN_SECONDS - diff)
    bot.cooldowns[user_id] = now
    return False, 0

async def download_attachment(attachment) -> tuple:
    if attachment.size > Config.MAX_FILE_SIZE:
        return None, "File too large (max 5MB)"
    if not attachment.filename.endswith(('.lua', '.txt')):
        return None, "Invalid file type. Use .lua or .txt"
    try:
        content = await attachment.read()
        return content.decode('utf-8'), None
    except Exception as e:
        return None, f"Failed to read file: {str(e)}"

# ============ SLASH COMMANDS ============

@bot.tree.command(name="deobfuscate", description="Deobfuscate Lua code")
@app_commands.describe(
    code="The obfuscated Lua code",
    trace="Trace mode for dynamic analysis",
    file="Upload a .lua file instead"
)
@app_commands.choices(trace=[
    app_commands.Choice(name="Off - Static only (fastest)", value="off"),
    app_commands.Choice(name="Prints - print/io.write", value="prints"),
    app_commands.Choice(name="Calls - Global functions", value="calls"),
    app_commands.Choice(name="API - Roblox/Global API", value="api"),
    app_commands.Choice(name="Debug - Verbose output", value="debug"),
])
async def slash_deob(
    interaction: discord.Interaction,
    code: str = None,
    trace: str = "off",
    file: discord.Attachment = None
):
    # Check cooldown
    on_cd, remaining = check_cooldown(interaction.user.id)
    if on_cd:
        await interaction.response.send_message(
            embed=create_embed("⏳ Cooldown", f"Wait {remaining} seconds", 0xffc800),
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    # Get code from file if provided
    if file:
        content, error = await download_attachment(file)
        if error:
            await interaction.followup.send(embed=create_embed("❌ Error", error, 0xff6464))
            return
        code = content
    
    if not code:
        await interaction.followup.send(
            embed=create_embed("❌ Error", "Please provide code or upload a file", 0xff6464)
        )
        return
    
    if len(code) > Config.MAX_CODE_LENGTH:
        await interaction.followup.send(
            embed=create_embed("❌ Error", "Code is too long (max 500k chars)", 0xff6464)
        )
        return
    
    # Update stats
    bot.stats['total'] += 1
    
    # Send processing message
    msg = await interaction.followup.send(
        embed=create_embed("🔄 Processing", "Deobfuscating your code...", 0xffc800)
    )
    
    # Run deobfuscator
    result = await run_deobfuscator(code, trace)
    
    if result['success']:
        bot.stats['success'] += 1
        output = result['output']
        
        embed = create_embed(
            "✅ Deobfuscation Complete",
            f"**Trace Mode:** `{trace}`\n**Input:** `{len(code):,}` chars\n**Output:** `{len(output):,}` chars",
            0x00ff64
        )
        
        if len(output) > 1900:
            # Send as file
            await msg.edit(embed=embed)
            await interaction.followup.send(
                file=discord.File(io.BytesIO(output.encode()), filename="deobfuscated.lua")
            )
        else:
            embed.add_field(name="📤 Output", value=f"```lua\n{output[:1800]}\n```", inline=False)
            await msg.edit(embed=embed)
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result['error'][:500], 0xff6464))

@bot.tree.command(name="help", description="Show help information")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔓 Prometheus Deobfuscator V2",
        description="Powerful Lua Deobfuscation Bot",
        color=0x00d4ff,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(
        name="📝 Slash Commands",
        value="""
`/deobfuscate` - Deobfuscate code with options
`/trace-info` - Learn about trace modes
`/stats` - View bot statistics
`/help` - Show this message
        """,
        inline=False
    )
    
    embed.add_field(
        name="💬 Prefix Commands",
        value="""
`!deob <code>` - Quick deobfuscate
`!trace <mode> <code>` - Deobfuscate with trace mode
`!help` - Show help
        """,
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Trace Modes",
        value="""
• `off` - Static analysis only (fastest)
• `prints` - Reconstruct print/io.write
• `calls` - Global function calls
• `api` - Roblox/Global API logging
• `debug` - Verbose debug output
        """,
        inline=False
    )
    
    embed.add_field(
        name="📎 File Upload",
        value="Attach a `.lua` file with your command to deobfuscate it!",
        inline=False
    )
    
    embed.set_footer(text="Prometheus Deobfuscator V2")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="trace-info", description="Information about trace modes")
async def slash_trace_info(interaction: discord.Interaction):
    embed = create_embed("🔍 Trace Modes Explained", "Different modes for different needs")
    
    modes = [
        ("⚡ Off", "Pure static analysis. Fastest and most reliable for basic deobfuscation."),
        ("📝 Prints", "Reconstructs print() and io.write() calls. Good for scripts with output."),
        ("📞 Calls", "Reconstructs meaningful global function calls. Helps understand flow."),
        ("🎮 API", "Logs Roblox/global API calls. Best for Roblox script analysis."),
        ("🐛 Debug", "Verbose debug hooks with calls, lines, locals. Most detailed output."),
    ]
    
    for name, desc in modes:
        embed.add_field(name=name, value=desc, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="View bot statistics")
async def slash_stats(interaction: discord.Interaction):
    uptime = datetime.utcnow() - bot.start_time
    hours, rem = divmod(int(uptime.total_seconds()), 3600)
    mins, secs = divmod(rem, 60)
    days, hours = divmod(hours, 24)
    
    uptime_str = f"{days}d {hours}h {mins}m" if days else f"{hours}h {mins}m {secs}s"
    
    embed = create_embed("📊 Bot Statistics", "")
    embed.add_field(name="Total Requests", value=f"`{bot.stats['total']}`", inline=True)
    embed.add_field(name="Successful", value=f"`{bot.stats['success']}`", inline=True)
    embed.add_field(name="Failed", value=f"`{bot.stats['failed']}`", inline=True)
    embed.add_field(name="Servers", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="Uptime", value=f"`{uptime_str}`", inline=True)
    
    await interaction.response.send_message(embed=embed)

# ============ PREFIX COMMANDS ============

@bot.command(name='deob')
async def cmd_deob(ctx, *, code: str = None):
    """Quick deobfuscate command"""
    # Check for attachment
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        content, error = await download_attachment(attachment)
        if error:
            await ctx.send(embed=create_embed("❌ Error", error, 0xff6464))
            return
        code = content
    
    if not code:
        await ctx.send(embed=create_embed("❌ Error", "Usage: `!deob <code>` or attach a .lua file", 0xff6464))
        return
    
    # Check cooldown
    on_cd, remaining = check_cooldown(ctx.author.id)
    if on_cd:
        await ctx.send(embed=create_embed("⏳ Cooldown", f"Wait {remaining}s", 0xffc800))
        return
    
    bot.stats['total'] += 1
    msg = await ctx.send(embed=create_embed("🔄 Processing", "Deobfuscating...", 0xffc800))
    
    result = await run_deobfuscator(code)
    
    if result['success']:
        bot.stats['success'] += 1
        output = result['output']
        
        if len(output) > 1900:
            await msg.edit(embed=create_embed("✅ Success", "See attached file", 0x00ff64))
            await ctx.send(file=discord.File(io.BytesIO(output.encode()), filename="deobfuscated.lua"))
        else:
            await msg.edit(embed=create_embed("✅ Success", f"```lua\n{output[:1800]}\n```", 0x00ff64))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result['error'][:500], 0xff6464))

@bot.command(name='trace')
async def cmd_trace(ctx, mode: str = 'off', *, code: str = None):
    """Deobfuscate with specific trace mode"""
    valid_modes = ['off', 'prints', 'calls', 'api', 'debug']
    
    if mode not in valid_modes:
        await ctx.send(embed=create_embed("❌ Error", f"Valid modes: {', '.join(valid_modes)}", 0xff6464))
        return
    
    # Check for attachment
    if ctx.message.attachments:
        content, error = await download_attachment(ctx.message.attachments[0])
        if error:
            await ctx.send(embed=create_embed("❌ Error", error, 0xff6464))
            return
        code = content
    
    if not code:
        await ctx.send(embed=create_embed("❌ Error", f"Usage: `!trace {mode} <code>`", 0xff6464))
        return
    
    # Check cooldown
    on_cd, remaining = check_cooldown(ctx.author.id)
    if on_cd:
        await ctx.send(embed=create_embed("⏳ Cooldown", f"Wait {remaining}s", 0xffc800))
        return
    
    bot.stats['total'] += 1
    msg = await ctx.send(embed=create_embed("🔄 Processing", f"Trace mode: `{mode}`", 0xffc800))
    
    result = await run_deobfuscator(code, mode)
    
    if result['success']:
        bot.stats['success'] += 1
        await msg.edit(embed=create_embed("✅ Success", f"Trace: `{mode}`", 0x00ff64))
        await ctx.send(file=discord.File(io.BytesIO(result['output'].encode()), filename="deobfuscated.lua"))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result['error'][:500], 0xff6464))

@bot.command(name='help')
async def cmd_help(ctx):
    """Show help"""
    embed = discord.Embed(
        title="🔓 Prometheus Deobfuscator V2",
        description="Lua Deobfuscation Bot",
        color=0x00d4ff
    )
    embed.add_field(
        name="Commands",
        value="""
`/deobfuscate` - Deobfuscate with options
`/help` - Show help
`!deob <code>` - Quick deobfuscate
`!trace <mode> <code>` - With trace mode
        """,
        inline=False
    )
    embed.add_field(
        name="Trace Modes",
        value="`off`, `prints`, `calls`, `api`, `debug`",
        inline=False
    )
    await ctx.send(embed=embed)

# ============ ERROR HANDLERS ============

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.send(embed=create_embed("❌ Error", str(error)[:200], 0xff6464))

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await interaction.response.send_message(
        embed=create_embed("❌ Error", str(error)[:200], 0xff6464),
        ephemeral=True
    )

# ============ RUN BOT ============

if __name__ == '__main__':
    if not Config.DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN not set in environment variables!")
        exit(1)
    
    print("Starting Discord Bot...")
    bot.run(Config.DISCORD_TOKEN)
