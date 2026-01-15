import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import io
import os
from datetime import datetime, timedelta
from config import Config
from deobfuscator import deobfuscator, DeobfuscatorError
from utils.embeds import *
from utils.helpers import *

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

class DeobBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=Config.BOT_PREFIX,
            intents=intents,
            help_command=None
        )
        self.start_time = datetime.utcnow()
        self.cooldowns = {}
    
    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced slash commands")
    
    async def on_ready(self):
        print(f'Bot is ready! Logged in as {self.user}')
        print(f'Servers: {len(self.guilds)}')
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="/help | Lua Deobfuscator"
            )
        )
    
    def check_cooldown(self, user_id: int) -> tuple:
        """Check if user is on cooldown"""
        if str(user_id) in Config.ADMIN_IDS:
            return False, 0
        
        now = datetime.utcnow()
        if user_id in self.cooldowns:
            diff = (now - self.cooldowns[user_id]).total_seconds()
            if diff < Config.COOLDOWN_SECONDS:
                return True, Config.COOLDOWN_SECONDS - int(diff)
        
        self.cooldowns[user_id] = now
        return False, 0
    
    def get_uptime(self) -> str:
        delta = datetime.utcnow() - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        
        if days:
            return f"{days}d {hours}h {minutes}m"
        elif hours:
            return f"{hours}h {minutes}m {seconds}s"
        else:
            return f"{minutes}m {seconds}s"

bot = DeobBot()

# ============== TRACE MODE SELECT MENU ==============

class TraceModeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Off",
                value="off",
                description="Pure static passes only (fastest)",
                emoji="⚡"
            ),
            discord.SelectOption(
                label="Prints",
                value="prints",
                description="Reconstruct print/io.write",
                emoji="📝"
            ),
            discord.SelectOption(
                label="Calls",
                value="calls",
                description="Global function calls reconstruction",
                emoji="📞"
            ),
            discord.SelectOption(
                label="API",
                value="api",
                description="Roblox/Global API logging",
                emoji="🎮"
            ),
            discord.SelectOption(
                label="Debug",
                value="debug",
                description="Verbose debug hooks",
                emoji="🐛"
            )
        ]
        super().__init__(
            placeholder="Select trace mode...",
            options=options,
            custom_id="trace_select"
        )

class TraceSelectView(discord.ui.View):
    def __init__(self, code: str, user_id: int):
        super().__init__(timeout=60)
        self.code = code
        self.user_id = user_id
        self.add_item(TraceModeSelect())
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your deobfuscation request!",
                ephemeral=True
            )
            return False
        return True

# ============== OPTIONS VIEW ==============

class DeobOptionsView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.trace_mode = "off"
        self.pretty = True
        self.emit_ast = False
    
    @discord.ui.select(
        placeholder="🔍 Select Trace Mode",
        options=[
            discord.SelectOption(label="Off (Static)", value="off", emoji="⚡", default=True),
            discord.SelectOption(label="Prints", value="prints", emoji="📝"),
            discord.SelectOption(label="Calls", value="calls", emoji="📞"),
            discord.SelectOption(label="API", value="api", emoji="🎮"),
            discord.SelectOption(label="Debug", value="debug", emoji="🐛"),
        ]
    )
    async def trace_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.trace_mode = select.values[0]
        await interaction.response.defer()
    
    @discord.ui.button(label="Pretty Print: ON", style=discord.ButtonStyle.green, emoji="✨")
    async def toggle_pretty(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pretty = not self.pretty
        button.label = f"Pretty Print: {'ON' if self.pretty else 'OFF'}"
        button.style = discord.ButtonStyle.green if self.pretty else discord.ButtonStyle.gray
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(label="Emit AST: OFF", style=discord.ButtonStyle.gray, emoji="🌳")
    async def toggle_ast(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.emit_ast = not self.emit_ast
        button.label = f"Emit AST: {'ON' if self.emit_ast else 'OFF'}"
        button.style = discord.ButtonStyle.green if self.emit_ast else discord.ButtonStyle.gray
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(label="Start Deobfuscation", style=discord.ButtonStyle.primary, emoji="🚀", row=2)
    async def start_deob(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.defer()

# ============== SLASH COMMANDS ==============

@bot.tree.command(name="deobfuscate", description="Deobfuscate Lua code with options")
@app_commands.describe(
    code="The obfuscated Lua code to deobfuscate",
    trace="Trace mode for dynamic reconstruction",
    pretty="Enable pretty printing",
    file="Upload a .lua file instead"
)
@app_commands.choices(trace=[
    app_commands.Choice(name="Off - Static only", value="off"),
    app_commands.Choice(name="Prints - print/io.write", value="prints"),
    app_commands.Choice(name="Calls - Global functions", value="calls"),
    app_commands.Choice(name="API - Roblox/Global API", value="api"),
    app_commands.Choice(name="Debug - Verbose", value="debug"),
])
async def slash_deobfuscate(
    interaction: discord.Interaction,
    code: str = None,
    trace: str = "off",
    pretty: bool = True,
    file: discord.Attachment = None
):
    # Check cooldown
    on_cooldown, remaining = bot.check_cooldown(interaction.user.id)
    if on_cooldown:
        await interaction.response.send_message(
            embed=warning_embed("Cooldown", f"Please wait {remaining} seconds before using this command again."),
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    # Get code from file or parameter
    if file:
        content, error = await download_attachment(file)
        if error:
            await interaction.followup.send(embed=error_embed("File Error", error))
            return
        code = content
    
    if not code:
        await interaction.followup.send(
            embed=error_embed("No Code", "Please provide code or upload a file."),
            ephemeral=True
        )
        return
    
    # Validate code
    valid, error = validate_lua_code(code)
    if not valid:
        await interaction.followup.send(embed=error_embed("Invalid Code", error))
        return
    
    # Send processing message
    processing_msg = await interaction.followup.send(embed=processing_embed())
    
    try:
        # Run deobfuscation
        result = await deobfuscator.deobfuscate(
            code=code,
            trace_mode=trace,
            pretty=pretty
        )
        
        output = result['output']
        truncated_output, was_truncated = truncate_output(output, 1800)
        
        # Create success embed
        embed = success_embed(
            "Deobfuscation Complete",
            f"**Trace Mode:** `{trace}`\n**Pretty Print:** `{pretty}`",
            fields=[
                {"name": "📊 Input Size", "value": f"`{len(code):,}` chars", "inline": True},
                {"name": "📊 Output Size", "value": f"`{len(output):,}` chars", "inline": True},
            ]
        )
        
        # Send result
        if was_truncated or len(output) > 1900:
            # Send as file
            file_output = discord.File(
                io.BytesIO(output.encode()),
                filename="deobfuscated.lua"
            )
            await processing_msg.edit(embed=embed)
            await interaction.followup.send(
                "📄 **Deobfuscated Code:**",
                file=file_output
            )
        else:
            embed.add_field(
                name="📤 Output",
                value=f"```lua\n{truncated_output}\n```",
                inline=False
            )
            await processing_msg.edit(embed=embed)
    
    except DeobfuscatorError as e:
        await processing_msg.edit(embed=error_embed("Deobfuscation Failed", str(e)))
    except Exception as e:
        await processing_msg.edit(embed=error_embed("Error", str(e)))

@bot.tree.command(name="deob-file", description="Deobfuscate a Lua file with interactive options")
@app_commands.describe(file="The .lua file to deobfuscate")
async def slash_deob_file(interaction: discord.Interaction, file: discord.Attachment):
    # Download file
    content, error = await download_attachment(file)
    if error:
        await interaction.response.send_message(
            embed=error_embed("File Error", error),
            ephemeral=True
        )
        return
    
    # Show options view
    view = DeobOptionsView(interaction.user.id)
    
    embed = create_embed(
        "⚙️ Deobfuscation Options",
        f"**File:** `{file.filename}`\n**Size:** `{len(content):,}` characters\n\nSelect your options and click **Start Deobfuscation**",
        fields=[
            {"name": "Current Settings", "value": f"• Trace: `off`\n• Pretty Print: `ON`\n• Emit AST: `OFF`", "inline": False}
        ]
    )
    
    await interaction.response.send_message(embed=embed, view=view)
    
    # Wait for user to click start
    await view.wait()
    
    if view.is_finished():
        # Process with selected options
        processing_msg = await interaction.followup.send(embed=processing_embed())
        
        try:
            result = await deobfuscator.deobfuscate(
                code=content,
                trace_mode=view.trace_mode,
                pretty=view.pretty,
                emit_ast=view.emit_ast
            )
            
            output = result['output']
            
            embed = success_embed(
                "Deobfuscation Complete",
                f"**File:** `{file.filename}`\n**Trace:** `{view.trace_mode}`",
                fields=[
                    {"name": "📊 Stats", "value": f"Input: `{len(content):,}` → Output: `{len(output):,}` chars", "inline": False}
                ]
            )
            
            file_output = discord.File(
                io.BytesIO(output.encode()),
                filename=f"deobfuscated_{file.filename}"
            )
            
            await processing_msg.edit(embed=embed)
            await interaction.followup.send(file=file_output)
        
        except DeobfuscatorError as e:
            await processing_msg.edit(embed=error_embed("Failed", str(e)))

@bot.tree.command(name="help", description="Show help information")
async def slash_help(interaction: discord.Interaction):
    await interaction.response.send_message(embed=help_embed())

@bot.tree.command(name="trace-info", description="Show information about trace modes")
async def slash_trace_info(interaction: discord.Interaction):
    embed = create_embed(
        "🔍 Trace Modes Explained",
        "Different trace modes provide different levels of dynamic analysis",
        fields=[
            {
                "name": "⚡ Off",
                "value": "Pure static passes only. Fastest and most reliable for basic deobfuscation.",
                "inline": False
            },
            {
                "name": "📝 Prints",
                "value": "Reconstructs `print()` and `io.write()` calls. Clean output for scripts with print statements.",
                "inline": False
            },
            {
                "name": "📞 Calls",
                "value": "Reconstructs meaningful global function calls with filtering. Good for understanding script behavior.",
                "inline": False
            },
            {
                "name": "🎮 API",
                "value": "Logs Roblox and global API calls/sets as printable lines. Best for Roblox script analysis.",
                "inline": False
            },
            {
                "name": "🐛 Debug",
                "value": "Verbose debug hooks including calls, lines, and locals. Most detailed but verbose output.",
                "inline": False
            }
        ]
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="Show bot statistics")
async def slash_stats(interaction: discord.Interaction):
    stats = deobfuscator.get_stats()
    stats['servers'] = len(bot.guilds)
    stats['users'] = sum(g.member_count for g in bot.guilds)
    stats['uptime'] = bot.get_uptime()
    
    await interaction.response.send_message(embed=stats_embed(stats))

# ============== PREFIX COMMANDS ==============

@bot.command(name='deob')
async def cmd_deob(ctx, *, code: str = None):
    """Quick deobfuscate command"""
    # Check for attachment
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        content, error = await download_attachment(attachment)
        if error:
            await ctx.send(embed=error_embed("File Error", error))
            return
        code = content
    
    if not code:
        await ctx.send(embed=error_embed("No Code", "Provide code or attach a .lua file\nUsage: `!deob <code>` or attach file"))
        return
    
    # Check cooldown
    on_cooldown, remaining = bot.check_cooldown(ctx.author.id)
    if on_cooldown:
        await ctx.send(embed=warning_embed("Cooldown", f"Wait {remaining}s"))
        return
    
    processing_msg = await ctx.send(embed=processing_embed())
    
    try:
        result = await deobfuscator.deobfuscate(code=code, trace_mode='off', pretty=True)
        output = result['output']
        
        if len(output) > 1900:
            file_output = discord.File(io.BytesIO(output.encode()), filename="deobfuscated.lua")
            await processing_msg.edit(embed=success_embed("Done", "See attached file"))
            await ctx.send(file=file_output)
        else:
            embed = success_embed("Deobfuscated", f"```lua\n{output[:1800]}\n```")
            await processing_msg.edit(embed=embed)
    
    except DeobfuscatorError as e:
        await processing_msg.edit(embed=error_embed("Failed", str(e)))

@bot.command(name='trace')
async def cmd_trace(ctx, mode: str = 'off', *, code: str = None):
    """Deobfuscate with specific trace mode"""
    valid_modes = ['off', 'prints', 'calls', 'api', 'debug']
    
    if mode not in valid_modes:
        await ctx.send(embed=error_embed("Invalid Mode", f"Valid modes: {', '.join(valid_modes)}"))
        return
    
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        content, error = await download_attachment(attachment)
        if error:
            await ctx.send(embed=error_embed("File Error", error))
            return
        code = content
    
    if not code:
        await ctx.send(embed=error_embed("No Code", f"Usage: `!trace {mode} <code>`"))
        return
    
    on_cooldown, remaining = bot.check_cooldown(ctx.author.id)
    if on_cooldown:
        await ctx.send(embed=warning_embed("Cooldown", f"Wait {remaining}s"))
        return
    
    processing_msg = await ctx.send(embed=processing_embed())
    
    try:
        result = await deobfuscator.deobfuscate(code=code, trace_mode=mode, pretty=True)
        output = result['output']
        
        file_output = discord.File(io.BytesIO(output.encode()), filename="deobfuscated.lua")
        await processing_msg.edit(embed=success_embed("Done", f"Trace mode: `{mode}`"))
        await ctx.send(file=file_output)
    
    except DeobfuscatorError as e:
        await processing_msg.edit(embed=error_embed("Failed", str(e)))

@bot.command(name='help')
async def cmd_help(ctx):
    """Show help"""
    await ctx.send(embed=help_embed())

# ============== ERROR HANDLERS ==============

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=error_embed("Permission Denied", "You don't have permission to use this command."))
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(embed=warning_embed("Cooldown", f"Try again in {error.retry_after:.1f}s"))
    else:
        await ctx.send(embed=error_embed("Error", str(error)))

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            embed=warning_embed("Cooldown", f"Try again in {error.retry_after:.1f}s"),
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            embed=error_embed("Error", str(error)),
            ephemeral=True
        )

def run_bot():
    if not Config.DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN not set!")
        return
    
    bot.run(Config.DISCORD_TOKEN)

if __name__ == '__main__':
    run_bot()
