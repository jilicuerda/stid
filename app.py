import streamlit as st
import pandas as pd
import re
import pdfplumber

# --- CONFIGURATION ---
st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- BACKEND: SMART PDF PARSER ---
def parse_pdf_match(file):
    """
    Extracts the match result specifically from the 'RESULTATS' table 
    using the Set Duration (e.g. 26') as an anchor.
    """
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    # 1. Extract Team Names (Look for the top header)
    # Heuristic: Find lines with "Senior" or "Masculin" and grab nearby capitalized text
    lines = text.split('\n')
    team_a = "Home Team"
    team_b = "Away Team"
    
    # Try to find specific FFvolley headers
    for i, line in enumerate(lines[:30]):
        if "Equipe A" in line or "Team A" in line:
            # Usually the team name is on the next line or same line
            team_a = line.replace("Equipe A", "").replace(":", "").strip()
            if not team_a and i+1 < len(lines): team_a = lines[i+1].strip()
        if "Equipe B" in line or "Team B" in line:
            team_b = line.replace("Equipe B", "").replace(":", "").strip()
            if not team_b and i+1 < len(lines): team_b = lines[i+1].strip()

    # 2. Extract Sets from the RESULTATS table
    # We look for lines containing a duration pattern like "26'" or "1h57"
    valid_sets = []
    
    # Regex to find the 'Duration' column (e.g., "26'", "31'", "110'")
    # The structure is: [Stats A] [Score A] [Duration] [Score B] [Stats B]
    duration_pattern = re.compile(r"\s+(\d{1,3})['’]\s+")
    
    found_results_table = False
    
    for line in lines:
        if "RESULTATS" in line:
            found_results_table = True
            continue
            
        if found_results_table:
            # Stop if we hit the footer signatures
            if "Vainqueur" in line or "SIGNATURES" in line:
                break
                
            # Search for the duration anchor (e.g., 26')
            match = duration_pattern.search(line)
            if match:
                # Split the line into Left (Team A) and Right (Team B) using the duration
                anchor_span = match.span()
                left_part = line[:anchor_span[0]].strip()
                right_part = line[anchor_span[1]:].strip()
                
                # Logic: The SCORE is the LAST number on the Left and FIRST number on the Right
                # Filter out non-digit characters to be safe
                left_nums = re.findall(r'\d+', left_part)
                right_nums = re.findall(r'\d+', right_part)
                
                if left_nums and right_nums:
                    try:
                        score_a = int(left_nums[-1]) # Last number on left
                        score_b = int(right_nums[0]) # First number on right
                        
                        # Sanity Check: A set must have ~15-30 points
                        if score_a > 5 and score_b > 5: 
                            valid_sets.append({"Home": score_a, "Away": score_b})
                    except:
                        continue

    # 3. Fallback: If 'RESULTATS' table parsing failed, try strict regex
    if not valid_sets:
        # Strict pattern: Look for "25-22" or "25:22" explicitly
        # Ignore anything with "15:" (likely substitutions)
        raw_scores = re.findall(r'(?<!\d)(1[0-9]|2[0-9]|3[0-5])\s*[:\-]\s*(1[0-9]|2[0-9]|3[0-5])(?!\d)', text)
        for s1, s2 in raw_scores:
            if abs(int(s1) - int(s2)) >= 2: # Must be 2 point diff
                valid_sets.append({"Home": int(s1), "Away": int(s2)})
        # Remove duplicates preserving order
        valid_sets = [dict(t) for t in {tuple(d.items()) for d in valid_sets}]

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
            sets_df['Set'] = range(1, len(sets_df) + 1)
            sets_df['Diff'] = sets_df['Home'] - sets_df['Away']
            
            # 1. Score Table
            st.subheader("Set Scores")
            st.table(sets_df.set_index('Set'))
            
            # 2. Momentum Chart
            st.subheader("Momentum (Point Differential)")
            st.bar_chart(sets_df, x='Set', y='Diff')

if __name__ == "__main__":
    main()