#!/usr/bin/env python3

import asyncio
import datetime
import logging
import os
from datetime import timedelta

import discord
import dotenv
from discord.ext import commands


dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO)


class CBot(commands.Bot):
    async def get_messages_after_date(self, channel, after_date):
        messages = []
        try:
            async for message in channel.history(after=after_date, limit=None):
                messages.append(message)
            return messages
        except discord.errors.Forbidden:
            logging.warning(f"Missing permissions to read message history in {channel.name}")
        except Exception as e:
            logging.error(f"Error retrieving messages from {channel.name}: {e}")
        return []

    async def summarize(self, days_ago=7) -> str:
        """
        Summarizes messages from all channels in all guilds from the specified number of days ago.
        """
        cutoff_date = datetime.datetime.now(datetime.timezone.utc) - timedelta(days=days_ago)
        summary_lines = [f"Message summary for the last {days_ago} days (since {cutoff_date.strftime('%Y-%m-%d')})"]
        
        total_messages = 0
        total_channels = 0
        
        for guild in self.guilds:
            try:
                guild_message_count = 0
                guild_channels = [channel for channel in guild.channels if isinstance(channel, discord.TextChannel)]
                total_channels += len(guild_channels)
                summary_lines.append(f"\n# Guild: {guild.name}")
                
                for channel in guild_channels:
                    messages = await self.get_messages_after_date(channel, cutoff_date)
                    guild_message_count += len(messages)
                    
                    # Only add channel details if there are messages
                    if messages:
                        summary_lines.append(f"## {channel.name} ({len(messages)} msgs)")
                        
                        # Group messages by author
                        authors = {}
                        for msg in messages:
                            author_name = str(msg.author)
                            authors[author_name] = authors.get(author_name, 0) + 1
                            summary_lines.append(f"* {author_name}: {msg.content}")
                        
                summary_lines.append(f"Total messages: {guild_message_count}")
                total_messages += guild_message_count
                
            except Exception as e:
                summary_lines.append(f"Error processing guild {guild.name}: {e}")
        
        # Add overall summary at the end
        summary_lines.append(f"\nOverall Summary:")
        summary_lines.append(f"Total channels: {total_channels}")
        summary_lines.append(f"Total messages in the last {days_ago} days: {total_messages}")
                
        return '\n'.join(summary_lines)
        
    async def on_ready(self):
        logging.info(f'Logged on as {self.user}')
        
        # Get a summary of messages from the last 7 days
        summary = await self.summarize(days_ago=7)
        logging.info(summary)

    async def on_message(self, message):
        # don't respond to ourselves
        if message.author != self.user:
            logging.info(f'Message from {message.author}: {message.content}')
        await super().on_message(message)


@commands.command()
async def summary(ctx, days_ago: int = 7):
    summary = ctx.bot.summarize(days_ago=days_ago)
    await ctx.send(summary)


def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guild_messages = True  # For accessing guild message history
    intents.members = True  # Often needed for complete message data
    intents.typing = False
    intents.presences = False

    bot = CBot(command_prefix='/', intents=intents)
    bot.add_command(summary)
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))


if __name__ == '__main__':
    main()
