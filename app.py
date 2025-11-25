import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re
import pdfplumber

# --- CONFIGURATION ---
st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- UTILS: MOCK DATA GENERATOR ---
def generate_mock_player_stats(team_name):
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

# --- BACKEND: PARSER ---
def parse_pdf_match(file):
    raw_text = ""
    debug_log = []
    
    with pdfplumber.open(file) as pdf:
        for i, page in enumerate(pdf.pages):
            raw_text += page.extract_text() + "\n"

    lines = raw_text.split('\n')
    
    # --- 1. TEAM NAME DETECTION ---
    potential_names = []
    
    for line in lines:
        if "Début:" in line:
            parts = line.split("Début:")
            for part in parts[:-1]:
                if "Fin:" in part:
                    candidate = part.split("Fin:")[-1]
                else:
                    candidate = part
                
                # Cleanup
                candidate = re.sub(r'\d{2}:\d{2}\s*R?', '', candidate)
                clean_name = re.sub(r'\b(SA|SB|S|R)\b', '', candidate)
                clean_name = re.sub(r'^[^A-Z]+|[^A-Z]+$', '', clean_name)
                
                if len(clean_name) > 3:
                    potential_names.append(clean_name)

    unique_names = list(dict.fromkeys(potential_names))
    
    # Default Assignment (Can be swapped in UI)
    name_1 = unique_names[0] if len(unique_names) > 0 else "Team A"
    name_2 = unique_names[1] if len(unique_names) > 1 else "Team B"

    # --- 2. EXTRACT SETS ---
    valid_sets = []
    duration_pattern = re.compile(r"(\d{1,3})\s*['’′`]")
    found_results_table = False
    
    for line in lines:
        if "RESULTATS" in line:
            found_results_table = True
        
        if found_results_table:
            match = duration_pattern.search(line)
            if match:
                duration_val = int(match.group(1))
                anchor_span = match.span()
                left_part = line[:anchor_span[0]].strip()
                right_part = line[anchor_span[1]:].strip()

                if duration_val < 60:
                    left_nums = re.findall(r'\d+', left_part)
                    right_nums = re.findall(r'\d+', right_part)
                    
                    if len(left_nums) >= 2 and len(right_nums) >= 1:
                        try:
                            score_a = int(left_nums[-2]) 
                            set_num = int(left_nums[-1])
                            score_b = int(right_nums[0])
                            
                            if set_num > 5: 
                                s_str = str(set_num)
                                set_num = int(s_str[-1])
                                score_a = int(s_str[:-1])

                            if 1 <= set_num <= 5:
                                valid_sets.append({
                                    "Set": set_num,
                                    "Score_1": score_a, # We map these to Home/Away later
                                    "Score_2": score_b
                                })
                        except:
                            pass
        
        if "Vainqueur" in line:
            found_results_table = False

    valid_sets.sort(key=lambda x: x['Set'])
    unique_sets = {s['Set']: s for s in valid_sets}
    final_sets = sorted(unique_sets.values(), key=lambda x: x['Set'])

    return {
        "names": [name_1, name_2],
        "sets": final_sets,
        "raw_text": raw_text,
        "logs": debug_log
    }

# --- FRONTEND ---
def main():
    st.title("🏐 VolleyStats Pro")

    with st.sidebar:
        st.header("Settings")
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")
        
        st.divider()
        st.subheader("Team Config")
        # SWAP BUTTON
        swap_teams = st.checkbox("🔄 Swap Home/Away Teams", value=False)
        st.info("Check this box if Team A and Team B are reversed.")

    if uploaded_file:
        data = parse_pdf_match(uploaded_file)
        
        # Determine Home/Away based on Toggle
        if swap_teams:
            home_name = data['names'][1]
            away_name = data['names'][0]
            # If swapped, we might need to swap scores too? 
            # Usually FFVolley result table is fixed (Left=A, Right=B).
            # If the parser read unique_names[0] as A, but it's actually B...
            # We usually just swap the NAMES, the scores in the table are fixed Left vs Right.
        else:
            home_name = data['names'][0]
            away_name = data['names'][1]

        # Prepare Set Data
        # IMPORTANT: The PDF table usually lists Home(Left) vs Away(Right).
        # We assume Score_1 is Left Column, Score_2 is Right Column.
        sets_data = []
        for s in data['sets']:
            sets_data.append({
                "Set": s['Set'],
                "Home": s['Score_1'],
                "Away": s['Score_2']
            })
            
        sets_df = pd.DataFrame(sets_data)
        
        # --- DISPLAY ---
        c1, c2, c3 = st.columns(3)
        c1.metric("Home Team", home_name)
        c2.metric("Away Team", away_name)
        
        s_home = sum(1 for s in sets_data if s['Home'] > s['Away'])
        s_away = sum(1 for s in sets_data if s['Away'] > s['Home'])
        
        winner_color = "green" if s_home > s_away else "red"
        c3.markdown(f"## Result: :{winner_color}[{s_home} - {s_away}]")

        if sets_data:
            sets_df['Diff'] = sets_df['Home'] - sets_df['Away']
            mock_stats = generate_mock_player_stats(away_name)

            tab1, tab2, tab3, tab4 = st.tabs([
                "📈 Score & Momentum", 
                "🔄 Rotation Analysis", 
                "🚀 Offensive Geometry", 
                "🔥 Clutch Performance"
            ])

            with tab1:
                st.subheader("Set Scores")
                st.dataframe(sets_df.set_index('Set'), use_container_width=True)
                
                st.subheader("Momentum")
                fig_mom = px.bar(
                    sets_df, x='Set', y='Diff', text='Diff', color='Diff',
                    color_continuous_scale="RdYlGn", labels={'Diff': 'Point Gap'}
                )
                st.plotly_chart(fig_mom, use_container_width=True)

            with tab2:
                st.warning("⚠️ Demo Data")
                st.markdown("### Sideout % by Rotation")
                c_rad, c_txt = st.columns(2)
                with c_rad:
                    rotations = ['Rot 1', 'Rot 2', 'Rot 3', 'Rot 4', 'Rot 5', 'Rot 6']
                    so_rates = [35, 60, 55, 42, 65, 50] 
                    fig_radar = go.Figure(data=go.Scatterpolar(r=so_rates, theta=rotations, fill='toself'))
                    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
                    st.plotly_chart(fig_radar, use_container_width=True)
                with c_txt: 
                    st.info("Rotation 1 is weak (35%).")

            with tab3:
                st.warning("⚠️ Demo Data")
                st.markdown("### Hitting Efficiency")
                fig_eff = px.scatter(
                    mock_stats, x="Attempts", y="Efficiency", size="Kills", 
                    color="Efficiency", text="Player", color_continuous_scale="RdYlGn",
                    range_y=[-0.1, 0.6]
                )
                st.plotly_chart(fig_eff, use_container_width=True)

            with tab4:
                st.subheader("Clutch Performance")
                clutch = sets_df[sets_df['Diff'].abs() <= 3]
                if not clutch.empty:
                    st.table(clutch.set_index('Set'))
                else:
                    st.write("No close sets.")

        # DEBUGGER
        st.divider()
        with st.expander("🛠️ Debug Inspector"):
            st.write("Raw Names Found:", data['names'])
            st.text("\n".join(data['logs']))

if __name__ == "__main__":
    main()
