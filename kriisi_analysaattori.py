import os
import sqlite3
import time
from datetime import datetime
import feedparser
import yfinance as yf
from google import genai
from google.genai import types

DB_NAME = "uutiset.db"

RSS_FEEDS = {
    "Suomi": "https://yle.fi/rss/uutiset/paauutiset",
    "Maailma": "https://www.iltalehti.fi/rss/uutiset.xml",
    "Talous": "https://www.mtvuutiset.fi/api/feed/rss/uutiset"
}

def alusta_tietokanta():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uutiset (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paivays TEXT,
            alue TEXT,
            otsikko TEXT,
            kuvaus TEXT,
            linkki TEXT,
            kriisi_indeksi INTEGER,
            analyysi TEXT
        )
    """)
    # Varmistetaan, että alue-sarake löytyy varmasti myös vanhasta kannasta
    try:
        cursor.execute("ALTER TABLE uutiset ADD COLUMN alue TEXT")
    except sqlite3.OperationalError:
        pass  # Sarake on jo olemassa

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS markkinat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paivays TEXT,
            nimi TEXT,
            arvo REAL,
            muutos_prosentti REAL
        )
    """)
    conn.commit()
    conn.close()

def hae_ja_analysoi_uutiset():
    print("Haetaan uutisia alueellisista/teemallisista RSS-syötteistä...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("VIRHE: GEMINI_API_KEY-ympäristömuuttuja puuttuu!")
        return

    client = genai.Client(api_key=api_key)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    tanaan = datetime.now().strftime("%Y-%m-%d")
    laskuri = 0

    for alue, feed_url in RSS_FEEDS.items():
        print(f"Käsitellään aluetta/teemaa: {alue}")
        parsed = feedparser.parse(feed_url)
        
        for entry in parsed.entries[:2]:
            otsikko = entry.get("title", "")
            kuvaus = entry.get("summary", "")
            linkki = entry.get("link", "")
            
            cursor.execute("SELECT id FROM uutiset WHERE linkki = ?", (linkki,))
            if cursor.fetchone():
                continue

            prompt = (
                f"Analysoi seuraava uutinen geopoliittisen ja globaalin taloudellisen epävakauden, kriisien tai uhkien näkökulmasta. "
                f"Anna sille kriisi-indeksi kokonaislukuna väliltä 1 (täysin rauhallinen / normaali) ja 10 (äärimmäinen kriisi/sota/romahtaminen). "
                f"Vastaa tarkalleen muodossa: 'INDEKSI: [numero]\nANALYYSI: [lyhyt suomenkielinen perustelu]'.\n\n"
                f"Otsikko: {otsikko}\nKuvaus: {kuvaus}"
            )

            for yritys in range(3):
                try:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt
                    )
                    vastaus_teksti = response.text
                    
                    indeksi = 1
                    analyysi = "Ei analyysiä."
                    for r in vastaus_teksti.split("\n"):
                        if "INDEKSI:" in r:
                            import re
                            numerot = re.findall(r'\d+', r)
                            if numerot:
                                indeksi = int(numerot[0])
                        elif "ANALYYSI:" in r:
                            analyysi = r.replace("ANALYYSI:", "").strip()

                    cursor.execute("""
                        INSERT INTO uutiset (paivays, alue, otsikko, kuvaus, linkki, kriisi_indeksi, analyysi)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (tanaan, alue, otsikko, kuvaus, linkki, indeksi, analyysi))
                    laskuri += 1
                    print(f"  -> [{alue}] Tallennettu: {otsikko[:40]}... (Indeksi: {indeksi})")
                    break
                except Exception as e:
                    if ("503" in str(e) or "429" in str(e)) and yritys < 2:
                        print(f"  -> Palvelinruuhka, odotetaan 5s ja yritetään uudelleen ({yritys+1}/3)...")
                        time.sleep(5)
                    else:
                        print(f"  -> Virhe Gemini-analyysissä: {e}")
                        break
            
            time.sleep(2)

    conn.commit()
    conn.close()
    print(f"Uutiset käsitelty. Tallennettu {laskuri} uutta uutista.")

def paivita_markkinat():
    print("Haetaan markkinatietoja (yfinance)...")
    tickers = {
        "^VIX": "VIX (Pelkomittari)",
        "^OMXH25": "OMX Helsinki 25",
        "^STOXX50E": "Euro Stoxx 50",
        "^N225": "Nikkei 225",
        "^GSPC": "S&P 500",
        "BZ=F": "Raakaöljy (Brent)",
        "GC=F": "Kulta"
    }

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    for ticker, nimi in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if not hist.empty:
                for index, row in hist.iterrows():
                    paivays = index.strftime("%Y-%m-%d")
                    arvo = float(row["Close"])
                    
                    cursor.execute("SELECT id FROM markkinat WHERE paivays = ? AND nimi = ?", (paivays, nimi))
                    if cursor.fetchone():
                        continue

                    cursor.execute("""
                        INSERT INTO markkinat (paivays, nimi, arvo, muutos_prosentti)
                        VALUES (?, ?, ?, ?)
                    """, (paivays, nimi, arvo, 0.0))
                print(f"  -> Tallennettu markkinatieto: {nimi}")
        except Exception as e:
            print(f"  -> Virhe haettaessa {nimi}: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    print("Kriisianalysaattori käynnistyy...")
    alusta_tietokanta()
    paivita_markkinat()
    hae_ja_analysoi_uutiset()
    print("Ajo valmis.")
