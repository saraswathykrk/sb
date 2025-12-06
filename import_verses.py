import sqlite3
import csv

# If you have CSV with verses
conn = sqlite3.connect('srimad_bhagavatam.db')
c = conn.cursor()

# Import from CSV
with open('verses.csv', 'r') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    for row in reader:
        c.execute('INSERT OR REPLACE INTO verses VALUES (?, ?, ?, ?, ?, ?, ?)', row)

conn.commit()
conn.close()
