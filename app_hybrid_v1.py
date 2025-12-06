from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright
import sqlite3
import os
import time
import re

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

def extract_section_content(text, heading):
    """Extract content that appears after a specific heading"""
    # Split by the heading
    pattern = f"{heading}\\s*\\n(.+?)(?=\\n[A-Z][a-z]+\\s*\\n|$)"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""

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
            time.sleep(3)
            
            # Get the full page text
            full_text = page.inner_text('body')
            
            # Extract sections based on headings
            sanskrit_verse = ""
            word_meanings = ""
            translation = ""
            purport = ""
            
            # Look for "Verse text" section
            verse_match = re.search(r'Verse text\s*\n(.+?)(?=\nSynonyms|\nTranslation|$)', full_text, re.DOTALL)
            if verse_match:
                sanskrit_verse = verse_match.group(1).strip()
                print(f"✅ Found verse text: {sanskrit_verse[:50]}...")
            
            # Look for "Synonyms" section
            synonyms_match = re.search(r'Synonyms\s*\n(.+?)(?=\nTranslation|\nPurport|$)', full_text, re.DOTALL)
            if synonyms_match:
                word_meanings = synonyms_match.group(1).strip()
                print(f"✅ Found synonyms: {word_meanings[:50]}...")
            
            # Look for "Translation" section
            translation_match = re.search(r'Translation\s*\n(.+?)(?=\nPurport|Text \d+|$)', full_text, re.DOTALL)
            if translation_match:
                translation = translation_match.group(1).strip()
                print(f"✅ Found translation: {translation[:50]}...")
            
            # Look for "Purport" section
            purport_match = re.search(r'Purport\s*\n(.+?)(?=Text \d+|« Text \d+|$)', full_text, re.DOTALL)
            if purport_match:
                purport = purport_match.group(1).strip()
                # Clean up the purport - remove navigation text at the end
                purport = re.sub(r'« Text \d+.*$', '', purport, flags=re.DOTALL).strip()
                print(f"✅ Found purport: {purport[:50]}...")
            
            browser.close()
            
            # Save to database if we got something
            if sanskrit_verse or translation:
                save_to_database(canto, chapter, verse, sanskrit_verse, 
                               word_meanings, translation, purport)
                print(f"💾 Saved to database: SB {canto}.{chapter}.{verse}")
            else:
                print(f"⚠️ No content extracted for SB {canto}.{chapter}.{verse}")
            
            return {
                'sanskrit_verse': sanskrit_verse,
                'word_meanings': word_meanings,
                'translation': translation,
                'purport': purport,
                'source': 'vedabase.io (fetched)'
            }
            
    except Exception as e:
        print(f"❌ Error fetching from vedabase: {str(e)}")
        import traceback
        traceback.print_exc()
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
    
    return {
        'success': False,
        'error': f'Could not fetch verse {verse_ref}. Please try again.'
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
    print("🕉️  HYBRID Srimad Bhagavatam Verse Finder (FIXED)")
    print("="*70)
    print("📊 Features:")
    print("  • Instant results from database (cached verses)")
    print("  • Auto-fetch from vedabase.io (new verses)")
    print("  • Auto-save fetched verses for future use")
    print("  • Fixed extraction using regex patterns")
    print("="*70)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5019)
