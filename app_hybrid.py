from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import sqlite3
import os
import time
import re
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from langdetect import detect

# import assemblyai as aai

# # AssemblyAI API Key (add to environment variables on Render)
# ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY', '')

# # Configure AssemblyAI
# if ASSEMBLYAI_API_KEY:
#     aai.settings.api_key = ASSEMBLYAI_API_KEY


import whisper
import torch

# Load Whisper model (tiny for speed, base for better accuracy)
WHISPER_MODEL = None

def load_whisper_model():
    """Load Whisper model (lazy loading)"""
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        print("🎤 Loading Whisper model...")
        # Use 'tiny' for faster processing (75MB), 'base' for better accuracy (142MB)
        WHISPER_MODEL = whisper.load_model("tiny")
        print("✅ Whisper model loaded")
    return WHISPER_MODEL


app = Flask(__name__)
DB_PATH = '/tmp/srimad_bhagavatam.db'

VIDEO_MAPPING = {
    (3, 6): "TEiPIekJjcw&t=190s",  # Replace with actual video ID
    (3, 7): "ZjYSN_mp-2k&t=41s",  # Replace with actual video ID
}

def init_db():
    """Initialize database with both tables"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS verses (
                canto INTEGER,
                chapter INTEGER,
                verse INTEGER,
                devanagari_verse TEXT,
                sanskrit_verse TEXT,
                word_meanings TEXT,
                translation TEXT,
                purport TEXT,
                PRIMARY KEY (canto, chapter, verse)
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS chapter_meanings (
                canto INTEGER,
                chapter INTEGER,
                video_id TEXT,
                transcript TEXT,
                translation TEXT,
                fetched_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (canto, chapter)
            )
        """)
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database init error: {e}")


import json
import subprocess

# YouTube playlist URL
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLyepYeJqc4uE3d3CHZbUP9eS6jI471qbK"

# Cache file for video mappings
MAPPING_CACHE_FILE = '/tmp/video_mappings.json'

def fetch_playlist_videos():
    """Fetch all videos from YouTube playlist using yt-dlp"""
    try:
        print(f"📺 Fetching playlist videos from YouTube...")
        
        # Check cache first
        if os.path.exists(MAPPING_CACHE_FILE):
            try:
                with open(MAPPING_CACHE_FILE, 'r') as f:
                    cached_data = json.load(f)
                    cache_age = time.time() - cached_data.get('timestamp', 0)
                    
                    # Cache valid for 7 days
                    if cache_age < 7 * 24 * 3600:
                        print(f"✅ Using cached playlist data ({len(cached_data['videos'])} videos)")
                        return cached_data['videos']
            except:
                pass
        
        # Fetch fresh data using yt-dlp
        cmd = [
            'yt-dlp',
            '--dump-json',
            '--flat-playlist',
            '--skip-download',
            PLAYLIST_URL
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"⚠️ yt-dlp error: {result.stderr}")
            return []
        
        # Parse output (each line is a JSON object)
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                try:
                    video_data = json.loads(line)
                    videos.append({
                        'id': video_data.get('id'),
                        'title': video_data.get('title'),
                        'url': f"https://www.youtube.com/watch?v={video_data.get('id')}"
                    })
                except:
                    continue
        
        print(f"✅ Fetched {len(videos)} videos from playlist")
        
        # Cache the results
        try:
            with open(MAPPING_CACHE_FILE, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'videos': videos
                }, f)
        except:
            pass
        
        return videos
        
    except Exception as e:
        print(f"❌ Error fetching playlist: {e}")
        return []

def parse_title_for_canto_chapter(title):
    """Extract canto and chapter from video title"""
    try:
        title = title.lower()
        
        # Pattern 1: "SB 3.1" or "sb 3.1"
        match = re.search(r'sb\s*(\d+)\.(\d+)', title)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        
        # Pattern 2: "Canto 3 Chapter 1" or "canto 3 chapter 1"
        match = re.search(r'canto\s*(\d+)\s*chapter\s*(\d+)', title)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        
        # Pattern 3: "3.1" at start or after space
        match = re.search(r'(?:^|\s)(\d+)\.(\d+)', title)
        if match:
            canto = int(match.group(1))
            chapter = int(match.group(2))
            # Sanity check: canto should be 1-12
            if 1 <= canto <= 12:
                return (canto, chapter)
        
        # Pattern 4: Tamil/Hindi - "பாகவதம் 3 அத்தியாயம் 1" etc
        match = re.search(r'(\d+).*?(\d+)', title)
        if match:
            canto = int(match.group(1))
            chapter = int(match.group(2))
            if 1 <= canto <= 12:
                return (canto, chapter)
        
        return None
        
    except Exception as e:
        print(f"⚠️ Error parsing title '{title}': {e}")
        return None

def build_video_mapping():
    """Build automatic mapping of (canto, chapter) -> video_id"""
    try:
        print("\n🔄 Building automatic video mapping...")
        
        videos = fetch_playlist_videos()
        
        if not videos:
            print("⚠️ No videos found in playlist")
            return {}
        
        mapping = {}
        unmapped = []
        
        for video in videos:
            title = video['title']
            video_id = video['id']
            
            result = parse_title_for_canto_chapter(title)
            
            if result:
                canto, chapter = result
                mapping[(canto, chapter)] = video_id
                print(f"  ✅ Mapped: Canto {canto}.{chapter} → {title[:50]}...")
            else:
                unmapped.append(title)
        
        print(f"\n📊 Mapping complete:")
        print(f"  ✅ Successfully mapped: {len(mapping)} videos")
        print(f"  ⚠️ Could not parse: {len(unmapped)} videos")
        
        if unmapped and len(unmapped) <= 10:
            print(f"\n⚠️ Unmapped titles:")
            for title in unmapped[:10]:
                print(f"    - {title}")
        
        return mapping
        
    except Exception as e:
        print(f"❌ Error building mapping: {e}")
        import traceback
        traceback.print_exc()
        return {}

# Global variable to store mappings
_VIDEO_MAPPING_CACHE = None

def get_video_mapping():
    """Get video mapping (cached)"""
    global _VIDEO_MAPPING_CACHE
    
    if _VIDEO_MAPPING_CACHE is None:
        _VIDEO_MAPPING_CACHE = build_video_mapping()
    
    return _VIDEO_MAPPING_CACHE

def is_devanagari(text):
    """Check if text contains Devanagari script"""
    return bool(re.search(r'[\u0900-\u097F]', text))

def fetch_from_vedabase(canto, chapter, verse, retry_count=0):
    """Fetch verse from vedabase.io with retry logic"""
    max_retries = 2
    
    try:
        url = f"https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/"
        print(f"🔍 Fetching (attempt {retry_count + 1}): {url}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            page.set_default_timeout(60000)
            
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                time.sleep(3)
            except PlaywrightTimeout:
                print("⚠️ Page load timeout")
                browser.close()
                
                if retry_count < max_retries:
                    print(f"🔄 Retrying... ({retry_count + 1}/{max_retries})")
                    time.sleep(2)
                    return fetch_from_vedabase(canto, chapter, verse, retry_count + 1)
                else:
                    return None
            
            full_text = page.inner_text('body')
            lines = full_text.split('\n')
            
            sb_idx = synonyms_idx = translation_idx = purport_idx = -1
            
            for i, line in enumerate(lines):
                line_lower = line.strip().lower()
                
                if re.match(r'[śŚ]b \d+\.\d+\.\d+', line.strip(), re.IGNORECASE):
                    sb_idx = i
                
                if line_lower == 'synonyms':
                    synonyms_idx = i
                
                if line_lower == 'translation':
                    translation_idx = i
                
                if line_lower == 'purport':
                    purport_idx = i
            
            devanagari_verse = ""
            sanskrit_verse = ""
            word_meanings = ""
            translation = ""
            purport = ""
            
            if sb_idx > 0 and synonyms_idx > 0:
                devanagari_lines = []
                verse_lines = []
                
                for i in range(sb_idx + 1, synonyms_idx):
                    line = lines[i].strip()
                    if line and not any(skip in line for skip in ['Default View', 'Dual Language', 'Advanced View']):
                        if is_devanagari(line):
                            devanagari_lines.append(line)
                        elif len(line) > 3:
                            verse_lines.append(line)
                
                devanagari_verse = '\n'.join(devanagari_lines)
                sanskrit_verse = '\n'.join(verse_lines)
            
            if synonyms_idx > 0 and translation_idx > 0:
                synonym_lines = []
                for i in range(synonyms_idx + 1, translation_idx):
                    line = lines[i].strip()
                    if line and len(line) > 3:
                        synonym_lines.append(line)
                word_meanings = ' '.join(synonym_lines)
            
            if translation_idx > 0 and purport_idx > 0:
                translation_lines = []
                for i in range(translation_idx + 1, purport_idx):
                    line = lines[i].strip()
                    if line and len(line) > 3:
                        translation_lines.append(line)
                translation = ' '.join(translation_lines)
            
            if purport_idx > 0:
                purport_lines = []
                for i in range(purport_idx + 1, len(lines)):
                    line = lines[i].strip()
                    
                    if any(stop in line for stop in ['Donate', 'Thanks to', 'His Divine Grace', '©', 'Content used with permission']):
                        break
                    
                    if re.match(r'^Text \d+$', line):
                        break
                    
                    if line and len(line) > 3:
                        purport_lines.append(line)
                
                purport = ' '.join(purport_lines)
            
            browser.close()
            
            print(f"✅ Extracted - Purport: {len(purport)} chars")
            
            return {
                'devanagari_verse': devanagari_verse.strip(),
                'sanskrit_verse': sanskrit_verse.strip(),
                'word_meanings': word_meanings.strip(),
                'translation': translation.strip(),
                'purport': purport.strip(),
                'source': 'vedabase.io (fetched)'
            }
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_from_database(canto, chapter, verse):
    """Get verse from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''SELECT devanagari_verse, sanskrit_verse, word_meanings, translation, purport
                     FROM verses WHERE canto=? AND chapter=? AND verse=?''',
                  (canto, chapter, verse))
        
        result = c.fetchone()
        conn.close()
        
        if result:
            return {
                'devanagari_verse': result[0] or "",
                'sanskrit_verse': result[1] or "",
                'word_meanings': result[2] or "",
                'translation': result[3] or "",
                'purport': result[4] or "",
                'source': 'database (cached)'
            }
        return None
            
    except Exception as e:
        print(f"❌ Database error: {e}")
        return None

def save_to_database(canto, chapter, verse, devanagari_verse, sanskrit_verse, word_meanings, translation, purport):
    """Save to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''INSERT OR REPLACE INTO verses 
                     (canto, chapter, verse, devanagari_verse, sanskrit_verse, word_meanings, translation, purport)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (canto, chapter, verse, devanagari_verse, sanskrit_verse, word_meanings, translation, purport))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Save error: {e}")
        return False

def fetch_verse_hybrid(canto, chapter, verse):
    """Hybrid approach"""
    verse_ref = f"SB {canto}.{chapter}.{verse}"
    
    db_result = get_from_database(canto, chapter, verse)
    if db_result:
        return {
            'success': True,
            'reference': verse_ref,
            **db_result,
            'url': f'https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/'
        }
    
    web_result = fetch_from_vedabase(canto, chapter, verse)
    if web_result:
        save_to_database(canto, chapter, verse, web_result['devanagari_verse'], 
                        web_result['sanskrit_verse'], web_result['word_meanings'],
                        web_result['translation'], web_result['purport'])
        
        return {
            'success': True,
            'reference': verse_ref,
            **web_result,
            'url': f'https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/'
        }
    
    return {
        'success': False,
        'error': f'Could not fetch verse {verse_ref}. Please try again.'
    }

# ==================== TRANSLATION FUNCTIONS ====================

def translate_with_libretranslate(text, source_lang='ta', target_lang='en'):
    """Translate using LibreTranslate"""
    try:
        print(f"🌐 LibreTranslate ({source_lang} → {target_lang})")
        
        url = "https://libretranslate.com/translate"
        
        payload = {
            "q": text[:5000],
            "source": source_lang,
            "target": target_lang,
            "format": "text"
        }
        
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            translation = result.get('translatedText', '')
            print(f"✅ LibreTranslate: {len(translation)} chars")
            return translation
        else:
            print(f"⚠️ LibreTranslate error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ LibreTranslate error: {e}")
        return None

def translate_with_mymemory(text, source_lang='ta', target_lang='en'):
    """Translate using MyMemory"""
    try:
        print(f"🌐 MyMemory ({source_lang} → {target_lang})")
        
        url = "https://api.mymemory.translated.net/get"
        
        lang_map = {
            'ta': 'ta-IN',
            'hi': 'hi-IN',
            'en': 'en-US'
        }
        
        source = lang_map.get(source_lang, source_lang)
        target = lang_map.get(target_lang, target_lang)
        
        chunks = [text[i:i+450] for i in range(0, len(text), 450)]
        translated_chunks = []
        
        for i, chunk in enumerate(chunks[:10]):
            params = {
                'q': chunk,
                'langpair': f'{source}|{target}'
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('responseStatus') == 200:
                    translated_text = result.get('responseData', {}).get('translatedText', '')
                    translated_chunks.append(translated_text)
                    time.sleep(0.5)
            else:
                break
        
        if translated_chunks:
            full_translation = ' '.join(translated_chunks)
            print(f"✅ MyMemory: {len(full_translation)} chars")
            return full_translation
        else:
            return None
            
    except Exception as e:
        print(f"❌ MyMemory error: {e}")
        return None

def translate_with_googletrans(text, source_lang='ta', target_lang='en'):
    """Translate using Google Translate"""
    try:
        print(f"🌐 Google Translate ({source_lang} → {target_lang})")
        
        from googletrans import Translator
        
        translator = Translator()
        
        max_chunk = 4000
        chunks = [text[i:i+max_chunk] for i in range(0, len(text), max_chunk)]
        translated_chunks = []
        
        for i, chunk in enumerate(chunks[:5]):
            result = translator.translate(chunk, src=source_lang, dest=target_lang)
            translated_chunks.append(result.text)
            time.sleep(0.5)
        
        full_translation = ' '.join(translated_chunks)
        print(f"✅ Google Translate: {len(full_translation)} chars")
        return full_translation
            
    except Exception as e:
        print(f"❌ Google Translate error: {e}")
        return None

def translate_text_cascade(text, source_lang='ta'):
    """Try multiple translation services"""
    
    print(f"\n🔄 Translation cascade for {len(text)} chars...")
    
    # Try LibreTranslate
    translation = translate_with_libretranslate(text, source_lang, 'en')
    if translation and len(translation) > 50:
        return translation
    
    # Try MyMemory
    print("⚠️ Trying MyMemory...")
    translation = translate_with_mymemory(text, source_lang, 'en')
    if translation and len(translation) > 50:
        return translation
    
    # Try Google Translate
    print("⚠️ Trying Google Translate...")
    translation = translate_with_googletrans(text, source_lang, 'en')
    if translation and len(translation) > 50:
        return translation
    
    print("❌ All translation services failed")
    return None

# ==================== YOUTUBE FUNCTIONS ====================

@app.route('/test_video/<video_id>', methods=['GET'])
def test_video(video_id):
    """Test endpoint to check if a video has transcripts"""
    try:
        print(f"\n🧪 Testing video: {video_id}")
        
        result = get_youtube_transcript(video_id)
        
        if result:
            return jsonify({
                'success': True,
                'video_id': video_id,
                'has_transcript': True,
                'language': result['language'],
                'text_length': len(result['text']),
                'preview': result['text'][:200]
            })
        else:
            return jsonify({
                'success': False,
                'video_id': video_id,
                'has_transcript': False,
                'error': 'No transcript available'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/test_mapping', methods=['GET'])
def test_mapping():
    """Test endpoint to see video mappings"""
    try:
        mapping = get_video_mapping()
        
        # Convert to serializable format
        mapping_list = [
            {
                'canto': c,
                'chapter': ch,
                'video_id': vid,
                'url': f'https://www.youtube.com/watch?v={vid}'
            }
            for (c, ch), vid in sorted(mapping.items())
        ]
        
        return jsonify({
            'success': True,
            'total_videos': len(mapping_list),
            'mappings': mapping_list[:50]  # First 50
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


def find_video_for_chapter(canto, chapter):
    """Find YouTube video ID for canto/chapter"""
    try:
        # Get auto-generated mapping
        mapping = get_video_mapping()
        
        video_id = mapping.get((canto, chapter))
        
        if video_id:
            print(f"✅ Found video for Canto {canto}, Chapter {chapter}: {video_id}")
            return video_id
        else:
            print(f"⚠️ No video found for Canto {canto}, Chapter {chapter}")
            print(f"   Available mappings: {list(mapping.keys())[:10]}")
            return None
            
    except Exception as e:
        print(f"❌ Error finding video: {e}")
        return None

def get_youtube_transcript(video_id):
    """Fetch YouTube transcript with detailed error handling"""
    try:
        print(f"📺 Fetching transcript for video: {video_id}")
        print(f"   URL: https://www.youtube.com/watch?v={video_id}")
        
        # List all available transcripts
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            print(f"✅ Found transcripts for video")
            
            # Show available languages
            available = []
            for transcript in transcript_list:
                lang_info = f"{transcript.language} ({transcript.language_code})"
                if transcript.is_generated:
                    lang_info += " [auto-generated]"
                available.append(lang_info)
            
            print(f"   Available transcripts: {', '.join(available)}")
            
        except Exception as e:
            print(f"❌ No transcripts available for this video: {e}")
            return None
        
        # Try to get transcript in preferred order
        transcript = None
        
        # Try manual transcripts first
        for lang in ['ta', 'hi', 'en', 'te', 'kn', 'ml']:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang])
                print(f"✅ Found manual transcript in: {lang}")
                break
            except:
                continue
        
        # Try auto-generated if manual not found
        if not transcript:
            for lang in ['ta', 'hi', 'en', 'te', 'kn', 'ml']:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    print(f"✅ Found auto-generated transcript in: {lang}")
                    break
                except:
                    continue
        
        if not transcript:
            print(f"❌ Could not find any usable transcript")
            return None
        
        # Fetch the transcript
        segments = transcript.fetch()
        full_text = ' '.join([segment['text'] for segment in segments])
        
        # Detect language
        try:
            lang_code = detect(full_text)
        except:
            lang_code = transcript.language_code
        
        print(f"✅ Transcript fetched: {len(full_text)} chars, language: {lang_code}")
        
        return {
            'text': full_text,
            'language': lang_code,
            'segments': segments
        }
        
    except Exception as e:
        print(f"❌ Transcript error: {e}")
        import traceback
        traceback.print_exc()
        return None


# def download_audio_from_youtube(video_id):
#     """Download audio from YouTube video"""
#     try:
#         print(f"🎵 Downloading audio for video: {video_id}")
        
#         output_path = f"/tmp/audio_{video_id}.mp3"
        
#         # Check if already downloaded
#         if os.path.exists(output_path):
#             print(f"✅ Audio already downloaded")
#             return output_path
        
#         video_url = f"https://www.youtube.com/watch?v={video_id}"
        
#         # Download audio using yt-dlp
#         cmd = [
#             'yt-dlp',
#             '-x',  # Extract audio
#             '--audio-format', 'mp3',
#             '--audio-quality', '0',  # Best quality
#             '-o', output_path,
#             video_url
#         ]
        
#         result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
#         if result.returncode == 0 and os.path.exists(output_path):
#             print(f"✅ Audio downloaded: {os.path.getsize(output_path) / (1024*1024):.2f} MB")
#             return output_path
#         else:
#             print(f"❌ Download failed: {result.stderr}")
#             return None
            
#     except Exception as e:
#         print(f"❌ Error downloading audio: {e}")
#         return None

def transcribe_audio_assemblyai(audio_path, language='ta'):
    """Transcribe audio using AssemblyAI"""
    try:
        if not ASSEMBLYAI_API_KEY:
            print("⚠️ AssemblyAI API key not configured")
            return None
        
        print(f"🎤 Transcribing audio with AssemblyAI (language: {language})...")
        
        # Language code mapping
        lang_map = {
            'ta': 'ta',  # Tamil
            'hi': 'hi',  # Hindi
            'te': 'te',  # Telugu
            'kn': 'kn',  # Kannada
            'ml': 'ml',  # Malayalam
            'en': 'en'   # English
        }
        
        lang_code = lang_map.get(language, 'ta')
        
        # Configure transcription
        config = aai.TranscriptionConfig(
            language_code=lang_code,
            punctuate=True,
            format_text=True
        )
        
        # Create transcriber
        transcriber = aai.Transcriber()
        
        # Transcribe
        transcript = transcriber.transcribe(audio_path, config=config)
        
        if transcript.status == aai.TranscriptStatus.error:
            print(f"❌ Transcription error: {transcript.error}")
            return None
        
        print(f"✅ Transcription complete: {len(transcript.text)} chars")
        
        return {
            'text': transcript.text,
            'language': lang_code,
            'confidence': transcript.confidence if hasattr(transcript, 'confidence') else None
        }
        
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        import traceback
        traceback.print_exc()
        return None

def transcribe_audio_deepgram(audio_path, language='ta'):
    """Transcribe audio using Deepgram (alternative)"""
    try:
        DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY', '')
        
        if not DEEPGRAM_API_KEY:
            print("⚠️ Deepgram API key not configured")
            return None
        
        print(f"🎤 Transcribing with Deepgram (language: {language})...")
        
        url = "https://api.deepgram.com/v1/listen"
        
        # Language mapping
        lang_map = {
            'ta': 'ta',
            'hi': 'hi',
            'te': 'te',
            'kn': 'kn',
            'ml': 'ml',
            'en': 'en-US'
        }
        
        headers = {
            'Authorization': f'Token {DEEPGRAM_API_KEY}',
            'Content-Type': 'audio/mp3'
        }
        
        params = {
            'language': lang_map.get(language, 'ta'),
            'punctuate': 'true',
            'model': 'general'
        }
        
        with open(audio_path, 'rb') as audio_file:
            response = requests.post(url, headers=headers, params=params, data=audio_file, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            transcript_text = result['results']['channels'][0]['alternatives'][0]['transcript']
            print(f"✅ Deepgram transcription: {len(transcript_text)} chars")
            
            return {
                'text': transcript_text,
                'language': language
            }
        else:
            print(f"❌ Deepgram error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Deepgram error: {e}")
        return None

# def get_or_create_transcript(video_id, language='ta'):
#     """Get transcript - try YouTube first, then generate from audio"""
#     try:
#         print(f"\n📝 Getting transcript for video: {video_id}")
        
#         # Try YouTube transcript first (fastest)
#         youtube_transcript = get_youtube_transcript(video_id)
        
#         if youtube_transcript:
#             print(f"✅ Found YouTube transcript")
#             return youtube_transcript
        
#         print(f"⚠️ No YouTube transcript - generating from audio...")
        
#         # Download audio
#         audio_path = download_audio_from_youtube(video_id)
        
#         if not audio_path:
#             return None
        
#         # Try AssemblyAI first
#         transcript = transcribe_audio_assemblyai(audio_path, language)
        
#         # Fallback to Deepgram if AssemblyAI fails
#         if not transcript:
#             print("⚠️ AssemblyAI failed, trying Deepgram...")
#             transcript = transcribe_audio_deepgram(audio_path, language)
        
#         # Clean up audio file
#         try:
#             os.remove(audio_path)
#             print(f"🗑️ Cleaned up audio file")
#         except:
#             pass
        
#         return transcript
        
#     except Exception as e:
#         print(f"❌ Error getting transcript: {e}")
#         return None


# def get_chapter_meaning(canto, chapter):
#     """Get chapter meaning from YouTube"""
#     try:
#         # Check database first
#         conn = sqlite3.connect(DB_PATH)
#         c = conn.cursor()
        
#         c.execute('''SELECT video_id, transcript, translation 
#                      FROM chapter_meanings 
#                      WHERE canto=? AND chapter=?''', (canto, chapter))
#         result = c.fetchone()
#         conn.close()
        
#         if result:
#             print(f"✅ Chapter meaning from database")
#             return {
#                 'success': True,
#                 'video_id': result[0],
#                 'transcript': result[1],
#                 'translation': result[2],
#                 'source': 'database (cached)'
#             }
        
#         # Get video mapping
#         video_id = find_video_for_chapter(canto, chapter)
        
#         if not video_id:
#             # Show available mappings for debugging
#             mapping = get_video_mapping()
#             available_cantos = sorted(set(c for c, ch in mapping.keys()))
            
#             return {
#                 'success': False,
#                 'error': f'No video found for Canto {canto}, Chapter {chapter}.\n\nAvailable Cantos in playlist: {available_cantos}\n\nPlease check if the video exists in the playlist.'
#             }
        
#         print(f"✅ Found video ID: {video_id}")
        
#         # Get transcript
#         transcript_data = get_youtube_transcript(video_id)
        
#         if not transcript_data:
#             return {
#                 'success': False,
#                 'error': f'Could not fetch transcript for video ID: {video_id}\n\nPossible reasons:\n1. Video does not have captions/transcripts enabled\n2. Video is private or unavailable\n3. Transcripts are disabled for this video\n\nVideo URL: https://www.youtube.com/watch?v={video_id}\n\nPlease check if the video has captions enabled on YouTube.'
#             }
        
#         original_text = transcript_data['text']
#         language = transcript_data['language']
        
#         print(f"📝 Original: {len(original_text)} chars, language: {language}")
        
#         # Translate if needed
#         translated_text = original_text
        
#         if language in ['ta', 'hi', 'te', 'kn', 'ml'] and language != 'en':
#             print(f"🔄 Translating from {language}...")
            
#             translated_text = translate_text_cascade(original_text, language)
            
#             if not translated_text:
#                 translated_text = f"[Translation failed - showing original text]\n\n{original_text}"
        
#         # Save to database
#         try:
#             conn = sqlite3.connect(DB_PATH)
#             c = conn.cursor()
#             c.execute('''INSERT OR REPLACE INTO chapter_meanings 
#                          (canto, chapter, video_id, transcript, translation) 
#                          VALUES (?, ?, ?, ?, ?)''',
#                       (canto, chapter, video_id, original_text, translated_text))
#             conn.commit()
#             conn.close()
#             print(f"💾 Saved to database")
#         except Exception as e:
#             print(f"⚠️ Database save error: {e}")
        
#         return {
#             'success': True,
#             'video_id': video_id,
#             'transcript': original_text,
#             'translation': translated_text,
#             'language': language,
#             'source': 'YouTube (fetched & translated)'
#         }
        
#     except Exception as e:
#         print(f"❌ Error: {e}")
#         import traceback
#         traceback.print_exc()
#         return {
#             'success': False,
#             'error': f'Error: {str(e)}\n\nPlease check Render logs for details.'
#         }

# def get_chapter_meaning(canto, chapter):
#     """Get chapter meaning from YouTube"""
#     try:
#         # Check database first
#         conn = sqlite3.connect(DB_PATH)
#         c = conn.cursor()
        
#         c.execute('''SELECT video_id, transcript, translation 
#                      FROM chapter_meanings 
#                      WHERE canto=? AND chapter=?''', (canto, chapter))
#         result = c.fetchone()
#         conn.close()
        
#         if result and result[1]:  # Has transcript
#             return {
#                 'success': True,
#                 'video_id': result[0],
#                 'transcript': result[1],
#                 'translation': result[2],
#                 'source': 'database (cached)'
#             }
        
#         # Get video ID
#         video_id = find_video_for_chapter(canto, chapter)
        
#         if not video_id:
#             return {
#                 'success': False,
#                 'error': f'No video found for Canto {canto}, Chapter {chapter}'
#             }
        
#         # Try to get transcript
#         transcript_data = get_youtube_transcript(video_id)
        
#         if not transcript_data:
#             # No transcript available - return video link anyway
#             return {
#                 'success': True,
#                 'video_id': video_id,
#                 'transcript': '',
#                 'translation': '',
#                 'no_transcript': True,
#                 'message': f'This video does not have captions/transcripts enabled on YouTube. You can still watch the video directly.',
#                 'source': 'YouTube (no transcript)'
#             }
        
#         # Has transcript - translate if needed
#         original_text = transcript_data['text']
#         language = transcript_data['language']
        
#         translated_text = original_text
        
#         if language in ['ta', 'hi', 'te', 'kn', 'ml'] and language != 'en':
#             translated_text = translate_text_cascade(original_text, language)
            
#             if not translated_text:
#                 translated_text = original_text
        
#         # Save to database
#         try:
#             conn = sqlite3.connect(DB_PATH)
#             c = conn.cursor()
#             c.execute('''INSERT OR REPLACE INTO chapter_meanings 
#                          (canto, chapter, video_id, transcript, translation) 
#                          VALUES (?, ?, ?, ?, ?)''',
#                       (canto, chapter, video_id, original_text, translated_text))
#             conn.commit()
#             conn.close()
#         except:
#             pass
        
#         return {
#             'success': True,
#             'video_id': video_id,
#             'transcript': original_text,
#             'translation': translated_text,
#             'language': language,
#             'source': 'YouTube (fetched & translated)'
#         }
        
#     except Exception as e:
#         print(f"❌ Error: {e}")
#         return {
#             'success': False,
#             'error': str(e)
#         }

def get_chapter_meaning(canto, chapter):
    """Get chapter meaning - generates transcript from audio if needed"""
    try:
        # Check database first
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''SELECT video_id, transcript, translation 
                     FROM chapter_meanings 
                     WHERE canto=? AND chapter=?''', (canto, chapter))
        result = c.fetchone()
        conn.close()
        
        if result and result[1]:
            print(f"✅ Chapter meaning from database")
            return {
                'success': True,
                'video_id': result[0],
                'transcript': result[1],
                'translation': result[2],
                'source': 'database (cached)'
            }
        
        # Get video ID
        video_id = find_video_for_chapter(canto, chapter)
        
        if not video_id:
            return {
                'success': False,
                'error': f'No video found for Canto {canto}, Chapter {chapter}'
            }
        
        print(f"✅ Found video: {video_id}")
        
        # Detect likely language from canto
        # (You can improve this by checking video title)
        likely_language = 'ta'  # Default to Tamil
        
        # Get or create transcript
        transcript_data = get_or_create_transcript(video_id, likely_language)
        
        if not transcript_data:
            return {
                'success': False,
                'error': f'Could not get or generate transcript for this video.\n\nVideo URL: https://www.youtube.com/watch?v={video_id}\n\nPossible reasons:\n1. Video is unavailable\n2. Audio quality is too poor\n3. API quota exceeded\n\nPlease try again later or watch the video directly.'
            }
        
        original_text = transcript_data['text']
        language = transcript_data['language']
        
        print(f"📝 Got transcript: {len(original_text)} chars, language: {language}")
        
        # Translate if needed
        translated_text = original_text
        
        if language in ['ta', 'hi', 'te', 'kn', 'ml'] and language != 'en':
            print(f"🔄 Translating from {language} to English...")
            
            translated_text = translate_text_cascade(original_text, language)
            
            if not translated_text:
                translated_text = original_text + "\n\n[Translation unavailable]"
        
        # Save to database
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO chapter_meanings 
                         (canto, chapter, video_id, transcript, translation) 
                         VALUES (?, ?, ?, ?, ?)''',
                      (canto, chapter, video_id, original_text, translated_text))
            conn.commit()
            conn.close()
            print(f"💾 Saved to database")
        except:
            pass
        
        return {
            'success': True,
            'video_id': video_id,
            'transcript': original_text,
            'translation': translated_text,
            'language': language,
            'source': 'Auto-transcribed from audio & translated'
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f'Error: {str(e)}'
        }


# ==================== ROUTES ====================

@app.before_request
def ensure_database():
    if not hasattr(app, '_database_initialized'):
        init_db()
        app._database_initialized = True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch_verse', methods=['POST'])
def get_verse():
    try:
        data = request.json
        canto = int(data.get('canto'))
        chapter = int(data.get('chapter'))
        verse = int(data.get('verse'))
        
        result = fetch_verse_hybrid(canto, chapter, verse)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/chapter_meaning', methods=['POST'])
# def get_chapter_meaning_route():
#     try:
#         data = request.json
#         canto = int(data.get('canto'))
#         chapter = int(data.get('chapter'))
        
#         result = get_chapter_meaning(canto, chapter)
#         return jsonify(result)
        
#     except Exception as e:
#         return jsonify({'success': False, 'error': str(e)})
def get_chapter_meaning(canto, chapter):
    """Get chapter meaning - generates transcript from audio if needed"""
    try:
        # Check database first
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''SELECT video_id, transcript, translation 
                     FROM chapter_meanings 
                     WHERE canto=? AND chapter=?''', (canto, chapter))
        result = c.fetchone()
        conn.close()
        
        if result and result[1]:
            print(f"✅ Chapter meaning from database")
            return {
                'success': True,
                'video_id': result[0],
                'transcript': result[1],
                'translation': result[2],
                'source': 'database (cached)'
            }
        
        # Get video ID
        video_id = find_video_for_chapter(canto, chapter)
        
        if not video_id:
            return {
                'success': False,
                'error': f'No video found for Canto {canto}, Chapter {chapter}'
            }
        
        print(f"✅ Found video: {video_id}")
        
        # Detect language (default to Tamil)
        likely_language = 'ta'
        
        # Get or create transcript
        transcript_data = get_or_create_transcript(video_id, likely_language)
        
        if not transcript_data:
            return {
                'success': False,
                'error': f'Could not transcribe audio. Video may be unavailable or too long.\n\nVideo URL: https://www.youtube.com/watch?v={video_id}'
            }
        
        original_text = transcript_data['text']
        language = transcript_data['language']
        
        print(f"📝 Transcript: {len(original_text)} chars, language: {language}")
        
        # Translate if needed
        translated_text = original_text
        
        if language in ['ta', 'hi', 'te', 'kn', 'ml'] and language != 'en':
            print(f"🔄 Translating to English...")
            
            translated_text = translate_text_cascade(original_text, language)
            
            if not translated_text:
                translated_text = original_text + "\n\n[Translation unavailable - showing original]"
        
        # Save to database
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO chapter_meanings 
                         (canto, chapter, video_id, transcript, translation) 
                         VALUES (?, ?, ?, ?, ?)''',
                      (canto, chapter, video_id, original_text, translated_text))
            conn.commit()
            conn.close()
            print(f"💾 Saved to database")
        except Exception as e:
            print(f"⚠️ Database save failed: {e}")
        
        return {
            'success': True,
            'video_id': video_id,
            'transcript': original_text,
            'translation': translated_text,
            'language': language,
            'source': 'Whisper AI (auto-transcribed) + translated'
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f'Error: {str(e)}'
        }


def download_audio_from_youtube(video_id):
    """Download audio from YouTube video"""
    try:
        print(f"🎵 Downloading audio for video: {video_id}")
        
        output_path = f"/tmp/audio_{video_id}.mp3"
        
        # Check if already downloaded
        if os.path.exists(output_path):
            print(f"✅ Audio already exists")
            return output_path
        
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Download audio using yt-dlp (best quality, small file)
        cmd = [
            'yt-dlp',
            '-x',  # Extract audio
            '--audio-format', 'mp3',
            '--audio-quality', '5',  # 128kbps (good quality, smaller file)
            '--postprocessor-args', '-ar 16000',  # 16kHz for Whisper
            '-o', output_path,
            video_url
        ]
        
        print("📥 Downloading audio (this may take 1-2 minutes)...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Audio downloaded: {file_size:.2f} MB")
            return output_path
        else:
            print(f"❌ Download failed: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Error downloading audio: {e}")
        return None

def transcribe_with_whisper(audio_path, language='ta'):
    """Transcribe audio using Whisper (completely free, no limits)"""
    try:
        print(f"🎤 Transcribing audio with Whisper...")
        
        # Load model
        model = load_whisper_model()
        
        # Language mapping
        lang_map = {
            'ta': 'tamil',
            'hi': 'hindi',
            'te': 'telugu',
            'kn': 'kannada',
            'ml': 'malayalam',
            'en': 'english'
        }
        
        whisper_lang = lang_map.get(language, 'tamil')
        
        # Transcribe
        print(f"   Language: {whisper_lang}")
        print(f"   This will take 2-5 minutes for a 30-minute video...")
        
        result = model.transcribe(
            audio_path,
            language=whisper_lang,
            fp16=False,  # Use FP32 for CPU compatibility
            verbose=False
        )
        
        transcript_text = result['text'].strip()
        
        print(f"✅ Transcription complete: {len(transcript_text)} chars")
        
        return {
            'text': transcript_text,
            'language': language
        }
        
    except Exception as e:
        print(f"❌ Whisper transcription error: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_or_create_transcript(video_id, language='ta'):
    """Get transcript - try YouTube first, then Whisper"""
    try:
        print(f"\n📝 Getting transcript for video: {video_id}")
        
        # Try YouTube transcript first (instant, free)
        youtube_transcript = get_youtube_transcript(video_id)
        
        if youtube_transcript:
            print(f"✅ Found YouTube transcript")
            return youtube_transcript
        
        print(f"⚠️ No YouTube transcript - generating with Whisper...")
        
        # Download audio
        audio_path = download_audio_from_youtube(video_id)
        
        if not audio_path:
            print("❌ Could not download audio")
            return None
        
        # Transcribe with Whisper
        transcript = transcribe_with_whisper(audio_path, language)
        
        # Clean up audio file
        try:
            os.remove(audio_path)
            print(f"🗑️ Cleaned up audio file")
        except:
            pass
        
        return transcript
        
    except Exception as e:
        print(f"❌ Error getting transcript: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5019))
    app.run(debug=False, host='0.0.0.0', port=port)