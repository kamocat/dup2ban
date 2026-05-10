import asyncio
import hashlib
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import nextcord
from nextcord.ext import commands, tasks


def _normalize(content: str) -> str:
    return content.strip().lower()


def _hash(content: str) -> str:
    return hashlib.sha256(_normalize(content).encode()).hexdigest()


class DuplicateDetector(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # cache[guild_id][content_hash] = {
        #     "first_seen": datetime (UTC),
        #     "messages": [nextcord.Message, ...]
        # }
        self.cache: dict[int, dict[str, dict]] = defaultdict(dict)
        self._cleanup_task.start()

    def cog_unload(self):
        self._cleanup_task.cancel()

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _get_guild_config(self, guild_id: int) -> dict:
        default = self.bot.config.get("default", {})
        overrides = self.bot.config.get("guilds", {}).get(str(guild_id), {})
        return {**default, **overrides}

    # ------------------------------------------------------------------
    # Background cleanup task
    # ------------------------------------------------------------------

    @tasks.loop(seconds=10)
    async def _cleanup_task(self):
        now = datetime.now(timezone.utc)
        for guild_id, hashes in list(self.cache.items()):
            for h, entry in list(hashes.items()):
                cfg = self._get_guild_config(guild_id)
                window = timedelta(seconds=cfg.get("detection_window_seconds", 30))
                if now - entry["first_seen"] > window:
                    del self.cache[guild_id][h]
            if not self.cache[guild_id]:
                del self.cache[guild_id]

    @_cleanup_task.before_loop
    async def _before_cleanup(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Message listener
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message):
        # Ignore DMs, bots, and webhooks
        if not message.guild:
            return
        if message.author.bot:
            return
        if message.webhook_id:
            return
        # Ignore empty content (attachment/embed only messages)
        if not message.content or not message.content.strip():
            return

        guild_id = message.guild.id
        cfg = self._get_guild_config(guild_id)
        window = timedelta(seconds=cfg.get("detection_window_seconds", 30))
        min_channels = cfg.get("min_channels", 2)
        now = datetime.now(timezone.utc)

        content_hash = _hash(message.content)
        entry = self.cache[guild_id].get(content_hash)

        if entry is None:
            # First occurrence — start tracking
            self.cache[guild_id][content_hash] = {
                "first_seen": now,
                "messages": [message],
            }
            return

        # Prune messages outside the window
        entry["messages"] = [
            m for m in entry["messages"] if now - m.created_at < window
        ]

        # Only add if this message is from a new channel
        seen_channel_ids = {m.channel.id for m in entry["messages"]}
        if message.channel.id not in seen_channel_ids:
            entry["messages"].append(message)

        distinct_channels = len({m.channel.id for m in entry["messages"]})

        if distinct_channels >= min_channels:
            await self._trigger_action(message, content_hash, cfg)

    # ------------------------------------------------------------------
    # Action: punish first, then delete
    # ------------------------------------------------------------------

    async def _trigger_action(
        self,
        triggering_message: nextcord.Message,
        content_hash: str,
        cfg: dict,
    ):
        guild = triggering_message.guild
        author = triggering_message.author
        entry = self.cache[triggering_message.guild.id].pop(content_hash, None)
        if entry is None:
            # Already handled by a concurrent trigger
            return

        messages_to_delete = entry["messages"]
        # Ensure the triggering message is included
        if triggering_message not in messages_to_delete:
            messages_to_delete.append(triggering_message)

        # -- 1. Apply punishment first --
        exempt = cfg.get("exempt_admins", True)
        is_admin = (
            isinstance(author, nextcord.Member)
            and author.guild_permissions.manage_guild
        )

        if not (exempt and is_admin):
            await self._punish(guild, author, cfg)

        # -- 2. Delete all copies --
        delete_tasks = [self._safe_delete(m) for m in messages_to_delete]
        await asyncio.gather(*delete_tasks)

    async def _punish(
        self,
        guild: nextcord.Guild,
        member: nextcord.Member,
        cfg: dict,
    ):
        punishment = cfg.get("punishment", "none")
        reason = "Duplicate message posted across multiple channels (cross2ban)"

        try:
            if punishment == "ban":
                await guild.ban(member, reason=reason, delete_message_seconds=0)
            elif punishment == "timeout":
                duration = timedelta(minutes=cfg.get("timeout_duration_minutes", 60))
                await member.timeout(duration, reason=reason)
            # "none" → do nothing
        except nextcord.Forbidden:
            print(
                f"[cross2ban] Missing permissions to {punishment} {member} in {guild}",
                file=sys.stderr,
            )
        except nextcord.HTTPException as exc:
            print(
                f"[cross2ban] HTTP error applying {punishment} to {member}: {exc}",
                file=sys.stderr,
            )

    @staticmethod
    async def _safe_delete(message: nextcord.Message):
        try:
            await message.delete()
        except (nextcord.NotFound, nextcord.Forbidden, nextcord.HTTPException):
            pass


def setup(bot: commands.Bot):
    bot.add_cog(DuplicateDetector(bot))
