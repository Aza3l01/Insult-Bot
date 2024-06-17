import hikari
import lightbulb
import random
import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()
channel = os.getenv("CHANNEL_ID")

hearing_string = os.getenv("HEARING_LIST")
hearing = hearing_string.split(",")

response_string = os.getenv("RESPONSE_LIST")
response = response_string.split(",")

prem_users_string = os.getenv("PREM_USERS_LIST")
prem_users = prem_users_string.split(",")

custom_insults = {857112618963566592: ["test insult", "test insult 24"], 1006195077409951864: ["support insult"]}

bot = lightbulb.BotApp(
	intents = hikari.Intents.ALL_UNPRIVILEGED | hikari.Intents.GUILD_MESSAGES | hikari.Intents.MESSAGE_CONTENT,
	token=os.getenv("BOT_TOKEN")
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

#join
@bot.listen(hikari.GuildJoinEvent)
async def on_guild_join(event):
    guild = event.get_guild()
    if guild is not None:
        await bot.rest.create_message(channel, f"Joined `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"Joined unknown server.")

#leave
@bot.listen(hikari.GuildLeaveEvent)
async def on_guild_leave(event):
    guild = event.old_guild
    if guild is not None:
        await bot.rest.create_message(channel, f"Left `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"Left unknown server.")

#Core----------------------------------------------------------------------------------------------------------------------------------------
#message event
@bot.listen(hikari.MessageCreateEvent)
async def on_message(event: hikari.MessageCreateEvent):
    if not event.is_human:
        return
    if isinstance(event.content, str) and any(word in event.content.lower() for word in hearing):
        guild_id = event.guild_id
        if guild_id in custom_insults:
            all_responses = response + custom_insults[guild_id]
        else:
            all_responses = response
        selected_response = random.choice(all_responses)
        await event.message.respond(f"{selected_response}")
        guild = bot.cache.get_guild(event.guild_id) if event.guild_id else None
        guild_name = guild.name if guild else "DM"
        await bot.rest.create_message(channel, f"`keyword` was used in `{guild_name}`.")
        await asyncio.sleep(15)

#add insult
@bot.command
@lightbulb.command("addinsult", "Add a custom insult to a server of your choice.")
@lightbulb.implements(lightbulb.SlashCommand)
async def addinsult(ctx):
    if str(ctx.author.id) not in prem_users:
        await ctx.respond("To use this premium command, sign up as a [member](https://ko-fi.com/azaelbots). Premium commands exist to cover the bot's hosting costs.")
        return
    await ctx.respond("Enter the server ID where you want to add the insult:")

    def check_server_id(event):
        return event.author_id == ctx.author.id and event.channel_id == ctx.channel_id
    try:
        server_id_event = await bot.wait_for(hikari.MessageCreateEvent, timeout=60, predicate=check_server_id)
        server_id = int(server_id_event.content)
        await ctx.respond("Enter your insult string, ensuring it complies with Discord's TOS and does not contain discriminatory language (maximum 200 characters):")
        def check_insult_message(event):
            return event.author_id == ctx.author.id and event.channel_id == ctx.channel_id
        insult_message_event = await bot.wait_for(hikari.MessageCreateEvent, timeout=60, predicate=check_insult_message)
        insult = insult_message_event.content
        if len(insult) > 200:
            await ctx.respond("Your insult is too long. Keep it under 200 characters.")
            return
        if server_id not in custom_insults:
            custom_insults[server_id] = []
        custom_insults[server_id].append(insult)
        await ctx.respond(f"New insult added.")
        log_message = (
            f"`addinsult` invoked by user {ctx.author.id}\n"
            f"Received server ID: {server_id_event.content}\n"
            f"Received insult: {insult_message_event.content}\n"
            f"Updated custom_insults = {custom_insults}\n\n"
        )
        await bot.rest.create_message(1246889573141839934, content=log_message)
    except asyncio.TimeoutError:
        await ctx.respond("You took too long to respond.")
    except Exception as e:
        await ctx.respond("An error occurred while processing your request.")

#remove insult
@bot.command
@lightbulb.command("removeinsult", "Remove a custom insult from a server of your choice.")
@lightbulb.implements(lightbulb.SlashCommand)
async def removeinsult(ctx):
    if str(ctx.author.id) not in prem_users:
        await ctx.respond("To use this premium command, sign up as a [member](https://ko-fi.com/azaelbots). Premium commands exist to cover the bot's hosting costs.")
        return
    await ctx.respond("Enter the server ID where you want to remove the insult:")
    def check_server_id(event):
        return event.author_id == ctx.author.id and event.channel_id == ctx.channel_id
    try:
        server_id_event = await bot.wait_for(hikari.MessageCreateEvent, timeout=60, predicate=check_server_id)
        server_id = int(server_id_event.content)
        if server_id not in custom_insults or not custom_insults[server_id]:
            await ctx.respond(f"No insult found.")
            return
        insults_list = "\n".join(f"{i+1}. {insult}" for i, insult in enumerate(custom_insults[server_id]))
        await ctx.respond(f"Select the number to the left of the insult to remove from the server:\n{insults_list}")
        def check_insult_index(event):
            return event.author_id == ctx.author.id and event.channel_id == ctx.channel_id
        insult_index_event = await bot.wait_for(hikari.MessageCreateEvent, timeout=60, predicate=check_insult_index)
        insult_index = int(insult_index_event.content) - 1
        if insult_index < 0 or insult_index >= len(custom_insults[server_id]):
            await ctx.respond("Please select the number next to the insult.")
            return
        removed_insult = custom_insults[server_id].pop(insult_index)
        await ctx.respond("The selected insult has been removed.")
        log_message = (
            f"`removeinsult` invoked by user {ctx.author.id}\n"
            f"Removed insult: {removed_insult}\n"
            f"Updated custom_insults = {custom_insults}\n\n"
        )
        await bot.rest.create_message(1246889573141839934, content=log_message)
    except asyncio.TimeoutError:
        await ctx.respond("You took too long to respond.")
    except Exception as e:
        await ctx.respond("An error occurred while processing your request.")

#view insults
@bot.command
@lightbulb.command("viewinsults", "View custom insults added to a server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def viewinsults(ctx):
    if str(ctx.author.id) not in prem_users:
        await ctx.respond("To use this premium command, sign up as a [member](https://ko-fi.com/azaelbots). Premium commands exist to cover the bot's hosting costs.")
        return
    await ctx.respond("Enter the server ID where you want to view the added insults:")
    def check_server_id(event):
        return event.author_id == ctx.author.id and event.channel_id == ctx.channel_id
    try:
        server_id_event = await bot.wait_for(hikari.MessageCreateEvent, timeout=60, predicate=check_server_id)
        server_id = int(server_id_event.content)
        if server_id in custom_insults:
            insults_list = custom_insults[server_id]
            insults_text = "\n".join(insults_list)
            await ctx.respond(f"Custom insults in this server:\n{insults_text}")
        else:
            await ctx.respond(f"No custom insults found.")
        log_message = (
            f"`viewinsults` invoked by user {ctx.author.id}\n"
            f"Received server ID: {server_id_event.content}\n"
            f"Displayed insults: {custom_insults.get(server_id, 'No insults found')}\n\n"
        )
        await bot.rest.create_message(1246889573141839934, content=log_message)
    except asyncio.TimeoutError:
        await ctx.respond("You took too long to respond.")
    except Exception as e:
        await ctx.respond("An error occurred while processing your request.")

#insult command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("insult", "Generate a random insult.")
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

#MISC----------------------------------------------------------------------------------------------------------------------------------------
#help command
@bot.command
@lightbulb.add_cooldown(length=10, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("help", "You know what this is ;)")
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
        title="📚 Help 📚",
        description=(
            "**Core Commands:**\n"
            "**/help:** You just used this command.\n"
            "**/insult:** Generate a random insult.\n\n"
            "**Premium Commands:**\n"
            "**/addinsult:** Add a custom insult to a server of your choice.\n"
            "**/removeinsult:** Remove a custom insult you added.\n"
            "**/viewinsults:** View the custom insults you have added.\n"
            "Premium commands keep Insult Bot online, become a [member](https://ko-fi.com/azaelbots).\n\n"
            "**Miscellaneous Commands:**\n"
            "**/invite:** Invite the bot to your server.\n"
            "**/vote:** Vote on top.gg.\n"
            "**/support:** Join the support server.\n"
            "**/premium:** What is premium.\n"
            "**/more:** Check out more bots from me.\n"
            "**/privacy:** View our privacy policy."
        ),
        color=0x2B2D31
    )
    embed.set_footer("Join the support server if you need help.")
    await ctx.respond(embed=embed)
    thank_you_embed = hikari.Embed(
        title="Thank you!",
        description=(
            "If you like using Insult Bot, consider [voting](https://top.gg/bot/801431445452750879/vote) or leaving a [review](https://top.gg/bot/801431445452750879).\n"
            "To help keep Insult Bot online, consider becoming a [member](https://ko-fi.com/azaelbots)."
        ),
        color=0x2B2D31
    )
    await ctx.respond(embed=thank_you_embed)

#invite command
@bot.command
@lightbulb.add_cooldown(length=10, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("invite", "Invite the bot to your server.")
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
        title="Invite:",
        description=("[Invite the bot to your server.](https://discord.com/oauth2/authorize?client_id=801431445452750879&permissions=414464727104&scope=applications.commands%20bot)"),
        color=0x2f3136
    )
    await ctx.respond(embed=embed)

#vote command
@bot.command
@lightbulb.add_cooldown(length=10, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("vote", "Vote on top.gg.")
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
        title="Vote:",
        description=("[Vote on top.gg, thank you!](https://top.gg/bot/801431445452750879/vote)"),
        color=0x2B2D31
    )
    await ctx.respond(embed=embed)

#support command
@bot.command
@lightbulb.add_cooldown(length=10, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("support", "Join the support server.")
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
        title="Support Server:",
        description=("[Join the support server.](https://discord.com/invite/x7MdgVFUwa)"),
        color=0x2B2D31
    )
    await ctx.respond(embed=embed)

#premium command
@bot.command
@lightbulb.add_cooldown(length=10, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("premium", "What is premium.")
@lightbulb.implements(lightbulb.SlashCommand)
async def premium(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    embed = hikari.Embed(
        title="What is premium:",
        description=("With premium, you can use premium commands and skip cool-downs. Premium is important for supporting the bot's hosting costs.\nThe main functions of the bot will never be paywalled, but a few extra commands serve as an incentive to subscribe.\nIf you would like to keep the bot online and support me, [become a member](https://ko-fi.com/azaelbots).\nIt helps massively. ❤️"),
        color=0x2B2D31
    )
    await ctx.respond(embed=embed)

#more command
@bot.command
@lightbulb.add_cooldown(length=10, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("more", "More bots from me.")
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
        title="More:",
        description=("[Check out more bots from me.](https://top.gg/user/67067136345571328)"),
        color=0x2B2D31
    )
    await ctx.respond(embed=embed)

#privacy command
@bot.command
@lightbulb.add_cooldown(length=10, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("privacy", "Privacy policy statement.")
@lightbulb.implements(lightbulb.SlashCommand)
async def privacy(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(channel, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    embed = hikari.Embed(
		title="Privacy Policy:",
		description="The personal information of any user, including the message content it replies to, is not tracked by Insult Bot.\n\nThe user_id, server_id and added insults of premium members are stored to provide the user the with perks and is deleted once a user is no longer a member.\n\nJoin the [support server](https://discord.com/invite/x7MdgVFUwa) to request the deletion of your data.",
		color=0x2B2D31
	)
    await ctx.respond(embed=embed)

#error handling
@bot.listen(lightbulb.CommandErrorEvent)
async def on_error(event: lightbulb.CommandErrorEvent) -> None:
	if isinstance(event.exception, lightbulb.CommandInvocationError):
		await event.context.respond(f"Something went wrong, please try again.")
		raise event.exception

	exception = event.exception.__cause__ or event.exception

	if isinstance(exception, lightbulb.CommandIsOnCooldown):
		await event.context.respond(f"`/{event.context.command.name}` is on cooldown. Retry in `{exception.retry_after:.0f}` seconds. ⏱️\nCommands are ratelimited to prevent spam abuse which could bring the bot down. To remove cool-downs, become a [member](<https://ko-fi.com/azaelbots>).")
	else:
		raise exception

@bot.listen(hikari.StoppedEvent)
async def on_stopping(event: hikari.StoppedEvent) -> None:
    await topgg_client.close()

bot.run()