import streamlit as st
import pdfplumber
import pandas as pd
import re
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf = pdfplumber.open(pdf_file)
        self.page0 = self.pdf.pages[0]
        
        # Calculate the Scale Factor (Pixels vs PDF Points)
        # Standard PDF is 72 points per inch. We render image at 150 DPI.
        self.img_scale = 150 
        self.scale_factor = 72 / 150  # Roughly 0.48

    def get_page_image(self):
        return self.page0.to_image(resolution=self.img_scale).original

    def _scale_coords(self, val):
        """Converts Slider Pixels to PDF Points"""
        return val * self.scale_factor

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y):
        match_data = []
        
        # Loop through Sets 1 to 5
        for set_num in range(1, 6): 
            # Calculate Y for this set (in Pixels)
            current_y_pixels = base_y + ((set_num - 1) * offset_y)
            
            # --- TEAM A (LEFT) ---
            # Convert pixels to PDF points before cropping
            # We add a small 'buffer' to shrink the box slightly and avoid borders
            team_a_starters = self._extract_row(base_x, current_y_pixels, w, h)
            if team_a_starters:
                match_data.append({
                    "Set": set_num, "Team": "Left Grid", "Starters": team_a_starters
                })
            
            # --- TEAM B (RIGHT) ---
            team_b_x_pixels = base_x + offset_x
            team_b_starters = self._extract_row(team_b_x_pixels, current_y_pixels, w, h)
            if team_b_starters:
                match_data.append({
                    "Set": set_num, "Team": "Right Grid", "Starters": team_b_starters
                })
            
        return match_data

    def _extract_row(self, start_x_px, start_y_px, w_px, h_px):
        """Helper to extract 6 grid cells using SCALED coordinates."""
        row_data = []
        
        # Convert the row start position to PDF points
        pdf_y = self._scale_coords(start_y_px)
        pdf_h = self._scale_coords(h_px)
        
        # Safety Check: Is this Y off the page?
        if pdf_y + pdf_h > self.page0.height:
            return []

        for i in range(6):
            # Calculate X in Pixels
            x_px = start_x_px + (i * w_px)
            
            # Convert to PDF Points
            pdf_x = self._scale_coords(x_px)
            pdf_w = self._scale_coords(w_px)
            
            # Crop Box (x0, y0, x1, y1)
            # We shrink the box by 2 points to avoid grabbing black grid lines
            bbox = (pdf_x + 2, pdf_y + 2, pdf_x + pdf_w - 2, pdf_y + pdf_h - 2)
            
            try:
                crop = self.page0.crop(bbox)
                text = crop.extract_text()
                
                # CLEANUP: Remove non-digits (like "I", "II", ":", "Left")
                # We only want the Player Number
                clean_val = re.sub(r'[^0-9]', '', text) if text else "?"
                
                # If empty after cleaning, mark as ?
                if not clean_val: clean_val = "?"
                
                row_data.append(clean_val)
            except:
                row_data.append("?")
                
        # Filter out empty rows (if all are ?)
        if all(x == "?" for x in row_data):
            return []
            
        return row_data

    def draw_full_grid(self, img, bx, by, w, h, off_x, off_y):
        draw = ImageDraw.Draw(img)
        # Draw 5 Sets
        for s in range(5):
            cur_y = by + (s * off_y)
            # Left
            for i in range(6):
                draw.rectangle([bx + (i*w), cur_y, bx + (i*w) + w, cur_y + h], outline="red", width=3)
            # Right
            if off_x > 0:
                cur_x = bx + off_x
                for i in range(6):
                    draw.rectangle([cur_x + (i*w), cur_y, cur_x + (i*w) + w, cur_y + h], outline="blue", width=3)
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
        st.write("### Calibration (Pixels)")
        c1, c2 = st.columns(2)
        with c1:
            # I updated these defaults to match the "Image Scale"
            # If you previously used 264, try sticking with it, the code now scales it correctly.
            base_x = st.number_input("Start X", value=264)
            base_y = st.number_input("Start Y", value=186)
            w = st.number_input("Cell Width", value=50)
            h = st.number_input("Cell Height", value=50)
        with c2:
            offset_x = st.number_input("Right Offset", value=880) 
            offset_y = st.number_input("Down Offset", value=330)

        img = extractor.get_page_image()
        debug_img = extractor.draw_full_grid(img, base_x, base_y, w, h, offset_x, offset_y)
        st.image(debug_img, use_container_width=True)

    with tab2:
        if st.button("🚀 Extract All Lineups"):
            data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y)
            
            if data:
                df = pd.DataFrame(data)
                df['Starters'] = df['Starters'].apply(lambda x: " | ".join(x))
                st.dataframe(df, use_container_width=True)
            else:
                st.error("No data extracted. Check your X/Y coordinates in Tab 1.")

if __name__ == "__main__":
    main()
