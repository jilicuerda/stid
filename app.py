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
# 1. ENGINE (Reading Data)
# ==========================================

@st.cache_data(show_spinner=False)
def get_page_image(file_bytes):
    """Renders PDF page to image using C++ engine (Fast & Low RAM)."""
    pdf = pdfium.PdfDocument(file_bytes)
    page = pdf[0]
    scale = 1.0 # 72 DPI
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
    
    # A. Detect Team Names
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
    t_home = unique_names[1] if len(unique_names) > 1 else "Home Team"
    t_away = unique_names[0] if len(unique_names) > 0 else "Away Team"
    
    # B. Detect Set Scores
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
                if duration_val < 60: # Filter out Total Duration
                    parts = line.split(match.group(0))
                    if len(parts) >= 2:
                        left = re.findall(r'\d+', parts[0])
                        right = re.findall(r'\d+', parts[1])
                        if len(left) >= 2 and len(right) >= 1:
                            try:
                                scores.append({"Home": int(left[-2]), "Away": int(right[0]), "Duration": duration_val})
                            except: pass
    return t_home, t_away, scores

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
            # Box: +3px width, Top 80% height
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
# 2. ANALYTICS (Math)
# ==========================================

def calculate_player_stats(df, scores):
    """Calculates Win % for starters."""
    stats = {}
    set_winners = {i+1: ("Home" if s['Home'] > s['Away'] else "Away") for i, s in enumerate(scores)}

    for _, row in df.iterrows():
        team = row['Team']
        set_n = row['Set']
        if set_n in set_winners:
            won = (team == set_winners[set_n])
            for p in row['Starters']:
                if p.isdigit():
                    if p not in stats: stats[p] = {'team': team, 'played': 0, 'won': 0}
                    stats[p]['played'] += 1
                    if won: stats[p]['won'] += 1
    
    data = []
    for p, s in stats.items():
        pct = (s['won']/s['played'])*100 if s['played'] > 0 else 0
        data.append({"Player": f"#{p}", "Team": s['team'], "Sets": s['played'], "Win %": round(pct, 1)})
    
    if not data: return pd.DataFrame()
    return pd.DataFrame(data).sort_values(['Team', 'Win %'], ascending=[True, False])

def analyze_money_time(scores, t_home, t_away):
    """Analyzes close sets."""
    analysis = []
    clutch_stats = {t_home: 0, t_away: 0}
    
    for i, s in enumerate(scores):
        diff = abs(s['Home'] - s['Away'])
        winner = t_home if s['Home'] > s['Away'] else t_away
        
        if max(s['Home'], s['Away']) >= 20 and diff <= 3:
            clutch_stats[winner] += 1
            analysis.append(f"✅ Set {i+1} ({s['Home']}-{s['Away']}) : Won by **{winner}** (Clutch).")
        elif diff > 5:
            analysis.append(f"⚠️ Set {i+1} ({s['Home']}-{s['Away']}) : Comfortable win for {winner}.")
        else:
            analysis.append(f"ℹ️ Set {i+1} ({s['Home']}-{s['Away']}) : Standard win for {winner}.")
            
    return analysis, clutch_stats

# ==========================================
# 3. VISUALS (Drawings)
# ==========================================

def draw_court_view(starters):
    safe = [s if s != "?" else "-" for s in starters]
    while len(safe) < 6: safe.append("-")
    # Grid: Front(4,3,2) Back(5,6,1)
    grid = [[safe[3], safe[2], safe[1]], [safe[4], safe[5], safe[0]]]
    
    fig = px.imshow(grid, text_auto=True, color_continuous_scale='Blues',
                    x=['Left', 'Center', 'Right'], y=['Front Row', 'Back Row'])
    fig.update_layout(coloraxis_showscale=False, height=300, margin=dict(l=10, r=10, t=10, b=10))
    fig.update_traces(textfont_size=24)
    return fig

def draw_grid(base_img, bx, by, w, h, off_x, off_y):
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    for s in range(4):
        y = by + (s * off_y)
        for i in range(6):
            d = i * 0.3
            draw.rectangle([bx+(i*w)+d, y, bx+(i*w)+d+w, y+h], outline="red", width=2)
            draw.rectangle([bx+off_x+(i*w)+d, y, bx+off_x+(i*w)+d+w, y+h], outline="blue", width=2)
    return img

# ==========================================
# 4. MAIN APP
# ==========================================

def main():
    st.title("🏐 VolleyStats Pro")

    with st.sidebar:
        uploaded_file = st.file_uploader("Upload PDF", type="pdf")
        with st.expander("⚙️ Calibration"):
            base_x = st.number_input("X Start", 123); base_y = st.number_input("Y Start", 88)
            w = st.number_input("Width", 23); h = st.number_input("Height", 20)
            off_x = st.number_input("Right Offset", 492)
            off_y = st.number_input("Down Offset", 151)

    if not uploaded_file:
        st.info("Please upload a file.")
        return

    extractor = VolleySheetExtractor(uploaded_file)
    t_home, t_away, scores = extract_match_info(uploaded_file)
    
    with st.spinner("Extracting Data..."):
        lineups = extractor.extract_full_match(base_x, base_y, w, h, off_x, off_y, 842)
        df = pd.DataFrame(lineups)

    if df.empty:
        st.error("Extraction failed. Check PDF.")
        return

    # Scoreboard
    h_wins = sum(1 for s in scores if s['Home'] > s['Away'])
    a_wins = sum(1 for s in scores if s['Away'] > s['Home'])
    
    c1, c2, c3 = st.columns([2, 1, 2])
    c1.metric("HOME", t_home)
    c3.metric("AWAY", t_away)
    c2.markdown(f"<h1 style='text-align: center; color: #FF4B4B;'>{h_wins} - {a_wins}</h1>", unsafe_allow_html=True)

    # Analytics Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["1. Money Time", "2. Players", "3. Rotations", "4. Duration", "5. Export"])

    with tab1:
        if scores:
            analysis, clutch = analyze_money_time(scores, t_home, t_away)
            c_mt1, c_mt2 = st.columns(2)
            c_mt1.metric(f"Clutch Wins ({t_home})", clutch.get(t_home, 0))
            c_mt2.metric(f"Clutch Wins ({t_away})", clutch.get(t_away, 0))
            for item in analysis: st.write(item)
        else: st.warning("No score data found.")

    with tab2:
        if scores:
            stats = calculate_player_stats(df, scores)
            if not stats.empty:
                ca, cb = st.columns(2)
                with ca: st.dataframe(stats[stats['Team']=="Home"], use_container_width=True)
                with cb: st.dataframe(stats[stats['Team']=="Away"], use_container_width=True)

    with tab3:
        c_s, c_t = st.columns(2)
        sel_set = c_s.selectbox("Set", df['Set'].unique())
        sel_team = c_t.selectbox("Team", ["Home", "Away"])
        row = df[(df['Set'] == sel_set) & (df['Team'] == sel_team)]
        if not row.empty:
            st.plotly_chart(draw_court_view(row.iloc[0]['Starters']), use_container_width=False)
            

#[Image of volleyball rotation diagram]


    with tab4:
        if scores:
            durations = [s['Duration'] for s in scores if 'Duration' in s]
            if durations:
                st.metric("Total Duration", f"{sum(durations)} min")
                st.bar_chart(pd.DataFrame({"Set": range(1, len(durations)+1), "Minutes": durations}).set_index("Set"))

    with tab5:
        try:
            f_bytes = uploaded_file.getvalue()
            img, _ = get_page_image(f_bytes)
            st.image(draw_grid(img, base_x, base_y, w, h, off_x, off_y))
        except: pass
        
        export = df.copy()
        cols = pd.DataFrame(export['Starters'].tolist(), columns=[f'Z{i+1}' for i in range(6)])
        final = pd.concat([export[['Set', 'Team']], cols], axis=1)
        st.download_button("Download CSV", final.to_csv(index=False).encode('utf-8'), "match.csv", "text/csv")

if __name__ == "__main__":
    main()

