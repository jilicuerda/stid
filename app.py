import streamlit as st
import pdfplumber
import pandas as pd
import pypdfium2 as pdfium
import re
import gc
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# ==========================================
# 1. UTILS & SIMULATION (For Advanced Stats)
# ==========================================

def generate_mock_player_stats(team_name):
    """
    Generates sample data for Hitting Efficiency Analysis.
    Since PDF lacks attack logs, we simulate this to show the feature.
    """
    players = [f"#{i}" for i in [1, 4, 7, 9, 10, 12, 15, 18]]
    data = []
    for player in players:
        # Simulate realistic volleyball stats
        kills = np.random.randint(2, 18)
        errors = np.random.randint(0, 6)
        blocked = np.random.randint(0, 3)
        attempts = kills + errors + blocked + np.random.randint(2, 10)
        
        # Efficiency Formula: (K - E - B) / Total Attempts
        eff = (kills - errors - blocked) / attempts if attempts > 0 else 0.0
        
        data.append({
            "Player": player,
            "Kills": kills,
            "Errors": errors,
            "Blocked": blocked,
            "Attempts": attempts,
            "Efficiency": round(eff, 3)
        })
    return pd.DataFrame(data)

# ==========================================
# 2. CORE ENGINES (IMAGE & TEXT)
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
    """Extracts Team Names and Set Scores."""
    text = ""
    with pdfplumber.open(file) as pdf:
        text = pdf.pages[0].extract_text()
    
    lines = text.split('\n')
    potential_names = []
    for line in lines:
        if "Début:" in line:
            parts = line.split("Début:")
            for part in parts[:-1]:
                if "Fin:" in part: part = part.split("Fin:")[-1]
                part = re.sub(r'\d{2}:\d{2}\s*R?', '', part)
                clean_name = re.sub(r'\b(SA|SB|S|R)\b', '', part)
                clean_name = re.sub(r'^[^A-Z]+|[^A-Z]+$', '', clean_name).strip()
                if len(clean_name) > 3: potential_names.append(clean_name)

    unique_names = list(dict.fromkeys(potential_names))
    team_home = unique_names[1] if len(unique_names) > 1 else "Home Team"
    team_away = unique_names[0] if len(unique_names) > 0 else "Away Team"
    
    scores = []
    duration_pattern = re.compile(r"(\d{1,3})\s*['’′`]")
    found_table = False
    for line in lines:
        if "RESULTATS" in line: found_table = True
        if "Vainqueur" in line: found_table = False
        if found_table:
            match = duration_pattern.search(line)
            if match and int(match.group(1)) < 60:
                parts = line.split(match.group(0))
                if len(parts) >= 2:
                    left = re.findall(r'\d+', parts[0])
                    right = re.findall(r'\d+', parts[1])
                    if len(left) >= 2 and len(right) >= 1:
                        try:
                            scores.append({"Home": int(left[-2]), "Away": int(right[0])})
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
                    row_l = self._extract_row(page, current_y, base_x, w, h)
                    if row_l: match_data.append({"Set": set_num, "Team": "Home", "Starters": row_l})
                    row_r = self._extract_row(page, current_y, base_x + offset_x, w, h)
                    if row_r: match_data.append({"Set": set_num, "Team": "Away", "Starters": row_r})
        gc.collect()
        return match_data

    def _extract_row(self, page, top_y, start_x, w, h):
        row_data = []
        for i in range(6):
            drift = i * 0.3
            px_x = start_x + (i * w) + drift
            bbox = (px_x - 3, top_y, px_x + w + 3, top_y + (h * 0.8))
            try:
                text = page.crop(bbox).extract_text()
                val = "?"
                if text:
                    for token in text.split():
                        clean = re.sub(r'[^0-9]', '', token)
                        if clean.isdigit() and len(clean) <= 2:
                            val = clean; break
                row_data.append(val)
            except: row_data.append("?")
        if all(x == "?" for x in row_data): return None
        return row_data

# ==========================================
# 3. VISUALIZERS (COURT & CHARTS)
# ==========================================

def draw_court_view(starters):
    """Visualizes the starting rotation."""
    safe_starters = [s if s != "?" else "-" for s in starters]
    while len(safe_starters) < 6: safe_starters.append("-")

    # Standard Rotation Layout:
    # 4 3 2 (Front)
    # 5 6 1 (Back)
    court_data = [
        [safe_starters[3], safe_starters[2], safe_starters[1]], 
        [safe_starters[4], safe_starters[5], safe_starters[0]]
    ]
    
    fig = px.imshow(court_data, text_auto=True, color_continuous_scale='Blues',
                    labels=dict(x="Zone", y="Row", color="Val"),
                    x=['Left', 'Center', 'Right'], y=['Front Row', 'Back Row'])
    fig.update_traces(textfont_size=24)
    fig.update_layout(coloraxis_showscale=False, height=300)
    return fig

def draw_grid(base_img, bx, by, w, h, off_x, off_y):
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    for s in range(4): 
        cur_y = by + (s * off_y)
        for i in range(6):
            drift = i * 0.3
            x = bx + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="red", width=2)
        cur_x = bx + off_x
        for i in range(6):
            drift = i * 0.3
            x = cur_x + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="blue", width=2)
    return img

# ==========================================
# 4. MAIN APP UI
# ==========================================

def main():
    st.title("🏐 VolleyStats Pro")
    st.caption("Advanced Statistical Framework Implementation")

    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet (PDF)", type="pdf")
        with st.expander("⚙️ Calibration"):
            base_x = st.number_input("Start X", value=123)
            base_y = st.number_input("Start Y", value=88)
            offset_x = st.number_input("Right Offset", value=492) 
            
    if not uploaded_file:
        st.info("Upload a PDF to generate analytics.")
        return

    extractor = VolleySheetExtractor(uploaded_file)
    
    # Extract Data
    t_home, t_away, scores = extract_match_info(uploaded_file)
    lineups_data = extractor.extract_full_match(base_x, base_y, 23, 20, offset_x, 151, 842)
    df_lineups = pd.DataFrame(lineups_data)

    if df_lineups.empty:
        st.error("No lineup data found.")
        return

    # Match Header
    home_wins = sum(1 for s in scores if s['Home'] > s['Away'])
    away_wins = sum(1 for s in scores if s['Away'] > s['Home'])
    c1, c2, c3 = st.columns([2, 1, 2])
    c1.metric("HOME", t_home)
    c3.metric("AWAY", t_away)
    c2.markdown(f"<h1 style='text-align: center;'>{home_wins} - {away_wins}</h1>", unsafe_allow_html=True)

    # Tabs based on Report Structure
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Real Stats (Red Zone)", 
        "🚀 Efficiency (Simulated)", 
        "🔄 Rotation Analysis (Simulated)", 
        "🏟️ Court Map"
    ])

    # --- TAB 1: REAL DATA (RED ZONE) ---
    with tab1:
        st.subheader("Contextual Metrics: The 'Red Zone'")
        st.markdown("Performance in sets decided by a margin of **≤ 3 points**.")
        
        if scores:
            clutch_data = []
            for i, s in enumerate(scores):
                margin = abs(s['Home'] - s['Away'])
                if margin <= 3:
                    winner = t_home if s['Home'] > s['Away'] else t_away
                    clutch_data.append({
                        "Set": i+1, 
                        "Score": f"{s['Home']}-{s['Away']}", 
                        "Margin": margin,
                        "Winner": winner
                    })
            
            if clutch_data:
                st.dataframe(pd.DataFrame(clutch_data), use_container_width=True)
                st.success(f"This match had {len(clutch_data)} 'Clutch' sets.")
            else:
                st.info("No sets reached the 'Red Zone' (all wins were >3 points).")
        else:
            st.warning("Score data unavailable.")

    # --- TAB 2: EFFICIENCY (SIMULATED) ---
    with tab2:
        st.warning("⚠️ **Demo Mode:** Individual attack logs are not in the PDF. Showing framework based on.")
        st.subheader("Hitting Efficiency Matrix")
        st.latex(r"Hitting Efficiency = \frac{(Kills - Errors - Blocked)}{Total Attempts}")
        
        mock_df = generate_mock_player_stats(t_away)
        
        # Scatter Plot: Efficiency vs Volume
        fig = px.scatter(mock_df, x="Attempts", y="Efficiency", size="Kills", color="Efficiency",
                         hover_name="Player", text="Player", color_continuous_scale="RdYlGn",
                         range_y=[-0.2, 0.6])
        fig.add_hline(y=0.300, line_dash="dash", line_color="green", annotation_text="Elite Benchmark (>0.300)")
        
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(mock_df)

    # --- TAB 3: ROTATION ANALYSIS (SIMULATED) ---
    with tab3:
        st.warning("⚠️ **Demo Mode:** Point-by-point logs are required for Sideout %. Showing framework based on.")
        st.subheader("Sideout % by Rotation")
        
        # Mock Radar Data
        rotations = ['Rot 1', 'Rot 2', 'Rot 3', 'Rot 4', 'Rot 5', 'Rot 6']
        mock_so = [35, 60, 55, 42, 65, 50] # Hypothetical data
        
        fig_radar = go.Figure(data=go.Scatterpolar(
            r=mock_so, theta=rotations, fill='toself', name='Sideout %'
        ))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False)
        
        c_rad, c_txt = st.columns([2, 1])
        with c_rad: st.plotly_chart(fig_radar, use_container_width=True)
        with c_txt: 
            st.info("**Insight:** Rotation 1 is effectively stuck (35%). Consider substitution strategy.")

    # --- TAB 4: REAL DATA (COURT MAP) ---
    with tab4:
        st.subheader("Starting Rotations")
        c_sel1, c_sel2 = st.columns(2)
        selected_set = c_sel1.selectbox("Set", df_lineups['Set'].unique())
        selected_team = c_sel2.selectbox("Team", ["Home", "Away"])
        
        subset = df_lineups[(df_lineups['Set'] == selected_set) & (df_lineups['Team'] == selected_team)]
        
        if not subset.empty:
            starters = subset.iloc[0]['Starters']
            fig = draw_court_view(starters)
            st.plotly_chart(fig, use_container_width=False)
            

[Image of volleyball rotation diagram]

        else:
            st.info("No data.")

        # Export
        with st.expander("📥 Download Extracted Data"):
            export_df = df_lineups.copy()
            cols = pd.DataFrame(export_df['Starters'].tolist(), columns=[f'Zone {i+1}' for i in range(6)])
            export_df = pd.concat([export_df[['Set', 'Team']], cols], axis=1)
            st.dataframe(export_df)
            csv = export_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "match_data.csv", "text/csv")

if __name__ == "__main__":
    main()