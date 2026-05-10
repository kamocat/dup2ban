# cross2ban

A Nextcord Discord bot that detects identical messages posted across multiple channels. When the same content appears in too many channels within a configurable time window, the bot applies a punishment to the author first, then deletes all copies of the message.

## Features

- Detects cross-channel duplicate messages in real time
- Configurable per-guild: detection window, minimum channels threshold, and punishment type
- **Punishes the author before deleting messages** (ban or timeout)
- Admins (`Manage Server` permission) are optionally exempt from punishment
- Fully containerized with Docker

## Requirements

- Python 3.12+
- A Discord bot token with the following intents enabled in the [Developer Portal](https://discord.com/developers/applications):
  - **Message Content Intent**
  - **Server Members Intent**
- Bot permissions needed: `Ban Members`, `Moderate Members`, `Manage Messages`

## Configuration

Edit `config.json` to set your defaults and per-guild overrides.

| Field | Type | Description |
|---|---|---|
| `detection_window_seconds` | int | Time window in which identical messages across channels trigger action |
| `min_channels` | int | Number of distinct channels the same content must appear in to trigger action |
| `punishment` | string | `"timeout"`, `"ban"`, or `"none"` |
| `timeout_duration_minutes` | int | Timeout length in minutes (only used when `punishment` is `"timeout"`) |
| `exempt_admins` | bool | If `true`, users with `Manage Server` are not punished (messages still deleted) |

### Example

```json
{
  "default": {
    "detection_window_seconds": 30,
    "min_channels": 2,
    "punishment": "timeout",
    "timeout_duration_minutes": 60,
    "exempt_admins": true
  },
  "guilds": {
    "123456789012345678": {
      "punishment": "ban",
      "detection_window_seconds": 10
    }
  }
}
```

Per-guild settings are merged on top of the defaults — only include fields you want to override.

## Setup (Native Python)

1. Clone the repo and enter the directory.

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy `.env` and fill in your token:
   ```bash
   # .env
   BOT_TOKEN=your_bot_token_here
   ```

4. Edit `config.json` with your guild IDs and preferred settings.

5. Run the bot:
   ```bash
   python bot.py
   ```

## Setup (Docker)

1. Fill in your token in `.env`.

2. Edit `config.json`.

3. Build and start:
   ```bash
   docker compose up --build -d
   ```

4. View logs:
   ```bash
   docker compose logs -f
   ```

5. Stop:
   ```bash
   docker compose down
   ```

`config.json` is volume-mounted read-only into the container, so you can edit it and restart the bot without rebuilding the image:
```bash
docker compose restart
```

## How It Works

1. Every message in a guild is normalized (stripped, lowercased) and SHA-256 hashed.
2. The hash is tracked in an in-memory cache alongside the message objects and a timestamp.
3. When the same hash appears in `min_channels` or more **distinct channels** within `detection_window_seconds`:
   - The punishment (ban or timeout) is applied to the author first.
   - All tracked copies of the message are then deleted.
4. A background task purges stale cache entries every 10 seconds.

Bot messages and webhooks are always ignored. Empty messages (attachment/embed only) are also ignored.
