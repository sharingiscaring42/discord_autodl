# Discord Auto-Downloader

A Python bot that monitors Discord channels and automatically downloads files from multiple platforms (Mega.nz, Pixeldrain, Google Drive) based on customizable patterns and triggers.

## Features

- 🤖 Monitors specific Discord channels for new messages
- 📥 Downloads from **three platforms**: Mega.nz, Pixeldrain, Google Drive
- 🎯 Pattern-based episode detection using regex
- 📊 Tracks last downloaded episode to avoid duplicates
- 🔄 Multi-platform priority with automatic fallback
- 📁 **Folder support** for batch downloads with smart episode matching
- 🔁 Automatic retry queue for failed downloads
- 📝 Age filtering for folder files (skip old uploads)
- 🔀 Platform-specific configuration overrides
- ⚙️ Flexible configuration via JSON

## Prerequisites

- Python 3.10+ (Tested on 3.10 and 3.12)
- A Discord account and token
- Mega.nz command-line tools (only for Mega downloads)
- Linux environment

## Installation

### 1. Install Mega CMD (Optional, for Mega downloads only)

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

The `requirements.txt` includes:
- `discum` - Discord API client
- `requests` - HTTP requests for Pixeldrain and Google Drive
- `beautifulsoup4` - HTML parsing for Google Drive
- `lxml` - HTML parser for BeautifulSoup
- `python-dotenv` - Environment variable loading

### 3. Configure Discord Token

Create a `.env` file in the project root:

```bash
echo "DISCORD_TOKEN=YOUR_DISCORD_TOKEN_HERE" > .env
```

**Optional:** Add retry and age filtering configuration:

```bash
echo "MAX_RETRY=10" >> .env
echo "FOLDER_FILE_MAX_AGE_DAYS=30" >> .env
```

**How to get your Discord token:**
1. Open Discord in your web browser (discord.com/app).

2. Open developer tools (Control + Shift + I, or F12) and open the Network tab within it.

3. Open a different text channel than the one you already had open (to force it to fetch the messages)

4. In the dev tools, look for the messages?limit=50 request. You can filter Fetch/XHR or search for it, if that helps. Once you've found it, click on the request.

5. Under the 'Headers' section, scroll to 'Request headers', then 'Authorization'. The value of that header is the token.
Obviously, you should be very careful giving the token to anything/anywhere/anyone, since that token proves that you are you to Discord.

## Configuration

### settings.json Structure

The `settings.json` file controls what the bot monitors and downloads. Rename `settings_example.json` to `settings.json` and fill it.

```json
{
  "section_name": {
    "entries": [
      {
        "name": "Series Name",
        "channel_id": "1234567890123456789",
        "regex": "Episode (\\d+)",
        "path": "/path/to/download/folder",
        "last_episode": 0,
        "platforms": ["pixeldrain", "gdrive", "mega"],
        "link_labels": {
          "pixeldrain": "[1080p]",
          "gdrive": "[1080p]",
          "mega": "[1080p]"
        },
        "share_type": "file"
      }
    ]
  },
  "retry_queue": []
}
```

### How Regex and Link Labels Work

The bot uses **two independent mechanisms** to identify downloads:

#### 1. Regex - Episode Extraction
The regex extracts the episode number from the **entire message text**:

```
Message: "My Serie Name - 207 (1080p).mkv"
Regex:   "My Serie Name - (\\d+)"
Match:    "207"  ← This becomes the episode number
```

- Uses `re.search()` - matches pattern anywhere in message
- Must have exactly one capture group `(\\d+)` for the episode number
- Returns the first match only
- Episode must be greater than `last_episode` to trigger download

#### 2. Link Labels - Link Identification
Link labels are **text identifiers in the message** that tell the bot which links to use for each platform:

```
Message: "My Serie Name - 207 (1080p).mkv
         (1080p) https://mega.nz/file/abc123..."
                                             ↑
                                      This is the actual link
```

**Important:** The label is NOT part of the URL. It's just marker text that tells the bot "look here for a [platform] link".

**How the bot finds links (two-step process):**

**Step 1 - Markdown Format:**
Tries to match structured markdown links first:
```
[1080p](<https://mega.nz/file/abc123...>)
[**[1080p]**](<https://mega.nz/file/abc123...>)
```

**Step 2 - Fallback:**
If markdown format not found, it checks if label exists anywhere in message, then finds the FIRST platform URL:

```
My Serie Name - 207 (1080p) https://mega.nz/file/abc123...
                         ↑ label exists? YES → Find first mega.nz URL
```

**Key point:** In fallback mode, the label doesn't need to be near the URL - it just needs to exist somewhere in the message.

#### Example: Multiple Links with Same Label

```
Discord Message:
My Serie Name - 207 (1080p).mkv

(1080p) https://mega.nz/file/abc123...
(1080p) https://pixeldrain.com/u/xyz456...
(1080p) https://drive.google.com/file/def789...
```

With `link_labels: {"mega": "(1080p)", "pixeldrain": "(1080p)", "gdrive": "(1080p)"}`:

1. Bot finds label "(1080p)" exists in message ✓
2. For each platform in `platforms` order:
   - **mega**: Finds `https://mega.nz/file/abc123...`
   - **pixeldrain**: Finds `https://pixeldrain.com/u/xyz456...`
   - **gdrive**: Finds `https://drive.google.com/file/def789...`
3. Tries platforms in priority order until one succeeds

#### Example: Different Labels per Platform

```json
"link_labels": {
  "mega": "[Mega 1080p]",
  "pixeldrain": "[Pixel 4K]",
  "gdrive": "[GDrive HEVC]"
}
```

Message:
```
[Mega 1080p] https://mega.nz/file/abc...
[Pixel 4K] https://pixeldrain.com/u/xyz...
[GDrive HEVC] https://drive.google.com/file/def...
```

### Configuration Fields Explained

#### Basic Fields
- **section_name**: Organizational category (e.g., "anime", "tv_shows", "documentaries", "donghua")
- **entries**: Array of download configurations
  - **name**: Friendly name for logging purposes
  - **channel_id**: Discord channel ID to monitor
  - **regex**: Pattern to extract episode number from messages (must have capture group for episode number)
  - **path**: Absolute path where files should be downloaded
  - **last_episode**: Tracks the last downloaded episode (auto-updated by the bot)

#### Platform Configuration
- **platforms**: Array defining download priority order
  - Bot tries platforms in order, stops at first success
  - Available platforms: `"mega"`, `"pixeldrain"`, `"gdrive"`
  - Example: `["pixeldrain", "gdrive", "mega"]` tries Pixeldrain first, then GDrive, then Mega

- **link_labels**: Object with label for each platform
  - Keys: Platform names (`"mega"`, `"pixeldrain"`, `"gdrive"`)
  - Values: Label text to identify links in Discord messages
  - Same label can be used for all platforms (e.g., `"(1080p)"` works for all)
  - Different labels can be specified per platform
  - Label is just text marker - doesn't need to be in URL or specific format

- **share_type**: Whether URL points to single file or folder (optional, auto-detected)
  - `"file"`: Single file download (default)
  - `"folder"`: Download from folder/list (Pixeldrain/GDrive folders, Mega folders)
  - Auto-detection works for most URLs

- **folder_regex**: Regex to extract episode number from folder filenames (optional)
  - Used only when `share_type` is `"folder"`
  - Falls back to Discord regex if no match
  - Falls back to common patterns if neither matches

- **download_multiple**: Download all new episodes from folder (optional, Pixeldrain only)
  - `false` (default): Download only the detected episode
  - `true`: Download all episodes > last_episode in folder

- **platform_config**: Per-platform overrides (optional)
  - Override `share_type`, `folder_regex`, `download_multiple` for specific platforms
  - Useful for mixed single/folder downloads per platform

### Example Configurations

#### Single Platform (Mega Only)
```json
{
  "anime": {
    "entries": [
      {
        "channel_id": "1234567890123456789",
        "name": "My Favorite Anime",
        "regex": "Episode (\\d+)",
        "path": "/media/downloads/anime/my-favorite-anime",
        "last_episode": 0,
        "platforms": ["mega"],
        "link_labels": {
          "mega": "[1080p]"
        }
      }
    ]
  },
  "retry_queue": []
}
```

#### Multi-Platform with Priority
```json
{
  "anime": {
    "entries": [
      {
        "channel_id": "1234567890123456789",
        "name": "Series with Multiple Sources",
        "regex": "Episode (\\d+)",
        "path": "/media/downloads/anime/series",
        "last_episode": 0,
        "platforms": ["pixeldrain", "gdrive", "mega"],
        "link_labels": {
          "pixeldrain": "[1080p]",
          "gdrive": "[1080p]",
          "mega": "[1080p]"
        }
      }
    ]
  },
  "retry_queue": []
}
```

**Platform Priority Behavior:**
```
Message contains: Pixeldrain, GDrive, Mega links all with "[1080p]" label

Bot behavior:
1. Try Pixeldrain first
   ├─ Success? YES → Download, update last_episode, STOP
   └─ Success? NO (quota/error) → Try next platform ↓
2. Try Google Drive
   ├─ Success? YES → Download, update last_episode, STOP
   └─ Success? NO → Try next platform ↓
3. Try Mega
   └─ Success or fail → Done
```

#### Different Labels per Platform
```json
{
  "anime": {
    "entries": [
      {
        "channel_id": "1234567890123456789",
        "name": "Series with Different Qualities",
        "regex": "Episode (\\d+)",
        "path": "/media/downloads/anime/series",
        "last_episode": 0,
        "platforms": ["pixeldrain", "mega"],
        "link_labels": {
          "pixeldrain": "[4K HEVC]",
          "mega": "[1080p]"
        }
      }
    ]
  },
  "retry_queue": []
}
```

#### Folder Download with Episode Matching
```json
{
  "donghua": {
    "entries": [
      {
        "channel_id": "1234567890123456789",
        "name": "Chinese Anime - Batch",
        "regex": "(\\d+)",
        "path": "/media/donghua/series",
        "last_episode": 38,
        "platforms": ["pixeldrain"],
        "link_labels": {
          "pixeldrain": "[Batch]"
        },
        "share_type": "folder",
        "folder_regex": "第(\\d+)话"
      }
    ]
  },
  "retry_queue": []
}
```

#### Multi-Platform with Platform-Specific Config
```json
{
  "donghua": {
    "entries": [
      {
        "channel_id": "1234567890123456789",
        "name": "Mixed Single/Folder Downloads",
        "regex": "第(\\d+)集",
        "path": "/media/donghua/series",
        "last_episode": 25,
        "platforms": ["pixeldrain", "gdrive", "mega"],
        "link_labels": {
          "pixeldrain": "[Folder 1080p]",
          "gdrive": "[Single 4K]",
          "mega": "[Single 1080p]"
        },
        "platform_config": {
          "pixeldrain": {
            "share_type": "folder",
            "folder_regex": "第(\\d+)话",
            "download_multiple": false
          },
          "gdrive": {
            "share_type": "file"
          },
          "mega": {
            "share_type": "file"
          }
        }
      }
    ]
  },
  "retry_queue": []
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
- `第(\\d+)话` - Matches Chinese "第X话" (episode X)
- `第(\\d+)集` - Matches Chinese "第X集" (episode X)
- `My Serie Name - (\\d+)` - Specific series format

**Important:**
- The `\\d+` must be in parentheses `()` to create a capture group for the episode number
- `re.search()` matches pattern ANYWHERE in message
- Only the FIRST match is used as the episode number

**⚠️ Warning:** Too-broad regex like `(\\d+)` will match ANY number in the message, including file sizes (e.g., "638.8 MB"), years, etc. Be as specific as possible.

### Creating Custom Regex Patterns

If you're unsure what regex pattern to use, you can ask an LLM (like Claude, ChatGPT, etc.) to extract the episode number from example messages.

**When to use this:**
- Series is shared in a channel with **multiple other series/links**
- Message format is unique or complex
- You want to avoid matching wrong episodes from other series

**Step-by-step process:**

1. **Copy 2-3 example messages** from Discord showing the series you want to download
2. **Provide them to an LLM** with this prompt:
   ```
   I have these Discord messages. Please write a regex pattern to extract ONLY the episode number from these messages:
   
   Message 1: [paste message here]
   Message 2: [paste message here]
   Message 3: [paste message here]
   
   Requirements:
   - Must use (\\d+) as the capture group for the number
   - Should match the episode number but NOT other numbers (like file sizes, years)
   - Pattern should work with Python re.search()
   - Return only the regex pattern in the format: "pattern here"
   ```

3. **Test the pattern** at regex101.com (select "Python" flavor)
4. **Add to your config** - Remember: This is a JSON file, so backslashes must be **double-escaped**

**Double-Escaping Example:**

When LLM gives you a regex, it will usually look like this in plain text:
```
Pattern: Episode (\d+)
```

But in your `settings.json` file, you need to **double-escape** the backslashes:
```json
{
  "regex": "Episode (\\d+)"
}
```

**Common mistakes to avoid:**

❌ Wrong: `"regex": "Episode (\d+)"` - Single backslash (won't work)
✅ Correct: `"regex": "Episode (\\d+)"` - Double backslash (required for JSON)

**Example workflow:**

**Your Discord messages:**
```
🔥 MySuperShow EP 207 (1080p).mkv 🔥

Link: https://mega.nz/file/abc123...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Server: Best Server Ever
```

```
🔥 Tunshi Xingkong - 207 (1080p) 🔥

https://mega.nz/file/def456...
```

```
[1080p] https://mega.nz/file/xyz789...
MySuperShow - Episode 207 (1080p).mkv
```

**Ask LLM:**
```
Write a regex to extract episode number 207 from these messages. Use (\d+) as capture group.
```

**LLM might suggest:**
```
MySuperShow.*EP\s*(\d+)
Tunshi Xingkong\s*-\s*(\d+)
```

**Add to your config:**
```json
{
  "regex": "MySuperShow.*EP\\s*(\\d+)"
}
```

**Result:** Bot only matches "MySuperShow EP 207" and not "Tunshi Xingkong - 207"

### Folder Regex Examples (for folder downloads)

Used when `share_type` is `"folder"` to extract episode numbers from filenames within the folder:

- `第(\\d+)话` - Matches Chinese episode numbers in filenames
- `第(\\d+)集` - Alternative Chinese format
- `S\\d+E(\\d+)` - Standard TV format
- `EP(\\d+)` - Short episode format

If `folder_regex` is not provided, the bot falls back to:
1. Using the Discord regex pattern
2. Using common patterns (English + Chinese)

## Usage

### Running Manually

```bash
cd discord_autodl
source .venv/bin/activate
python downloader.py
```

Expected output:
```
Loaded JSON OK.
============================================================
Bot logged in and monitoring...
MAX_RETRY configured: 10
============================================================
[QUEUE] Processing retry queue (0 items)...
```

### Running as a Service (Recommended)

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

### Handling Low-Activity Channels

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

**Note:** Replace `/full/path/to/discord_autodl` with your actual path (e.g., `/home/user/discord_autodl`)

Then start with the ecosystem file:
```bash
pm2 delete discord-autodl  // Remove old instance if exists
pm2 start ecosystem.config.js
pm2 save
pm2 logs discord-autodl    // Verify it's working
```

**Common cron restart intervals:**
- `0 */3 * * *` - Every 3 hours (recommended for low-activity channels)
- `0 */6 * * *` - Every 6 hours
- `0 */12 * * *` - Every 12 hours
- `0 0 * * *` - Once daily at midnight

This ensures your bot maintains a fresh connection to Discord's gateway and processes the retry queue periodically.

## How It Works

1. Bot connects to Discord using your token
2. Processes retry queue on startup (retries failed downloads)
3. Monitors all channels specified in `settings.json`
4. When a new message arrives:
    - Checks if channel ID matches any configuration
    - **Regex step**: Applies regex pattern to extract episode number from message content
    - Verifies episode is newer than `last_episode`
    - **Link step**: For each platform in priority order, finds label text and extracts platform URL
    - Tries platforms in priority order (first success wins)
    - Downloads the file using platform-specific downloader
    - Updates `last_episode` in `settings.json`
    - Sets file permissions to 754
5. If download fails with quota error:
    - Adds to retry queue with 4-hour retry interval
    - Bot will retry automatically up to MAX_RETRY times
6. Other failures:
    - Retries next platform in priority order
    - Or adds to retry queue with 1-hour interval

### Platform-Specific Behavior

**Mega.nz:**
- Uses `mega-get` CLI tool
- Requires Mega CMD installation
- Ignores quota warnings
- Supports both file and folder links

**Pixeldrain:**
- Pure Python, no system requirements
- API-based downloads (fastest)
- Auto-detects file vs folder from URL
- For folders: Parses filenames to extract episode numbers
- Supports age filtering (skips files older than `FOLDER_FILE_MAX_AGE_DAYS`)
- Extracts original filenames automatically

**Google Drive:**
- Pure Python, no system requirements
- Handles large files with confirmation bypass
- Auto-detects file vs folder from URL
- Multiple fallback strategies for download URLs
- Extracts filenames from headers or generates fallback
- More prone to quota limits (use retry queue)

### Understanding Logs

**Successful Download:**
```
[MATCH] Channel ID: 123456
[MATCH] Series: My Anime
[MATCH] Episode 12 detected (last: 11)
[FOUND] Available platforms: ['pixeldrain', 'gdrive']

[DOWNLOAD] Trying PIXELDRAIN
[DOWNLOAD] My Anime EP12
[DOWNLOAD] URL: https://pixeldrain.com/u/abc123
[PIXELDRAIN] File ID: abc123
[PIXELDRAIN] Original filename: My_Anime_EP12.mkv
[PIXELDRAIN] Downloading...
[PIXELDRAIN] ✓ Downloaded: My_Anime_EP12.mkv
[SUCCESS] My Anime EP12 downloaded from pixeldrain
```

**Multi-Platform Fallback:**
```
[MATCH] Channel ID: 123456
[MATCH] Series: My Anime
[MATCH] Episode 12 detected (last: 11)
[FOUND] Available platforms: ['pixeldrain', 'gdrive', 'mega']

[DOWNLOAD] Trying PIXELDRAIN
[PIXELDRAIN] ✗ Quota exceeded
[QUOTA] pixeldrain quota exceeded, adding to retry queue
[QUEUE] Added to retry queue: My Anime EP12 (pixeldrain)
[QUEUE] Channel: 123456, URL: https://pixeldrain.com/u/abc123
[QUEUE] Reason: quota_exceeded, Next retry: 2026-01-17T14:30:00

[DOWNLOAD] Trying GDRIVE
[GDRIVE] File ID: abc123
[GDRIVE] ✓ Downloaded: My_Anime_EP12.mkv
[SUCCESS] My Anime EP12 downloaded from gdrive
```

**Retry Queue Processing:**
```
[QUEUE] Processing retry queue (1 items)...

[QUEUE] Retrying: My Anime EP12 (pixeldrain)
[QUEUE] Attempt 2/10
[QUEUE] Channel: 123456, URL: https://pixeldrain.com/u/abc123
[PIXELDRAIN] ✓ Downloaded: My_Anime_EP12.mkv
[QUEUE] ✓ Retry successful! Removing from queue.
```

## Troubleshooting

### Bot doesn't connect
- Verify your Discord token is correct in `.env`
- Check your internet connection
- Ensure you haven't been rate-limited by Discord

### Downloads don't start
- Confirm channel IDs are correct (check bot logs)
- Test your regex patterns (use regex101.com with Python flavor)
- Check that `link_labels` text actually exists in Discord message
- Verify `platforms` array includes the platform being used
- Verify download paths exist and have write permissions

### "KeyError: 'entries'" error
- Your config is in old format (separate `"mega": []` arrays)
- Migrate to new format using `settings_example.json` as reference
- See `MIGRATION_GUIDE.md` for detailed migration steps

### Platform not trying
- Check `platforms` array includes the platform
- Check `link_labels` has entry for the platform
- Verify link label text exists in Discord message
- Check logs for "[FOUND] Available platforms" output

### Folder downloads not working
- Verify `share_type` is set to `"folder"`
- Check URL format (Pixeldrain: `/l/` for folder, `/u/` for file)
- Add `folder_regex` for better episode matching
- Check logs for age filtering messages
- Adjust `FOLDER_FILE_MAX_AGE_DAYS` if needed

### Regex matching wrong numbers
- Your regex is too broad (e.g., `(\\d+)` matches everything)
- Be more specific with context (e.g., `Episode (\\d+)`, `- (\d+) `)
- Remember: Only the FIRST match in the message is used

### Retry queue not processing
- Check `MAX_RETRY` is set in `.env`
- Verify `retry_queue` array exists in `settings.json`
- Wait 4 hours for quota retries, 1 hour for other errors
- Check logs for "[QUEUE] Processing retry queue" messages

### Permission errors
- Ensure download directories exist: `mkdir -p /path/to/download`
- Check folder permissions: `chmod 755 /path/to/download`

### Platform-specific issues

**Mega quota warnings:**
The bot uses `--ignore-quota-warn` flag, but if you hit quota limits, downloads may fail. The bot will automatically retry later or try alternative platforms.

**Google Drive quota exceeded:**
- Download added to retry queue automatically
- Bot retries every 4 hours
- Consider using different platform as primary
- Use `platforms` priority to try faster platforms first

**Pixeldrain not finding episode in folder:**
- Check `folder_regex` matches filenames in folder
- Try removing `folder_regex` to use Discord regex fallback
- Check logs for "[PIXELDRAIN] Matched" messages
- Verify files in folder are not too old (see age filter)

## Testing Your Setup

### Config Validation
```bash
python -c "import json; print(json.load(open('settings.json')))"
```
Should print your config without errors.

### Bot Startup
```bash
python downloader.py
```
Should see "Bot logged in and monitoring..."

### Send Test Message
In your Discord channel, send:
```
Episode 99 test message
[1080p](<https://pixeldrain.com/u/test123>)
```

Expected log:
```
[MATCH] Channel ID: your_channel_id
[MATCH] Series: Your Series Name
[MATCH] Episode 99 detected (last: 0)
[FOUND] Available platforms: ['pixeldrain']
```

## Monitoring

### Check Retry Queue
```bash
cat settings.json | jq .retry_queue
```

### Check Last Episodes
```bash
cat settings.json | jq '.donghua.entries[] | {name, last_episode}'
```

### Follow Logs (if using PM2)
```bash
pm2 logs discord-autodl --lines 50
```

## New Features (v0.1)

### Multi-Platform Support
The bot now supports three download platforms:
- **Mega.nz** - Cloud storage with large file support
- **Pixeldrain** - Fast API-based downloads
- **Google Drive** - Google's cloud storage service

Configure platform priority in the `platforms` array. The bot tries each platform in order and stops at the first successful download.

### Folder Download Support
For platforms that support folders (Pixeldrain, Mega, Google Drive):
- Set `share_type: "folder"` in config
- Use `folder_regex` to match episodes in folder filenames
- Set `download_multiple: true` to download all new episodes at once

### Automatic Retry Queue
Failed downloads are automatically added to a retry queue:
- Quota errors: Retry every 4 hours
- Other errors: Retry every 1 hour
- Max retries controlled by `MAX_RETRY` environment variable
- Queue persists across bot restarts

### Age Filtering
For folder downloads, skip files older than `FOLDER_FILE_MAX_AGE_DAYS` (default: 30):
- Reduces download time for large folders
- Skips old/irrelevant files
- Configurable via `.env`

### Platform-Specific Overrides
Use `platform_config` to override settings per platform:
- Different `share_type` per platform
- Different `folder_regex` per platform
- Different `download_multiple` per platform

## Documentation

For more detailed information:
- **Migration Guide**: See `MIGRATION_GUIDE.md` (if upgrading from old format)
- **Implementation Details**: See `IMPLEMENTATION_SUMMARY.md`
- **Example Config**: See `setting_example.json`

## Security Notes

- Never share your Discord token
- Never commit `.env` or `settings.json` to version control (they're in `.gitignore`)
- Use a dedicated Discord account for automation
- Be aware that automating Discord may violate Terms of Service
- The retry queue stores URLs in `settings.json` - keep it secure
- Google Drive downloads use no authentication cookies (safer)

## Contributing

Feel free to open issues or submit pull requests for improvements!

## Platform Comparison

| Platform | Speed | Quota | Requirements | Best For |
|----------|-------|-------|--------------|----------|
| Pixeldrain | ⚡⚡⚡ | 6 GB per day per IP | None (pure Python) | Fastest downloads, API-based |
| Mega.nz | ⚡⚡⚡ | 5 GB per day per IP (not always enforced) | Mega CMD | Large files, stable service |
| Google Drive | ⚡⚡⚡ | Don't know | None (pure Python) | Google ecosystem, large files |

**Recommendation:** Use platform priority `["mega", "gdrive", "pixeldrain"]` for optimal speed and reliability.

## License

This project is provided as-is for educational purposes. Use responsibly and in accordance with Discord's Terms of Service.
