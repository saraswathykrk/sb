from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import sqlite3
import os
import time
import re

app = Flask(__name__)
DB_PATH = '/tmp/srimad_bhagavatam.db'  # Use /tmp for ephemeral storage

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
    """Fetch verse from vedabase.io"""
    try:
        url = f"https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/"
        print(f"🔍 Fetching: {url}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            page.set_default_timeout(10000)
            
            try:
                page.goto(url, wait_until='domcontentloaded')
                time.sleep(2)
            except PlaywrightTimeout:
                print("⚠️ Page load timeout - trying anyway...")
            
            full_text = page.inner_text('body')
            lines = full_text.split('\n')
            
            sb_idx = synonyms_idx = translation_idx = -1
            
            for i, line in enumerate(lines):
                line_clean = line.strip()
                
                if re.match(r'ŚB \d+\.\d+\.\d+', line_clean):
                    sb_idx = i
                    print(f"📍 Found verse ref at line {i}")
                
                if line_clean.lower() == 'synonyms':
                    synonyms_idx = i
                    print(f"📍 Found 'Synonyms' at line {i}")
                
                if line_clean.lower() == 'translation':
                    translation_idx = i
                    print(f"📍 Found 'Translation' at line {i}")
            
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
                    if line and not line.startswith('Default') and not line.startswith('Dual'):
                        if is_devanagari(line):
                            devanagari_lines.append(line)
                        else:
                            verse_lines.append(line)
                
                devanagari_verse = '\n'.join(devanagari_lines)
                sanskrit_verse = '\n'.join(verse_lines)
                
                if devanagari_verse:
                    print(f"✅ Devanagari: {devanagari_verse[:50]}...")
                if sanskrit_verse:
                    print(f"✅ Sanskrit: {sanskrit_verse[:50]}...")
            
            if synonyms_idx > 0 and translation_idx > 0:
                synonym_lines = []
                for i in range(synonyms_idx + 1, translation_idx):
                    line = lines[i].strip()
                    if line:
                        synonym_lines.append(line)
                word_meanings = ' '.join(synonym_lines)
                if word_meanings:
                    print(f"✅ Synonyms: {word_meanings[:50]}...")
            
            if translation_idx > 0:
                translation_lines = []
                for i in range(translation_idx + 1, min(translation_idx + 30, len(lines))):
                    line = lines[i].strip()
                    if line and not line.startswith('CHAPTER') and not line.startswith('Text'):
                        translation_lines.append(line)
                    if line.startswith('CHAPTER') or line.startswith('Text'):
                        break
                
                translation = ' '.join(translation_lines)
                if translation:
                    print(f"✅ Translation: {translation[:50]}...")
            
            browser.close()
            
            print(f"✅ Extraction complete")
            
            return {
                'devanagari_verse': devanagari_verse.strip(),
                'sanskrit_verse': sanskrit_verse.strip(),
                'word_meanings': word_meanings.strip(),
                'translation': translation.strip(),
                'purport': purport,
                'source': 'vedabase.io (fetched)'
            }
            
    except Exception as e:
        print(f"❌ Error: {e}")
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
