import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Geopoliittinen Kriisiseuranta", layout="wide")

st.title("🌍 Geopoliittinen Kriisiseuranta & Markkinaindikaattorit")
st.markdown("Päiväkohtaiset ja viikkotason keskiarvot: Kriisi-indeksi (pylväät) vs. Markkinaindikaattorit (trendiviivat).")

DB_NAME = "uutiset.db"

def lataa_tiedot():
    conn = sqlite3.connect(DB_NAME)
    try:
        df_uutiset = pd.read_sql("SELECT * FROM uutiset", conn)
    except Exception:
        df_uutiset = pd.DataFrame()
        
    try:
        df_markkinat = pd.read_sql("SELECT * FROM markkinat", conn)
    except Exception:
        df_markkinat = pd.DataFrame()
        
    conn.close()
    return df_uutiset, df_markkinat

df_uutiset, df_markkinat = lataa_tiedot()

if df_uutiset.empty and df_markkinat.empty:
    st.warning("Tietokanta on tyhjä. Aja ensin kriisi_analysaattori.py!")
else:
    st.sidebar.header("Asetukset")
    
    valittu_alue = "Kaikki"
    if not df_uutiset.empty and "alue" in df_uutiset.columns:
        alueet = ["Kaikki"] + list(df_uutiset["alue"].dropna().unique())
        valittu_alue = st.sidebar.selectbox("Valitse uutisten alue / teema", alueet)

    aikataso = st.sidebar.radio("Valitse tarkasteluaikaväli", ["Päivätaso", "Viikkotaso (keskiarvot)"])

    tab1, tab2 = st.tabs(["📈 Yhdistetty Kaavio & Taulukko", "📰 Viimeisimmät Analyysit"])

    with tab1:
        st.subheader("Kriisi-indeksi & Markkinatiedot rinnakkain (nuolilla varustettuna)")

        # 1. Käsitellään uutiset (Kriisi-indeksi)
        df_u_agg = pd.DataFrame(columns=["aikaleima", "Kriisi-indeksi"])
        if not df_uutiset.empty and "kriisi_indeksi" in df_uutiset.columns and "paivays" in df_uutiset.columns:
            df_u_filt = df_uutiset.copy()
            if valittu_alue != "Kaikki" and "alue" in df_u_filt.columns:
                df_u_filt = df_u_filt[df_u_filt["alue"] == valittu_alue]
            
            if not df_u_filt.empty:
                df_u_filt["paivays"] = pd.to_datetime(df_u_filt["paivays"], format="mixed", errors="coerce")
                if aikataso.startswith("Viikko"):
                    df_u_filt["aikaleima"] = df_u_filt["paivays"].dt.to_period("W").dt.start_time.dt.strftime("%Y-%m-%d")
                else:
                    df_u_filt["aikaleima"] = df_u_filt["paivays"].dt.strftime("%Y-%m-%d")
                    
                df_u_agg = df_u_filt.groupby("aikaleima")["kriisi_indeksi"].mean().reset_index()
                df_u_agg.rename(columns={"kriisi_indeksi": "Kriisi-indeksi"}, inplace=True)

        # 2. Käsitellään markkinatiedot
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

        # 3. Yhdistetään uutiset ja markkinat
        if not df_u_agg.empty and not df_m_pivot.empty:
            yhdistetty = pd.merge(df_u_agg, df_m_pivot, on="aikaleima", how="outer")
        elif not df_u_agg.empty:
            yhdistetty = df_u_agg
        else:
            yhdistetty = df_m_pivot

        if not yhdistetty.empty:
            yhdistetty = yhdistetty.sort_values("aikaleima").reset_index(drop=True)
            
            # Luodaan taulukko, jossa lukujen perässä on nuolet verrattuna edelliseen riviin
            yhdistetty_nuolilla = yhdistetty.copy()
            indikaattori_sarakkeet = [col for col in yhdistetty_nuolilla.columns if col != "aikaleima"]

            for col in indikaattori_sarakkeet:
                erotus = yhdistetty_nuolilla[col].diff()
                yhdistetty_nuolilla[col] = yhdistetty_nuolilla.apply(
                    lambda row: f"{row[col]:.2f} ➔" if pd.isna(erotus[row.name]) or erotus[row.name] == 0 
                    else (f"{row[col]:.2f} ↗" if erotus[row.name] > 0 else f"{row[col]:.2f} ↘"),
                    axis=1
                )

            st.markdown("### Taulukko: Indeksit ja muutokset nuolilla")
            st.dataframe(yhdistetty_nuolilla.set_index("aikaleima"), use_container_width=True)

            # 4. Piirretään Plotly-kaavio
            fig = go.Figure()

            if "Kriisi-indeksi" in yhdistetty.columns:
                fig.add_trace(go.Bar(
                    x=yhdistetty["aikaleima"],
                    y=yhdistetty["Kriisi-indeksi"],
                    name="Kriisi-indeksi (Uutiset)",
                    marker_color="indianred",
                    yaxis="y1"
                ))

            markkina_sarakkeet = [col for col in yhdistetty.columns if col not in ["aikaleima", "Kriisi-indeksi"]]
            
            for col in markkina_sarakkeet:
                fig.add_trace(go.Scatter(
                    x=yhdistetty["aikaleima"],
                    y=yhdistetty[col],
                    mode="lines+markers",
                    name=col,
                    yaxis="y2"
                ))

            fig.update_layout(
                title=f"Kriisi-indeksi (Pylväät) vs. Markkinaindikaattorit (Viivat) - {aikataso}",
                xaxis=dict(title="Aikaleima"),
                yaxis=dict(title="Kriisi-indeksi (1-10)", side="left", range=[0, 10]),
                yaxis2=dict(title="Markkina-arvo", overlaying="y", side="right", showgrid=False),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=50, r=50, t=80, b=50),
                height=550
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ei tarpeeksi yhdistettyä dataa taulukon tai kaavion piirtämiseen.")

    with tab2:
        st.subheader(f"Analyysit (Alue: {valittu_alue})")
        if not df_uutiset.empty:
            df_u_show = df_uutiset.copy()
            if valittu_alue != "Kaikki" and "alue" in df_u_show.columns:
                df_u_show = df_u_show[df_u_show["alue"] == valittu_alue]
                
            for index, row in df_u_show.iterrows():
                with st.expander(f"[{row.get('alue', 'Yleinen')}] {row.get('otsikko', '')} (Indeksi: {row.get('kriisi_indeksi', 1)}/10)"):
                    st.write(f"**Päiväys:** {row.get('paivays', '')}")
                    st.write(f"**Analyysi:** {row.get('analyysi', '')}")
                    st.markdown(f"[Lue alkuperäinen uutinen]({row.get('linkki', '#')})")
        else:
            st.info("Ei tallennettuja uutisia.")
