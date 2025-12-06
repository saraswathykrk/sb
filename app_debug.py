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
            time.sleep(3)  # Wait longer
            
            # DEBUG: Save page content
            page_content = page.content()
            with open('debug_page.html', 'w', encoding='utf-8') as f:
                f.write(page_content)
            print("📝 Saved page HTML to debug_page.html")
            
            # Try multiple selector strategies
            sanskrit_verse = ""
            word_meanings = ""
            translation = ""
            purport = ""
            
            # Strategy 1: Try specific classes
            try:
                verse_elements = page.query_selector_all('.verse')
                if verse_elements:
                    sanskrit_verse = '\n'.join([elem.inner_text() for elem in verse_elements])
                    print(f"✅ Found verse with .verse selector: {len(verse_elements)} elements")
            except Exception as e:
                print(f"❌ .verse selector failed: {e}")
            
            # Strategy 2: Look for any element with Sanskrit text
            if not sanskrit_verse:
                try:
                    all_text = page.inner_text('body')
                    print(f"📄 Page text length: {len(all_text)}")
                    print(f"📄 First 500 chars: {all_text[:500]}")
                    
                    # Look for Sanskrit characters
                    lines = all_text.split('\n')
                    for line in lines:
                        if any(char in line for char in ['ā', 'ī', 'ū', 'ṛ', 'ṁ', 'ḥ', 'ṅ', 'ñ', 'ṭ', 'ḍ', 'ṇ', 'ś', 'ṣ']):
                            if 50 < len(line) < 500 and not sanskrit_verse:
                                sanskrit_verse = line.strip()
                                print(f"✅ Found Sanskrit via character detection: {line[:50]}...")
                                break
                except Exception as e:
                    print(f"❌ Text extraction failed: {e}")
            
            # Strategy 3: Try common text patterns
            if not translation:
                try:
                    # Look for divs or paragraphs that might contain translation
                    all_paragraphs = page.query_selector_all('p, div')
                    for p in all_paragraphs:
                        text = p.inner_text().strip()
                        if len(text) > 100 and not any(char in text for char in ['ā', 'ī', 'ū', 'ṛ', 'ṁ', 'ḥ']):
                            if not translation:
                                translation = text
                                print(f"✅ Found potential translation: {text[:50]}...")
                                break
                except Exception as e:
                    print(f"❌ Translation extraction failed: {e}")
            
            # Get ALL text as fallback
            if not sanskrit_verse and not translation:
                full_text = page.inner_text('body')
                print("⚠️ Using full page text as fallback")
                return {
                    'sanskrit_verse': full_text[:1000],  # First 1000 chars
                    'word_meanings': "See full page",
                    'translation': full_text[1000:2000] if len(full_text) > 1000 else "",
                    'purport': "Check debug_page.html for full content",
                    'source': 'vedabase.io (fetched - debug mode)'
                }
            
            browser.close()
            
            # Save to database if we got something
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
    """HYBRID APPROACH with debug"""
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
        'error': f'Could not fetch verse {verse_ref}. Check debug_page.html for details.'
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
    print("🕉️  DEBUG MODE - Srimad Bhagavatam Verse Finder")
    print("="*70)
    print("📝 This version will save the page HTML to debug_page.html")
    print("="*70)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5019)
