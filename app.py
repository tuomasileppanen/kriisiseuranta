import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Kriisianalysaattori", layout="wide")

st.title("🌐 Geopoliittinen Kriisiseuranta")

# --- SIVUPALKKI: INDEKSIN SELITTEET ---
st.sidebar.header("ℹ️ Kriisi-indeksin Asteikko")
st.sidebar.markdown("""
* **1.0 – 3.0 (Vihreä):** Normalisoitunut tilanne / Diplomatiaa.
* **3.1 – 5.0 (Keltainen):** Kohonnut jännite / Poliittista sanaharkkaa.
* **5.1 – 7.0 (Oranssi):** Vakava kriisi / Pakotteet / Rajamustelmia.
* **7.1 – 8.5 (Punainen):** Aseellinen konflikti / Laaja kriisi.
* **8.6 – 10.0 (Tummanpunainen):** Täysimittainen sota / Globaali katastrofi.
""")

st.sidebar.divider()

# --- TIETOKANNAN LUKU ---
conn = sqlite3.connect("uutiset.db")
df = pd.read_sql_query("SELECT * FROM uutisolio ORDER BY pvm DESC", conn)
conn.close()

if df.empty:
    st.warning("Tietokanta on tyhjä. Aja kriisi_analysaattori.py ensin.")
else:
    # Luodaan päivämäärä- ja viikkosarake (esim. 2026-W38)
    df['pvm_dt'] = pd.to_datetime(df['pvm'], errors='coerce')
    df['viikko'] = df['pvm_dt'].dt.strftime('%Y-W%V')

    # --- SIVUPALKKI: VIIKKOSUODATIN ---
    kaikki_viikot = sorted(df['viikko'].dropna().unique().tolist(), reverse=True)
    valittu_viikko = st.sidebar.selectbox("Valitse tarkasteltava viikko:", ["Kaikki viikot"] + kaikki_viikot)

    # Suodatetaan data valinnan mukaan
    if valittu_viikko != "Kaikki viikot":
        df_filtered = df[df['viikko'] == valittu_viikko]
    else:
        df_filtered = df.copy()

    # --- 1. TÄMÄN PÄIVÄN SPOT-TILANNE ---
    tanaan_str = datetime.now().strftime('%Y-%m-%d')
    df_tanaan = df[df['pvm'] == tanaan_str]

    st.subheader(f"⚡ Tämän päivän Spot-tilanne ({tanaan_str})")
    
    if not df_tanaan.empty:
        s_col1, s_col2, s_col3 = st.columns(3)
        spot_keskiarvo = df_tanaan['kriisi_indeksi'].mean()
        spot_max = df_tanaan['kriisi_indeksi'].max()
        spot_maara = len(df_tanaan)
        
        s_col1.metric("Tänään keskimäärin", f"{spot_keskiarvo:.2f} / 10")
        s_col2.metric("Tänään korkein piikki", f"{spot_max:.1f} / 10")
        s_col3.metric("Uutisia kirjattu tänään", f"{spot_maara} kpl")
        
        with st.expander("Näytä tämän päivän uutiset"):
            st.dataframe(df_tanaan[['pvm', 'alue', 'kriisi_indeksi', 'otsikko']], use_container_width=True, hide_index=True)
    else:
        st.info(f"Ei uutisia kirjattuna tälle päivälle ({tanaan_str}) vielä.")

    st.divider()

    # --- 2. YLÄRIVIN MITTARIT (Valittu viikko / Kaikki) ---
    st.subheader(f"📊 Tilannekuva: {valittu_viikko}")
    col1, col2, col3 = st.columns(3)
    
    keskiarvo = df_filtered['kriisi_indeksi'].mean()
    korkein = df_filtered['kriisi_indeksi'].max()
    uutisia_yht = len(df_filtered)
    
    col1.metric("Keskimääräinen Kriisi-indeksi", f"{keskiarvo:.2f} / 10" if pd.notnull(keskiarvo) else "N/A")
    col2.metric("Korkein Piikki", f"{korkein:.1f} / 10" if pd.notnull(korkein) else "N/A")
    col3.metric("Uutisia Valikoimassa", f"{uutisia_yht} kpl")

    st.divider()

    # --- VIIKKOTRENDI (VIIKKOKOHTAINEN KEHITYS) ---
    st.subheader("🗓️ Viikkokohtainen kriisitrendi (Kehitys viikoittain)")
    
    df_weekly = df.groupby(['viikko', 'alue'])['kriisi_indeksi'].mean().reset_index()
    
    fig_weekly = px.bar(
        df_weekly, 
        x='viikko', 
        y='kriisi_indeksi', 
        color='alue',
        barmode='group',
        labels={'viikko': 'Viikko', 'kriisi_indeksi': 'Keskiarvo (1-10)', 'alue': 'Alue'},
        title="Viikoittaiset keskiarvot alueittain"
    )
    st.plotly_chart(fig_weekly, use_container_width=True)

    st.divider()

    # --- PÄIVITTÄINEN TRENDI VALITULLA VIIKOLLA ---
    st.subheader("📈 Päivittäinen kehitys valitulla jaksolla")
    df_daily = df_filtered.groupby(['pvm', 'alue'])['kriisi_indeksi'].mean().reset_index()
    
    fig_line = px.line(
        df_daily, 
        x='pvm', 
        y='kriisi_indeksi', 
        color='alue',
        markers=True,
        labels={'pvm': 'Päivämäärä', 'kriisi_indeksi': 'Keskiarvo (1-10)', 'alue': 'Alue'},
        title="Päivittäiset pisteet"
    )
    fig_line.update_layout(hovermode="x unified")
    st.plotly_chart(fig_line, use_container_width=True)

    # --- OSALLISUUS JA KRIITTISET ---
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("📊 Alueiden vertailu")
        df_alue = df_filtered.groupby('alue')['kriisi_indeksi'].mean().reset_index().sort_values(by='kriisi_indeksi', ascending=False)
        fig_bar = px.bar(
            df_alue, 
            x='alue', 
            y='kriisi_indeksi', 
            color='kriisi_indeksi',
            color_continuous_scale='Reds',
            labels={'kriisi_indeksi': 'Keskiarvo'},
            title="Aluekohtainen keskiarvo"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_right:
        st.subheader("🔥 Vakavimmat uutiset (> 7.0)")
        kriittiset = df_filtered[df_filtered['kriisi_indeksi'] >= 7.0][['pvm', 'alue', 'kriisi_indeksi', 'otsikko']]
        st.dataframe(kriittiset, use_container_width=True, hide_index=True)

    # --- TAULUKKO ---
    with st.expander("Selaa kaikkia uutisia tietokannassa"):
        st.dataframe(df_filtered[['pvm', 'alue', 'kriisi_indeksi', 'otsikko']], use_container_width=True)
