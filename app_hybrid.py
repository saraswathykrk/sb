from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import sqlite3
import os
import time
import re

app = Flask(__name__)
#DB_PATH = '/tmp/srimad_bhagavatam.db'  # Use /tmp for ephemeral storage
import tempfile
DB_PATH = os.path.join(tempfile.gettempdir(), 'srimad_bhagavatam.db')


def init_db():
    """Initialize database - runs on every startup"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Always create table if not exists
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
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database init error: {e}")

def is_devanagari(text):
    """Check if text contains Devanagari script"""
    return bool(re.search(r'[\u0900-\u097F]', text))

def fetch_from_vedabase(canto, chapter, verse):
    """Fetch verse from vedabase.io with robust extraction"""
    try:
        url = f"https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/"
        print(f"🔍 Fetching: {url}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            # Load page with longer timeout
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for content to load
            try:
                page.wait_for_selector('body', timeout=10000)
                time.sleep(5)  # Extra wait for dynamic content
            except:
                print("⚠️ Timeout waiting for content")
            
            # Get full page text
            full_text = page.inner_text('body')
            
            # Save to file for debugging
            debug_file = f'/tmp/page_debug_{canto}_{chapter}_{verse}.txt'
            try:
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(full_text)
                print(f"📝 Saved debug file: {debug_file}")
            except:
                pass
            
            print(f"📄 Page length: {len(full_text)} characters")
            print(f"📄 First 200 chars: {full_text[:200]}")
            
            lines = full_text.split('\n')
            print(f"📄 Total lines: {len(lines)}")
            
            # Find key sections
            sb_idx = synonyms_idx = translation_idx = -1
            
            for i, line in enumerate(lines):
                line_lower = line.strip().lower()
                
                # Look for verse reference
                if re.match(r'[śŚ]b \d+\.\d+\.\d+', line.strip(), re.IGNORECASE):
                    sb_idx = i
                    print(f"📍 Found verse ref at line {i}: {line.strip()}")
                
                # Look for Synonyms
                if line_lower == 'synonyms':
                    synonyms_idx = i
                    print(f"📍 Found 'Synonyms' at line {i}")
                
                # Look for Translation
                if line_lower == 'translation':
                    translation_idx = i
                    print(f"📍 Found 'Translation' at line {i}")
            
            # Initialize results
            devanagari_verse = ""
            sanskrit_verse = ""
            word_meanings = ""
            translation = ""
            purport = ""
            
            # Extract verse text (between SB ref and Synonyms)
            if sb_idx > 0 and synonyms_idx > 0:
                print(f"🔍 Extracting verse between lines {sb_idx} and {synonyms_idx}")
                
                devanagari_lines = []
                verse_lines = []
                
                for i in range(sb_idx + 1, synonyms_idx):
                    line = lines[i].strip()
                    # Skip navigation/UI elements
                    if line and not any(skip in line for skip in ['Default View', 'Dual Language', 'Advanced View', 'Show in']):
                        if is_devanagari(line):
                            devanagari_lines.append(line)
                            print(f"  📜 Devanagari line {i}: {line[:50]}")
                        elif len(line) > 3:  # Skip very short lines
                            verse_lines.append(line)
                            print(f"  📝 Sanskrit line {i}: {line[:50]}")
                
                devanagari_verse = '\n'.join(devanagari_lines)
                sanskrit_verse = '\n'.join(verse_lines)
                
                print(f"✅ Devanagari: {len(devanagari_verse)} chars")
                print(f"✅ Sanskrit: {len(sanskrit_verse)} chars")
            else:
                print(f"⚠️ Could not find verse boundaries. sb_idx={sb_idx}, synonyms_idx={synonyms_idx}")
            
            # Extract synonyms
            if synonyms_idx > 0 and translation_idx > 0:
                print(f"🔍 Extracting synonyms between lines {synonyms_idx} and {translation_idx}")
                
                synonym_lines = []
                for i in range(synonyms_idx + 1, translation_idx):
                    line = lines[i].strip()
                    if line and len(line) > 3:
                        synonym_lines.append(line)
                
                word_meanings = ' '.join(synonym_lines)
                print(f"✅ Synonyms: {len(word_meanings)} chars")
            else:
                print(f"⚠️ Could not find synonyms. synonyms_idx={synonyms_idx}, translation_idx={translation_idx}")
            
            # Extract translation
            if translation_idx > 0:
                print(f"🔍 Extracting translation from line {translation_idx}")
                
                translation_lines = []
                for i in range(translation_idx + 1, min(translation_idx + 50, len(lines))):
                    line = lines[i].strip()
                    
                    # Stop at chapter headings or next section
                    if any(stop in line for stop in ['CHAPTER', 'Text ', 'Purport']):
                        break
                    
                    if line and len(line) > 5:
                        translation_lines.append(line)
                
                translation = ' '.join(translation_lines)
                print(f"✅ Translation: {len(translation)} chars")
            else:
                print(f"⚠️ Could not find translation. translation_idx={translation_idx}")
            
            browser.close()
            
            # Final summary
            print(f"\n📊 EXTRACTION SUMMARY:")
            print(f"  Devanagari: {len(devanagari_verse)} chars")
            print(f"  Sanskrit: {len(sanskrit_verse)} chars")
            print(f"  Synonyms: {len(word_meanings)} chars")
            print(f"  Translation: {len(translation)} chars")
            
            return {
                'devanagari_verse': devanagari_verse.strip(),
                'sanskrit_verse': sanskrit_verse.strip(),
                'word_meanings': word_meanings.strip(),
                'translation': translation.strip(),
                'purport': purport,
                'source': 'vedabase.io (fetched)'
            }
            
    except Exception as e:
        print(f"❌ Error fetching verse: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_from_database(canto, chapter, verse):
    """Get from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''SELECT devanagari_verse, sanskrit_verse, word_meanings, translation, purport
                     FROM verses WHERE canto=? AND chapter=? AND verse=?''',
                  (canto, chapter, verse))
        
        result = c.fetchone()
        conn.close()
        
        if result:
            print(f"✅ Found in database: SB {canto}.{chapter}.{verse}")
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
        print(f"💾 Saved: SB {canto}.{chapter}.{verse}")
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
        'error': f'Could not fetch verse {verse_ref}'
    }

@app.before_request
def ensure_database():
    """Ensure database exists before first request"""
    if not hasattr(app, '_database_initialized'):
        print("🔄 Initializing database...")
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
        print(f"❌ Route error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

# Initialize database on startup
print("="*70)
print("🕉️  Srimad Bhagavatam Verse Finder - Initializing...")
print("="*70)
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5019))
    app.run(debug=False, host='0.0.0.0', port=port)
