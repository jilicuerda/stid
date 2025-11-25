import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="VolleyStats Auto-Pilot", page_icon="🏐", layout="wide")

class AutoVolleyExtractor:
    def __init__(self, pdf_file):
        self.pdf = pdfplumber.open(pdf_file)
        self.page = self.pdf.pages[0]

    def find_starters_automatically(self):
        """
        Detects the starting lineup by finding the grid structure 
        defined by horizontal and vertical lines.
        """
        # 1. Extract all lines (horizontal and vertical)
        lines = self.page.lines
        
        # 2. Filter for vertical lines that separate player columns
        # FFVolley columns are usually ~30-40pts wide.
        v_lines = sorted([l['x0'] for l in lines if l['height'] > 10])
        
        # Cluster lines to find the main grid columns
        # We look for sequences of lines that are roughly equidistant
        columns = []
        if v_lines:
            current_group = [v_lines[0]]
            for x in v_lines[1:]:
                if x - current_group[-1] > 5: # New line if >5pts away
                    if len(current_group) > 0:
                        columns.append(sum(current_group)/len(current_group)) # Avg x
                    current_group = [x]
                else:
                    current_group.append(x)
            columns.append(sum(current_group)/len(current_group))

        # 3. Identify the "6-column" structures
        # A valid lineup grid will have 7 vertical lines (borders + 5 separators)
        valid_grids = []
        for i in range(len(columns) - 6):
            # Check if these 7 lines form 6 cells of roughly equal width
            subset = columns[i:i+7]
            widths = [subset[j+1] - subset[j] for j in range(6)]
            avg_w = sum(widths) / 6
            
            # If deviation is low, it's a grid!
            if all(abs(w - avg_w) < 5 for w in widths):
                valid_grids.append({
                    "x_start": subset[0],
                    "cell_width": avg_w,
                    "cols": subset
                })

        # 4. Find the Rows (Horizontal Lines) relative to "Set" headers
        # We search for text "I", "II", "III" which are headers for the grid
        words = self.page.extract_words()
        headers = [w for w in words if w['text'] in ['I', 'II', 'III', 'IV', 'V', 'VI']]
        
        if not headers:
            return pd.DataFrame()

        # Group headers by Y position to find the rows
        # Sort by Y top
        headers.sort(key=lambda w: w['top'])
        
        # The starters are usually just BELOW these headers
        match_data = []
        
        # Iterate through unique Y levels of headers to find each "Set" block
        # We group headers that are on the same line (within 5px)
        rows = []
        if headers:
            current_row = [headers[0]]
            for h in headers[1:]:
                if abs(h['top'] - current_row[-1]['top']) < 5:
                    current_row.append(h)
                else:
                    rows.append(current_row)
                    current_row = [h]
            rows.append(current_row)

        # For each header row found (representing a Set), try to read the numbers below it
        for i, row in enumerate(rows):
            # Use the first header (I) to define the top Y
            # Starters are usually in the box immediately below the header
            header_bottom = row[0]['bottom']
            # Expected cell height is approx 25-30 pts
            cell_h = 28 
            
            # Determine X coordinates from our line detection (or fall back to header position)
            # We look for the grid that matches this row's X position
            best_grid = None
            header_x_center = sum(r['x0'] for r in row) / len(row)
            
            for grid in valid_grids:
                grid_center = grid['x_start'] + (grid['cell_width'] * 3)
                if abs(grid_center - header_x_center) < 100:
                    best_grid = grid
                    break
            
            if best_grid:
                # Extract!
                starters = []
                for col_idx in range(6):
                    x0 = best_grid['cols'][col_idx]
                    x1 = best_grid['cols'][col_idx+1]
                    
                    # Define box below header
                    bbox = (x0, header_bottom + 2, x1, header_bottom + cell_h)
                    
                    try:
                        text = self.page.crop(bbox).extract_text()
                        val = "?"
                        if text:
                            # Clean numbers
                            clean = re.sub(r'[^0-9]', '', text)
                            if clean.isdigit() and len(clean) <= 2:
                                val = clean
                        starters.append(val)
                    except:
                        starters.append("?")
                
                if any(s != "?" for s in starters):
                    # Guessing Set Number and Team based on position
                    # Left side grids are usually X < 300
                    team = "Left" if best_grid['x_start'] < 300 else "Right"
                    match_data.append({
                        "Team": team,
                        "Starters": " | ".join(starters)
                    })

        return pd.DataFrame(match_data)

def main():
    st.title("🏐 VolleyStats: Auto-Pilot")
    st.markdown("**No calibration required.** This tool detects the grid lines automatically.")
    
    uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")

    if uploaded_file:
        if st.button("🚀 Analyze Automatically"):
            with st.spinner("Scanning document structure..."):
                extractor = AutoVolleyExtractor(uploaded_file)
                df = extractor.find_starters_automatically()
                
                if not df.empty:
                    st.success(f"Found {len(df)} lineups automatically!")
                    st.table(df)
                else:
                    st.error("Could not auto-detect grid lines. The PDF might be scanned too lightly.")

if __name__ == "__main__":
    main()
