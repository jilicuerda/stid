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

def extract_match_info(file):
    """
    Extracts Team Names and Set Scores using text analysis.
    """
    text = ""
    with pdfplumber.open(file) as pdf:
        text = pdf.pages[0].extract_text()
    
    lines = text.split('\n')
    
    # --- 1. TEAM NAMES (Robust 'Début' Logic) ---
    potential_names = []
    for line in lines:
        if "Début:" in line:
            segment = line.split("Début:")[0]
            if "Fin:" in segment:
                segment = segment.split("Fin:")[-1]
                segment = re.sub(r'\d{2}:\d{2}\s*R?', '', segment)
            
            clean_name = re.sub(r'\b(SA|SB|S|R)\b', '', segment)
            clean_name = re.sub(r'^[^A-Z]+|[^A-Z]+$', '', clean_name).strip()
            
            if len(clean_name) > 3:
                potential_names.append(clean_name)

    unique_names = list(dict.fromkeys(potential_names))
    team_home = unique_names[1] if len(unique_names) > 1 else "Home Team"
    team_away = unique_names[0] if len(unique_names) > 0 else "Away Team"
    
    # --- 2. SCORES ---
    scores = []
    duration_pattern = re.compile(r"(\d{1,3})\s*['’′`]")
    found_table = False
    
    for line in lines:
        if "RESULTATS" in line: found_table = True
        if "Vainqueur" in line: found_table = False
        
        if found_table:
            match = duration_pattern.search(line)
            if match:
                duration_val = int(match.group(1))
                # Only look at lines that are actual sets (duration < 60 mins)
                # This prevents reading the "Total Match Time" line as a score
                if duration_val < 60:
                    parts = line.split(match.group(0))
                    if len(parts) >= 2:
                        left = re.findall(r'\d+', parts[0])
                        right = re.findall(r'\d+', parts[1])
                        if left and right:
                            try:
                                s_home = int(left[-1])
                                s_away = int(right[0])
                                # Sanity check: A set score must be reasonable (e.g. > 5)
                                if s_home > 5 and s_away > 5:
                                    scores.append({"Home": s_home, "Away": s_away})
                            except: pass
                            
    return team_home, team_away, scores

class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf_file = pdf_file

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y, p_height):
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
    # Handle short lists
    safe_starters = [s if s != "?" else "-" for s in starters]
    while len(safe_starters) < 6: safe_starters.append("-")

    court_data = [
        [safe_starters[3], safe_starters[2], safe_starters[1]], 
        [safe_starters[4], safe_starters[5], safe_starters[0]]
    ]
    
    fig = px.imshow(court_data, 
                    text_auto=True, 
                    color_continuous_scale='Blues',
                    labels=dict(x="Zone", y="Row", color="Val"),
                    x=['Left (4/5)', 'Center (3/6)', 'Right (2/1)'],
                    y=['Front Row', 'Back Row'])
    fig.update_traces(textfont_size=24)
    fig.update_layout(coloraxis_showscale=False, width=400, height=300, margin=dict(l=20, r=20, t=20, b=20))
    return fig

def calculate_player_stats(df, scores):
    player_stats = {}
    
    # Map Set Number to Winner
    set_winners = {}
    for i, s in enumerate(scores):
        set_num = i + 1
        winner = "Home" if s['Home'] > s['Away'] else "Away"
        set_winners[set_num] = winner

    for index, row in df.iterrows():
        team = row['Team'] 
        set_n = row['Set']
        
        if set_n in set_winners:
            did_win = (team == set_winners[set_n])
            
            for player in row['Starters']:
                if player != "?" and player.isdigit():
                    if player not in player_stats:
                        player_stats[player] = {'played': 0, 'won': 0, 'team': team}
                    
                    player_stats[player]['played'] += 1
                    if did_win:
                        player_stats[player]['won'] += 1
    
    stats_list = []
    for p, data in player_stats.items():
        win_pct = (data['won'] / data['played']) * 100 if data['played'] > 0 else 0
        stats_list.append({
            "Player": f"#{p}",
            "Team": data['team'],
            "Sets Played": data['played'],
            "Win %": round(win_pct, 1)
        })
        
    if not stats_list: return pd.DataFrame()
    return pd.DataFrame(stats_list).sort_values(by=['Team', 'Win %'], ascending=False)

def draw_grid(base_img, bx, by, w, h, off_x, off_y):
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    
    for s in range(4): 
        cur_y = by + (s * off_y)
        # Left (Red)
        for i in range(6):
            drift = i * 0.3
            x = bx + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="red", width=2)
        # Right (Blue)
        cur_x = bx + off_x
        for i in range(6):
            drift = i * 0.3
            x = cur_x + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="blue", width=2)
    return img

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

    extractor = VolleySheetExtractor(uploaded_file)
    
    # 1. Extract Info (Scores & Names)
    t_home, t_away, scores_data = extract_match_info(uploaded_file)
    
    # 2. Extract Lineups
    with st.spinner("Analyzing Match..."):
        lineups_data = extractor.extract_full_match(base_x, base_y, 23, 20, offset_x, 151, 842)
        df_lineups = pd.DataFrame(lineups_data)

    if df_lineups.empty:
        st.error("No lineup data found.")
        return

    # --- DASHBOARD ---
    
    # Calculate Match Winner based on Sets Won
    home_wins = sum(1 for s in scores_data if s['Home'] > s['Away'])
    away_wins = sum(1 for s in scores_data if s['Away'] > s['Home'])
    
    c_head1, c_head2, c_head3 = st.columns([1, 2, 1])
    c_head1.metric("Home", t_home)
    c_head3.metric("Away", t_away)
    c_head2.markdown(f"<h1 style='text-align: center; color: #FF4B4B;'>{home_wins} - {away_wins}</h1>", unsafe_allow_html=True)

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📊 Player Stats", "🏟️ Rotation Map", "📥 Raw Data"])

    # TAB 1: PLAYER WIN %
    with tab1:
        if scores_data:
            stats_df = calculate_player_stats(df_lineups, scores_data)
            
            if not stats_df.empty:
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader(f"{t_home} Stats")
                    home_stats = stats_df[stats_df['Team'] == 'Home']
                    st.dataframe(home_stats[['Player', 'Sets Played', 'Win %']], use_container_width=True)
                with c2:
                    st.subheader(f"{t_away} Stats")
                    away_stats = stats_df[stats_df['Team'] == 'Away']
                    st.dataframe(away_stats[['Player', 'Sets Played', 'Win %']], use_container_width=True)
            else:
                st.warning("No player stats calculated.")
        else:
            st.warning("Could not read set scores from text.")

    # TAB 2: VISUAL ROTATIONS
    with tab2:
        c_sel1, c_sel2 = st.columns(2)
        selected_set = c_sel1.selectbox("Select Set", df_lineups['Set'].unique())
        selected_team = c_sel2.selectbox("Select Team", ["Home", "Away"])
        
        subset = df_lineups[(df_lineups['Set'] == selected_set) & (df_lineups['Team'] == selected_team)]
        
        if not subset.empty:
            starters = subset.iloc[0]['Starters']
            fig = draw_court_view(starters)
            st.plotly_chart(fig, use_container_width=False)
        else:
            st.info("No data for this selection.")

    # TAB 3: EXPORT
    with tab3:
        # Draw Debug Grid to verify alignment if needed
        try:
            file_bytes = uploaded_file.getvalue()
            base_img, _ = get_page_image(file_bytes)
            debug_img = draw_grid(base_img, base_x, base_y, 23, 20, offset_x, 151)
            with st.expander("View Alignment Grid"):
                st.image(debug_img)
        except: pass

        export_df = df_lineups.copy()
        cols = pd.DataFrame(export_df['Starters'].tolist(), columns=[f'Zone {i+1}' for i in range(6)])
        export_df = pd.concat([export_df[['Set', 'Team']], cols], axis=1)
        
        st.dataframe(export_df)
        csv = export_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "match_stats.csv", "text/csv")

if __name__ == "__main__":
    main()
