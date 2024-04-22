import discord
import datetime
import asyncio

from redbot.core import commands
from typing import Optional
from redbot.core.utils.tunnel import Tunnel
from discord.utils import format_dt


class Speak(commands.Cog):
    def __init__(self, bot):
        self.tunnel_users = []
        self.bot = bot

    async def message_handler(self, ctx: commands.Context, channel: discord.TextChannel, task: asyncio.Task):
        user = ctx.author.id
        stime = datetime.datetime.now()
        while user in self.tunnel_users:
            try:
                msg = await self.bot.wait_for('message', timeout=360)
            except TimeoutError:
                await ctx.author.send("Tunnel closed due to inactivity.")
                self.tunnel_users.remove(user)
                break
            if msg.content.startswith(ctx.prefix):
                continue
            if msg.author == self.bot.user:
                continue
            if msg.author.id == user and msg.channel == ctx.author.dm_channel:
                if msg.content.lower() == "close_tunnel":
                    self.tunnel_users.remove(user)
                    await ctx.author.send("Tunnel closed.")
                    break
                files = await Tunnel.files_from_attatch(msg)
                await Tunnel.message_forwarder(destination=channel, content=msg.content, files=files)
                stime = datetime.datetime.now()
            elif msg.author.id == user:
                continue
            elif msg.channel == channel:
                title = f"Message from {channel.name}"
                files = await Tunnel.files_from_attatch(msg)
                description = msg.content
                color = msg.author.color

                embed = discord.Embed(title=title, description=description, color=color)
                embed.set_author(name=msg.author.display_name, icon_url=msg.author.avatar)
                content = f'Sent {format_dt(msg.created_at, "R")}'
                await ctx.author.send(embed=embed)
                await ctx.author.send(content)
                if files:
                    await ctx.author.send(files=files)
                stime = datetime.datetime.now()

            else:
                if datetime.datetime.now() - stime > datetime.timedelta(minutes=5):
                    await ctx.author.send("Tunnel closed due to inactivity.")
                    self.tunnel_users.remove(user)
                    break
        task.cancel()
        print("Task cancelled")

    async def edit_handler(self, ctx: commands.Context, channel: discord.TextChannel):
        def user_check(person):
            if person not in self.tunnel_users:
                raise TimeoutError

        user = ctx.author.id
        active = []
        while user in self.tunnel_users:
            print("Edit handler running")
            print(self.tunnel_users)
            if user not in self.tunnel_users:
                break
            msg = None
            try:
                msg = await self.bot.wait_for('message_edit', timeout=5)
                user_check(user)
                msg = await channel.fetch_message(msg[1].id)
                if msg.id in active:
                    continue
                active.append(msg.id)
            except asyncio.TimeoutError:
                print("Timeout error")
                continue
            except discord.errors.NotFound:
                print("Message not found")
                continue
            if msg is None:
                continue
            try:
                user_check(user)
            except TimeoutError:
                break
            if msg.channel == ctx.author.dm_channel:
                continue
            elif msg.author == self.bot.user:
                continue
            elif msg.channel == channel:
                title = f"Message edited in {channel.name}"
                files = await Tunnel.files_from_attatch(msg)
                description = msg.content
                color = msg.author.color

                embed = discord.Embed(title=title, description=description, color=color)
                embed.set_author(name=msg.author.display_name, icon_url=msg.author.avatar)
                content = f'A message was edited {format_dt(msg.created_at, "R")}'
                await ctx.author.send(embed=embed)
                await ctx.author.send(content)
                if files:
                    await ctx.author.send(files=files)
            active.remove(msg.id)
        print("Edit handler ended")

    @commands.admin()
    @commands.command(aliases=["say"])
    async def speak(self, ctx: commands.Context, channel: Optional[discord.TextChannel], *, message: str):
        """Say a message in a channel."""
        if channel is None:  # If channel is a number then it will automatically convert to a channel object
            channel = ctx.channel

        files = await Tunnel.files_from_attatch(ctx.message)
        if files:
            await Tunnel.message_forwarder(
                destination=channel, content=message, files=files
            )
        else:
            await Tunnel.message_forwarder(destination=channel, content=message)
        await ctx.tick()

    @commands.admin()
    @commands.command(name="tunnel")
    async def tunnel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Open a tunnel to a channel."""
        user = ctx.author.id
        if user in self.tunnel_users:
            return await ctx.author.send("You already have a tunnel open.")
        dm_msg = ("You have opened a tunnel to this channel. "
                  "\nAnything you say will be sent to the channel you have chosen. "
                  "\nYou will also receive any messages sent to that channel. "
                  "\nTo close the tunnel, send a message here that says `close_tunnel`.")  # Message to send to the user
        await ctx.author.send(dm_msg)
        self.tunnel_users.append(user)
        loop = asyncio.get_event_loop()
        edit_handler_task = loop.create_task(self.edit_handler(ctx, channel))
        message_handler_task = loop.create_task(self.message_handler(ctx, channel, edit_handler_task))
        await ctx.tick()
        await asyncio.gather(message_handler_task, edit_handler_task)

    @commands.admin()
    @commands.command(name="reply")
    async def reply(self, ctx: commands.Context, mention: Optional[bool], message: discord.Message, *, content: str):
        """Reply to a message."""
        if mention is None:
            mention = False
        files = await Tunnel.files_from_attatch(ctx.message)
        if files:
            await message.reply(content=content, files=files, mention_author=mention)

        else:
            await message.reply(content=content, mention_author=mention)
        await ctx.tick()

    @commands.admin()
    @commands.command(name="editmsg")
    async def edit(self, ctx: commands.Context, message: discord.Message, *, content: str):
        """Edit a message."""
        if message.author != self.bot.user:
            return await ctx.send("I can only edit my own messages.")
        if message.content == content:
            return await ctx.send("The content is the same as the original message.")
        if len(content) > 2000:
            return await ctx.send("The message is too long.")
        await message.edit(content=content)
        await ctx.tick()
