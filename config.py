"""
Configuration file for Srimad Bhagavatam Verse Finder
Modify these settings to customize the application
"""

# Server Configuration
HOST = '0.0.0.0'  # Listen on all network interfaces (use '127.0.0.1' for localhost only)
PORT = 5000       # Port number (change if 5000 is already in use)
DEBUG = True      # Set to False in production

# Request Configuration
REQUEST_TIMEOUT = 10  # Timeout for web requests in seconds
MAX_RETRIES = 3       # Number of retries for failed requests

# User Agent (browser identifier)
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Base URL for vedabase.io
BASE_URL = 'https://vedabase.io/en/library/sb'

# Display Configuration
SHOW_SANSKRIT = True      # Display Sanskrit verse
SHOW_WORD_MEANINGS = True # Display word-for-word meanings
SHOW_TRANSLATION = True   # Display English translation
SHOW_PURPORT = True       # Display purport/explanation

# Cache Configuration (for future implementation)
ENABLE_CACHE = False      # Enable caching of fetched verses
CACHE_DURATION = 3600     # Cache duration in seconds (1 hour)

# Rate Limiting (for future implementation)
ENABLE_RATE_LIMIT = False # Enable rate limiting
REQUESTS_PER_MINUTE = 30  # Maximum requests per minute

# Logging Configuration
LOG_LEVEL = 'INFO'        # Options: DEBUG, INFO, WARNING, ERROR
LOG_FILE = 'app.log'      # Log file name (None to disable file logging)

# UI Configuration
THEME_COLOR = '#667eea'   # Primary color for the UI
SECONDARY_COLOR = '#764ba2' # Secondary color for gradients

# API Response Configuration
INCLUDE_URL = True        # Include source URL in response
INCLUDE_METADATA = True   # Include metadata like timestamp
