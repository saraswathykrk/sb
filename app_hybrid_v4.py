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
        
        # Verses table
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
        
        # Chapter meanings table
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

def is_devanagari(text):
    """Check if text contains Devanagari script"""
    return bool(re.search(r'[\u0900-\u097F]', text))

# ==================== TRANSLATION FUNCTIONS ====================

def translate_with_libretranslate(text, source_lang='ta', target_lang='en'):
    """Translate using LibreTranslate (free, open source)"""
    try:
        print(f"🌐 Translating with LibreTranslate ({source_lang} → {target_lang})")
        
        # Public LibreTranslate instance
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
        
        # MyMemory API
        url = "https://api.mymemory.translated.net/get"
        
        # Language code mapping
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
                    print(f"⚠️ MyMemory chunk {i} failed")
                    break
            else:
                print(f"⚠️ MyMemory error: {response.status_code}")
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
        
        # Split into chunks (Google Translate has char limits)
        max_chunk = 4000
        chunks = [text[i:i+max_chunk] for i in range(0, len(text), max_chunk)]
        translated_chunks = []
        
        for i, chunk in enumerate(chunks[:5]):  # Limit to 5 chunks
            result = translator.translate(chunk, src=source_lang, dest=target_lang)
            translated_chunks.append(result.text)
            time.sleep(0.5)  # Rate limiting
        
        full_translation = ' '.join(translated_chunks)
        print(f"✅ Google Translate: {len(full_translation)} chars")
        return full_translation
            
    except Exception as e:
        print(f"❌ Google Translate error: {e}")
        return None

def translate_text_cascade(text, source_lang='ta'):
    """Try multiple translation services in order until one works"""
    
    # Language code conversions
    lang_conversions = {
        'ta': 'ta',  # Tamil
        'hi': 'hi',  # Hindi
        'te': 'te',  # Telugu
        'kn': 'kn',  # Kannada
        'ml': 'ml',  # Malayalam
        'en': 'en'   # English
    }
    
    source = lang_conversions.get(source_lang, source_lang)
    
    print(f"\n🔄 Starting translation cascade for {len(text)} chars...")
    
    # Try LibreTranslate first
    translation = translate_with_libretranslate(text, source, 'en')
    if translation and len(translation) > 50:
        return translation
    
    # Try MyMemory second
    print("⚠️ LibreTranslate failed, trying MyMemory...")
    translation = translate_with_mymemory(text, source, 'en')
    if translation and len(translation) > 50:
        return translation
    
    # Try Google Translate as last resort
    print("⚠️ MyMemory failed, trying Google Translate...")
    translation = translate_with_googletrans(text, source, 'en')
    if translation and len(translation) > 50:
        return translation
    
    print("❌ All translation services failed")
    return None

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
            
            # Increased timeout to 60 seconds
            page.set_default_timeout(60000)
            
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                time.sleep(3)  # Reduced from 5 to 3 seconds
            except PlaywrightTimeout:
                print("⚠️ Page load timeout")
                browser.close()
                
                # Retry if not exceeded max retries
                if retry_count < max_retries:
                    print(f"🔄 Retrying... ({retry_count + 1}/{max_retries})")
                    time.sleep(2)
                    return fetch_from_vedabase(canto, chapter, verse, retry_count + 1)
                else:
                    return None
            
            full_text = page.inner_text('body')
            print(f"📄 Page length: {len(full_text)} characters")
            
            lines = full_text.split('\n')
            
            # Find key sections
            sb_idx = synonyms_idx = translation_idx = purport_idx = -1
            
            for i, line in enumerate(lines):
                line_lower = line.strip().lower()
                
                if re.match(r'[śŚ]b \d+\.\d+\.\d+', line.strip(), re.IGNORECASE):
                    sb_idx = i
                    print(f"📍 Verse ref at line {i}")
                
                if line_lower == 'synonyms':
                    synonyms_idx = i
                    print(f"📍 Synonyms at line {i}")
                
                if line_lower == 'translation':
                    translation_idx = i
                    print(f"📍 Translation at line {i}")
                
                if line_lower == 'purport':
                    purport_idx = i
                    print(f"📍 Purport at line {i}")
            
            # Extract sections
            devanagari_verse = ""
            sanskrit_verse = ""
            word_meanings = ""
            translation = ""
            purport = ""
            
            # Extract verse text
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
            
            # Extract synonyms
            if synonyms_idx > 0 and translation_idx > 0:
                synonym_lines = []
                for i in range(synonyms_idx + 1, translation_idx):
                    line = lines[i].strip()
                    if line and len(line) > 3:
                        synonym_lines.append(line)
                word_meanings = ' '.join(synonym_lines)
            
            # Extract translation
            if translation_idx > 0 and purport_idx > 0:
                translation_lines = []
                for i in range(translation_idx + 1, purport_idx):
                    line = lines[i].strip()
                    if line and len(line) > 3:
                        translation_lines.append(line)
                translation = ' '.join(translation_lines)
            
            # Extract purport - FIXED to get full purport
            if purport_idx > 0:
                purport_lines = []
                for i in range(purport_idx + 1, len(lines)):
                    line = lines[i].strip()
                    
                    # Stop at these markers
                    if any(stop in line for stop in ['Donate', 'Thanks to', 'His Divine Grace', '©', 'Content used with permission']):
                        break
                    
                    # Stop at next text number
                    if re.match(r'^Text \d+$', line):
                        break
                    
                    if line and len(line) > 3:
                        purport_lines.append(line)
                
                purport = ' '.join(purport_lines)
            
            browser.close()
            
            print(f"✅ Extracted - Dev: {len(devanagari_verse)}, San: {len(sanskrit_verse)}, Pur: {len(purport)} chars")
            
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
        import traceback
        traceback.print_exc()
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
            print(f"✅ Found in database")
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
        'error': f'Could not fetch verse {verse_ref}. The site may be slow or unavailable. Please try again.'
    }

# ==================== YOUTUBE CHAPTER MEANINGS ====================

# Manual mapping of videos (you'll need to populate this)
VIDEO_MAPPING = {
    # Format: (canto, chapter): video_id
    (1, 1): "VIDEO_ID_HERE",
    (3, 1): "VIDEO_ID_HERE",
    # Add more mappings
}

def find_video_for_chapter(canto, chapter):
    """Find YouTube video ID for canto/chapter"""
    # Check manual mapping first
    video_id = VIDEO_MAPPING.get((canto, chapter))
    
    if video_id and video_id != "VIDEO_ID_HERE":
        return video_id
    
    # For now, return None - we'll add search functionality later
    print(f"⚠️ No video mapping for Canto {canto}, Chapter {chapter}")
    return None

def get_youtube_transcript(video_id):
    """Fetch transcript from YouTube"""
    try:
        print(f"📺 Fetching transcript for video: {video_id}")
        
        # Try to get transcript in multiple languages
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Prefer manual transcripts over auto-generated
        try:
            transcript = transcript_list.find_manually_created_transcript(['ta', 'hi', 'en'])
        except:
            transcript = transcript_list.find_generated_transcript(['ta', 'hi', 'en'])
        
        segments = transcript.fetch()
        
        # Combine all segments
        full_text = ' '.join([segment['text'] for segment in segments])
        
        # Detect language
        try:
            lang_code = detect(full_text)
        except:
            lang_code = 'en'
        
        print(f"✅ Transcript fetched: {len(full_text)} chars, language: {lang_code}")
        
        return {
            'text': full_text,
            'language': lang_code,
            'segments': segments
        }
        
    except Exception as e:
        print(f"❌ Transcript error: {e}")
        return None

def translate_with_ollama(text, source_lang='Tamil'):
    """Translate using Ollama"""
    try:
        print(f"🤖 Translating with Ollama ({source_lang} → English)")
        
        # Ollama API endpoint (assumes running locally)
        url = "http://localhost:11434/api/generate"
        
        prompt = f"""Translate the following {source_lang} text to English. 
Provide only the English translation, no explanations or notes.

{source_lang} text:
{text[:2000]}

English translation:"""
        
        payload = {
            "model": "llama2",  # or "mistral", "gemma", etc.
            "prompt": prompt,
            "stream": False
        }
        
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            translation = result.get('response', '').strip()
            print(f"✅ Ollama translation: {len(translation)} chars")
            return translation
        else:
            print(f"⚠️ Ollama error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Ollama error: {e}")
        return None

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
        
#         # Find video
#         video_id = find_video_for_chapter(canto, chapter)
        
#         if not video_id:
#             return {
#                 'success': False,
#                 'error': f'No video found for Canto {canto}, Chapter {chapter}. Please add video mapping.'
#             }
        
#         # Get transcript
#         transcript_data = get_youtube_transcript(video_id)
        
#         if not transcript_data:
#             return {
#                 'success': False,
#                 'error': 'Could not fetch transcript from YouTube'
#             }
        
#         original_text = transcript_data['text']
#         language = transcript_data['language']
        
#         # Translate if needed
#         translated_text = original_text
        
#         if language in ['ta', 'hi']:
#             lang_name = 'Tamil' if language == 'ta' else 'Hindi'
#             print(f"🔄 Translating from {lang_name}...")
            
#             translated_text = translate_with_ollama(original_text, lang_name)
            
#             if not translated_text:
#                 translated_text = original_text + "\n\n[Translation unavailable - Ollama may not be running]"
        
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
#             print(f"💾 Saved chapter meaning to database")
#         except:
#             pass
        
#         return {
#             'success': True,
#             'video_id': video_id,
#             'transcript': original_text,
#             'translation': translated_text,
#             'language': language,
#             'source': 'YouTube (fetched)'
#         }
        
#     except Exception as e:
#         print(f"❌ Error: {e}")
#         import traceback
#         traceback.print_exc()
#         return {
#             'success': False,
#             'error': str(e)
#         }

def get_chapter_meaning(canto, chapter):
    """Get chapter meaning from YouTube"""
    try:
        # Check database first
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''SELECT video_id, transcript, translation 
                     FROM chapter_meanings 
                     WHERE canto=? AND chapter=?''', (canto, chapter))
        result = c.fetchone()
        conn.close()
        
        if result:
            print(f"✅ Chapter meaning from database")
            return {
                'success': True,
                'video_id': result[0],
                'transcript': result[1],
                'translation': result[2],
                'source': 'database (cached)'
            }
        
        # Find video
        video_id = find_video_for_chapter(canto, chapter)
        
        if not video_id:
            return {
                'success': False,
                'error': f'No video found for Canto {canto}, Chapter {chapter}. Please add video mapping.'
            }
        
        # Get transcript
        transcript_data = get_youtube_transcript(video_id)
        
        if not transcript_data:
            return {
                'success': False,
                'error': 'Could not fetch transcript from YouTube'
            }
        
        original_text = transcript_data['text']
        language = transcript_data['language']
        
        print(f"📝 Original transcript: {len(original_text)} chars, language: {language}")
        
        # Translate if needed
        translated_text = original_text
        
        if language in ['ta', 'hi', 'te', 'kn', 'ml'] and language != 'en':
            lang_names = {
                'ta': 'Tamil',
                'hi': 'Hindi',
                'te': 'Telugu',
                'kn': 'Kannada',
                'ml': 'Malayalam'
            }
            lang_name = lang_names.get(language, language)
            
            print(f"🔄 Translating from {lang_name} to English...")
            
            # Use cascade translation
            translated_text = translate_text_cascade(original_text, language)
            
            if not translated_text:
                translated_text = f"[Translation failed]\n\nOriginal {lang_name} transcript:\n{original_text}"
        
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
            print(f"💾 Saved chapter meaning to database")
        except Exception as e:
            print(f"⚠️ Database save error: {e}")
        
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
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }

# ==================== ROUTES ====================

@app.before_request
def ensure_database():
    """Ensure database exists"""
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
        
        print(f"\n📥 Request: SB {canto}.{chapter}.{verse}")
        
        result = fetch_verse_hybrid(canto, chapter, verse)
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/chapter_meaning', methods=['POST'])
def get_chapter_meaning_route():
    try:
        data = request.json
        canto = int(data.get('canto'))
        chapter = int(data.get('chapter'))
        
        print(f"\n📺 YouTube Request: Canto {canto} Chapter {chapter}")
        
        result = get_chapter_meaning(canto, chapter)
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5019))
    app.run(debug=False, host='0.0.0.0', port=port)
