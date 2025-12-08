from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import sqlite3
import os
import time
import re
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
DB_PATH = 'srimad_bhagavatam.db'

# Use PostgreSQL if DATABASE_URL exists, otherwise SQLite
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if DATABASE_URL:
        # PostgreSQL
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        # SQLite (local development)
        import sqlite3
        conn = sqlite3.connect('srimad_bhagavatam.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if using PostgreSQL or SQLite
    if DATABASE_URL:
        # PostgreSQL
        cursor.execute("""
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
    else:
        # SQLite
        cursor.execute("""
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


def fetch_from_vedabase(canto, chapter, verse):
    try:
        url = f"https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/"
        print(f"🔍 Fetching: {url}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Set timeout to 10 seconds
            page.set_default_timeout(10000)
            
            try:
                page.goto(url, wait_until='domcontentloaded')
                time.sleep(2)
            except PlaywrightTimeout:
                print("⚠️ Page load timeout - trying anyway...")
            
            full_text = page.inner_text('body')
            lines = full_text.split('\n')
            
            # Quick extraction
            sb_idx = synonyms_idx = translation_idx = -1
            
            for i, line in enumerate(lines):
                if re.match(r'ŚB \d+\.\d+\.\d+', line.strip()):
                    sb_idx = i
                elif line.strip().lower() == 'synonyms':
                    synonyms_idx = i
                elif line.strip().lower() == 'translation':
                    translation_idx = i
            
            # Extract
            devanagari = sanskrit = synonyms = translation = purport = ""
            
            if sb_idx > 0 and synonyms_idx > 0:
                for i in range(sb_idx + 1, synonyms_idx):
                    line = lines[i].strip()
                    if line:
                        if re.search(r'[\u0900-\u097F]', line):
                            devanagari += line + '\n'
                        else:
                            sanskrit += line + '\n'
            
            if synonyms_idx > 0 and translation_idx > 0:
                synonyms = ' '.join(lines[synonyms_idx+1:translation_idx])
            
            if translation_idx > 0:
                trans_lines = []
                for i in range(translation_idx+1, len(lines)):
                    if 'CHAPTER' in lines[i] or lines[i].startswith('Text'):
                        break
                    trans_lines.append(lines[i].strip())
                translation = ' '.join(trans_lines[:20])  # Limit
            
            browser.close()
            
            print(f"✅ Extracted - Dev: {bool(devanagari)}, San: {bool(sanskrit)}, Syn: {bool(synonyms)}, Trans: {bool(translation)}")
            
            return {
                'devanagari_verse': devanagari.strip(),
                'sanskrit_verse': sanskrit.strip(),
                'word_meanings': synonyms.strip(),
                'translation': translation.strip(),
                'purport': purport,
                'source': 'vedabase.io (fetched)'
            }
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

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
        
        # Try database first
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT devanagari_verse, sanskrit_verse, word_meanings, translation, purport FROM verses WHERE canto=? AND chapter=? AND verse=?',
                  (canto, chapter, verse))
        result = c.fetchone()
        conn.close()
        
        if result:
            print("✅ From database")
            return jsonify({
                'success': True,
                'reference': f'SB {canto}.{chapter}.{verse}',
                'devanagari_verse': result[0] or '',
                'sanskrit_verse': result[1] or '',
                'word_meanings': result[2] or '',
                'translation': result[3] or '',
                'purport': result[4] or '',
                'url': f'https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/',
                'source': 'database (cached)'
            })
        
        # Fetch from web
        web_result = fetch_from_vedabase(canto, chapter, verse)
        
        if web_result:
            # Save to DB
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('INSERT OR REPLACE INTO verses VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                          (canto, chapter, verse, web_result['devanagari_verse'], 
                           web_result['sanskrit_verse'], web_result['word_meanings'],
                           web_result['translation'], web_result['purport']))
                conn.commit()
                conn.close()
            except:
                pass
            
            return jsonify({
                'success': True,
                'reference': f'SB {canto}.{chapter}.{verse}',
                **web_result,
                'url': f'https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/'
            })
        
        return jsonify({'success': False, 'error': 'Could not fetch verse'})
        
    except Exception as e:
        print(f"❌ Route error: {e}")
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    init_db()
    print("="*70)
    print("🕉️  Srimad Bhagavatam Verse Finder")
    print("="*70)
    #app.run(debug=True, host='0.0.0.0', port=5019)
    port = int(os.environ.get('PORT', 5019))
    app.run(host='0.0.0.0', port=port)
