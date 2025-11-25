import streamlit as st
import pandas as pd
# Import des modules créés
from src.extractor import get_page_image, extract_match_info, VolleySheetExtractor
from src.analytics import calculate_real_stats, format_export_data
from src.visualizer import draw_alignment_grid, draw_court

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

def main():
    st.title("🏐 VolleyStats Pro")
    
    # --- SIDEBAR (Configuration) ---
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
        st.info("Veuillez uploader un PDF pour commencer.")
        return

    # --- 1. LECTURE ---
    extractor = VolleySheetExtractor(uploaded_file)
    t_home, t_away, scores = extract_match_info(uploaded_file)
    
    # Extraction des lineups (Partie lourde)
    with st.spinner("Extraction des données..."):
        lineups = extractor.extract_full_match(base_x, base_y, w, h, off_x, off_y, 842)
        df = pd.DataFrame(lineups)

    if df.empty:
        st.error("Aucune donnée trouvée. Vérifiez la calibration.")
        return

    # --- 2. AFFICHAGE SCORE ---
    h_wins = sum(1 for s in scores if s['Home'] > s['Away'])
    a_wins = sum(1 for s in scores if s['Away'] > s['Home'])
    
    c1, c2, c3 = st.columns([2, 1, 2])
    c1.metric("DOMICILE", t_home)
    c3.metric("EXTÉRIEUR", t_away)
    c2.markdown(f"<h1 style='text-align: center; color: #FF4B4B;'>{h_wins} - {a_wins}</h1>", unsafe_allow_html=True)

    if not scores:
        st.warning("⚠️ Scores non détectés automatiquement.")

    # --- 3. ONGLETS D'ANALYSE ---
    tab1, tab2, tab3 = st.tabs(["📊 Stats Joueurs", "🏟️ Rotations", "🔧 Données & Export"])

    with tab1:
        if scores:
            stats_df = calculate_real_stats(df, scores)
            if not stats_df.empty:
                ca, cb = st.columns(2)
                with ca: 
                    st.subheader("Stats Domicile")
                    st.dataframe(stats_df[stats_df['Équipe']=="Home"], use_container_width=True)
                with cb: 
                    st.subheader("Stats Extérieur")
                    st.dataframe(stats_df[stats_df['Équipe']=="Away"], use_container_width=True)
            else:
                st.info("Pas assez de données pour calculer les stats.")

    with tab2:
        col_s, col_t = st.columns(2)
        sel_set = col_s.selectbox("Choisir le Set", df['Set'].unique())
        sel_team = col_t.selectbox("Choisir l'équipe", ["Home", "Away"])
        
        row = df[(df['Set'] == sel_set) & (df['Team'] == sel_team)]
        if not row.empty:
            starters = row.iloc[0]['Starters']
            st.plotly_chart(draw_court(starters), use_container_width=False)
            

#[Image of volleyball rotation diagram]

        else:
            st.info("Pas de données pour cette sélection.")

    with tab3:
        # Vérification visuelle
        try:
            f_bytes = uploaded_file.getvalue()
            img, _ = get_page_image(f_bytes)
            st.image(draw_alignment_grid(img, base_x, base_y, w, h, off_x, off_y), caption="Grille d'extraction")
        except: pass
        
        # Export
        final_df = format_export_data(df)
        st.dataframe(final_df)
        st.download_button("Télécharger Excel/CSV", final_df.to_csv(index=False).encode('utf-8'), "match_stats.csv", "text/csv")

if __name__ == "__main__":
    main()