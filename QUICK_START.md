# 🕉️ Quick Start Guide

Get started with the Śrīmad-Bhāgavatam Verse Finder in under 2 minutes!

## Super Quick Start (Easiest Way)

### For Linux/Mac:
```bash
cd /mnt/user-data/outputs/
./start.sh
```

### For Windows:
```cmd
cd \mnt\user-data\outputs
start.bat
```

That's it! The script will:
1. Install dependencies automatically
2. Ask you to choose between Web App or CLI mode
3. Launch the application

---

## Manual Start (If you prefer)

### Option 1: Web App (Recommended)

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt --break-system-packages
   ```

2. **Run the server:**
   ```bash
   python app.py
   ```

3. **Open browser:**
   - Go to: `http://localhost:5000`

4. **Use the app:**
   - Enter Canto, Chapter, Verse numbers
   - Click "Fetch Verse"
   - Enjoy! 🎉

### Option 2: CLI (Command Line)

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt --break-system-packages
   ```

2. **Run the CLI:**
   ```bash
   python fetch_verse_cli.py <canto> <chapter> <verse>
   ```

3. **Example:**
   ```bash
   python fetch_verse_cli.py 1 1 1
   ```

---

## First Verse to Try

Try the very first verse of Śrīmad-Bhāgavatam:

- **Canto:** 1
- **Chapter:** 1  
- **Verse:** 1

This is the famous opening verse:

> janmādy asya yato 'nvayād itarataś cārtheṣv abhijñaḥ svarāṭ
> tene brahma hṛdā ya ādi-kavaye muhyanti yat sūrayaḥ

---

## Popular Verses to Explore

Here are some popular verses to get you started:

| Verse | Description |
|-------|-------------|
| SB 1.1.1 | Opening invocation |
| SB 1.1.2 | The purpose of this scripture |
| SB 1.2.6 | Definition of real religion |
| SB 10.14.1 | Lord Brahmā's prayers |
| SB 10.8.13 | Mother Yaśodā and baby Krishna |

---

## Troubleshooting

### "Module not found" error?
```bash
pip install -r requirements.txt --break-system-packages
```

### Port 5000 already in use?
Edit `app.py` and change:
```python
app.run(debug=True, host='0.0.0.0', port=5001)  # Changed to 5001
```

### Getting 403 errors?
The website may be temporarily blocking requests. Wait a few minutes and try again.

---

## Next Steps

Once you're comfortable with the basics:

1. Read the full [README.md](README.md) for detailed documentation
2. Explore different Cantos and Chapters
3. Use the web interface for the best experience
4. Share verses with friends! 📚

---

## Files Overview

```
/mnt/user-data/outputs/
├── start.sh              # Quick start (Linux/Mac)
├── start.bat             # Quick start (Windows)
├── app.py               # Web server
├── fetch_verse_cli.py   # CLI version
├── templates/
│   └── index.html       # Web interface
├── requirements.txt      # Dependencies
├── README.md            # Full documentation
└── QUICK_START.md       # This file
```

---

## Need Help?

- Check the [README.md](README.md) for detailed information
- Make sure Python 3.7+ is installed
- Ensure you have internet connection (to fetch from vedabase.io)

---

**Happy exploring the wisdom of Śrīmad-Bhāgavatam! 🕉️**
