import os
import sqlite3
import feedparser
from google import genai
from google.genai import errors
import time
from datetime import datetime

# Haetaan API-avain ympäristömuuttujasta
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("VIRHE: GEMINI_API_KEY puuttuu!")
    exit(1)

client = genai.Client(api_key=api_key)

# Tietokannan alustus
def alusta_tietokanta():
    conn = sqlite3.connect('uutiset.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uutiset (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paivays TEXT,
            alue TEXT,
            otsikko TEXT,
            linkki TEXT,
            analyysi TEXT,
            kriisi_indeksi INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def luo_google_news_url(hakusana):
    import urllib.parse
    encoded_query = urllib.parse.quote(hakusana)
    return f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

RSS_FEEDS = {
    "Amerikka & USA": [
        luo_google_news_url("US geopolitics conflict crisis")
    ],
    "Kiina & Aasia": [
        luo_google_news_url("China geopolitics military crisis")
    ],
    "Venäjä & Itä-Eurooppa": [
        luo_google_news_url("Russia conflict war sanctions crisis")
    ],
    "Eurooppa": [
        luo_google_news_url("Europe security crisis conflict")
    ],
    "Globaali Talous": [
        luo_google_news_url("global financial crisis inflation market")
    ]
}

def analysoi_ja_tallenna():
    alusta_tietokanta()
    conn = sqlite3.connect('uutiset.db')
    cursor = conn.cursor()

    for alue, url_listatyrot in RSS_FEEDS.items():
        print(f"Käsitellään aluetta: {alue}")
        for url in url_listatyrot:
            feed = feedparser.parse(url)
            # Otetaan max 3 tuoreinta per syöte, jotta pysytään rajoissa
            for entry in feed.entries[:3]:
                otsikko = entry.get('title', 'Ei otsikkoa')
                linkki = entry.get('link', '')
                
                # Tarkistetaan onko uutinen jo kannassa
                cursor.execute("SELECT id FROM uutiset WHERE linkki = ?", (linkki,))
                if cursor.fetchone():
                    continue # Ohitetaan jos löytyy jo
                
                prompt = f"""
                Analysoi seuraava uutinen geopoliittisen kriisin tai markkinariskin näkökulmasta:
                Otsikko: {otsikko}
                
                Anna vastauksena:
                1. Lyhyt analyysi suomeksi (max 2 virkettä).
                2. Kriisi-indeksi kokonaislukuna asteikolla 1-10 (jossa 1 on normaali tilanne ja 10 on globaali kriisi).
                
                Muotoile vastaus tarkasti näin:
                ANALYYSI: [tähän lyhyt analyysi]
                INDEKSI: [tähän numero 1-10]
                """

                try:
                    # Käytetään tuettua ja päivitettyä mallia
                    response = client.models.generate_content(
                        model='gemini-3.6-flash',
                        contents=prompt,
                    )
                    vastaus_teksti = response.text
                    
                    # Parsitaan vastaus
                    analyysi = "Ei analyysiä"
                    indeksi = 5
                    
                    for rivi in vastaus_teksti.split('\n'):
                        if rivi.startswith("ANALYYSI:"):
                            analyysi = rivi.replace("ANALYYSI:", "").strip()
                        elif rivi.startswith("INDEKSI:"):
                            try:
                                indeksi = int(rivi.replace("INDEKSI:", "").strip())
                            except ValueError:
                                indeksi = 5

                    paivays = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    cursor.execute('''
                        INSERT INTO uutiset (paivays, alue, otsikko, linkki, analyysi, kriisi_indeksi)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (paivays, alue, otsikko, linkki, analyysi, indeksi))
                    conn.commit()
                    print(f"Tallennettu: {otsikko} (Indeksi: {indeksi})")

                    # Tauko pyyntöjen välissä, ettei Free Tier -rajoitus (429) pauku
                    time.sleep(12)

                except Exception as e:
                    print(f"Virhe analyysissä ({alue}): {e}")
                    time.sleep(15) # Pidempi tauko virhetilanteessa

    conn.close()

if __name__ == "__main__":
    analysoi_ja_tallenna()
