import os
import json
import sqlite3
import urllib.request
import urllib.error
import time
import feedparser
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("VIRHE: GEMINI_API_KEY puuttuu! Aja ensin: export GEMINI_API_KEY='sinun_avaimesi'")
    exit()

conn = sqlite3.connect("uutiset.db")
cursor = conn.cursor()

# Luodaan taulukko ja varmistetaan alue-sarake
cursor.execute('''
    CREATE TABLE IF NOT EXISTS uutisolio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        otsikko TEXT UNIQUE,
        pvm TEXT,
        lahde TEXT,
        alue TEXT,
        kriisi_indeksi REAL
    )
''')

try:
    cursor.execute("ALTER TABLE uutisolio ADD COLUMN alue TEXT")
except sqlite3.OperationalError:
    pass

conn.commit()

alueet_syotteet = {
    "Europe": "https://news.google.com/rss/search?q=geopolitics+crisis+Europe&hl=en-US&gl=US&ceid=US:en",
    "Asia": "https://news.google.com/rss/search?q=geopolitics+crisis+Asia&hl=en-US&gl=US&ceid=US:en",
    "Middle East": "https://news.google.com/rss/search?q=geopolitics+crisis+Middle+East&hl=en-US&gl=US&ceid=US:en",
    "North America": "https://news.google.com/rss/search?q=geopolitics+crisis+North+America&hl=en-US&gl=US&ceid=US:en",
    "Africa": "https://news.google.com/rss/search?q=geopolitics+crisis+Africa&hl=en-US&gl=US&ceid=US:en"
}

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"

print("=== ALOITETAAN KRIISIANALYYSI ===\n")

uudet_yhteensa = 0
vanhat_yhteensa = 0

for alue, rss_url in alueet_syotteet.items():
    feed = feedparser.parse(rss_url)
    uutiset = feed.entries
    yhteensa_alueella = len(uutiset)
    
    uudet_alueella = 0
    vanhat_alueella = 0
    
    print(f"\n--- Alue: {alue} ({yhteensa_alueella} uutista) ---")

    for i, entry in enumerate(uutiset, 1):
        otsikko = entry.title
        
        # Jäsennetään julkaisupäivämäärä
        pvm_raaka = getattr(entry, 'published', None)
        if pvm_raaka:
            try:
                dt = parsedate_to_datetime(pvm_raaka)
                pvm_pvm = dt.strftime('%Y-%m-%d')
            except Exception:
                pvm_pvm = datetime.now().strftime('%Y-%m-%d')
        else:
            pvm_pvm = datetime.now().strftime('%Y-%m-%d')

        cursor.execute("SELECT id FROM uutisolio WHERE otsikko = ?", (otsikko,))
        if cursor.fetchone():
            vanhat_alueella += 1
            vanhat_yhteensa += 1
            print(f"[{i}/{yhteensa_alueella}] [OHITETTU - Kannassa]: {otsikko[:40]}...")
            continue

        prompt = f"Olet kriisianalyytikko. Arvioi uutisen vakavuus asteikolla 1.0-10.0 (1.0=normaali, 10.0=sota/katastrofi). Otsikko: '{otsikko}'. Palauta AINOASTAAN pelkkä numero."
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        
        for yritys in range(2):
            try:
                req = urllib.request.Request(
                    url, 
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    vastaus_teksti = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    kriisi_pisteet = float(vastaus_teksti)
                    
                    cursor.execute('''
                        INSERT INTO uutisolio (otsikko, pvm, lahde, alue, kriisi_indeksi)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (otsikko, pvm_pvm, "Google News", alue, kriisi_pisteet))
                    conn.commit()
                    
                    uudet_alueella += 1
                    uudet_yhteensa += 1
                    print(f"[{i}/{yhteensa_alueella}] [UUSI ({pvm_pvm}) - {kriisi_pisteet}]: {otsikko[:35]}...")
                    time.sleep(0.2)
                    break
                    
            except urllib.error.HTTPError as e:
                if e.code in [503, 429]:
                    time.sleep(1)
                else:
                    break
            except Exception:
                break

    print(f"-> {alue} valmis: {uudet_alueella} uutta, {vanhat_alueella} vanhaa.")

# --- AUTOMATISOITU SIIVOUS JA MUOTOILU ---
cursor.execute("SELECT id, pvm FROM uutisolio")
for rivi_id, pvm_str in cursor.fetchall():
    if pvm_str and "," in pvm_str:
        try:
            dt = parsedate_to_datetime(pvm_str)
            cursor.execute("UPDATE uutisolio SET pvm = ? WHERE id = ?", (dt.strftime('%Y-%m-%d'), rivi_id))
        except Exception:
            pass

# Poistetaan yli 90vrk vanhat
raja_pvm = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
cursor.execute("DELETE FROM uutisolio WHERE pvm < ?", (raja_pvm,))
conn.commit()

# --- TULOSTETAAN TAULUKKO ALUEEN KANSSA ---
print("\n" + "="*85)
print(f"AJON TULOKSET: {uudet_yhteensa} uutta | {vanhat_yhteensa} vanhaa | Kanta siivottu")
print("="*85)
print(f"{'ID':<5} | {'ALUE':<15} | {'INDEKSI':<8} | {'PVM':<10} | {'OTSIKKO'}")
print("="*85)

cursor.execute('''
    SELECT id, COALESCE(alue, 'Tuntematon'), kriisi_indeksi, pvm, otsikko 
    FROM uutisolio 
    ORDER BY id DESC 
    LIMIT 15
''')

for rivi in cursor.fetchall():
    u_id, u_alue, u_indeksi, u_pvm, u_otsikko = rivi
    print(f"{u_id:<5} | {u_alue:<15} | {u_indeksi:<8.1f} | {u_pvm:<10} | {u_otsikko[:35]}...")

print("="*85)

conn.close()
