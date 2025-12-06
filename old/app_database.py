from flask import Flask, render_template, request, jsonify
import sqlite3
import os

app = Flask(__name__)
DB_PATH = 'srimad_bhagavatam.db'

def init_db():
    """Initialize database with sample verses"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS verses
                 (canto INTEGER, chapter INTEGER, verse INTEGER,
                  sanskrit_verse TEXT, word_meanings TEXT,
                  translation TEXT, purport TEXT,
                  PRIMARY KEY (canto, chapter, verse))''')
    
    # Add sample verses (you can add more!)
    sample_verses = [
        (1, 1, 1,
         'janmādy asya yato \'nvayād itarataś cārtheṣv abhijñaḥ svarāṭ\ntene brahma hṛdā ya ādi-kavaye muhyanti yat sūrayaḥ\ntejo-vāri-mṛdāṁ yathā vinimayo yatra tri-sargo \'mṛṣā\ndhāmnā svena sadā nirasta-kuhakaṁ satyaṁ paraṁ dhīmahi',
         'janma-ādi — creation, etc.; asya — of this (universe); yataḥ — from whom; anvayāt — directly; itarataḥ — indirectly; ca — and; artheṣu — purposes; abhijñaḥ — fully cognizant; sva-rāṭ — independent; tene — imparted; brahma — the Vedic knowledge; hṛdā — through the heart; yaḥ — who; ādi-kavaye — unto the original created being; muhyanti — are bewildered; yat — about whom; sūrayaḥ — great sages; tejaḥ-vāri-mṛdām — fire, water and earth; yathā — as; vinimayaḥ — action and reaction; yatra — whereupon; tri-sargaḥ — three modes of creation; amṛṣā — almost factual; dhāmnā — along with all transcendental paraphernalia; svena — self-sufficiently; sadā — always; nirasta — negation; kuhakam — illusion; satyam — truth; param — absolute; dhīmahi — let us meditate upon.',
         'O my Lord, Śrī Kṛṣṇa, son of Vasudeva, O all-pervading Personality of Godhead, I offer my respectful obeisances unto You. I meditate upon Lord Śrī Kṛṣṇa because He is the Absolute Truth and the primeval cause of all causes of the creation, sustenance and destruction of the manifested universes.',
         'Obeisances unto the Personality of Godhead, Vāsudeva, directly indicate Lord Śrī Kṛṣṇa, who is the divine son of Vasudeva and Devakī. This is confirmed by the Bhagavad-gītā.')
    ]
    
    for verse in sample_verses:
        c.execute('''INSERT OR REPLACE INTO verses 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''', verse)
    
    conn.commit()
    conn.close()
    print("Database initialized!")

def fetch_verse_db(canto, chapter, verse):
    """Fetch verse from local database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''SELECT sanskrit_verse, word_meanings, translation, purport
                     FROM verses WHERE canto=? AND chapter=? AND verse=?''',
                  (canto, chapter, verse))
        
        result = c.fetchone()
        conn.close()
        
        if result:
            return {
                'success': True,
                'reference': f"SB {canto}.{chapter}.{verse}",
                'sanskrit_verse': result[0],
                'word_meanings': result[1],
                'translation': result[2],
                'purport': result[3],
                'url': f'https://vedabase.io/en/library/sb/{canto}/{chapter}/{verse}/'
            }
        else:
            return {
                'success': False,
                'error': f'Verse SB {canto}.{chapter}.{verse} not found in database. Please add it first.'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Database error: {str(e)}'
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
    
    result = fetch_verse_db(canto, chapter, verse)
    return jsonify(result)

@app.route('/add_verse', methods=['POST'])
def add_verse():
    """API to add new verses to database"""
    data = request.json
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''INSERT OR REPLACE INTO verses 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (data['canto'], data['chapter'], data['verse'],
                   data['sanskrit_verse'], data['word_meanings'],
                   data['translation'], data['purport']))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Verse added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    # Initialize database if it doesn't exist
    if not os.path.exists(DB_PATH):
        init_db()
    
    app.run(debug=True, host='0.0.0.0', port=5019)
