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
import time

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
            "user_memory_preferences": {},
            "user_conversation_memory": {},
            "custom_only_servers": [],
            "user_custom_styles": {},
            "allowed_channels_per_guild": {},
            "allowed_ai_channel_per_guild": {},
            "custom_insults": {},
            "custom_triggers": {},
            "custom_combos": {},
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
user_memory_preferences = data.get('user_memory_preferences', {})
user_conversation_memory = data.get('user_conversation_memory', {})
custom_only_servers = data.get('custom_only_servers', [])
custom_insults = data.get('custom_insults', {})
custom_triggers = data.get('custom_triggers', {})
user_custom_styles = data.get('user_custom_styles', {})
allowed_channels_per_guild = data.get('allowed_channels_per_guild', {})
allowed_ai_channel_per_guild = data.get('allowed_ai_channel_per_guild', {})
autorespond_servers = data.get('autorespond_servers', {})
custom_combos = data.get('custom_combos', {})

# Nonpersistent data
prem_email = []
user_reset_time = {}
user_response_count = {}
user_limit_reached = {}

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
        self.session = None

    async def setup(self):
        """Initialize the aiohttp.ClientSession in an async context."""
        self.session = aiohttp.ClientSession()

    async def post_guild_count(self, count):
        """Post the guild count to Top.gg."""
        if not self.session:
            raise RuntimeError("Client session is not initialized. Call setup() first.")
        url = f"https://top.gg/api/bots/{self.bot.get_me().id}/stats"
        headers = {"Authorization": self.token}
        payload = {"server_count": count}
        async with self.session.post(url, json=payload, headers=headers) as response:
            if response.status != 200:
                print(f"Failed to post guild count to Top.gg: {response.status}")
            else:
                print("Posted server count to Top.gg")

    async def get_user_vote(self, user_id):
        """Check if a user has voted for the bot on Top.gg."""
        if not self.session:
            raise RuntimeError("Client session is not initialized. Call setup() first.")
        url = f"https://top.gg/api/bots/{self.bot.get_me().id}/check?userId={user_id}"
        headers = {"Authorization": self.token}
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
        """Close the aiohttp.ClientSession."""
        if self.session:
            await self.session.close()

topgg_token = os.getenv("TOPGG_TOKEN")
topgg_client = TopGGClient(bot, topgg_token)

# AI
async def generate_text(prompt, user_id=None):
    try:
        data = load_data()
        
        system_message = "Be sarcastic, rude, and direct. Don't repeat yourself, and don't be overly nice or keep asking how can I help you. Keep it short and sharp."
        
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
    if event.channel_id == 1285293925699031080:
        email = event.message.content.strip()
        if re.match(r"[^@]+@[^@]+\.[^@]+", email):
            if email not in prem_email:
                prem_email.append(email)
                await bot.rest.create_message(1285303149682364548, f"prem_email = {prem_email}")
            else:
                await bot.rest.create_message(1285303149682364548, f"prem_email = {prem_email}")
        else:
            await bot.rest.create_message(1285303149682364548, "The provided email is invalid.")

# Presence
@bot.listen(hikari.StartedEvent)
async def on_starting(event: hikari.StartedEvent):
    await topgg_client.setup()
    asyncio.create_task(check_premium_users())
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

# Join event
@bot.listen(hikari.GuildJoinEvent)
async def on_guild_join(event):
    guild = event.get_guild()
    if guild is not None:
        await bot.rest.create_message(1285303149682364548, f"Joined `{guild.name}`.")
    else:
        await bot.rest.create_message(1285303149682364548, "Joined unknown server.")

# Leave event
@bot.listen(hikari.GuildLeaveEvent)
async def on_guild_leave(event):
    guild = event.old_guild
    if guild is not None:
        await bot.rest.create_message(1285303149682364548, f"Left `{guild.name}`.")

# Premium check task
async def check_premium_users():
    while True:
        data = load_data()
        current_time = int(time.time())
        updated_prem_users = data.get('prem_users', {})

        for user_id, details in list(updated_prem_users.items()):
            email = details['email']
            claim_time = details['claim_time']

            if current_time - claim_time >= 30 * 24 * 60 * 60:
                if email in prem_email:
                    updated_prem_users[user_id]["claim_time"] = current_time
                    prem_email.remove(email)
                    await bot.rest.create_message(1285303149682364548, f"`{email}` updated with new `claim_time`.")
                else:
                    updated_prem_users.pop(user_id)
                    await bot.rest.create_message(1285303149682364548, f"`{email}` removed from `prem_users`.")

        data['prem_users'] = updated_prem_users
        save_data(data)
        await asyncio.sleep(24 * 60 * 60)

# Core----------------------------------------------------------------------------------------------------------------------------------------

# Message event listener
async def should_process_event(event: hikari.MessageCreateEvent) -> bool:
    bot_id = bot.get_me().id
    guild_id = str(event.guild_id)
    
    data = load_data()
    allowed_channels_per_guild = data.get('allowed_channels_per_guild', {})

    if guild_id in allowed_channels_per_guild and allowed_channels_per_guild[guild_id]:
        if str(event.channel_id) not in allowed_channels_per_guild[guild_id]:
            return False

    message_content = event.message.content.lower() if isinstance(event.message.content, str) else ""
    mentions_bot = f"<@{bot_id}>" in message_content
    
    if event.message.message_reference:
        referenced_message_id = event.message.message_reference.id
        try:
            referenced_message = await bot.rest.fetch_message(event.channel_id, referenced_message_id)
            if referenced_message.author.id == bot_id:
                return False
        except (hikari.errors.ForbiddenError, hikari.errors.NotFoundError):
            pass

    return not mentions_bot

@bot.listen(hikari.MessageCreateEvent)
async def on_general_message(event: hikari.MessageCreateEvent):
    if not event.is_human or not await should_process_event(event):
        return

    message_content = event.content.lower() if isinstance(event.content, str) else ""
    guild_id = str(event.guild_id)

    data = load_data()
    custom_combos = data.get('custom_combos', {})
    custom_insults = data.get('custom_insults', {})
    custom_triggers = data.get('custom_triggers', {})
    hearing = data.get('hearing', [])

    all_responses = []

    if guild_id in custom_combos:
        for trigger, insult in custom_combos[guild_id]:
            if trigger.lower() in message_content:
                try:
                    await event.message.respond(insult)
                except (hikari.errors.BadRequestError, hikari.errors.ForbiddenError):
                    pass
                await asyncio.sleep(15)
                return

    if guild_id in custom_insults and any(word in message_content for word in custom_triggers.get(guild_id, [])):
        all_responses = custom_insults[guild_id]

    if guild_id in custom_insults:
        all_responses.extend(custom_insults[guild_id])
    all_responses.extend(hearing)

    if all_responses:
        if guild_id in custom_combos:
            for trigger, insult in custom_combos[guild_id]:
                if trigger.lower() in message_content:
                    try:
                        await event.message.respond(insult)
                    except (hikari.errors.BadRequestError, hikari.errors.ForbiddenError):
                        pass
                    await asyncio.sleep(15)
                    return

        if any(word in message_content for word in hearing):
            selected_response = random.choice(all_responses)
            try:
                await event.message.respond(selected_response)
            except (hikari.errors.BadRequestError, hikari.errors.ForbiddenError):
                pass
            await asyncio.sleep(15)
            return

        if guild_id in custom_triggers:
            for trigger in custom_triggers[guild_id]:
                if trigger.lower() in message_content:
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
        if referenced_message_id:
            try:
                referenced_message = await bot.rest.fetch_message(event.channel_id, referenced_message_id)
                is_reference_to_bot = referenced_message.author.id == bot_id
            except (hikari.errors.ForbiddenError, hikari.errors.NotFoundError):
                is_reference_to_bot = False
            except hikari.errors.BadRequestError as e:
                print(f"BadRequestError: {e}")
                is_reference_to_bot = False
        else:
            is_reference_to_bot = False
    else:
        is_reference_to_bot = False

    guild_id = str(event.guild_id)
    channel_id = str(event.channel_id)

    data = load_data()
    autorespond_servers = data.get('autorespond_servers', {})
    prem_users = data.get('prem_users', {})
    allowed_ai_channel_per_guild = data.get('allowed_ai_channel_per_guild', {})

    user_id = str(event.message.author.id)
    current_time = asyncio.get_event_loop().time()
    reset_time = user_reset_time.get(user_id, 0)

    if user_id in user_limit_reached:
        if current_time - user_limit_reached[user_id] < 21600:
            return
        else:
            del user_limit_reached[user_id]

    if autorespond_servers.get(guild_id):
        allowed_channels = allowed_ai_channel_per_guild.get(guild_id, [])
        if allowed_channels and channel_id not in allowed_channels:
            return

        if current_time - reset_time > 21600:
            user_response_count[user_id] = 0
            user_reset_time[user_id] = current_time
        else:
            if user_id not in user_response_count:
                user_response_count[user_id] = 0
                user_reset_time[user_id] = current_time

        if user_id not in prem_users:
            if user_response_count.get(user_id, 0) >= 20:
                has_voted = await topgg_client.get_user_vote(user_id)
                if not has_voted:
                    embed = hikari.Embed(
                        title="Limit Reached :(",
                        description=(
                            f"{event.message.author.mention}, limit resets in `6 hours`.\n\n"
                            "If you want to continue for free, [vote](https://top.gg/bot/801431445452750879/vote) to gain unlimited access for the next 12 hours or become a [supporter](https://ko-fi.com/azaelbots) for $1.99 a month.\n\n"
                            "I will never completely paywall my bot, but limits like this lower running costs and keep the bot running. ❤️\n\n"
                            "**Access Premium Commands Like:**\n"
                            "• Unlimited responses from Insult Bot.\n"
                            "• Have Insult Bot respond to every message in set channel(s).\n"
                            "• Add custom trigger-insult combos.\n"
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
                    await bot.rest.create_message(1285303149682364548, f"Voting message sent in `{event.get_guild().name}` to `{event.author.id}`.")

                    # Mark user as having hit the limit
                    user_limit_reached[user_id] = current_time
                    return

        async with bot.rest.trigger_typing(channel_id):
            ai_response = await generate_text(content, user_id)

        user_response_count[user_id] = user_response_count.get(user_id, 0) + 1
        response_message = f"{event.message.author.mention} {ai_response}"
        try:
            await event.message.respond(response_message)
        except hikari.errors.ForbiddenError:
            pass
        return

    if mentions_bot or is_reference_to_bot:
        allowed_channels = allowed_ai_channel_per_guild.get(guild_id, [])
        if allowed_channels and channel_id not in allowed_channels:
            return

        if user_id not in prem_users:
            if user_response_count.get(user_id, 0) >= 20:
                has_voted = await topgg_client.get_user_vote(user_id)
                if not has_voted:
                    embed = hikari.Embed(
                        title="Limit Reached :(",
                        description=(
                            f"{event.message.author.mention}, limit resets in `6 hours`.\n\n"
                            "If you want to continue for free, [vote](https://top.gg/bot/801431445452750879/vote) to gain unlimited access for the next 12 hours or become a [supporter](https://ko-fi.com/azaelbots) for $1.99 a month.\n\n"
                            "I will never completely paywall my bot, but limits like this lower running costs and keep the bot running. ❤️\n\n"
                            "**Access Premium Commands Like:**\n"
                            "• Unlimited responses from Insult Bot.\n"
                            "• Have Insult Bot respond to every message in set channel(s).\n"
                            "• Add custom trigger-insult combos.\n"
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
                    await bot.rest.create_message(1285303149682364548, f"Voting message sent in `{event.get_guild().name}` to `{event.author.id}`.")

                    user_limit_reached[user_id] = current_time
                    return

        async with bot.rest.trigger_typing(channel_id):
            ai_response = await generate_text(content, user_id)

        user_response_count[user_id] = user_response_count.get(user_id, 0) + 1
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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Setchannel command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("toggle", "Toggle Insult Bot on/off in the selected channel.", choices=["on", "off"], type=hikari.OptionType.STRING)
@lightbulb.option("channel", "Select a channel to proceed.", type=hikari.OptionType.CHANNEL, channel_types=[hikari.ChannelType.GUILD_TEXT])
@lightbulb.option("type", "Select whether to enable 'chatbot' or 'replybot' responses in the channel.", choices=["chatbot", "replybot"], type=hikari.OptionType.STRING, required=True)
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
    is_admin = any(role.permissions & hikari.Permissions.ADMINISTRATOR for role in member.get_roles())
    is_premium_user = str(ctx.author.id) in prem_users

    if not is_admin and not is_premium_user:
        await ctx.respond("Ask your admins or upgrade to premium to set this up. 🤦")
        try:
            await bot.rest.create_message(1285303149682364548, f"Failed to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
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
        if channel_type == "replybot":
            if channel_id and channel_id not in allowed_channels_per_guild[guild_id]:
                allowed_channels_per_guild[guild_id].append(channel_id)
                await ctx.respond(f"Insult Bot will only respond with replybot in <#{channel_id}>.")
            elif channel_id in allowed_channels_per_guild[guild_id]:
                await ctx.respond(f"Insult Bot is already restricted to replybot in <#{channel_id}>.")
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
        if channel_type == "replybot" and channel_id in allowed_channels_per_guild[guild_id]:
            allowed_channels_per_guild[guild_id].remove(channel_id)
            await ctx.respond(f"Bot's restriction to send replybot in <#{channel_id}> has been removed.")
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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Chatbot----------------------------------------------------------------------------------------------------------------------------------------
# Autorespond (P)
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("toggle", "Toggle autorespond on or off.", choices=["on", "off"], type=hikari.OptionType.STRING)
@lightbulb.command("autorespond", "Enable or disable autorespond in the server. (Premium Only)")
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
                "To toggle Insult Bot to auto respond in your server, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom trigger-insult combos.\n"
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
            await bot.rest.create_message(1285303149682364548, f"Failed to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
        return

    autorespond_servers = data.get('autorespond_servers', {})
    allowed_ai_channel_per_guild = data.get('allowed_ai_channel_per_guild', {})

    if server_id not in allowed_ai_channel_per_guild or not allowed_ai_channel_per_guild[server_id]:
        await ctx.respond("Please set a channel for AI responses using the `/setchannel_toggle` command before enabling autorespond.")
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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Memory command (P)
@bot.command()
@lightbulb.option('toggle', 'Choose to toggle or clear memory.', choices=['on', 'off', 'clear'])
@lightbulb.command('memory', 'Make Insult Bot remember your conversations. (Premium Only)')
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
                "To toggle Insult Bot to remember your conversations, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom trigger-insult combos.\n"
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
            await bot.rest.create_message(1285303149682364548, f"Failed to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Replybot----------------------------------------------------------------------------------------------------------------------------------------
# Add insult command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("insult", "Add your insult, ensuring it complies with Discord's TOS. (maximum 200 characters)", type=str)
@lightbulb.command("insult_add", "Add a custom insult to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def addinsult(ctx: lightbulb.Context) -> None:
    if str(ctx.author.id) in prem_users:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    
    data = load_data()
    server_id = str(ctx.guild_id)
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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Remove insult command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("insult", "The insult to remove.", type=str)
@lightbulb.command("insult_remove", "Remove a custom insult from this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def removeinsult(ctx: lightbulb.Context) -> None:
    if str(ctx.author.id) in prem_users:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    data = load_data()
    server_id = str(ctx.guild_id)
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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# View insults command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("insult_view", "View custom insults added to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def viewinsults(ctx: lightbulb.Context) -> None:
    if str(ctx.author.id) in prem_users:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    
    data = load_data()
    server_id = str(ctx.guild_id)

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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
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
    trigger = ctx.options.trigger.lower()

    if len(trigger) > 200:
        await ctx.respond("Your trigger is too long. Keep it under 200 characters.")
        return

    if server_id not in data['custom_triggers']:
        data['custom_triggers'][server_id] = []

    custom_combos = data.get('custom_combos', {}).get(server_id, [])

    # Check if the trigger already exists in custom_triggers
    if trigger in (t.lower() for t in data['custom_triggers'][server_id]):
        await ctx.respond("This trigger already exists in this server.")
        return

    # Check if the trigger already exists in custom_combos
    if any(trigger == t.lower() for t, _ in custom_combos):
        await ctx.respond("This trigger already exists in `/combo_add`. Please remove it from there before adding it here.")
        return

    # Add the new trigger
    data['custom_triggers'][server_id].append(trigger)
    save_data(data)
    await ctx.respond("New trigger added.")

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"Failed to log command usage: {e}")

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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Add combo command (P)
@bot.command
@lightbulb.option("insult", "The insult to send when the trigger is activated.", type=str)
@lightbulb.option("trigger", "The trigger phrase to add.", type=str)
@lightbulb.command("combo_add", "Add a trigger-insult combo to this server. (Premium Only)")
@lightbulb.implements(lightbulb.SlashCommand)
async def combo_add(ctx: lightbulb.Context) -> None:
    data = load_data()
    user_id = str(ctx.author.id)
    server_id = str(ctx.guild_id)

    if user_id not in data.get('prem_users', {}):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To add custom combos to your server, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot respond to every message in set channel(s).\n"
                "• Add custom trigger-insult combos.\n"
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
            await bot.rest.create_message(1285303149682364548, f"Failed to invoke `{ctx.command.name}` tried to invoke in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
        return

    trigger = ctx.options.trigger.lower()
    insult = ctx.options.insult.lower()

    if any(prohibited_word in insult for prohibited_word in prohibited_words):
        await ctx.respond("Your insult does not comply with Discord's TOS.")
        return

    # Initialize server data if it doesn't exist
    if server_id not in data['custom_combos']:
        data['custom_combos'][server_id] = []

    custom_triggers = data.get('custom_triggers', {}).get(server_id, [])

    # Check if the trigger already exists in custom_combos
    if any(trigger == t.lower() for t, _ in data['custom_combos'][server_id]):
        await ctx.respond("This trigger already exists in `/combo_add`. Please remove it from there before adding it here.")
        return

    # Check if the trigger already exists in custom_triggers
    if trigger in (t.lower() for t in custom_triggers):
        await ctx.respond("This trigger already exists in `/trigger_add`. Please remove it from there before adding it here.")
        return

    # Add the new combo
    data['custom_combos'][server_id].append((trigger, insult))
    
    save_data(data)
    
    await ctx.respond("New combo added.")

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Remove combo command (P)
@bot.command
@lightbulb.option("trigger", "The trigger phrase to remove the combo.", type=str)
@lightbulb.command("combo_remove", "Remove a trigger-insult combo from this server. (Premium Only)")
@lightbulb.implements(lightbulb.SlashCommand)
async def combo_remove(ctx: lightbulb.Context) -> None:
    data = load_data()
    user_id = str(ctx.author.id)
    server_id = str(ctx.guild_id)

    if user_id not in data.get('prem_users', {}):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To remove custom combos from your server, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom trigger-insult combos.\n"
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
            await bot.rest.create_message(1285303149682364548, f"Failed to invoke `{ctx.command.name}` tried to invoke in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
        return

    trigger_to_remove = ctx.options.trigger

    if server_id not in data['custom_combos'] or not data['custom_combos'][server_id]:
        await ctx.respond("No combos found.")
        return

    combos = data['custom_combos'][server_id]
    filtered_combos = [combo for combo in combos if combo[0] != trigger_to_remove]

    if len(filtered_combos) == len(combos):
        await ctx.respond("Combo not found.")
        return

    data['custom_combos'][server_id] = filtered_combos
    save_data(data)
    
    await ctx.respond(f"The combo with trigger `{trigger_to_remove}` has been removed.")

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# View combo command (P)
@bot.command
@lightbulb.command("combo_view", "View all trigger-insult combos in this server. (Premium Only)")
@lightbulb.implements(lightbulb.SlashCommand)
async def combo_view(ctx: lightbulb.Context) -> None:
    data = load_data()
    user_id = str(ctx.author.id)
    server_id = str(ctx.guild_id)

    if user_id not in data.get('prem_users', {}):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To view custom combos in your server, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom trigger-insult combos.\n"
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
            await bot.rest.create_message(1285303149682364548, f"Failed to invoke `{ctx.command.name}` tried to invoke in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
        return

    if server_id in data['custom_combos']:
        combos = data['custom_combos'][server_id]
        if combos:
            combo_list = "\n".join([f"`{trigger}`: `{insult}`" for trigger, insult in combos])
            embed = hikari.Embed(
                title="🔹 Custom Combos 🔹",
                description=combo_list,
                color=0x2B2D31
            )
            await ctx.respond(embed=embed)
        else:
            await ctx.respond("No custom combos found.")
    else:
        await ctx.respond("No custom combos found.")

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Custom only toggle command (P)
@bot.command
@lightbulb.option("toggle", "Toggle custom insults and triggers only mode on/off.", choices=["on", "off"], type=hikari.OptionType.STRING)
@lightbulb.command("customonly", "Set custom insults and triggers only. (Premium Only)")
@lightbulb.implements(lightbulb.SlashCommand)
async def customonly(ctx: lightbulb.Context) -> None:
    data = load_data()
    user_id = str(ctx.author.id)
    server_id = str(ctx.guild_id)

    if user_id not in data['prem_users']:
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To toggle custom only triggers/insults for your server, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom trigger-insult combos.\n"
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
            await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
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
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
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
            "To talk to Insult Bot, reply or ping the bot in chat. Use the `/setchannel_toggle` command to set channels for the bot to respond in.\n\n"
            "For suggestions and help, feel free to join the [support server](https://discord.com/invite/x7MdgVFUwa). My developer will be happy to help! "
            "[Click here](https://discord.com/api/oauth2/authorize?client_id=801431445452750879&permissions=414464727104&scope=applications.commands%20bot), to invite the bot to your server.\n\n"
            "Use the `/claim` command to receive your perks after becoming a supporter.\n\n"
            "**Core Commands:**\n"
            "**/insult:** Send an insult to someone.\n"
            "**/setchannel_toggle:** Restrict Insult Bot to particular channel(s).\n"
            "**/setchannel_view:** View channel(s) Insult Bot is restricted to.\n\n"
            "**Chatbot Commands:**\n"
            "**/autorespond:** Have Insult Bot respond to every message in a set channel(s). (P)\n"
            "**/memory:** Make Insult Bot remember your conversations. (P)\n"
            "**/style_[set/view/clear]:** Set/view/clear the custom style of Insult Bot.\n\n"
            "**Replybot Commands:**\n"
            "**/insult_[add/remove/view]:** Add/remove/view custom insults.\n"
            "**/trigger_[add/remove/view]:** Add/remove/view custom triggers.\n"
            "**/combo_[add/remove/view]:** Add/remove/view trigger-insult combos. (P)\n"
            "**/customonly:** Set custom insults and triggers only. (P)\n\n"
            "**To use (P) premium commands and help cover costs associated with running Insult Bot, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for  $1.99 a month. ❤️**\n\n"
        ),
        color=0x2B2D31
    )
    await ctx.respond(embed=embed)

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Claim command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("email", "Enter your Ko-fi email", type=str)
@lightbulb.command("claim", "Claim premium after subscribing.")
@lightbulb.implements(lightbulb.SlashCommand)
async def claim(ctx: lightbulb.Context) -> None:
    data = load_data()
    user_id = str(ctx.author.id)
    email = ctx.options.email
    current_time = int(time.time())

    if user_id in data['prem_users']:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
        await ctx.respond("You already have premium. Thank you! ❤️")
        try:
            await bot.rest.create_message(1285303149682364548, f"`{ctx.author.id}` tried to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` but already had premium.")
        except Exception as e:
            print(f"{e}")
        return

    if email in prem_email:
        data['prem_users'][user_id] = {
            "email": email,
            "claim_time": current_time,
        }
        prem_email.remove(email)
        save_data(data)
        await ctx.respond("You have premium now! Thank you so much. ❤️")
        try:
            await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
    else:
        embed = hikari.Embed(
            title="Invite:",
            description=(
                "Your email was not recognized. If you think this is an error, join the [support server](https://discord.com/invite/x7MdgVFUwa) to fix this issue.\n\n"
                "If you haven't yet subscribed, consider doing so for $1.99 a month. It helps cover the costs associated with running Insult Bot. ❤️\n\n"
                "Premium Perks:\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot repond to every message in set channel(s).\n"
                "• Add custom trigger-insult combos.\n"
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
            await bot.rest.create_message(1285303149682364548, f"Failed to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
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
		await event.context.respond(f"`/{event.context.command.name}` is on cooldown. Retry in `{exception.retry_after:.0f}` seconds. ⏱️\nCommands are ratelimited to prevent spam abuse. To remove cool-downs, become a [supporter](http://ko-fi.com/azaelbots/tiers).")
	else:
		raise exception

# Top.gg stop
@bot.listen(hikari.StoppedEvent)
async def on_stopping(event: hikari.StoppedEvent):
    await topgg_client.close()

bot.run()