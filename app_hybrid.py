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

def get_youtube_transcript(video_id):
    """Fetch transcript from YouTube - improved version"""
    try:
        print(f"📺 Fetching transcript for: {video_id}")
        print(f"   URL: https://www.youtube.com/watch?v={video_id}")
        
        from langdetect import detect
        
        # Get all available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        print(f"✅ Transcripts available for video")
        
        # List all available transcripts
        all_transcripts = []
        for t in transcript_list:
            info = f"{t.language} ({t.language_code})"
            if t.is_generated:
                info += " [auto-generated]"
            else:
                info += " [manual]"
            all_transcripts.append(info)
            print(f"   - {info}")
        
        # Priority order: manual Tamil > auto Tamil > manual Hindi > auto Hindi > any
        transcript = None
        
        # Try manual Tamil first
        try:
            transcript = transcript_list.find_manually_created_transcript(['ta'])
            print(f"✅ Using manual Tamil transcript")
        except:
            pass
        
        # Try auto-generated Tamil
        if not transcript:
            try:
                transcript = transcript_list.find_generated_transcript(['ta'])
                print(f"✅ Using auto-generated Tamil transcript")
            except:
                pass
        
        # Try Hindi
        if not transcript:
            try:
                transcript = transcript_list.find_transcript(['hi'])
                print(f"✅ Using Hindi transcript")
            except:
                pass
        
        # Try English
        if not transcript:
            try:
                transcript = transcript_list.find_transcript(['en'])
                print(f"✅ Using English transcript")
            except:
                pass
        
        # Try ANY available transcript
        if not transcript:
            try:
                available = list(transcript_list)
                if available:
                    transcript = available[0]
                    print(f"✅ Using first available: {transcript.language_code}")
            except:
                pass
        
        if not transcript:
            print(f"❌ No usable transcript found")
            return None
        
        # Fetch transcript content
        print(f"📥 Downloading transcript...")
        segments = transcript.fetch()
        
        if not segments:
            print(f"❌ Transcript is empty")
            return None
        
        # Combine all text
        full_text = ' '.join([seg['text'].strip() for seg in segments if seg.get('text')])
        
        if not full_text or len(full_text) < 10:
            print(f"❌ Transcript too short: {len(full_text)} chars")
            return None
        
        # Detect language
        try:
            detected_lang = detect(full_text[:500])  # Use first 500 chars for detection
            print(f"🔍 Detected language: {detected_lang}")
        except:
            detected_lang = transcript.language_code
        
        print(f"✅ Transcript success: {len(full_text)} chars, {len(segments)} segments")
        
        return {
            'text': full_text,
            'language': detected_lang,
            'segments': segments,
            'language_name': transcript.language
        }
        
    except Exception as e:
        print(f"❌ Transcript error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None
        
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5019))
    app.run(debug=False, host='0.0.0.0', port=port)