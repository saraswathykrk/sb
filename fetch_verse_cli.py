#!/usr/bin/env python3
"""
Standalone CLI script to fetch Srimad Bhagavatam verses from vedabase.io
Usage: python fetch_verse_cli.py <canto> <chapter> <verse>
Example: python fetch_verse_cli.py 1 1 1
"""

import sys
import requests
from bs4 import BeautifulSoup

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
        
        print(f"\n🔍 Fetching verse from: {url}")
        print("⏳ Please wait...\n")
        
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
            paragraphs = purport_elem.find_all('p')
            purport = '\n\n'.join([p.get_text(strip=True) for p in paragraphs])
        
        # If specific classes don't work, try generic extraction
        if not sanskrit_verse and not translation:
            all_paragraphs = soup.find_all('p')
            for i, p in enumerate(all_paragraphs):
                text = p.get_text(strip=True)
                if any(char in text for char in ['ā', 'ī', 'ū', 'ṛ', 'ṁ', 'ḥ', 'ṅ', 'ñ', 'ṭ', 'ḍ', 'ṇ', 'ś', 'ṣ']):
                    if len(text) < 500 and not sanskrit_verse:
                        sanskrit_verse = text
                    elif i > 0 and len(text) > 100:
                        if not translation:
                            translation = text
                        elif not purport:
                            purport = text
        
        # Display results
        print("=" * 80)
        print(f"📚 {verse_ref}")
        print("=" * 80)
        
        if sanskrit_verse:
            print("\n📜 SANSKRIT VERSE")
            print("-" * 80)
            print(sanskrit_verse)
        
        if word_meanings:
            print("\n📖 WORD-FOR-WORD MEANINGS")
            print("-" * 80)
            print(word_meanings)
        
        if translation:
            print("\n🌟 TRANSLATION")
            print("-" * 80)
            print(translation)
        
        if purport:
            print("\n💡 PURPORT")
            print("-" * 80)
            print(purport)
        
        print("\n" + "=" * 80)
        print(f"📍 Source: {url}")
        print("=" * 80)
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error parsing data: {str(e)}")
        return False

def main():
    """
    Main function to handle CLI arguments
    """
    # Check arguments
    if len(sys.argv) != 4:
        print("\n🕉️  Śrīmad-Bhāgavatam Verse Fetcher (CLI)")
        print("=" * 80)
        print("\nUsage: python fetch_verse_cli.py <canto> <chapter> <verse>")
        print("\nExamples:")
        print("  python fetch_verse_cli.py 1 1 1    # First verse of SB")
        print("  python fetch_verse_cli.py 10 14 1  # First verse of 10th Canto, Chapter 14")
        print("\nArguments:")
        print("  canto   : Canto number (1-12)")
        print("  chapter : Chapter number")
        print("  verse   : Verse number")
        print("=" * 80)
        sys.exit(1)
    
    try:
        canto = int(sys.argv[1])
        chapter = int(sys.argv[2])
        verse = int(sys.argv[3])
        
        # Validate canto
        if canto < 1 or canto > 12:
            print("❌ Error: Canto must be between 1 and 12")
            sys.exit(1)
        
        # Validate chapter and verse
        if chapter < 1 or verse < 1:
            print("❌ Error: Chapter and verse must be positive numbers")
            sys.exit(1)
        
        # Fetch and display verse
        success = fetch_verse(canto, chapter, verse)
        
        if success:
            print("\n✅ Verse fetched successfully!\n")
        else:
            print("\n❌ Failed to fetch verse. Please try again.\n")
            sys.exit(1)
            
    except ValueError:
        print("❌ Error: Canto, chapter, and verse must be valid numbers")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(0)

if __name__ == "__main__":
    main()
