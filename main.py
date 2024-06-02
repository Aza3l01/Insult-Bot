import hikari
import lightbulb
import random
import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()
channel = os.getenv('CHANNEL_ID')

hearing_string = os.getenv("HEARING_LIST")
hearing = hearing_string.split(",")

response_string = os.getenv("RESPONSE_LIST")
response = response_string.split(",")

prem_users_string = os.getenv("PREM_USERS_LIST")
prem_users = prem_users_string.split(",")

bot = lightbulb.BotApp(
	intents = hikari.Intents.ALL_UNPRIVILEGED | hikari.Intents.GUILD_MESSAGES | hikari.Intents.MESSAGE_CONTENT,
	token=os.getenv('BOT_TOKEN')
)

class TopGGClient:
    def __init__(self, bot, token):
        self.bot = bot
        self.token = token
        self.session = aiohttp.ClientSession()

    async def post_guild_count(self, count):
        url = f"https://top.gg/api/bots/{self.bot.get_me().id}/stats"
        headers = {
            "Authorization": self.token
        }
        payload = {
            "server_count": count
        }
        async with self.session.post(url, json=payload, headers=headers) as response:
            if response.status != 200:
                print(f"Failed to post guild count to Top.gg: {response.status}")
            else:
                print("Posted server count to Top.gg")
    async def close(self):
        await self.session.close()

topgg_token = os.getenv("TOPGG_TOKEN")
topgg_client = TopGGClient(bot, topgg_token)

# Server count update
@bot.listen(hikari.StartedEvent)
async def on_starting(event: hikari.StartedEvent) -> None:
    guilds = await bot.rest.fetch_my_guilds()
    server_count = len(guilds)
    
    await bot.update_presence(
        activity=hikari.Activity(
            name=f"{server_count} servers! | /help",
            type=hikari.ActivityType.WATCHING,
        )
    )
    await topgg_client.post_guild_count(server_count)

#main
@bot.listen(hikari.MessageCreateEvent)
async def on_message(event: hikari.MessageCreateEvent):
    if not event.is_human:
        return
    if isinstance(event.content, str) and any(word in event.content.lower() for word in hearing):
        try:
            await event.message.respond(random.choice(response))
        except hikari.ForbiddenError:
            guild = bot.cache.get_guild(event.guild_id) if event.guild_id else None
            guild_name = guild.name if guild else "DM"
            try:
                await bot.rest.create_message(channel, f"`keyword` was used in `{guild_name}`.")
            except hikari.ForbiddenError:
                await bot.rest.create_message(channel, f"`Bot doesn't have permission to send messages in `{guild_name}`.")
        except Exception as e:
            print(f"An error occurred: {e}")
        await asyncio.sleep(5)

#help command
@bot.command
@lightbulb.add_cooldown(length=30, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command('help', 'You know what this is ;)')
@lightbulb.implements(lightbulb.SlashCommand)
async def help(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    embed = hikari.Embed(
        title='__**Commands**__',
        description=(
            '**__Main:__**\n'
            '**/insult:** Generate a random insult.\n'
            '**/list:** List of all the insults.\n\n'
            '**__Misc:__**\n'
            '**/invite:** Get the bot\'s invite link.\n'
            '**/vote:** Get the link to vote at top.gg.\n'
            '**/support:** Join the support server.\n'
            '**/donate:** Support Insult Bot.\n'
            '**/more:** Check out more bots from me.'
        ),
        color=0x2f3136
    )
    await ctx.respond(embed=embed)

    thank_you_embed = hikari.Embed(
        description=(
            '**Thank you!**\n'
            'If you like using Insult Bot, consider [voting](https://top.gg/bot/801431445452750879/vote) or leaving a [review](https://top.gg/bot/801431445452750879).\n'
            'To help keep Insult Bot online, consider becoming a [member](https://buymeacoffee.com/azael/membership).'
        ),
        color=0x2f3136
    )
    await ctx.respond(embed=thank_you_embed)

#insult command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command('insult', 'Generate a random insult.')
@lightbulb.implements(lightbulb.SlashCommand)
async def insult(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    
    await ctx.respond(random.choice(response))

#list command
@bot.command
@lightbulb.add_cooldown(length=30, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command('list', 'List of all the insults.')
@lightbulb.implements(lightbulb.SlashCommand)
async def list(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    
    insult_list = (
        "No you | Fuck you | Your mom\n"
        "Stfu | Bruh | Dickhead | Asshole\n"
        "Idiot | Go fuck yourself | Pussy\n"
        "Insecure turd goblin | Shithead\n"
        "You can do better | Stfu inbred\n"
        "Bitch pls | Shut your mouth\n"
        "You disgust me | Fuck off\n"
        "Dumbass | You're dumb\n"
        "*Includes different variations.*"
    )
    
    embed = hikari.Embed(
        title="__**Insults**__",
        description=insult_list,
        color=0x2f3136
    )
    await ctx.respond(embed=embed)
    
    thank_you_embed = hikari.Embed(
        description=(
            '**Thank you!**\n'
            'If you like using Insult Bot, consider [voting](https://top.gg/bot/801431445452750879/vote) or leaving a [review](https://top.gg/bot/801431445452750879).\n'
            'To help keep Anicord online, consider becoming a [member](https://buymeacoffee.com/azael/membership).'
        ),
        color=0x2f3136
    )
    await ctx.respond(embed=thank_you_embed)

#invite command
@bot.command
@lightbulb.add_cooldown(length=30, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command('invite', "Get the bot's invite link.")
@lightbulb.implements(lightbulb.SlashCommand)
async def invite(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    
    embed = hikari.Embed(
        description=(
            '**Invite:**\n'
            'Get the bot\'s invite link [here](https://discord.com/oauth2/authorize?client_id=801431445452750879&permissions=414464727104&scope=applications.commands%20bot).'
        ),
        color=0x2f3136
    )
    await ctx.respond(embed=embed)

#vote command
@bot.command
@lightbulb.add_cooldown(length=30, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command('vote', 'Get the link to vote at top.gg.')
@lightbulb.implements(lightbulb.SlashCommand)
async def vote(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    embed = hikari.Embed(
        description=(
            '**Vote:**\n'
            'Click [here](https://top.gg/bot/801431445452750879/vote) to vote on top.gg (thank you!)'
        ),
        color=0x2f3136
    )
    await ctx.respond(embed=embed)

#support command
@bot.command
@lightbulb.add_cooldown(length=30, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command('support', 'Invite to join the support server.')
@lightbulb.implements(lightbulb.SlashCommand)
async def support(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    embed = hikari.Embed(
        description=(
            '**Support:**\n'
            'Click [here](https://discord.com/invite/CvpujuXmEf) to join the support server.'
        ),
        color=0x2f3136
    )
    await ctx.respond(embed=embed)

#donate command
@bot.command
@lightbulb.add_cooldown(length=30, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command('donate', 'Donate to support Insult Bot.')
@lightbulb.implements(lightbulb.SlashCommand)
async def donate(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    embed = hikari.Embed(
        description=(
            '**Donate:**\n'
            '[Buy me a coffee](https://buymeacoffee.com/azael/membership) to keep Insult Bot online.\n'
            'Thank you! :)'
        ),
        color=0x2f3136
    )
    await ctx.respond(embed=embed)

#more command
@bot.command
@lightbulb.add_cooldown(length=30, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("more", "Check out more bots from me.")
@lightbulb.implements(lightbulb.SlashCommand)
async def more(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    embed = hikari.Embed(
        description=(
            '**More:**\n'
            'Click [here](https://top.gg/user/67067136345571328) to check out more bots from me.'
        ),
        color=0x2f3136
    )
    await ctx.respond(embed=embed)

#privacy command
@bot.command
@lightbulb.command("privacy", "View the privacy policy statement.")
@lightbulb.implements(lightbulb.SlashCommand)
async def privacy(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used.")
    embed = hikari.Embed(
		title="",
		description="**Privacy Policy:** \n The personal information of any user, including the message content it replies to, is not tracked by Insult Bot.",
		color=0x2f3136
	)
    await ctx.respond(embed=embed)

#error handling
@bot.listen(lightbulb.CommandErrorEvent)
async def on_error(event: lightbulb.CommandErrorEvent) -> None:
	if isinstance(event.exception, lightbulb.CommandInvocationError):
		await event.context.respond(f"Something went wrong during invocation of command `{event.context.command.name}`, Please try again.")
		raise event.exception

	exception = event.exception.__cause__ or event.exception

	if isinstance(exception, lightbulb.CommandIsOnCooldown):
		await event.context.respond(f"`/{event.context.command.name}` is on cooldown. Retry in `{exception.retry_after:.0f}` seconds. ⏱️ \n To avoid cooldowns, become a member at https://www.buymeacoffee.com/azael. \n It helps keep the bot online. 👉👈")
	else:
		raise exception

@bot.listen(hikari.StoppedEvent)
async def on_stopping(event: hikari.StoppedEvent) -> None:
    await topgg_client.close()

bot.run()