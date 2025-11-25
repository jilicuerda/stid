import streamlit as st
import pandas as pd
import re
import pdfplumber

# --- CONFIGURATION ---
st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- BACKEND: FINAL PARSER ---
def parse_pdf_match(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    # 1. Team Name Extraction (Improved)
    lines = text.split('\n')
    team_a = "Home Team"
    team_b = "Away Team"
    
    # Heuristics for FFvolley
    for i, line in enumerate(lines[:40]):
        # explicit labels
        if "Equipe A" in line or "Team A" in line:
            clean = line.replace("Equipe A", "").replace("Team A", "").replace(":", "").strip()
            if len(clean) > 3: team_a = clean
            elif i+1 < len(lines): team_a = lines[i+1].strip()
        
        if "Equipe B" in line or "Team B" in line:
            clean = line.replace("Equipe B", "").replace("Team B", "").replace(":", "").strip()
            if len(clean) > 3: team_b = clean
            elif i+1 < len(lines): team_b = lines[i+1].strip()
            
        # positional heuristics (A PARIS...)
        if re.match(r"^\s*A\s+[A-Z\s\-]{4,}", line):
             cand = line.replace("A ", "").strip()
             if "NATIONALE" not in cand: team_a = cand
        if re.match(r"^\s*B\s+[A-Z\s\-]{4,}", line):
             cand = line.replace("B ", "").strip()
             if "NATIONALE" not in cand: team_b = cand

    # 2. Extract Sets (Fixed Footer Logic)
    valid_sets = []
    
    # Regex for duration (e.g. 29', 29 ' 29’ etc)
    duration_pattern = re.compile(r"(\d{1,3})\s*['’′`]")
    
    found_results_table = False
    
    for line in lines:
        # Start looking when we see RESULTATS
        if "RESULTATS" in line:
            found_results_table = True
            
        if found_results_table:
            match = duration_pattern.search(line)
            if match:
                # 1. Extract Data FIRST (Before checking for footer stop)
                anchor_span = match.span()
                left_part = line[:anchor_span[0]].strip()
                right_part = line[anchor_span[1]:].strip()
                duration_val = int(match.group(1))

                # Ignore Total Duration (usually > 60)
                if duration_val < 60:
                    left_nums = re.findall(r'\d+', left_part)
                    right_nums = re.findall(r'\d+', right_part)
                    
                    # Logic: 
                    # Left side ends with: ... [Score] [SetNum]
                    # Right side starts with: [Score] ...
                    if len(left_nums) >= 2 and len(right_nums) >= 1:
                        try:
                            score_a = int(left_nums[-2]) 
                            set_num = int(left_nums[-1])
                            score_b = int(right_nums[0])
                            
                            # Sanity check for merged numbers (e.g. "254" -> Set 4, Score 25)
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

        # Stop looking ONLY if "Vainqueur" is found (Signatures often share line with Set 4)
        if "Vainqueur" in line:
            found_results_table = False

    # Sort and Deduplicate
    valid_sets.sort(key=lambda x: x['Set'])
    unique_sets = {s['Set']: s for s in valid_sets}
    final_sets = sorted(unique_sets.values(), key=lambda x: x['Set'])

    return {
        "teams": {"Home": team_a, "Away": team_b},
        "sets": final_sets
    }

# --- FRONTEND ---
def main():
    st.title("🏐 VolleyStats Pro")

    uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")

    if uploaded_file:
        data = parse_pdf_match(uploaded_file)
        
        # 1. Match Header
        c1, c2, c3 = st.columns(3)
        c1.metric("Home Team", data['teams']['Home'])
        c2.metric("Away Team", data['teams']['Away'])
        
        s_home = sum(1 for s in data['sets'] if s['Home'] > s['Away'])
        s_away = sum(1 for s in data['sets'] if s['Away'] > s['Home'])
        
        winner_color = "green" if s_home > s_away else "red"
        c3.markdown(f"### Result: :{winner_color}[{s_home} - {s_away}]")

        st.divider()

        # 2. Visualization
        if data['sets']:
            sets_df = pd.DataFrame(data['sets'])
            sets_df['Diff'] = sets_df['Home'] - sets_df['Away']
            sets_df['Winner'] = sets_df['Diff'].apply(lambda x: "Home" if x > 0 else "Away")
            
            # Score Table
            st.subheader("Set Scores")
            st.dataframe(sets_df.set_index('Set'), use_container_width=True)
            
            # Momentum Chart
            st.subheader("Momentum (Point Differential)")
            st.bar_chart(sets_df, x='Set', y='Diff', color='Winner')
        else:
            st.error("⚠️ No sets found. Please ensure the PDF has a filled 'RESULTATS' table.")

if __name__ == "__main__":
    main()
