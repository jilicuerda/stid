import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Import des modules locaux
from src.extractor import get_page_image, extract_match_info, VolleySheetExtractor
from src.analytics import calculate_player_stats, analyze_money_time, format_export_data
from src.visualizer import draw_alignment_grid, draw_court_view

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

def main():
    st.title("🏐 VolleyStats Pro : Rapport Complet")

    # --- SIDEBAR ---
    with st.sidebar:
        uploaded_file = st.file_uploader("Importer Feuille de Match (PDF)", type="pdf")
        with st.expander("⚙️ Calibration"):
            base_x = st.number_input("X Départ", 123)
            base_y = st.number_input("Y Départ", 88)
            w = st.number_input("Largeur Case", 23)
            h = st.number_input("Hauteur Case", 20)
            off_x = st.number_input("Décalage Droite", 492)
            off_y = st.number_input("Décalage Bas", 151)

    if not uploaded_file:
        st.info("En attente du fichier PDF...")
        return

    # --- 1. EXTRACTION ---
    extractor = VolleySheetExtractor(uploaded_file)
    t_home, t_away, scores = extract_match_info(uploaded_file)
    
    with st.spinner("Analyse tactique en cours..."):
        raw_data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y, 842)
        df = pd.DataFrame(raw_data)

    if df.empty:
        st.error("Données illisibles.")
        return

    # --- 2. SCOREBOARD ---
    h_wins = sum(1 for s in scores if s['Home'] > s['Away'])
    a_wins = sum(1 for s in scores if s['Away'] > s['Home'])
    
    c1, c2, c3 = st.columns([2, 1, 2])
    c1.metric("DOMICILE", t_home)
    c3.metric("EXTÉRIEUR", t_away)
    c2.markdown(f"<h1 style='text-align: center; color: #FF4B4B;'>{h_wins} - {a_wins}</h1>", unsafe_allow_html=True)

    # --- 3. ANALYSE DÉTAILLÉE (Les 5 Axes) ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1. Money Time", 
        "2. Stats Joueurs", 
        "3. Rotations", 
        "4. Physique & Durée", 
        "5. Export & Vérif"
    ])

    # AXE 1 : MONEY TIME
    with tab1:
        st.header("Gestion des fins de sets")
        if scores:
            analysis, clutch_stats = analyze_money_time(scores, t_home, t_away)
            col_mt1, col_mt2 = st.columns(2)
            col_mt1.metric(f"Sets Serrés ({t_home})", clutch_stats.get(t_home, 0))
            col_mt2.metric(f"Sets Serrés ({t_away})", clutch_stats.get(t_away, 0))
            
            st.write("##### Analyse Chronologique :")
            for item in analysis:
                st.write(item)
        else:
            st.warning("Scores non détectés.")

    # AXE 2 : STATS JOUEURS (Win %)
    with tab2:
        st.header("Impact des Titulaires")
        if scores:
            stats_df = calculate_player_stats(df, scores)
            if not stats_df.empty:
                ca, cb = st.columns(2)
                with ca: 
                    st.subheader(f"{t_home}")
                    st.dataframe(stats_df[stats_df['Équipe']=="Home"], use_container_width=True)
                with cb: 
                    st.subheader(f"{t_away}")
                    st.dataframe(stats_df[stats_df['Équipe']=="Away"], use_container_width=True)
        else:
            st.info("Nécessite les scores pour calculer l'impact.")

    # AXE 3 : ROTATIONS VISUELLES
    with tab3:
        st.header("Cartographie des Rotations")
        col_s, col_t = st.columns(2)
        sel_set = col_s.selectbox("Set", df['Set'].unique())
        sel_team = col_t.selectbox("Équipe", ["Home", "Away"])
        
        row = df[(df['Set'] == sel_set) & (df['Team'] == sel_team)]
        if not row.empty:
            starters = row.iloc[0]['Starters']
            st.plotly_chart(draw_court_view(starters), use_container_width=False)
            

#[Image of volleyball rotation diagram]

        else:
            st.info("Pas de données.")

    # AXE 4 : PHYSIQUE & DURÉE
    with tab4:
        st.header("Intensité du Match")
        # Récupération Durée (si dispo dans scores, sinon simulée pour démo structurelle)
        # Note: Le PDF actuel ne donne pas la durée facilement, on met un placeholder intelligent
        total_points = sum(s['Home'] + s['Away'] for s in scores)
        est_duration = int(total_points * 1.5) # Est. 1.5 min par point
        
        c_d1, c_d2 = st.columns(2)
        c_d1.metric("Points Totaux Joués", total_points)
        c_d2.metric("Durée Estimée", f"~{est_duration // 60}h {est_duration % 60}min")
        
        st.bar_chart(pd.DataFrame([s['Home']+s['Away'] for s in scores], columns=["Intensité (Points/Set)"]))

    # AXE 5 : EXPORT
    with tab5:
        try:
            f_bytes = uploaded_file.getvalue()
            img, _ = get_page_image(f_bytes)
            st.image(draw_alignment_grid(img, base_x, base_y, w, h, offset_x, offset_y), caption="Calibration")
        except: pass
        
        final_df = format_export_data(df)
        st.dataframe(final_df)
        st.download_button("Télécharger CSV", final_df.to_csv(index=False).encode('utf-8'), "match_stats.csv", "text/csv")

if __name__ == "__main__":
    main()