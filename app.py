import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(page_title="Geopoliittinen Kriisiseuranta", layout="wide")

st.title("🌍 Geopoliittinen Kriisiseuranta ja Markkinadata")

# Funktio tietokannan lataamiseen turvallisesti
def get_data():
    try:
        conn = sqlite3.connect('uutiset.db')
        # Haetaan tuoreimmat uutiset ilman tiukkaa päivämäärärajoitusta
        df_uutiset = pd.read_sql("SELECT * FROM uutiset ORDER BY id DESC LIMIT 50", conn)
        
        # Tarkistetaan onko markkinat-taulua olemassa
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='markkinat'")
        if cursor.fetchone():
            df_markkinat = pd.read_sql("SELECT * FROM markkinat", conn)
        else:
            df_markkinat = pd.DataFrame()
            
        conn.close()
        return df_uutiset, df_markkinat
    except Exception as e:
        st.error(f"Virhe tietokannan luvussa: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_uutiset, df_markkinat = get_data()

# Sivupalkki
st.sidebar.header("Asetukset & Suodattimet")
aikataso = st.sidebar.selectbox("Aikataso", ["Päivä", "Viikko"])

if df_uutiset.empty:
    st.warning("Tietokannasta ei löytynyt vielä uutisia. Varmista, että GitHub Actions on ajanut analysaattorin vähintään kerran.")
else:
    # Yhteenveto / kriisi-indeksit
    st.subheader("📊 Viimeisimmät Kriisi-indeksit")
    
    latest_news = df_uutiset.head(5)
    
    col1, col2, col3 = st.columns(3)
    if not latest_news.empty:
        with col1:
            st.metric("Viimeisin Kriisi-indeksi", f"{latest_news.iloc[0]['kriisi_indeksi']} / 10", f"Alue: {latest_news.iloc[0]['alue']}")
        with col2:
            keskiarvo_indeksi = df_uutiset['kriisi_indeksi'].mean()
            st.metric("Keskimääräinen Indeksi", f"{keskiarvo_indeksi:.1f} / 10")
        with col3:
            st.metric("Analysoituja uutisia yhteensä", len(df_uutiset))

    # Markkinatiedot
    df_m_pivot = pd.DataFrame(columns=["aikaleima"])
    if not df_markkinat.empty and "paivays" in df_markkinat.columns:
        df_m = df_markkinat.copy()
        df_m["paivays"] = pd.to_datetime(df_m["paivays"], format="mixed", errors="coerce")
        
        if aikataso.startswith("Viikko"):
            df_m["aikaleima"] = df_m["paivays"].dt.to_period("W").dt.start_time.dt.strftime("%Y-%m-%d")
        else:
            df_m["aikaleima"] = df_m["paivays"].dt.strftime("%Y-%m-%d")
            
        df_m_agg = df_m.groupby(["aikaleima", "nimi"])["arvo"].mean().reset_index()
        df_m_pivot = df_m_agg.pivot(index="aikaleima", columns="nimi", values="arvo").reset_index()

    # Näytetään markkinakaavio jos dataa on
    if not df_m_pivot.empty:
        st.subheader("📈 Markkinakehitys")
        st.line_chart(df_m_pivot.set_index("aikaleima"))

    # Uutisvirta / listaus
    st.subheader("📰 Viimeisimmät Uutiset ja Analyysit")
    for index, row in df_uutiset.iterrows():
        indeksi_arvo = row.get('kriisi_indeksi', 'Ei määritelty')
        with st.expander(f"[{row['alue']}] Kriisi-indeksi: {indeksi_arvo}/10 — {row['otsikko']}"):
            st.write(f"**Päivämäärä:** {row['paivays']}")
            st.write(f"**Analyysi:** {row['analyysi']}")
            if 'linkki' in row and row['linkki']:
                st.markdown(f"[Lue alkuperäinen uutinen]({row['linkki']})")
