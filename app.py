import streamlit as st
import pandas as pd
import re
import pdfplumber

# --- CONFIGURATION ---
st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- BACKEND: ROBUST PARSER ---
def parse_pdf_match(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    # 1. Improved Team Name Extraction
    # We look for patterns like "A [Name]" or "Equipe A: [Name]"
    lines = text.split('\n')
    team_a = "Home Team"
    team_b = "Away Team"
    
    # Strategy: Look for the specific "Match Info" block often found at the top
    for i, line in enumerate(lines[:40]):
        # Check for explicit "Equipe A" labels
        if "Equipe A" in line or "Team A" in line:
            clean = line.replace("Equipe A", "").replace("Team A", "").replace(":", "").strip()
            if len(clean) > 3: team_a = clean
            elif i+1 < len(lines): team_a = lines[i+1].strip()
        
        if "Equipe B" in line or "Team B" in line:
            clean = line.replace("Equipe B", "").replace("Team B", "").replace(":", "").strip()
            if len(clean) > 3: team_b = clean
            elif i+1 < len(lines): team_b = lines[i+1].strip()
            
        # Fallback: Look for "A" and "B" followed by names (Common in FFvolley)
        # But ignore "A" if it's part of a word like "NATIONALE"
        if re.match(r"^\s*A\s+[A-Z\s\-]{4,}", line):
             cand = line.replace("A ", "").strip()
             if "NATIONALE" not in cand: team_a = cand
        if re.match(r"^\s*B\s+[A-Z\s\-]{4,}", line):
             cand = line.replace("B ", "").strip()
             if "NATIONALE" not in cand: team_b = cand

    # 2. Extract Sets using "Flexible Anchor" Logic
    valid_sets = []
    
    # Regex: Finds 1-3 digits followed by ANY apostrophe-like character
    # Handles: "26'", "26 '", "26’", "26′"
    duration_pattern = re.compile(r"(\d{1,3})\s*['’′`]")
    
    found_results_table = False
    debug_lines = [] # To show in UI
    
    for line in lines:
        if "RESULTATS" in line:
            found_results_table = True
        
        if "Vainqueur" in line or "SIGNATURES" in line:
            found_results_table = False
            
        if found_results_table:
            match = duration_pattern.search(line)
            if match:
                debug_lines.append(f"Found Anchor in: {line}")
                
                # Split line by the duration match
                anchor_span = match.span()
                left_part = line[:anchor_span[0]].strip()
                right_part = line[anchor_span[1]:].strip()
                duration_val = int(match.group(1))

                # Ignore Total Duration row (usually > 60)
                if duration_val > 60:
                    continue
                
                left_nums = re.findall(r'\d+', left_part)
                right_nums = re.findall(r'\d+', right_part)
                
                # Logic: Left side ends with [Score] [SetNum]
                # Right side starts with [Score]
                if len(left_nums) >= 2 and len(right_nums) >= 1:
                    try:
                        # Grab standard positions
                        score_a = int(left_nums[-2]) 
                        set_num = int(left_nums[-1])
                        score_b = int(right_nums[0])
                        
                        # Data Cleanup: sometimes Set Num is merged?
                        # If Set Num > 5, maybe the parser missed a space (e.g. "251" -> 25, 1)
                        if set_num > 5: 
                            # Try to split last digit
                            s_str = str(set_num)
                            set_num = int(s_str[-1])
                            score_a = int(s_str[:-1])

                        if 1 <= set_num <= 5:
                            valid_sets.append({
                                "Set": set_num,
                                "Home": score_a,
                                "Away": score_b
                            })
                    except Exception as e:
                        debug_lines.append(f"Error parsing line: {e}")
                        continue

    # Sort and remove duplicates
    valid_sets.sort(key=lambda x: x['Set'])
    
    # Deduplicate based on Set number (keep last found if dupes exist)
    unique_sets = {s['Set']: s for s in valid_sets}
    final_sets = sorted(unique_sets.values(), key=lambda x: x['Set'])

    return {
        "teams": {"Home": team_a, "Away": team_b},
        "sets": final_sets,
        "raw_text": text,
        "debug_lines": debug_lines
    }

# --- FRONTEND ---
def main():
    st.title("🏐 VolleyStats Pro")

    uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")

    if uploaded_file:
        data = parse_pdf_match(uploaded_file)
        
        # 1. Header
        c1, c2, c3 = st.columns(3)
        c1.metric("Home Team", data['teams']['Home'])
        c2.metric("Away Team", data['teams']['Away'])
        
        s_home = sum(1 for s in data['sets'] if s['Home'] > s['Away'])
        s_away = sum(1 for s in data['sets'] if s['Away'] > s['Home'])
        c3.metric("Result", f"{s_home} - {s_away}")

        st.divider()

        # 2. Stats
        if data['sets']:
            sets_df = pd.DataFrame(data['sets'])
            sets_df['Diff'] = sets_df['Home'] - sets_df['Away']
            
            st.subheader("Set Scores")
            st.table(sets_df.set_index('Set'))
            
            st.subheader("Momentum (Point Differential)")
            st.bar_chart(sets_df, x='Set', y='Diff')
        else:
            st.error("No sets found. Check the inspector below.")

        # 3. Debug Inspector (Crucial for fixing edge cases)
        with st.expander("🕵️ Debug / Raw Data Inspector"):
            st.write("### Recognized Lines in Results Table:")
            for l in data['debug_lines']:
                st.code(l)
            
            st.write("### Full Raw Text Dump:")
            st.text(data['raw_text'])

if __name__ == "__main__":
    main()
