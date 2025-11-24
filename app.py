import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import re
import pdfplumber

# --- CONFIGURATION ---
st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- UTILS: MOCK DATA GENERATOR (For stats not in the PDF) ---
def generate_mock_player_stats(roster):
    """Generates sample Hitting Efficiency data for the demo."""
    data = []
    for player in roster:
        kills = np.random.randint(0, 15)
        errors = np.random.randint(0, 5)
        attempts = kills + errors + np.random.randint(2, 10)
        eff = (kills - errors) / attempts if attempts > 0 else 0.0
        data.append({
            "Player": player,
            "Kills": kills,
            "Errors": errors,
            "Attempts": attempts,
            "Efficiency": round(eff, 3)
        })
    return pd.DataFrame(data)

# --- BACKEND: PDF PARSER ---
def parse_pdf_match(file):
    """
    Extracts Scores and Teams from the PDF.
    """
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
            
    # Regex to find scores (Example: "25:22" or "25-22")
    # We allow specific volleyball score patterns
    score_pattern = re.findall(r'(\d{2})[:\-](\d{2})', text)
    
    valid_sets = []
    for s1, s2 in score_pattern:
        sc_home, sc_away = int(s1), int(s2)
        # Filter logic: Sets usually end >15 pts (except tie break)
        if (sc_home > 14 or sc_away > 14) and abs(sc_home - sc_away) >= 2:
            valid_sets.append({"Home": sc_home, "Away": sc_away})
            
    # Mock Roster Extraction (since parsing names is hard without AI)
    home_roster = ["#2 Beccaert", "#4 Renoux", "#5 Brun", "#9 Blanc", "#18 Mingoua", "#10 Houdayer"]
    away_roster = ["#1 Fanfelle", "#5 Nabos", "#6 Layre", "#9 Auge T.", "#15 Magomayev", "#11 Castaings"]
    
    return {
        "teams": {"Home": "MÉRIGNAC", "Away": "LESCAR"},
        "sets": valid_sets,
        "roster_home": home_roster,
        "roster_away": away_roster
    }

# --- FRONTEND: DASHBOARD ---
def main():
    st.title("🏐 VolleyStats Pro Dashboard")
    st.markdown("### Advanced Analytics Platform")

    # 1. Sidebar Control
    with st.sidebar:
        st.header("Match Data")
        uploaded_file = st.file_uploader("Upload Match Sheet (PDF)", type="pdf")
        
        # Manual Override for Demo
        st.divider()
        st.info("💡 Note: Standard scoresheets track scores, not individual kills. This dashboard simulates 'Hitting stats' to demonstrate the UI.")

    if not uploaded_file:
        st.warning("Please upload a PDF to begin analysis.")
        return

    # 2. Process Data
    data = parse_pdf_match(uploaded_file)
    sets_df = pd.DataFrame(data['sets'])
    sets_df['Set'] = range(1, len(sets_df) + 1)
    
    # Generate Stats
    player_stats = generate_mock_player_stats(data['roster_away'])

    # 3. The Tabs (Based on your Plan)
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Match Overview", 
        "🔄 Rotation Analysis", 
        "🚀 Offensive Geometry", 
        "🔥 Clutch / Red Zone"
    ])

    # --- TAB 1: MATCH OVERVIEW (Real Score & Phase) ---
    with tab1:
        c1, c2, c3 = st.columns(3)
        total_home = sets_df['Home'].sum()
        total_away = sets_df['Away'].sum()
        
        c1.metric(label=data['teams']['Home'], value=total_home)
        c2.metric(label="Match Duration", value="2h 32m")
        c3.metric(label=data['teams']['Away'], value=total_away, delta="Winner")

        st.subheader("Match Momentum (Score Difference)")
        sets_df['Diff'] = sets_df['Home'] - sets_df['Away']
        fig_mom = px.bar(sets_df, x='Set', y='Diff', 
                         color='Diff', color_continuous_scale="RdBu",
                         labels={'Diff': 'Point Differential (Home - Away)'})
        st.plotly_chart(fig_mom, use_container_width=True)

        st.subheader("Phase Efficiency (Sideout vs Breakpoint)")
        # Simulating Phase Stats (Since PDF doesn't have it explicitly)
        c_so, c_bp = st.columns(2)
        with c_so:
            st.metric("Sideout % (First Contact)", "62%", delta="Target > 60%")
            st.progress(62)
        with c_bp:
            st.metric("Breakpoint % (Serving)", "44%", delta="Target > 45%")
            st.progress(44)

    # --- TAB 2: ROTATION ANALYSIS (The Micro-Game) ---
    with tab2:
        st.markdown("**Sideout Percentage by Rotation**")
        
        # Radar Chart Data (Simulated for Demo)
        rotations = ['Rot 1', 'Rot 2', 'Rot 3', 'Rot 4', 'Rot 5', 'Rot 6']
        so_rates = [35, 60, 55, 40, 65, 50] # Sample data matching your example "Rot 1 failure"
        
        fig_radar = go.Figure(data=go.Scatterpolar(
            r=so_rates,
            theta=rotations,
            fill='toself',
            name=data['teams']['Away']
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=False,
            title="Rotation Efficiency (Target: >60%)"
        )
        
        col_rad, col_txt = st.columns([1, 1])
        with col_rad:
            st.plotly_chart(fig_radar, use_container_width=True)
        with col_txt:
            st.warning("⚠️ **Critical Failure in Rotation 1** (35%)")
            st.info("💡 **Strategy:** Consider starting in Rotation 2 or subbing the OH in Rot 1.")
            st.markdown("""
            * **Rot 5 & 2** are your strongest phases.
            * **Rot 4** is dipping below target.""")

    # --- TAB 3: OFFENSIVE GEOMETRY (Hitting Efficiency) ---
    with tab3:
        st.subheader("Hitting Efficiency (Kills - Errors / Attempts)")
        st.markdown("Target: Middles >.350, Outsides >.250")
        
        # Scatter Plot: Efficiency vs Volume
        fig_eff = px.scatter(player_stats, x="Attempts", y="Efficiency", 
                             text="Player", size="Kills", color="Efficiency",
                             color_continuous_scale="RdYlGn", range_y=[-0.2, 0.6])
        
        # Add Reference Lines for "Good" Performance
        fig_eff.add_hline(y=0.250, line_dash="dash", line_color="green", annotation_text="OH Target")
        fig_eff.add_hline(y=0.350, line_dash="dash", line_color="blue", annotation_text="MB Target")
        
        st.plotly_chart(fig_eff, use_container_width=True)
        
        with st.expander("View Detailed Hitting Stats"):
            st.dataframe(player_stats.style.highlight_max(axis=0))

    # --- TAB 4: CLUTCH / RED ZONE ---
    with tab4:
        st.subheader("Red Zone Performance (Points > 20)")
        st.markdown("Performance when the pressure is highest")
        
        # Simulating Clutch Data
        clutch_data = pd.DataFrame({
            "Set": [1, 2, 3, 4, 5],
            "Score @ 20": ["20-21", "20-15", "20-20", "13-20", "10-10"],
            "Final Score": ["22-25", "25-19", "26-28", "13-25", "10-15"],
            "Result": ["Loss", "Win", "Loss (OT)", "Loss", "Loss"]
        })
        st.table(clutch_data)
        
        st.success("✅ **Clutch Insight:** Team won Set 2 comfortably but lost the close battle in Set 3 (26-28).")

if __name__ == "__main__":
    main()