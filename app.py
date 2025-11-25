import streamlit as st
import pdfplumber
import pandas as pd
import pypdfium2 as pdfium
import re
import gc
import plotly.express as px
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# ==========================================
# 1. ENGINE ROOM (Performance & Extraction)
# ==========================================

@st.cache_data(show_spinner=False)
def get_page_image(file_bytes):
    """High-performance PDF-to-Image renderer."""
    pdf = pdfium.PdfDocument(file_bytes)
    page = pdf[0]
    scale = 1.0 # 72 DPI (PDF Points)
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()
    page.close()
    pdf.close()
    gc.collect()
    return pil_image, scale

def extract_match_info(file):
    """Extracts metadata (Teams, Scores) from text layer."""
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
    team_home = unique_names[1] if len(unique_names) > 1 else "Home Team"
    team_away = unique_names[0] if len(unique_names) > 0 else "Away Team"
    
    # B. Detect Set Scores
    scores = []
    duration_pattern = re.compile(r"(\d{1,3})\s*['’′`]")
    found_table = False
    
    for line in lines:
        if "RESULTATS" in line: found_table = True
        if "Vainqueur" in line: found_table = False
        
        if found_table:
            match = duration_pattern.search(line)
            # Ensure we aren't reading the "Total Match Time" (usually > 60 mins)
            if match and int(match.group(1)) < 60:
                parts = line.split(match.group(0))
                if len(parts) >= 2:
                    left = re.findall(r'\d+', parts[0])
                    right = re.findall(r'\d+', parts[1])
                    if len(left) >= 2 and len(right) >= 1:
                        try:
                            # Logic: Left=[-2] (Score), Right=[0] (Score)
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
                    # Extract Left
                    row_l = self._extract_row(page, current_y, base_x, w, h)
                    if row_l: match_data.append({"Set": set_num, "Team": "Home", "Starters": row_l})
                    # Extract Right
                    row_r = self._extract_row(page, current_y, base_x + offset_x, w, h)
                    if row_r: match_data.append({"Set": set_num, "Team": "Away", "Starters": row_r})
        gc.collect()
        return match_data

    def _extract_row(self, page, top_y, start_x, w, h):
        row_data = []
        for i in range(6):
            drift = i * 0.3
            px_x = start_x + (i * w) + drift
            # Box: 3px wider, Top 80% only
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
# 2. ANALYTICS & VISUALS
# ==========================================

def calculate_real_stats(df, scores):
    """Calculates Win % based on Sets Started."""
    stats = {}
    set_winners = {i+1: ("Home" if s['Home'] > s['Away'] else "Away") for i, s in enumerate(scores)}

    for _, row in df.iterrows():
        team = row['Team']; set_n = row['Set']
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

def draw_court(starters):
    safe = [s if s != "?" else "-" for s in starters]
    while len(safe) < 6: safe.append("-")
    # Court Grid: Front(4,3,2) Back(5,6,1)
    grid = [[safe[3], safe[2], safe[1]], [safe[4], safe[5], safe[0]]]
    
    fig = px.imshow(grid, text_auto=True, color_continuous_scale='Blues',
                    x=['Left', 'Center', 'Right'], y=['Front', 'Back'])
    fig.update_layout(coloraxis_showscale=False, height=300, margin=dict(l=10, r=10, t=10, b=10))
    fig.update_traces(textfont_size=24)
    return fig

def draw_alignment_grid(base_img, bx, by, w, h, off_x, off_y):
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
# 3. MAIN UI
# ==========================================

def main():
    st.title("🏐 VolleyStats Pro")
    st.markdown("**Official Match Sheet Analyzer**")

    with st.sidebar:
        uploaded_file = st.file_uploader("Upload PDF", type="pdf")
        
        # Hidden calibration by default
        with st.expander("⚙️ Settings"):
            base_x = st.number_input("X", 123); base_y = st.number_input("Y", 88)
            w = st.number_input("W", 23); h = st.number_input("H", 20)
            off_x = st.number_input("Right Offset", 492)
            off_y = st.number_input("Down Offset", 151)

    if not uploaded_file:
        st.info("Please upload a file.")
        return

    extractor = VolleySheetExtractor(uploaded_file)
    
    # 1. Process Data
    t_home, t_away, scores = extract_match_info(uploaded_file)
    lineups = extractor.extract_full_match(base_x, base_y, w, h, off_x, off_y, 842)
    df = pd.DataFrame(lineups)

    if df.empty:
        st.error("Could not extract lineups.")
        return

    # 2. Header
    h_wins = sum(1 for s in scores if s['Home'] > s['Away'])
    a_wins = sum(1 for s in scores if s['Away'] > s['Home'])
    
    c1, c2, c3 = st.columns([1, 2, 1])
    c1.metric("HOME", t_home)
    c3.metric("AWAY", t_away)
    c2.markdown(f"<h1 style='text-align: center; color: #4CAF50;'>{h_wins} - {a_wins}</h1>", unsafe_allow_html=True)

    # 3. Tabs
    tab1, tab2, tab3 = st.tabs(["📈 Match Analysis", "🏟️ Rotation Map", "📋 Data & Verification"])

    with tab1:
        # A. Game Flow
        if scores:
            sets_df = pd.DataFrame([
                {"Set": i+1, "Score": f"{s['Home']}-{s['Away']}", "Diff": s['Home']-s['Away'],
                 "Winner": t_home if s['Home']>s['Away'] else t_away,
                 "Clutch": "🔥" if abs(s['Home']-s['Away']) <= 3 else ""}
                for i, s in enumerate(scores)
            ])
            st.subheader("Set-by-Set Breakdown")
            st.dataframe(sets_df.set_index("Set"), use_container_width=True)
            
            # B. Player Stats
            st.subheader("Rotation Impact (Win % when Starting)")
            stats_df = calculate_real_stats(df, scores)
            if not stats_df.empty:
                ca, cb = st.columns(2)
                with ca: st.dataframe(stats_df[stats_df['Team']=="Home"], use_container_width=True)
                with cb: st.dataframe(stats_df[stats_df['Team']=="Away"], use_container_width=True)
        else:
            st.warning("Scores not found in text.")

    with tab2:
        c_s, c_t = st.columns(2)
        sel_set = c_s.selectbox("Set", df['Set'].unique())
        sel_team = c_t.selectbox("Team", ["Home", "Away"])
        
        row = df[(df['Set'] == sel_set) & (df['Team'] == sel_team)]
        if not row.empty:
            starters = row.iloc[0]['Starters']
            st.plotly_chart(draw_court(starters), use_container_width=False)
        else: st.info("No data.")

    with tab3:
        # Debug Image
        try:
            f_bytes = uploaded_file.getvalue()
            img, _ = get_page_image(f_bytes)
            st.image(draw_alignment_grid(img, base_x, base_y, w, h, off_x, off_y), caption="Extraction Grid")
        except: pass
        
        # CSV Export
        export = df.copy()
        cols = pd.DataFrame(export['Starters'].tolist(), columns=[f'Z{i+1}' for i in range(6)])
        export = pd.concat([export[['Set', 'Team']], cols], axis=1)
        st.dataframe(export)
        st.download_button("Download CSV", export.to_csv(index=False).encode('utf-8'), "match.csv", "text/csv")

if __name__ == "__main__":
    main()
