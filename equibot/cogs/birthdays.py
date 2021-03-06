from discord.ext import commands
import discord
import asyncio
import calendar

from . import util
from .. import repository

class Birthdays(commands.Cog):

    def __init__(self, repo: repository.Repository):
        self.repo = repo

    @commands.command(usage='birthday [month] [day]')
    async def birthday(self, ctx: commands.Context, *args):
        """
        Add your name to birthday calendar!
        """

        print(f'Command {ctx.command.name} from guild {ctx.guild.name}')

        if not await util.ensure_args(ctx, 2, args):
            return

        month, day = None, None

        if not args[0].isnumeric() or (month := int(args[0])) > 12:
            await ctx.send(f"Does {args[0]} looks like a month number to you? ;-;")
            return

        if not args[1].isnumeric():
            await ctx.send(f"Does {args[1]} looks like a number to you? ;-;")
            return

        month_limit = calendar.monthrange(0, month)[1]
        if (day := int(args[1])) > month_limit:
            await ctx.send(
                util.simpleEmbed(
                    ";-;",
                    f"{calendar.month_name[month]} has only {month_limit} days",
                    discord.Color.red()
                )
            )

            return

        await self.repo.set_birthdate(ctx.author.id, month, day)

        await ctx.send(
            embed = util.simpleEmbed(
                "Awesome!",

                "We will remember your birthday\n" +
                "UmU"
            )
        )

        try:
            if not await self.update_calendar(ctx.guild):
                await ctx.send(
                    "**Note:** This Server has not registered the channels " +
                    "to be used for greets and calendar\n" +
                    "Owner must run birthday-setup command for calendar to work"
                )
        except discord.NotFound:
            await ctx.send(
                "**Note:** Previously created calendar messages were deleted.\n" +
                "You must run birthday-setup for calendar to show up."
            )

    async def update_calendar(self, guild: discord.Guild):
        """
        Updates the calendar messages.
        Returns False if calendar channel was not registered or not found.
        """

        #Check if we know about which channel to post calendar.
        channel_ids = await self.repo.get_birthday_channels(guild.id)
        if channel_ids == None:
            return False

        channel = guild.get_channel(channel_ids[0])
        if channel == None:
            return False

        builders = [util.CalendarEmbedBuilder(month) for month in range(1, 13)]

        for member in guild.members:
            if (bd := await self.repo.get_user_birthdate(member.id)) == None:
                continue

            month = bd[0]
            day = bd[1]

            builders[month - 1].add(member.mention, day)

        #Check if calendar messages were created
        #Create if not.
        #id at 0 is for January, 1 for February and so on.
        ids = await self.repo.get_calendar_message_ids(guild.id)
        if ids == None: #Send new messages.
            ids = []
            for builder in builders:
                msg = await channel.send(embed=builder.build())
                ids.append(msg.id)

            #Store these in db for future use.
            await self.repo.update_calendar_message_ids(guild.id, ids)

        else: #Edit exsiting messages
            for i in range(12):
                message_id = ids[i]
                msg = await channel.fetch_message(message_id)
                await msg.edit(content="", embed=builders[i].build())

        return True

    @commands.command(name="birthdaysetup", usage='birthdaysetup [channel for calendar] [channel for greets]')
    async def birthday_setup(self, ctx: commands.Context, *args):
        """
        Set-up birthday calendar for server!
        """

        print(f'Command {ctx.command.name} from guild {ctx.guild.name}')

        if not await util.ensureOwner(ctx):
            return

        if not await util.ensure_args(ctx, 2, args):
            return

        calendar_channel = await util.find_channel_by_mention(ctx, args[0])
        greet_channel = await util.find_channel_by_mention(ctx, args[1])

        if calendar_channel == None or greet_channel == None:
            return
        
        await ctx.message.add_reaction('👍🏼')

        await self.repo.set_birthday_channels(
            ctx.guild.id,
            calendar_channel.id,
            greet_channel.id
        )

        await self.repo.clear_calendar_message_ids(ctx.guild.id)
        await self.update_calendar(ctx.guild)

        await ctx.send(
            embed = util.simpleEmbed(
                "Awesome!",

                "I've set it up as follows:\n" +
                f"**Bithday calendar at:** {calendar_channel.mention}\n" +
                f"**Greetings at:** {greet_channel.mention}\n" +
                ":3"
            )
        )

    async def greet_birthday(self, channel, member):
        greeting = ""

        if (role_id := await self.repo.get_birthday_ping_role(channel.guild.id)) != None:
            role = channel.guild.get_role(role_id)
            greeting += role.mention + "\n"

        greeting += f"It's {member.mention}'s birthday! "
        greeting += "Everybody go wish them!"

        await channel.send(
            embed = util.simpleEmbed("Party time! 🎉", greeting)
        )

    async def birthday_ticker(self, bot: commands.Bot):
        while True:

            if await self.repo.has_greeted_today():
                await asyncio.sleep(60 * 30) #Half hour
                continue

            birthdays = await self.repo.get_birthday_kids()

            if birthdays != None:
                for guild in bot.guilds:
                    if (channel_ids := await self.repo.get_birthday_channels(guild.id)) != None:
                        channel = guild.get_channel(channel_ids[1])

                        for kid_id in birthdays:
                            if kid_id in map(lambda member: member.id, guild.members):
                                await self.greet_birthday(channel, guild.get_member(kid_id))
                                
                    else: print(f"Birthday channels not setup for guild: '{guild.name}' id: {guild.id}")

                await self.repo.update_greet_completion_date()
                print("Birthdays concluded.")

            else:
                print("No birthdays today.")
                await self.repo.update_greet_completion_date()

            await asyncio.sleep(15)

    @commands.command(usage='birthdayping [role name or mention]')
    async def birthdayping(self, ctx: commands.Context, *args):
        """
        Set a role to ping when there's somebody's birthday.
        """

        print(f'Command {ctx.command.name} from guild {ctx.guild.name}')

        if not await util.ensureOwner(ctx):
            return

        if not await util.ensure_args(ctx, 1, args):
            return

        role = discord.utils.find(
            lambda role: role.name == args[0] or role.mention == args[0],
            ctx.guild.roles
        )

        if role == None:
            await ctx.send(
                embed = util.simpleEmbed(
                    ";-;",
                    f"Can't find role: {args[0]}",
                    discord.Color.red()
                )
            )
            return
        
        await self.repo.set_bithday_ping_role(ctx.guild.id, role.id)
        await ctx.send(
            embed = util.simpleEmbed(
                "Done",
                f"Updated birthday ping role to {role.name}"
            )
        )