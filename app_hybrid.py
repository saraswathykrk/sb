from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import sqlite3
import os
import time
import re
import requests
import json
import subprocess
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__)
DB_PATH = '/tmp/srimad_bhagavatam.db'
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLyepYeJqc4uE3d3CHZbUP9eS6jI471qbK"
MAPPING_CACHE_FILE = '/tmp/video_mappings.json'

def init_db():
    """Initialize database"""
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
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database init error: {e}")

def is_devanagari(text):
    """Check if text contains Devanagari script"""
    return bool(re.search(r'[\u0900-\u097F]', text))

# def fetch_from_vedabase(canto, chapter, verse, retry_count=0):
#     """Fetch verse from vedabase.io"""
#     max_retries = 2
    
#     try:
#         url = f"https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/"
#         print(f"🔍 Fetching: {url}")
        
#         with sync_playwright() as p:
#             browser = p.chromium.launch(headless=True)
#             context = browser.new_context(
#                 user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
#             )
#             page = context.new_page()
#             page.set_default_timeout(60000)
            
#             try:
#                 page.goto(url, wait_until='domcontentloaded', timeout=60000)
#                 time.sleep(3)
#             except PlaywrightTimeout:
#                 browser.close()
#                 if retry_count < max_retries:
#                     time.sleep(2)
#                     return fetch_from_vedabase(canto, chapter, verse, retry_count + 1)
#                 else:
#                     return None
            
#             full_text = page.inner_text('body')
#             lines = full_text.split('\n')
            
#             sb_idx = synonyms_idx = translation_idx = purport_idx = -1
            
#             for i, line in enumerate(lines):
#                 line_lower = line.strip().lower()
#                 if re.match(r'[śŚ]b \d+\.\d+\.\d+', line.strip(), re.IGNORECASE):
#                     sb_idx = i
#                 if line_lower == 'synonyms':
#                     synonyms_idx = i
#                 if line_lower == 'translation':
#                     translation_idx = i
#                 if line_lower == 'purport':
#                     purport_idx = i
            
#             devanagari_verse = ""
#             sanskrit_verse = ""
#             word_meanings = ""
#             translation = ""
#             purport = ""
            
#             if sb_idx > 0 and synonyms_idx > 0:
#                 devanagari_lines = []
#                 verse_lines = []
                
#                 for i in range(sb_idx + 1, synonyms_idx):
#                     line = lines[i].strip()
#                     if line and not any(skip in line for skip in ['Default View', 'Dual Language']):
#                         if is_devanagari(line):
#                             devanagari_lines.append(line)
#                         elif len(line) > 3:
#                             verse_lines.append(line)
                
#                 devanagari_verse = '\n'.join(devanagari_lines)
#                 sanskrit_verse = '\n'.join(verse_lines)
            
#             if synonyms_idx > 0 and translation_idx > 0:
#                 synonym_lines = []
#                 for i in range(synonyms_idx + 1, translation_idx):
#                     line = lines[i].strip()
#                     if line and len(line) > 3:
#                         synonym_lines.append(line)
#                 word_meanings = ' '.join(synonym_lines)
            
#             if translation_idx > 0 and purport_idx > 0:
#                 translation_lines = []
#                 for i in range(translation_idx + 1, purport_idx):
#                     line = lines[i].strip()
#                     if line and len(line) > 3:
#                         translation_lines.append(line)
#                 translation = ' '.join(translation_lines)
            
#             if purport_idx > 0:
#                 purport_lines = []
#                 for i in range(purport_idx + 1, len(lines)):
#                     line = lines[i].strip()
#                     if any(stop in line for stop in ['Donate', 'Thanks to', 'His Divine Grace', '©']):
#                         break
#                     if re.match(r'^Text \d+$', line):
#                         break
#                     if line and len(line) > 3:
#                         purport_lines.append(line)
#                 purport = ' '.join(purport_lines)
            
#             browser.close()
            
#             return {
#                 'devanagari_verse': devanagari_verse.strip(),
#                 'sanskrit_verse': sanskrit_verse.strip(),
#                 'word_meanings': word_meanings.strip(),
#                 'translation': translation.strip(),
#                 'purport': purport.strip(),
#                 'source': 'vedabase.io (fetched)'
#             }
            
#     except Exception as e:
#         print(f"❌ Error: {e}")
#         return None

def fetch_from_vedabase(canto, chapter, verse, retry_count=0):
    """Fetch verse from vedabase.io with better error handling"""
    max_retries = 3  # Increased from 2
    
    try:
        url = f"https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/"
        print(f"🔍 Fetching (attempt {retry_count + 1}/{max_retries + 1}): {url}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            page.set_default_timeout(90000)  # Increased to 90 seconds
            
            try:
                # Navigate with longer timeout
                page.goto(url, wait_until='domcontentloaded', timeout=90000)
                time.sleep(4)  # Increased wait time
                
            except PlaywrightTimeout:
                print("⚠️ Page load timeout")
                browser.close()
                
                if retry_count < max_retries:
                    print(f"🔄 Retrying... ({retry_count + 1}/{max_retries})")
                    time.sleep(3)
                    return fetch_from_vedabase(canto, chapter, verse, retry_count + 1)
                else:
                    return None
            except Exception as e:
                print(f"⚠️ Navigation error: {e}")
                browser.close()
                
                if retry_count < max_retries:
                    time.sleep(3)
                    return fetch_from_vedabase(canto, chapter, verse, retry_count + 1)
                else:
                    return None
            
            # Rest of the extraction code stays the same
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
                    if line and not any(skip in line for skip in ['Default View', 'Dual Language']):
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
                    if any(stop in line for stop in ['Donate', 'Thanks to', 'His Divine Grace', '©']):
                        break
                    if re.match(r'^Text \d+$', line):
                        break
                    if line and len(line) > 3:
                        purport_lines.append(line)
                purport = ' '.join(purport_lines)
            
            browser.close()
            
            print(f"✅ Extracted successfully")
            
            return {
                'devanagari_verse': devanagari_verse.strip(),
                'sanskrit_verse': sanskrit_verse.strip(),
                'word_meanings': word_meanings.strip(),
                'translation': translation.strip(),
                'purport': purport.strip(),
                'source': 'vedabase.io (fetched)'
            }
            
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        
        if retry_count < max_retries:
            print(f"🔄 Retrying due to error...")
            time.sleep(3)
            return fetch_from_vedabase(canto, chapter, verse, retry_count + 1)
        
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
    except:
        return False

# def fetch_verse_hybrid(canto, chapter, verse):
#     """Hybrid approach"""
#     verse_ref = f"SB {canto}.{chapter}.{verse}"
    
#     db_result = get_from_database(canto, chapter, verse)
#     if db_result:
#         return {
#             'success': True,
#             'reference': verse_ref,
#             **db_result,
#             'url': f'https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/'
#         }
    
#     web_result = fetch_from_vedabase(canto, chapter, verse)
#     if web_result:
#         save_to_database(canto, chapter, verse, web_result['devanagari_verse'], 
#                         web_result['sanskrit_verse'], web_result['word_meanings'],
#                         web_result['translation'], web_result['purport'])
        
#         return {
#             'success': True,
#             'reference': verse_ref,
#             **web_result,
#             'url': f'https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/'
#         }
    
#     return {
#         'success': False,
#         'error': f'Could not fetch verse {verse_ref}'
#     }

def fetch_verse_hybrid(canto, chapter, verse):
    """Hybrid approach - optimized"""
    verse_ref = f"SB {canto}.{chapter}.{verse}"
    
    print(f"\n📥 Request: {verse_ref}")
    
    # Check database first (fast path)
    db_result = get_from_database(canto, chapter, verse)
    if db_result:
        print(f"✅ Found in database (instant)")
        return {
            'success': True,
            'reference': verse_ref,
            **db_result,
            'url': f'https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/'
        }
    
    # Fetch from web (slow path)
    print(f"⏳ Not in database, fetching from web (30-60 seconds)...")
    web_result = fetch_from_vedabase(canto, chapter, verse)
    
    if web_result:
        # Save to database for next time
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
        'error': f'Could not fetch verse {verse_ref}. The site may be slow. Please try again in a moment.'
    }

# YouTube functions
_VIDEO_MAPPING_CACHE = None

def build_video_mapping():
    """Build video mapping with detailed logging"""
    try:
        # Check cache
        if os.path.exists(MAPPING_CACHE_FILE):
            try:
                with open(MAPPING_CACHE_FILE, 'r') as f:
                    cached = json.load(f)
                    if time.time() - cached.get('timestamp', 0) < 7 * 24 * 3600:
                        mapping = {}
                        for key_str, video_id in cached.get('mapping', {}).items():
                            canto, chapter = key_str.strip('()').split(',')
                            mapping[(int(canto.strip()), int(chapter.strip()))] = video_id
                        print(f"✅ Loaded {len(mapping)} videos from cache")
                        return mapping
            except Exception as e:
                print(f"⚠️ Cache load error: {e}")
        
        # Don't test version - just try to use it
        print("📺 Fetching playlist (skipping version test)...")
        
        cmd = ['yt-dlp', '--dump-json', '--flat-playlist', '--skip-download', PLAYLIST_URL]
        
        print(f"   Command: {' '.join(cmd)}")
        
        # Increase timeout to 180 seconds
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        print(f"   Return code: {result.returncode}")
        print(f"   Stdout length: {len(result.stdout)} chars")
        
        if result.stderr:
            print(f"   Stderr: {result.stderr[:200]}")
        
        if result.returncode != 0:
            print(f"❌ yt-dlp failed")
            return {}
        
        if not result.stdout.strip():
            print(f"❌ Empty output")
            return {}
        
        # Parse with Tamil pattern
        print("📝 Parsing video data...")
        mapping = {}
        line_count = 0
        
        for line in result.stdout.strip().split('\n'):
            line_count += 1
            if not line.strip():
                continue
                
            try:
                video_data = json.loads(line)
                video_id = video_data.get('id')
                title = video_data.get('title', '')
                
                if line_count <= 10:
                    print(f"  Title {line_count}: {title}")
                
                if not video_id or not title:
                    continue
                
                title_lower = title.lower()
                
                # Try Tamil pattern first
                patterns = [
                    r'skandam\s*(\d+)\s*adhyaayam\s*(\d+)',
                    r'sb\s*(\d+)\.(\d+)',
                    r'canto\s*(\d+)\s*chapter\s*(\d+)',
                    r'(\d+)\.(\d+)',
                ]
                
                matched = False
                for pattern in patterns:
                    match = re.search(pattern, title_lower)
                    if match:
                        canto = int(match.group(1))
                        chapter = int(match.group(2))
                        
                        if 1 <= canto <= 12:
                            mapping[(canto, chapter)] = video_id
                            if line_count <= 10:
                                print(f"    ✅ Canto {canto}.{chapter}")
                            matched = True
                            break
                
                if not matched and line_count <= 10:
                    print(f"    ❌ No match")
                    
            except Exception as e:
                if line_count <= 10:
                    print(f"⚠️ Parse error: {e}")
        
        print(f"\n📊 Total: {line_count} lines, {len(mapping)} mapped")
        
        # Save cache
        if len(mapping) > 0:
            try:
                cache_data = {
                    'timestamp': time.time(),
                    'mapping': {f"({c},{ch})": vid for (c, ch), vid in mapping.items()}
                }
                with open(MAPPING_CACHE_FILE, 'w') as f:
                    json.dump(cache_data, f)
                print(f"💾 Cached {len(mapping)} videos")
            except Exception as e:
                print(f"⚠️ Cache save error: {e}")
        
        return mapping
        
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout after 180 seconds")
        return {}
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {}

@app.route('/debug/mapping', methods=['GET'])
def debug_mapping():
    """Debug endpoint to see video mappings"""
    try:
        mapping = get_video_mapping()
        
        # Convert to readable format
        mapping_list = []
        for (canto, chapter), video_id in sorted(mapping.items()):
            mapping_list.append({
                'canto': canto,
                'chapter': chapter,
                'video_id': video_id,
                'url': f'https://www.youtube.com/watch?v={video_id}'
            })
        
        return jsonify({
            'success': True,
            'total': len(mapping_list),
            'has_3_1': (3, 1) in mapping,
            'mappings': mapping_list
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })

@app.route('/debug/clear_cache', methods=['GET'])
def clear_cache():
    """Clear the video mapping cache"""
    try:
        global _VIDEO_MAPPING_CACHE
        _VIDEO_MAPPING_CACHE = None
        
        if os.path.exists(MAPPING_CACHE_FILE):
            os.remove(MAPPING_CACHE_FILE)
            return jsonify({'success': True, 'message': 'Cache cleared. Refresh to rebuild.'})
        else:
            return jsonify({'success': True, 'message': 'No cache file found.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
        
              
# def get_video_mapping():
#     """Get cached mapping"""
#     global _VIDEO_MAPPING_CACHE
#     if _VIDEO_MAPPING_CACHE is None:
#         raw_mapping = build_video_mapping()
#         _VIDEO_MAPPING_CACHE = {(int(k.split(',')[0].strip('() ')), int(k.split(',')[1].strip('() '))): v 
#                                 for k, v in raw_mapping.items() if isinstance(k, str)} if isinstance(raw_mapping, dict) else raw_mapping
#     return _VIDEO_MAPPING_CACHE

def get_video_mapping():
    """Get cached mapping"""
    global _VIDEO_MAPPING_CACHE
    if _VIDEO_MAPPING_CACHE is None:
        _VIDEO_MAPPING_CACHE = build_video_mapping()
    return _VIDEO_MAPPING_CACHE

# def get_chapter_meaning(canto, chapter):
#     """Simple chapter meaning"""
#     try:
#         # Check database
#         conn = sqlite3.connect(DB_PATH)
#         c = conn.cursor()
#         c.execute('''SELECT video_id, transcript, translation 
#                      FROM chapter_meanings WHERE canto=? AND chapter=?''', (canto, chapter))
#         result = c.fetchone()
#         conn.close()
        
#         if result and result[1]:
#             return {
#                 'success': True,
#                 'video_id': result[0],
#                 'transcript': result[1],
#                 'translation': result[2],
#                 'source': 'database'
#             }
        
#         # Get video ID
#         mapping = get_video_mapping()
#         video_id = mapping.get((int(canto), int(chapter)))
        
#         if not video_id:
#             return {
#                 'success': False,
#                 'error': f'No video found for Canto {canto}, Chapter {chapter}'
#             }
        
#         # Return video info without transcript for now
#         return {
#             'success': True,
#             'video_id': video_id,
#             'transcript': '',
#             'translation': '',
#             'no_transcript': True,
#             'message': 'Video found! Transcript feature coming soon. Watch on YouTube:',
#             'source': 'YouTube'
#         }
        
#     except Exception as e:
#         print(f"❌ Chapter meaning error: {e}")
#         import traceback
#         traceback.print_exc()
#         return {
#             'success': False,
#             'error': str(e)
#         }


def get_chapter_meaning(canto, chapter):
    """Get chapter meaning with full transcript and translation support"""
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
        mapping = get_video_mapping()
        video_id = mapping.get((int(canto), int(chapter)))
        
        if not video_id:
            print(f"⚠️ No video found for Canto {canto}, Chapter {chapter}")
            return {
                'success': False,
                'error': f'No video found for Canto {canto}, Chapter {chapter}'
            }
        
        print(f"✅ Found video: {video_id}")
        
        # Try to get YouTube transcript
        transcript_data = get_youtube_transcript(video_id)
        
        if not transcript_data:
            # No transcript available
            return {
                'success': True,
                'video_id': video_id,
                'transcript': '',
                'translation': '',
                'no_transcript': True,
                'message': 'This video does not have captions/transcripts available on YouTube. Please watch the video directly.',
                'source': 'YouTube (no transcript)'
            }
        
        original_text = transcript_data['text']
        language = transcript_data['language']
        
        print(f"📝 Transcript: {len(original_text)} chars, language: {language}")
        
        # Translate if needed
        translated_text = original_text
        
        if language in ['ta', 'hi', 'te', 'kn', 'ml'] and language != 'en':
            print(f"🔄 Translating from {language} to English...")
            
            translated_text = translate_text_cascade(original_text, language)
            
            if not translated_text:
                translated_text = f"[Translation failed - showing original]\n\n{original_text}"
                print(f"⚠️ Translation failed, using original")
        
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
            'source': 'YouTube transcript (with translation)'
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f'Error: {str(e)}'
        }


# ==================== TRANSLATION FUNCTIONS ====================

def translate_with_libretranslate(text, source_lang='ta', target_lang='en'):
    """Translate using LibreTranslate (free, open source)"""
    try:
        print(f"🌐 Translating with LibreTranslate ({source_lang} → {target_lang})")
        
        url = "https://libretranslate.com/translate"
        
        payload = {
            "q": text[:5000],  # Limit to 5000 chars
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
    """Translate using MyMemory (free 1000 requests/day)"""
    try:
        print(f"🌐 Translating with MyMemory ({source_lang} → {target_lang})")
        
        url = "https://api.mymemory.translated.net/get"
        
        lang_map = {
            'ta': 'ta-IN',
            'hi': 'hi-IN',
            'en': 'en-US'
        }
        
        source = lang_map.get(source_lang, source_lang)
        target = lang_map.get(target_lang, target_lang)
        
        # Split text into chunks (MyMemory has 500 char limit per request)
        chunks = [text[i:i+450] for i in range(0, len(text), 450)]
        translated_chunks = []
        
        for i, chunk in enumerate(chunks[:10]):  # Limit to 10 chunks
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
                    time.sleep(0.5)  # Rate limiting
                else:
                    break
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
    """Translate using unofficial Google Translate API"""
    try:
        print(f"🌐 Translating with Google Translate ({source_lang} → {target_lang})")
        
        from googletrans import Translator
        
        translator = Translator()
        
        # Split into chunks
        max_chunk = 4000
        chunks = [text[i:i+max_chunk] for i in range(0, len(text), max_chunk)]
        translated_chunks = []
        
        for i, chunk in enumerate(chunks[:5]):  # Limit to 5 chunks
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
    """Try multiple translation services in order"""
    
    print(f"\n🔄 Starting translation cascade for {len(text)} chars...")
    
    # Try LibreTranslate first
    translation = translate_with_libretranslate(text, source_lang, 'en')
    if translation and len(translation) > 50:
        return translation
    
    # Try MyMemory second
    print("⚠️ LibreTranslate failed, trying MyMemory...")
    translation = translate_with_mymemory(text, source_lang, 'en')
    if translation and len(translation) > 50:
        return translation
    
    # Try Google Translate as last resort
    print("⚠️ MyMemory failed, trying Google Translate...")
    translation = translate_with_googletrans(text, source_lang, 'en')
    if translation and len(translation) > 50:
        return translation
    
    print("❌ All translation services failed")
    return None

# ==================== YOUTUBE TRANSCRIPT ====================

# def get_youtube_transcript(video_id):
#     """Fetch transcript from YouTube with detailed error handling"""
#     try:
#         print(f"📺 Fetching transcript for video: {video_id}")
        
#         from langdetect import detect
        
#         # List all available transcripts
#         try:
#             transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
#             print(f"✅ Found transcripts for video")
            
#             # Show available languages
#             available = []
#             for transcript in transcript_list:
#                 lang_info = f"{transcript.language} ({transcript.language_code})"
#                 if transcript.is_generated:
#                     lang_info += " [auto]"
#                 available.append(lang_info)
            
#             print(f"   Available: {', '.join(available)}")
            
#         except Exception as e:
#             print(f"❌ No transcripts available: {e}")
#             return None
        
#         # Try to get transcript
#         transcript = None
        
#         # Try manual transcripts first
#         for lang in ['ta', 'hi', 'en', 'te', 'kn', 'ml']:
#             try:
#                 transcript = transcript_list.find_manually_created_transcript([lang])
#                 print(f"✅ Found manual transcript in: {lang}")
#                 break
#             except:
#                 continue
        
#         # Try auto-generated if manual not found
#         if not transcript:
#             for lang in ['ta', 'hi', 'en', 'te', 'kn', 'ml']:
#                 try:
#                     transcript = transcript_list.find_generated_transcript([lang])
#                     print(f"✅ Found auto transcript in: {lang}")
#                     break
#                 except:
#                     continue
        
#         if not transcript:
#             print(f"❌ Could not find any usable transcript")
#             return None
        
#         # Fetch the transcript
#         segments = transcript.fetch()
#         full_text = ' '.join([segment['text'] for segment in segments])
        
#         # Detect language
#         try:
#             lang_code = detect(full_text)
#         except:
#             lang_code = transcript.language_code
        
#         print(f"✅ Transcript fetched: {len(full_text)} chars, language: {lang_code}")
        
#         return {
#             'text': full_text,
#             'language': lang_code,
#             'segments': segments
#         }
        
#     except Exception as e:
#         print(f"❌ Transcript error: {e}")
#         import traceback
#         traceback.print_exc()
#         return None

# def get_youtube_transcript(video_id):
#     """Fetch transcript from YouTube - improved version"""
#     try:
#         print(f"📺 Fetching transcript for: {video_id}")
#         print(f"   URL: https://www.youtube.com/watch?v={video_id}")
        
#         from langdetect import detect
        
#         # Get all available transcripts
#         transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
#         print(f"✅ Transcripts available for video")
        
#         # List all available transcripts
#         all_transcripts = []
#         for t in transcript_list:
#             info = f"{t.language} ({t.language_code})"
#             if t.is_generated:
#                 info += " [auto-generated]"
#             else:
#                 info += " [manual]"
#             all_transcripts.append(info)
#             print(f"   - {info}")
        
#         # Priority order: manual Tamil > auto Tamil > manual Hindi > auto Hindi > any
#         transcript = None
        
#         # Try manual Tamil first
#         try:
#             transcript = transcript_list.find_manually_created_transcript(['ta'])
#             print(f"✅ Using manual Tamil transcript")
#         except:
#             pass
        
#         # Try auto-generated Tamil
#         if not transcript:
#             try:
#                 transcript = transcript_list.find_generated_transcript(['ta'])
#                 print(f"✅ Using auto-generated Tamil transcript")
#             except:
#                 pass
        
#         # Try Hindi
#         if not transcript:
#             try:
#                 transcript = transcript_list.find_transcript(['hi'])
#                 print(f"✅ Using Hindi transcript")
#             except:
#                 pass
        
#         # Try English
#         if not transcript:
#             try:
#                 transcript = transcript_list.find_transcript(['en'])
#                 print(f"✅ Using English transcript")
#             except:
#                 pass
        
#         # Try ANY available transcript
#         if not transcript:
#             try:
#                 available = list(transcript_list)
#                 if available:
#                     transcript = available[0]
#                     print(f"✅ Using first available: {transcript.language_code}")
#             except:
#                 pass
        
#         if not transcript:
#             print(f"❌ No usable transcript found")
#             return None
        
#         # Fetch transcript content
#         print(f"📥 Downloading transcript...")
#         segments = transcript.fetch()
        
#         if not segments:
#             print(f"❌ Transcript is empty")
#             return None
        
#         # Combine all text
#         full_text = ' '.join([seg['text'].strip() for seg in segments if seg.get('text')])
        
#         if not full_text or len(full_text) < 10:
#             print(f"❌ Transcript too short: {len(full_text)} chars")
#             return None
        
#         # Detect language
#         try:
#             detected_lang = detect(full_text[:500])  # Use first 500 chars for detection
#             print(f"🔍 Detected language: {detected_lang}")
#         except:
#             detected_lang = transcript.language_code
        
#         print(f"✅ Transcript success: {len(full_text)} chars, {len(segments)} segments")
        
#         return {
#             'text': full_text,
#             'language': detected_lang,
#             'segments': segments,
#             'language_name': transcript.language
#         }
        
#     except Exception as e:
#         print(f"❌ Transcript error: {type(e).__name__}: {e}")
#         import traceback
#         traceback.print_exc()
#         return None


# def get_youtube_transcript(video_id):
#     """Fetch transcript from YouTube - multiple methods"""
#     try:
#         print(f"📺 Fetching transcript for: {video_id}")
#         print(f"   URL: https://www.youtube.com/watch?v={video_id}")
        
#         from langdetect import detect
        
#         # Method 1: Try standard API
#         try:
#             transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
#             print(f"✅ Found transcript list")
            
#             # Try to get ANY available transcript
#             transcript = None
#             for t in transcript_list:
#                 try:
#                     print(f"   Trying: {t.language} ({t.language_code})")
#                     transcript = t
#                     break
#                 except:
#                     continue
            
#             if transcript:
#                 segments = transcript.fetch()
#                 full_text = ' '.join([seg['text'].strip() for seg in segments if seg.get('text')])
                
#                 if full_text and len(full_text) > 10:
#                     try:
#                         detected_lang = detect(full_text[:500])
#                     except:
#                         detected_lang = transcript.language_code
                    
#                     print(f"✅ Method 1 success: {len(full_text)} chars")
                    
#                     return {
#                         'text': full_text,
#                         'language': detected_lang,
#                         'segments': segments
#                     }
#         except Exception as e:
#             print(f"⚠️ Method 1 failed: {e}")
        
#         # Method 2: Try without language preference
#         try:
#             print(f"   Trying Method 2: Direct fetch...")
#             transcript = YouTubeTranscriptApi.get_transcript(video_id)
            
#             if transcript:
#                 full_text = ' '.join([seg['text'].strip() for seg in transcript if seg.get('text')])
                
#                 if full_text and len(full_text) > 10:
#                     try:
#                         detected_lang = detect(full_text[:500])
#                     except:
#                         detected_lang = 'ta'
                    
#                     print(f"✅ Method 2 success: {len(full_text)} chars")
                    
#                     return {
#                         'text': full_text,
#                         'language': detected_lang,
#                         'segments': transcript
#                     }
#         except Exception as e:
#             print(f"⚠️ Method 2 failed: {e}")
        
#         # Method 3: Try with specific language codes
#         for lang_code in ['ta', 'hi', 'en', 'ta-IN', 'hi-IN', 'en-US']:
#             try:
#                 print(f"   Trying Method 3 with lang: {lang_code}...")
#                 transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang_code])
                
#                 if transcript:
#                     full_text = ' '.join([seg['text'].strip() for seg in transcript if seg.get('text')])
                    
#                     if full_text and len(full_text) > 10:
#                         try:
#                             detected_lang = detect(full_text[:500])
#                         except:
#                             detected_lang = lang_code[:2]
                        
#                         print(f"✅ Method 3 success ({lang_code}): {len(full_text)} chars")
                        
#                         return {
#                             'text': full_text,
#                             'language': detected_lang,
#                             'segments': transcript
#                         }
#             except:
#                 continue
        
#         print(f"❌ All methods failed for video: {video_id}")
#         return None
        
#     except Exception as e:
#         print(f"❌ Transcript error: {type(e).__name__}: {e}")
#         return None

# def get_youtube_transcript(video_id):
#     """Fetch transcript from YouTube - multiple methods"""
#     try:
#         print(f"📺 Fetching transcript for: {video_id}")
        
#         from langdetect import detect
        
#         # Method 1: Try yt-dlp (BEST for extracting subtitles)
#         print(f"   Method 1: yt-dlp subtitle extraction...")
#         result = get_youtube_transcript_ytdlp(video_id)
#         if result:
#             return result
        
#         # Method 2: Try youtube-transcript-api
#         try:
#             print(f"   Method 2: youtube-transcript-api...")
#             transcript = YouTubeTranscriptApi.get_transcript(video_id)
            
#             if transcript:
#                 full_text = ' '.join([seg['text'].strip() for seg in transcript if seg.get('text')])
                
#                 if full_text and len(full_text) > 10:
#                     try:
#                         detected_lang = detect(full_text[:500])
#                     except:
#                         detected_lang = 'ta'
                    
#                     print(f"✅ Method 2 success: {len(full_text)} chars")
                    
#                     return {
#                         'text': full_text,
#                         'language': detected_lang,
#                         'segments': transcript
#                     }
#         except Exception as e:
#             print(f"⚠️ Method 2 failed: {type(e).__name__}")
        
#         # Method 3: Try with language codes
#         for lang_code in ['ta', 'hi', 'en']:
#             try:
#                 print(f"   Method 3: Trying lang {lang_code}...")
#                 transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang_code])
                
#                 if transcript:
#                     full_text = ' '.join([seg['text'].strip() for seg in transcript if seg.get('text')])
                    
#                     if full_text and len(full_text) > 10:
#                         try:
#                             detected_lang = detect(full_text[:500])
#                         except:
#                             detected_lang = lang_code
                        
#                         print(f"✅ Method 3 success: {len(full_text)} chars")
                        
#                         return {
#                             'text': full_text,
#                             'language': detected_lang,
#                             'segments': transcript
#                         }
#             except:
#                 continue
        
#         # Method 4: Direct HTML scraping
#         print(f"   Method 4: Direct HTML scraping...")
#         result = get_youtube_transcript_direct(video_id)
#         if result:
#             return result
        
#         print(f"❌ All methods failed for video: {video_id}")
#         return None
        
#     except Exception as e:
#         print(f"❌ Transcript error: {e}")
#         return None

# def get_youtube_transcript(video_id):
#     """Main transcript fetching function"""
#     return extract_subtitles_comprehensive(video_id)

# def get_youtube_transcript(video_id):
#     """Fetch transcript with auto-translation support"""
#     try:
#         print(f"📺 Fetching transcript for: {video_id}")
        
#         from youtube_transcript_api import YouTubeTranscriptApi
#         from langdetect import detect
        
#         # Step 1: List all available transcripts
#         try:
#             transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
#             print(f"✅ Transcripts available:")
#             available_transcripts = []
#             for t in transcript_list:
#                 info = f"{t.language} ({t.language_code})"
#                 if t.is_generated:
#                     info += " [auto]"
#                 print(f"   - {info}")
#                 available_transcripts.append(t)
            
#             if not available_transcripts:
#                 print(f"❌ No transcripts found")
#                 return None
            
#             # Step 2: Try to get English transcript directly
#             try:
#                 print(f"   Trying direct English transcript...")
#                 transcript = transcript_list.find_transcript(['en'])
#                 segments = transcript.fetch()
                
#                 full_text = ' '.join([seg['text'].strip() for seg in segments if seg.get('text')])
                
#                 if full_text and len(full_text) > 50:
#                     print(f"✅ Found English transcript: {len(full_text)} chars")
#                     return {
#                         'text': full_text,
#                         'language': 'en',
#                         'method': 'Direct English',
#                         'segments': segments
#                     }
#             except:
#                 print(f"   No direct English transcript")
            
#             # Step 3: Get any available transcript and translate to English
#             print(f"   Trying auto-translation to English...")
            
#             for transcript in available_transcripts:
#                 try:
#                     print(f"   Attempting: {transcript.language_code} → English")
                    
#                     # Translate to English
#                     translated = transcript.translate('en')
#                     segments = translated.fetch()
                    
#                     full_text = ' '.join([seg['text'].strip() for seg in segments if seg.get('text')])
                    
#                     if full_text and len(full_text) > 50:
#                         print(f"✅ SUCCESS! Translated {transcript.language_code} → English: {len(full_text)} chars")
#                         print(f"   Preview: {full_text[:200]}...")
                        
#                         return {
#                             'text': full_text,
#                             'language': 'en',
#                             'original_language': transcript.language_code,
#                             'method': f'Auto-translated from {transcript.language}',
#                             'segments': segments
#                         }
                    
#                 except Exception as e:
#                     print(f"   ⚠️ Translation failed for {transcript.language_code}: {e}")
#                     continue
            
#             # Step 4: If translation fails, get original text
#             print(f"   Translation failed, getting original text...")
            
#             for transcript in available_transcripts:
#                 try:
#                     segments = transcript.fetch()
#                     full_text = ' '.join([seg['text'].strip() for seg in segments if seg.get('text')])
                    
#                     if full_text and len(full_text) > 50:
#                         try:
#                             detected_lang = detect(full_text[:500])
#                         except:
#                             detected_lang = transcript.language_code
                        
#                         print(f"✅ Got original text in {transcript.language}: {len(full_text)} chars")
                        
#                         return {
#                             'text': full_text,
#                             'language': detected_lang,
#                             'method': f'Original {transcript.language}',
#                             'segments': segments
#                         }
#                 except:
#                     continue
            
#             print(f"❌ All methods failed")
#             return None
            
#         except Exception as e:
#             print(f"❌ Error listing transcripts: {e}")
#             return None
        
#     except Exception as e:
#         print(f"❌ Transcript error: {e}")
#         import traceback
#         traceback.print_exc()
#         return None

# Routes
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
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/chapter_meaning', methods=['POST'])
def get_chapter_meaning_route():
    try:
        data = request.json
        canto = int(data.get('canto'))
        chapter = int(data.get('chapter'))
        
        print(f"\n📺 Request: Canto {canto} Chapter {chapter}")
        
        result = get_chapter_meaning(canto, chapter)
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Route error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/test_simple/<video_id>', methods=['GET'])
def test_simple(video_id):
    """Simple transcript test with detailed output"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        result = {
            'video_id': video_id,
            'url': f'https://www.youtube.com/watch?v={video_id}'
        }
        
        # Try to list transcripts
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            available = []
            for t in transcript_list:
                available.append({
                    'language': t.language,
                    'code': t.language_code,
                    'auto': t.is_generated
                })
            
            result['transcripts_available'] = available
            result['count'] = len(available)
            
            # Try to get first transcript and translate
            if available:
                first = list(transcript_list)[0]
                
                # Get original
                segments = first.fetch()
                orig_text = ' '.join([s['text'] for s in segments[:5]])
                result['original_sample'] = orig_text
                result['original_lang'] = first.language_code
                
                # Try translate to English
                try:
                    translated = first.translate('en')
                    trans_segments = translated.fetch()
                    trans_text = ' '.join([s['text'] for s in trans_segments[:5]])
                    result['translated_sample'] = trans_text
                    result['translation_success'] = True
                except Exception as e:
                    result['translation_error'] = str(e)
                    result['translation_success'] = False
            
        except Exception as e:
            result['error'] = str(e)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)})

# def get_youtube_transcript_ytdlp(video_id):
#     """Extract subtitles using yt-dlp command-line tool"""
#     try:
#         print(f"🎯 Extracting subtitles with yt-dlp for: {video_id}")
        
#         video_url = f"https://www.youtube.com/watch?v={video_id}"
        
#         # Create temp directory for subtitle files
#         import tempfile
#         temp_dir = tempfile.mkdtemp()
#         subtitle_path = os.path.join(temp_dir, 'subtitle')
        
#         # Try to download Tamil subtitles (auto-generated or manual)
#         cmd = [
#             'yt-dlp',
#             '--write-auto-sub',  # Get auto-generated subs
#             '--write-sub',       # Get manual subs
#             '--skip-download',   # Don't download video
#             '--sub-lang', 'ta,hi,en',  # Try Tamil, Hindi, English
#             '--sub-format', 'vtt',  # VTT format (easiest to parse)
#             '--output', subtitle_path,
#             video_url
#         ]
        
#         print(f"   Command: {' '.join(cmd)}")
        
#         result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
#         print(f"   Return code: {result.returncode}")
#         if result.stderr:
#             print(f"   Stderr: {result.stderr[:500]}")
        
#         # Look for generated subtitle files
#         import glob
#         subtitle_files = glob.glob(f"{subtitle_path}*.vtt")
        
#         if not subtitle_files:
#             print(f"❌ No subtitle files found")
#             # Cleanup
#             import shutil
#             shutil.rmtree(temp_dir, ignore_errors=True)
#             return None
        
#         print(f"✅ Found subtitle file: {subtitle_files[0]}")
        
#         # Read and parse VTT file
#         with open(subtitle_files[0], 'r', encoding='utf-8') as f:
#             vtt_content = f.read()
        
#         # Parse VTT format
#         import re
        
#         # Remove VTT header and timing lines
#         lines = vtt_content.split('\n')
#         text_lines = []
        
#         for line in lines:
#             line = line.strip()
#             # Skip empty lines, WEBVTT header, and timing lines
#             if (line and 
#                 not line.startswith('WEBVTT') and 
#                 not line.startswith('Kind:') and
#                 not line.startswith('Language:') and
#                 not '-->' in line and
#                 not line.isdigit()):
#                 # Remove HTML tags
#                 line = re.sub(r'<[^>]+>', '', line)
#                 if line:
#                     text_lines.append(line)
        
#         full_text = ' '.join(text_lines)
        
#         # Cleanup
#         import shutil
#         shutil.rmtree(temp_dir, ignore_errors=True)
        
#         if not full_text or len(full_text) < 10:
#             print(f"❌ Extracted text too short: {len(full_text)} chars")
#             return None
        
#         # Detect language
#         try:
#             from langdetect import detect
#             detected_lang = detect(full_text[:500])
#         except:
#             detected_lang = 'ta'
        
#         print(f"✅ yt-dlp success: {len(full_text)} chars, language: {detected_lang}")
        
#         return {
#             'text': full_text,
#             'language': detected_lang,
#             'segments': []
#         }
        
#     except subprocess.TimeoutExpired:
#         print(f"❌ yt-dlp timeout")
#         return None
#     except Exception as e:
#         print(f"❌ yt-dlp error: {type(e).__name__}: {e}")
#         import traceback
#         traceback.print_exc()
#         return None

def get_youtube_transcript_ytdlp(video_id):
    """Extract subtitles using yt-dlp - improved version"""
    try:
        print(f"🎯 Extracting subtitles with yt-dlp for: {video_id}")
        
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Step 1: List available subtitles first
        print(f"   Step 1: Checking available subtitles...")
        list_cmd = ['yt-dlp', '--list-subs', video_url]
        
        list_result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
        
        if list_result.stdout:
            print(f"   Available subtitles:")
            for line in list_result.stdout.split('\n')[:20]:
                if line.strip():
                    print(f"     {line}")
        
        # Step 2: Try to download subtitles
        import tempfile
        temp_dir = tempfile.mkdtemp()
        subtitle_path = os.path.join(temp_dir, 'subtitle')
        
        # Try multiple approaches
        subtitle_text = None
        
        # Approach 1: Try all available subtitles
        for sub_format in ['vtt', 'srv3', 'srv2', 'srv1', 'ttml', 'json3']:
            if subtitle_text:
                break
                
            for lang_option in [
                'ta',           # Tamil
                'hi',           # Hindi  
                'en',           # English
                'ta-IN',        # Tamil (India)
                'hi-IN',        # Hindi (India)
            ]:
                if subtitle_text:
                    break
                    
                print(f"   Trying: lang={lang_option}, format={sub_format}")
                
                cmd = [
                    'yt-dlp',
                    '--write-auto-sub',
                    '--write-sub',
                    '--skip-download',
                    '--sub-lang', lang_option,
                    '--sub-format', sub_format,
                    '--output', subtitle_path,
                    '--no-warnings',
                    video_url
                ]
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    # Look for subtitle files
                    import glob
                    subtitle_files = glob.glob(f"{subtitle_path}*")
                    
                    if subtitle_files:
                        print(f"   ✅ Found file: {os.path.basename(subtitle_files[0])}")
                        
                        # Read the file
                        with open(subtitle_files[0], 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Parse based on format
                        if content:
                            import re
                            
                            # Remove timestamps and formatting
                            lines = content.split('\n')
                            text_lines = []
                            
                            for line in lines:
                                line = line.strip()
                                # Skip headers, timestamps, and empty lines
                                if (line and 
                                    not line.startswith('WEBVTT') and
                                    not line.startswith('Kind:') and
                                    not line.startswith('Language:') and
                                    not line.startswith('<?xml') and
                                    not '-->' in line and
                                    not line.isdigit() and
                                    not line.startswith('<') and
                                    not line.endswith('>')):
                                    # Remove HTML/XML tags
                                    line = re.sub(r'<[^>]+>', '', line)
                                    if line and len(line) > 2:
                                        text_lines.append(line)
                            
                            subtitle_text = ' '.join(text_lines)
                            
                            if len(subtitle_text) > 50:
                                print(f"   ✅ Extracted {len(subtitle_text)} chars")
                                break
                            else:
                                subtitle_text = None
                        
                        # Clean up this attempt
                        for f in subtitle_files:
                            try:
                                os.remove(f)
                            except:
                                pass
                                
                except subprocess.TimeoutExpired:
                    print(f"   ⏱️ Timeout for {lang_option}/{sub_format}")
                except Exception as e:
                    print(f"   ⚠️ Error: {e}")
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        if not subtitle_text or len(subtitle_text) < 50:
            print(f"❌ No valid subtitles extracted")
            return None
        
        # Detect language
        try:
            from langdetect import detect
            detected_lang = detect(subtitle_text[:500])
        except:
            detected_lang = 'ta'
        
        print(f"✅ SUCCESS: {len(subtitle_text)} chars, language: {detected_lang}")
        print(f"   Preview: {subtitle_text[:200]}...")
        
        return {
            'text': subtitle_text,
            'language': detected_lang,
            'segments': []
        }
        
    except Exception as e:
        print(f"❌ yt-dlp error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None

@app.route('/test_transcript/<video_id>', methods=['GET'])
def test_transcript(video_id):
    """Test transcript fetching for a specific video"""
    try:
        result = get_youtube_transcript(video_id)
        
        if result:
            return jsonify({
                'success': True,
                'video_id': video_id,
                'text_length': len(result['text']),
                'language': result['language'],
                'preview': result['text'][:500],
                'segments_count': len(result.get('segments', []))
            })
        else:
            return jsonify({
                'success': False,
                'video_id': video_id,
                'error': 'No transcript found'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'video_id': video_id,
            'error': str(e)
        })


@app.route('/debug/test_video/<int:canto>/<int:chapter>', methods=['GET'])
def debug_test_video(canto, chapter):
    """Debug endpoint to test video and transcript"""
    try:
        # Get video mapping
        mapping = get_video_mapping()
        video_id = mapping.get((canto, chapter))
        
        result = {
            'mapping_total': len(mapping),
            'canto': canto,
            'chapter': chapter,
            'video_id': video_id,
            'has_video': video_id is not None
        }
        
        if video_id:
            result['youtube_url'] = f'https://www.youtube.com/watch?v={video_id}'
            
            # Try to get transcript
            print(f"\n{'='*60}")
            print(f"TESTING VIDEO: {video_id}")
            print(f"{'='*60}\n")
            
            transcript = get_youtube_transcript(video_id)
            
            if transcript:
                result['transcript_found'] = True
                result['transcript_length'] = len(transcript['text'])
                result['transcript_language'] = transcript['language']
                result['transcript_preview'] = transcript['text'][:200]
            else:
                result['transcript_found'] = False
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        })

def get_youtube_transcript(video_id):
    """Fetch transcript - try browser automation first"""
    try:
        print(f"📺 Fetching transcript for: {video_id}")
        
        # METHOD 1: Browser automation (clicks CC button)
        print(f"   Method 1: Playwright browser automation...")
        result = extract_captions_with_playwright(video_id)
        if result:
            return result
        
        # METHOD 2: youtube-transcript-api (fallback)
        print(f"   Method 2: youtube-transcript-api...")
        from youtube_transcript_api import YouTubeTranscriptApi
        
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            for transcript in transcript_list:
                try:
                    # Try to translate to English
                    translated = transcript.translate('en')
                    segments = translated.fetch()
                    full_text = ' '.join([seg['text'].strip() for seg in segments if seg.get('text')])
                    
                    if full_text and len(full_text) > 50:
                        return {
                            'text': full_text,
                            'language': 'en',
                            'method': 'youtube-transcript-api',
                            'segments': segments
                        }
                except:
                    continue
        except:
            pass
        
        return None
        
    except Exception as e:
        print(f"❌ All methods failed: {e}")
        return None

def get_youtube_transcript_direct(video_id):
    """Fetch transcript using direct YouTube approach - last resort"""
    try:
        print(f"   Method 4: Direct HTML scraping...")
        
        import urllib.request
        import json
        from html import unescape
        import re
        
        # Get video page
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9,ta;q=0.8'
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')
        
        # Look for caption tracks in page HTML
        if '"captions":' not in html and 'captionTracks' not in html:
            print(f"     No caption data found in HTML")
            return None
        
        # Extract caption track URL
        pattern = r'"captionTracks":\s*(\[.*?\])'
        match = re.search(pattern, html)
        
        if not match:
            print(f"     Caption tracks not found in HTML")
            return None
        
        tracks_json = match.group(1)
        tracks = json.loads(tracks_json)
        
        if not tracks:
            print(f"     Caption tracks empty")
            return None
        
        # Get first available track
        track = tracks[0]
        caption_url = track.get('baseUrl')
        
        if not caption_url:
            print(f"     No baseUrl in caption track")
            return None
        
        print(f"     Found caption URL, fetching...")
        
        # Fetch captions
        req = urllib.request.Request(caption_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            caption_xml = response.read().decode('utf-8')
        
        # Parse XML to extract text
        text_pattern = r'<text[^>]*>(.*?)</text>'
        texts = re.findall(text_pattern, caption_xml, re.DOTALL)
        
        if not texts:
            print(f"     No text found in captions")
            return None
        
        # Unescape HTML entities and clean
        full_text = ' '.join([unescape(re.sub(r'<[^>]+>', '', t)) for t in texts])
        
        if len(full_text) < 50:
            print(f"     Text too short: {len(full_text)} chars")
            return None
        
        print(f"   ✅ Direct method success: {len(full_text)} chars")
        
        # Detect language
        try:
            from langdetect import detect
            lang = detect(full_text[:500])
        except:
            lang = 'ta'
        
        return {
            'text': full_text,
            'language': lang,
            'segments': []
        }
        
    except Exception as e:
        print(f"     Direct method error: {e}")
        return None

# def extract_captions_with_playwright(video_id):
#     """Extract captions by automating CC button click"""
#     try:
#         print(f"🎬 Browser automation for: {video_id}")
        
#         from playwright.sync_api import sync_playwright
#         import time
        
#         video_url = f"https://www.youtube.com/watch?v={video_id}"
#         caption_data = []
        
#         with sync_playwright() as p:
#             # Launch browser
#             browser = p.chromium.launch(headless=True)
#             context = browser.new_context(
#                 user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
#                 locale='en-US'
#             )
#             page = context.new_page()
            
#             # Intercept network requests to capture caption data
#             def handle_response(response):
#                 if 'timedtext' in response.url or 'caption' in response.url:
#                     try:
#                         print(f"   📥 Captured caption URL: {response.url[:100]}...")
#                         text = response.text()
#                         caption_data.append({
#                             'url': response.url,
#                             'data': text
#                         })
#                     except Exception as e:
#                         print(f"   ⚠️ Error capturing response: {e}")
            
#             page.on('response', handle_response)
            
#             print(f"   Loading video page...")
#             page.goto(video_url, wait_until='domcontentloaded', timeout=60000)
            
#             # Wait for player to load
#             time.sleep(5)
            
#             # Try to find and click CC button
#             try:
#                 print(f"   Looking for CC button...")
                
#                 # Wait for player controls
#                 page.wait_for_selector('.ytp-chrome-bottom', timeout=10000)
                
#                 # Try different CC button selectors
#                 cc_selectors = [
#                     'button.ytp-subtitles-button',
#                     'button[aria-label*="Subtitles"]',
#                     'button[aria-label*="Captions"]',
#                     '.ytp-subtitles-button',
#                 ]
                
#                 clicked = False
#                 for selector in cc_selectors:
#                     try:
#                         element = page.query_selector(selector)
#                         if element:
#                             print(f"   Found CC button: {selector}")
                            
#                             # Check if captions are already on
#                             aria_pressed = element.get_attribute('aria-pressed')
#                             if aria_pressed != 'true':
#                                 print(f"   Clicking CC button...")
#                                 element.click()
#                                 clicked = True
#                                 time.sleep(3)  # Wait for captions to load
#                                 break
#                             else:
#                                 print(f"   Captions already enabled")
#                                 clicked = True
#                                 break
#                     except Exception as e:
#                         continue
                
#                 if not clicked:
#                     print(f"   ⚠️ Could not find/click CC button")
                
#                 # Wait a bit more for any delayed network requests
#                 time.sleep(2)
                
#             except Exception as e:
#                 print(f"   ⚠️ Error with CC button: {e}")
            
#             # Alternative: Try to extract captions from DOM
#             if not caption_data:
#                 print(f"   Trying to extract from DOM...")
#                 try:
#                     # Look for caption elements in the player
#                     caption_elements = page.query_selector_all('.ytp-caption-segment')
#                     if caption_elements:
#                         print(f"   Found {len(caption_elements)} caption elements")
#                 except:
#                     pass
            
#             browser.close()
        
#         # Process captured caption data
#         if caption_data:
#             print(f"✅ Captured {len(caption_data)} caption responses")
            
#             for item in caption_data:
#                 data = item['data']
                
#                 # Try to parse the caption data
#                 text = parse_subtitle_content(data)
                
#                 if text and len(text) > 50:
#                     print(f"✅ Successfully extracted {len(text)} chars")
                    
#                     # Detect language
#                     try:
#                         from langdetect import detect
#                         lang = detect(text[:500])
#                     except:
#                         lang = 'unknown'
                    
#                     return {
#                         'text': text,
#                         'language': lang,
#                         'method': 'Playwright browser automation',
#                         'segments': []
#                     }
        
#         print(f"❌ No captions extracted via browser automation")
#         return None
        
#     except Exception as e:
#         print(f"❌ Browser automation error: {e}")
#         import traceback
#         traceback.print_exc()
#         return None

def extract_captions_with_playwright(video_id):
    """Extract captions by automating CC button click - improved"""
    try:
        print(f"🎬 Browser automation for: {video_id}")
        
        from playwright.sync_api import sync_playwright
        import time
        
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        caption_data = []
        
        with sync_playwright() as p:
            # Launch browser with more realistic settings
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox'
                ]
            )
            
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = context.new_page()
            
            # Intercept network requests to capture caption data
            def handle_response(response):
                url = response.url
                if 'timedtext' in url or 'api/timedtext' in url:
                    try:
                        print(f"   📥 Captured caption URL")
                        text = response.text()
                        if len(text) > 100:
                            caption_data.append(text)
                    except Exception as e:
                        pass
            
            page.on('response', handle_response)
            
            print(f"   Loading video page...")
            page.goto(video_url, wait_until='domcontentloaded', timeout=90000)
            
            # Wait longer for player to fully load
            print(f"   Waiting for player to load...")
            time.sleep(10)
            
            # Try to interact with player to trigger caption loading
            try:
                print(f"   Looking for player...")
                
                # Try to find the video player element
                player_selectors = [
                    '#movie_player',
                    '.html5-video-player',
                    'video'
                ]
                
                player_found = False
                for selector in player_selectors:
                    try:
                        if page.query_selector(selector):
                            print(f"   Found player: {selector}")
                            player_found = True
                            break
                    except:
                        continue
                
                if not player_found:
                    print(f"   ⚠️ Player not found")
                
                # Try to find and click CC button - multiple approaches
                print(f"   Looking for CC button...")
                
                # Approach 1: Try clicking by JavaScript
                try:
                    js_code = """
                    const buttons = document.querySelectorAll('button');
                    for (let btn of buttons) {
                        const ariaLabel = btn.getAttribute('aria-label') || '';
                        const className = btn.className || '';
                        if (ariaLabel.toLowerCase().includes('subtitle') || 
                            ariaLabel.toLowerCase().includes('caption') ||
                            className.includes('ytp-subtitles-button')) {
                            btn.click();
                            return 'clicked';
                        }
                    }
                    return 'not found';
                    """
                    
                    result = page.evaluate(js_code)
                    print(f"   JS click result: {result}")
                    
                    if result == 'clicked':
                        time.sleep(5)  # Wait for captions to load
                        
                except Exception as e:
                    print(f"   ⚠️ JS click failed: {e}")
                
                # Approach 2: Try Playwright click
                cc_selectors = [
                    'button.ytp-subtitles-button',
                    'button[aria-label*="ubtitle"]',
                    'button[aria-label*="aption"]',
                    '.ytp-subtitles-button'
                ]
                
                for selector in cc_selectors:
                    try:
                        element = page.wait_for_selector(selector, timeout=5000, state='visible')
                        if element:
                            print(f"   Found CC button: {selector}")
                            element.click()
                            time.sleep(5)
                            break
                    except:
                        continue
                
                # Wait for any network requests
                time.sleep(3)
                
            except Exception as e:
                print(f"   ⚠️ Button interaction error: {e}")
            
            # Try to extract captions from page source as fallback
            if not caption_data:
                print(f"   Trying to extract from page HTML...")
                try:
                    html = page.content()
                    
                    # Look for caption data in page source
                    import re
                    import json
                    
                    # Try to find captionTracks in the HTML
                    patterns = [
                        r'"captionTracks":\s*(\[.*?\])',
                        r'"captions".*?"captionTracks":\s*(\[.*?\])'
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, html, re.DOTALL)
                        for match in matches:
                            try:
                                tracks = json.loads(match)
                                if tracks and len(tracks) > 0:
                                    # Found caption track URLs
                                    for track in tracks:
                                        base_url = track.get('baseUrl', '')
                                        if base_url:
                                            print(f"   Found caption track in HTML")
                                            # Fetch the caption data
                                            try:
                                                caption_response = page.request.get(base_url, timeout=30000)
                                                if caption_response.ok:
                                                    caption_text = caption_response.text()
                                                    if len(caption_text) > 100:
                                                        caption_data.append(caption_text)
                                                        print(f"   ✅ Fetched caption from track URL")
                                            except:
                                                pass
                            except:
                                continue
                except Exception as e:
                    print(f"   ⚠️ HTML extraction error: {e}")
            
            browser.close()
        
        # Process captured caption data
        if caption_data:
            print(f"✅ Captured {len(caption_data)} caption responses")
            
            for data in caption_data:
                # Parse the caption content
                text = parse_subtitle_content(data)
                
                if text and len(text) > 100:
                    print(f"✅ Extracted {len(text)} chars")
                    
                    # Detect language
                    try:
                        from langdetect import detect
                        lang = detect(text[:500])
                    except:
                        lang = 'unknown'
                    
                    return {
                        'text': text,
                        'language': lang,
                        'method': 'Playwright automation',
                        'segments': []
                    }
        
        print(f"❌ No captions extracted via browser automation")
        return None
        
    except Exception as e:
        print(f"❌ Browser automation error: {e}")
        import traceback
        traceback.print_exc()
        return None
        
def extract_subtitles_comprehensive(video_id):
    """Try EVERY method to extract subtitles - comprehensive approach"""
    
    print(f"\n{'='*70}")
    print(f"COMPREHENSIVE SUBTITLE EXTRACTION FOR: {video_id}")
    print(f"{'='*70}\n")
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # ==================== METHOD 1: yt-dlp with verbose listing ====================
    print(f"🔍 METHOD 1: Detailed yt-dlp subtitle check")
    try:
        cmd = ['yt-dlp', '--list-subs', '--verbose', video_url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        print("Available subtitles (full output):")
        print(result.stdout)
        
        if result.stderr:
            print("Stderr:")
            print(result.stderr[:1000])
            
    except Exception as e:
        print(f"❌ Method 1 error: {e}")
    
    # ==================== METHOD 2: Try to download ANY subtitle ====================
    print(f"\n🔍 METHOD 2: Force download with all options")
    try:
        import tempfile
        temp_dir = tempfile.mkdtemp()
        
        # Try with ALL subtitle options enabled
        cmd = [
            'yt-dlp',
            '--write-auto-sub',
            '--write-sub',
            '--all-subs',  # Download ALL available subtitles
            '--skip-download',
            '--output', os.path.join(temp_dir, 'subtitle'),
            video_url
        ]
        
        print(f"Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout[:500]}")
        
        # Check what files were created
        import glob
        all_files = glob.glob(os.path.join(temp_dir, '*'))
        
        if all_files:
            print(f"✅ Files created: {len(all_files)}")
            for f in all_files:
                print(f"   - {os.path.basename(f)} ({os.path.getsize(f)} bytes)")
                
                # Try to read and parse each file
                try:
                    with open(f, 'r', encoding='utf-8', errors='ignore') as file:
                        content = file.read()
                        
                        # Parse subtitle content
                        text = parse_subtitle_content(content)
                        
                        if text and len(text) > 50:
                            print(f"   ✅ SUCCESS! Extracted {len(text)} chars from {os.path.basename(f)}")
                            
                            # Detect language
                            try:
                                from langdetect import detect
                                lang = detect(text[:500])
                            except:
                                lang = 'ta'
                            
                            # Cleanup
                            import shutil
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            
                            return {
                                'text': text,
                                'language': lang,
                                'method': 'yt-dlp --all-subs',
                                'segments': []
                            }
                except Exception as e:
                    print(f"   ⚠️ Error reading {os.path.basename(f)}: {e}")
        else:
            print(f"❌ No files created")
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    except Exception as e:
        print(f"❌ Method 2 error: {e}")
    
    # ==================== METHOD 3: YouTube timedtext API ====================
    print(f"\n🔍 METHOD 3: Direct YouTube timedtext API")
    try:
        import urllib.request
        import json
        import re
        from html import unescape
        
        # Get video page to find caption tracks
        print(f"Fetching video page...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9,ta;q=0.8,hi;q=0.7'
        }
        
        req = urllib.request.Request(video_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')
        
        # Find all caption track data
        patterns = [
            r'"captionTracks":\s*(\[.*?\])',
            r'"captions":\s*\{[^}]*"playerCaptionsTracklistRenderer":\s*\{[^}]*"captionTracks":\s*(\[.*?\])',
        ]
        
        caption_tracks = None
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    caption_tracks = json.loads(match.group(1))
                    print(f"✅ Found caption tracks using pattern")
                    break
                except:
                    continue
        
        if caption_tracks:
            print(f"Available caption tracks: {len(caption_tracks)}")
            
            for i, track in enumerate(caption_tracks):
                lang_code = track.get('languageCode', 'unknown')
                lang_name = track.get('name', {}).get('simpleText', 'Unknown')
                base_url = track.get('baseUrl', '')
                is_auto = track.get('kind', '') == 'asr'
                
                print(f"  Track {i+1}: {lang_name} ({lang_code}) {'[auto]' if is_auto else '[manual]'}")
                
                if base_url:
                    try:
                        print(f"    Fetching from: {base_url[:80]}...")
                        
                        req = urllib.request.Request(base_url, headers=headers)
                        with urllib.request.urlopen(req, timeout=30) as response:
                            caption_data = response.read().decode('utf-8')
                        
                        # Parse the caption data (usually XML or JSON)
                        text = parse_subtitle_content(caption_data)
                        
                        if text and len(text) > 50:
                            print(f"    ✅ SUCCESS! Extracted {len(text)} chars")
                            
                            try:
                                from langdetect import detect
                                detected_lang = detect(text[:500])
                            except:
                                detected_lang = lang_code
                            
                            return {
                                'text': text,
                                'language': detected_lang,
                                'method': 'YouTube timedtext API',
                                'segments': []
                            }
                        else:
                            print(f"    ⚠️ Text too short: {len(text) if text else 0} chars")
                            
                    except Exception as e:
                        print(f"    ❌ Error fetching track: {e}")
        else:
            print(f"❌ No caption tracks found in HTML")
    
    except Exception as e:
        print(f"❌ Method 3 error: {e}")
        import traceback
        traceback.print_exc()
    
    # ==================== METHOD 4: youtube-transcript-api with retries ====================
    print(f"\n🔍 METHOD 4: youtube-transcript-api (all languages)")
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        # Get list of all available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        print(f"Transcripts found:")
        for transcript in transcript_list:
            print(f"  - {transcript.language} ({transcript.language_code}) {'[auto]' if transcript.is_generated else '[manual]'}")
        
        # Try to fetch ANY transcript
        for transcript in transcript_list:
            try:
                print(f"  Trying to fetch: {transcript.language_code}...")
                segments = transcript.fetch()
                
                if segments:
                    full_text = ' '.join([seg['text'].strip() for seg in segments if seg.get('text')])
                    
                    if len(full_text) > 50:
                        print(f"  ✅ SUCCESS! Extracted {len(full_text)} chars")
                        
                        try:
                            from langdetect import detect
                            lang = detect(full_text[:500])
                        except:
                            lang = transcript.language_code
                        
                        return {
                            'text': full_text,
                            'language': lang,
                            'method': 'youtube-transcript-api',
                            'segments': segments
                        }
            except Exception as e:
                print(f"  ⚠️ Error: {e}")
    
    except Exception as e:
        print(f"❌ Method 4 error: {e}")
    
    print(f"\n{'='*70}")
    print(f"❌ ALL METHODS FAILED - NO SUBTITLES EXTRACTED")
    print(f"{'='*70}\n")
    
    return None


def parse_subtitle_content(content):
    """Parse subtitle content from various formats (VTT, XML, JSON, SRT)"""
    import re
    from html import unescape
    
    if not content:
        return None
    
    text_lines = []
    
    # Try XML format (YouTube timedtext)
    if '<text' in content or '<transcript' in content:
        pattern = r'<text[^>]*>(.*?)</text>'
        matches = re.findall(pattern, content, re.DOTALL)
        for match in matches:
            clean = re.sub(r'<[^>]+>', '', match)
            clean = unescape(clean)
            if clean.strip():
                text_lines.append(clean.strip())
    
    # Try VTT format
    elif 'WEBVTT' in content or '-->' in content:
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if (line and 
                not line.startswith('WEBVTT') and
                not line.startswith('Kind:') and
                not line.startswith('Language:') and
                not '-->' in line and
                not line.isdigit() and
                len(line) > 2):
                clean = re.sub(r'<[^>]+>', '', line)
                if clean.strip():
                    text_lines.append(clean.strip())
    
    # Try JSON format
    elif content.startswith('{') or content.startswith('['):
        try:
            import json
            data = json.loads(content)
            
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        text = item.get('text', '') or item.get('content', '') or item.get('snippet', '')
                        if text:
                            text_lines.append(text.strip())
            elif isinstance(data, dict):
                if 'events' in data:
                    for event in data.get('events', []):
                        if 'segs' in event:
                            for seg in event['segs']:
                                if 'utf8' in seg:
                                    text_lines.append(seg['utf8'].strip())
        except:
            pass
    
    # Try SRT format
    elif re.search(r'\d+\n\d{2}:\d{2}:\d{2}', content):
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.isdigit() and not re.match(r'\d{2}:\d{2}:\d{2}', line):
                text_lines.append(line)
    
    return ' '.join(text_lines) if text_lines else None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5019))
    app.run(debug=False, host='0.0.0.0', port=port)