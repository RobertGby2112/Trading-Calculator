import streamlit as st
import pandas as pd
import requests
import io
import math
import os
import json
import zipfile
from datetime import datetime

# ==========================================
# 1. CONFIGURARE
# ==========================================
st.set_page_config(page_title="Trading Journal & Calculator", page_icon="📈", layout="wide")

LINKURI_PIETE = {
    "GBPUSD": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQvx3dLFODeBqEEQ_nRHHY9AoQuMYpUT_JWlmoxaxPeqQV8a3Aiq3g-7xvye6q1gypHcYdIP1VNMULs/pub?gid=384557570&single=true&output=csv",
    "DAX": "PUNE_LINKUL_CSV_PENTRU_DAX_AICI",
    "UK100": "PUNE_LINKUL_CSV_PENTRU_UK100_AICI"
}

# ==========================================
# 2. MOTOARE DE CĂUTARE ÎN TABEL
# ==========================================
@st.cache_data(ttl=60)
def incarca_date(nume_piata):
    url = LINKURI_PIETE.get(nume_piata.upper())
    if not url or url == "" or "PUNE_LINKUL" in url: return None
    try:
        response = requests.get(url)
        response.raise_for_status()
        response.encoding = 'utf-8'
        try:
            return pd.read_csv(io.StringIO(response.text), header=None, sep=None, engine='python', dtype=str)
        except:
            return pd.read_csv(io.StringIO(response.text), header=None, dtype=str)
    except:
        return None

def parse_magic_procent(val):
    val_str = str(val).strip().lower().replace('\ufeff', '').replace('\xa0', '').replace(' ', '')
    if val_str in ['nan', 'none', '', 'null']: 
        return None
    
    if '%' in val_str:
        try:
            f = float(val_str.replace('%', '').replace(',', '.')) / 100.0
            if 0 <= f <= 1: return f
        except: pass
    else:
        try:
            f = float(val_str.replace(',', '.'))
            if 0 <= f <= 1 and ('.' in val_str or ',' in val_str):
                return f
        except: pass
    return None

def cauta_winrate_total(df):
    for i in range(min(50, df.shape[0])):
        for j in range(df.shape[1]):
            cel_curata = str(df.iloc[i, j]).strip().lower().replace('\ufeff', '')
            if cel_curata == "total stats":
                if i > 0:
                    rand_nume = df.iloc[i-1].values
                    for col_idx in range(len(rand_nume)):
                        if str(rand_nume[col_idx]).strip().lower() == "winrate":
                            f = parse_magic_procent(df.iloc[i, col_idx])
                            if f is not None:
                                return f
                
                rand_curent = df.iloc[i].values
                for k in range(j + 1, len(rand_curent)):
                    f = parse_magic_procent(rand_curent[k])
                    if f is not None and f > 0.10: 
                        return f
    return 0.3743

def cauta_procent(df, titlu_tabel, criteriu, media_istorica):
    if criteriu == "-" or criteriu == "" or not criteriu:
        return media_istorica, False
        
    criteriu_curat = str(criteriu).strip().lower().replace('\ufeff', '')
    titlu_curat = str(titlu_tabel).strip().lower().replace('\ufeff', '')
    
    for i in range(df.shape[0]):
        for j in range(df.shape[1]):
            celula_titlu = str(df.iloc[i, j]).strip().lower().replace('\ufeff', '')
            if celula_titlu == titlu_curat:
                for rand_tabel in range(i + 1, min(i + 50, df.shape[0])):
                    celula_criteriu = str(df.iloc[rand_tabel, j]).strip().lower().replace('\ufeff', '')
                    if celula_criteriu == criteriu_curat:
                        rand_curent = df.iloc[rand_tabel].values
                        for k in range(j + 1, len(rand_curent)):
                            f = parse_magic_procent(rand_curent[k])
                            if f is not None:
                                return f, True
                        return media_istorica, False
    return media_istorica, False

# ==========================================
# 3. INTERFAȚA WEB (UI)
# ==========================================
st.title("📊 Trading Journal & Winrate Calculator")

st.header("1. Parametrii Trade-ului")
col1, col2, col3 = st.columns(3)

with col1:
    piata = st.selectbox("Piața", ["GBPUSD", "DAX", "UK100"])
    setup = st.selectbox("Setup", ["SLG", "1G", "2G", "2CG", "3G", "3CG"])
    lichiditate_input = st.selectbox("Lichiditate", [
        "HoD/LoD", 
        "HoD/LoD+Liq (cu Locala)", 
        "HoD/LoD+Liq (cu Majora)", 
        "Locala", 
        "Majora", 
        "Maj+Loc", 
        "2x Locala", 
        "2x Majora"
    ])
    nota_forma = st.selectbox("Nota / Forma", ["-", "Nota 10", "Nota 5", "<1H", "1-2H", "2-3H", "3+"])

with col2:
    luna = st.selectbox("Luna", ["Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie", "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie"])
    saptamana = st.selectbox("Săptămâna", ["W1", "W2", "W3", "W4", "W5"])
    zi = st.selectbox("Ziua", ["Luni", "Marti", "Miercuri", "Joi", "Vineri"])
    ora = st.selectbox("Ora", ["9:00-10:00", "10:00-11:00", "11:00-12:00", "12:00-13:00", "13:00-14:00", "14:00-15:00", "15:00-16:00", "16:00-17:00", "17:00-18:00", "18:00-19:00"])

with col3:
    time_window = st.selectbox("Time Window", ["0-30", "31-60", "61-90", "91-120"])
    shift = st.selectbox("Shift", ["0-10", "10-20", "20-40", "40-60", "60-80", "80+"])
    gap = st.selectbox("Gap", ["0-2", "2-4", "4-6", "6-8", "8-10", "10+"])

st.header("2. Analiză Statistică")
if st.button("🧮 Calculează Șansele", type="primary"):
    df = incarca_date(piata)
    if df is None:
        st.error("❌ Nu am putut descărca datele. Verifică link-ul CSV.")
    else:
        media_istorica = cauta_winrate_total(df)

        if "hod/lod+liq" in lichiditate_input.lower():
            liq_cautare_baza = "HoD/LoD+LIQ"
        else:
            liq_cautare_baza = lichiditate_input

        activeaza_tabel_context = False
        nume_tabel_context = ""
        input_mic = lichiditate_input.lower()
        
        if input_mic == "hod/lod":
            activeaza_tabel_context = True
            nume_tabel_context = "HoD/Lod Form"
        elif input_mic in ["locala", "2x locala", "hod/lod+liq (cu locala)"]:
            activeaza_tabel_context = True
            nume_tabel_context = "Locala Grades"
            
        wr_setup, gasit_setup = cauta_procent(df, "SETUPS", setup, media_istorica)
        wr_liq, gasit_liq = cauta_procent(df, "Liquidities", liq_cautare_baza, media_istorica)
        
        baza = (wr_setup * 0.35) + (wr_liq * 0.45)
        
        detalii_context = []
        log_cautari = []
        
        if activeaza_tabel_context and nota_forma != "-":
            val_nota, gasit = cauta_procent(df, nume_tabel_context, nota_forma, media_istorica)
            detalii_context.append(val_nota)
            log_cautari.append(f"Nota/Forma ({nota_forma} in {nume_tabel_context}): {val_nota*100:.1f}% {'✅' if gasit else '❌'}")

        tabele_context = [
            (zi, "Days WR"), (zi, zi), (ora, "Hours"), (time_window, "Time Window 2"), 
            (shift, "Shift WR"), (gap, "Gap WR"), (saptamana, "Weeks WR"), (luna, "Months WR")
        ]

        for param, titlu in tabele_context:
            crit = liq_cautare_baza if titlu == zi else param
            val, gasit = cauta_procent(df, titlu, crit, media_istorica)
            detalii_context.append(val)
            log_cautari.append(f"{titlu} -> {crit}: {val*100:.1f}% {'✅' if gasit else '❌'}")

        modificator = ((sum(detalii_context) / len(detalii_context)) - media_istorica) * 0.20 if detalii_context else 0
        scor_final = baza + modificator
        winrate_real = scor_final / 0.80 
        
        st.session_state['rezultat'] = {
            "baza": baza, "modificator": modificator, "winrate_real": winrate_real, 
            "liq_selectata": lichiditate_input, "media_istorica": media_istorica,
            "wr_setup": wr_setup, "gasit_setup": gasit_setup,
            "wr_liq": wr_liq, "gasit_liq": gasit_liq,
            "log_cautari": log_cautari
        }

if 'rezultat' in st.session_state:
    r = st.session_state['rezultat']
    st.success(f"🎯 **Șansă Reală de Win: {r['winrate_real']*100:.1f}%** (raportat la avg de {r['media_istorica']*100:.2f}%)")
    
    text_baza = f"🔹 **Bază:** {r['baza']/0.80*100:.1f}%"
    semn_modificator = "+" if r['modificator'] > 0 else ""
    text_context = f"🔹 **Context:** {semn_modificator}{r['modificator']/0.80*100:.2f}%"
    st.info(f"{text_baza} | {text_context}")
    
    with st.expander("🔍 DEBUG: Vezi ce a găsit în Excel (Click pentru a deschide)"):
        st.write(f"**Setup** -> a luat {r['wr_setup']*100:.1f}% {'✅' if r['gasit_setup'] else '❌ (A luat media)'}")
        st.write(f"**Lichiditate** -> a luat {r['wr_liq']*100:.1f}% {'✅' if r['gasit_liq'] else '❌ (A luat media)'}")
        st.write("**Factori de Context:**")
        for log in r['log_cautari']:
            st.write(f"- {log}")

    st.header("3. Jurnalizare și Descărcare Trade")
    st.write("Dacă dorești să păstrezi acest trade pe calculatorul tău, adaugă notițe/poze și descarcă-l.")
    
    notițe = st.text_area("✍️ Side Notes (Observații despre piață, mindset, execuție):", height=100)
    poze_upload = st.file_uploader("📸 Încarcă Capturi de Ecran (Max 2 poze)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

    # Construim fișierul ZIP în memoria RAM, ca să îl poți descărca direct (Perfect pentru Cloud)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        date_salvare = {
            "Data": timestamp, "Piata": piata, "Setup": setup, "Lichiditate": lichiditate_input,
            "Nota_Forma": nota_forma, "Luna": luna, "Saptamana": saptamana, "Ziua": zi,
            "Ora": ora, "Time_Window": time_window, "Shift": shift, "Gap": gap,
            "Winrate_Calculat": f"{r['winrate_real']*100:.1f}%",
            "Notite": notițe
        }
        
        # Adaugam detaliile text/json in pachetul ZIP
        zip_file.writestr("detalii_trade.json", json.dumps(date_salvare, indent=4, ensure_ascii=False))
        
        text_rezumat = f"Piața: {piata}\nSetup: {setup}\nWinrate Calculat: {r['winrate_real']*100:.1f}%\n\nNotițe:\n{notițe}"
        zip_file.writestr("rezumat_simplu.txt", text_rezumat)
        
        # Adaugam pozele, daca ai incarcat
        if poze_upload:
            for idx, fisier in enumerate(poze_upload[:2]):
                zip_file.writestr(f"poza_{idx+1}_{fisier.name}", fisier.getvalue())

    st.download_button(
        label="⬇️ Descarcă Acest Trade",
        data=zip_buffer.getvalue(),
        file_name=f"Trade_{piata}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        mime="application/zip",
        type="primary"
    )