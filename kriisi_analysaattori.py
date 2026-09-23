import os
import sqlite3
import feedparser
import yfinance as yf
from datetime import datetime
from google import genai
import urllib.parse

DB_NAME = "uutiset.db"

def luo_google_news_url(hakusana):
    encoded_query = urllib.parse.quote(hakusana)
    return f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

RSS_FEEDS = {
    "Amerikka (USA & Kanada)": [
        luo_google_news_url("US geopolitics conflict crisis"),
        luo_google_news_url("United States national security threat")
    ],
    "Kiina": [
        luo_google_news_url("China geopolitics military crisis"),
        luo_google_news_url("China economy trade war tensions")
    ],
    "Venäjä": [
        luo_google_news_url("Russia conflict war sanctions crisis"),
        luo_google_news_url("Russia military security policy")
    ],
    "Eurooppa": [
        luo_google_news_url("Europe security crisis conflict"),
        luo_google_news_url("European Union geopolitical risk")
    ],
    "Aasia (Muut)": [
        luo_google_news_url("Asia Pacific geopolitical tension conflict"),
        luo_google_news_url("Taiwan South China Sea crisis")
    ],
    "Etelä-Amerikka": [
        luo_google_news_url("South America crisis political unrest"),
        luo_google_news_url("Latin America economic political conflict")
    ],
    "Lähi-itä & Afrikka": [
        luo_google_news_url("Middle East conflict war crisis"),
        luo_google_news_url("Africa political crisis conflict")
    ],
    "Globaali Talous & Markkinat": [
        luo_google_news_url("global financial crisis inflation market crash"),
        luo_google_news_url("global supply chain crisis energy shortage")
    ]
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
            linkki TEXT UNIQUE,
            kriisi_indeksi INTEGER,
            analyysi TEXT
        )
    """)
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
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("VIRHE: GEMINI_API_KEY puuttuu!")
        return

    client = genai.Client(api_key=api_key)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    tanaan = datetime.now().strftime("%Y-%m-%d")

    for alue, feed_list in RSS_FEEDS.items():
        for url in feed_list:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:3]:
                otsikko = entry.get("title", "")
                kuvaus = entry.get("summary", "")
                linkki = entry.get("link", "")
                
                if not linkki:
                    continue
                
                cursor.execute("SELECT id FROM uutiset WHERE linkki = ?", (linkki,))
                if cursor.fetchone():
                    continue

                prompt = (
                    f"Analysoi seuraava uutinen geopoliittisen ja globaalin taloudellisen epävakauden näkökulmasta. "
                    f"Anna sille kriisi-indeksi kokonaislukuna väliltä 1 (rauhallinen) ja 10 (kriisi/sota). "
                    f"Vastaa muodossa: 'INDEKSI: [numero]\nANALYYSI: [perustelu]'.\n\n"
                    f"Otsikko: {otsikko}\nKuvaus: {kuvaus}"
                )

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
                        INSERT OR IGNORE INTO uutiset (paivays, alue, otsikko, kuvaus, linkki, kriisi_indeksi, analyysi)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (tanaan, alue, otsikko, kuvaus, linkki, indeksi, analyysi))
                    conn.commit()
                except Exception as e:
                    print(f"Virhe analyysissä: {e}")

    conn.close()

def paivita_markkinat():
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
            hist = t.history(period="1mo")
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
        except Exception:
            pass
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    alusta_tietokanta()
    paivita_markkinat()
    hae_ja_analysoi_uutiset()
