#!/bin/bash

# Śrīmad-Bhāgavatam Verse Finder - Quick Start Script

echo "🕉️  Śrīmad-Bhāgavatam Verse Finder"
echo "=================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null
then
    echo "❌ Python 3 is not installed. Please install Python 3.7 or higher."
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo "✅ Dependencies installed successfully"
echo ""

# Ask user which mode to run
echo "Choose mode:"
echo "1. Web App (Browser-based UI)"
echo "2. CLI (Command-line interface)"
echo ""
read -p "Enter choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
    echo ""
    echo "🚀 Starting web server..."
    echo "🌐 Open your browser and go to: http://localhost:5000"
    echo "⏸️  Press Ctrl+C to stop the server"
    echo ""
    python3 app.py
elif [ "$choice" = "2" ]; then
    echo ""
    read -p "Enter Canto (1-12): " canto
    read -p "Enter Chapter: " chapter
    read -p "Enter Verse: " verse
    echo ""
    python3 fetch_verse_cli.py "$canto" "$chapter" "$verse"
else
    echo "❌ Invalid choice"
    exit 1
fi
