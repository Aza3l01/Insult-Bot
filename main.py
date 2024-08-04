import hikari
import lightbulb
import random
import asyncio
import aiohttp
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
import re

load_dotenv()

hearing_string = os.getenv("HEARING_LIST")
hearing = hearing_string.split(",")

response_string = os.getenv("RESPONSE_LIST")
response = response_string.split(",")

prohibited_keywords = os.getenv("PROHIBITED_WORDS")
prohibited_words = prohibited_keywords.split(",")

# Premium lists
# prem_users = ['364400063281102852','919005754130829352','1054440117705650217']
# user_memory_preferences = {}
# custom_only_servers = []
# custom_insults = {'1193319104917024849': ['I love you redhaven', 'I love Redhaven', 'Redhaven is so good looking', 'yea sure', 'corny jawn', 'your ass', 'how was trouble', 'cum dumpster', 'Redhaven sucks', 'hawk tuah']}
# custom_triggers = {'934644448187539517': ['dick', 'fuck', 'smd', 'motherfucker', 'bellend', 'report', 'pls']}

# Free lists
used_free_trial = []
user_custom_styles = {'212990040068849664': 'Complete Asshole', '606116619915231232': 'obsessive kpop fan'}
allowed_channels_per_guild = {'857112618963566592': ['924728966739279882'], '934644448187539517': ['1139231743682019408'], '1175923285314252870': ['1175923286312484977']}
allowed_ai_channel_per_guild = {'934644448187539517': ['1266099301529161799'], '1268391505706487889': ['1268394099556220960'], '855976724322582539': ['989295674015248394'], '1034558256233861170': ['1034558256233861173'], '1268398196955025501': ['1268427592768426067'], '1259111810213085185': ['1263718166215786608'], '1116186669788446760': ['1268386978835988480'], '1264775956145373184': ['1264775956145373186'], '1256608720943579156': ['1256608721409282116'], '857112618963566592': ['924728966739279882']}

# Free trial lists
prem_users = ['364400063281102852', '919005754130829352', '1054440117705650217', '212990040068849664', '1257306182297587712', '1061144263611654144', '1126319859056250940', '891606379767423036', '1136672469978202262', '1260110675804422235']
user_memory_preferences = {'212990040068849664': True}
used_free_trial = ['1260110675804422235']
custom_only_servers = ['1227739786341650482']
custom_insults = {'1193319104917024849': ['I love you redhaven', 'I love Redhaven', 'Redhaven is so good looking', 'yea sure', 'corny jawn', 'your ass', 'how was trouble', 'cum dumpster', 'Redhaven sucks', 'hawk tuah'], '1116186669788446760': ['Your mother was a hamster and your father smelt of elderberries!', 'Shut the fuck up, ya porch monkey!', 'Melon muncher', 'Chicken bone sucker', 'You tar monkey', 'Jigaboo', 'You queef goblin', 'I bet your dick smells like vinegar fermenting in feta cheese.', "Ok, we get it. You're a lumberjack by day and a hooker by night. Next topic.", 'Border hopping taco monkey', 'Oh look, a wretched, grumpy old Canuck! Go back to your igloo, you imposter of a native!', 'I must have been very cruel in my past time to have to deal with your down syndrome ass.', 'I will smack you so hard that you turn white!', 'Go back to your igloo, Canuck!'], '1267243400583974912': ['shut up bro'], '1061161566009045052': ['bootyhole'], '1227739786341650482': ['bitch ass boy I fucked your mom long dick style'], '1268410879846912060': ['bitch ass boy I fucked your family long dick style'], '1139807526062411837': ['i dont like black kids', 'i will ask drake to go and kidnap u', 'STHU U BLACK AND CANNOT STOP YAPPING WHEN I CANT EVEN SEE U BECUZ U R THAT SHORT AND DONT SAY IM SCARED U R JUST A SCARED LITTLE BITCH IN A SHIRT EATING MY SHIT', 'STHU U BLACK AND CANNOT STOP YAPPING WHEN I CANT EVEN SEE U BECUZ U R THAT SHORT AND DONT SAY IM SCARED U R JUST A SCARED LITTLE BITCH IN A SHIRT EATING MY SHIT', 'STHU U BLACK AND CANNOT STOP YAPPING WHEN I CANT EVEN SEE U BECUZ U R THAT SHORT AND DONT SAY IM SCARED U R JUST A SCARED LITTLE BITCH IN A SHIRT EATING MY SHIT']}
custom_triggers = {'934644448187539517': ['dick', 'fuck', 'smd', 'motherfucker', 'bellend', 'report', 'pls'], '857112618963566592': ['wew'], '1116186669788446760': ['Fuck you', 'Cunt', 'Asshole', 'Dickhead', 'gringo', 'Dick'], '1139807526062411837': ['hi', 'ok', 'bitch', 'stupid', 'fuck', 'dumb', 'idiot', 'fanum tax', 'sigma', 'grimace shake', 'ohio', 'mewing', 'caseoh', 'fat', 'ugly', 'dickhead', 'dick', 'pussy', 'bruh', 'stfu', 'sthu', 'hola', 'i dont talk to negros', '@unknown-role', 'no thx', 'ur welcome', 'smth', 'ikr', 'hate', 'dont like', 'lol', 'same', 'shortie', 'shorty', 'crazy', 'teaming', 'that', 'you', 'u', 'i', 'me', 'everyone', 'admitted', 'asked', 'when', 'what', 'where', 'why', 'how', 'skibidi', 'no', 'nope', 'faster', 'stronger', 'better', 'better', 'better', 'better', 'better', 'didnt', 'great', 'ground', 'coded', '1v1', 'MAD', 'cook', 'ate', 'roar', 'uwu', 'sed', 'sad'], '855976724322582539': []}

# Other lists
prem_email = ['billhamletjr@yahoo.com', 'billhamletjr23@gmail.com']
user_reset_time = {}
user_response_count = {}
user_conversation_memory = {}

openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
bot = lightbulb.BotApp(
	intents = hikari.Intents.ALL_UNPRIVILEGED | hikari.Intents.GUILD_MESSAGES | hikari.Intents.MESSAGE_CONTENT,
	token=os.getenv("BOT_TOKEN")
)

# Top.gg
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
        system_message = "Answer questions with a mean attitude but still be helpful and keep responses very brief"

        if user_id and user_id in user_custom_styles:
            system_message = user_custom_styles[user_id]

        messages = [{"role": "system", "content": system_message}]
        if user_id and user_id in user_conversation_memory:
            messages.extend(user_conversation_memory[user_id])
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

        if user_id and user_memory_preferences.get(user_id, False):
            if user_id not in user_conversation_memory:
                user_conversation_memory[user_id] = []
            user_conversation_memory[user_id].append({"role": "user", "content": prompt})
            user_conversation_memory[user_id].append({"role": "assistant", "content": ai_response})
        
        return ai_response
    except Exception as e:
        return f"An error occurred: {str(e)}"

# Email
@bot.listen(hikari.MessageCreateEvent)
async def on_message(event: hikari.MessageCreateEvent) -> None:
    if event.channel_id == 1266481246121234554:
        email = event.message.content.strip()
        if validate_email(email):
            if email not in prem_email:
                prem_email.append(email)
                await bot.rest.create_message(1246889573141839934, f"prem_email = {prem_email}")
            else:
                await bot.rest.create_message(1246889573141839934, f"prem_email list = {prem_email}")
        else:
            await bot.rest.create_message(1246889573141839934, "The provided email is invalid.")

def validate_email(email: str) -> bool:
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

# Server count
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

    if guild_id in custom_only_servers:
        if guild_id in custom_insults and any(word in message_content for word in custom_triggers.get(guild_id, [])):
            all_responses = custom_insults[guild_id]
        else:
            return
    else:
        all_responses = response + custom_insults.get(guild_id, [])

    if any(word in message_content for word in hearing):
        selected_response = random.choice(all_responses)
        if guild_id in custom_insults and any(word in message_content for word in custom_triggers.get(guild_id, [])):
            selected_response += " (user added insult)"
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
                if guild_id in custom_insults and trigger in message_content:
                    selected_response += " (user added insult)"
                try:
                    await event.message.respond(selected_response)
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

        guild_id = str(event.guild_id)
        channel_id = str(event.channel_id)

        if mentions_bot or is_reference_to_bot:
            if guild_id in allowed_ai_channel_per_guild:
                if channel_id not in allowed_ai_channel_per_guild[guild_id]:
                    ai_channel = allowed_ai_channel_per_guild[guild_id][0]
                    ai_channel_mention = f"<#{ai_channel}>"
                    try:
                        await event.message.respond(f"{event.message.author.mention}, AI responses are set to be in {ai_channel_mention}. Please use that channel for AI interactions.")
                    except hikari.errors.ForbiddenError:
                        pass
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

                if user_response_count[user_id] >= 15:
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
                        embed.set_image("https://i.imgur.com/hxZb7Sq.gif")
                        await event.message.respond(embed=embed)
                        await bot.rest.create_message(1246886903077408838, f"Voting message was sent in `{event.get_guild().name}`")
                    else:
                        message_content = content.strip()
                        async with bot.rest.trigger_typing(channel_id):
                            ai_response = await generate_text(message_content, user_id)

                        if user_id not in prem_users:
                            user_response_count[user_id] += 1

                        user_mention = event.message.author.mention
                        response_message = f"{user_mention} {ai_response}"
                        await event.message.respond(response_message)

                else:
                    message_content = content.strip()
                    async with bot.rest.trigger_typing(channel_id):
                        ai_response = await generate_text(message_content, user_id)

                    if user_id not in prem_users:
                        user_response_count[user_id] += 1

                    user_mention = event.message.author.mention
                    response_message = f"{user_mention} {ai_response}"
                    await event.message.respond(response_message)
            else:
                message_content = content.strip()
                async with bot.rest.trigger_typing(channel_id):
                    ai_response = await generate_text(message_content, user_id)

                user_mention = event.message.author.mention
                response_message = f"{user_mention} {ai_response}"
                await event.message.respond(response_message)

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
            await ctx.respond("Message sent.")
    except hikari.errors.NotFoundError:
        await ctx.respond("I don't have access to this channel.")
    except hikari.errors.ForbiddenError:
        await ctx.respond("I don't have permission to send messages in that channel.")
    except Exception as e:
        await ctx.respond(f"An error occurred: {e}")

# Setchannel command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("toggle", "Toggle Insult Bot on/off in the selected channel.", choices=["on", "off"], type=hikari.OptionType.STRING)
@lightbulb.option("channel", "Select a channel to proceed.", type=hikari.OptionType.CHANNEL, channel_types=[hikari.ChannelType.GUILD_TEXT])
@lightbulb.option("type", "Select whether to enable 'chatbot' or 'keywords' responses in the channel.", choices=["chatbot", "keywords"], type=hikari.OptionType.STRING, required=True)
@lightbulb.command("setchannel_toggle", "Restrict Insult Bot and AI Bot to particular channel(s).")
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

# View set channels command
@bot.command
@lightbulb.command("setchannel_view", "View channel(s) Insult Bot is restricted to.")
@lightbulb.implements(lightbulb.SlashCommand)
async def viewsetchannels(ctx):
    guild = ctx.get_guild()
    if guild is not None:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used in `{guild.name}`.")
    else:
        await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used.")
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

# Chatbot----------------------------------------------------------------------------------------------------------------------------------------
# Memory command (P)
@bot.command()
@lightbulb.option('toggle', 'Choose to toggle or clear memory.', choices=['on', 'off', 'clear'])
@lightbulb.command('memory', 'Make Insult Bot remember your conversations.')
@lightbulb.implements(lightbulb.SlashCommand)
async def memory(ctx: lightbulb.Context) -> None:
    if str(ctx.author.id) not in prem_users:
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To toggle Insult Bot remember your conversations, consider becoming a [supporter](https://ko-fi.com/azaelbots) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "Get a premium free trial for a week by using the `/free` command.\n"
                "**Access Premium Commands Like:**\n"
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
        await bot.rest.create_message(1246886903077408838, f"`{ctx.author.id}` tried to invoke `{ctx.command.name}`")
        return
    
    user_id = str(ctx.author.id)
    toggle = ctx.options.toggle
    
    if toggle == 'on':
        user_memory_preferences[user_id] = True
        response_message = 'Memory has been turned on for personalized interactions.'
    elif toggle == 'off':
        user_memory_preferences[user_id] = False
        response_message = 'Memory has been turned off. Memory will not be cleared until you choose to clear it.'
    elif toggle == 'clear':
        user_memory_preferences.pop(user_id, None)
        user_conversation_memory.pop(user_id, None)
        response_message = 'Memory has been cleared.'
    else:
        response_message = 'Invalid action.'

    await ctx.respond(response_message)

    log_message = (
        f"`memory` invoked by user {ctx.author.id}\n"
        f"toggle: {toggle.capitalize()}\n"
        f"user_memory_preferences = {user_memory_preferences}\n\n"
    )
    await bot.rest.create_message(1246889573141839934, content=log_message)

# Set Style command
@bot.command()
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option('style', 'Enter a chatbot style.', type=str)
@lightbulb.command('setstyle', 'Set a custom style for Insult Bot.')
@lightbulb.implements(lightbulb.SlashCommand)
async def setstyle(ctx: lightbulb.Context) -> None:
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
    user_id = str(ctx.author.id)
    style = ctx.options.style

    user_custom_styles[user_id] = style
    await ctx.respond(f'Custom response style has been set to: "{style}"')

    # Log the style change
    log_message = (
        f"`setstyle` invoked by user {ctx.author.id}\n"
        f"Style: {style}\n"
        f"user_custom_styles = {user_custom_styles}\n\n"
    )
    await bot.rest.create_message(1246889573141839934, content=log_message)

# Keyword----------------------------------------------------------------------------------------------------------------------------------------
# Add insult command (P)
@bot.command
@lightbulb.option("insult", "Add your insult, ensuring it complies with Discord's TOS. (maximum 200 characters)", type=str)
@lightbulb.command("insult_add", "Add a custom insult to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def addinsult(ctx):
    if str(ctx.author.id) not in prem_users:
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To add custom insults to your server, consider becoming a [supporter](https://ko-fi.com/azaelbots) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "Get a premium free trial for a week by using the `/free` command.\n"
                "**Access Premium Commands Like:**\n"
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

# Remove insult command (P)
@bot.command
@lightbulb.option("insult", "The insult to remove.", type=str)
@lightbulb.command("insult_remove", "Remove a custom insult from this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def removeinsult(ctx):
    if str(ctx.author.id) not in prem_users:
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To remove custom insults added to your server, consider becoming a [supporter](https://ko-fi.com/azaelbots) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "Get a premium free trial for a week by using the `/free` command.\n"
                "**Access Premium Commands Like:**\n"
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

# View insults command (P)
@bot.command
@lightbulb.command("insult_view", "View custom insults added to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def viewinsults(ctx):
    if str(ctx.author.id) not in prem_users:
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To view custom insults added to your server, consider becoming a [supporter](https://ko-fi.com/azaelbots) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "Get a premium free trial for a week by using the `/free` command.\n"
                "**Access Premium Commands Like:**\n"
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
    await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used in `{ctx.get_guild().name}`.")

# Add trigger command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("trigger", "Add your trigger, ensuring it complies with Discord's TOS. (maximum 200 characters)", type=str)
@lightbulb.command("trigger_add", "Add a custom trigger to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def addtrigger(ctx):
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
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
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("trigger", "The trigger to remove.", type=str)
@lightbulb.command("trigger_remove", "Remove a custom trigger from this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def removetrigger(ctx):
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
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
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("trigger_view", "View custom triggers added to this server.")
@lightbulb.implements(lightbulb.SlashCommand)
async def viewtriggers(ctx):
    if any(word in str(ctx.author.id) for word in prem_users):
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
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
    await bot.rest.create_message(1246886903077408838, f"`{ctx.command.name}` was used in `{ctx.get_guild().name}`.")

# Custom only toggle command (P)
@bot.command
@lightbulb.option("toggle", "Toggle custom insults and triggers only mode on/off.", choices=["on", "off"], type=hikari.OptionType.STRING)
@lightbulb.command("customonly", "Set custom insults and triggers only.")
@lightbulb.implements(lightbulb.SlashCommand)
async def customonly(ctx):
    if str(ctx.author.id) not in prem_users:
        embed = hikari.Embed(
            title="You found a premium command",
            description=(
                "To toggle custom only triggers/insults to your server, consider becoming a [supporter](https://ko-fi.com/azaelbots) for only $1.99 a month.\n\n"
                "I will never paywall the main functions of the bot but these few extra commands help keep the bot running. ❤️\n\n"
                "Get a premium free trial for a week by using the `/free` command.\n"
                "**Access Premium Commands Like:**\n"
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
# Help command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
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
            "**/insult:** Send an insult to someone.\n"
            "**/setchannel_toggle:** Restrict Insult Bot to particular channel(s).\n"
            "**/setchannel_view:** View channel(s) Insult Bot is restricted to.\n\n"
            "**Chatbot Commands:**\n"
            "**/memory:** Make Insult Bot remember your conversations. (P)\n"
            "**/style:** Set a custom style for Insult Bot.\n\n"
            "**Keyword Commands:**\n"
            "**/insult_[add/remove/view]:** Add/view/remove custom insults in your server. (P)\n"
            "**/trigger_[add/remove/view]:** Add/view/remove custom triggers in your server.\n"
            "**/customonly:** Set custom insults and triggers only. (P)\n\n"
            "**Miscellaneous Commands:**\n"
            "**/claim:** Claim premium by providing your Ko-fi email.\n"
            "**/invite:** Invite the bot to your server.\n"
            "**/support:** Join the support server.\n"
            "**/privacy:** View our privacy policy.\n"
            "**/free:** Get a premium free trial for a week.\n\n"
            "**To use (P) premium commands and help keep the bot running, consider becoming a [supporter](https://ko-fi.com/azaelbots) for  $1.99 a month. ❤️**\n\n"
        ),
        color=0x2B2D31
    )
    await ctx.respond(embed=embed)

# Claim premium command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.option("email", "Enter your Ko-fi email", type=str)
@lightbulb.command("claim", "Claim premium after subscribing.")
@lightbulb.implements(lightbulb.SlashCommand)
async def premium(ctx: lightbulb.Context) -> None:
    if str(ctx.author.id) in prem_users:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
        await ctx.respond("You already have premium. 🤦")
        return
    
    email = ctx.options.email
    
    if email in prem_email:
        prem_users.append(str(ctx.author.id))
        await ctx.respond("You have premium now! Thank you so much ❤️")
    else:
        await ctx.respond("Your email was not recognized. If you think this is an error, join the [support server](https://discord.com/invite/x7MdgVFUwa) to receive your perks.")

    log_message = (
        f"`{ctx.command.name}` invoked by user {ctx.author.id}\n"
        f"prem_users = {prem_users}\n\n"
    )
    await bot.rest.create_message(1246889573141839934, content=log_message)

# Invite command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
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

# Support command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
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
        description=("[Join the support server.](https://discord.com/invite/x7MdgVFUwa)"),
        color=0x2B2D31
    )
    await ctx.respond(embed=embed)

# Privacy command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
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

# Free premium command
@bot.command
@lightbulb.add_cooldown(length=5, uses=1, bucket=lightbulb.UserBucket)
@lightbulb.command("free", "Get premium for free for a week!")
@lightbulb.implements(lightbulb.SlashCommand)
async def premium(ctx: lightbulb.Context) -> None:
    user_id = str(ctx.author.id)

    if user_id in prem_users:
        await ctx.command.cooldown_manager.reset_cooldown(ctx)
        await ctx.respond("You already have premium. 🤦")
        return
    
    if user_id in used_free_trial:
        await ctx.respond("You have already claimed the free trial. 😔")
        return

    prem_users.append(user_id)
    used_free_trial.append(user_id)
    await ctx.respond("You have premium now! ❤️")

    log_message = (
        f"`{ctx.command.name}` invoked by user {ctx.author.id}\n"
        f"prem_users = {prem_users}\n"
        f"used_free_trial = {used_free_trial}\n"
    )
    await bot.rest.create_message(1246889573141839934, content=log_message)

# # Trial ending dm
# @bot.command
# @lightbulb.option("user_ids", "Comma-separated list of user IDs to notify.", type=str)
# @lightbulb.command("notify_users", "Notify specified users about their trial ending.")
# @lightbulb.implements(lightbulb.SlashCommand)
# async def notify_users(ctx: lightbulb.Context) -> None:
#     user_ids_str = ctx.options.user_ids
#     user_ids = [int(user_id.strip()) for user_id in user_ids_str.split(",")]
#     embed = hikari.Embed(
#         title="⌛ Free Trial Ending Soon ⌛",
#         description=(
#             "**You'll Soon Access Premium Commands Like:**\n"
#             "• Add custom insults.\n"
#             "• Insult Bot will remember your conversations.\n"
#             "• Remove cool-downs.\n"
#             "**Support Server Related Perks Like:**\n"
#             "• Access to behind the scenes discord channels.\n"
#             "• Have a say in the development of Insult Bot.\n"
#             "• Supporter exclusive channels.\n\n"
#             "To continue using premium commands, consider becoming a [supporter](https://ko-fi.com/azaelbots) for $1.99 a month. ❤️\n\n"
#             "*Any memberships bought can be refunded within 3 days of purchase.*"
#         ),
#         color=0x2B2D31
#     )

#     notified_users = []
#     for user_id in user_ids:
#         try:
#             user = await bot.rest.fetch_user(user_id)
#             await user.send(embed=embed)
#             notified_users.append(user_id)
#         except Exception as e:
#             await ctx.respond(f"Failed to notify user {user_id}: {e}")

#     if notified_users:
#         await ctx.respond(f"Notified users: {', '.join(map(str, notified_users))}")
#     else:
#         await ctx.respond("No users were notified.")

# Error handling
@bot.listen(lightbulb.CommandErrorEvent)
async def on_error(event: lightbulb.CommandErrorEvent) -> None:
	if isinstance(event.exception, lightbulb.CommandInvocationError):
		await event.context.respond(f"Something went wrong, please try again.")
		raise event.exception

	exception = event.exception.__cause__ or event.exception

	if isinstance(exception, lightbulb.CommandIsOnCooldown):
		await event.context.respond(f"`/{event.context.command.name}` is on cooldown. Retry in `{exception.retry_after:.0f}` seconds. ⏱️\nCommands are ratelimited to prevent spam abuse which could bring the bot down. To remove cool-downs, become a [supporter](https://ko-fi.com/azaelbots).")
	else:
		raise exception

# Top.gg stop
@bot.listen(hikari.StoppedEvent)
async def on_stopping(event: hikari.StoppedEvent) -> None:
    await topgg_client.close()

bot.run()