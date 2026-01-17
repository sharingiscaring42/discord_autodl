import discum
import os
import re
import json
import time
import subprocess
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# LOAD DISCORD_TOKEN and MAX_RETRY from .env
# DISCORD_TOKEN=XXXXXXXXXXXXXXXXXXXXXXXXXXX
# MAX_RETRY=10

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MAX_RETRY = int(os.getenv("MAX_RETRY", "10"))
FOLDER_FILE_MAX_AGE_DAYS = int(os.getenv("FOLDER_FILE_MAX_AGE_DAYS", "30"))

# ============================================================================
# DOWNLOAD RESULT CLASS
# ============================================================================

class DownloadResult:
    """Return object from downloader.download() methods."""
    def __init__(self, success, reason=None, filename=None):
        self.success = success
        self.reason = reason  # "quota_exceeded", "invalid_link", "network_error", etc.
        self.filename = filename  # Actual downloaded filename


# ============================================================================
# MESSAGE PROCESSOR CLASS
# ============================================================================

class MessageProcessor:
    """Handles message analysis independent of download platform."""
    
    def __init__(self, entry):
        self.name = entry["name"]
        self.regex = entry["regex"]
        self.link_labels = entry.get("link_labels", {})
        self.platforms = entry.get("platforms", ["mega"])
        self.last_episode = entry.get("last_episode", 0)
        self.share_type = entry.get("share_type", "file")  # Default to "file"
        self.folder_regex = entry.get("folder_regex", None)  # Optional regex for folder files
        self.download_multiple = entry.get("download_multiple", False)
        self.platform_config = entry.get("platform_config", {})  # Per-platform overrides
    
    def get_platform_share_type(self, platform):
        """Get share type for specific platform (with per-platform override)."""
        if platform in self.platform_config:
            return self.platform_config[platform].get("share_type", self.share_type)
        return self.share_type
    
    def get_platform_folder_regex(self, platform):
        """Get folder regex for specific platform."""
        if platform in self.platform_config:
            return self.platform_config[platform].get("folder_regex", self.folder_regex)
        return self.folder_regex
    
    def get_platform_download_multiple(self, platform):
        """Get download_multiple setting for specific platform."""
        if platform in self.platform_config:
            return self.platform_config[platform].get("download_multiple", self.download_multiple)
        return self.download_multiple
    
    def extract_episode(self, message_content):
        """Returns episode number or None if no match or already downloaded."""
        match = re.search(self.regex, message_content)
        if not match:
            return None
        try:
            episode = int(match.group(1))
            return episode if episode > self.last_episode else None
        except (IndexError, ValueError):
            return None
    
    def find_platform_links(self, message_content):
        """
        Find links for all configured platforms respecting priority order.
        Returns: dict like {"pixeldrain": "url", "gdrive": "url", "mega": "url"}
        """
        found = {}
        
        for platform in self.platforms:
            label = self.link_labels.get(platform, "")
            if not label:
                continue
            
            link = self._extract_link_by_label(message_content, label, platform)
            if link:
                found[platform] = link
        
        return found
    
    def _extract_link_by_label(self, content, label, platform):
        """Extract platform-specific link based on label with markdown support."""
        # Normalize the label to handle markdown bold or italic
        label_pattern = re.escape(label).replace(r'\[', r'[\*\s]*\[').replace(r'\]', r'\][\*\s]*')
        
        # Define platform URL patterns
        platform_patterns = {
            "mega": r"https://mega\.nz/\S+",
            "pixeldrain": r"https://pixeldrain\.com/[ul]/[a-zA-Z0-9]+",  # Support both /u/ (file) and /l/ (list/folder)
            "gdrive": r"https://drive\.(?:google\.com|usercontent\.google\.com)/[^\s>)]+",  # Support both domains
        }
        
        url_pattern = platform_patterns.get(platform, r"https://\S+")
        
        # Match [Label](<link>) or [**[Label]**](<link>)
        md_pattern = re.compile(
            rf"\[\s*\**\s*{label_pattern}\s*\**\s*\]\s*\(<({url_pattern})>\)", 
            re.IGNORECASE
        )
        match = md_pattern.search(content)
        if match:
            return match.group(1)
        
        # Fallback: look for label and any platform link nearby
        if label in content:
            link_match = re.search(rf"({url_pattern})", content)
            if link_match:
                return link_match.group(1)
        
        return None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def detect_share_type_from_url(url, platform):
    """
    Auto-detect if URL is a folder or single file.
    Returns: "folder" or "file"
    """
    url_lower = url.lower()
    
    if platform == "pixeldrain":
        if "/l/" in url_lower:
            return "folder"
        elif "/u/" in url_lower:
            return "file"
    
    elif platform == "mega":
        if "/folder/" in url_lower or "#F!" in url:
            return "folder"
        elif "/file/" in url_lower or "#!" in url:
            return "file"
    
    elif platform == "gdrive":
        if "/folders/" in url_lower or "/drive/folders/" in url_lower:
            return "folder"
        elif "/file/" in url_lower or "/uc?id=" in url_lower:
            return "file"
    
    return "file"  # Default to file if can't detect


def is_file_too_old(date_string, max_age_days=FOLDER_FILE_MAX_AGE_DAYS):
    """
    Check if a file's upload date is older than max_age_days.
    Args:
        date_string: ISO format date string (e.g., "2025-12-12T23:03:01.681Z")
        max_age_days: Maximum age in days
    Returns:
        True if file is too old, False otherwise
    """
    if not date_string:
        return False  # If no date, don't filter
    
    try:
        from datetime import datetime, timezone
        file_date = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        age_days = (now - file_date).days
        return age_days > max_age_days
    except Exception:
        return False  # If parsing fails, don't filter


# ============================================================================
# PLATFORM DOWNLOADERS
# ============================================================================

class MegaDownloader:
    """Downloads from Mega.nz via mega-get CLI."""
    
    def download(self, link, path, entry_name, episode):
        """
        Args:
            link: Mega.nz URL
            path: Absolute directory path
            entry_name: Series name for logging
            episode: Episode number for logging
        Returns:
            DownloadResult
        """
        print(f"[MEGA] Downloading to {path}")
        os.chdir(path)
        result = subprocess.run(
            ["mega-get", "--ignore-quota-warn", link],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            subprocess.run("chmod 754 *", shell=True)
            print(f"[MEGA] ✓ Download successful")
            return DownloadResult(success=True, filename="unknown")
        else:
            error_msg = result.stderr.lower()
            if "quota" in error_msg or "limit" in error_msg:
                print(f"[MEGA] ✗ Quota exceeded")
                return DownloadResult(success=False, reason="quota_exceeded")
            else:
                print(f"[MEGA] ✗ Download failed: {result.stderr}")
                return DownloadResult(success=False, reason="download_error")


class PixeldrainDownloader:
    """Downloads from Pixeldrain via API with folder/list support."""
    
    def download(self, link, path, entry_name, episode, share_type=None, 
                 folder_regex=None, download_multiple=False, last_episode=0, discord_regex=None):
        """
        Args:
            link: Pixeldrain URL
            path: Absolute directory path
            entry_name: Series name
            episode: Episode number from Discord message
            share_type: "file" or "folder" (auto-detected if None)
            folder_regex: Regex to match episodes in folder filenames
            download_multiple: Download all new episodes from folder
            last_episode: Last downloaded episode number
            discord_regex: Original Discord regex for fallback matching
        Returns:
            DownloadResult
        """
        # Auto-detect share type if not specified
        if share_type is None:
            share_type = detect_share_type_from_url(link, "pixeldrain")
            print(f"[PIXELDRAIN] Auto-detected share type: {share_type}")
        else:
            # Verify config matches URL
            detected = detect_share_type_from_url(link, "pixeldrain")
            if detected != share_type:
                print(f"[PIXELDRAIN] ⚠ Warning: Config says '{share_type}' but URL looks like '{detected}'")
                print(f"[PIXELDRAIN] Using config value: {share_type}")
        
        if share_type == "folder":
            return self._download_from_folder(
                link, path, entry_name, episode, 
                folder_regex, download_multiple, last_episode, discord_regex
            )
        else:
            return self._download_single_file(link, path, entry_name, episode)
    
    def _download_from_folder(self, link, path, entry_name, episode, 
                              folder_regex, download_multiple, last_episode, discord_regex):
        """Download episode(s) from a Pixeldrain folder with smart matching."""
        list_id = link.replace("https://pixeldrain.com/l/", "").split("/")[0].split("?")[0]
        print(f"[PIXELDRAIN] Folder ID: {list_id}")
        
        try:
            # Fetch folder data
            response = requests.get(link, timeout=30)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            script_tag = soup.find('script', string=re.compile(r'window\.viewer_data'))
            
            if not script_tag:
                print("[PIXELDRAIN] ✗ Could not find viewer_data in page")
                return DownloadResult(success=False, reason="folder_parse_error")
            
            script_content = script_tag.string
            match = re.search(r'window\.viewer_data\s*=\s*({.*?});', script_content, re.DOTALL)
            
            if not match:
                print("[PIXELDRAIN] ✗ Could not extract viewer_data JSON")
                return DownloadResult(success=False, reason="folder_parse_error")
            
            viewer_data = json.loads(match.group(1))
            files = viewer_data.get('api_response', {}).get('files', [])
            
            if not files:
                print("[PIXELDRAIN] ✗ No files found in folder")
                return DownloadResult(success=False, reason="no_files")
            
            print(f"[PIXELDRAIN] Found {len(files)} files in folder")
            
            # Extract episode numbers from filenames with age filtering
            files_with_episodes = []
            for file_data in files:
                filename = file_data.get('name', '')
                upload_date = file_data.get('date_upload', '')
                
                # Check if file is too old
                if is_file_too_old(upload_date, FOLDER_FILE_MAX_AGE_DAYS):
                    from datetime import timezone
                    age_days = (datetime.now(timezone.utc) - 
                               datetime.fromisoformat(upload_date.replace('Z', '+00:00'))).days
                    print(f"[PIXELDRAIN] ⏭ Skipping (too old: {age_days} days): {filename}")
                    continue
                
                # Try to extract episode number with fallback chain
                ep_num = self._extract_episode_from_filename(
                    filename, folder_regex, discord_regex
                )
                
                if ep_num is not None:
                    files_with_episodes.append({
                        'file_data': file_data,
                        'episode': ep_num,
                        'filename': filename,
                        'upload_date': upload_date
                    })
            
            if not files_with_episodes:
                print("[PIXELDRAIN] ✗ No files with valid episode numbers found")
                return DownloadResult(success=False, reason="no_episodes_found")
            
            # Sort by episode number
            files_with_episodes.sort(key=lambda x: x['episode'])
            
            print(f"[PIXELDRAIN] Found {len(files_with_episodes)} files with episode numbers")
            
            if download_multiple:
                return self._download_multiple_episodes(
                    files_with_episodes, path, last_episode
                )
            else:
                return self._download_single_episode_from_folder(
                    files_with_episodes, path, episode
                )
            
        except Exception as e:
            print(f"[PIXELDRAIN] ✗ Folder processing failed: {e}")
            import traceback
            traceback.print_exc()
            return DownloadResult(success=False, reason="folder_error")
    
    def _extract_episode_from_filename(self, filename, folder_regex, discord_regex):
        """
        Extract episode number from filename using fallback chain:
        1. folder_regex (if provided)
        2. discord_regex (if provided)
        3. Common patterns (English + Chinese)
        """
        # Try folder_regex first
        if folder_regex:
            match = re.search(folder_regex, filename)
            if match:
                try:
                    ep_num = int(match.group(1))
                    print(f"[PIXELDRAIN] Matched (folder_regex): EP{ep_num} - {filename}")
                    return ep_num
                except (ValueError, IndexError):
                    pass
        
        # Try discord_regex second
        if discord_regex:
            match = re.search(discord_regex, filename)
            if match:
                try:
                    ep_num = int(match.group(1))
                    print(f"[PIXELDRAIN] Matched (discord_regex): EP{ep_num} - {filename}")
                    return ep_num
                except (ValueError, IndexError):
                    pass
        
        # Try common patterns third
        ep_num = self._extract_episode_common_patterns(filename)
        if ep_num is not None:
            print(f"[PIXELDRAIN] Matched (common pattern): EP{ep_num} - {filename}")
            return ep_num
        
        print(f"[PIXELDRAIN] No match: {filename}")
        return None
    
    def _extract_episode_common_patterns(self, filename):
        """Extract episode using common English and Chinese patterns."""
        patterns = [
            # Chinese patterns (try first for donghua)
            (r"第0*(\d+)话", 1),
            (r"第0*(\d+)集", 1),
            (r"第0*(\d+)章", 1),
            (r"第0*(\d+)期", 1),
            # English patterns
            (r"[Ss]\d+[Ee]0*(\d+)", 1),  # S01E07 (most specific)
            (r"[Ee](?:pisode)?[-_\s]*0*(\d+)", 1),  # E07, Episode 7
            (r"EP0*(\d+)", 1),  # EP07
            (r"[-_\s]0*(\d+)(?:\D|$)", 1),  # -07 (least specific, may false match)
        ]
        
        for pattern, group in patterns:
            match = re.search(pattern, filename)
            if match:
                try:
                    return int(match.group(group))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _download_multiple_episodes(self, files_with_episodes, path, last_episode):
        """Download all episodes > last_episode from folder."""
        print(f"[PIXELDRAIN] Multiple download mode: episodes > {last_episode}")
        
        to_download = [f for f in files_with_episodes if f['episode'] > last_episode]
        
        if not to_download:
            print(f"[PIXELDRAIN] ✗ No new episodes (all <= {last_episode})")
            return DownloadResult(success=False, reason="no_new_episodes")
        
        print(f"[PIXELDRAIN] Found {len(to_download)} new episodes to download")
        
        highest_episode = last_episode
        successful_count = 0
        
        for idx, file_info in enumerate(to_download, 1):
            ep_num = file_info['episode']
            file_id = file_info['file_data'].get('id', '')
            filename = file_info['filename']
            
            print(f"\n[PIXELDRAIN] Downloading {idx}/{len(to_download)}: EP{ep_num}")
            result = self._download_file_by_id(file_id, filename, path)
            
            if result.success:
                highest_episode = ep_num
                successful_count += 1
                print(f"[PIXELDRAIN] ✓ EP{ep_num} downloaded, updating last_episode")
                # Note: last_episode will be updated by caller after each success
            else:
                print(f"[PIXELDRAIN] ✗ EP{ep_num} failed: {result.reason}")
                print(f"[PIXELDRAIN] Stopping multiple download (stop on fail)")
                break
        
        if successful_count > 0:
            return DownloadResult(
                success=True,
                filename=f"EP{highest_episode}",  # Caller will parse this
                reason=None
            )
        else:
            return DownloadResult(success=False, reason="all_downloads_failed")
    
    def _download_single_episode_from_folder(self, files_with_episodes, path, episode):
        """Download specific episode from folder."""
        print(f"[PIXELDRAIN] Single download mode: looking for EP{episode}")
        
        matched = None
        for file_info in files_with_episodes:
            if file_info['episode'] == episode:
                matched = file_info
                break
        
        if not matched:
            print(f"[PIXELDRAIN] ✗ EP{episode} not found in folder")
            return DownloadResult(success=False, reason="episode_not_found")
        
        print(f"[PIXELDRAIN] ✓ Found EP{episode}: {matched['filename']}")
        
        file_id = matched['file_data'].get('id', '')
        filename = matched['filename']
        
        return self._download_file_by_id(file_id, filename, path)
    
    def _download_single_file(self, link, path, entry_name, episode):
        """Download a single file from Pixeldrain."""
        # Extract file ID
        file_id = link.replace("https://pixeldrain.com/u/", "").split("/")[0].split("?")[0]
        print(f"[PIXELDRAIN] File ID: {file_id}")
        
        # Get filename from API
        try:
            info_response = requests.get(
                f"https://pixeldrain.com/api/file/{file_id}/info",
                timeout=10
            )
            info_response.raise_for_status()
            info = info_response.json()
            filename = info.get('name', f"{entry_name}_EP{episode:02d}.mkv")
            print(f"[PIXELDRAIN] Original filename: {filename}")
        except Exception as e:
            print(f"[PIXELDRAIN] ⚠ Failed to get info: {e}, using fallback name")
            filename = f"{entry_name}_EP{episode:02d}.mkv"
        
        return self._download_file_by_id(file_id, filename, path)
    
    def _download_file_by_id(self, file_id, filename, path):
        """Common download logic for both single files and list items."""
        try:
            print(f"[PIXELDRAIN] Downloading {filename}...")
            filepath = os.path.join(path, filename)
            
            # Stream download to avoid loading entire file in memory
            with requests.get(
                f"https://pixeldrain.com/api/file/{file_id}",
                stream=True,
                timeout=30
            ) as response:
                response.raise_for_status()
                
                # Check for quota errors
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    error_data = response.json()
                    if 'quota' in str(error_data).lower():
                        print(f"[PIXELDRAIN] ✗ Quota exceeded")
                        return DownloadResult(success=False, reason="quota_exceeded")
                
                # Stream to file in chunks
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            
            os.chmod(filepath, 0o754)
            print(f"[PIXELDRAIN] ✓ Downloaded: {filename}")
            return DownloadResult(success=True, filename=filename)
            
        except requests.exceptions.Timeout:
            print(f"[PIXELDRAIN] ✗ Download timeout")
            return DownloadResult(success=False, reason="timeout")
        except Exception as e:
            print(f"[PIXELDRAIN] ✗ Download failed: {e}")
            import traceback
            traceback.print_exc()
            return DownloadResult(success=False, reason="download_error")


class GoogleDriveDownloader:
    """Downloads from Google Drive without external libraries."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def download(self, link, path, entry_name, episode):
        """
        Args:
            link: Google Drive URL (any format)
            path: Absolute directory path
            entry_name: Series name for fallback naming
            episode: Episode number for fallback naming
        Returns:
            DownloadResult
        """
        file_id = self._extract_file_id(link)
        if not file_id:
            print("[GDRIVE] ✗ Could not extract file ID from URL")
            return DownloadResult(success=False, reason="invalid_link")
        
        print(f"[GDRIVE] File ID: {file_id}")
        
        try:
            # Try the usercontent.google.com domain first (direct download)
            download_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&authuser=0"
            
            print(f"[GDRIVE] Attempting direct download from usercontent.google.com...")
            response = self.session.get(download_url, stream=True, timeout=30, allow_redirects=True)
            
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            
            # If we got HTML, try the traditional drive.google.com URL
            if 'text/html' in content_type:
                print(f"[GDRIVE] Got HTML from usercontent, trying drive.google.com...")
                
                # Read a bit to check for errors
                first_chunk = next(response.iter_content(chunk_size=4096), b'')
                html_preview = first_chunk.decode('utf-8', errors='ignore').lower()
                
                # Check for quota
                if 'quota' in html_preview or 'download quota' in html_preview:
                    print("[GDRIVE] ✗ Quota exceeded")
                    return DownloadResult(success=False, reason="quota_exceeded")
                
                # Try alternative approach with confirm=t
                print(f"[GDRIVE] Trying with confirm=t parameter...")
                download_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&authuser=0&confirm=t"
                response = self.session.get(download_url, stream=True, timeout=30, allow_redirects=True)
                
                content_type = response.headers.get('Content-Type', '')
                
                # Still HTML? This means it really needs the old-style confirmation
                if 'text/html' in content_type:
                    print(f"[GDRIVE] Still HTML, trying legacy confirmation method...")
                    
                    # Get the full HTML to parse
                    legacy_url = f"https://drive.google.com/uc?id={file_id}&export=download"
                    response = self.session.get(legacy_url, timeout=30)
                    
                    # Check for quota in HTML
                    html_content = response.text
                    if 'quota' in html_content.lower() or 'download quota' in html_content.lower():
                        print("[GDRIVE] ✗ Quota exceeded")
                        return DownloadResult(success=False, reason="quota_exceeded")
                    
                    # Try to extract confirm token
                    confirm_token = self._extract_confirm_token(html_content)
                    
                    if confirm_token:
                        print(f"[GDRIVE] Found confirm token: {confirm_token[:20]}...")
                        
                        # Try multiple confirmation URL formats
                        confirm_urls = [
                            f"https://drive.usercontent.google.com/download?id={file_id}&export=download&authuser=0&confirm={confirm_token}",
                            f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm_token}",
                        ]
                        
                        for confirm_url in confirm_urls:
                            print(f"[GDRIVE] Trying confirmation URL...")
                            response = self.session.get(confirm_url, stream=True, timeout=30, allow_redirects=True)
                            content_type = response.headers.get('Content-Type', '')
                            
                            if 'text/html' not in content_type:
                                print(f"[GDRIVE] ✓ Confirmation successful")
                                break
                        else:
                            print("[GDRIVE] ✗ All confirmation attempts failed")
                            return DownloadResult(success=False, reason="confirmation_failed")
                    else:
                        print("[GDRIVE] ✗ Could not find confirmation token")
                        return DownloadResult(success=False, reason="confirmation_failed")
            
            # At this point we should have the actual file stream
            # Verify we didn't get HTML
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                print(f"[GDRIVE] ✗ Still receiving HTML, cannot download")
                return DownloadResult(success=False, reason="html_response")
            
            # Determine filename
            filename = self._determine_filename(response, file_id, entry_name, episode)
            print(f"[GDRIVE] Filename: {filename}")
            
            # Stream download to file
            filepath = os.path.join(path, filename)
            print(f"[GDRIVE] Downloading to {filepath}...")
            
            total_size = 0
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
            
            print(f"[GDRIVE] Downloaded {total_size} bytes ({total_size / (1024*1024):.2f} MB)")
            
            # Verify we got a real file (not tiny HTML error page)
            if total_size < 10000:
                print(f"[GDRIVE] ⚠ Warning: File size is very small ({total_size} bytes), checking content...")
                with open(filepath, 'r', errors='ignore') as f:
                    content_preview = f.read(500).lower()
                    if 'html' in content_preview or '<html' in content_preview:
                        print(f"[GDRIVE] ✗ Downloaded HTML instead of file")
                        os.remove(filepath)
                        return DownloadResult(success=False, reason="html_instead_of_file")
            
            os.chmod(filepath, 0o754)
            print(f"[GDRIVE] ✓ Downloaded: {filename}")
            return DownloadResult(success=True, filename=filename)
            
        except requests.exceptions.Timeout:
            print("[GDRIVE] ✗ Download timeout")
            return DownloadResult(success=False, reason="timeout")
        except Exception as e:
            print(f"[GDRIVE] ✗ Download failed: {e}")
            import traceback
            traceback.print_exc()
            return DownloadResult(success=False, reason="download_error")
    
    def _extract_file_id(self, url):
        """Parse various Google Drive URL formats."""
        # Handle drive.usercontent.google.com format
        if 'drive.usercontent.google.com' in url:
            match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
            if match:
                return match.group(1)
        
        # Handle regular drive.google.com formats
        patterns = [
            r'/file/d/([a-zA-Z0-9_-]+)',
            r'id=([a-zA-Z0-9_-]+)',
            r'/open\?id=([a-zA-Z0-9_-]+)',
            r'/uc\?id=([a-zA-Z0-9_-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def _extract_confirm_token(self, html_content):
        """Extract confirmation token from Google Drive HTML."""
        # Try multiple patterns
        patterns = [
            r'confirm=([^&"]+)',
            r'"confirm"\s*:\s*"([^"]+)"',
            r'name="confirm"\s+value="([^"]+)"',
            r'id="download-form"[^>]*action="[^"]*confirm=([^&"]+)',
            r'"downloadUrl":"[^"]*confirm=([^&"]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                return match.group(1)
        
        return None
    
    def _determine_filename(self, response, file_id, entry_name, episode):
        """Multi-strategy filename detection."""
        # Strategy 1: Content-Disposition header (most reliable)
        content_disp = response.headers.get('Content-Disposition', '')
        if content_disp:
            # Try UTF-8 encoded filename first
            match = re.search(r"filename\*=UTF-8''([^;]+)", content_disp)
            if match:
                filename = requests.utils.unquote(match.group(1))
                if filename and filename != "download":
                    return filename
            
            # Try regular filename
            match = re.search(r'filename="?([^";]+)"?', content_disp)
            if match:
                filename = match.group(1).strip('"')
                if filename and filename != "download":
                    return filename
        
        # Strategy 2: Generate from entry metadata
        sanitized_name = re.sub(r'[^\w\s\-]', '_', entry_name)
        sanitized_name = re.sub(r'\s+', '_', sanitized_name)
        return f"{sanitized_name}_EP{episode:02d}.mkv"


# ============================================================================
# DOWNLOADER FACTORY
# ============================================================================

_downloaders = {
    "mega": MegaDownloader(),
    "pixeldrain": PixeldrainDownloader(),
    "gdrive": GoogleDriveDownloader()
}

def get_downloader(platform):
    """Factory function to get platform downloader."""
    return _downloaders.get(platform)


# ============================================================================
# RETRY QUEUE MANAGEMENT
# ============================================================================

def add_to_retry_queue(entry_name, episode, platform, link, path, channel_id, reason):
    """Add failed download to retry queue."""
    retry_item = {
        "entry_name": entry_name,
        "episode": episode,
        "platform": platform,
        "link": link,
        "path": path,
        "channel_id": channel_id,
        "attempts": 1,
        "next_retry": (datetime.now() + timedelta(hours=4)).isoformat(),
        "reason": reason
    }
    
    if "retry_queue" not in config:
        config["retry_queue"] = []
    
    config["retry_queue"].append(retry_item)
    save_config()
    
    print(f"[QUEUE] Added to retry queue: {entry_name} EP{episode} ({platform})")
    print(f"[QUEUE] Channel: {channel_id}, URL: {link}")
    print(f"[QUEUE] Reason: {reason}, Next retry: {retry_item['next_retry']}")


def process_retry_queue():
    """Process items in retry queue that are due for retry."""
    if "retry_queue" not in config or not config["retry_queue"]:
        return
    
    now = datetime.now()
    items_to_remove = []
    
    print(f"[QUEUE] Processing retry queue ({len(config['retry_queue'])} items)...")
    
    for i, item in enumerate(config["retry_queue"]):
        next_retry = datetime.fromisoformat(item["next_retry"])
        
        if now < next_retry:
            continue  # Not time yet
        
        print(f"\n[QUEUE] Retrying: {item['entry_name']} EP{item['episode']} ({item['platform']})")
        print(f"[QUEUE] Attempt {item['attempts']}/{MAX_RETRY}")
        print(f"[QUEUE] Channel: {item['channel_id']}, URL: {item['link']}")
        
        # Attempt download
        downloader = get_downloader(item["platform"])
        if not downloader:
            print(f"[QUEUE] ✗ Unknown platform: {item['platform']}")
            items_to_remove.append(i)
            continue
        
        result = downloader.download(
            item["link"],
            item["path"],
            item["entry_name"],
            item["episode"]
        )
        
        if result.success:
            print(f"[QUEUE] ✓ Retry successful! Removing from queue.")
            items_to_remove.append(i)
            
            # Update last_episode in config
            for section, data in config.items():
                if section == "retry_queue":
                    continue
                if "entries" in data:
                    for entry in data["entries"]:
                        if entry["name"] == item["entry_name"]:
                            entry["last_episode"] = item["episode"]
                            break
        
        elif result.reason == "quota_exceeded":
            # Increment attempts and schedule next retry
            item["attempts"] += 1
            
            if item["attempts"] >= MAX_RETRY:
                print(f"[QUEUE] ✗ Max retries ({MAX_RETRY}) reached. Giving up.")
                print(f"[QUEUE] Failed item: {item['entry_name']} EP{item['episode']}")
                print(f"[QUEUE] Channel: {item['channel_id']}, URL: {item['link']}")
                items_to_remove.append(i)
            else:
                item["next_retry"] = (datetime.now() + timedelta(hours=4)).isoformat()
                print(f"[QUEUE] Still quota limited. Next retry: {item['next_retry']}")
        
        else:
            # Other error - increment and retry sooner (1 hour)
            item["attempts"] += 1
            
            if item["attempts"] >= MAX_RETRY:
                print(f"[QUEUE] ✗ Max retries ({MAX_RETRY}) reached. Giving up.")
                print(f"[QUEUE] Failed item: {item['entry_name']} EP{item['episode']}")
                print(f"[QUEUE] Channel: {item['channel_id']}, URL: {item['link']}")
                items_to_remove.append(i)
            else:
                item["next_retry"] = (datetime.now() + timedelta(hours=1)).isoformat()
                print(f"[QUEUE] Error: {result.reason}. Next retry in 1 hour: {item['next_retry']}")
    
    # Remove completed/failed items
    for i in reversed(items_to_remove):
        config["retry_queue"].pop(i)
    
    if items_to_remove:
        save_config()
        print(f"[QUEUE] Removed {len(items_to_remove)} items from queue")


# ============================================================================
# CONFIG LOADING
# ============================================================================

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


# ============================================================================
# MESSAGE HANDLER
# ============================================================================

def handle_new_message(message):
    """Process incoming Discord message across all configured entries."""
    content = message.get('content', '')
    channel_id = message['channel_id']
    
    # Process retry queue after handling new message
    process_retry_queue()
    
    # Iterate through all sections and entries
    for section, data in config.items():
        if section == "retry_queue":
            continue
        
        if "entries" not in data:
            continue
        
        for entry in data["entries"]:
            if entry["channel_id"] != channel_id:
                continue
            
            print(f"\n[MATCH] Channel ID: {entry['channel_id']}")
            print(f"[MATCH] Series: {entry['name']}")
            
            # Use MessageProcessor for analysis
            processor = MessageProcessor(entry)
            episode = processor.extract_episode(content)
            
            if not episode:
                continue
            
            print(f"[MATCH] Episode {episode} detected (last: {entry.get('last_episode', 0)})")
            
            # Find all platform links in the message
            platform_links = processor.find_platform_links(content)
            
            if not platform_links:
                print(f"[SKIP] No matching links found for configured platforms")
                continue
            
            print(f"[FOUND] Available platforms: {list(platform_links.keys())}")
            
            # Try platforms in priority order
            download_success = False
            for platform in processor.platforms:
                if platform not in platform_links:
                    continue
                
                download_link = platform_links[platform]
                print(f"\n[DOWNLOAD] Trying {platform.upper()}")
                print(f"[DOWNLOAD] {entry['name']} EP{episode}")
                print(f"[DOWNLOAD] URL: {download_link}")
                
                # Get appropriate downloader
                downloader = get_downloader(platform)
                if not downloader:
                    print(f"[ERROR] Unknown platform: {platform}")
                    continue
                
                # Get platform-specific configuration
                share_type = processor.get_platform_share_type(platform)
                folder_regex = processor.get_platform_folder_regex(platform)
                download_multiple = processor.get_platform_download_multiple(platform)
                
                # Prepare download arguments
                download_args = {
                    "link": download_link,
                    "path": entry["path"],
                    "entry_name": entry["name"],
                    "episode": episode
                }
                
                # Add folder-specific parameters for Pixeldrain
                if platform == "pixeldrain":
                    download_args.update({
                        "share_type": share_type,
                        "folder_regex": folder_regex,
                        "download_multiple": download_multiple,
                        "last_episode": entry.get("last_episode", 0),
                        "discord_regex": processor.regex
                    })
                
                # Attempt download
                result = downloader.download(**download_args)
                
                if result.success:
                    print(f"[SUCCESS] {entry['name']} EP{episode} downloaded from {platform}")
                    
                    # For multiple downloads, extract highest episode from result
                    if download_multiple and share_type == "folder":
                        # result.filename contains "EP{highest}" for multiple downloads
                        match = re.search(r'EP(\d+)', result.filename)
                        if match:
                            highest_ep = int(match.group(1))
                            entry["last_episode"] = highest_ep
                            print(f"[UPDATE] last_episode = {highest_ep}")
                        else:
                            entry["last_episode"] = episode
                    else:
                        entry["last_episode"] = episode
                    
                    save_config()
                    download_success = True
                    break  # Success, don't try other platforms
                
                elif result.reason == "quota_exceeded":
                    print(f"[QUOTA] {platform} quota exceeded, adding to retry queue")
                    add_to_retry_queue(
                        entry["name"],
                        episode,
                        platform,
                        download_link,
                        entry["path"],
                        channel_id,
                        "quota_exceeded"
                    )
                    # Try next platform
                    continue
                
                else:
                    print(f"[FAILED] {platform} download failed: {result.reason}")
                    # Try next platform
                    continue
            
            if not download_success:
                print(f"[FAILED] All platforms failed for {entry['name']} EP{episode}")


# ============================================================================
# BOT INITIALIZATION
# ============================================================================

bot = discum.Client(token=DISCORD_TOKEN, log=False)

@bot.gateway.command
def on_message(resp):
    if resp.event.ready_supplemental:
        print("="*60)
        print("Bot logged in and monitoring...")
        print(f"MAX_RETRY configured: {MAX_RETRY}")
        print("="*60)
        # Process retry queue on startup
        process_retry_queue()

    if resp.event.message:
        msg = resp.parsed.auto()
        handle_new_message(msg)


# ============================================================================
# MAIN LOOP
# ============================================================================

while True:
    try:
        bot.gateway.run(auto_reconnect=True)
    except Exception as e:
        print("⚠️ Crash or disconnect:", e)
        time.sleep(10)