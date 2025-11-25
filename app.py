import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re
import pdfplumber

# --- CONFIGURATION ---
st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- UTILS: MOCK DATA GENERATOR (For features not in PDF) ---
def generate_mock_player_stats(team_name):
    """Generates sample data to demonstrate the Advanced Analytics features."""
    # Create generic player list based on team name
    players = [f"#{i} Player" for i in [1, 4, 7, 9, 10, 12, 15, 18]]
    data = []
    for player in players:
        kills = np.random.randint(2, 18)
        errors = np.random.randint(0, 6)
        attempts = kills + errors + np.random.randint(5, 15)
        eff = (kills - errors) / attempts if attempts > 0 else 0.0
        data.append({
            "Player": player,
            "Kills": kills,
            "Errors": errors,
            "Attempts": attempts,
            "Efficiency": round(eff, 3)
        })
    return pd.DataFrame(data)

# --- BACKEND: ROBUST PARSER ---
def parse_pdf_match(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    lines = text.split('\n')
    
    # --- 1. TEAM NAME DETECTION (Improved "Fin-Début" Logic) ---
    potential_names = []
    
    for line in lines:
        # We only care about lines with a Start Time ("Début:")
        if "Début:" in line:
            # 1. Isolate the text BEFORE "Début:"
            segment = line.split("Début:")[0]
            
            # 2. If this line also has "Fin:" (from prev set), take text AFTER "Fin:"
            if "Fin:" in segment:
                segment = segment.split("Fin:")[-1]
                # Remove the timestamp (e.g., "14:24 R")
                segment = re.sub(r'\d{2}:\d{2}\s*R?', '', segment)
            
            # 3. Clean up the name
            # Remove "S", "SA", "SB", "R" markers
            clean_name = re.sub(r'\b(SA|SB|S|R)\b', '', segment)
            # Remove leading/trailing non-letters (whitespace, colons, numbers)
            clean_name = re.sub(r'^[^A-Z]+|[^A-Z]+$', '', clean_name)
            
            if len(clean_name) > 3:
                potential_names.append(clean_name)

    # Deduplicate preserving order
    unique_names = list(dict.fromkeys(potential_names))
    
    # Assign Teams (Default to generic if extraction fails)
    team_home = unique_names[0] if len(unique_names) > 0 else "Home Team"
    team_away = unique_names[1] if len(unique_names) > 1 else "Away Team"

    # --- 2. EXTRACT SETS (Proven Logic) ---
    valid_sets = []
    # Matches: 26', 26 ', 26’
    duration_pattern = re.compile(r"(\d{1,3})\s*['’′`]")
    
    found_results_table = False
    
    for line in lines:
        if "RESULTATS" in line:
            found_results_table = True
        
        if found_results_table:
            match = duration_pattern.search(line)
            if match:
                # Extract Data FIRST
                anchor_span = match.span()
                left_part = line[:anchor_span[0]].strip()
                right_part = line[anchor_span[1]:].strip()
                duration_val = int(match.group(1))

                if duration_val < 60: # Ignore Total
                    left_nums = re.findall(r'\d+', left_part)
                    right_nums = re.findall(r'\d+', right_part)
                    
                    if len(left_nums) >= 2 and len(right_nums) >= 1:
                        try:
                            score_a = int(left_nums[-2]) 
                            set_num = int(left_nums[-1])
                            score_b = int(right_nums[0])
                            
                            # Fix merged SetNum (e.g. "254" -> 25, 4)
                            if set_num > 5: 
                                s_str = str(set_num)
                                set_num = int(s_str[-1])
                                score_a = int(s_str[:-1])

                            if 1 <= set_num <= 5:
                                valid_sets.append({
                                    "Set": set_num,
                                    "Home": score_a,
                                    "Away": score_b
                                })
                        except:
                            pass
        
        # Stop check
        if "Vainqueur" in line:
            found_results_table = False

    valid_sets.sort(key=lambda x: x['Set'])
    # Dedupe
    unique_sets = {s['Set']: s for s in valid_sets}
    final_sets = sorted(unique_sets.values(), key=lambda x: x['Set'])

    return {
        "teams": {"Home": team_home, "Away": team_away},
        "sets": final_sets
    }

# --- FRONTEND: THE COMPLETE DASHBOARD ---
def main():
    st.title("🏐 VolleyStats Pro")

    # Sidebar for Upload
    with st.sidebar:
        st.header("Match Data")
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")
        st.divider()
        st.info("💡 **Note:** Standard scoresheets only contain Final Scores. Advanced tabs (Rotation/Efficiency) use simulated data to demonstrate the analytics engine.")

    if uploaded_file:
        data = parse_pdf_match(uploaded_file)
        
        # --- HEADER SECTION ---
        c1, c2, c3 = st.columns(3)
        c1.metric("Home Team", data['teams']['Home'])
        c2.metric("Away Team", data['teams']['Away'])
        
        s_home = sum(1 for s in data['sets'] if s['Home'] > s['Away'])
        s_away = sum(1 for s in data['sets'] if s['Away'] > s['Home'])
        
        winner_color = "green" if s_home > s_away else "red"
        c3.markdown(f"## {s_home} - {s_away}")

        if not data['sets']:
            st.error("⚠️ No sets detected. Check PDF format.")
            return

        # --- DATA PREP ---
        sets_df = pd.DataFrame(data['sets'])
        sets_df['Diff'] = sets_df['Home'] - sets_df['Away']
        
        # Generate Mock Stats for the "Demo" tabs
        mock_stats = generate_mock_player_stats(data['teams']['Away'])

        # --- TABS FOR ANALYSIS ---
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 Score & Momentum", 
            "🔄 Rotation Analysis", 
            "🚀 Offensive Geometry", 
            "🔥 Clutch Performance"
        ])

        # --- TAB 1: REAL DATA ---
        with tab1:
            st.subheader("Set Scores")
            st.dataframe(sets_df.set_index('Set'), use_container_width=True)
            
            st.subheader("Momentum (Point Differential)")
            # Color logic: Green if Home leads, Red if Away leads
            sets_df['Color'] = sets_df['Diff'].apply(lambda x: '#4CAF50' if x > 0 else '#F44336')
            
            fig_mom = px.bar(
                sets_df, 
                x='Set', 
                y='Diff',
                text='Diff',
                color='Diff',
                color_continuous_scale="RdYlGn",
                labels={'Diff': 'Point Gap'}
            )
            st.plotly_chart(fig_mom, use_container_width=True)

        # --- TAB 2: DEMO DATA (Rotation) ---
        with tab2:
            st.warning("⚠️ Demonstration Mode: Using simulated data (PDF lacks rotation logs).")
            st.markdown("### Sideout Percentage by Rotation")
            
            col_rad, col_txt = st.columns([1, 1])
            with col_rad:
                 # Sample Radar Data
                rotations = ['Rot 1', 'Rot 2', 'Rot 3', 'Rot 4', 'Rot 5', 'Rot 6']
                so_rates = [35, 60, 55, 42, 65, 50] 
                
                fig_radar = go.Figure(data=go.Scatterpolar(
                    r=so_rates,
                    theta=rotations,
                    fill='toself',
                    name='Sideout %'
                ))
                fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
                st.plotly_chart(fig_radar, use_container_width=True)
            
            with col_txt:
                st.info("💡 **Analysis:** Rotation 1 is a critical weak point (35%).")
                st.markdown("

[Image of volleyball rotation diagram]
")

        # --- TAB 3: DEMO DATA (Efficiency) ---
        with tab3:
            st.warning("⚠️ Demonstration Mode: Using simulated data.")
            st.subheader("Hitting Efficiency Matrix")
            st.markdown("**Formula:** (Kills - Errors) / Attempts")
            
            fig_eff = px.scatter(
                mock_stats, 
                x="Attempts", 
                y="Efficiency", 
                size="Kills", 
                color="Efficiency",
                text="Player",
                color_continuous_scale="RdYlGn",
                range_y=[-0.1, 0.6]
            )
            # Add Benchmarks
            fig_eff.add_hline(y=0.300, line_dash="dash", line_color="green", annotation_text="Elite Target")
            
            st.plotly_chart(fig_eff, use_container_width=True)
            st.dataframe(mock_stats)

        # --- TAB 4: REAL DATA (Derived) ---
        with tab4:
            st.subheader("Clutch Set Performance")
            st.markdown("Analysis of sets decided by **3 points or less**.")
            
            clutch_sets = sets_df[sets_df['Diff'].abs() <= 3]
            
            if not clutch_sets.empty:
                st.success(f"Found {len(clutch_sets)} clutch sets.")
                st.table(clutch_sets.set_index('Set'))
            else:
                st.info("No close sets found in this match (Margin <= 3).")

if __name__ == "__main__":
    main()
