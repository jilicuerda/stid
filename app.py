import streamlit as st
import pandas as pd
import re
import pdfplumber

# --- CONFIGURATION ---
st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- BACKEND: PRECISION PDF PARSER ---
def parse_pdf_match(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    # 1. Extract Team Names
    lines = text.split('\n')
    team_a = "Home Team"
    team_b = "Away Team"
    
    for i, line in enumerate(lines[:30]):
        if "Equipe A" in line or "Team A" in line:
            clean_line = line.replace("Equipe A", "").replace(":", "").strip()
            if len(clean_line) > 3: team_a = clean_line
            elif i+1 < len(lines): team_a = lines[i+1].strip()
        if "Equipe B" in line or "Team B" in line:
            clean_line = line.replace("Equipe B", "").replace(":", "").strip()
            if len(clean_line) > 3: team_b = clean_line
            elif i+1 < len(lines): team_b = lines[i+1].strip()

    # 2. Extract Sets using "Duration Anchor" Logic
    valid_sets = []
    
    # Regex to find duration (e.g., 26', 31')
    duration_pattern = re.compile(r"\s+(\d{1,3})['’]\s+")
    
    found_results_table = False
    
    for line in lines:
        if "RESULTATS" in line:
            found_results_table = True
        
        # Stop processing if we hit the footer
        if "Vainqueur" in line or "SIGNATURES" in line:
            found_results_table = False
            
        if found_results_table:
            match = duration_pattern.search(line)
            if match:
                # Split line by the duration anchor
                anchor_span = match.span()
                left_part = line[:anchor_span[0]].strip()
                right_part = line[anchor_span[1]:].strip()
                duration_val = int(match.group(1))

                # Filter out the "Total" row (usually > 60 mins)
                if duration_val > 60:
                    continue
                
                # Get all numbers
                left_nums = re.findall(r'\d+', left_part)
                right_nums = re.findall(r'\d+', right_part)
                
                # LOGIC: 
                # Left side ends with: [Score] [SetNum] -> so we need second to last
                # Right side starts with: [Score]
                if len(left_nums) >= 2 and len(right_nums) >= 1:
                    try:
                        score_a = int(left_nums[-2]) # Second to last (20)
                        set_num = int(left_nums[-1]) # Last (1)
                        score_b = int(right_nums[0]) # First (25)
                        
                        # Verification: Set Num must be 1-5, Scores > 0
                        if 1 <= set_num <= 5 and score_a > 0 and score_b > 0:
                            valid_sets.append({
                                "Set": set_num,
                                "Home": score_a,
                                "Away": score_b
                            })
                    except:
                        continue

    # 3. Sort by Set Number
    valid_sets.sort(key=lambda x: x['Set'])

    return {
        "teams": {"Home": team_a, "Away": team_b},
        "sets": valid_sets
    }

# --- FRONTEND ---
def main():
    st.title("🏐 VolleyStats Pro")

    uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")

    if uploaded_file:
        data = parse_pdf_match(uploaded_file)
        
        # Display Header
        c1, c2, c3 = st.columns(3)
        c1.metric("Home Team", data['teams']['Home'])
        c2.metric("Away Team", data['teams']['Away'])
        
        # Calculate Winner
        sets_home = sum(1 for s in data['sets'] if s['Home'] > s['Away'])
        sets_away = sum(1 for s in data['sets'] if s['Away'] > s['Home'])
        c3.metric("Result", f"{sets_home} - {sets_away}")

        st.divider()

        if not data['sets']:
            st.error("Could not auto-detect scores. Please check PDF format.")
        else:
            # Visualization
            sets_df = pd.DataFrame(data['sets'])
            sets_df['Diff'] = sets_df['Home'] - sets_df['Away']
            
            # 1. Score Table
            st.subheader("Set Scores")
            st.table(sets_df.set_index('Set'))
            
            # 2. Momentum Chart
            st.subheader("Momentum (Point Differential)")
            st.bar_chart(sets_df, x='Set', y='Diff')

if __name__ == "__main__":
    main()