import hikari
import lightbulb
import random
import asyncio

bot = lightbulb.BotApp(
	intents = hikari.Intents.GUILD_MESSAGES | hikari.Intents.MESSAGE_CONTENT,
	token = 'ODAxNDMxNDQ1NDUyNzUwODc5.G82qGH.zqBwCgebcJ5sbbfxmpZaNifVQguEc7k3i3NvVo'
)

hearing = [
	'no you', 'no u', 'fuck you', 'fuck u', 'shut up', 'stfu', 'asshole', 'idiot', 'fuck yourself', 'pussy', 
	'bitch', 'cunt', 'shithead', 'fuck off', 'you\'re gay', 'ur gay', 'your gay', 'suck my dick', 'suck a dick', 
	'shut your mouth', 'dumbass', 'twat', 'you\'re dumb', 'your dumb', 'kys', 'kill yourself', 'kill urself', 
	'wanker', 'tosser', 'ming', 'prick', 'clunge', 'slut', 'bastard', 'twit', 'pillock', 'bint', 'asslicker',
	'asswipe', 'nob jocky', 'your mom', 'you\'re mom', 'minger', 'little shit'
]

response = [
	'no u', 'fuck you', 'your mom', 'stfu', 'bruh', 'dickhead', 'asshole', 'idiot', 'you can do better', 
	'stfu inbred', 'yeah', 'scumbag', 'shithead', 'scumbag', 'go fuck yourself', 'insecure turd goblin', 
	'pussy', 'bitch pls', 'fuck off', 'shut your mouth', 'dumbass', 'you\'re dumb'
]

prem_users = [
	'364400063281102852', '601858736205856768'
]

#server count
@bot.listen()
async def on_starting(_: hikari.StartedEvent) -> None:
	await bot.update_presence(
		activity=hikari.Activity(
			name=f"{len([*await bot.rest.fetch_my_guilds()])} servers! | /help",
			type=hikari.ActivityType.WATCHING,
		)
	)

#main thing
@bot.listen(hikari.MessageCreateEvent)
async def on_message(event):
	#print(f"Received message: {event.content}")
	if event.is_human:
		if isinstance(event.content, str):
			if any(word in event.content.lower() for word in hearing):
				await event.message.respond(random.choice(response))
				await asyncio.sleep(10)

#help command
@bot.command
@lightbulb.add_cooldown(length = 30, uses = 1, bucket = lightbulb.UserBucket)
@lightbulb.command('help', 'You know what this is ;)')
@lightbulb.implements(lightbulb.SlashCommand)
async def help(ctx):
	await bot.rest.create_message(1013490212736876594, f"`{ctx.command.name}` was used.")
	if any(word in str(ctx.author.id) for word in prem_users):
		await ctx.command.cooldown_manager.reset_cooldown(ctx)
		embed = hikari.Embed(
			title = '__**Commands**__',
			description = '**__Main:__** \n **/insult:** Generate a random insult. \n **/list:** List of all the insults. \n \n **__Misc:__** \n **/invite:** Get the bot\'s invite link. \n **/vote:** Get the link to vote at top.gg. \n **/support:** Invite to join the support server. \n **/donate:** Donate to support Insult Bot \n **/more:** Check out more bots from me.',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)
		embed = embed = hikari.Embed(
		title = '',
			description = '**Thank you!** \n If you like using Insult Bot, consider [voting](https://top.gg/bot/801431445452750879/vote) or leaving a [review](https://top.gg/bot/801431445452750879).',
			color = 0x2f3136
		)
		await ctx.respond(embed=embed)
	else:
		embed = hikari.Embed(
			title = '__**Commands**__',
			description = '**__Main:__** \n **/insult:** Generate a random insult. \n **/list:** List of all the insults. \n \n **__Misc:__** \n **/invite:** Get the bot\'s invite link. \n **/vote:** Get the link to vote at top.gg. \n **/support:** Invite to join the support server. \n **/donate:** Donate to support Insult Bot \n **/more:** Check out more bots from me.',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)
		embed = embed = hikari.Embed(
		title = '',
			description = '**Thank you!** \n If you like using Insult Bot, consider [voting](https://top.gg/bot/801431445452750879/vote) or leaving a [review](https://top.gg/bot/801431445452750879).',
			color = 0x2f3136
		)
		await ctx.respond(embed=embed)

#test command
@bot.command
@lightbulb.add_cooldown(length = 30, uses = 1, bucket = lightbulb.UserBucket)
@lightbulb.command('insult', 'Generate a random insult.')
@lightbulb.implements(lightbulb.SlashCommand)
async def insult(ctx):
	await bot.rest.create_message(1013490212736876594, f"`{ctx.command.name}` was used.")
	if any(word in str(ctx.author.id) for word in prem_users):
		await ctx.command.cooldown_manager.reset_cooldown(ctx)
		await ctx.respond(random.choice(response))
	else:
		await ctx.respond(random.choice(response))

#list command
@bot.command
@lightbulb.add_cooldown(length = 30, uses = 1, bucket = lightbulb.UserBucket)
@lightbulb.command('list', 'List of all the insults.')
@lightbulb.implements(lightbulb.SlashCommand)
async def list(ctx):
	await bot.rest.create_message(1013490212736876594, f"`{ctx.command.name}` was used.")
	if any(word in str(ctx.author.id) for word in prem_users):
		await ctx.command.cooldown_manager.reset_cooldown(ctx)
		embed = hikari.Embed(
			title = '__**Insults**__',
			description = 'No you | Fuck you | Your mom \n Stfu | Bruh | Dickhead | Asshole \n Idiot | Go fuck yourself | Pussy \n Insecure turd goblin | Shithead \n You can do better | Stfu inbred \n Bitch pls | Shut your mouth \n You disgust me | Fuck off \n Dumbass | You\'re dumb \n*Includes different variations.*',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)
		embed = hikari.Embed(
			title = '',
			description = '**Thank you!** \n If you like using Insult Bot, consider [voting](https://top.gg/bot/801431445452750879/vote) or leaving a [review](https://top.gg/bot/801431445452750879).',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)
	else:
		embed = hikari.Embed(
			title = '__**Insults**__',
			description = 'No you | Fuck you | Your mom \n Stfu | Bruh | Dickhead | Asshole \n Idiot | Go fuck yourself | Pussy \n Insecure turd goblin | Shithead \n You can do better | Stfu inbred \n Bitch pls | Shut your mouth \n You disgust me | Fuck off \n Dumbass | You\'re dumb \n*Includes different variations.*',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)
		embed = hikari.Embed(
			title = '',
			description = '**Thank you!** \n If you like using Insult Bot, consider [voting](https://top.gg/bot/801431445452750879/vote) or leaving a [review](https://top.gg/bot/801431445452750879).',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)

#invite command
@bot.command
@lightbulb.add_cooldown(length = 30, uses = 1, bucket = lightbulb.UserBucket)
@lightbulb.command('invite', 'Get the bot\'s invite link.')
@lightbulb.implements(lightbulb.SlashCommand)
async def invite(ctx):
	await bot.rest.create_message(1013490212736876594, f"`{ctx.command.name}` was used.")
	if any(word in str(ctx.author.id) for word in prem_users):
		await ctx.command.cooldown_manager.reset_cooldown(ctx)
		embed = hikari.Embed(
			title = '',
			description = '**Invite:** \n Get the bot\'s invite link [here](https://discord.com/oauth2/authorize?client_id=801431445452750879&permissions=414464727104&scope=applications.commands%20bot).',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)
	else:
		embed = hikari.Embed(
			title = '',
			description = '**Invite:** \n Get the bot\'s invite link [here](https://discord.com/oauth2/authorize?client_id=801431445452750879&permissions=414464727104&scope=applications.commands%20bot).',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)

#vote command
@bot.command
@lightbulb.add_cooldown(length = 30, uses = 1, bucket = lightbulb.UserBucket)
@lightbulb.command('vote', 'Get the link to vote at top.gg.')
@lightbulb.implements(lightbulb.SlashCommand)
async def vote(ctx):
	await bot.rest.create_message(1013490212736876594, f"`{ctx.command.name}` was used.")
	if any(word in str(ctx.author.id) for word in prem_users):
		await ctx.command.cooldown_manager.reset_cooldown(ctx)
		embed = hikari.Embed(
			title = '',
			description = '**Vote:** \n Click [here](https://top.gg/bot/801431445452750879/vote) to vote on top.gg (thank you!)',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)
	else:
		embed = hikari.Embed(
			title = '',
			description = '**Vote:** \n Click [here](https://top.gg/bot/801431445452750879/vote) to vote on top.gg (thank you!)',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)

#support command
@bot.command
@lightbulb.add_cooldown(length = 30, uses = 1, bucket = lightbulb.UserBucket)
@lightbulb.command('support', 'Invite to join the support server.')
@lightbulb.implements(lightbulb.SlashCommand)
async def support(ctx):
	await bot.rest.create_message(1013490212736876594, f"`{ctx.command.name}` was used.")
	if any(word in str(ctx.author.id) for word in prem_users):
		await ctx.command.cooldown_manager.reset_cooldown(ctx)
		embed = hikari.Embed(
			title = '',
			description = '**Support:** \n Click [here](https://discord.com/invite/xNb8mpySK8) to join the support server.',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)
	else:
		embed = hikari.Embed(
			title = '',
			description = '**Support:** \n Click [here](https://discord.com/invite/xNb8mpySK8) to join the support server.',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)

#donate command
@bot.command
@lightbulb.add_cooldown(length = 30, uses = 1, bucket = lightbulb.UserBucket)
@lightbulb.command('donate', 'Donate to support Insult Bot.')
@lightbulb.implements(lightbulb.SlashCommand)
async def donate(ctx):
	await bot.rest.create_message(1013490212736876594, f"`{ctx.command.name}` was used.")
	if any(word in str(ctx.author.id) for word in prem_users):
		await ctx.command.cooldown_manager.reset_cooldown(ctx)
		embed = hikari.Embed(
			title = '',
			description = '**Donate:** \n [Buy me a coffee](https://www.buymeacoffee.com/azael) to support me in making Insult Bot. \n Thank you! :)',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)
	else:
		embed = hikari.Embed(
			title = '',
			description = '**Donate:** \n [Buy me a coffee](https://www.buymeacoffee.com/azael) to support me in making Insult Bot. \n Thank you! :)',
			color = 0x2f3136
		)
		await ctx.respond(embed = embed)

#more command
@bot.command
@lightbulb.add_cooldown(length = 30, uses = 1, bucket = lightbulb.UserBucket)
@lightbulb.command("more", "Check out more bots from me.")
@lightbulb.implements(lightbulb.SlashCommand)
async def more(ctx):
	await bot.rest.create_message(1013490212736876594, f"`{ctx.command.name}` was used.")
	if any(word in str(ctx.author.id) for word in prem_users):
		await ctx.command.cooldown_manager.reset_cooldown(ctx)
		embed = hikari.Embed(
			title="",
			description="**More:** \n Click [here](https://top.gg/user/67067136345571328) to check out more bots from me.",
			color=0x2f3136
		)
		await ctx.respond(embed=embed)
	else:
		embed = hikari.Embed(
			title="",
			description="**More:** \n Click [here](https://top.gg/user/67067136345571328) to check out more bots from me.",
			color=0x2f3136
		)
		await ctx.respond(embed=embed)

#privacy command
@bot.command
@lightbulb.command("privacy", "View the privacy policy statement.")
@lightbulb.implements(lightbulb.SlashCommand)
async def privacy(ctx):
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
		await event.context.respond(f"Something went wrong during invocation of command `{event.context.command.name}`.")
		raise event.exception

	exception = event.exception.__cause__ or event.exception

	if isinstance(exception, lightbulb.CommandIsOnCooldown):
		await event.context.respond(f"`/{event.context.command.name}` is on cooldown. Retry in `{exception.retry_after:.0f}` seconds. ⏱️ \n To avoid cooldowns, become a member at https://www.buymeacoffee.com/azael. \n It helps keep the bot online. 👉👈")
	else:
		raise exception

bot.run()