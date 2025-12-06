#!/usr/bin/env python3
"""
Test script to verify the Srimad Bhagavatam Verse Finder installation
Run this to check if everything is working correctly
"""

import sys

print("🕉️  Testing Srimad Bhagavatam Verse Finder Installation")
print("=" * 70)
print()

# Test 1: Check Python version
print("Test 1: Checking Python version...")
if sys.version_info >= (3, 7):
    print(f"✅ PASS - Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
else:
    print(f"❌ FAIL - Python version too old. Need 3.7+, have {sys.version_info.major}.{sys.version_info.minor}")
    sys.exit(1)
print()

# Test 2: Check dependencies
print("Test 2: Checking required packages...")
required_packages = ['flask', 'requests', 'bs4']
missing_packages = []

for package in required_packages:
    try:
        __import__(package)
        print(f"✅ {package:15} - Installed")
    except ImportError:
        print(f"❌ {package:15} - Missing")
        missing_packages.append(package)

if missing_packages:
    print()
    print("⚠️  Missing packages detected!")
    print("Run: pip install -r requirements.txt --break-system-packages")
    sys.exit(1)
print()

# Test 3: Check file structure
print("Test 3: Checking file structure...")
import os

required_files = [
    'app.py',
    'fetch_verse_cli.py',
    'requirements.txt',
    'templates/index.html',
    'README.md',
    'QUICK_START.md'
]

missing_files = []
for file in required_files:
    if os.path.exists(file):
        print(f"✅ {file:30} - Found")
    else:
        print(f"❌ {file:30} - Missing")
        missing_files.append(file)

if missing_files:
    print()
    print("⚠️  Some files are missing!")
    sys.exit(1)
print()

# Test 4: Test imports
print("Test 4: Testing imports...")
try:
    from flask import Flask, render_template, request, jsonify
    print("✅ Flask imports - OK")
    import requests
    print("✅ Requests module - OK")
    from bs4 import BeautifulSoup
    print("✅ BeautifulSoup - OK")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
print()

# Test 5: Test basic Flask app
print("Test 5: Testing Flask app initialization...")
try:
    from flask import Flask
    test_app = Flask(__name__)
    print("✅ Flask app creation - OK")
except Exception as e:
    print(f"❌ Flask app creation failed: {e}")
    sys.exit(1)
print()

# Test 6: Test network connectivity
print("Test 6: Testing network connectivity...")
try:
    import requests
    response = requests.get('https://vedabase.io', timeout=5)
    if response.status_code in [200, 403, 301, 302]:
        print(f"✅ Network connection - OK (Status: {response.status_code})")
    else:
        print(f"⚠️  Network connection - Unexpected status: {response.status_code}")
except requests.exceptions.Timeout:
    print("⚠️  Network connection - Timeout (vedabase.io may be slow)")
except requests.exceptions.RequestException as e:
    print(f"⚠️  Network connection - Error: {e}")
print()

# Summary
print("=" * 70)
print("✅ All tests passed! Your installation is ready.")
print()
print("Next steps:")
print("1. Run the web app: python app.py")
print("2. Or use CLI: python fetch_verse_cli.py 1 1 1")
print("3. Or use quick start: ./start.sh")
print()
print("Happy exploring! 🕉️")
print("=" * 70)
