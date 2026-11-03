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
# 2. MOTORUL PENTRU TRADING JOURNAL (PE COORDONATE EXACTE)
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

def get_val_by_coord(df, col_name, col_wr, row_start, row_end, target_name):
    """ Funcție care caută un target într-un interval strict de rânduri și coloane """
    target = str(target_name).strip().lower()
    r_start = row_start - 1
    r_end = row_end - 1
    for r in range(r_start, r_end + 1):
        if r >= df.shape[0] or col_wr >= df.shape[1] or col_name >= df.shape[1]: 
            continue
        cell_name = str(df.iloc[r, col_name]).strip().lower()
        if cell_name == target:
            cell_wr = str(df.iloc[r, col_wr]).strip().lower()
            if cell_wr == '' or cell_wr == 'nan' or cell_wr == 'none':
                return "blank space"
            val = parse_magic_procent(cell_wr)
            return val if val is not None else "blank space"
    return None

def get_day_liq_wr(df, ziua, liq_name):
    """ Extrage winrate-ul pentru lichiditate fix din tabelul corelat al zilei respective """
    ziua = ziua.lower()
    liq_name = liq_name.lower()
    if "hod/lod+liq" in liq_name: liq_name = "hod/lod+liq"
    
    # Mapare coordonate tabele zile: (col_nume, col_wr, start_row, end_row)
    ranges = {
        "luni": (0, 5, 20, 26),        # A20-A26 (0), F20-F26 (5)
        "marti": (8, 13, 20, 26),      # I20-I26 (8), N20-N26 (13)
        "miercuri": (0, 5, 31, 37),    # A31-A37 (0), F31-F37 (5)
        "joi": (8, 13, 31, 37),        # I31-I37 (8), N31-N37 (13)
        "vineri": (4, 9, 42, 48)       # E42-E48 (4), J42-J48 (9)
    }
    if ziua not in ranges: return None
    c_name, c_wr, r_start, r_end = ranges[ziua]
    return get_val_by_coord(df, c_name, c_wr, r_start, r_end, liq_name)

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
        
        # --- LOGICĂ DE VALIDARE STRICTĂ (CROSS-VALIDATION) ---
        erori = []
        liq = lichiditate_input
        
        # Validare Timp Formare (Doar pentru K10: HoD/LoD)
        if liq == "HoD/LoD":
            if timp_formare == "-":
                erori.append("Pentru lichiditatea 'HoD/LoD' TREBUIE să selectezi un Timp de Formare!")
        else:
            if timp_formare != "-":
                erori.append(f"Timpul de formare se aplică DOAR pentru 'HoD/LoD' (K10). Ai selectat '{liq}', generând o eroare de calcul.")

        # Validare Notă Locală (Doar pentru K11 Locala, K12 Locala, K15 2x Locala)
        liq_cu_nota = ["HoD/LoD+Liq (cu Locala)", "Locala", "2x Locala"]
        if liq in liq_cu_nota:
            if nota_locala == "-":
                erori.append(f"Pentru lichiditatea '{liq}' TREBUIE să acorzi o Notă Locală!")
        else:
            if nota_locala != "-":
                erori.append(f"Nota Locală se aplică DOAR pentru zonele locale permise. Ai selectat '{liq}', generând o eroare de calcul.")

        if erori:
            for eroare in erori:
                st.error(f"⚠️ Eroare: {eroare}")
        else:
            # --- PRELUARE ȘI CALCUL ---
            df = incarca_date(piata)
            if df is None: 
                st.error("❌ Nu am putut descărca datele din tabel.")
            else:
                media_istorica = cauta_winrate_total(df)
                
                detalii_context = []
                log_cautari = []
                
                def log_and_append(val, log_text):
                    if val == "blank space":
                        detalii_context.append(media_istorica)
                        log_cautari.append(f"{log_text}: blank space -> s-a folosit media ({media_istorica*100:.1f}%)")
                    elif val is not None:
                        detalii_context.append(val)
                        log_cautari.append(f"{log_text}: {val*100:.1f}%")
                    else:
                        detalii_context.append(media_istorica)
                        log_cautari.append(f"{log_text}: Nu a fost găsit -> s-a folosit media ({media_istorica*100:.1f}%)")

                # BAZA (Setup + Lichiditate)
                wr_setup = get_val_by_coord(df, 10, 15, 2, 7, setup)  # K2-K7 -> P2-P7
                if wr_setup == "blank space" or wr_setup is None: wr_setup = media_istorica
                
                liq_nume_tabel = "hod/lod+liq" if "hod/lod+liq" in liq.lower() else liq
                wr_liq = get_val_by_coord(df, 10, 15, 10, 16, liq_nume_tabel) # K10-K16 -> P10-P16
                if wr_liq == "blank space" or wr_liq is None: wr_liq = media_istorica
                
                baza = (wr_setup * 0.35) + (wr_liq * 0.45)
                log_cautari.append(f"Setup ({setup}): {wr_setup*100:.1f}%")
                log_cautari.append(f"Lichiditate ({liq}): {wr_liq*100:.1f}%")

                # CONTEXT (Secțiuni adiționale conform cerințelor)
                # 1. Tabel Zi-Lichiditate
                val_zi_liq = get_day_liq_wr(df, zi, liq_nume_tabel)
                log_and_append(val_zi_liq, f"Tabel Ziua {zi} corelat cu Lichiditatea")
                
                # 2. Timp Formare HoD/LoD (S50-S53 -> V50-V53)
                if timp_formare != "-":
                    val_timp = get_val_by_coord(df, 18, 21, 50, 53, timp_formare)
                    log_and_append(val_timp, f"Timp Formare ({timp_formare})")
                    
                # 3. Notă Locală (S56-S57 -> V56-V57)
                if nota_locala != "-":
                    val_nota = get_val_by_coord(df, 18, 21, 56, 57, nota_locala)
                    log_and_append(val_nota, f"Notă Locală ({nota_locala})")
                
                # 4. Restul elementelor din coloana S
                val_zi = get_val_by_coord(df, 18, 21, 60, 64, zi) # S60-S64 -> V60-V64
                log_and_append(val_zi, f"Ziua ({zi})")
                
                val_ora = get_val_by_coord(df, 18, 22, 38, 47, ora) # S38-S47 -> W38-W47
                log_and_append(val_ora, f"Ora ({ora})")
                
                val_tw = get_val_by_coord(df, 18, 21, 32, 35, time_window) # S32-S35 -> V32-V35
                log_and_append(val_tw, f"Time Window ({time_window})")
                
                val_shift = get_val_by_coord(df, 18, 21, 97, 102, shift) # S97-S102 -> V97-V102
                log_and_append(val_shift, f"Shift ({shift})")
                
                val_gap = get_val_by_coord(df, 18, 21, 89, 94, gap) # S89-S94 -> V89-V94
                log_and_append(val_gap, f"Gap ({gap})")
                
                val_sapt = get_val_by_coord(df, 18, 21, 68, 72, saptamana) # S68-S72 -> V68-V72
                log_and_append(val_sapt, f"Săptămâna ({saptamana})")
                
                val_luna = get_val_by_coord(df, 18, 21, 75, 86, luna) # S75-S86 -> V75-V86
                log_and_append(val_luna, f"Luna ({luna})")

                # FINALIZARE CALCUL
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
        
        st.success(f"🎯 **Șansă Reală: {r['winrate_real']*100:.1f}%**")
        st.info(f"Bază: {r['baza']/0.80*100:.1f}% | Context adăugat: {r['modificator']/0.80*100:.2f}%")
        
        with st.expander("🔍 Vezi Debug-urile (Mapare Exactă Rând/Coloană)", expanded=True):
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