from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import sqlite3
import os
import time
import re
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from langdetect import detect

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



def find_video_for_chapter(canto, chapter):
    """Find YouTube video ID"""
    video_id = VIDEO_MAPPING.get((canto, chapter))
    
    if video_id:
        return video_id
    
    return None

def get_youtube_transcript(video_id):
    """Fetch YouTube transcript"""
    try:
        print(f"📺 Fetching transcript: {video_id}")
        
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        try:
            transcript = transcript_list.find_manually_created_transcript(['ta', 'hi', 'en'])
        except:
            transcript = transcript_list.find_generated_transcript(['ta', 'hi', 'en'])
        
        segments = transcript.fetch()
        full_text = ' '.join([segment['text'] for segment in segments])
        
        try:
            lang_code = detect(full_text)
        except:
            lang_code = 'en'
        
        print(f"✅ Transcript: {len(full_text)} chars, language: {lang_code}")
        
        return {
            'text': full_text,
            'language': lang_code,
            'segments': segments
        }
        
    except Exception as e:
        print(f"❌ Transcript error: {e}")
        return None

def get_chapter_meaning(canto, chapter):
    """Get chapter meaning from YouTube"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''SELECT video_id, transcript, translation 
                     FROM chapter_meanings 
                     WHERE canto=? AND chapter=?''', (canto, chapter))
        result = c.fetchone()
        conn.close()
        
        if result:
            return {
                'success': True,
                'video_id': result[0],
                'transcript': result[1],
                'translation': result[2],
                'source': 'database (cached)'
            }
        
        video_id = find_video_for_chapter(canto, chapter)
        
        if not video_id:
            return {
                'success': False,
                'error': f'No video found for Canto {canto}, Chapter {chapter}'
            }
        
        transcript_data = get_youtube_transcript(video_id)
        
        if not transcript_data:
            return {
                'success': False,
                'error': 'Could not fetch transcript'
            }
        
        original_text = transcript_data['text']
        language = transcript_data['language']
        
        translated_text = original_text
        
        if language in ['ta', 'hi', 'te', 'kn', 'ml'] and language != 'en':
            translated_text = translate_text_cascade(original_text, language)
            
            if not translated_text:
                translated_text = f"[Translation failed]\n\n{original_text}"
        
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO chapter_meanings 
                         (canto, chapter, video_id, transcript, translation) 
                         VALUES (?, ?, ?, ?, ?)''',
                      (canto, chapter, video_id, original_text, translated_text))
            conn.commit()
            conn.close()
        except:
            pass
        
        return {
            'success': True,
            'video_id': video_id,
            'transcript': original_text,
            'translation': translated_text,
            'language': language,
            'source': 'YouTube (fetched & translated)'
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            'success': False,
            'error': str(e)
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
def get_chapter_meaning_route():
    try:
        data = request.json
        canto = int(data.get('canto'))
        chapter = int(data.get('chapter'))
        
        result = get_chapter_meaning(canto, chapter)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5019))
    app.run(debug=False, host='0.0.0.0', port=port)