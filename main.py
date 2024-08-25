import hikari
import lightbulb
import random
import asyncio
import aiohttp
import os
import re
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
hearing = [item for item in os.getenv("HEARING_LIST", "").split(",") if item]
response = [item for item in os.getenv("RESPONSE_LIST", "").split(",") if item]
prohibited_words = [item for item in os.getenv("PROHIBITED_WORDS", "").split(",") if item]

DATA_FILE = 'data.json'

def load_data():
    try:
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "prem_users": {},
            "used_free_trial": [],
            "free_trial_start_time": {},
            "user_memory_preferences": {},
            "user_conversation_memory": {},
            "custom_only_servers": [],
            "user_custom_styles": {},
            "allowed_channels_per_guild": {},
            "allowed_ai_channel_per_guild": {},
            "custom_insults": {},
            "custom_triggers": {},
            "autorespond_servers": {}
        }

def save_data(data):
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def update_data(new_data):
    data = load_data()
    data.update(new_data)
    save_data(data)

data = load_data()

# Load data
prem_users = data.get('prem_users', {})
used_free_trial = data.get('used_free_trial', [])
free_trial_start_time = data.get('free_trial_start_time', {})
user_memory_preferences = data.get('user_memory_preferences', {})
user_conversation_memory = data.get('user_conversation_memory', {})
custom_only_servers = data.get('custom_only_servers', [])
custom_insults = data.get('custom_insults', {})
custom_triggers = data.get('custom_triggers', {})
user_custom_styles = data.get('user_custom_styles', {})
allowed_channels_per_guild = data.get('allowed_channels_per_guild', {})
allowed_ai_channel_per_guild = data.get('allowed_ai_channel_per_guild', {})
autorespond_servers = data.get('autorespond_servers', {})

# Nonpersistent data
prem_email = ["test@gmail.com"]
user_reset_time = {}
user_response_count = {}

# Tokens
openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
bot = lightbulb.BotApp(
	intents = hikari.Intents.ALL_UNPRIVILEGED | hikari.Intents.GUILD_MESSAGES | hikari.Intents.MESSAGE_CONTENT,
	token=os.getenv("BOT_TOKEN")
)

# # Top.gg
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

# AI
async def generate_text(prompt, user_id=None):
    try:
        data = load_data()
        
        system_message = "Answer questions with a mean attitude but still be helpful and keep responses very brief"
        
        if user_id and user_id in data.get('user_custom_styles', {}):
            system_message = data['user_custom_styles'][user_id]
        
        messages = [{"role": "system", "content": system_message}]
        
        if user_id and user_id in data.get('user_conversation_memory', {}):
            messages.extend(data['user_conversation_memory'][user_id])
        
        messages.append({"role": "user", "content": prompt})
        
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=1,
            max_tokens=256,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        if user_id and data['user_memory_preferences'].get(user_id, False):
            if user_id not in data['user_conversation_memory']:
                data['user_conversation_memory'][user_id] = []
            data['user_conversation_memory'][user_id].append({"role": "user", "content": prompt})
            data['user_conversation_memory'][user_id].append({"role": "assistant", "content": ai_response})
            save_data(data)
        
        return ai_response
    except Exception as e:
        return f"An error occurred: {str(e)}"

# Email
@bot.listen(hikari.MessageCreateEvent)
async def on_message(event: hikari.MessageCreateEvent) -> None:
    if event.channel_id == 1266481246121234554:
        email = event.message.content.strip()
        if re.match(r"[^@]+@[^@]+\.[^@]+", email):
            if email not in prem_email:
                prem_email.append(email)
                await bot.rest.create_message(1246886903077408838, f"prem_email = {prem_email}")
            else:
                await bot.rest.create_message(1246886903077408838, f"prem_email list = {prem_email}")
        else:
            await bot.rest.create_message(1246886903077408838, "The provided email is invalid.")

# Presence
@bot.listen(hikari.StartedEvent)
async def on_starting(event: hikari.StartedEvent) -> None:
    asyncio.create_task(check_expired_trials())
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

# Expiration check
async def check_expired_trials():
    while True:
        current_time = asyncio.get_event_loop().time()
        expired_users = []
        data = load_data()

        for user_id, start_time in data['free_trial_start_time'].items():
            if current_time - start_time > 432000:
                expired_users.append(user_id)

        for user_id in expired_users:
            if user_id in data['prem_users']:
                server_ids = list(data['prem_users'][user_id])

                for server_id in server_ids:
                    if server_id in data['custom_only_servers']:
                        data['custom_only_servers'].remove(server_id)

                    if server_id in data['custom_insults']:
                        del data['custom_insults'][server_id]

                    if server_id in data.get('autorespond_servers', {}):
                        del data['autorespond_servers'][server_id]

                del data['prem_users'][user_id]
                data['user_conversation_memory'].pop(user_id, None)

            data['free_trial_start_time'].pop(user_id, None)

            try:
                user = await bot.rest.fetch_user(int(user_id))
                embed = hikari.Embed(
                    title="⌛ Free Trial Ending Soon ⌛",
                    description=(
                        "**You'll Soon Lose Access To Premium Commands Like:**\n"
                        "• Unlimited responses from Insult Bot.\n"
                        "• Have Insult Bot repond to every message in set channel(s).\n"
                        "• Add custom insults.\n"
                        "• Insult Bot will remember your conversations.\n"
                        "• Remove cool-downs.\n"
                        "**And Support Server-related Perks Like:**\n"
                        "• Access to behind-the-scenes Discord channels.\n"
                        "• Have a say in the development of Insult Bot.\n"
                        "• Supporter-exclusive channels.\n\n"
                        "For privacy reasons, the data you've entered while using premium commands will be deleted in 48 hours.\n\n"
                        "If you would like me to hold your data in case you want to become a supporter in the future, feel free to join the [support server](https://discord.com/invite/x7MdgVFUwa) to talk to my developer about saving your data.\n\n"
                        "Thank you for trying out premium, means a lot to me!\n\n"
                        "To continue using premium commands, consider becoming a [supporter](https://ko-fi.com/azaelbots) for $1.99 a month. ❤️\n\n"
                        "*Any memberships bought can be refunded within 3 days of purchase.*"
                    ),
                    color=0x2B2D31
                )
                await user.send(embed=embed)
                await bot.rest.create_message(1246886903077408838, f"Trial expiration DM sent to `{user_id}`.")
            except hikari.errors.NotFoundError:
                await bot.rest.create_message(1246886903077408838, f"Failed to send trial expiration DM to `{user_id}`: User not found.")
            except hikari.errors.ForbiddenError:
                await bot.rest.create_message(1246886903077408838, f"Failed to send trial expiration DM to `{user_id}`: Forbidden to send DM.")

            asyncio.create_task(delete_user_data_after_delay(user_id, 172800))

        save_data(data)
        await asyncio.sleep(3600)

# Delete free trial data
async def delete_user_data_after_delay(user_id, delay):
    await asyncio.sleep(delay)
    
    data = load_data()

    if user_id in data['prem_users']:
        server_ids = list(data['prem_users'][user_id])

        for server_id in server_ids:
            if server_id in data['custom_only_servers']:
                data['custom_only_servers'].remove(server_id)

            if server_id in data['custom_insults']:
                del data['custom_insults'][server_id]

            if server_id in data.get('autorespond_servers', {}):
                del data['autorespond_servers'][server_id]

        del data['prem_users'][user_id]
        data['user_conversation_memory'].pop(user_id, None)
        print(f"Removed user_conversation_memory entry for user {user_id}")

    data['free_trial_start_time'].pop(user_id, None)
    data['user_memory_preferences'].pop(user_id, None)
    
    save_data(data)
    await bot.rest.create_message(1246886903077408838, f"Premium data for `{user_id}` has been deleted.")

# Join event
@bot.listen(hikari.GuildJoinEvent)
async def on_guild_join(event):
    guild = event.get_guild()
    if guild is not None:
        for channel in guild.get_channels().values():
            if isinstance(channel, hikari.TextableChannel):
                embed = hikari.Embed(
                    title="Thanks for inviting me ❤️",
                    description=(
                        "Reply or Ping me to talk to me.\n\n"
                        "Use the `/help` command to get an overview of all available commands.\n\n"
                        "Get a premium free trial for a week by using the `/free` command.\n\n"
                        "Feel free to join the [support server](https://discord.com/invite/x7MdgVFUwa) for any help!"
                    ),
                    color=0x2B2D31
                )
                embed.set_footer("Insult Bot is under extensive development, expect to see updates regularly!")
                try:
                    await channel.send(embed=embed)
                    await bot.rest.create_message(1246886903077408838, f"Joined and sent join message in `{guild.name}`.")
                except hikari.errors.ForbiddenError:
                    await bot.rest.create_message(1246886903077408838, f"Joined and failed to send message in `{guild.name}`")
                break
        else:
            await bot.rest.create_message(1246886903077408838, f"Joined and found no channels in `{guild.name}` to send join message.")
    else:
        await bot.rest.create_message(1246886903077408838, "Joined unknown server.")

# Leave event
@bot.listen(hikari.GuildLeaveEvent)
async def on_guild_leave(event):
    guild = event.old_guild
    if guild is not None:
        await bot.rest.create_message(1246886903077408838, f"Left `{guild.name}`.")

# Core----------------------------------------------------------------------------------------------------------------------------------------
# General message event listener
async def should_process_event(event: hikari.MessageCreateEvent) -> bool:
    bot_id = bot.get_me().id
    guild_id = str(event.guild_id)
    
    data = load_data()
    allowed_channels_per_guild = data.get('allowed_channels_per_guild', {})

    if guild_id in allowed_channels_per_guild:
        if allowed_channels_per_guild[guild_id]:
            if str(event.channel_id) not in allowed_channels_per_guild[guild_id]:
                return False

    message_content = event.message.content.lower() if isinstance(event.message.content, str) else ""
    mentions_bot = f"<@{bot_id}>" in message_content
    
    references_message = False
    if event.message.message_reference:
        referenced_message_id = event.message.message_reference.id
        try:
            referenced_message = await bot.rest.fetch_message(event.channel_id, referenced_message_id)
            if referenced_message.author.id == bot_id:
                references_message = True
        except (hikari.errors.ForbiddenError, hikari.errors.NotFoundError):
            pass

    if mentions_bot or references_message:
        return False

    return True

@bot.listen(hikari.MessageCreateEvent)
async def on_general_message(event: hikari.MessageCreateEvent):
    if not event.is_human or not await should_process_event(event):
        return

    message_content = event.content.lower() if isinstance(event.content, str) else ""
    guild_id = str(event.guild_id)

    data = load_data()
    custom_only_servers = data.get('custom_only_servers', {})
    custom_insults = data.get('custom_insults', {})
    custom_triggers = data.get('custom_triggers', {})

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
                except hikari.errors.ForbiddenError:
                    pass
                await asyncio.sleep(15)
                break

# AI response message event listener
@bot.listen(hikari.MessageCreateEvent)
async def on_ai_message(event: hikari.MessageCreateEvent):
    if event.message.author.is_bot:
        return

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
        except (hikari.errors.ForbiddenError, hikari.errors.NotFoundError):
            is_reference_to_bot = False
    else:
        is_reference_to_bot = False

    guild_id = str(event.guild_id)
    channel_id = str(event.channel_id)

    data = load_data()
    autorespond_servers = data.get('autorespond_servers', {})
    prem_users = data.get('prem_users', {})
    allowed_ai_channel_per_guild = data.get('allowed_ai_channel_per_guild', {})

    # Check if autorespond is enabled in this server
    if autorespond_servers.get(guild_id):
        # Get the allowed AI channel for this guild if set
        allowed_channels = allowed_ai_channel_per_guild.get(guild_id, [])
        if allowed_channels and channel_id not in allowed_channels:
            # If a specific channel is set, only respond in that channel
            return

        user_id = str(event.message.author.id)
        message_content = content.strip()

        async with bot.rest.trigger_typing(channel_id):
            ai_response = await generate_text(message_content, user_id)

        response_message = f"{event.message.author.mention} {ai_response}"

        try:
            await event.message.respond(response_message)
        except hikari.errors.ForbiddenError:
            pass
        return

    # Handle bot mentions or references to the bot
    if mentions_bot or is_reference_to_bot:
        # Check if there's an allowed AI channel set
        allowed_channels = allowed_ai_channel_per_guild.get(guild_id, [])
        if allowed_channels and channel_id not in allowed_channels:
            # If a specific channel is set, only respond in that channel
            return

        user_id = str(event.message.author.id)

        current_time = asyncio.get_event_loop().time()
        reset_time = user_reset_time.get(user_id, 0)

        if current_time - reset_time > 21600:
            user_response_count[user_id] = 0
            user_reset_time[user_id] = current_time

        if user_id not in prem_users:
            if user_id not in user_response_count:
                user_response_count[user_id] = 0
                user_reset_time[user_id] = current_time

            if user_response_count[user_id] >= 20:
                has_voted = await topgg_client.get_user_vote(user_id)
                if not has_voted:
                    embed = hikari.Embed(
                        title="Limit Reached :(",
                        description=(
                            f"{event.message.author.mention}, limit resets in `6 hours`.\n\n"
                            "If you want to continue for free, [vote](https://top.gg/bot/801431445452750879/vote) to gain unlimited access for the next 12 hours or become a [supporter](https://ko-fi.com/azaelbots) for $1.99 a month.\n\n"
                            "I will never completely paywall my bot, but limits like this lower running costs and keep the bot running. ❤️\n\n"
                            "Get a premium free trial for a week by using the `/free` command.\n\n"
                            "**Access Premium Commands Like:**\n"
                            "• Unlimited responses from Insult Bot.\n"
                            "• Have Insult Bot respond to every message in set channel(s).\n"
                            "• Add custom insults.\n"
                            "• Insult Bot will remember your conversations.\n"
                            "• Remove cool-downs.\n"
                            "**Support Server Related Perks Like:**\n"
                            "• Access to behind the scenes discord channels.\n"
                            "• Have a say in the development of Insult Bot.\n"
                            "• Supporter exclusive channels.\n\n"
                            "*Any memberships bought can be refunded within 3 days of purchase.*"
                        ),
                        color=0x2B2D31
                    )
                    embed.set_image("https://i.imgur.com/rcgSVxC.gif")
                    await event.message.respond(embed=embed)
                    await bot.rest.create_message(1246886903077408838, f"Voting message sent in `{event.get_guild().name}` to `{event.author.id}`.")
                    return

        async with bot.rest.trigger_typing(channel_id):
            ai_response = await generate_text(content, user_id)

        user_response_count[user_id] += 1
        response_message = f"{event.message.author.mention} {ai_response}"

        try:
            await event.message.respond(response_message)
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
    # Load data
    data = load_data()
    prem_users = data.get('prem_users', {})

    if str(ctx.author.id) in prem_users:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    
    channel = ctx.options.channel
    user = ctx.options.user
    insult = ctx.options.insult
    target_channel = ctx.channel_id if channel is None else channel.id
    
    if insult and any(word in insult.lower() for word in prohibited_words):
        await ctx.respond("Your insult does not comply with Discord's TOS.")
        return
    
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
        try:
            await bot.rest.create_message(target_channel, message)
            await ctx.respond("Message sent.")
        except hikari.errors.NotFoundError:
            await ctx.respond("I don't have access to this channel.")
        except hikari.errors.ForbiddenError:
            await ctx.respond("I don't have permission to send messages in that channel.")
    
    if str(ctx.author.id) in prem_users:
        prem_users[str(ctx.author.id)] = guild_id
        update_data({'prem_users': prem_users})
    
    # Log command usage
    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Setchannel command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("toggle", "Toggle Insult Bot on/off in the selected channel.", choices=["on", "off"], type=hikari.OptionType.STRING)
@lightbulb.option("channel", "Select a channel to proceed.", type=hikari.OptionType.CHANNEL, channel_types=[hikari.ChannelType.GUILD_TEXT])
@lightbulb.option("type", "Select whether to enable 'chatbot' or 'keywords' responses in the channel.", choices=["chatbot", "keywords"], type=hikari.OptionType.STRING, required=True)
@lightbulb.command("setchannel_toggle", "Restrict Insult Bot and AI Bot to particular channel(s).")
@lightbulb.implements(lightbulb.SlashCommand)
async def setchannel(ctx):
    # Load data
    data = load_data()
    prem_users = data.get('prem_users', {})
    allowed_channels_per_guild = data.get('allowed_channels_per_guild', {})
    allowed_ai_channel_per_guild = data.get('allowed_ai_channel_per_guild', {})
    
    if str(ctx.author.id) in prem_users:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    guild_id = str(ctx.guild_id)

    member = await ctx.bot.rest.fetch_member(ctx.guild_id, ctx.author.id)
    if not any(role.permissions & hikari.Permissions.ADMINISTRATOR for role in member.get_roles()):
        await ctx.respond("Ask your admins to set this up for you. 🤦")
        try:
            await bot.rest.create_message(1246886903077408838, f"Failed to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
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

    update_data({
        'allowed_channels_per_guild': allowed_channels_per_guild,
        'allowed_ai_channel_per_guild': allowed_ai_channel_per_guild
    })

    if str(ctx.author.id) in prem_users:
        prem_users[str(ctx.author.id)] = guild_id
        update_data({'prem_users': prem_users})

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# View set channels command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("setchannel_view", "View channel(s) Insult Bot is restricted to.")
@lightbulb.implements(lightbulb.SlashCommand)
async def viewsetchannels(ctx):
    data = load_data()
    prem_users = data.get('prem_users', {})
    allowed_channels_per_guild = data.get('allowed_channels_per_guild', {})
    allowed_ai_channel_per_guild = data.get('allowed_ai_channel_per_guild', {})
    
    if str(ctx.author.id) in prem_users:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    guild_id = str(ctx.guild_id)
    keyword_channels = allowed_channels_per_guild.get(guild_id, [])
    chatbot_channels = allowed_ai_channel_per_guild.get(guild_id, [])

    keyword_channel_list = "\n".join([f"<#{channel_id}>" for channel_id in keyword_channels]) if keyword_channels else "No channels set."
    chatbot_channel_list = "\n".join([f"<#{channel_id}>" for channel_id in chatbot_channels]) if chatbot_channels else "No channels set."

    embed = hikari.Embed(
        title="🔹 Channel Settings 🔹",
        description=(
            f"**Keyword Response Channels:**\n{keyword_channel_list}\n\n"
            f"**Chatbot Response Channels:**\n{chatbot_channel_list}"
        ),
        color=0x2B2D31
    )
    await ctx.respond(embed=embed)

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Chatbot----------------------------------------------------------------------------------------------------------------------------------------
#autorespond
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("toggle", "Toggle autorespond on or off.", choices=["on", "off"], type=hikari.OptionType.STRING)
@lightbulb.command("autorespond", "Enable or disable autorespond in the server (Premium only).")
@lightbulb.implements(lightbulb.SlashCommand)
async def autorespond(ctx: lightbulb.Context):
    user_id = str(ctx.author.id)
    server_id = str(ctx.guild_id)
    data = load_data()

    prem_users = data.get('prem_users', {})
    if user_id not in prem_users:
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To toggle Insult Bot to auto respond in your server, consider becoming a [supporter](https://ko-fi.com/azaelbots) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "Get a premium free trial for a week by using the `/free` command.\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom insults.\n"
                "• Insult Bot will remember your conversations.\n"
                "• Remove cool-downs.\n"
                "**Support Server Related Perks Like:**\n"
                "• Access to behind-the-scenes discord channels.\n"
                "• Have a say in the development of Insult Bot.\n"
                "• Supporter-exclusive channels.\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
            ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)

        try:
            await bot.rest.create_message(1246886903077408838, f"Failed to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
        return

    autorespond_servers = data.get('autorespond_servers', {})
    allowed_ai_channel_per_guild = data.get('allowed_ai_channel_per_guild', {})

    if server_id not in allowed_ai_channel_per_guild or not allowed_ai_channel_per_guild[server_id]:
        await ctx.respond("Please set a channel for AI responses using the `/setchannel` command before enabling autorespond.")
        return

    toggle = ctx.options.toggle
    if toggle == "on":
        if not autorespond_servers.get(server_id):
            autorespond_servers[server_id] = True
            await ctx.respond("Autorespond has been enabled for this server.")
        else:
            await ctx.respond("Autorespond is already enabled for this server.")
    elif toggle == "off":
        if autorespond_servers.get(server_id):
            autorespond_servers[server_id] = False
            await ctx.respond("Autorespond has been disabled for this server.")
        else:
            await ctx.respond("Autorespond is already disabled for this server.")

    if user_id not in prem_users:
        prem_users[user_id] = [server_id]
    elif server_id not in prem_users[user_id]:
        prem_users[user_id].append(server_id)

    update_data({
        'autorespond_servers': autorespond_servers,
        'allowed_ai_channel_per_guild': allowed_ai_channel_per_guild,
        'prem_users': prem_users
    })

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Memory command (P)
@bot.command()
@lightbulb.option('toggle', 'Choose to toggle or clear memory.', choices=['on', 'off', 'clear'])
@lightbulb.command('memory', 'Make Insult Bot remember your conversations.')
@lightbulb.implements(lightbulb.SlashCommand)
async def memory(ctx: lightbulb.Context) -> None:
    user_id = str(ctx.author.id)
    toggle = ctx.options.toggle

    data = load_data()
    prem_users = data.get('prem_users', {})
    if user_id not in prem_users:
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To toggle Insult Bot to remember your conversations, consider becoming a [supporter](https://ko-fi.com/azaelbots) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "Get a premium free trial for a week by using the `/free` command.\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom insults.\n"
                "• Insult Bot will remember your conversations.\n"
                "• Remove cool-downs.\n"
                "**Support Server Related Perks Like:**\n"
                "• Access to behind-the-scenes discord channels.\n"
                "• Have a say in the development of Insult Bot.\n"
                "• Supporter-exclusive channels.\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
            ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)
        try:
            await bot.rest.create_message(1246886903077408838, f"Failed to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
        return

    if toggle == 'on':
        data['user_memory_preferences'][user_id] = True
        response_message = 'Memory has been turned on for personalized interactions.'
    elif toggle == 'off':
        data['user_memory_preferences'][user_id] = False
        response_message = 'Memory has been turned off. Memory will not be cleared until you choose to clear it.'
    elif toggle == 'clear':
        data['user_conversation_memory'].pop(user_id, None)
        response_message = 'Memory has been cleared.'
    else:
        response_message = 'Invalid action.'

    update_data({
        'user_memory_preferences': data['user_memory_preferences'],
        'user_conversation_memory': data['user_conversation_memory'],
        'prem_users': prem_users
    })

    await ctx.respond(response_message)

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Set Style command
@bot.command()
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option('style', 'Enter your prefered AI style.', type=str)
@lightbulb.command('style_set', 'Set a custom style for Insult Bot to respond with.')
@lightbulb.implements(lightbulb.SlashCommand)
async def setstyle(ctx: lightbulb.Context) -> None:
    user_id = str(ctx.author.id)
    style = ctx.options.style

    if user_id in prem_users:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    
    if len(style) > 200:
        await ctx.respond("Your style is too long. Keep it under 200 characters.")
        return

    if any(prohibited_word in style.lower() for prohibited_word in prohibited_words):
        await ctx.respond("Your style does not comply with Discord's TOS.")
        return

    data = load_data()
    data['user_custom_styles'][user_id] = style
    save_data(data)
    
    await ctx.respond(f'Custom response style has been set to: "{style}"')

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# View style command    
@bot.command()
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command('style_view', 'View your current custom style.')
@lightbulb.implements(lightbulb.SlashCommand)
async def viewstyle(ctx: lightbulb.Context) -> None:
    user_id = str(ctx.author.id)
    data = load_data()

    if user_id in data.get('user_custom_styles', {}):
        style = data['user_custom_styles'][user_id]
        await ctx.respond(f'Your current custom style is: "{style}"')
    else:
        await ctx.respond("You haven't set a custom style yet.")

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

#Clear style command
@bot.command()
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command('style_clear', 'Clear your custom style.')
@lightbulb.implements(lightbulb.SlashCommand)
async def clearstyle(ctx: lightbulb.Context) -> None:
    user_id = str(ctx.author.id)
    data = load_data()

    if user_id in data.get('user_custom_styles', {}):
        del data['user_custom_styles'][user_id]
        save_data(data)
        await ctx.respond("Your custom style has been cleared.")
    else:
        await ctx.respond("You haven't set a custom style yet.")

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Keyword----------------------------------------------------------------------------------------------------------------------------------------
# Add insult command (P)
@bot.command
@lightbulb.option("insult", "Add your insult, ensuring it complies with Discord's TOS. (maximum 200 characters)", type=str)
@lightbulb.command("insult_add", "Add a custom insult to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def addinsult(ctx: lightbulb.Context) -> None:
    data = load_data()
    user_id = str(ctx.author.id)
    server_id = str(ctx.guild_id)

    # Check if the user is a premium user first
    if user_id not in data.get('prem_users', {}):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To add custom insults to your server, consider becoming a [supporter](https://ko-fi.com/azaelbots) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "Get a premium free trial for a week by using the `/free` command.\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom insults.\n"
                "• Insult Bot will remember your conversations.\n"
                "• Remove cool-downs.\n"
                "**Support Server Related Perks Like:**\n"
                "• Access to behind the scenes discord channels.\n"
                "• Have a say in the development of Insult Bot.\n"
                "• Supporter exclusive channels.\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
            ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)
        try:
            await bot.rest.create_message(1246886903077408838, f"Failed to invoke `{ctx.command.name}` tried to invoke in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
        return

    # If the user is a premium user, ensure their server is listed under them
    if server_id not in data['prem_users'].get(user_id, []):
        data['prem_users'][user_id].append(server_id)

    insult = ctx.options.insult

    if len(insult) > 200:
        await ctx.respond("Your insult is too long. Keep it under 200 characters.")
        return

    if any(prohibited_word in insult.lower() for prohibited_word in prohibited_words):
        await ctx.respond("Your insult does not comply with Discord's TOS.")
        return

    if server_id not in data['custom_insults']:
        data['custom_insults'][server_id] = []

    data['custom_insults'][server_id].append(insult)
    
    save_data(data)
    
    await ctx.respond("New insult added.")

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Remove insult command (P)
@bot.command
@lightbulb.option("insult", "The insult to remove.", type=str)
@lightbulb.command("insult_remove", "Remove a custom insult from this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def removeinsult(ctx: lightbulb.Context) -> None:
    data = load_data()
    user_id = str(ctx.author.id)
    server_id = str(ctx.guild_id)

    if user_id not in data.get('prem_users', {}):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To remove custom insults added to your server, consider becoming a [supporter](https://ko-fi.com/azaelbots) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "Get a premium free trial for a week by using the `/free` command.\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom insults.\n"
                "• Insult Bot will remember your conversations.\n"
                "• Remove cool-downs.\n"
                "**Support Server Related Perks Like:**\n"
                "• Access to behind the scenes discord channels.\n"
                "• Have a say in the development of Insult Bot.\n"
                "• Supporter exclusive channels.\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
            ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)
        try:
            await bot.rest.create_message(1246886903077408838, f"Failed to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
        return

    if server_id not in data['prem_users'].get(user_id, []):
        data['prem_users'][user_id].append(server_id)

    insult_to_remove = ctx.options.insult

    if server_id not in data['custom_insults'] or not data['custom_insults'][server_id]:
        await ctx.respond("No insults found.")
        return

    if insult_to_remove not in data['custom_insults'][server_id]:
        await ctx.respond("Insult not found in the list.")
        return

    data['custom_insults'][server_id].remove(insult_to_remove)
    
    save_data(data)
    
    await ctx.respond("The selected insult has been removed.")

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# View insults command (P)
@bot.command
@lightbulb.command("insult_view", "View custom insults added to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def viewinsults(ctx: lightbulb.Context) -> None:
    data = load_data()
    user_id = str(ctx.author.id)
    server_id = str(ctx.guild_id)

    # Check if the user is a premium user first
    if user_id not in data.get('prem_users', {}):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To view custom insults added to your server, consider becoming a [supporter](https://ko-fi.com/azaelbots) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "Get a premium free trial for a week by using the `/free` command.\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom insults.\n"
                "• Insult Bot will remember your conversations.\n"
                "• Remove cool-downs.\n"
                "**Support Server Related Perks Like:**\n"
                "• Access to behind the scenes discord channels.\n"
                "• Have a say in the development of Insult Bot.\n"
                "• Supporter exclusive channels.\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
            ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)
        try:
            await bot.rest.create_message(1246886903077408838, f"Failed to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
        return

    # If the user is a premium user, show the custom insults
    if server_id in data.get('custom_insults', {}):
        insults_list = data['custom_insults'][server_id]
        if insults_list:
            insults_text = "\n".join(insults_list)
            embed = hikari.Embed(
                title="🔹 Custom Insults 🔹",
                description=insults_text,
                color=0x2B2D31
            )
            await ctx.respond(embed=embed)
        else:
            await ctx.respond("No custom insults found.")
    else:
        await ctx.respond("No custom insults found.")
    
    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Add trigger command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("trigger", "Add your trigger, ensuring it complies with Discord's TOS. (maximum 200 characters)", type=str)
@lightbulb.command("trigger_add", "Add a custom trigger to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def addtrigger(ctx: lightbulb.Context) -> None:
    if str(ctx.author.id) in prem_users:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    data = load_data()

    server_id = str(ctx.guild_id)
    trigger = ctx.options.trigger

    if len(trigger) > 200:
        await ctx.respond("Your trigger is too long. Keep it under 200 characters.")
        return

    if server_id not in data['custom_triggers']:
        data['custom_triggers'][server_id] = []

    data['custom_triggers'][server_id].append(trigger)
    save_data(data)
    await ctx.respond(f"New trigger added.")

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Remove trigger command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("trigger", "The trigger to remove.", type=str)
@lightbulb.command("trigger_remove", "Remove a custom trigger from this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def removetrigger(ctx: lightbulb.Context) -> None:
    if str(ctx.author.id) in prem_users:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    # Load data
    data = load_data()

    server_id = str(ctx.guild_id)
    trigger_to_remove = ctx.options.trigger

    if server_id not in data['custom_triggers'] or not data['custom_triggers'][server_id]:
        await ctx.respond("No triggers found.")
        return

    if trigger_to_remove not in data['custom_triggers'][server_id]:
        await ctx.respond("Trigger not found in the list.")
        return

    data['custom_triggers'][server_id].remove(trigger_to_remove)
    save_data(data)
    await ctx.respond("The selected trigger has been removed.")

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# View triggers command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("trigger_view", "View custom triggers added to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def viewtriggers(ctx: lightbulb.Context) -> None:
    if str(ctx.author.id) in prem_users:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    data = load_data()
    server_id = str(ctx.guild_id)

    if server_id in data['custom_triggers']:
        triggers_list = data['custom_triggers'][server_id]
        if not triggers_list:
            await ctx.respond("No custom triggers found.")
            return
        triggers_text = "\n".join(triggers_list)
        embed = hikari.Embed(
            title="🔹 Custom Triggers 🔹",
            description=triggers_text,
            color=0x2B2D31
        )
        await ctx.respond(embed=embed)
    else:
        await ctx.respond("No custom triggers found.")

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Custom only toggle command (P)
@bot.command
@lightbulb.option("toggle", "Toggle custom insults and triggers only mode on/off.", choices=["on", "off"], type=hikari.OptionType.STRING)
@lightbulb.command("customonly", "Set custom insults and triggers only.")
@lightbulb.implements(lightbulb.SlashCommand)
async def customonly(ctx: lightbulb.Context) -> None:
    data = load_data()
    user_id = str(ctx.author.id)
    server_id = str(ctx.guild_id)

    if user_id not in data['prem_users']:
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To toggle custom only triggers/insults for your server, consider becoming a [supporter](https://ko-fi.com/azaelbots) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "Get a premium free trial for a week by using the `/free` command.\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom insults.\n"
                "• Insult Bot will remember your conversations.\n"
                "• Remove cool-downs.\n"
                "**Support Server Related Perks Like:**\n"
                "• Access to behind the scenes discord channels.\n"
                "• Have a say in the development of Insult Bot.\n"
                "• Supporter exclusive channels.\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
            ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await ctx.respond(embed=embed)
        try:
            await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
        return
    
    if server_id not in data['prem_users'][user_id]:
        data['prem_users'][user_id].append(server_id)

    if ctx.options.toggle == "on":
        if server_id not in data['custom_only_servers']:
            data['custom_only_servers'].append(server_id)
            await ctx.respond(f"Custom insults and triggers only mode enabled for this server.")
        else:
            await ctx.respond(f"Custom insults and triggers only mode is already enabled for this server.")
    elif ctx.options.toggle == "off":
        if server_id in data['custom_only_servers']:
            data['custom_only_servers'].remove(server_id)
            await ctx.respond(f"Custom insults and triggers only mode disabled for this server.")
        else:
            await ctx.respond(f"Custom insults and triggers only mode is not enabled for this server.")
    
    save_data(data)

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")
    return

# MISC----------------------------------------------------------------------------------------------------------------------------------------
# Help command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("help", "You know what this is ;)")
@lightbulb.implements(lightbulb.SlashCommand)
async def help(ctx):
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    embed = hikari.Embed(
        title="📚 Help 📚",
        description=(
            "**Reply or ping Insult Bot to talk.**\n\n"
            "**Core Commands:**\n"
            "**/insult:** Send an insult to someone.\n"
            "**/setchannel_toggle:** Restrict Insult Bot to particular channel(s).\n"
            "**/setchannel_view:** View channel(s) Insult Bot is restricted to.\n\n"
            "**Chatbot Commands:**\n"
            "**/autorespond:** Have Insult Bot respond to every message in a set channel(s). (P)\n"
            "**/memory:** Make Insult Bot remember your conversations. (P)\n"
            "**/style_[set/view/clear]:** Set/view/clear the custom Insult Bot style.\n\n"
            "**Keyword Commands:**\n"
            "**/insult_[add/remove/view]:** Add/remove/view custom insults in your server. (P)\n"
            "**/trigger_[add/remove/view]:** Add/remove/view custom triggers in your server.\n"
            "**/customonly:** Set custom insults and triggers only. (P)\n\n"
            "**Miscellaneous Commands:**\n"
            "**/claim:** Claim premium by providing your Ko-fi email.\n"
            "**/free:** Get a premium free trial for a week.\n"
            "**/support:** Join the support server.\n"
            "**/privacy:** View our privacy policy.\n\n"
            "**To use (P) premium commands and help keep the bot running, consider becoming a [supporter](https://ko-fi.com/azaelbots) for  $1.99 a month. ❤️**\n\n"
        ),
        color=0x2B2D31
    )
    await ctx.respond(embed=embed)

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Claim premium command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("email", "Enter your Ko-fi email", type=str)
@lightbulb.command("claim", "Claim premium after subscribing.")
@lightbulb.implements(lightbulb.SlashCommand)
async def claim(ctx: lightbulb.Context) -> None:
    data = load_data()
    user_id = str(ctx.author.id)
    server_id = str(ctx.guild_id)

    if user_id in data['prem_users']:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
        await ctx.respond("You already have premium. 🤦")
        try:
            await bot.rest.create_message(1246886903077408838, f"`{ctx.author.id}` tried to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` but already had premium.")
        except Exception as e:
            print(f"{e}")
        return
    
    email = ctx.options.email
    
    if email in prem_email:
        if user_id not in data['prem_users']:
            data['prem_users'][user_id] = [server_id]
        else:
            if server_id not in data['prem_users'][user_id]:
                data['prem_users'][user_id].append(server_id)
        
        save_data(data)
        await ctx.respond("You have premium now! Thank you so much. ❤️")
        
        try:
            await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
    else:
        embed = hikari.Embed(
            title="Invite:",
            description=(
                "Your email was not recognized. If you think this is an error, join the [support server](https://discord.com/invite/x7MdgVFUwa) to fix this issue.\n\n"
                "If you haven't yet subscribed to premium, consider doing so for $1.99 a month. It helps cover the costs associated with running Insult Bot. ❤️\n\n"
                "Premium Perks:\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom insults.\n"
                "• Insult Bot will remember your conversations.\n"
                "• Remove cool-downs.\n"
                "**Support Server Related Perks Like:**\n"
                "• Access to behind the scenes discord channels.\n"
                "• Have a say in the development of Insult Bot.\n"
                "• Supporter exclusive channels.\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
            ),
            color=0x2f3136
        )
        await ctx.respond(embed=embed)
        try:
            await bot.rest.create_message(1246886903077408838, f"Failed to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")

# Free premium command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("free", "Get premium for free for a week!")
@lightbulb.implements(lightbulb.SlashCommand)
async def free(ctx: lightbulb.Context) -> None:
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    data = load_data()
    user_id = str(ctx.author.id)
    server_id = str(ctx.guild_id)

    if user_id in data['prem_users']:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
        await ctx.respond("You already have premium. 🤦")
        return
    
    if user_id in data['used_free_trial']:
        await ctx.respond("You have already claimed the free trial. 😔")
        return

    data['prem_users'][user_id] = [server_id]
    data['used_free_trial'].append(user_id)
    data['free_trial_start_time'][user_id] = asyncio.get_event_loop().time()
    save_data(data)
    await ctx.respond("You have premium now! ❤️")

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Support command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("support", "Join the support server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def support(ctx):
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    embed = hikari.Embed(
        title="Support Server:",
        description=("[Join the support server.](https://discord.com/invite/x7MdgVFUwa)"),
        color=0x2B2D31
    )
    await ctx.respond(embed=embed)

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Privacy command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("privacy", "Privacy policy statement.")
@lightbulb.implements(lightbulb.SlashCommand)
async def privacy(ctx):
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    embed = hikari.Embed(
		title="Privacy Policy:",
		description="The personal information of any user, including the message content it replies to, is not tracked by Insult Bot. The channel_id alone is stored when added by using the /setchannel command, and it is stored only while this command is active in your server.\n\nThe user_id, server_id and added insults of premium members are stored to provide the user the with perks and is deleted once a user is no longer a member.\n\nJoin the [support server](https://discord.com/invite/x7MdgVFUwa) to request the deletion of your data.",
		color=0x2B2D31
	)
    await ctx.respond(embed=embed)

    try:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Error handling
@bot.listen(lightbulb.CommandErrorEvent)
async def on_error(event: lightbulb.CommandErrorEvent) -> None:
	if isinstance(event.exception, lightbulb.CommandInvocationError):
		await event.context.respond(f"Uh oh, something went wrong, please try again. If this issue keeps persisting, join the [support server](https://discord.com/invite/x7MdgVFUwa) to have your issue resolved.")
		raise event.exception

	exception = event.exception.__cause__ or event.exception

	if isinstance(exception, lightbulb.CommandIsOnCooldown):
		await event.context.respond(f"`/{event.context.command.name}` is on cooldown. Retry in `{exception.retry_after:.0f}` seconds. ⏱️\nCommands are ratelimited to prevent spam abuse. To remove cool-downs, become a [supporter](https://ko-fi.com/azaelbots).")
	else:
		raise exception

# Top.gg stop
@bot.listen(hikari.StoppedEvent)
async def on_stopping(event: hikari.StoppedEvent) -> None:
    await topgg_client.close()

bot.run()