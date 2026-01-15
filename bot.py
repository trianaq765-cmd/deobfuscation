import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import subprocess
import os
import uuid
import io
import base64
import re
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
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, 
                name="/help | Lua Deobfuscator"
            )
        )

bot = DeobBot()

# ============ HELPER FUNCTIONS ============

def create_embed(title: str, desc: str, color: int = 0x00d4ff) -> discord.Embed:
    embed = discord.Embed(
        title=title, 
        description=desc, 
        color=color, 
        timestamp=datetime.utcnow()
    )
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
        return None, f"File too large (max {Config.MAX_FILE_SIZE // 1024 // 1024}MB)"
    if not attachment.filename.endswith(('.lua', '.txt')):
        return None, "Invalid file type. Use .lua or .txt"
    try:
        content = await attachment.read()
        return content.decode('utf-8'), None
    except Exception as e:
        return None, f"Failed to read file: {str(e)}"

def decode_strings(code: str) -> str:
    """Try to decode Base64 and other encoded strings"""
    def try_decode_base64(match):
        s = match.group(1)
        try:
            # Remove padding issues
            padding = 4 - len(s) % 4
            if padding != 4:
                s += '=' * padding
            decoded = base64.b64decode(s).decode('utf-8', errors='ignore')
            # Check if decoded string is printable
            if decoded.isprintable() and len(decoded) > 0:
                return f'"{decoded}"'
        except:
            pass
        return match.group(0)
    
    # Try to decode Base64 strings in quotes
    pattern = r'"([A-Za-z0-9+/=]{4,})"'
    return re.sub(pattern, try_decode_base64, code)

def clean_output(code: str) -> str:
    """Clean and format the output"""
    # Remove excessive empty lines
    code = re.sub(r'\n{3,}', '\n\n', code)
    # Try to decode strings
    code = decode_strings(code)
    return code

# ============ DEOBFUSCATOR FUNCTIONS ============

async def run_deobfuscator(
    code: str, 
    trace: str = 'off', 
    pretty: bool = True
) -> dict:
    """Run single pass deobfuscation"""
    req_id = str(uuid.uuid4())
    input_file = os.path.join(Config.UPLOAD_FOLDER, f'{req_id}.lua')
    output_file = os.path.join(Config.OUTPUT_FOLDER, f'{req_id}.deob.lua')
    
    try:
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)
        
        with open(input_file, 'w') as f:
            f.write(code)
        
        cmd = [
            'lua', 'src/deob/cli.lua', input_file,
            '--out', output_file,
            '--trace', trace,
            '--pretty' if pretty else '--no-pretty'
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=Config.DEOBFUSCATOR_PATH,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), 
            timeout=Config.DEOB_TIMEOUT
        )
        
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                output = f.read()
            output = clean_output(output)
            return {'success': True, 'output': output}
        else:
            error_msg = stderr.decode() if stderr else stdout.decode() if stdout else 'Unknown error'
            return {'success': False, 'error': error_msg}
    
    except asyncio.TimeoutError:
        return {'success': False, 'error': 'Timeout (5 min limit)'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        for f in [input_file, output_file]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

async def run_multipass_deobfuscator(
    code: str,
    passes: int = 3,
    progress_callback = None
) -> dict:
    """Run multi-pass deobfuscation for VM-protected scripts"""
    current_code = code
    results = []
    trace_modes = ['off', 'calls', 'prints', 'debug', 'api']
    
    for i in range(passes):
        trace = trace_modes[i % len(trace_modes)]
        
        if progress_callback:
            await progress_callback(i + 1, passes, trace)
        
        result = await run_deobfuscator(current_code, trace)
        
        if result['success']:
            new_code = result['output']
            old_len = len(current_code)
            new_len = len(new_code)
            
            if old_len > 0:
                change = ((old_len - new_len) / old_len) * 100
            else:
                change = 0
            
            results.append({
                'pass': i + 1,
                'trace': trace,
                'change': change,
                'success': True
            })
            
            # Update if code changed significantly or got smaller
            if new_len != old_len:
                current_code = new_code
        else:
            results.append({
                'pass': i + 1,
                'trace': trace,
                'error': result['error'][:100],
                'success': False
            })
    
    # Final cleanup
    current_code = clean_output(current_code)
    
    return {
        'success': True,
        'output': current_code,
        'results': results,
        'passes': passes
    }

# ============ SLASH COMMANDS ============

@bot.tree.command(name="deobfuscate", description="Deobfuscate Lua code")
@app_commands.describe(
    code="The obfuscated Lua code",
    trace="Trace mode for analysis",
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
    on_cd, remaining = check_cooldown(interaction.user.id)
    if on_cd:
        await interaction.response.send_message(
            embed=create_embed("⏳ Cooldown", f"Wait {remaining} seconds", 0xffc800),
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    if file:
        content, error = await download_attachment(file)
        if error:
            await interaction.followup.send(embed=create_embed("❌ Error", error, 0xff6464))
            return
        code = content
    
    if not code:
        await interaction.followup.send(
            embed=create_embed("❌ Error", "Provide code or upload a file", 0xff6464)
        )
        return
    
    if len(code) > Config.MAX_CODE_LENGTH:
        await interaction.followup.send(
            embed=create_embed("❌ Error", "Code too long (max 500k chars)", 0xff6464)
        )
        return
    
    bot.stats['total'] += 1
    msg = await interaction.followup.send(
        embed=create_embed("🔄 Processing", f"Deobfuscating with trace: `{trace}`", 0xffc800)
    )
    
    result = await run_deobfuscator(code, trace)
    
    if result['success']:
        bot.stats['success'] += 1
        output = result['output']
        
        embed = create_embed(
            "✅ Deobfuscation Complete",
            f"**Trace:** `{trace}`\n**Input:** `{len(code):,}` chars\n**Output:** `{len(output):,}` chars",
            0x00ff64
        )
        
        if len(output) > 1900:
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


@bot.tree.command(name="deob-vm", description="Deobfuscate VM-protected scripts (multi-pass)")
@app_commands.describe(
    file="Upload the obfuscated .lua file",
    passes="Number of passes (1-5, default: 3)"
)
async def slash_deob_vm(
    interaction: discord.Interaction,
    file: discord.Attachment,
    passes: int = 3
):
    on_cd, remaining = check_cooldown(interaction.user.id)
    if on_cd:
        await interaction.response.send_message(
            embed=create_embed("⏳ Cooldown", f"Wait {remaining} seconds", 0xffc800),
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    passes = max(1, min(5, passes))
    
    content, error = await download_attachment(file)
    if error:
        await interaction.followup.send(embed=create_embed("❌ Error", error, 0xff6464))
        return
    
    bot.stats['total'] += 1
    msg = await interaction.followup.send(
        embed=create_embed(
            "🔄 VM Deobfuscation", 
            f"**File:** `{file.filename}`\n**Passes:** `{passes}`\n**Status:** Starting...",
            0xffc800
        )
    )
    
    async def update_progress(current, total, trace):
        try:
            await msg.edit(embed=create_embed(
                "🔄 VM Deobfuscation",
                f"**File:** `{file.filename}`\n**Progress:** Pass `{current}/{total}`\n**Trace:** `{trace}`",
                0xffc800
            ))
        except:
            pass
    
    result = await run_multipass_deobfuscator(content, passes, update_progress)
    
    if result['success']:
        bot.stats['success'] += 1
        output = result['output']
        
        # Build results summary
        summary = []
        for r in result['results']:
            if r['success']:
                summary.append(f"✅ Pass {r['pass']} ({r['trace']}): {r['change']:.1f}% change")
            else:
                summary.append(f"❌ Pass {r['pass']}: {r.get('error', 'Failed')[:30]}")
        
        embed = create_embed(
            "✅ VM Deobfuscation Complete",
            f"**File:** `{file.filename}`\n**Passes:** `{passes}`\n\n**Results:**\n" + "\n".join(summary),
            0x00ff64
        )
        embed.add_field(
            name="📊 Size", 
            value=f"`{len(content):,}` → `{len(output):,}` chars", 
            inline=False
        )
        
        await msg.edit(embed=embed)
        await interaction.followup.send(
            file=discord.File(io.BytesIO(output.encode()), filename=f"vm_deob_{file.filename}")
        )
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result.get('error', 'Unknown error'), 0xff6464))


@bot.tree.command(name="deob-auto", description="Auto-detect and deobfuscate with best settings")
@app_commands.describe(file="Upload the obfuscated .lua file")
async def slash_deob_auto(interaction: discord.Interaction, file: discord.Attachment):
    on_cd, remaining = check_cooldown(interaction.user.id)
    if on_cd:
        await interaction.response.send_message(
            embed=create_embed("⏳ Cooldown", f"Wait {remaining} seconds", 0xffc800),
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    content, error = await download_attachment(file)
    if error:
        await interaction.followup.send(embed=create_embed("❌ Error", error, 0xff6464))
        return
    
    bot.stats['total'] += 1
    msg = await interaction.followup.send(
        embed=create_embed("🔍 Analyzing", "Detecting obfuscation type...", 0xffc800)
    )
    
    # Detect obfuscation type
    is_vm = any(x in content for x in ['while true do', 'local L=', 'local o=', 'F < ', 'F > '])
    is_string_heavy = content.count('\\') > 100 or content.count('==') > 50
    has_roblox = any(x in content for x in ['game:', 'workspace', 'Players', 'Instance'])
    
    if is_vm:
        await msg.edit(embed=create_embed("🔄 VM Detected", "Running multi-pass deobfuscation...", 0xffc800))
        result = await run_multipass_deobfuscator(content, passes=3)
    elif has_roblox:
        await msg.edit(embed=create_embed("🔄 Roblox Script", "Using API trace mode...", 0xffc800))
        result = await run_deobfuscator(content, trace='api')
    elif is_string_heavy:
        await msg.edit(embed=create_embed("🔄 String Obfuscation", "Using prints trace mode...", 0xffc800))
        result = await run_deobfuscator(content, trace='prints')
    else:
        await msg.edit(embed=create_embed("🔄 Standard", "Using static deobfuscation...", 0xffc800))
        result = await run_deobfuscator(content, trace='off')
    
    if result['success']:
        bot.stats['success'] += 1
        output = result['output']
        
        detection = "VM Protected" if is_vm else "Roblox Script" if has_roblox else "String Encoded" if is_string_heavy else "Standard"
        
        embed = create_embed(
            "✅ Auto Deobfuscation Complete",
            f"**Detected:** `{detection}`\n**Input:** `{len(content):,}` chars\n**Output:** `{len(output):,}` chars",
            0x00ff64
        )
        
        await msg.edit(embed=embed)
        await interaction.followup.send(
            file=discord.File(io.BytesIO(output.encode()), filename=f"auto_deob_{file.filename}")
        )
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result.get('error', 'Unknown error')[:500], 0xff6464))


@bot.tree.command(name="help", description="Show help information")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔓 Prometheus Deobfuscator V2",
        description="Advanced Lua Deobfuscation Bot",
        color=0x00d4ff,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(
        name="📝 Main Commands",
        value="""
`/deobfuscate` - Standard deobfuscation with options
`/deob-vm` - Multi-pass for VM-protected scripts
`/deob-auto` - Auto-detect and deobfuscate
`/trace-info` - Learn about trace modes
`/stats` - View statistics
        """,
        inline=False
    )
    
    embed.add_field(
        name="💬 Quick Commands",
        value="""
`!deob <code>` - Quick deobfuscate
`!vm` - VM deobfuscate (attach file)
`!trace <mode> <code>` - With specific trace
        """,
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Trace Modes",
        value="""
• `off` - Static analysis (fastest)
• `prints` - print/io.write reconstruction
• `calls` - Global function calls
• `api` - Roblox/API calls (best for Roblox)
• `debug` - Verbose output (most detailed)
        """,
        inline=False
    )
    
    embed.add_field(
        name="💡 Tips",
        value="""
• Use `/deob-auto` for best auto-detection
• Use `/deob-vm` for heavy obfuscation
• Upload `.lua` files for large scripts
        """,
        inline=False
    )
    
    embed.set_footer(text="Prometheus Deobfuscator V2")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="trace-info", description="Information about trace modes")
async def slash_trace_info(interaction: discord.Interaction):
    embed = create_embed("🔍 Trace Modes", "Choose the right mode for your script")
    
    modes = [
        ("⚡ Off", "Pure static analysis. Best for simple obfuscation. Fastest option."),
        ("📝 Prints", "Reconstructs print() and io.write(). Good for scripts with console output."),
        ("📞 Calls", "Reconstructs global function calls. Helps understand program flow."),
        ("🎮 API", "Logs Roblox/global API calls. **Best for Roblox scripts**."),
        ("🐛 Debug", "Full debug output with calls, lines, locals. Most detailed but verbose."),
    ]
    
    for name, desc in modes:
        embed.add_field(name=name, value=desc, inline=False)
    
    embed.add_field(
        name="💡 Recommendation",
        value="Start with `/deob-auto` - it will auto-detect the best mode for your script!",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="stats", description="View bot statistics")
async def slash_stats(interaction: discord.Interaction):
    uptime = datetime.utcnow() - bot.start_time
    hours, rem = divmod(int(uptime.total_seconds()), 3600)
    mins, secs = divmod(rem, 60)
    days, hours = divmod(hours, 24)
    
    uptime_str = f"{days}d {hours}h {mins}m" if days else f"{hours}h {mins}m {secs}s"
    
    success_rate = (bot.stats['success'] / bot.stats['total'] * 100) if bot.stats['total'] > 0 else 0
    
    embed = create_embed("📊 Bot Statistics", "")
    embed.add_field(name="📈 Total Requests", value=f"`{bot.stats['total']}`", inline=True)
    embed.add_field(name="✅ Successful", value=f"`{bot.stats['success']}`", inline=True)
    embed.add_field(name="❌ Failed", value=f"`{bot.stats['failed']}`", inline=True)
    embed.add_field(name="📊 Success Rate", value=f"`{success_rate:.1f}%`", inline=True)
    embed.add_field(name="🌐 Servers", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="⏱️ Uptime", value=f"`{uptime_str}`", inline=True)
    
    await interaction.response.send_message(embed=embed)


# ============ PREFIX COMMANDS ============

@bot.command(name='deob')
async def cmd_deob(ctx, *, code: str = None):
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        content, error = await download_attachment(attachment)
        if error:
            await ctx.send(embed=create_embed("❌ Error", error, 0xff6464))
            return
        code = content
    
    if not code:
        await ctx.send(embed=create_embed("❌ Error", "Usage: `!deob <code>` or attach a file", 0xff6464))
        return
    
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


@bot.command(name='vm')
async def cmd_vm(ctx):
    """VM deobfuscation - requires file attachment"""
    if not ctx.message.attachments:
        await ctx.send(embed=create_embed("❌ Error", "Attach a .lua file to deobfuscate", 0xff6464))
        return
    
    attachment = ctx.message.attachments[0]
    content, error = await download_attachment(attachment)
    if error:
        await ctx.send(embed=create_embed("❌ Error", error, 0xff6464))
        return
    
    on_cd, remaining = check_cooldown(ctx.author.id)
    if on_cd:
        await ctx.send(embed=create_embed("⏳ Cooldown", f"Wait {remaining}s", 0xffc800))
        return
    
    bot.stats['total'] += 1
    msg = await ctx.send(embed=create_embed("🔄 VM Deobfuscation", "Running 3 passes...", 0xffc800))
    
    result = await run_multipass_deobfuscator(content, passes=3)
    
    if result['success']:
        bot.stats['success'] += 1
        output = result['output']
        
        await msg.edit(embed=create_embed(
            "✅ VM Deobfuscation Complete",
            f"**Passes:** 3\n**Size:** `{len(content):,}` → `{len(output):,}` chars",
            0x00ff64
        ))
        await ctx.send(file=discord.File(io.BytesIO(output.encode()), filename="vm_deobfuscated.lua"))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result.get('error', 'Unknown')[:500], 0xff6464))


@bot.command(name='trace')
async def cmd_trace(ctx, mode: str = 'off', *, code: str = None):
    valid_modes = ['off', 'prints', 'calls', 'api', 'debug']
    
    if mode not in valid_modes:
        await ctx.send(embed=create_embed("❌ Error", f"Valid modes: {', '.join(valid_modes)}", 0xff6464))
        return
    
    if ctx.message.attachments:
        content, error = await download_attachment(ctx.message.attachments[0])
        if error:
            await ctx.send(embed=create_embed("❌ Error", error, 0xff6464))
            return
        code = content
    
    if not code:
        await ctx.send(embed=create_embed("❌ Error", f"Usage: `!trace {mode} <code>`", 0xff6464))
        return
    
    on_cd, remaining = check_cooldown(ctx.author.id)
    if on_cd:
        await ctx.send(embed=create_embed("⏳ Cooldown", f"Wait {remaining}s", 0xffc800))
        return
    
    bot.stats['total'] += 1
    msg = await ctx.send(embed=create_embed("🔄 Processing", f"Trace: `{mode}`", 0xffc800))
    
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
    embed = discord.Embed(title="🔓 Prometheus Deobfuscator V2", color=0x00d4ff)
    embed.add_field(
        name="Commands",
        value="""
`/deobfuscate` - Standard deobfuscation
`/deob-vm` - Multi-pass VM deobfuscation
`/deob-auto` - Auto-detect best mode
`!deob <code>` - Quick deobfuscate
`!vm` - VM deobfuscate (attach file)
`!trace <mode> <code>` - With trace mode
        """,
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
    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                embed=create_embed("❌ Error", str(error)[:200], 0xff6464),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=create_embed("❌ Error", str(error)[:200], 0xff6464),
                ephemeral=True
            )
    except:
        pass


# ============ RUN BOT ============

if __name__ == '__main__':
    if not Config.DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN not set!")
        exit(1)
    
    print("Starting Discord Bot...")
    bot.run(Config.DISCORD_TOKEN)
