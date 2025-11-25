import streamlit as st
import pandas as pd
from src.reader import render_page_to_image
from src.processor import extract_match_info, VolleySheetExtractor, calculate_stats
from src.visualizer import draw_calibration_grid, draw_court_view

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# Wrapper Cache pour le Reader
@st.cache_data(show_spinner=False)
def get_cached_image(file_bytes):
    return render_page_to_image(file_bytes, dpi=72)

def main():
    st.title("🏐 VolleyStats Pro")

    with st.sidebar:
        uploaded_file = st.file_uploader("Importer la Feuille de Match (PDF)", type="pdf")
        with st.expander("⚙️ Calibration Avancée"):
            base_x = st.number_input("Start X", value=123)
            base_y = st.number_input("Start Y", value=88)
            offset_x = st.number_input("Right Offset", value=492) 
            
    if not uploaded_file:
        st.info("Veuillez importer un fichier PDF pour commencer.")
        return

    # 1. Affichage & Calibration
    try:
        file_bytes = uploaded_file.getvalue()
        base_img, _ = get_cached_image(file_bytes)
    except Exception as e:
        st.error("Erreur de lecture du PDF.")
        return

    # 2. Extraction des Données
    extractor = VolleySheetExtractor(uploaded_file)
    t_home, t_away, scores = extract_match_info(uploaded_file)
    
    with st.spinner("Analyse du match en cours..."):
        # Extraction Lineups (W=23, H=20, OffY=151 sont les constantes magiques)
        raw_data = extractor.extract_full_match(base_x, base_y, 23, 20, offset_x, 151, 842)
        df = pd.DataFrame(raw_data)

    if df.empty:
        st.error("Impossible de lire les lineups. Vérifiez la calibration.")
        return

    # 3. Interface Dashboard
    home_wins = sum(1 for s in scores if s['Home'] > s['Away'])
    away_wins = sum(1 for s in scores if s['Away'] > s['Home'])
    
    c1, c2, c3 = st.columns([2, 1, 2])
    c1.metric("DOMICILE", t_home)
    c3.metric("EXTÉRIEUR", t_away)
    c2.markdown(f"<h1 style='text-align: center; color: #FF4B4B;'>{home_wins} - {away_wins}</h1>", unsafe_allow_html=True)

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📊 Statistiques Joueurs", "🏟️ Rotation Visuelle", "🔧 Calibration & Données"])

    with tab1:
        if scores:
            stats_df = calculate_stats(df, scores)
            if not stats_df.empty:
                c_a, c_b = st.columns(2)
                with c_a:
                    st.subheader(f"Impact {t_home}")
                    st.dataframe(stats_df[stats_df['Team'] == 'Home'][['Player', 'Sets', 'Win %']], use_container_width=True)
                with c_b:
                    st.subheader(f"Impact {t_away}")
                    st.dataframe(stats_df[stats_df['Team'] == 'Away'][['Player', 'Sets', 'Win %']], use_container_width=True)
        else:
            st.warning("Scores des sets non détectés. Statistiques indisponibles.")

    with tab2:
        c_sel1, c_sel2 = st.columns(2)
        sel_set = c_sel1.selectbox("Choisir le Set", df['Set'].unique())
        sel_team = c_sel2.selectbox("Choisir l'équipe", ["Home", "Away"])
        
        subset = df[(df['Set'] == sel_set) & (df['Team'] == sel_team)]
        if not subset.empty:
            starters = subset.iloc[0]['Starters']
            fig = draw_court_view(starters)
            st.plotly_chart(fig, use_container_width=False)
        else:
            st.info("Pas de données pour cette sélection.")

    with tab3:
        debug_img = draw_calibration_grid(base_img, base_x, base_y, 23, 20, offset_x, 151)
        st.image(debug_img, caption="Vérification visuelle des boîtes de capture", use_container_width=True)
        
        # Export CSV
        export_df = df.copy()
        cols = pd.DataFrame(export_df['Starters'].tolist(), columns=[f'Zone {i+1}' for i in range(6)])
        export_df = pd.concat([export_df[['Set', 'Team']], cols], axis=1)
        st.dataframe(export_df)

if __name__ == "__main__":
    main()