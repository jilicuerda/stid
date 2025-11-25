import streamlit as st
import pdfplumber
import pandas as pd
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf = pdfplumber.open(pdf_file)
        self.page0 = self.pdf.pages[0]
        self.page_width = self.page0.width
        self.page_height = self.page0.height
        self.img_scale = 150 

    def get_page_image(self):
        return self.page0.to_image(resolution=self.img_scale).original

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y):
        """Extracts all sets based on the calibrated offsets."""
        match_data = []
        
        # Loop through potential 5 sets
        for set_num in range(1, 6): 
            # Calculate Y for this set
            current_y = base_y + ((set_num - 1) * offset_y)
            
            # --- TEAM A (LEFT GRID) ---
            # Check if this row is even on the page
            if current_y + h <= self.page_height:
                team_a_starters = self._extract_row(base_x, current_y, w, h)
                # Only add if we actually got data (not empty list due to bounds)
                if team_a_starters:
                    match_data.append({
                        "Set": set_num, "Team": "Left Grid", "Starters": team_a_starters
                    })
            
            # --- TEAM B (RIGHT GRID) ---
            team_b_x = base_x + offset_x
            if current_y + h <= self.page_height and team_b_x + (6*w) <= self.page_width:
                team_b_starters = self._extract_row(team_b_x, current_y, w, h)
                if team_b_starters:
                    match_data.append({
                        "Set": set_num, "Team": "Right Grid", "Starters": team_b_starters
                    })
            
        return match_data

    def _extract_row(self, start_x, start_y, w, h):
        """Helper to extract 6 grid cells with SAFETY CHECKS."""
        row_data = []
        for i in range(6):
            x0 = start_x + (i * w)
            y0 = start_y
            x1 = x0 + w
            y1 = y0 + h
            
            # SAFETY CHECK: Is the box inside the page?
            if x1 > self.page_width or y1 > self.page_height:
                return [] # Stop if out of bounds
            
            try:
                # Crop using PDF coordinates
                crop = self.page0.crop((x0, y0, x1, y1))
                text = crop.extract_text()
                val = text.strip() if text else "?"
                row_data.append(val)
            except ValueError:
                # Catch specific pdfplumber bbox errors
                return []
                
        return row_data

    def draw_full_grid(self, img, bx, by, w, h, off_x, off_y):
        draw = ImageDraw.Draw(img)
        
        # Draw loops for 5 potential sets
        for s in range(5):
            cur_y = by + (s * off_y)
            
            # Draw Left Team (Red)
            for i in range(6):
                draw.rectangle(
                    [bx + (i*w), cur_y, bx + (i*w) + w, cur_y + h],
                    outline="red", width=3
                )
            
            # Draw Right Team (Blue)
            if off_x > 0:
                cur_x_right = bx + off_x
                for i in range(6):
                    draw.rectangle(
                        [cur_x_right + (i*w), cur_y, cur_x_right + (i*w) + w, cur_y + h],
                        outline="blue", width=3
                    )
        return img

def main():
    st.title("🏐 VolleyStats: Auto-Extractor")
    
    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")

    if not uploaded_file:
        st.info("Upload PDF to begin.")
        return

    extractor = VolleySheetExtractor(uploaded_file)

    tab1, tab2 = st.tabs(["👁️ Check Alignment", "📥 Extract Data"])

    with tab1:
        st.write("### Calibration")
        
        c1, c2 = st.columns(2)
        with c1:
            base_x = st.number_input("Start X", value=264)
            base_y = st.number_input("Start Y", value=186)
            w = st.number_input("Cell Width", value=50)
            h = st.number_input("Cell Height", value=50)
        with c2:
            offset_x = st.number_input("Right Offset", value=880) 
            offset_y = st.number_input("Down Offset", value=330)

        # Visualization
        img = extractor.get_page_image()
        debug_img = extractor.draw_full_grid(img, base_x, base_y, w, h, offset_x, offset_y)
        st.image(debug_img, use_container_width=True)

    with tab2:
        if st.button("🚀 Extract All Lineups"):
            data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y)
            
            if data:
                df = pd.DataFrame(data)
                # Format list for display
                df['Starters'] = df['Starters'].apply(lambda x: " | ".join(x) if x else "Error")
                st.dataframe(df, use_container_width=True)
                st.success(f"Successfully extracted {len(df)} rows of data.")
            else:
                st.warning("No data found inside the calibrated boxes. Check your X/Y coordinates.")

if __name__ == "__main__":
    main()
