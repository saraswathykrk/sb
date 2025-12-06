from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

def fetch_verse(canto, chapter, verse):
    """
    Fetch verse and meaning from vedabase.io
    """
    try:
        url = f"https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/"
        
        # Headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract verse reference
        verse_ref = f"SB {canto}.{chapter}.{verse}"
        
        # Extract Sanskrit verse
        sanskrit_verse = ""
        verse_elements = soup.find_all('p', class_='verse')
        if verse_elements:
            sanskrit_verse = '\n'.join([v.get_text(strip=True) for v in verse_elements])
        
        # Alternative: Look for verse in different structure
        if not sanskrit_verse:
            verse_div = soup.find('div', class_='verse')
            if verse_div:
                sanskrit_verse = verse_div.get_text(strip=True)
        
        # Extract word-for-word meanings
        word_meanings = ""
        synonyms = soup.find('p', class_='synonyms')
        if synonyms:
            word_meanings = synonyms.get_text(strip=True)
        
        # Extract translation
        translation = ""
        translation_elem = soup.find('p', class_='translation')
        if translation_elem:
            translation = translation_elem.get_text(strip=True)
        
        # Extract purport/meaning
        purport = ""
        purport_elem = soup.find('div', class_='purport')
        if purport_elem:
            # Get all paragraphs in purport
            paragraphs = purport_elem.find_all('p')
            purport = '\n\n'.join([p.get_text(strip=True) for p in paragraphs])
        
        # If specific classes don't work, try generic extraction
        if not sanskrit_verse and not translation:
            # Look for the verse text in the page
            all_paragraphs = soup.find_all('p')
            for i, p in enumerate(all_paragraphs):
                text = p.get_text(strip=True)
                # Sanskrit verses usually contain diacritical marks
                if any(char in text for char in ['ā', 'ī', 'ū', 'ṛ', 'ṁ', 'ḥ', 'ṅ', 'ñ', 'ṭ', 'ḍ', 'ṇ', 'ś', 'ṣ']):
                    if len(text) < 500 and not sanskrit_verse:  # Likely the verse
                        sanskrit_verse = text
                    elif i > 0 and len(text) > 100:  # Likely translation or purport
                        if not translation:
                            translation = text
                        elif not purport:
                            purport = text
        
        result = {
            'success': True,
            'reference': verse_ref,
            'sanskrit_verse': sanskrit_verse,
            'word_meanings': word_meanings,
            'translation': translation,
            'purport': purport,
            'url': url
        }
        
        return result
        
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': f"Error fetching data: {str(e)}"
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Error parsing data: {str(e)}"
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
    
    result = fetch_verse(canto, chapter, verse)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5019)
