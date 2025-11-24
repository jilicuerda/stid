import streamlit as st
import pdfplumber
import pandas as pd
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="VolleyStats AI", page_icon="🏐", layout="wide")

# --- BACKEND: PDF EXTRACTION ENGINE ---
def extract_data_from_pdf(uploaded_file):
    """
    Reads the PDF and uses Regex/Logic to find the scores.
    Currently uses pdfplumber (Free/Local). 
    """
    text_content = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text_content += page.extract_text() + "\n"

    # --- PARSING LOGIC (The "Brain") ---
    # This regex looks for patterns like "25-22" or "25:22"
    # It's a simple heuristic for this demo.
    score_pattern = re.findall(r'(\d{2})[:\-](\d{2})', text_content)
    
    # We attempt to find the Team Names (heuristic: usually at the top)
    lines = text_content.split('\n')
    team_a = "Team A (Unknown)"
    team_b = "Team B (Unknown)"
    
    # Simple search for team names (adjust keywords based on your files)
    for line in lines[:20]: # Check first 20 lines
        if "MASCULINE" in line or "SENIOR" in line: continue
        if len(line) > 5 and "VOLLEY" in line.upper():
            if "Team A" == "Team A (Unknown)": team_a = line
            else: team_b = line

    # Structure the found data into a clean JSON format
    extracted_data = {
        "match_info": {
            "team_home": team_a,
            "team_away": team_b,
        },
        "raw_scores": score_pattern, # List of tuples like [('25', '22'), ('19', '25')]
        "sets": []
    }

    # Convert raw scores into structured Set objects
    for i, (score_a, score_b) in enumerate(score_pattern):
        # Filter out obvious non-set scores (like timestamps 20:30)
        # Real volleyball sets usually end with 15 or 25, or >24 in extra time
        s_a, s_b = int(score_a), int(score_b)
        if (s_a >= 15 or s_b >= 15) and abs(s_a - s_b) >= 2:
            extracted_data["sets"].append({
                "set_number": i + 1,
                "score_home": s_a,
                "score_away": s_b,
                "winner": "Home" if s_a > s_b else "Away"
            })
            
    return extracted_data

# --- FRONTEND: USER INTERFACE ---
def main():
    # 1. Header Section
    st.title("🏐 VolleyStats Auto-Analyzer")
    st.markdown("""
    **Upload your FFvolley Scoresheet (PDF)** to automatically extract stats and insights.
    """)

    # 2. File Uploader
    uploaded_file = st.file_uploader("Drop your PDF here", type=['pdf'])

    if uploaded_file is not None:
        with st.spinner('Reading match data...'):
            # Run the extraction function
            match_data = extract_data_from_pdf(uploaded_file)

        # 3. Display Match Summary
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Home Team", match_data['match_info']['team_home'])
        c2.metric("Away Team", match_data['match_info']['team_away'])
        c3.metric("Total Sets Found", len(match_data['sets']))

        # 4. Visualization (The "Wow" Factor)
        st.subheader("Match Momentum (Score Difference)")
        
        # Prepare data for the chart
        if match_data['sets']:
            chart_data = []
            for s in match_data['sets']:
                # Calculate point difference (Home - Away)
                diff = s['score_home'] - s['score_away']
                chart_data.append({
                    "Set": f"Set {s['set_number']}",
                    "Score Diff (Home)": diff,
                    "Winner": s['winner']
                })
            
            df_chart = pd.DataFrame(chart_data)
            
            # Bar Chart: Positive = Home leads, Negative = Away leads
            st.bar_chart(df_chart, x="Set", y="Score Diff (Home)", color=["#FF4B4B"])
        
        else:
            st.warning("No valid set scores could be automatically detected. Please check the PDF format.")

        # 5. Raw Data Inspector (For the Coach to verify)
        with st.expander("View Extracted Raw JSON"):
            st.json(match_data)

if __name__ == "__main__":
    main()