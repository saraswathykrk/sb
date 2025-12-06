# Śrīmad-Bhāgavatam Verse Finder

A beautiful web application to fetch Srimad Bhagavatam verses and their meanings from vedabase.io.

## Features

- 🔍 Search verses by Canto, Chapter, and Verse number
- 📜 Display Sanskrit verses with diacritical marks
- 📖 Show word-for-word meanings
- 🌟 Display English translations
- 💡 Include purports/explanations
- 🎨 Beautiful, responsive UI
- 📱 Mobile-friendly design

## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

### Setup Steps

1. **Navigate to the project directory**
   ```bash
   cd /mnt/user-data/outputs/
   ```

2. **Install required packages**
   ```bash
   pip install -r requirements.txt
   ```
   
   Or install with --break-system-packages if needed:
   ```bash
   pip install -r requirements.txt --break-system-packages
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Open in browser**
   - Open your web browser
   - Go to: `http://localhost:5000`
   - Or if running on a server: `http://your-server-ip:5000`

## Usage

1. Enter the **Canto** number (1-12)
2. Enter the **Chapter** number
3. Enter the **Verse** number
4. Click "🔍 Fetch Verse"
5. View the verse, translation, and purport

### Example
- **Canto**: 1
- **Chapter**: 1
- **Verse**: 1

This will fetch the very first verse of Srimad Bhagavatam!

## URL Pattern

The app fetches data from vedabase.io using this URL pattern:
```
https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/
```

## Project Structure

```
/mnt/user-data/outputs/
├── app.py                 # Flask backend server
├── templates/
│   └── index.html        # Frontend HTML/CSS/JS
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## How It Works

1. **Backend (app.py)**
   - Flask web server
   - Web scraping using `requests` and `BeautifulSoup`
   - Parses HTML from vedabase.io
   - Extracts verse, translation, and purport
   - Returns JSON response

2. **Frontend (index.html)**
   - Beautiful gradient UI design
   - Form for user input
   - Async fetch to backend API
   - Dynamic content display
   - Responsive design for mobile

## API Endpoint

### POST /fetch_verse

**Request Body:**
```json
{
  "canto": 1,
  "chapter": 1,
  "verse": 1
}
```

**Response:**
```json
{
  "success": true,
  "reference": "SB 1.1.1",
  "sanskrit_verse": "...",
  "word_meanings": "...",
  "translation": "...",
  "purport": "...",
  "url": "https://vedabase.io/en/library/sb/1/1/1/"
}
```

## Troubleshooting

### Issue: Cannot connect to localhost:5000
**Solution**: Make sure the Flask app is running. Check if port 5000 is already in use.

### Issue: 403 Forbidden error
**Solution**: The website may be blocking requests. The app uses proper headers to mimic a browser, but vedabase.io may update their anti-scraping measures.

### Issue: Empty results
**Solution**: The HTML structure of vedabase.io may have changed. You may need to update the parsing logic in `app.py`.

### Issue: Module not found
**Solution**: Install the requirements:
```bash
pip install -r requirements.txt --break-system-packages
```

## Notes

- The app respects vedabase.io's content and provides attribution with source links
- Web scraping is used as vedabase.io doesn't provide an official API
- Please use responsibly and don't overload their servers
- Consider adding rate limiting for production use

## Future Enhancements

- [ ] Add caching to reduce server load
- [ ] Search by keywords
- [ ] Browse by Canto/Chapter structure
- [ ] Save favorite verses
- [ ] Export verses to PDF
- [ ] Multilingual support
- [ ] Offline database option

## License

This is a personal tool for accessing publicly available content from vedabase.io. 
Please respect their terms of service and copyright.

## Credits

- Content source: [Vedabase.io](https://vedabase.io)
- Translations by His Divine Grace A.C. Bhaktivedanta Swami Prabhupada
- Built with Flask, BeautifulSoup, and ❤️
# sb
