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

def fetch_from_vedabase(canto, chapter, verse, retry_count=0):
    """Fetch verse from vedabase.io"""
    max_retries = 2
    
    try:
        url = f"https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/"
        print(f"🔍 Fetching: {url}")
        
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
                browser.close()
                if retry_count < max_retries:
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
    except:
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
        'error': f'Could not fetch verse {verse_ref}'
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
                        # Convert string keys back to tuple keys
                        mapping = {}
                        for key_str, video_id in cached.get('mapping', {}).items():
                            canto, chapter = key_str.strip('()').split(',')
                            mapping[(int(canto.strip()), int(chapter.strip()))] = video_id
                        print(f"✅ Loaded {len(mapping)} videos from cache")
                        return mapping
            except Exception as e:
                print(f"⚠️ Cache load error: {e}")
        
        # Test if yt-dlp is available
        print("🔍 Testing yt-dlp availability...")
        try:
            test_result = subprocess.run(['yt-dlp', '--version'], 
                                        capture_output=True, text=True, timeout=5)
            print(f"   yt-dlp version: {test_result.stdout.strip()}")
        except FileNotFoundError:
            print("❌ yt-dlp command not found!")
            return {}
        except Exception as e:
            print(f"❌ yt-dlp test error: {e}")
            return {}
        
        # Fetch from YouTube
        print(f"📺 Fetching playlist: {PLAYLIST_URL}")
        cmd = ['yt-dlp', '--dump-json', '--flat-playlist', '--skip-download', PLAYLIST_URL]
        
        print(f"   Command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        print(f"   Return code: {result.returncode}")
        print(f"   Stdout length: {len(result.stdout)} chars")
        print(f"   Stderr length: {len(result.stderr)} chars")
        
        if result.stderr:
            print(f"   Stderr: {result.stderr[:500]}")
        
        if result.returncode != 0:
            print(f"❌ yt-dlp failed with code {result.returncode}")
            print(f"   Error: {result.stderr[:1000]}")
            return {}
        
        if not result.stdout.strip():
            print(f"❌ yt-dlp returned empty output")
            return {}
        
        # Parse output
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
                
                if not video_id or not title:
                    continue
                
                title_lower = title.lower()
                
                # Try multiple patterns
                match = re.search(r'(\d+)\.(\d+)', title_lower)
                if match:
                    canto = int(match.group(1))
                    chapter = int(match.group(2))
                    
                    if 1 <= canto <= 12:
                        mapping[(canto, chapter)] = video_id
                        print(f"  ✅ [{canto}.{chapter}] {title[:60]}")
                    
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON parse error on line {line_count}: {e}")
                print(f"   Line: {line[:200]}")
            except Exception as e:
                print(f"⚠️ Parse error on line {line_count}: {e}")
        
        print(f"\n📊 Results:")
        print(f"   Total lines processed: {line_count}")
        print(f"   Videos mapped: {len(mapping)}")
        
        if len(mapping) > 0:
            print(f"   Sample mappings:")
            for (c, ch), vid in list(mapping.items())[:5]:
                print(f"     Canto {c}.{ch} → {vid}")
        
        # Save to cache
        if len(mapping) > 0:
            try:
                cache_data = {
                    'timestamp': time.time(),
                    'mapping': {f"({c},{ch})": vid for (c, ch), vid in mapping.items()}
                }
                with open(MAPPING_CACHE_FILE, 'w') as f:
                    json.dump(cache_data, f)
                print(f"💾 Saved {len(mapping)} videos to cache")
            except Exception as e:
                print(f"⚠️ Cache save error: {e}")
        
        return mapping
        
    except subprocess.TimeoutExpired:
        print(f"❌ yt-dlp timeout after 120 seconds")
        return {}
    except Exception as e:
        print(f"❌ Mapping error: {e}")
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

def get_chapter_meaning(canto, chapter):
    """Simple chapter meaning"""
    try:
        # Check database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT video_id, transcript, translation 
                     FROM chapter_meanings WHERE canto=? AND chapter=?''', (canto, chapter))
        result = c.fetchone()
        conn.close()
        
        if result and result[1]:
            return {
                'success': True,
                'video_id': result[0],
                'transcript': result[1],
                'translation': result[2],
                'source': 'database'
            }
        
        # Get video ID
        mapping = get_video_mapping()
        video_id = mapping.get((int(canto), int(chapter)))
        
        if not video_id:
            return {
                'success': False,
                'error': f'No video found for Canto {canto}, Chapter {chapter}'
            }
        
        # Return video info without transcript for now
        return {
            'success': True,
            'video_id': video_id,
            'transcript': '',
            'translation': '',
            'no_transcript': True,
            'message': 'Video found! Transcript feature coming soon. Watch on YouTube:',
            'source': 'YouTube'
        }
        
    except Exception as e:
        print(f"❌ Chapter meaning error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }

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