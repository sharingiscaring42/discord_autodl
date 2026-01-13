# Discord Auto-Downloader

A Python bot that monitors Discord channels and automatically downloads files from Mega.nz links based on customizable patterns and triggers.

## Features

- 🤖 Monitors specific Discord channels for new messages
- 📥 Automatically downloads files from Mega.nz links
- 🎯 Pattern-based episode detection using regex
- 📊 Tracks last downloaded episode to avoid duplicates
- 🔄 Auto-reconnect on connection loss
- ⚙️ Flexible configuration via JSON

## Prerequisites

- Python 3.10 or 3.12
- A Discord account and token
- Mega.nz command-line tools
- Linux environment (Ubuntu 24.04 or Debian 13 recommended)

## Installation

### 1. Install Mega CMD

Visit [https://mega.io/cmd#download](https://mega.io/cmd#download) and install for your OS.

**For Ubuntu 24.04:**
```bash
wget https://mega.nz/linux/repo/xUbuntu_24.04/amd64/megacmd-xUbuntu_24.04_amd64.deb
sudo apt install "$PWD/megacmd-xUbuntu_24.04_amd64.deb"
```

**For Debian 13:**
```bash
wget https://mega.nz/linux/repo/Debian_13/amd64/megacmd-Debian_13_amd64.deb
sudo apt install "$PWD/megacmd-Debian_13_amd64.deb"
```

### 2. Install Python Dependencies

```bash
sudo apt update
sudo apt install -y git python3-venv

git clone https://github.com/sharingiscaring42/discord_autodl.git
cd discord_autodl

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Discord Token

Create a `.env` file in the project root:

```bash
echo "DISCORD_TOKEN=YOUR_DISCORD_TOKEN_HERE" > .env
```

**How to get your Discord token:**
1. Open Discord in your web browser
2. Press F12 to open Developer Tools
3. Go to the Console tab
4. Type: `(webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let c in e.c)m.push(e.c[c])}]),m).find(m=>m?.exports?.default?.getToken!==void 0).exports.default.getToken()`
5. Copy the token (keep it secret!)

## Configuration

### settings.json Structure

The `settings.json` file controls what the bot monitors and downloads. Here's the structure:
Rename `settings_example.json` to `settings.json` and fill it
```json
{
  "section_name": {
    "mega": [
      {
        "name": "Series Name",
        "channel_id": "1234567890123456789",
        "regex": "Episode (\\d+)",
        "link": "[1080p]",
        "path": "/path/to/download/folder",
        "last_episode": 0
      }
    ]
  }
}
```

### Configuration Fields Explained

- **section_name**: Organizational category (e.g., "anime", "tv_shows", "documentaries")
- **mega**: Array of download configurations
  - **name**: Friendly name for logging purposes
  - **channel_id**: Discord channel ID to monitor
  - **regex**: Pattern to extract episode number from messages (must have capture group for episode number)
  - **link**: Label text to identify the correct Mega link (e.g., "[1080p]", "[4K]", "[HEVC]")
  - **path**: Absolute path where files should be downloaded
  - **last_episode**: Tracks the last downloaded episode (auto-updated by the bot)

### Example Configuration

```json
{
  "anime": {
    "mega": [
      {
        "name": "My Favorite Anime",
        "channel_id": "1234567890123456789",
        "regex": "Episode (\\d+)",
        "link": "[1080p]",
        "path": "/media/downloads/anime/my-favorite-anime",
        "last_episode": 0
      },
      {
        "name": "Another Anime",
        "channel_id": "9876543210987654321",
        "regex": "EP(\\d+)",
        "link": "[HEVC]",
        "path": "/media/downloads/anime/another-anime",
        "last_episode": 5
      }
    ]
  },
  "tv_shows": {
    "mega": [
      {
        "name": "Cool TV Show",
        "channel_id": "1111222233334444555",
        "regex": "S\\d+E(\\d+)",
        "link": "[4K]",
        "path": "/media/downloads/tv/cool-show",
        "last_episode": 3
      }
    ]
  }
}
```

### How to Get Channel IDs

1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click on the channel you want to monitor
3. Click "Copy Channel ID"
4. Paste it into your `settings.json`

### Regex Pattern Examples

- `Episode (\\d+)` - Matches "Episode 1", "Episode 23", etc.
- `EP(\\d+)` - Matches "EP1", "EP23", etc.
- `S\\d+E(\\d+)` - Matches "S01E05", "S02E12", etc.
- `\\[(\\d+)\\]` - Matches "[1]", "[23]", etc.
- `#(\\d+)` - Matches "#1", "#23", etc.

**Important:** The `\\d+` must be in parentheses `()` to create a capture group for the episode number.

### Link Label Matching

The bot looks for Mega.nz links associated with specific labels in Discord messages. Common formats:

- `[1080p](<https://mega.nz/...>)`
- `**[1080p]**(<https://mega.nz/...>)`
- `[4K HEVC]` followed by a mega.nz link

Set the `link` field to match the exact label text (without markdown symbols).

## Usage

### Running Manually

```bash
cd discord_autodl
source .venv/bin/activate
python main.py
```

### Running as a Service (Recommended)

For continuous operation, use a process manager like PM2:

**Install PM2:**
```bash
sudo apt install -y nodejs npm
sudo npm install -g pm2
```

**Start the bot:**
```bash
cd discord_autodl
pm2 start downloader.py --name discord-autodl --interpreter .venv/bin/python
pm2 save
pm2 startup
```

**Useful PM2 commands:**
```bash
pm2 status              # Check bot status
pm2 logs discord-autodl # View logs
pm2 restart discord-autodl # Restart bot
pm2 stop discord-autodl    # Stop bot
pm2 delete discord-autodl  # Remove from PM2
```

#### Handling Low-Activity Channels

If your Discord account monitors channels that don't receive many messages (inactive for hours/days), the gateway connection may go stale and stop receiving events. This is a known issue with Discord's API.

**Solution: Use PM2 with automatic periodic restarts**

Create an `ecosystem.config.js` file in your project directory:
```javascript
module.exports = {
  apps: [{
    name: 'discord-autodl',
    script: 'downloader.py',
    interpreter: '/full/path/to/discord_autodl/.venv/bin/python',
    cwd: '/full/path/to/discord_autodl',
    cron_restart: '0 */3 * * *',  // Restart every 3 hours
    autorestart: true,             // Also restart on crashes
    max_restarts: 10,
    min_uptime: '10s'
  }]
}
```

**Note:** Replace `/full/path/to/discord_autodl` with your actual path (e.g., `/home/anon/code/discord_autodl`)

Then start with the ecosystem file:
```bash
pm2 delete discord-autodl  # Remove old instance if exists
pm2 start ecosystem.config.js
pm2 save
pm2 logs discord-autodl    # Verify it's working
```

**Common cron restart intervals:**
- `0 */3 * * *` - Every 3 hours (recommended for low-activity channels)
- `0 */6 * * *` - Every 6 hours
- `0 */12 * * *` - Every 12 hours
- `0 0 * * *` - Once daily at midnight

This ensures your bot maintains a fresh connection to Discord's gateway, preventing the "silent death" issue where it appears running but stops receiving messages.

## How It Works

1. Bot connects to Discord using your token
2. Monitors all channels specified in `settings.json`
3. When a new message arrives:
   - Checks if channel ID matches any configuration
   - Applies regex pattern to extract episode number
   - Verifies episode is newer than `last_episode`
   - Searches for the specified link label
   - Downloads the file using `mega-get`
   - Updates `last_episode` in `settings.json`
   - Sets file permissions to 754

## Troubleshooting

### Bot doesn't connect
- Verify your Discord token is correct in `.env`
- Check your internet connection
- Ensure you haven't been rate-limited by Discord

### Downloads don't start
- Confirm channel IDs are correct
- Test your regex patterns (use regex101.com)
- Check that the link label exactly matches the Discord message format
- Verify download paths exist and have write permissions

### Permission errors
- Ensure download directories exist: `mkdir -p /path/to/download`
- Check folder permissions: `chmod 755 /path/to/download`

### Mega quota warnings
The bot uses `--ignore-quota-warn` flag, but if you hit quota limits, downloads may fail. Consider upgrading your Mega account or waiting for quota reset.

## Security Notes

- Never share your Discord token
- Never commit `.env` to version control (it's in `.gitignore`)
- Use a dedicated Discord account for automation
- Be aware that automating Discord may violate Terms of Service

## License

This project is provided as-is for educational purposes. Use responsibly and in accordance with Discord's Terms of Service.

## Contributing

Feel free to open issues or submit pull requests for improvements!