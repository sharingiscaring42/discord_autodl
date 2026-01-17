# Quick Start: Multi-Platform Setup

## Prerequisites Installed
- ✅ Python 3.10+ 
- ✅ mega-get CLI tool
- ✅ Discord token

## Step-by-Step Setup

### 1. Install New Dependencies
```bash
cd /home/anon/code/discord_autodl
source .venv/bin/activate
pip install beautifulsoup4==4.12.3 lxml==5.1.0
```

### 2. Update .env File
```bash
# Add this line to .env
echo "MAX_RETRY=10" >> .env
```

Your `.env` should now contain:
```
DISCORD_TOKEN=your_token_here
MAX_RETRY=10
```

### 3. Update settings.json

**OLD FORMAT** (won't work anymore):
```json
{
  "anime": {
    "mega": [
      {
        "channel_id": "123",
        "name": "Series",
        "regex": "EP(\\d+)",
        "link": "[1080p]",
        "path": "/downloads",
        "last_episode": 0
      }
    ]
  }
}
```

**NEW FORMAT** (required):
```json
{
  "anime": {
    "entries": [
      {
        "channel_id": "123",
        "name": "Series",
        "regex": "EP(\\d+)",
        "path": "/downloads",
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

### 4. Start Bot
```bash
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

## Example Configs

### Single Platform (Mega Only)
```json
{
  "anime": {
    "entries": [
      {
        "channel_id": "1234567890",
        "name": "My Anime Series",
        "regex": "Episode (\\d+)",
        "path": "/home/user/downloads/anime",
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

### Multi-Platform with Priority
```json
{
  "anime": {
    "entries": [
      {
        "channel_id": "1234567890",
        "name": "My Anime Series",
        "regex": "Episode (\\d+)",
        "path": "/home/user/downloads/anime",
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

**Platform Priority Explained**:
- Bot tries Pixeldrain first
- If Pixeldrain fails (quota/error), tries Google Drive
- If GDrive fails, tries Mega
- Stops at first successful download

### Multiple Series
```json
{
  "anime": {
    "entries": [
      {
        "channel_id": "111111",
        "name": "Series One",
        "regex": "Episode (\\d+)",
        "path": "/downloads/series-one",
        "last_episode": 5,
        "platforms": ["pixeldrain", "mega"],
        "link_labels": {
          "pixeldrain": "[1080p]",
          "mega": "[1080p]"
        }
      },
      {
        "channel_id": "222222",
        "name": "Series Two",
        "regex": "EP(\\d+)",
        "path": "/downloads/series-two",
        "last_episode": 12,
        "platforms": ["gdrive"],
        "link_labels": {
          "gdrive": "[4K]"
        }
      }
    ]
  },
  "donghua": {
    "entries": [
      {
        "channel_id": "333333",
        "name": "Chinese Series",
        "regex": "S\\d+E(\\d+)",
        "path": "/media/donghua",
        "last_episode": 0,
        "platforms": ["pixeldrain", "gdrive", "mega"],
        "link_labels": {
          "pixeldrain": "[HEVC]",
          "gdrive": "[HEVC]",
          "mega": "[HEVC]"
        }
      }
    ]
  },
  "retry_queue": []
}
```

## Testing Your Setup

### Test 1: Config Validation
```bash
python -c "import json; print(json.load(open('settings.json')))"
```
Should print your config without errors.

### Test 2: Bot Startup
```bash
python downloader.py
```
Should see "Bot logged in and monitoring..."

### Test 3: Send Test Message
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

## Common Issues

### Issue: "KeyError: 'entries'"
**Cause**: Old config format
**Fix**: Migrate config using new format (see examples above)

### Issue: "ModuleNotFoundError: No module named 'bs4'"
**Cause**: Missing dependencies
**Fix**: `pip install beautifulsoup4 lxml`

### Issue: No logs appearing
**Cause**: Wrong channel_id or regex not matching
**Fix**: Enable debug - uncomment line 563 in downloader.py:
```python
print("📥 New message received!")  # Enable this
print("From channel:", msg.get("channel_id"))
print("Message content:", msg.get("content"))
```

### Issue: Downloads not starting
**Check**:
1. Verify channel_id is correct (enable debug mode)
2. Verify regex matches your message format
3. Verify link_labels match Discord message exactly
4. Verify download path exists and is writable

## Understanding Logs

### Successful Download
```
[MATCH] Channel ID: 123456
[MATCH] Series: My Anime
[MATCH] Episode 12 detected (last: 11)
[FOUND] Available platforms: ['pixeldrain']

[DOWNLOAD] Trying PIXELDRAIN
[DOWNLOAD] My Anime EP12
[DOWNLOAD] URL: https://pixeldrain.com/u/abc123
[PIXELDRAIN] File ID: abc123
[PIXELDRAIN] Original filename: My_Anime_EP12.mkv
[PIXELDRAIN] Downloading...
[PIXELDRAIN] ✓ Downloaded: My_Anime_EP12.mkv
[SUCCESS] My Anime EP12 downloaded from pixeldrain
```

### Quota Failure (Auto-Retry)
```
[GDRIVE] ✗ Quota exceeded
[QUOTA] gdrive quota exceeded, adding to retry queue
[QUEUE] Added to retry queue: My Anime EP12 (gdrive)
[QUEUE] Channel: 123456, URL: https://drive.google.com/.../xxx
[QUEUE] Reason: quota_exceeded, Next retry: 2026-01-14T20:30:00
```

Bot will automatically retry every 4 hours.

### Retry Success
```
[QUEUE] Processing retry queue (1 items)...

[QUEUE] Retrying: My Anime EP12 (gdrive)
[QUEUE] Attempt 2/10
[QUEUE] Channel: 123456, URL: https://drive.google.com/.../xxx
[GDRIVE] ✓ Downloaded: My_Anime_EP12.mkv
[QUEUE] ✓ Retry successful! Removing from queue.
```

## Platform-Specific Notes

### Mega.nz
- Requires `mega-get` installed: `sudo apt install megacmd`
- Same behavior as before (unchanged)
- quota warnings ignored automatically

### Pixeldrain
- No system requirements (pure Python)
- Very fast downloads
- Rare quota issues
- Extracts original filenames automatically

### Google Drive
- No system requirements (pure Python)
- Handles large files automatically
- More prone to quota limits
- Extracts filenames from server or generates fallback

## Monitoring

### Check Retry Queue
```bash
cat settings.json | jq .retry_queue
```

### Check Last Episodes
```bash
cat settings.json | jq '.anime.entries[] | {name, last_episode}'
```

### Follow Logs (if using PM2)
```bash
pm2 logs discord-autodl --lines 50
```

## Next Steps

1. ✅ Start bot with one simple entry
2. ✅ Verify episode detection works
3. ✅ Add more series gradually
4. ✅ Enable multi-platform for redundancy
5. ✅ Monitor retry queue for quota issues

## Need Help?

- **Config Format**: See `setting_example.json`
- **Migration**: See `MIGRATION_GUIDE.md`
- **Architecture**: See `.github/copilot-instructions.md`
- **Full Details**: See `IMPLEMENTATION_SUMMARY.md`

## Production Deployment

Once tested, set up PM2:
```bash
pm2 start downloader.py --name discord-autodl --interpreter .venv/bin/python
pm2 save
pm2 startup
```

Or with cron restart (recommended):
```javascript
// ecosystem.config.js
module.exports = {
  apps: [{
    name: 'discord-autodl',
    script: 'downloader.py',
    interpreter: '/home/anon/code/discord_autodl/.venv/bin/python',
    cwd: '/home/anon/code/discord_autodl',
    cron_restart: '0 */3 * * *',  // Restart every 3 hours
    autorestart: true,
    max_restarts: 10,
    min_uptime: '10s'
  }]
}
```

Start:
```bash
pm2 start ecosystem.config.js
pm2 save
```

✨ You're ready to go!
