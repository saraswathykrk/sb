from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright
import time

app = Flask(__name__)

def fetch_verse_playwright(canto, chapter, verse):
    """Fetch verse using Playwright"""
    try:
        url = f"https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/"
        
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            # Go to URL
            page.goto(url, wait_until='networkidle')
            time.sleep(2)  # Extra wait for dynamic content
            
            # Extract verse reference
            verse_ref = f"SB {canto}.{chapter}.{verse}"
            
            # Extract Sanskrit verse
            sanskrit_verse = ""
            verse_elements = page.query_selector_all('p.verse, div.verse')
            if verse_elements:
                sanskrit_verse = '\n'.join([elem.inner_text() for elem in verse_elements])
            
            # Extract word meanings
            word_meanings = ""
            synonyms_elem = page.query_selector('p.synonyms')
            if synonyms_elem:
                word_meanings = synonyms_elem.inner_text()
            
            # Extract translation
            translation = ""
            translation_elem = page.query_selector('p.translation')
            if translation_elem:
                translation = translation_elem.inner_text()
            
            # Extract purport
            purport = ""
            purport_elem = page.query_selector('div.purport')
            if purport_elem:
                paragraphs = purport_elem.query_selector_all('p')
                purport = '\n\n'.join([p.inner_text() for p in paragraphs])
            
            # Fallback extraction
            if not sanskrit_verse:
                body_text = page.query_selector('body').inner_text()
                lines = body_text.split('\n')
                for line in lines:
                    if any(char in line for char in ['ā', 'ī', 'ū', 'ṛ', 'ṁ', 'ḥ']):
                        if len(line) < 200 and not sanskrit_verse:
                            sanskrit_verse = line
                            break
            
            browser.close()
            
            return {
                'success': True,
                'reference': verse_ref,
                'sanskrit_verse': sanskrit_verse,
                'word_meanings': word_meanings,
                'translation': translation,
                'purport': purport,
                'url': url
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Error: {str(e)}'
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
    
    result = fetch_verse_playwright(canto, chapter, verse)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5019)
