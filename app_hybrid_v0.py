from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright
import sqlite3
import os
import time

app = Flask(__name__)
DB_PATH = 'srimad_bhagavatam.db'

def init_db():
    """Initialize database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS verses
                 (canto INTEGER, chapter INTEGER, verse INTEGER,
                  sanskrit_verse TEXT, word_meanings TEXT,
                  translation TEXT, purport TEXT,
                  fetched_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (canto, chapter, verse))''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized!")

def fetch_from_vedabase(canto, chapter, verse):
    """Fetch verse from vedabase.io using Playwright"""
    try:
        url = f"https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/"
        print(f"🔍 Fetching from vedabase.io: {url}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            page.goto(url, wait_until='networkidle')
            time.sleep(2)
            
            # Extract content
            sanskrit_verse = ""
            verse_elements = page.query_selector_all('p.verse, div.verse')
            if verse_elements:
                sanskrit_verse = '\n'.join([elem.inner_text() for elem in verse_elements])
            
            word_meanings = ""
            synonyms_elem = page.query_selector('p.synonyms')
            if synonyms_elem:
                word_meanings = synonyms_elem.inner_text()
            
            translation = ""
            translation_elem = page.query_selector('p.translation')
            if translation_elem:
                translation = translation_elem.inner_text()
            
            purport = ""
            purport_elem = page.query_selector('div.purport')
            if purport_elem:
                paragraphs = purport_elem.query_selector_all('p')
                purport = '\n\n'.join([p.inner_text() for p in paragraphs])
            
            browser.close()
            
            # Save to database for future use
            if sanskrit_verse or translation:
                save_to_database(canto, chapter, verse, sanskrit_verse, 
                               word_meanings, translation, purport)
                print(f"💾 Saved to database: SB {canto}.{chapter}.{verse}")
            
            return {
                'sanskrit_verse': sanskrit_verse,
                'word_meanings': word_meanings,
                'translation': translation,
                'purport': purport,
                'source': 'vedabase.io (fetched)'
            }
            
    except Exception as e:
        print(f"❌ Error fetching from vedabase: {str(e)}")
        return None

def get_from_database(canto, chapter, verse):
    """Try to get verse from local database first"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''SELECT sanskrit_verse, word_meanings, translation, purport
                     FROM verses WHERE canto=? AND chapter=? AND verse=?''',
                  (canto, chapter, verse))
        
        result = c.fetchone()
        conn.close()
        
        if result:
            print(f"✅ Found in database: SB {canto}.{chapter}.{verse}")
            return {
                'sanskrit_verse': result[0],
                'word_meanings': result[1],
                'translation': result[2],
                'purport': result[3],
                'source': 'database (cached)'
            }
        else:
            print(f"⚠️ Not in database: SB {canto}.{chapter}.{verse}")
            return None
            
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        return None

def save_to_database(canto, chapter, verse, sanskrit_verse, word_meanings, translation, purport):
    """Save verse to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''INSERT OR REPLACE INTO verses 
                     (canto, chapter, verse, sanskrit_verse, word_meanings, translation, purport)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (canto, chapter, verse, sanskrit_verse, word_meanings, translation, purport))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error saving to database: {str(e)}")
        return False

def fetch_verse_hybrid(canto, chapter, verse):
    """
    HYBRID APPROACH:
    1. Try database first (instant)
    2. If not found, fetch from vedabase.io
    3. Save fetched verse to database for next time
    """
    verse_ref = f"SB {canto}.{chapter}.{verse}"
    
    # Try database first
    db_result = get_from_database(canto, chapter, verse)
    if db_result:
        return {
            'success': True,
            'reference': verse_ref,
            'sanskrit_verse': db_result['sanskrit_verse'],
            'word_meanings': db_result['word_meanings'],
            'translation': db_result['translation'],
            'purport': db_result['purport'],
            'url': f'https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/',
            'source': db_result['source']
        }
    
    # Not in database, fetch from vedabase
    web_result = fetch_from_vedabase(canto, chapter, verse)
    if web_result:
        return {
            'success': True,
            'reference': verse_ref,
            'sanskrit_verse': web_result['sanskrit_verse'],
            'word_meanings': web_result['word_meanings'],
            'translation': web_result['translation'],
            'purport': web_result['purport'],
            'url': f'https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/',
            'source': web_result['source']
        }
    
    # Both failed
    return {
        'success': False,
        'error': f'Could not fetch verse {verse_ref}. Please check the numbers and try again.'
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch_verse', methods=['POST'])
def get_verse():
    data = request.json
    canto = data.get('canto')
    chapter = data.get('chapter')
    verse = data.get('verse')
    
    if not all([canto, chapter, verse]):
        return jsonify({
            'success': False,
            'error': 'Please provide canto, chapter, and verse numbers'
        })
    
    result = fetch_verse_hybrid(canto, chapter, verse)
    return jsonify(result)

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_db()
    
    print("="*70)
    print("🕉️  HYBRID Srimad Bhagavatam Verse Finder")
    print("="*70)
    print("📊 Features:")
    print("  • Instant results from database (cached verses)")
    print("  • Auto-fetch from vedabase.io (new verses)")
    print("  • Auto-save fetched verses for future use")
    print("="*70)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5019)
