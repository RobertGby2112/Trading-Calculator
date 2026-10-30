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
# 1. CONFIGURARE APLICAȚIE
# ==========================================
st.set_page_config(page_title="Command Center", page_icon="⚙️", layout="wide")

# ==========================================
# 2. MOTORUL PENTRU TRADING JOURNAL
# ==========================================
LINKURI_PIETE = {
    "GBPUSD": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQvx3dLFODeBqEEQ_nRHHY9AoQuMYpUT_JWlmoxaxPeqQV8a3Aiq3g-7xvye6q1gypHcYdIP1VNMULs/pub?gid=384557570&single=true&output=csv",
    "DAX": "PUNE_LINKUL_CSV_PENTRU_DAX_AICI",
    "UK100": "PUNE_LINKUL_CSV_PENTRU_UK100_AICI"
}

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
    if val_str in ['nan', 'none', '', 'null']: return None
    if '%' in val_str:
        try:
            f = float(val_str.replace('%', '').replace(',', '.')) / 100.0
            if 0 <= f <= 1: return f
        except: pass
    else:
        try:
            f = float(val_str.replace(',', '.'))
            if 0 <= f <= 1 and ('.' in val_str or ',' in val_str): return f
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
                            if f is not None: return f
                rand_curent = df.iloc[i].values
                for k in range(j + 1, len(rand_curent)):
                    f = parse_magic_procent(rand_curent[k])
                    if f is not None and f > 0.10: return f
    return 0.3743

def cauta_procent(df, titlu_tabel, criteriu, media_istorica):
    if criteriu == "-" or criteriu == "" or not criteriu: return media_istorica, False
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
                            if f is not None: return f, True
                        return media_istorica, False
    return media_istorica, False

# ==========================================
# 3. INTERFEȚE - PAGINI
# ==========================================

def pagina_trading():
    st.title("📊 Trading Journal & Calculator")
    st.header("1. Parametrii Trade-ului")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        piata = st.selectbox("Piața", ["GBPUSD", "DAX", "UK100"])
        setup = st.selectbox("Setup", ["SLG", "1G", "2G", "2CG", "3G", "3CG"])
        lichiditate_input = st.selectbox("Lichiditate", ["HoD/LoD", "HoD/LoD+Liq (cu Locala)", "HoD/LoD+Liq (cu Majora)", "Locala", "Majora", "Maj+Loc", "2x Locala", "2x Majora"])
        timp_formare = st.selectbox("Timp Formare HoD/LoD", ["-", "<1H", "1-2H", "2-3H", "3+"])
        nota_locala = st.selectbox("Nota Locală", ["-", "Nota 10", "Nota 5"])
        
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
        
        # --- LOGICĂ DE VALIDARE STRICTĂ ---
        liq_lower = lichiditate_input.lower()
        are_hod_lod = "hod/lod" in liq_lower
        are_locala = "locala" in liq_lower or "maj+loc" in liq_lower

        erori = []
        
        # Validare Timp Formare
        if timp_formare != "-" and not are_hod_lod:
            erori.append(f"Nu poți pune Timp de Formare ('{timp_formare}') dacă lichiditatea nu conține HoD/LoD!")
        if timp_formare == "-" and are_hod_lod:
            erori.append(f"Ai selectat o lichiditate cu HoD/LoD, deci TREBUIE să alegi Timpul de Formare!")
            
        # Validare Notă Locală
        if nota_locala != "-" and not are_locala:
            erori.append(f"Nu poți pune Notă Locală ('{nota_locala}') dacă lichiditatea nu conține o zonă Locală!")
        if nota_locala == "-" and are_locala:
            erori.append(f"Ai selectat o lichiditate cu zonă Locală, deci TREBUIE să îi acorzi o Notă Locală!")

        if erori:
            for eroare in erori:
                st.error(f"⚠️ Eroare: {eroare}")
        else:
            # --- CALCUL ȘI LOG-URI ---
            df = incarca_date(piata)
            if df is None: 
                st.error("❌ Nu am putut descărca datele.")
            else:
                media_istorica = cauta_winrate_total(df)
                
                # Mapare strictă pentru căutarea în fișier (Liquidities)
                if lichiditate_input in ["HoD/LoD+Liq (cu Majora)", "HoD/LoD+Liq (cu Locala)"]:
                    liq_cautare_baza = "HoD/LoD+LIQ"
                else:
                    liq_cautare_baza = lichiditate_input
                
                log_cautari = []
                detalii_context = []
                
                # Căutare Setup și Lichiditate (Baza)
                wr_setup, _ = cauta_procent(df, "SETUPS", setup, media_istorica)
                wr_liq, _ = cauta_procent(df, "Liquidities", liq_cautare_baza, media_istorica)
                baza = (wr_setup * 0.35) + (wr_liq * 0.45)
                
                log_cautari.append(f"Media Istorică Globală (Default): {media_istorica*100:.1f}%")
                log_cautari.append(f"Setup ({setup}): {wr_setup*100:.1f}%")
                log_cautari.append(f"Lichiditate în tabel ({liq_cautare_baza}): {wr_liq*100:.1f}%")
                
                # Căutare pentru modificatori (Context)
                if timp_formare != "-":
                    val_timp, _ = cauta_procent(df, "HoD/Lod Form", timp_formare, media_istorica)
                    detalii_context.append(val_timp)
                    log_cautari.append(f"Timp Formare ({timp_formare}): {val_timp*100:.1f}%")
                    
                if nota_locala != "-":
                    val_nota, _ = cauta_procent(df, "Locala Grades", nota_locala, media_istorica)
                    detalii_context.append(val_nota)
                    log_cautari.append(f"Notă Locală ({nota_locala}): {val_nota*100:.1f}%")

                # Restul parametrilor
                for param, titlu in [(zi, "Days WR"), (zi, zi), (ora, "Hours"), (time_window, "Time Window 2"), (shift, "Shift WR"), (gap, "Gap WR"), (saptamana, "Weeks WR"), (luna, "Months WR")]:
                    crit = liq_cautare_baza if titlu == zi else param
                    val, gasit = cauta_procent(df, titlu, crit, media_istorica)
                    detalii_context.append(val)
                    if gasit:
                        log_cautari.append(f"{titlu} ({crit}): {val*100:.1f}%")
                    else:
                        log_cautari.append(f"{titlu} ({crit}): N/A -> s-a folosit media ({media_istorica*100:.1f}%)")

                modificator = ((sum(detalii_context) / len(detalii_context)) - media_istorica) * 0.20 if detalii_context else 0
                scor_final = baza + modificator
                
                st.session_state['rezultat'] = {
                    "winrate_real": scor_final / 0.80,
                    "baza": baza,
                    "modificator": modificator,
                    "log_cautari": log_cautari
                }

    if 'rezultat' in st.session_state:
        r = st.session_state['rezultat']
        
        # AFIȘARE REZULTAT
        st.success(f"🎯 **Șansă Reală: {r['winrate_real']*100:.1f}%**")
        st.info(f"Bază: {r['baza']/0.80*100:.1f}% | Context adăugat: {r['modificator']/0.80*100:.2f}%")
        
        # AFIȘARE DEBUG-URI PENTRU USER
        with st.expander("🔍 Vezi Debug-urile (Ce a citit algoritmul din tabel)", expanded=True):
            for log in r['log_cautari']:
                st.write(f"- {log}")
        
        st.header("3. Jurnalizare și Descărcare Trade")
        notițe = st.text_area("✍️ Side Notes (Observații piață, mindset):", height=100)
        poze_upload = st.file_uploader("📸 Încarcă Capturi (Max 2)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            date_salvare = {"Data": timestamp, "Piata": piata, "Setup": setup, "Winrate": f"{r['winrate_real']*100:.1f}%", "Notite": notițe}
            zip_file.writestr("detalii_trade.json", json.dumps(date_salvare, indent=4))
            if poze_upload:
                for idx, fisier in enumerate(poze_upload[:2]):
                    zip_file.writestr(f"poza_{idx+1}_{fisier.name}", fisier.getvalue())

        st.download_button(label="⬇️ Descarcă Acest Trade", data=zip_buffer.getvalue(), file_name=f"Trade_{piata}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip", mime="application/zip", type="primary")


def pagina_finante():
    st.title("⚖️ TFO (Total Financial Optimization)")
    st.markdown("*Matematica nu minte. Această secțiune transformă deciziile zilnice (micro) în obiective de viață (macro).*")
    
    st.header("1. Date de Intrare (Micro Management)")
    col1, col2, col3 = st.columns(3)
    with col1:
        venit_net = st.number_input("💵 Venit Total Net / lună", value=0)
        chirie_venit_pasiv = st.number_input("🏠 Venit Pasiv din Chirii", value=0)
    with col2:
        cheltuieli_fixe = st.number_input("🛡️ Cheltuieli Fixe (Supraviețuire, Chirie)", value=0)
        cheltuieli_vicii = st.number_input("🍔 Vicii / Oraș / Pariuri", value=0)
    with col3:
        rata_obligatorie = st.number_input("🏦 Rată Minimă Bancă", value=0)
        plata_anticipata = st.number_input("🚀 Plată Anticipată Datorie (extra)", value=0)
        economii_investitii = st.number_input("📈 Banii puși deoparte (Investiții/Urgență)", value=0)
    
    venit_total = venit_net + chirie_venit_pasiv
    
    st.header("2. Analiză Decizională")
    buget_ramas = venit_total - (cheltuieli_fixe + cheltuieli_vicii + rata_obligatorie + plata_anticipata + economii_investitii)
    waste_ratio = (cheltuieli_vicii / venit_total * 100) if venit_total > 0 else 0
    
    r_lunar = 0.10 / 12
    luni = 120 
    cost_oportunitate = cheltuieli_vicii * (((1 + r_lunar)**luni - 1) / r_lunar) if cheltuieli_vicii > 0 else 0

    col_a, col_b, col_c = st.columns(3)
    col_a.metric(label="Buget Ne-alocat (Zero-Based Check)", value=f"{buget_ramas} €", delta="Trebuie să fie 0!" if buget_ramas != 0 else "Perfect echilibrat", delta_color="inverse")
    col_b.metric(label="Rata de Sângerare (Waste Ratio)", value=f"{waste_ratio:.1f}%", delta="Pericol (peste 10%)" if waste_ratio > 10 else "Optim", delta_color="inverse")
    col_c.metric(label="Cost Oportunitate Vicii (pe 10 ani)", value=f"- {cost_oportunitate:,.0f} €", help="Câți bani ai fi avut în 10 ani dacă investeai lunar banii dați pe vicii în S&P 500.")

    st.header("3. Roadmap Macro-Obiective (2-5-10 ani)")
    
    st.subheader("Faza 1: The Debt Destroyer")
    total_datorie = st.number_input("Valoare Totală Datorie Rămasă", value=35000)
    plata_lunara_totala = rata_obligatorie + plata_anticipata
    
    if total_datorie > 0 and plata_lunara_totala > 0:
        luni_ramase = total_datorie / plata_lunara_totala
        st.info(f"Cu ritmul actual de plată ({plata_lunara_totala}€/lună), datoria ta va fi **ZERO în {luni_ramase/12:.1f} ani** ({int(luni_ramase)} luni).")
        progres_datorie = (35000 - total_datorie) / 35000 if 35000 > total_datorie else 0.0 
        st.progress(max(0.0, min(1.0, progres_datorie)), text="Progres Eliminare Datorie")
    elif total_datorie > 0:
        st.warning("Introduce rata lunară și plata anticipată pentru a calcula timpul de eliberare.")
    else:
        st.success("✅ FELICITĂRI! DATORIE 0! Treci la Faza 2.")

    st.subheader("Faza 2: The Foundation (Fond Urgență)")
    target_urgenta = cheltuieli_fixe * 6
    fond_strans = st.number_input("Câți bani ai acum în Fondul de Urgență?", value=0)
    
    if target_urgenta > 0:
        st.write(f"Ținta ta matematică de siguranță (6 luni de supraviețuire): **{target_urgenta} €**")
        st.progress(min(1.0, fond_strans / target_urgenta), text=f"Progres Fond: {fond_strans} / {target_urgenta} €")

    st.subheader("Faza 3: The Asset Builder (Ținta: 5 Apartamente)")
    st.write("Aceste grafice se umplu cu banii din *Economii pentru Investiții*. Un apartament reprezintă strict **AVANSUL** necesar pentru a lua credit imobiliar de investiție (aprox. 15.000€ - 20.000€ per apartament).")
    
    cost_avans = st.number_input("Target Avans per Apartament (€)", value=15000)
    economii_totale_imobiliare = st.number_input("Total Bani Strânși pentru Avansuri Imobiliare (€)", value=0)
    
    if cost_avans > 0:
        nr_apartamente = 5
        for i in range(1, nr_apartamente + 1):
            bani_alocati = max(0, min(cost_avans, economii_totale_imobiliare - (i - 1) * cost_avans))
            procent = bani_alocati / cost_avans
            
            if procent == 1.0:
                st.success(f"🏢 Apartament {i} - ASIGURAT! (Pregătit pentru achiziție și generare chirie)")
                st.progress(1.0)
            else:
                st.write(f"🏢 Apartament {i} - {bani_alocati} / {cost_avans} €")
                st.progress(procent)

# ==========================================
# 4. RUTARE MENIU LATERAL
# ==========================================
st.sidebar.title("Comutator Module")
optiune_meniu = st.sidebar.radio("Alege aplicația:", ["📈 Trading Journal", "💰 TFO (Finanțe & Obiective)"])

if optiune_meniu == "📈 Trading Journal":
    pagina_trading()
else:
    pagina_finante()