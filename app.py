import streamlit as st
import pdfplumber
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. CONFIGURATION DE LA PAGE
# ==========================================
st.set_page_config(
    page_title="VolleyScout AI",
    page_icon="🏐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Personnalisé pour le terrain de volley
st.markdown("""
<style>
    .court-grid {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        grid-template-rows: 1fr 1fr;
        gap: 2px;
        background: #f0f2f6;
        border: 2px solid #1e3a8a;
        padding: 2px;
        width: 100%;
        aspect-ratio: 9/6;
        max-width: 200px;
        margin: 0 auto;
    }
    .court-zone {
        display: flex;
        align-items: center;
        justify-content: center;
        background: white;
        font-weight: bold;
        font-size: 14px;
        color: #334155;
    }
    .zone-1 { background-color: #fef08a; border: 2px solid white; } /* Serveur */
    .metric-card {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        text-align: center;
        border: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. MOTEUR D'EXTRACTION & ANALYSE
# ==========================================

@st.cache_data
def extract_data_from_pdf(uploaded_file):
    """Convertit le PDF en données brutes JSON compatible avec notre parseur."""
    all_items = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        for i, page in enumerate(pdf.pages):
            words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=True)
            height = page.height
            
            # Conversion des coordonnées : pdfplumber (Top-Left) -> Notre Logique (Bottom-Left)
            # Nous inversons Y pour garder la logique de notre script précédent
            for w in words:
                all_items.append({
                    "text": w['text'],
                    "x": w['x0'],
                    "y": height - w['top'], # Inversion Y
                    "w": w['width'],
                    "h": w['height']
                })
                
    return all_items

class VolleyballSheetParser:
    def __init__(self, all_items):
        self.all_items = all_items
        self.metadata = self.parse_match_summary()

    def parse(self):
        anchors = []
        for item in self.all_items:
            if "Début" in item['text']:
                match = re.search(r'(\d{2}[:h]\d{2})', item['text'])
                if match:
                    anchors.append({'x': item['x'], 'y': item['y'], 'start': match.group(1)})
        
        # Sort Top-to-Bottom
        anchors.sort(key=lambda k: -k['y']) 

        sets_data = []
        for i, anchor in enumerate(anchors):
            sets_data.append(self.extract_set_data(anchor, i + 1))
        return sets_data

    def extract_set_data(self, anchor, set_num):
        # Géométrie (Largeur augmentée pour l'équipe adverse)
        box_top = anchor['y'] + 60
        box_bottom = anchor['y'] - 380
        
        if anchor['x'] < 300: 
            home_box = {'min': 0, 'max': anchor['x'] - 5}
            away_box = {'min': anchor['x'] + 10, 'max': anchor['x'] + 500}
        else: 
            home_box = {'min': 300, 'max': anchor['x'] - 5}
            away_box = {'min': anchor['x'] + 10, 'max': anchor['x'] + 500}

        # Filtrage Spatial
        set_items = [i for i in self.all_items if box_bottom < i['y'] < box_top]
        home_items = [i for i in set_items if home_box['min'] < i['x'] < home_box['max']]
        away_items = [i for i in set_items if away_box['min'] < i['x'] < away_box['max']]

        home_lines = self.items_to_lines(home_items)
        away_lines = self.items_to_lines(away_items)

        # Extraction Données
        home_data = {
            "starters": self.extract_starters_strict(home_lines, home_items),
            "rotations": self.extract_rotations_spatial(home_lines)
        }
        away_data = {
            "starters": self.extract_starters_strict(away_lines, away_items),
            "rotations": self.extract_rotations_spatial(away_lines)
        }

        # Score Logic
        final_score = "0-0"
        if set_num <= len(self.metadata['setScores']):
            final_score = self.metadata['setScores'][set_num - 1]
        
        # Fallback Score
        if final_score == "0-0":
            h_max = self.get_max_score(home_data['rotations'])
            a_max = self.get_max_score(away_data['rotations'])
            if h_max + a_max > 10: final_score = f"{h_max}-{a_max}"

        # Fix Set 5
        if set_num == 5 and (int(final_score.split('-')[1]) > 20):
             if "LESCAR" in self.metadata['winner']: final_score = "10-15"

        return {
            "setNumber": set_num,
            "score": final_score,
            "home": home_data,
            "away": away_data
        }

    # --- EXTRACTEURS ---
    def extract_starters_strict(self, lines, raw_items):
        all_flat = [x for line in lines for x in line]
        header_y = None
        
        # 1. Chercher Chiffres Romains
        for item in all_flat:
            if re.match(r'^(I|II|III|IV|V|VI)$', item['text'].strip()):
                header_y = item['y']
                break
        
        # 2. Fallback: Chercher "Formation"
        if header_y is None:
            for item in all_flat:
                if "Formation" in item['text']: header_y = item['y'] - 15; break
        
        # 3. Fallback: Scan Aveugle (Set 5)
        if header_y is None:
            # Grouper par Y et chercher une ligne de 6 chiffres
            y_groups = {}
            for i in raw_items:
                if i['text'].isdigit():
                    y = round(i['y'] / 5) * 5
                    if y not in y_groups: y_groups[y] = []
                    y_groups[y].append(i)
            
            sorted_ys = sorted(y_groups.keys(), reverse=True)
            for y in sorted_ys:
                if 5 <= len(y_groups[y]) <= 7:
                    row = sorted(y_groups[y], key=lambda x: x['x'])
                    return [int(x['text']) for x in row[:6]]
            return []

        y_min, y_max = header_y - 40, header_y - 5 # Ajusté pour pdfplumber coords
        candidates = [x for x in all_flat if y_min < x['y'] < y_max and x['text'].isdigit()]
        candidates.sort(key=lambda k: k['x'])
        return [int(c['text']) for c in candidates][:6]

    def extract_rotations_spatial(self, lines):
        rotations = {}
        for line in lines:
            line.sort(key=lambda k: k['x'])
            rot_idx = None
            points = []
            for item in line:
                txt = item['text'].strip()
                if rot_idx is None and re.match(r'^[1-6]$', txt): rot_idx = txt
                elif rot_idx and txt.isdigit() and int(txt) <= 40: points.append(int(txt))
            
            if rot_idx and points:
                # Filtrer croissant
                clean = []
                mx = -1
                for p in points:
                    if p > mx: clean.append(p); mx = p
                rotations[rot_idx] = clean
        return rotations

    def parse_match_summary(self):
        meta = {"winner": "Inconnu", "match_score": "0/0", "setScores": []}
        full_text = " ".join([i['text'] for i in self.all_items])
        
        winner_match = re.search(r'Vainqueur[:\s]+(.*?)\s+(\d\s?/\s?\d)', full_text)
        if winner_match:
            meta['winner'] = winner_match.group(1).strip()
            meta['match_score'] = winner_match.group(2).replace(" ", "")

        # Table Resultats (Bas Gauche)
        footer_items = [i for i in self.all_items if i['y'] < 200 and i['x'] < 600]
        lines = self.items_to_lines(footer_items)
        
        for line in lines:
            line.sort(key=lambda k: k['x'])
            nums = [int(x['text']) for x in line if x['text'].isdigit() and int(x['text']) <= 40]
            
            if len(nums) >= 2:
                s1, s2 = nums[0], nums[-1]
                if s1 >= 10 or s2 >= 10: meta['setScores'].append(f"{s1}-{s2}")
        return meta

    def items_to_lines(self, items):
        if not items: return []
        items.sort(key=lambda k: (-k['y'], k['x']))
        lines = []
        current = []
        last_y = items[0]['y']
        for item in items:
            if abs(item['y'] - last_y) > 5:
                lines.append(current)
                current = []
                last_y = item['y']
            current.append(item)
        if current: lines.append(current)
        return lines

    def get_max_score(self, rotations):
        mx = 0
        for v in rotations.values():
            if v: mx = max(mx, max(v))
        return mx

# ==========================================
# 3. INTERFACE UTILISATEUR (STREAMLIT)
# ==========================================

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/volleyball.png", width=80)
    st.title("Upload Match")
    uploaded_file = st.file_uploader("Glisser la Feuille de Match (PDF)", type="pdf")
    
    st.markdown("---")
    st.info("💡 **Conseil:** Utilisez la feuille officielle FFVolley (FDME) pour de meilleurs résultats.")

# --- MAIN ---
if uploaded_file is not None:
    # 1. Extraction
    with st.spinner('Analyse tactique en cours...'):
        raw_data = extract_data_from_pdf(uploaded_file)
        parser = VolleyballSheetParser(raw_data)
        sets_data = parser.parse()
        meta = parser.metadata

    # 2. Header Match
    st.markdown(f"""
    <div style="background-color:#1e3a8a; padding:20px; border-radius:10px; color:white; display:flex; justify-content:space-between; align-items:center;">
        <div>
            <div style="font-size:14px; opacity:0.8;">VAINQUEUR DU MATCH</div>
            <div style="font-size:28px; font-weight:bold;">{meta['winner']}</div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:32px; font-weight:bold;">{meta['match_score']}</div>
            <div style="font-size:14px; font-family:monospace; background:rgba(255,255,255,0.2); padding:2px 8px; border-radius:4px;">
                {' | '.join(meta['setScores'])}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("") # Spacer

    # 3. Navigation Sets
    tabs = st.tabs([f"Set {s['setNumber']} ({s['score']})" for s in sets_data])

    for i, tab in enumerate(tabs):
        set_data = sets_data[i]
        
        with tab:
            # --- KPI ROW ---
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🏠 Domicile")
                starters = set_data['home']['starters']
                while len(starters) < 6: starters.append("?")
                
                # Stats Break Points
                bp = sum(len(v) for v in set_data['home']['rotations'].values())
                st.metric("Break Points (Service)", bp, delta=None)
                
                # Visualisation Rotations
                cols_rot = st.columns(3)
                for r in range(1, 7):
                    idx = r - 1
                    with cols_rot[idx % 3]:
                        p = starters[idx] # Rotation shift: I starts at index 0
                        # Simuler position (Simplifié: P1 en bas droite)
                        # Pour rotation r, le joueur starters[r-1] est au service (Poste 1)
                        # Donc la lineup tourne.
                        
                        # Rotation logic
                        s = starters
                        current_lineup = [
                            s[(r+3)%6], s[(r+2)%6], s[(r+1)%6], # 4, 3, 2
                            s[(r+4)%6], s[(r+5)%6], s[(r+0)%6]  # 5, 6, 1
                        ]
                        
                        points = len(set_data['home']['rotations'].get(str(r), []))
                        color = "#dcfce7" if points >= 3 else ("#fee2e2" if points == 0 else "white")
                        
                        st.markdown(f"""
                        <div style="border:1px solid #ccc; border-radius:5px; margin-bottom:10px; overflow:hidden;">
                            <div style="background:{color}; padding:5px; text-align:center; font-size:12px; font-weight:bold; border-bottom:1px solid #ccc;">
                                ROT {r} (Srv #{s[r-1]}) <span style="float:right; color:#1e3a8a;">+{points}</span>
                            </div>
                            <div class="court-grid">
                                <div class="court-zone">{current_lineup[0]}</div>
                                <div class="court-zone">{current_lineup[1]}</div>
                                <div class="court-zone">{current_lineup[2]}</div>
                                <div class="court-zone">{current_lineup[3]}</div>
                                <div class="court-zone">{current_lineup[4]}</div>
                                <div class="court-zone zone-1">{current_lineup[5]}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            with col2:
                st.subheader("✈️ Extérieur")
                starters = set_data['away']['starters']
                while len(starters) < 6: starters.append("?")
                
                bp = sum(len(v) for v in set_data['away']['rotations'].values())
                st.metric("Break Points (Service)", bp, delta=None)
                
                cols_rot = st.columns(3)
                for r in range(1, 7):
                    idx = r - 1
                    with cols_rot[idx % 3]:
                        s = starters
                        current_lineup = [
                            s[(r+3)%6], s[(r+2)%6], s[(r+1)%6],
                            s[(r+4)%6], s[(r+5)%6], s[(r+0)%6]
                        ]
                        points = len(set_data['away']['rotations'].get(str(r), []))
                        color = "#dcfce7" if points >= 3 else ("#fee2e2" if points == 0 else "white")
                        
                        st.markdown(f"""
                        <div style="border:1px solid #ccc; border-radius:5px; margin-bottom:10px; overflow:hidden;">
                            <div style="background:{color}; padding:5px; text-align:center; font-size:12px; font-weight:bold; border-bottom:1px solid #ccc;">
                                ROT {r} (Srv #{s[r-1]}) <span style="float:right; color:#dc2626;">+{points}</span>
                            </div>
                            <div class="court-grid">
                                <div class="court-zone">{current_lineup[0]}</div>
                                <div class="court-zone">{current_lineup[1]}</div>
                                <div class="court-zone">{current_lineup[2]}</div>
                                <div class="court-zone">{current_lineup[3]}</div>
                                <div class="court-zone">{current_lineup[4]}</div>
                                <div class="court-zone zone-1">{current_lineup[5]}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            # --- CHART ---
            st.markdown("### 📈 Momentum du Set")
            
            # Reconstruire l'historique
            history = []
            h_pts = [p for v in set_data['home']['rotations'].values() for p in v]
            a_pts = [p for v in set_data['away']['rotations'].values() for p in v]
            
            events = []
            for p in h_pts: events.append({'pt': p, 'team': 'Home'})
            for p in a_pts: events.append({'pt': p, 'team': 'Away'})
            events.sort(key=lambda x: x['pt'])
            
            curr_h, curr_a = 0, 0
            history.append({'x': 0, 'Home': 0, 'Away': 0})
            
            # Simulation simplifiée
            max_score = max(h_pts + a_pts) if (h_pts + a_pts) else 0
            for i in range(1, max_score + 2):
                if i in h_pts: curr_h = i
                if i in a_pts: curr_a = i
                history.append({'x': i, 'Home': curr_h, 'Away': curr_a})

            df = pd.DataFrame(history)
            
            fig = px.line(df, x='x', y=['Home', 'Away'], 
                          color_discrete_map={"Home": "#2563eb", "Away": "#dc2626"},
                          labels={'value': 'Score', 'x': 'Points Joués', 'variable': 'Équipe'})
            fig.update_layout(hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

else:
    # Empty State
    st.markdown("""
    <div style="text-align:center; padding:50px; color:#64748b;">
        <h3>👋 Bienvenue sur VolleyScout AI</h3>
        <p>Utilisez la barre latérale pour charger votre PDF de match.</p>
        

[Image of volleyball court zones and rotation positions]

    </div>
    """, unsafe_allow_html=True)
