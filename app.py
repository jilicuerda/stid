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
    
    lines = text.split('\n')

    # --- 1. TEAM NAME DETECTION (The "Début" Trick) ---
    # Strategy: Find lines with "Début:" (Start time) and grab the text before it.
    # Example: "SA PARIS VOLLEY Début: 14:00" -> Captures "PARIS VOLLEY"
    
    potential_names = []
    
    for line in lines:
        if "Début:" in line:
            # Split line at "Début:"
            parts = line.split("Début:")
            before_debut = parts[0].strip()
            
            # Clean up the name (Remove "SA", "SB", "S", "R")
            # Regex removes "S", "SA", "SB", "R" from the END or START of the name part
            # Often appears as "SA PARIS" or "PARIS S"
            clean_name = re.sub(r'\b(SA|SB|S|R)\b', '', before_debut).strip()
            
            # Additional Cleanup: Remove trailing/leading non-letters
            clean_name = re.sub(r'^[^A-Z]+|[^A-Z]+$', '', clean_name)
            
            if len(clean_name) > 3:
                potential_names.append(clean_name)

    # Filter duplicates while preserving order
    unique_names = list(dict.fromkeys(potential_names))
    
    # Assign Home/Away
    # Heuristic: Usually Home is listed first in the file header, but 'Début' lines mix them.
    # We will try to find specific "Equipe A" headers to confirm.
    team_a = "Home Team"
    team_b = "Away Team"

    if len(unique_names) >= 2:
        # Default assumption
        team_a = unique_names[0]
        team_b = unique_names[1]
        
        # Try to correct A/B assignment by looking for explicit "(A)" or "(B)" labels in roster
        # This scans the whole text for "(A) TeamName" patterns
        for name in unique_names:
            # Pattern: "(A) PARIS" or "Equipe A : PARIS"
            if re.search(r"\(A\)\s*" + re.escape(name), text) or re.search(r"Equipe A.*" + re.escape(name), text):
                team_a = name
            if re.search(r"\(B\)\s*" + re.escape(name), text) or re.search(r"Equipe B.*" + re.escape(name), text):
                team_b = name

    # Fallback: If names are still generic, try to grab from top of file
    if team_a == "Home Team" and len(lines) > 5:
        # Look for the line describing the match "Category - TeamA TeamB"
        # We skip the first few lines which are usually titles
        for line in lines[:10]:
            if "SENIORS" in line or "MASCULIN" in line:
                 # It's usually a mess like "SENIORS CONFLANS PARIS"
                 # We can't parse this reliably without the "Début" names
                 pass

    # --- 2. EXTRACT SETS (Existing Working Logic) ---
    valid_sets = []
    duration_pattern = re.compile(r"(\d{1,3})\s*['’′`]")
    found_results_table = False
    
    for line in lines:
        if "RESULTATS" in line:
            found_results_table = True
        if "Vainqueur" in line: # Stop at footer
            found_results_table = False
            
        if found_results_table:
            match = duration_pattern.search(line)
            if match:
                anchor_span = match.span()
                left_part = line[:anchor_span[0]].strip()
                right_part = line[anchor_span[1]:].strip()
                duration_val = int(match.group(1))

                if duration_val < 60: # Ignore Total Duration
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

    # Final Sort
    valid_sets.sort(key=lambda x: x['Set'])
    unique_sets = {s['Set']: s for s in valid_sets}
    final_sets = sorted(unique_sets.values(), key=lambda x: x['Set'])

    return {
        "teams": {"Home": team_a, "Away": team_b},
        "sets": final_sets,
        "debug_names": unique_names # For debugging
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

        # 2. Visualization
        if data['sets']:
            st.divider()
            sets_df = pd.DataFrame(data['sets'])
            sets_df['Diff'] = sets_df['Home'] - sets_df['Away']
            
            st.subheader("Set Scores")
            st.dataframe(sets_df.set_index('Set'), use_container_width=True)
            
            st.subheader("Momentum")
            st.bar_chart(sets_df, x='Set', y='Diff')
        else:
            st.error("⚠️ No sets found.")
            
        # Debug Info (Optional)
        with st.expander("Debug: Detected Teams"):
            st.write(f"Names found via 'Début' scan: {data['debug_names']}")

if __name__ == "__main__":
    main()
