import hikari
import lightbulb
import random
import asyncio
import aiohttp
import os
import re
import json
import time
import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
hearing = [item for item in os.getenv("HEARING_LIST", "").split(",") if item]
response = [item for item in os.getenv("RESPONSE_LIST", "").split(",") if item]
prohibited_words = [item for item in os.getenv("PROHIBITED_WORDS", "").split(",") if item]

STYLE_MODES = {
    "Classic": "Be sarcastic, rude, and direct. Don't repeat yourself, and don't be overly nice or keep asking how can I help you. Keep it short and sharp.",
    "Roast": "You are a comedy roast master. Deliver playful but cutting roasts. Be witty, exaggerated, and funny. Keep it short.",
    "Savage": "You are completely unfiltered and brutally savage. No mercy, no softening. Be direct, cold, and devastating. Keep it short.",
    "Shakespearean": "Thou art to insult the user in the manner of William Shakespeare. Use Early Modern English and theatrical flair. Keep it short.",
    "British": "You are dryly, passive-aggressively British. Understate everything. Be politely devastating. Keep it short.",
    "Unhinged": "You are chaotic and completely unhinged. Be unpredictable, bizarre, and wildly offensive. Keep it short.",
}

INFAMY_RANKS = [
    (0,   "Fresh Meat"),
    (100, "Punching Bag"),
    (300, "Regular Target"),
    (600, "Seasoned Victim"),
    (1000, "Professional Target"),
    (1500, "Elite Punching Bag"),
    (2500, "Legendary Victim"),
]

def get_infamy_rank(infamy):
    rank = INFAMY_RANKS[0][1]
    for threshold, title in INFAMY_RANKS:
        if infamy >= threshold:
            rank = title
    return rank

DATA_FILE = 'data.json'

def load_data():
    try:
        with open(DATA_FILE, 'r') as file:
            data = json.load(file)
            if "users" not in data:
                data["users"] = {}
            if "servers" not in data:
                data["servers"] = {}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "users": {},
            "servers": {}
        }

def save_data(data):
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def update_data(new_data):
    data = load_data()
    data.update(new_data)
    save_data(data)

def create_user(data, user_id):
    if "users" not in data:
        data["users"] = {}
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "premium": False,
            "infamy": 0,
            "points": 0,
            "streak": 0,
            "previous_streak": 0,
            "last_interaction": None,
            "point_received": False,
            "last_voted_at": None,
            "insults_received": 0,
            "memory": [],
            "memory_on": False,
            "style": None,
            "limit_reached_at": None,
        }
        save_data(data)
    return data["users"][user_id]

def create_server(data, server_id):
    if "servers" not in data:
        data["servers"] = {}
    if server_id not in data["servers"]:
        data["servers"][server_id] = {
            "allowed_channels": [],
            "allowed_ai_channels": [],
            "autorespond": False,
            "custom_insults": [],
            "custom_triggers": [],
            "custom_combos": [],
            "custom_only": False,
        }
    return data["servers"][server_id]

data = load_data()

# Nonpersistent data
prem_email = []
user_response_count = {}
user_reset_time = {}

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

        system_message = STYLE_MODES["Classic"]

        if user_id:
            user_data = create_user(data, user_id)
            selected_style = user_data.get("style")
            if selected_style and selected_style in STYLE_MODES:
                system_message = STYLE_MODES[selected_style]

        messages = [{"role": "system", "content": system_message}]

        if user_id:
            user_data = data["users"][user_id]
            if user_data.get("memory_on") and user_data.get("memory"):
                messages.extend(user_data["memory"])

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

        if user_id:
            user_data = data["users"][user_id]
            if user_data.get("memory_on"):
                user_data["memory"].append({"role": "user", "content": prompt})
                user_data["memory"].append({"role": "assistant", "content": ai_response})
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
    await topgg_client.setup()  # Initialize aiohttp.ClientSession
    asyncio.create_task(daily_maintenance())
    while True:
        guilds = await bot.rest.fetch_my_guilds()
        server_count = len(guilds)
        await bot.update_presence(
            activity=hikari.Activity(
                name=f"{server_count} servers! | /help",
                type=hikari.ActivityType.WATCHING,
            )
        )
        await topgg_client.post_guild_count(server_count)  # Call the method here
        await asyncio.sleep(3600)

# Daily maintenance
async def daily_maintenance():
    while True:
        now = datetime.datetime.now(datetime.timezone.utc)
        next_reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        await asyncio.sleep((next_reset - now).total_seconds())

        data = load_data()
        current_time = time.time()
        current_date = datetime.datetime.fromtimestamp(current_time, tz=datetime.timezone.utc).date()

        for user_id, user_data in data["users"].items():
            if user_data.get("last_interaction"):
                last_date = datetime.datetime.fromtimestamp(
                    user_data["last_interaction"], tz=datetime.timezone.utc
                ).date()
                days_since = (current_date - last_date).days
                if days_since > 1:
                    user_data["previous_streak"] = user_data.get("streak", 0)
                    user_data["streak"] = 0

        save_data(data)

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
                        "Feel free to join the [support server](https://discord.com/invite/x7MdgVFUwa) for any help!"
                    ),
                    color=0x2B2D31
                )
                embed.set_footer("Insult Bot is under extensive development, expect to see updates regularly!")
                try:
                    await channel.send(embed=embed)
                    await bot.rest.create_message(1285303149682364548, f"Joined `{guild.name}` with message.")
                except hikari.errors.ForbiddenError:
                    await bot.rest.create_message(1285303149682364548, f"Joined `{guild.name}` without message.")
                break
        else:
            await bot.rest.create_message(1285303149682364548, f"Joined `{guild.name}` and no channel found.")
    else:
        await bot.rest.create_message(1285303149682364548, "Joined unknown server.")

# Leave event
@bot.listen(hikari.GuildLeaveEvent)
async def on_guild_leave(event):
    guild = event.old_guild
    if guild is not None:
        await bot.rest.create_message(1285303149682364548, f"Left `{guild.name}`.")

# Core----------------------------------------------------------------------------------------------------------------------------------------
# Message event listener
async def should_process_event(event: hikari.MessageCreateEvent) -> bool:
    bot_id = bot.get_me().id
    guild_id = str(event.guild_id)

    data = load_data()
    server_data = data.get("servers", {}).get(guild_id, {})
    allowed_channels = server_data.get("allowed_channels", [])
    if allowed_channels:
        if str(event.channel_id) not in allowed_channels:
            return False

    message_content = event.message.content.lower() if isinstance(event.message.content, str) else ""
    mentions_bot = f"<@{bot_id}>" in message_content
    
    if event.message.message_reference:
        referenced_message_id = event.message.message_reference.id
        if referenced_message_id:
            try:
                referenced_message = await bot.rest.fetch_message(event.channel_id, referenced_message_id)
                if referenced_message.author.id == bot_id:
                    return False
            except (hikari.errors.ForbiddenError, hikari.errors.NotFoundError, hikari.errors.BadRequestError):
                pass

    return not mentions_bot

@bot.listen(hikari.GuildMessageCreateEvent)
async def on_general_message(event: hikari.GuildMessageCreateEvent):
    if not event.is_human or not await should_process_event(event):
        return

    message_content = event.content.lower() if isinstance(event.content, str) else ""
    guild_id = str(event.guild_id)

    data = load_data()
    server_data = data.get("servers", {}).get(guild_id, {})
    custom_combos = server_data.get("custom_combos", [])
    custom_insults = server_data.get("custom_insults", [])
    custom_triggers = server_data.get("custom_triggers", [])

    all_responses = []

    for trigger, insult in custom_combos:
        if trigger.lower() in message_content:
            try:
                await event.message.respond(insult)
            except (hikari.errors.BadRequestError, hikari.errors.ForbiddenError):
                pass
            await asyncio.sleep(15)
            return

    if any(word in message_content for word in custom_triggers):
        all_responses = list(custom_insults)

    if custom_insults:
        all_responses.extend(custom_insults)
    all_responses.extend(hearing)

    if all_responses:
        for trigger, insult in custom_combos:
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

        for trigger in custom_triggers:
            if trigger.lower() in message_content:
                selected_response = random.choice(all_responses)
                try:
                    await event.message.respond(selected_response)
                except hikari.errors.ForbiddenError:
                    pass
                await asyncio.sleep(15)
                break

# AI response message event listener
@bot.listen(hikari.GuildMessageCreateEvent)
async def on_ai_message(event: hikari.GuildMessageCreateEvent):
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
    server_data = data.get("servers", {}).get(guild_id, {})
    user_id = str(event.message.author.id)
    real_time = time.time()
    reset_time = user_reset_time.get(user_id, 0)
    user_data = create_user(data, user_id)

    # Rate limit check (persisted across restarts)
    limit_reached_at = user_data.get("limit_reached_at")
    if limit_reached_at:
        if real_time - limit_reached_at < 21600:
            return
        else:
            user_data["limit_reached_at"] = None
            save_data(data)

    autorespond = server_data.get("autorespond", False)
    allowed_ai_channels = server_data.get("allowed_ai_channels", [])
    should_respond = autorespond or mentions_bot or is_reference_to_bot
    if not should_respond:
        return

    if allowed_ai_channels and channel_id not in allowed_ai_channels:
        return

    is_premium = user_data.get("premium", False)

    last_interaction = user_data.get("last_interaction")
    if last_interaction:
        last_date = datetime.datetime.fromtimestamp(last_interaction, tz=datetime.timezone.utc).date()
        current_date = datetime.datetime.fromtimestamp(real_time, tz=datetime.timezone.utc).date()
        if current_date > last_date:
            user_data["streak"] = user_data.get("streak", 0) + 1
            points_to_add = 10 + (5 * user_data["streak"])
            if is_premium:
                points_to_add *= 2
            user_data["points"] = user_data.get("points", 0) + points_to_add

    user_data["last_interaction"] = real_time
    user_data["infamy"] = user_data.get("infamy", 0) + 1
    user_data["insults_received"] = user_data.get("insults_received", 0) + 1
    save_data(data)

    if not is_premium:
        if real_time - reset_time > 21600:
            user_response_count[user_id] = 0
            user_reset_time[user_id] = real_time
        else:
            if user_id not in user_response_count:
                user_response_count[user_id] = 0
                user_reset_time[user_id] = real_time

        if user_response_count.get(user_id, 0) >= 20:
            has_voted = await topgg_client.get_user_vote(user_id)
            if not has_voted:
                embed = hikari.Embed(
                    title="Limit Reached :(",
                    description=(
                        f"{event.message.author.mention}, limit resets in `6 hours`.\n\n"
                        "If you want to continue for free, [vote](https://top.gg/bot/801431445452750879/vote) to gain unlimited access for the next 12 hours or become a [supporter](https://ko-fi.com/azaelbots) for $3.99 a month.\n\n"
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
                try:
                    await bot.rest.create_message(1285303149682364548, f"Voting message sent in `{event.get_guild().name}` to `{event.author.id}`.")
                except Exception:
                    pass
                user_data["limit_reached_at"] = real_time
                save_data(data)
                return
            else:
                # Voted — grant bonus points
                if not user_data.get("point_received"):
                    bonus = 100 if is_premium else 50
                    user_data["points"] = user_data.get("points", 0) + bonus
                    user_data["point_received"] = True
                    user_data["last_voted_at"] = real_time
                    save_data(data)

    async with bot.rest.trigger_typing(channel_id):
        ai_response = await generate_text(content, user_id)

    user_response_count[user_id] = user_response_count.get(user_id, 0) + 1
    response_message = f"{event.message.author.mention} {ai_response}"
    try:
        await event.message.respond(response_message)
    except hikari.errors.ForbiddenError:
        pass

# DM message listener
@bot.listen(hikari.DMMessageCreateEvent)
async def on_dm_message(event: hikari.DMMessageCreateEvent):
    if event.message.author.is_bot:
        return

    user_id = str(event.message.author.id)
    data = load_data()
    user_data = create_user(data, user_id)
    is_premium = user_data.get("premium", False)

    if not is_premium:
        embed = hikari.Embed(
            title="DMs are a Premium Feature",
            description=(
                "To chat with Insult Bot in DMs, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $3.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "**Access Premium Commands Like:**\n"
                "• Chat with Insult Bot in DMs.\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot respond to every message in set channel(s).\n"
                "• Add custom trigger-insult combos.\n"
                "• Insult Bot will remember your conversations.\n"
                "• Remove cool-downs.\n\n"
                "*Any memberships bought can be refunded within 3 days of purchase.*"
            ),
            color=0x2B2D31
        )
        embed.set_image("https://i.imgur.com/rcgSVxC.gif")
        await event.message.respond(embed=embed)
        return

    content = event.message.content or ""
    real_time = time.time()

    # Rate limit check (persisted across restarts)
    limit_reached_at = user_data.get("limit_reached_at")
    if limit_reached_at:
        if real_time - limit_reached_at < 21600:
            return
        else:
            user_data["limit_reached_at"] = None
            save_data(data)

    user_data["last_interaction"] = real_time
    user_data["infamy"] = user_data.get("infamy", 0) + 1
    user_data["insults_received"] = user_data.get("insults_received", 0) + 1
    save_data(data)

    async with bot.rest.trigger_typing(event.channel_id):
        ai_response = await generate_text(content, user_id)

    try:
        await event.message.respond(ai_response)
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
    user_data = create_user(data, str(ctx.author.id))

    if user_data.get("premium", False):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    
    channel = ctx.options.channel
    user = ctx.options.user
    insult = ctx.options.insult
    target_channel = ctx.channel_id if channel is None else channel.id
    
    if insult and any(word in insult.lower() for word in prohibited_words):
        await ctx.respond("Your insult does not comply with Discord's TOS.")
        return
    
    guild_id = str(ctx.guild_id)
    server_data = data.get("servers", {}).get(guild_id, {})
    srv_custom_insults = server_data.get("custom_insults", [])
    if srv_custom_insults:
        all_responses = response + srv_custom_insults
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
    user_data = create_user(data, str(ctx.author.id))
    guild_id = str(ctx.guild_id)
    server_data = create_server(data, guild_id)
    is_premium_user = user_data.get("premium", False)

    if is_premium_user:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    member = await ctx.bot.rest.fetch_member(ctx.guild_id, ctx.author.id)
    is_admin = any(role.permissions & hikari.Permissions.ADMINISTRATOR for role in member.get_roles())

    if not is_admin and not is_premium_user:
        await ctx.respond("Ask your admins or upgrade to premium to set this up. 🤦")
        try:
            await bot.rest.create_message(1285303149682364548, f"Failed to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
        except Exception as e:
            print(f"{e}")
        return

    toggle = ctx.options.toggle
    channel_id = str(ctx.options.channel.id) if ctx.options.channel else None
    channel_type = ctx.options.type

    if toggle == "on":
        if channel_type == "replybot":
            if channel_id and channel_id not in server_data["allowed_channels"]:
                server_data["allowed_channels"].append(channel_id)
                await ctx.respond(f"Insult Bot will only respond with replybot in <#{channel_id}>.")
            elif channel_id in server_data["allowed_channels"]:
                await ctx.respond(f"Insult Bot is already restricted to replybot in <#{channel_id}>.")
            else:
                await ctx.respond("Please specify a valid channel.")
        elif channel_type == "chatbot":
            if channel_id and channel_id not in server_data["allowed_ai_channels"]:
                server_data["allowed_ai_channels"].append(channel_id)
                await ctx.respond(f"Insult Bot will only respond as a chatbot in <#{channel_id}>.")
            elif channel_id in server_data["allowed_ai_channels"]:
                await ctx.respond(f"Insult Bot is already a chatbot in <#{channel_id}>.")
            else:
                await ctx.respond("Please specify a valid channel.")
    elif toggle == "off":
        if channel_type == "replybot" and channel_id in server_data["allowed_channels"]:
            server_data["allowed_channels"].remove(channel_id)
            await ctx.respond(f"Bot's restriction to send replybot in <#{channel_id}> has been removed.")
        elif channel_type == "chatbot" and channel_id in server_data["allowed_ai_channels"]:
            server_data["allowed_ai_channels"].remove(channel_id)
            await ctx.respond(f"Bot's restriction as a chatbot in <#{channel_id}> has been removed.")
        else:
            await ctx.respond("Channel is not currently restricted.")
    else:
        await ctx.respond("Invalid toggle. Use `/setchannel on <#channel>` or `/setchannel off <#channel>`.")

    save_data(data)

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
    user_data = create_user(data, str(ctx.author.id))
    guild_id = str(ctx.guild_id)
    server_data = data.get("servers", {}).get(guild_id, {})

    if user_data.get("premium", False):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    keyword_channels = server_data.get("allowed_channels", [])
    chatbot_channels = server_data.get("allowed_ai_channels", [])

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

    user_data = create_user(data, user_id)
    if not user_data.get("premium", False):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To toggle Insult Bot to auto respond in your server, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $3.99 a month.\n\n"
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

    server_data = create_server(data, server_id)

    if not server_data.get("allowed_ai_channels"):
        await ctx.respond("Please set a channel for AI responses using the `/setchannel_toggle` command before enabling autorespond.")
        return

    toggle = ctx.options.toggle
    if toggle == "on":
        if not server_data.get("autorespond"):
            server_data["autorespond"] = True
            await ctx.respond("Autorespond has been enabled for this server.")
        else:
            await ctx.respond("Autorespond is already enabled for this server.")
    elif toggle == "off":
        if server_data.get("autorespond"):
            server_data["autorespond"] = False
            await ctx.respond("Autorespond has been disabled for this server.")
        else:
            await ctx.respond("Autorespond is already disabled for this server.")

    save_data(data)

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Memory command (P)
@bot.command()
@lightbulb.option('toggle', 'Toggle memory on or off.', choices=['on', 'off'])
@lightbulb.command('memory', 'Make Insult Bot remember your conversations. (Premium Only)')
@lightbulb.implements(lightbulb.SlashCommand)
async def memory(ctx: lightbulb.Context) -> None:
    user_id = str(ctx.author.id)
    toggle = ctx.options.toggle
    data = load_data()
    user_data = create_user(data, user_id)
    if not user_data.get("premium", False):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To toggle Insult Bot to remember your conversations, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $3.99 a month.\n\n"
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

    await ctx.command.cooldown_manager.reset_cooldown(ctx)

    if toggle == 'on':
        user_data["memory_on"] = True
        response_message = 'Memory has been turned on. I\'ll remember our conversations!'
    elif toggle == 'off':
        user_data["memory_on"] = False
        response_message = 'Memory has been turned off. I\'ll stop remembering new messages.'
    else:
        response_message = 'Invalid action.'

    save_data(data)
    await ctx.respond(response_message)

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Set Style command (P)
@bot.command()
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option('style', 'Choose a style for Insult Bot.', choices=list(STYLE_MODES.keys()), type=str)
@lightbulb.command('style_set', 'Set a roast style for Insult Bot. (Premium Only)')
@lightbulb.implements(lightbulb.SlashCommand)
async def setstyle(ctx: lightbulb.Context) -> None:
    user_id = str(ctx.author.id)
    data = load_data()
    user_data = create_user(data, user_id)

    if not user_data.get("premium", False):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To set a custom roast style, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $3.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "**Available Styles:** Classic, Roast, Savage, Shakespearean, British, Unhinged\n\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot respond to every message in set channel(s).\n"
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

    await ctx.command.cooldown_manager.reset_cooldown(ctx)
    selected_style = ctx.options.style
    user_data["style"] = selected_style if selected_style != "Classic" else None
    save_data(data)
    await ctx.respond(f'Roast style set to **{selected_style}**.')

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# View style command
@bot.command()
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command('style_view', 'View your current roast style. (Premium Only)')
@lightbulb.implements(lightbulb.SlashCommand)
async def viewstyle(ctx: lightbulb.Context) -> None:
    user_id = str(ctx.author.id)
    data = load_data()
    user_data = create_user(data, user_id)
    if not user_data.get("premium", False):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To view and manage your roast style, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $3.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot respond to every message in set channel(s).\n"
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

    await ctx.command.cooldown_manager.reset_cooldown(ctx)
    style = user_data.get("style") or "Classic"
    await ctx.respond(f'Your current roast style is: **{style}**.')

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Clear style command
@bot.command()
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command('style_clear', 'Reset your roast style to Classic. (Premium Only)')
@lightbulb.implements(lightbulb.SlashCommand)
async def clearstyle(ctx: lightbulb.Context) -> None:
    user_id = str(ctx.author.id)
    data = load_data()
    user_data = create_user(data, user_id)
    if not user_data.get("premium", False):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To view and manage your roast style, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $3.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "**Access Premium Commands Like:**\n"
                "• Unlimited responses from Insult Bot.\n"
                "• Have Insult Bot respond to every message in set channel(s).\n"
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

    await ctx.command.cooldown_manager.reset_cooldown(ctx)
    user_data["style"] = None
    save_data(data)
    await ctx.respond("Your roast style has been reset to **Classic**.")

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
    data = load_data()
    user_data = create_user(data, str(ctx.author.id))
    if user_data.get("premium", False):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    server_id = str(ctx.guild_id)
    insult = ctx.options.insult

    if len(insult) > 200:
        await ctx.respond("Your insult is too long. Keep it under 200 characters.")
        return

    if any(prohibited_word in insult.lower() for prohibited_word in prohibited_words):
        await ctx.respond("Your insult does not comply with Discord's TOS.")
        return

    server_data = create_server(data, server_id)
    server_data["custom_insults"].append(insult)
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
    data = load_data()
    user_data = create_user(data, str(ctx.author.id))
    if user_data.get("premium", False):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    server_id = str(ctx.guild_id)
    insult_to_remove = ctx.options.insult

    server_data = data.get("servers", {}).get(server_id, {})
    if not server_data.get("custom_insults"):
        await ctx.respond("No insults found.")
        return

    if insult_to_remove not in server_data["custom_insults"]:
        await ctx.respond("Insult not found in the list.")
        return

    server_data["custom_insults"].remove(insult_to_remove)
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
    data = load_data()
    user_data = create_user(data, str(ctx.author.id))
    if user_data.get("premium", False):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    server_id = str(ctx.guild_id)

    server_data = data.get("servers", {}).get(server_id, {})
    insults_list = server_data.get("custom_insults", [])
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
    data = load_data()
    user_data = create_user(data, str(ctx.author.id))
    if user_data.get("premium", False):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    server_id = str(ctx.guild_id)
    trigger = ctx.options.trigger.lower()

    if len(trigger) > 200:
        await ctx.respond("Your trigger is too long. Keep it under 200 characters.")
        return

    server_data = create_server(data, server_id)

    # Check if the trigger already exists in custom_triggers
    if trigger in (t.lower() for t in server_data["custom_triggers"]):
        await ctx.respond("This trigger already exists in this server.")
        return

    # Check if the trigger already exists in custom_combos
    if any(trigger == t.lower() for t, _ in server_data["custom_combos"]):
        await ctx.respond("This trigger already exists in `/combo_add`. Please remove it from there before adding it here.")
        return

    # Add the new trigger
    server_data["custom_triggers"].append(trigger)
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
    data = load_data()
    user_data = create_user(data, str(ctx.author.id))
    if user_data.get("premium", False):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    server_id = str(ctx.guild_id)
    trigger_to_remove = ctx.options.trigger

    server_data = data.get("servers", {}).get(server_id, {})
    if not server_data.get("custom_triggers"):
        await ctx.respond("No triggers found.")
        return

    if trigger_to_remove not in server_data["custom_triggers"]:
        await ctx.respond("Trigger not found in the list.")
        return

    server_data["custom_triggers"].remove(trigger_to_remove)
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
    data = load_data()
    user_data = create_user(data, str(ctx.author.id))
    if user_data.get("premium", False):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    server_id = str(ctx.guild_id)

    server_data = data.get("servers", {}).get(server_id, {})
    triggers_list = server_data.get("custom_triggers", [])
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
    user_data = create_user(data, user_id)

    if not user_data.get("premium", False):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To add custom combos to your server, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $3.99 a month.\n\n"
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

    server_data = create_server(data, server_id)

    # Check if the trigger already exists in custom_combos
    if any(trigger == t.lower() for t, _ in server_data["custom_combos"]):
        await ctx.respond("This trigger already exists in `/combo_add`. Please remove it from there before adding it here.")
        return

    # Check if the trigger already exists in custom_triggers
    if trigger in (t.lower() for t in server_data["custom_triggers"]):
        await ctx.respond("This trigger already exists in `/trigger_add`. Please remove it from there before adding it here.")
        return

    # Add the new combo
    server_data["custom_combos"].append((trigger, insult))
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
    user_data = create_user(data, user_id)

    if not user_data.get("premium", False):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To remove custom combos from your server, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $3.99 a month.\n\n"
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
    server_data = data.get("servers", {}).get(server_id, {})

    if not server_data.get("custom_combos"):
        await ctx.respond("No combos found.")
        return

    combos = server_data["custom_combos"]
    filtered_combos = [combo for combo in combos if combo[0] != trigger_to_remove]

    if len(filtered_combos) == len(combos):
        await ctx.respond("Combo not found.")
        return

    server_data["custom_combos"] = filtered_combos
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
    user_data = create_user(data, user_id)

    if not user_data.get("premium", False):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To view custom combos in your server, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $3.99 a month.\n\n"
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

    server_data = data.get("servers", {}).get(server_id, {})
    combos = server_data.get("custom_combos", [])
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
    user_data = create_user(data, user_id)

    if not user_data.get("premium", False):
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To toggle custom only triggers/insults for your server, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for only $3.99 a month.\n\n"
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

    server_data = create_server(data, server_id)
    if ctx.options.toggle == "on":
        if not server_data.get("custom_only"):
            server_data["custom_only"] = True
            await ctx.respond(f"Custom insults and triggers only mode enabled for this server.")
        else:
            await ctx.respond(f"Custom insults and triggers only mode is already enabled for this server.")
    elif ctx.options.toggle == "off":
        if server_data.get("custom_only"):
            server_data["custom_only"] = False
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
# Memory clear command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("memory_clear", "Clear Insult Bot's memory of your conversations.")
@lightbulb.implements(lightbulb.SlashCommand)
async def memory_clear(ctx: lightbulb.Context):
    user_id = str(ctx.author.id)
    data = load_data()
    user_data = create_user(data, user_id)
    if user_data.get("premium", False):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    if user_data["memory"]:
        user_data["memory"] = []
        save_data(data)
        await ctx.respond("Your conversation memory has been cleared.")
    else:
        await ctx.respond("There's no memory to clear.")

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Reset data command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("reset_data", "Reset all your saved data permanently.")
@lightbulb.implements(lightbulb.SlashCommand)
async def reset_data(ctx: lightbulb.Context):
    user_id = str(ctx.author.id)
    data = load_data()
    user_data = create_user(data, user_id)
    if user_data.get("premium", False):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    if user_id in data.get("users", {}):
        was_premium = data["users"][user_id].get("premium", False)
        del data["users"][user_id]
        if was_premium:
            create_user(data, user_id)
            data["users"][user_id]["premium"] = True
        await ctx.respond("You have no saved data to delete.")

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Profile command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("profile", "View your Insult Bot profile.")
@lightbulb.implements(lightbulb.SlashCommand)
async def profile(ctx: lightbulb.Context):
    user_id = str(ctx.author.id)
    data = load_data()
    user_data = create_user(data, user_id)
    is_premium = user_data.get("premium", False)
    if is_premium:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    has_voted = await topgg_client.get_user_vote(user_id)

    # Grant vote points if not yet received
    if has_voted and not user_data.get("point_received"):
        bonus = 100 if is_premium else 50
        user_data["points"] = user_data.get("points", 0) + bonus
        user_data["point_received"] = True
        user_data["last_voted_at"] = time.time()
        save_data(data)

    style = user_data.get("style") or "Classic"
    infamy = user_data.get("infamy", 0)
    rank = get_infamy_rank(infamy)

    embed = hikari.Embed(
        color=0x2B2D31,
        description=(
            f"Rank: **{rank}**\n\n"
            "Get roasted daily to climb the ranks.\n"
            "Use the `/top` command to see where you stand.\n\n"
            "[Vote to earn bonus points.](https://top.gg/bot/801431445452750879/vote)"
        )
    )
    embed.set_author(name=f"{ctx.author.username}'s Profile", icon=ctx.author.avatar_url)
    embed.add_field(name="Streak", value=f"🔥 {user_data.get('streak', 0)} days", inline=True)
    embed.add_field(name="Infamy", value=f"💀 {infamy}", inline=True)
    embed.add_field(name="Points", value=f"🏅 {user_data.get('points', 0)}", inline=True)
    embed.add_field(name="Insults Received", value=f"🎯 {user_data.get('insults_received', 0)}", inline=True)
    embed.add_field(name="Style", value=f"🎨 {style}", inline=True)
    embed.add_field(name="Premium", value=f'{"✅ Active" if is_premium else "❌ Not Active"}', inline=True)

    await ctx.respond(embed=embed)

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")

# Leaderboard command
@bot.command
@lightbulb.command("top", "View the Infamy leaderboard.", auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def leaderboard(ctx: lightbulb.Context):
    data = load_data()
    current_user_id = str(ctx.author.id)
    current_user_data = create_user(data, current_user_id)
    if current_user_data.get("premium", False) and ctx.command.cooldown_manager:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    all_users = [
        {"user_id": uid, **udata}
        for uid, udata in data.get("users", {}).items()
    ]
    sorted_users = sorted(all_users, key=lambda x: x.get("infamy", 0), reverse=True)
    top_5 = sorted_users[:5]

    current_user_rank = next(
        (i + 1 for i, u in enumerate(sorted_users) if u["user_id"] == current_user_id), None
    )
    current_user_data = next((u for u in sorted_users if u["user_id"] == current_user_id), None)

    embed = hikari.Embed(title="💀 Infamy Leaderboard 💀", color=0x2B2D31)

    top_list = []
    for idx, user in enumerate(top_5, 1):
        try:
            user_obj = await bot.rest.fetch_user(int(user["user_id"]))
            username = user_obj.username
        except Exception:
            username = "Unknown User"
        rank = get_infamy_rank(user.get("infamy", 0))
        entry = (
            f"`#{idx}` {username}\n"
            f"Infamy: {user.get('infamy', 0)} • Streak: {user.get('streak', 0)} • {rank}"
        )
        top_list.append(entry)

    embed.add_field(
        name="Top 5",
        value="\n\n".join(top_list) if top_list else "No users yet!",
        inline=False
    )

    if current_user_data and current_user_rank:
        rank = get_infamy_rank(current_user_data.get("infamy", 0))
        try:
            current_user_obj = await bot.rest.fetch_user(int(current_user_id))
            current_username = current_user_obj.username
        except Exception:
            current_username = ctx.author.username
        embed.add_field(
            name="You",
            value=(
                f"`#{current_user_rank}` {current_username}\n"
                f"Infamy: {current_user_data.get('infamy', 0)} • Streak: {current_user_data.get('streak', 0)} • {rank}"
            ),
            inline=False
        )

    await ctx.respond(embed=embed)

    try:
        await bot.rest.create_message(1285303149682364548, f"`{ctx.command.name}` invoked in `{ctx.get_guild().name}` by `{ctx.author.id}`.")
    except Exception as e:
        print(f"{e}")
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("help", "You know what this is ;)")
@lightbulb.implements(lightbulb.SlashCommand)
async def help(ctx):
    data = load_data()
    user_data = create_user(data, str(ctx.author.id))
    if user_data.get("premium", False):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)

    embed = hikari.Embed(
        title="📚 Help 📚",
        description=(
            "**__Getting Started__**\n"
            "- Reply or ping Insult Bot in chat to get a response.\n"
            "- Use `/setchannel_toggle` to set channels for the bot to respond in.\n"
            "- Use `/claim` to receive your perks after becoming a supporter.\n\n"

            "**__Core Commands__**\n"
            "- **/insult:** Send an insult to someone.\n"
            "- **/setchannel_toggle:** Restrict Insult Bot to particular channel(s).\n"
            "- **/setchannel_view:** View channel(s) Insult Bot is restricted to.\n\n"

            "**__Chatbot Commands__**\n"
            "- **/autorespond:** Have Insult Bot respond to every message in a set channel(s). (P)\n"
            "- **/memory:** Make Insult Bot remember your conversations. (P)\n"
            "- **/memory_clear:** Clear Insult Bot's memory of your conversations.\n"
            "- **/style_set:** Set a roast style for Insult Bot. (P)\n"
            "- **/style_view:** View your current roast style. (P)\n"
            "- **/style_clear:** Reset your roast style to Classic. (P)\n\n"

            "**__Replybot Commands__**\n"
            "- **/insult_[add/remove/view]:** Add/remove/view custom insults.\n"
            "- **/trigger_[add/remove/view]:** Add/remove/view custom triggers.\n"
            "- **/combo_[add/remove/view]:** Add/remove/view trigger-insult combos. (P)\n"
            "- **/customonly:** Set custom insults and triggers only. (P)\n\n"

            "**__Profile & Leaderboard__**\n"
            "- **/profile:** View your Infamy rank, streak, points, and stats.\n"
            "- **/top:** View the global Infamy leaderboard.\n"
            "- **/reset_data:** Permanently delete all your saved data.\n\n"

            "**__Premium__**\n"
            "- To use (P) premium commands and help cover costs, consider becoming a [supporter](http://ko-fi.com/azaelbots/tiers) for $3.99 a month. ❤️\n"
            "- Premium users get: unlimited responses, cooldown bypass, memory, custom roast styles, and more.\n\n"

            "**__Troubleshooting and Suggestions__**\n"
            "For suggestions and help, feel free to join the [support server](https://discord.com/invite/x7MdgVFUwa). My developer will be happy to help! "
            "[Click here](https://discord.com/api/oauth2/authorize?client_id=801431445452750879&permissions=414464727104&scope=applications.commands%20bot), to invite the bot to your server.\n\n"
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
    server_id = str(ctx.guild_id)
    user_data = create_user(data, user_id)

    if user_data.get("premium", False):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
        await ctx.respond("You already have premium. 🤦")
        try:
            await bot.rest.create_message(1285303149682364548, f"`{ctx.author.id}` tried to invoke `{ctx.command.name}` in `{ctx.get_guild().name}` but already had premium.")
        except Exception as e:
            print(f"{e}")
        return
    
    email = ctx.options.email
    
    if email in prem_email:
        user_data["premium"] = True
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
                "If you haven't yet subscribed, consider doing so for $3.99 a month. It helps cover the costs associated with running Insult Bot. ❤️\n\n"
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