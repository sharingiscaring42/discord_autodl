import discum
import os
import re
import json
import time
import subprocess
from dotenv import load_dotenv

# LOAD DISCORD_TOKEN from .env
# DISCORD_TOKEN=XXXXXXXXXXXXXXXXXXXXXXXXXXX

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "settings.json")
with open(CONFIG_PATH, "r") as f:
    raw = f.read()
    # print("=== RAW CONTENT ===")
    # print(repr(raw))
    # print("=== END ===")
    config = json.loads(raw)
    print("Loaded JSON OK.")


    # config = json.load(f)

def save_config():
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)

def extract_link_by_label(content, label):
    """
    Extracts mega link based on label, allowing for markdown (e.g., bold) formatting.
    """
    # Normalize the label to handle markdown bold or italic
    label_pattern = re.escape(label).replace(r'\[', r'[\*\s]*\[').replace(r'\]', r'\][\*\s]*')

    # Match [Label] or [**[Label]**](<link>)
    md_pattern = re.compile(rf"\[\s*\**\s*{label_pattern}\s*\**\s*\]\s*\(<(https://mega\.nz/\S+)>\)", re.IGNORECASE)
    match = md_pattern.search(content)
    if match:
        return match.group(1)

    # Fallback: look for label and any mega link nearby
    if label in content:
        link_match = re.search(r"(https://mega\.nz/\S+)", content)
        if link_match:
            return link_match.group(1)

    return None

def handle_new_message(message):
    content = message.get('content', '')
    channel_id = message['channel_id']

    for section, sources in config.items():
        for entry in sources.get("mega", []):
            if entry["channel_id"] != channel_id:
                continue

            print("Channel ID matching:", entry["channel_id"])

            pattern = entry.get("regex", "").strip()
            match = re.search(pattern, content)
            if not match:
                continue
            print("Regex matching:", pattern)
            try:
                episode = int(match.group(1))
            except (IndexError, ValueError):
                continue

            if episode <= entry.get("last_episode", 0):
                continue
            print("Episode matching:", episode)

            label = entry.get("link", "").strip()
            download_link = extract_link_by_label(content, label)
            if not download_link:
                print(f"[SKIP] Label '{label}' not found or no Mega link.")
                continue

            print(f"[MATCH] {entry['name']} EP {episode} — Downloading {label} link...")

            os.chdir(entry["path"])
            subprocess.run(["mega-get", "--ignore-quota-warn", download_link])
            subprocess.run("chmod 754 *", shell=True)

            entry["last_episode"] = episode
            save_config()

            print(f"[DONE] {entry['name']} EP {episode} downloaded.")

bot = discum.Client(token=DISCORD_TOKEN, log=False)

@bot.gateway.command
def on_message(resp):
    if resp.event.ready_supplemental:
        print("Logged in and monitoring...")

    if resp.event.message:
#        print("📥 New message received!")  # Add this
        msg = resp.parsed.auto()
        # print("----------------------------")
        # print("From channel:", msg.get("channel_id"))
        # print("Message content:", msg.get("content"))
        handle_new_message(msg)

while True:
    try:
        bot.gateway.run(auto_reconnect=True)
    except Exception as e:
        print("⚠️ Crash or disconnect:", e)
        time.sleep(10)