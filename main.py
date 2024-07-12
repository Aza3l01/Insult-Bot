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

prohibited_keywords = os.getenv("PROHIBITED_WORDS")
prohibited_words = prohibited_keywords.split(",")

prem_users = ['364400063281102852','919005754130829352','1054440117705650217']

custom_insults = {'1193319104917024849': ['I love you redhaven', 'I love Redhaven', 'Redhaven is so good looking', 'yea sure', 'corny jawn', 'your ass', 'how was trouble', 'cum dumpster', 'Redhaven sucks', 'hawk tuah']}

custom_triggers = {'934644448187539517': ['dick', 'fuck', 'smd', 'motherfucker', 'bellend', 'report', 'pls'], '1193319104917024849': ['stream', 'loading', 'work', 'question']}

allowed_channels = ['1139231743682019408', '1187829517994172488']

custom_only_servers = []

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

#count update
@bot.listen(hikari.StartedEvent)
async def on_starting(event: hikari.StartedEvent) -> None:
    while True:
        guilds = await bot.rest.fetch_my_guilds()
        server_count = len(guilds)
        await bot.update_presence(
            activity=hikari.Activity(
                name=f"{server_count} servers! | /help",
                type=hikari.ActivityType.WATCHING,
            )
        )
        await topgg_client.post_guild_count(server_count)
        await asyncio.sleep(3600)

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

# Core----------------------------------------------------------------------------------------------------------------------------------------
# Message event
def should_process_event(event: hikari.MessageCreateEvent) -> bool:
    if not allowed_channels:
        return True
    return str(event.channel_id) in allowed_channels

# Message event listener
@bot.listen(hikari.MessageCreateEvent)
async def on_message(event: hikari.MessageCreateEvent):
    if not event.is_human or not should_process_event(event):
        return

    message_content = event.content.lower() if isinstance(event.content, str) else ""
    guild_id = str(event.guild_id)

    # Check if the server is in custom-only mode
    if guild_id in custom_only_servers:
        if guild_id in custom_insults and any(word in message_content for word in custom_triggers.get(guild_id, [])):
            all_responses = custom_insults[guild_id]
        else:
            return  # Ignore non-custom triggers and insults in custom-only mode
    else:
        all_responses = response + custom_insults.get(guild_id, [])

    if any(word in message_content for word in hearing):
        selected_response = random.choice(all_responses)
        try:
            await event.message.respond(f"{selected_response}")
            guild_name = event.get_guild().name if event.get_guild() else "DM"
            await bot.rest.create_message(channel, f"`Keyword` was used in {guild_name}.")
        except hikari.errors.ForbiddenError:
            pass
        await asyncio.sleep(15)

    if guild_id in custom_triggers:
        for trigger in custom_triggers[guild_id]:
            if trigger in message_content:
                selected_response = random.choice(all_responses)
                try:
                    await event.message.respond(f"{selected_response}")
                    guild_name = event.get_guild().name if event.get_guild() else "DM"
                    await bot.rest.create_message(channel, f"`Trigger` was used in {guild_name}.")
                except hikari.errors.ForbiddenError:
                    pass
                await asyncio.sleep(15)
                break

# Insult command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("insult", "Type out an insult you want the bot to send. (Optional)", type=hikari.OptionType.STRING, required=False)
@lightbulb.option("user", "Ping a user to insult. (Optional)", type=hikari.OptionType.USER, required=False)
@lightbulb.option("channel", "The channel to send the insult in. (Optional)", type=hikari.OptionType.CHANNEL, channel_types=[hikari.ChannelType.GUILD_TEXT], required=False)
@lightbulb.command("insult", "Generate a random insult.")
@lightbulb.implements(lightbulb.SlashCommand)
async def insult(ctx):
    channel = ctx.options.channel
    user = ctx.options.user
    custom_insult = ctx.options.custom_insult
    target_channel = ctx.channel_id if channel is None else channel.id

    try:
        guild = ctx.get_guild()
        if guild is not None:
            await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used in `{guild.name}`.")
        else:
            await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used.")
        
        if any(word in str(ctx.author.id) for word in prem_users):
            await ctx.command.cooldown_manager.reset_cooldown(ctx)
        
        guild_id = str(ctx.guild_id)
        if guild_id in custom_insults:
            all_responses = response + custom_insults[guild_id]
        else:
            all_responses = response

        selected_response = custom_insult if custom_insult else random.choice(all_responses)
        message = f"{user.mention}, {selected_response}" if user else selected_response

        if channel is None:
            await ctx.respond(message)
        else:
            await bot.rest.create_message(target_channel, message)
            await ctx.respond("Message was sent.")

    except hikari.errors.NotFoundError:
        await ctx.respond("I don't have access to this channel.")
    except hikari.errors.ForbiddenError:
        await ctx.respond("I don't have permission to send messages in that channel.")
    except Exception as e:
        await ctx.respond(f"An error occurred: {e}")

# Setchannel command
@bot.command
@lightbulb.add_cooldown(length=10, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("toggle", "Toggle Insult Bot on/off in the selected channel.", choices=["on", "off"], type=hikari.OptionType.STRING)
@lightbulb.option("channel", "Select a channel to proceed.", type=hikari.OptionType.CHANNEL, channel_types=[hikari.ChannelType.GUILD_TEXT])
@lightbulb.command("setchannel", "Restrict Insult Bot to particular channel(s).")
@lightbulb.implements(lightbulb.SlashCommand)
async def setchannel(ctx):
    global allowed_channels

    toggle = ctx.options.toggle
    channel_id = str(ctx.options.channel.id) if ctx.options.channel else None

    if toggle == "on":
        if channel_id:
            allowed_channels.append(channel_id)
            await ctx.respond(f"Insult Bot will only respond in <#{channel_id}>.")
        else:
            await ctx.respond("Please specify a valid channel.")
    elif toggle == "off":
        if channel_id in allowed_channels:
            allowed_channels.remove(channel_id)
            await ctx.respond(f"Insult Bot's restriction for <#{channel_id}> has been removed.")
        else:
            await ctx.respond("Channel is not currently restricted.")
    else:
        await ctx.respond("Invalid toggle. Use `/setchannel on <#channel>` or `/setchannel off <#channel>`.")
    
    server_id = str(ctx.guild_id)
    log_message = (
        f"`setchannel` invoked by user {ctx.author.id}\n"
        f"Received server_id: {server_id}\n"
        f"Received channel_id: {channel_id}\n"
        f"allowed_channels = {allowed_channels}\n\n"
    )
    await bot.rest.create_message(1246889573141839934, content=log_message)

# Premium----------------------------------------------------------------------------------------------------------------------------------------
# Add insult command
@bot.command
@lightbulb.option("insult", "Add your insult, ensuring it complies with Discord's TOS. (maximum 200 characters)", type=str)
@lightbulb.command("addinsult", "Add a custom insult to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def addinsult(ctx):
    if str(ctx.author.id) not in prem_users:
        await ctx.respond("To use this premium command, become a [member](https://ko-fi.com/azaelbots). Premium commands exist to cover the bot's hosting costs.")
        return

    server_id = str(ctx.guild_id)
    insult = ctx.options.insult

    if len(insult) > 200:
        await ctx.respond("Your insult is too long. Keep it under 200 characters.")
        return

    if any(prohibited_word in insult.lower() for prohibited_word in prohibited_words):
        await ctx.respond("Your insult does not comply with Discord's TOS.")
        return

    if server_id not in custom_insults:
        custom_insults[server_id] = []

    custom_insults[server_id].append(insult)
    await ctx.respond(f"New insult added.")

    log_message = (
        f"`addinsult` invoked by user {ctx.author.id}\n"
        f"Received server_id: {server_id}\n"
        f"Received insult: {insult}\n"
        f"custom_insults = {custom_insults}\n\n"
    )
    await bot.rest.create_message(1246889573141839934, content=log_message)

# Remove insult command
@bot.command
@lightbulb.option("insult", "The insult to remove.", type=str)
@lightbulb.command("removeinsult", "Remove a custom insult from this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def removeinsult(ctx):
    if str(ctx.author.id) not in prem_users:
        await ctx.respond("To use this premium command, become a [member](https://ko-fi.com/azaelbots). Premium commands exist to cover the bot's hosting costs.")
        return

    server_id = str(ctx.guild_id)
    insult_to_remove = ctx.options.insult

    if server_id not in custom_insults or not custom_insults[server_id]:
        await ctx.respond(f"No insults found.")
        return

    if insult_to_remove not in custom_insults[server_id]:
        await ctx.respond("Insult not found in the list.")
        return

    custom_insults[server_id].remove(insult_to_remove)
    await ctx.respond("The selected insult has been removed.")

    log_message = (
        f"`removeinsult` invoked by user {ctx.author.id}\n"
        f"Removed insult: {insult_to_remove}\n"
        f"custom_insults = {custom_insults}\n\n"
    )
    await bot.rest.create_message(1246889573141839934, content=log_message)

# View insults command
@bot.command
@lightbulb.command("viewinsults", "View custom insults added to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def viewinsults(ctx):
    if str(ctx.author.id) not in prem_users:
        await ctx.respond("To use this premium command, become a [member](https://ko-fi.com/azaelbots). Premium commands exist to cover the bot's hosting costs.")
        return

    server_id = str(ctx.guild_id)

    if server_id in custom_insults:
        insults_list = custom_insults[server_id]
        insults_text = "\n".join(insults_list)
        await ctx.respond(f"Custom insults in this server:\n{insults_text}")
    else:
        await ctx.respond(f"No custom insults found.")

    log_message = (
        f"`viewinsults` invoked by user {ctx.author.id}\n"
        f"Received server ID: {server_id}\n"
        f"Displayed insults: {custom_insults.get(server_id, 'No insults found')}\n\n"
    )
    await bot.rest.create_message(1246889573141839934, content=log_message)

# Add trigger command
@bot.command
@lightbulb.option("trigger", "Add your trigger, ensuring it complies with Discord's TOS. (maximum 200 characters)", type=str)
@lightbulb.command("addtrigger", "Add a custom trigger to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def addtrigger(ctx):
    if str(ctx.author.id) not in prem_users:
        await ctx.respond("To use this premium command, become a [member](https://ko-fi.com/azaelbots). Premium commands exist to cover the bot's hosting costs.")
        return

    server_id = str(ctx.guild_id)
    trigger = ctx.options.trigger

    if len(trigger) > 200:
        await ctx.respond("Your trigger is too long. Keep it under 200 characters.")
        return

    if server_id not in custom_triggers:
        custom_triggers[server_id] = []

    custom_triggers[server_id].append(trigger)
    await ctx.respond(f"New trigger added.")

    log_message = (
        f"`addtrigger` invoked by user {ctx.author.id}\n"
        f"Received server_id: {server_id}\n"
        f"Received trigger: {trigger}\n"
        f"custom_triggers = {custom_triggers}\n\n"
    )
    await bot.rest.create_message(1246889573141839934, content=log_message)

# Remove trigger command
@bot.command
@lightbulb.option("trigger", "The trigger to remove.", type=str)
@lightbulb.command("removetrigger", "Remove a custom trigger from this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def removetrigger(ctx):
    if str(ctx.author.id) not in prem_users:
        await ctx.respond("To use this premium command, become a [member](https://ko-fi.com/azaelbots). Premium commands exist to cover the bot's hosting costs.")
        return

    server_id = str(ctx.guild_id)
    trigger_to_remove = ctx.options.trigger

    if server_id not in custom_triggers or not custom_triggers[server_id]:
        await ctx.respond(f"No triggers found.")
        return

    if trigger_to_remove not in custom_triggers[server_id]:
        await ctx.respond("Trigger not found in the list.")
        return

    custom_triggers[server_id].remove(trigger_to_remove)
    await ctx.respond("The selected trigger has been removed.")

    log_message = (
        f"`removetrigger` invoked by user {ctx.author.id}\n"
        f"Removed trigger: {trigger_to_remove}\n"
        f"custom_triggers = {custom_triggers}\n\n"
    )
    await bot.rest.create_message(1246889573141839934, content=log_message)

# View triggers command
@bot.command
@lightbulb.command("viewtriggers", "View custom triggers added to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def viewtriggers(ctx):
    if str(ctx.author.id) not in prem_users:
        await ctx.respond("To use this premium command, become a [member](https://ko-fi.com/azaelbots). Premium commands exist to cover the bot's hosting costs.")
        return

    server_id = str(ctx.guild_id)

    if server_id in custom_triggers:
        triggers_list = custom_triggers[server_id]
        triggers_text = "\n".join(triggers_list)
        await ctx.respond(f"Custom triggers in this server:\n{triggers_text}")
    else:
        await ctx.respond(f"No custom triggers found.")

    log_message = (
        f"`viewtriggers` invoked by user {ctx.author.id}\n"
        f"Received server ID: {server_id}\n"
        f"Displayed triggers: {custom_triggers.get(server_id, 'No triggers found')}\n\n"
    )
    await bot.rest.create_message(1246889573141839934, content=log_message)

# Custom only toggle command
@bot.command
@lightbulb.add_cooldown(length=10, uses=1, bucket=lightbulb.GuildBucket)
@lightbulb.option("toggle", "Toggle custom insults and triggers only mode on/off.", choices=["on", "off"], type=hikari.OptionType.STRING)
@lightbulb.command("customonly", "Set custom insults and triggers only.")
@lightbulb.implements(lightbulb.SlashCommand)
async def customonly(ctx):
    global custom_only_servers

    server_id = str(ctx.guild_id)

    if ctx.options.toggle == "on":
        if server_id not in custom_only_servers:
            custom_only_servers.append(server_id)
            await ctx.respond(f"Custom insults and triggers only mode enabled for this server.")
        else:
            await ctx.respond(f"Custom insults and triggers only mode is already enabled for this server.")
    elif ctx.options.toggle == "off":
        if server_id in custom_only_servers:
            custom_only_servers.remove(server_id)
            await ctx.respond(f"Custom insults and triggers only mode disabled for this server.")
        else:
            await ctx.respond(f"Custom insults and triggers only mode is not enabled for this server.")
    
    log_message = (
        f"`customonly` invoked by user {ctx.author.id}\n"
        f"Received server ID: {server_id}\n"
        f"custom_only_servers = {custom_only_servers}\n\n"
    )
    await bot.rest.create_message(1246889573141839934, content=log_message)

# MISC----------------------------------------------------------------------------------------------------------------------------------------
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
            "**/insult:** Generate a random insult.\n"
            "**/setchannel:** Restrict Insult Bot to particular channel(s).\n\n"
            "**Premium Commands:**\n"
            "**/addinsult:** Add a custom insult to a server of your choice.\n"
            "**/removeinsult:** Remove a custom insult you added.\n"
            "**/viewinsults:** View the custom insults you have added.\n"
            "**/addtrigger:** Add a custom trigger to a server of your choice.\n"
            "**/removetrigger:** Remove a custom trigger from a server of your choice.\n"
            "**/viewtriggers:** View custom triggers added to a server.\n"
            "**/customonly:** Set custom insults and triggers only.\n\n"
            "**Premium commands keep Insult Bot online, consider becoming a [member](https://ko-fi.com/azaelbots).**\n\n"
            "**Miscellaneous Commands:**\n"
            "**/invite:** Invite the bot to your server.\n"
            "**/vote:** Vote on top.gg.\n"
            "**/support:** Join the support server.\n"
            "**/premium:** Learn more about the premium version of the bot.\n"
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
		description="The personal information of any user, including the message content it replies to, is not tracked by Insult Bot. The channel_id alone is stored when added by using the /setchannel command, and it is stored only while this command is active in your server.\n\nThe user_id, server_id and added insults of premium members are stored to provide the user the with perks and is deleted once a user is no longer a member.\n\nJoin the [support server](https://discord.com/invite/x7MdgVFUwa) to request the deletion of your data.",
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