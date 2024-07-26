import hikari
import lightbulb
import random
import asyncio
import aiohttp
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

hearing_string = os.getenv("HEARING_LIST")
hearing = hearing_string.split(",")

response_string = os.getenv("RESPONSE_LIST")
response = response_string.split(",")

prohibited_keywords = os.getenv("PROHIBITED_WORDS")
prohibited_words = prohibited_keywords.split(",")

prem_users = ['364400063281102852','919005754130829352','1054440117705650217']
custom_insults = {'1193319104917024849': ['I love you redhaven', 'I love Redhaven', 'Redhaven is so good looking', 'yea sure', 'corny jawn', 'your ass', 'how was trouble', 'cum dumpster', 'Redhaven sucks', 'hawk tuah']}
custom_triggers = {'934644448187539517': ['dick', 'fuck', 'smd', 'motherfucker', 'bellend', 'report', 'pls']}
allowed_channels_per_guild = {'934644448187539517': ['1139231743682019408'], '1174927290694635522': ['1263132859808485447'], '1263396901898948630': ['1263396901898948632'], '1163488034117918801': ['1163689143818260501'], '857112618963566592': ['924728966739279882'], '365235912512372738': ['985163775856504862'], '1266054751577968722': ['1266117205175697418'], '1196598381057953904': ['1209033029377589328'], '1019632213278588928': ['1071145558263218326'], '1006195077409951864': []}
allowed_ai_channel_per_guild = {'1266054751577968722': ['1266117205175697418'], '665647946213228592': ['665647946213228595'], '1123033635587620874': ['1124345771622408202'], '1196598381057953904': ['1209033029377589328'], '934644448187539517': ['1266099301529161799'], '1006195077409951864': ['1264483050968846357', '1243873717260386325'], '857112618963566592': ['924728966739279882', '857112618963566595']}
custom_only_servers = []
user_response_count = {}
user_reset_time = {}

openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
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

    async def get_user_vote(self, user_id):
        url = f"https://top.gg/api/bots/{self.bot.get_me().id}/check?userId={user_id}"
        headers = {
            "Authorization": self.token
        }
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('voted') == 1
                else:
                    print(f"Failed to check user vote: {response.status}")
                    return False
        except Exception as e:
            print(f"An error occurred while checking user vote: {e}")
            return False

    async def close(self):
        await self.session.close()

topgg_token = os.getenv("TOPGG_TOKEN")
topgg_client = TopGGClient(bot, topgg_token)

async def generate_text(prompt):
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Answer questions with a mean attitude but still be helpful and keep responses very brief"},
                {"role": "user", "content": prompt}
            ],
            temperature=1,
            max_tokens=256,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        # Accessing the content correctly
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"An error occurred: {str(e)}"

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
        await bot.rest.create_message(1246886903077408838, f"Joined `{guild.name}`.")
    else:
        await bot.rest.create_message(1246886903077408838, f"Joined unknown server.")

#leave
@bot.listen(hikari.GuildLeaveEvent)
async def on_guild_leave(event):
    guild = event.old_guild
    if guild is not None:
        await bot.rest.create_message(1246886903077408838, f"Left `{guild.name}`.")
    else:
        await bot.rest.create_message(1246886903077408838, f"Left unknown server.")

# Core----------------------------------------------------------------------------------------------------------------------------------------
# General message event listener
def should_process_event(event: hikari.MessageCreateEvent) -> bool:
    if str(event.guild_id) in allowed_channels_per_guild:
        return str(event.channel_id) in allowed_channels_per_guild[str(event.guild_id)]
    return True

@bot.listen(hikari.MessageCreateEvent)
async def on_general_message(event: hikari.MessageCreateEvent):
    if not event.is_human or not should_process_event(event):
        return

    message_content = event.content.lower() if isinstance(event.content, str) else ""
    guild_id = str(event.guild_id)

    if guild_id in custom_only_servers:
        if guild_id in custom_insults and any(word in message_content for word in custom_triggers.get(guild_id, [])):
            all_responses = custom_insults[guild_id]
        else:
            return
    else:
        all_responses = response + custom_insults.get(guild_id, [])

    if any(word in message_content for word in hearing):
        selected_response = random.choice(all_responses)
        try:
            await event.message.respond(selected_response)
        except hikari.errors.BadRequestError:
            pass
        except hikari.errors.ForbiddenError:
            pass
        await asyncio.sleep(15)

    if guild_id in custom_triggers:
        for trigger in custom_triggers[guild_id]:
            if trigger in message_content:
                selected_response = random.choice(all_responses)
                try:
                    await event.message.respond(selected_response)
                    guild_name = event.get_guild().name if event.get_guild() else "DM"
                except hikari.errors.ForbiddenError:
                    pass
                await asyncio.sleep(15)
                break

# AI response message event listener
@bot.listen(hikari.MessageCreateEvent)
async def on_ai_message(event: hikari.MessageCreateEvent):
    if not event.message.author.is_bot:
        content = event.message.content or ""

        bot_id = bot.get_me().id
        bot_mention = f"<@{bot_id}>"

        mentions_bot = bot_mention in content
        references_message = event.message.message_reference is not None

        if references_message:
            referenced_message_id = event.message.message_reference.id
            try:
                referenced_message = await bot.rest.fetch_message(event.channel_id, referenced_message_id)
                is_reference_to_bot = referenced_message.author.id == bot_id
            except hikari.errors.ForbiddenError:
                is_reference_to_bot = False
            except hikari.errors.NotFoundError:
                is_reference_to_bot = False
        else:
            is_reference_to_bot = False

        if mentions_bot or is_reference_to_bot:
            guild_id = str(event.guild_id)
            channel_id = str(event.channel_id)

            if guild_id in allowed_ai_channel_per_guild and channel_id in allowed_ai_channel_per_guild[guild_id]:
                user_id = str(event.message.author.id)

                current_time = asyncio.get_event_loop().time()
                reset_time = user_reset_time.get(user_id, 0)

                if current_time - reset_time > 21600:  # 6 hours in seconds
                    user_response_count[user_id] = 0
                    user_reset_time[user_id] = current_time

                if user_id not in prem_users:
                    if user_id not in user_response_count:
                        user_response_count[user_id] = 0
                        user_reset_time[user_id] = current_time

                    if user_response_count[user_id] >= 8:
                        has_voted = await topgg_client.get_user_vote(user_id)
                        if not has_voted:
                            embed = hikari.Embed(
                                title="Limit Reached :(",
                                description=(
                                    f"{event.message.author.mention}, limit resets in `6 hours`.\n\n"
                                    "If you want to continue for free, [vote](https://top.gg/bot/801431445452750879/vote) to gain unlimited access for the next 12 hours or become a [member](https://ko-fi.com/azaelbots) for $1.99 a month.\n\n"
                                    "I will never completely paywall my bot, but limits like this help lower running costs and keep the bot running. ❤️\n\n"
                                    "*Any memberships bought can be refunded within 3 days of purchase.*"
                                ),
                                color=0x2B2D31
                            )
                            embed.set_image("https://i.imgur.com/hxZb7Sq.gif")
                            await event.message.respond(embed=embed)
                            await bot.rest.create_message(1246886903077408838, f"Voting message was sent in `{event.get_guild().name}`")
                        else:
                            message_content = content.strip()
                            async with bot.rest.trigger_typing(channel_id):
                                ai_response = await generate_text(message_content)

                            if user_id not in prem_users:
                                user_response_count[user_id] += 1

                            user_mention = event.message.author.mention
                            response_message = f"{user_mention} {ai_response}"
                            await bot.rest.create_message(1246886903077408838, f"`ai response` was sent in `{event.get_guild().name}`")
                            await event.message.respond(response_message)

                    else:
                        message_content = content.strip()
                        async with bot.rest.trigger_typing(channel_id):
                            ai_response = await generate_text(message_content)

                        if user_id not in prem_users:
                            user_response_count[user_id] += 1

                        user_mention = event.message.author.mention
                        response_message = f"{user_mention} {ai_response}"
                        await bot.rest.create_message(1246886903077408838, f"`ai response` was sent in `{event.get_guild().name}`")
                        await event.message.respond(response_message)
                else:
                    message_content = content.strip()
                    async with bot.rest.trigger_typing(channel_id):
                        ai_response = await generate_text(message_content)

                    user_mention = event.message.author.mention
                    response_message = f"{user_mention} {ai_response}"
                    await bot.rest.create_message(1246886903077408838, f"`ai response` was sent in `{event.get_guild().name}`")
                    await event.message.respond(response_message)

            else:
                await bot.rest.create_message(1246886903077408838, f"`/setchannel` command was sent in `{event.get_guild().name}`")
                try:
                    await event.message.respond("Set a specific channel for AI responses using the /setchannel command or ask a trusted admin to do so.")
                except hikari.errors.ForbiddenError:
                    pass

# Insult command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("insult", "Type out an insult you want the bot to send. (Optional)", type=hikari.OptionType.STRING, required=False)
@lightbulb.option("user", "Ping a user to insult. (Optional)", type=hikari.OptionType.USER, required=False)
@lightbulb.option("channel", "The channel to send the insult in. (Optional)", type=hikari.OptionType.CHANNEL, channel_types=[hikari.ChannelType.GUILD_TEXT], required=False)
@lightbulb.command("insult", "Send an insult to someone.")
@lightbulb.implements(lightbulb.SlashCommand)
async def insult(ctx):
    channel = ctx.options.channel
    user = ctx.options.user
    insult = ctx.options.insult
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
        selected_response = insult if insult else random.choice(all_responses)
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
@lightbulb.option("type", "Select whether to enable 'chatbot' or 'keywords' responses in the channel.", choices=["chatbot", "keywords"], type=hikari.OptionType.STRING, required=True)
@lightbulb.command("setchannel", "Restrict Insult Bot and AI Bot to particular channel(s).")
@lightbulb.implements(lightbulb.SlashCommand)
async def setchannel(ctx):
    guild_id = str(ctx.guild_id)

    member = await ctx.bot.rest.fetch_member(ctx.guild_id, ctx.author.id)
    if not any(role.permissions & hikari.Permissions.ADMINISTRATOR for role in member.get_roles()):
        await ctx.respond("Ask your admins to set this up for you. 🤦")
        return

    if guild_id not in allowed_channels_per_guild:
        allowed_channels_per_guild[guild_id] = []
    if guild_id not in allowed_ai_channel_per_guild:
        allowed_ai_channel_per_guild[guild_id] = []

    toggle = ctx.options.toggle
    channel_id = str(ctx.options.channel.id) if ctx.options.channel else None
    channel_type = ctx.options.type

    if toggle == "on":
        if channel_type == "keywords":
            if channel_id and channel_id not in allowed_channels_per_guild[guild_id]:
                allowed_channels_per_guild[guild_id].append(channel_id)
                await ctx.respond(f"Insult Bot will only respond with keywords in <#{channel_id}>.")
            elif channel_id in allowed_channels_per_guild[guild_id]:
                await ctx.respond(f"Insult Bot is already restricted to keywords in <#{channel_id}>.")
            else:
                await ctx.respond("Please specify a valid channel.")
        elif channel_type == "chatbot":
            if channel_id and channel_id not in allowed_ai_channel_per_guild[guild_id]:
                allowed_ai_channel_per_guild[guild_id].append(channel_id)
                await ctx.respond(f"Insult Bot will only respond as a chatbot in <#{channel_id}>.")
            elif channel_id in allowed_ai_channel_per_guild[guild_id]:
                await ctx.respond(f"Insult Bot is already a chatbot in <#{channel_id}>.")
            else:
                await ctx.respond("Please specify a valid channel.")
    elif toggle == "off":
        if channel_type == "keywords" and channel_id in allowed_channels_per_guild[guild_id]:
            allowed_channels_per_guild[guild_id].remove(channel_id)
            await ctx.respond(f"Bot's restriction to send keywords in <#{channel_id}> has been removed.")
        elif channel_type == "chatbot" and channel_id in allowed_ai_channel_per_guild[guild_id]:
            allowed_ai_channel_per_guild[guild_id].remove(channel_id)
            await ctx.respond(f"Bot's restriction as a chatbot in <#{channel_id}> has been removed.")
        else:
            await ctx.respond("Channel is not currently restricted.")
    else:
        await ctx.respond("Invalid toggle. Use `/setchannel on <#channel>` or `/setchannel off <#channel>`.")

    log_message = (
        f"`setchannel` invoked by user {ctx.author.id}\n"
        f"Received server_id: {guild_id}\n"
        f"Received channel_id: {channel_id}\n"
        f"Type: {channel_type.capitalize()}\n"
        f"allowed_channels_per_guild = {allowed_channels_per_guild}\n"
        f"allowed_ai_channel_per_guild = {allowed_ai_channel_per_guild}\n\n"
    )
    try:
        await bot.rest.create_message(1246889573141839934, content=log_message)
    except Exception as e:
        print(f"Failed to send log message: {e}")

# Premium----------------------------------------------------------------------------------------------------------------------------------------
# Add insult command
@bot.command
@lightbulb.option("insult", "Add your insult, ensuring it complies with Discord's TOS. (maximum 200 characters)", type=str)
@lightbulb.command("addinsult", "Add a custom insult to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def addinsult(ctx):
    if str(ctx.author.id) not in prem_users:
        embed = hikari.Embed(
            title="You found a premium command :)",
            description=(
                "To add custom insults to your server, please consider becoming a [member](https://ko-fi.com/azaelbots) for only $1.99 a month. I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
                ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)
        await bot.rest.create_message(1246886903077408838, f"`{ctx.author.id}` tried to invoke `{ctx.command.name}`")
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
        embed = hikari.Embed(
            title="You found a premium command :)",
            description=(
                "To remove custom insults added to your server, please consider becoming a [member](https://ko-fi.com/azaelbots) for only $1.99 a month. I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
                ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)
        await bot.rest.create_message(1246886903077408838, f"`{ctx.author.id}` tried to invoke `{ctx.command.name}`")
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
        embed = hikari.Embed(
            title="You found a premium command :)",
            description=(
                "To view custom insults added to your server, please consider becoming a [member](https://ko-fi.com/azaelbots) for only $1.99 a month. I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
                ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)
        await bot.rest.create_message(1246886903077408838, f"`{ctx.author.id}` tried to invoke `{ctx.command.name}`")
        return

    server_id = str(ctx.guild_id)

    if server_id in custom_insults:
        insults_list = custom_insults[server_id]
        insults_text = "\n".join(insults_list)
        embed = hikari.Embed(
            title="🔹 Custom Insults 🔹",
            description=insults_text,
            color=0x2B2D31
        )
        await ctx.respond(embed=embed)
    else:
        await ctx.respond("No custom insults found.")

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
        embed = hikari.Embed(
            title="You found a premium command :)",
            description=(
                "To add custom triggers to your server, please consider becoming a [member](https://ko-fi.com/azaelbots) for only $1.99 a month. I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
                ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)
        await bot.rest.create_message(1246886903077408838, f"`{ctx.author.id}` tried to invoke `{ctx.command.name}`")
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
        embed = hikari.Embed(
            title="You found a premium command :)",
            description=(
                "To remove custom triggers added to your server, please consider becoming a [member](https://ko-fi.com/azaelbots) for only $1.99 a month. I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
                ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)
        await bot.rest.create_message(1246886903077408838, f"`{ctx.author.id}` tried to invoke `{ctx.command.name}`")
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
        embed = hikari.Embed(
            title="You found a premium command :)",
            description=(
                "To view custom triggers added to your server, please consider becoming a [member](https://ko-fi.com/azaelbots) for only $1.99 a month. I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
                ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)
        await bot.rest.create_message(1246886903077408838, f"`{ctx.author.id}` tried to invoke `{ctx.command.name}`")
        return

    server_id = str(ctx.guild_id)

    if server_id in custom_triggers:
        triggers_list = custom_triggers[server_id]
        triggers_text = "\n".join(triggers_list)
        embed = hikari.Embed(
            title="🔹 Custom Triggers 🔹",
            description=triggers_text,
            color=0x2B2D31
        )
        await ctx.respond(embed=embed)
    else:
        await ctx.respond("No custom triggers found.")

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
    if str(ctx.author.id) not in prem_users:
        embed = hikari.Embed(
            title="You found a premium command :)",
            description=(
                "To toggle custom only triggers/insults to your server, please consider becoming a [member](https://ko-fi.com/azaelbots) for only $1.99 a month. I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
                ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)
        await bot.rest.create_message(1246886903077408838, f"`{ctx.author.id}` tried to invoke `{ctx.command.name}`")
        return

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
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    embed = hikari.Embed(
        title="📚 Help 📚",
        description=(
            "**Reply or ping Insult Bot to talk.**\n\n"
            "**Core Commands:**\n"
            "**/help:** You just used this command.\n"
            "**/insult:** Send an insult to someone.\n"
            "**/setchannel:** Restrict Insult Bot to particular channel(s).\n\n"
            "**Premium Commands:**\n"
            "**/addinsult:** Add a custom insult to a server of your choice.\n"
            "**/removeinsult:** Remove a custom insult you added.\n"
            "**/viewinsults:** View the custom insults you have added.\n"
            "**/addtrigger:** Add a custom trigger to a server of your choice.\n"
            "**/removetrigger:** Remove a custom trigger from a server of your choice.\n"
            "**/viewtriggers:** View custom triggers added to a server.\n"
            "**/customonly:** Set custom insults and triggers only.\n\n"
            "**To use the commands above and help keep the bot running, please consider becoming a [member](https://ko-fi.com/azaelbots) for  $1.99 a month. ❤️**\n\n"
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

#invite command
@bot.command
@lightbulb.add_cooldown(length=10, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("invite", "Invite the bot to your server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def invite(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used.")
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
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used.")
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
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    embed = hikari.Embed(
        title="Support Server:",
        description=("[Join the support server.](<https://discord.com/invite/x7MdgVFUwa>)"),
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
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used.")
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    embed = hikari.Embed(
        title="What is premium:",
        description=("With premium, you can use premium commands and skip cool-downs. Premium is important for supporting the bot's hosting costs.\nThe main functions of the bot will never be paywalled, but a few extra commands serve as an incentive to subscribe.\nIf you would like to keep the bot online and support me, become a [member](https://ko-fi.com/azaelbots).\nIt helps massively. ❤️"),
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
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used.")
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
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used.")
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

#top.gg stop
@bot.listen(hikari.StoppedEvent)
async def on_stopping(event: hikari.StoppedEvent) -> None:
    await topgg_client.close()

bot.run()