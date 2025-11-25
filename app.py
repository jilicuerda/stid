import streamlit as st
import pdfplumber
import pandas as pd
import pypdfium2 as pdfium
import re
import gc
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# ==========================================
# 1. CORE ENGINES (IMAGE & TEXT)
# ==========================================

@st.cache_data(show_spinner=False)
def get_page_image(file_bytes):
    pdf = pdfium.PdfDocument(file_bytes)
    page = pdf[0]
    scale = 1.0 
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()
    page.close()
    pdf.close()
    gc.collect()
    return pil_image, scale

def extract_scores_text(file):
    """Extracts Set Scores from text to determine Win/Loss."""
    text = ""
    with pdfplumber.open(file) as pdf:
        text = pdf.pages[0].extract_text()
    
    # Find the 'RESULTATS' table logic
    lines = text.split('\n')
    scores = []
    duration_pattern = re.compile(r"(\d{1,3})\s*['’′`]")
    
    found_table = False
    for line in lines:
        if "RESULTATS" in line: found_table = True
        if "Vainqueur" in line: found_table = False
        
        if found_table:
            match = duration_pattern.search(line)
            if match:
                # Logic: Find numbers around the duration
                parts = line.split(match.group(0)) # Split by "26'"
                if len(parts) >= 2:
                    left = re.findall(r'\d+', parts[0])
                    right = re.findall(r'\d+', parts[1])
                    if left and right:
                        try:
                            # Last number on left, First on right
                            scores.append({
                                "Home": int(left[-1]),
                                "Away": int(right[0])
                            })
                        except: pass
    return scores

class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf_file = pdf_file

    def extract_lineups(self, base_x, base_y, w, h, offset_x, offset_y, p_height):
        match_data = []
        with pdfplumber.open(self.pdf_file) as pdf:
            page = pdf.pages[0]
            for set_num in range(1, 6): 
                current_y = base_y + ((set_num - 1) * offset_y)
                
                if current_y + h < p_height:
                    # Left
                    row_l = self._extract_row(page, current_y, base_x, w, h)
                    if row_l: match_data.append({"Set": set_num, "Team": "Home", "Starters": row_l})
                    # Right
                    row_r = self._extract_row(page, current_y, base_x + offset_x, w, h)
                    if row_r: match_data.append({"Set": set_num, "Team": "Away", "Starters": row_r})
        gc.collect()
        return match_data

    def _extract_row(self, page, top_y, start_x, w, h):
        row_data = []
        for i in range(6):
            drift = i * 0.3
            px_x = start_x + (i * w) + drift
            px_y = top_y
            bbox = (px_x - 3, px_y, px_x + w + 3, px_y + (h * 0.8))
            try:
                text = page.crop(bbox).extract_text()
                val = "?"
                if text:
                    for token in text.split():
                        clean = re.sub(r'[^0-9]', '', token)
                        if clean.isdigit() and len(clean) <= 2:
                            val = clean
                            break
                row_data.append(val)
            except:
                row_data.append("?")
        if all(x == "?" for x in row_data): return None
        return row_data

# ==========================================
# 2. VISUALIZATION HELPERS
# ==========================================

def draw_court_view(starters):
    """Draws a volleyball court with players in position."""
    # Starters list is [Z1, Z2, Z3, Z4, Z5, Z6]
    # Court Positions:
    # ----------------
    # |  4  |  3  |  2  |  (Net)
    # ----------------
    # |  5  |  6  |  1  |
    # ----------------
    
    # Map list index (0-5) to court grid coordinates (row, col)
    # Index 0 (Z1) -> (1, 2)
    # Index 1 (Z2) -> (0, 2)
    # Index 2 (Z3) -> (0, 1)
    # Index 3 (Z4) -> (0, 0)
    # Index 4 (Z5) -> (1, 0)
    # Index 5 (Z6) -> (1, 1)
    
    # We handle potential "?" data safely
    safe_starters = [s if s != "?" else "-" for s in starters]
    while len(safe_starters) < 6: safe_starters.append("-")

    court_data = [
        [safe_starters[3], safe_starters[2], safe_starters[1]], # Front Row (4, 3, 2)
        [safe_starters[4], safe_starters[5], safe_starters[0]]  # Back Row (5, 6, 1)
    ]
    
    fig = px.imshow(court_data, 
                    text_auto=True, 
                    color_continuous_scale='Blues',
                    labels=dict(x="Zone", y="Row", color="Val"),
                    x=['Left', 'Center', 'Right'],
                    y=['Front Row', 'Back Row'])
    fig.update_traces(textfont_size=24)
    fig.update_layout(coloraxis_showscale=False, width=400, height=300, margin=dict(l=20, r=20, t=20, b=20))
    return fig

def calculate_player_stats(df, scores):
    """Calculates Win % for each player based on games they started."""
    player_stats = {} # {player_num: {'sets_played': 0, 'sets_won': 0}}
    
    # Determine set winners
    set_winners = {}
    for i, s in enumerate(scores):
        set_num = i + 1
        winner = "Home" if s['Home'] > s['Away'] else "Away"
        set_winners[set_num] = winner

    # Iterate through lineups
    for index, row in df.iterrows():
        team = row['Team'] # 'Home' or 'Away'
        set_n = row['Set']
        
        # Only process if we know who won this set
        if set_n in set_winners:
            did_win = (team == set_winners[set_n])
            
            # Check all 6 starters
            for player in row['Starters']:
                if player != "?" and player.isdigit():
                    if player not in player_stats:
                        player_stats[player] = {'played': 0, 'won': 0, 'team': team}
                    
                    player_stats[player]['played'] += 1
                    if did_win:
                        player_stats[player]['won'] += 1
    
    # Convert to DataFrame
    stats_list = []
    for p, data in player_stats.items():
        win_pct = (data['won'] / data['played']) * 100 if data['played'] > 0 else 0
        stats_list.append({
            "Player": f"#{p}",
            "Team": data['team'],
            "Sets Played": data['played'],
            "Win %": round(win_pct, 1)
        })
        
    return pd.DataFrame(stats_list).sort_values(by=['Team', 'Win %'], ascending=False)

# ==========================================
# 3. MAIN APP UI
# ==========================================

def main():
    st.title("🏐 VolleyStats Pro")

    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")
        with st.expander("⚙️ Calibration"):
            base_x = st.number_input("Start X", value=123)
            base_y = st.number_input("Start Y", value=88)
            offset_x = st.number_input("Right Offset", value=492) 
            
    if not uploaded_file:
        st.info("Upload PDF to begin.")
        return

    # 1. Extract EVERYTHING
    extractor = VolleySheetExtractor(uploaded_file)
    
    with st.spinner("Analyzing Match..."):
        # A. Get Lineups
        lineups_data = extractor.extract_full_match(base_x, base_y, 23, 20, offset_x, 151, 842)
        df_lineups = pd.DataFrame(lineups_data)
        
        # B. Get Scores (for Win/Loss logic)
        scores_data = extract_scores_text(uploaded_file)

    if df_lineups.empty:
        st.error("No lineup data found.")
        return

    # --- DASHBOARD ---
    
    # Top Metric: Final Score
    home_sets = sum(1 for s in scores_data if s['Home'] > s['Away'])
    away_sets = sum(1 for s in scores_data if s['Away'] > s['Home'])
    st.markdown(f"<h1 style='text-align: center;'>Home {home_sets} - {away_sets} Away</h1>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📊 Player Stats", "🏟️ Rotation Map", "📥 Raw Data"])

    # TAB 1: PLAYER WIN % (Moneyball)
    with tab1:
        if scores_data:
            stats_df = calculate_player_stats(df_lineups, scores_data)
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Home Team Impact")
                home_stats = stats_df[stats_df['Team'] == 'Home']
                st.dataframe(home_stats[['Player', 'Sets Played', 'Win %']], use_container_width=True)
            with c2:
                st.subheader("Away Team Impact")
                away_stats = stats_df[stats_df['Team'] == 'Away']
                st.dataframe(away_stats[['Player', 'Sets Played', 'Win %']], use_container_width=True)
        else:
            st.warning("Could not read set scores from text. Win % unavailable.")

    # TAB 2: VISUAL ROTATIONS
    with tab2:
        st.write("Visualize the starting rotation for any set.")
        c_sel1, c_sel2 = st.columns(2)
        selected_set = c_sel1.selectbox("Select Set", df_lineups['Set'].unique())
        selected_team = c_sel2.selectbox("Select Team", ["Home", "Away"])
        
        # Filter data
        subset = df_lineups[(df_lineups['Set'] == selected_set) & (df_lineups['Team'] == selected_team)]
        
        if not subset.empty:
            starters = subset.iloc[0]['Starters']
            fig = draw_court_view(starters)
            st.plotly_chart(fig, use_container_width=False)
            st.caption("Zones: 4-3-2 (Front) | 5-6-1 (Back)")
        else:
            st.info("No data for this selection.")

    # TAB 3: EXPORT
    with tab3:
        # Format for Excel
        export_df = df_lineups.copy()
        cols = pd.DataFrame(export_df['Starters'].tolist(), columns=[f'Zone {i+1}' for i in range(6)])
        export_df = pd.concat([export_df[['Set', 'Team']], cols], axis=1)
        
        st.dataframe(export_df)
        csv = export_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "match_stats.csv", "text/csv")

if __name__ == "__main__":
    main()
