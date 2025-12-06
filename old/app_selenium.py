from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

app = Flask(__name__)

def get_driver():
    """Create headless Chrome driver"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def fetch_verse_selenium(canto, chapter, verse):
    """Fetch verse using Selenium"""
    driver = None
    try:
        url = f"https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/"
        
        driver = get_driver()
        driver.get(url)
        
        # Wait for page to load
        time.sleep(3)
        
        # Extract verse reference
        verse_ref = f"SB {canto}.{chapter}.{verse}"
        
        # Extract Sanskrit verse
        sanskrit_verse = ""
        try:
            verse_elements = driver.find_elements(By.CSS_SELECTOR, 'p.verse, div.verse')
            if verse_elements:
                sanskrit_verse = '\n'.join([elem.text for elem in verse_elements])
        except:
            pass
        
        # Extract word meanings
        word_meanings = ""
        try:
            synonyms = driver.find_element(By.CSS_SELECTOR, 'p.synonyms')
            word_meanings = synonyms.text
        except:
            pass
        
        # Extract translation
        translation = ""
        try:
            translation_elem = driver.find_element(By.CSS_SELECTOR, 'p.translation')
            translation = translation_elem.text
        except:
            pass
        
        # Extract purport
        purport = ""
        try:
            purport_elem = driver.find_element(By.CSS_SELECTOR, 'div.purport')
            paragraphs = purport_elem.find_elements(By.TAG_NAME, 'p')
            purport = '\n\n'.join([p.text for p in paragraphs])
        except:
            pass
        
        # Fallback: get all text if specific elements not found
        if not sanskrit_verse:
            page_text = driver.find_element(By.TAG_NAME, 'body').text
            # Extract verse from page text (basic extraction)
            lines = page_text.split('\n')
            for i, line in enumerate(lines):
                if any(char in line for char in ['ā', 'ī', 'ū', 'ṛ', 'ṁ', 'ḥ']):
                    if len(line) < 200 and not sanskrit_verse:
                        sanskrit_verse = line
        
        driver.quit()
        
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
        if driver:
            driver.quit()
        return {
            'success': False,
            'error': f"Error: {str(e)}"
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
    
    result = fetch_verse_selenium(canto, chapter, verse)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5019)
