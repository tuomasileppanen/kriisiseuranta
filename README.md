# Geopoliittinen Kriisiseuranta (MVP)

Tämä on automatisoitu, pilvipalvelussa pyörivä geopoliittisen kriisitilanteen seurantajärjestelmä. Järjestelmä kerää uutisia RSS-syötteistä, analysoi ne tekoälyn (Google Gemini) avulla kriisi-indeksillä (1–10) varustettuna ja tallentaa tulokset SQLite-tietokantaan.

## Ominaisuudet
* **Tämän päivän Spot-tilanne:** Näkee heti kuluvan päivän tuoreimmat uutiset ja keskiarvot.
* **Viikoittainen ja aluekohtainen trendi:** Seuraa kriisien kehitystä interaktiivisten Plotly-kaavioiden avulla.
* **Automaattinen tiedonkeruu:** GitHub Actions päivittää uutiset taustalla päivittäin.
* **Pilvipalvelu:** Visualisointi toimii Streamlit Cloudin kautta, ja järjestelmään pääsee käsiksi suoraan iPhonen kotivalikosta.

## Tech Stack
* **Python** (`feedparser`, `pandas`, `plotly`, `streamlit`, `google-generativeai`)
* **SQLite** (`uutiset.db`)
* **GitHub Actions** (Automatisoitu tausta-ajo)
* **Streamlit Cloud** (Dashboardin hostaus)
