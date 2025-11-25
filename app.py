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
        self.img_scale = 150 
        self.scale_factor = 72 / 150

    def get_page_image(self):
        return self.page0.to_image(resolution=self.img_scale).original

    def _scale_coords(self, val):
        return val * self.scale_factor

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y):
        match_data = []
        
        for set_num in range(1, 6): 
            current_y_pixels = base_y + ((set_num - 1) * offset_y)
            
            # --- TEAM A (LEFT) ---
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
        """Helper to extract 6 grid cells with SMART CLEANING."""
        row_data = []
        
        pdf_y = self._scale_coords(start_y_px)
        pdf_h = self._scale_coords(h_px)
        
        if pdf_y + pdf_h > self.page0.height:
            return []

        for i in range(6):
            x_px = start_x_px + (i * w_px)
            pdf_x = self._scale_coords(x_px)
            pdf_w = self._scale_coords(w_px)
            
            # Crop Box: Shrink slightly (2pts) to avoid borders
            bbox = (pdf_x + 2, pdf_y + 2, pdf_x + pdf_w - 2, pdf_y + pdf_h - 2)
            
            try:
                crop = self.page0.crop(bbox)
                text = crop.extract_text()
                
                # --- NEW CLEANING LOGIC ---
                val = "?"
                if text:
                    # 1. Split by whitespace or newlines
                    tokens = text.split()
                    
                    # 2. Find the first token that is a valid Jersey Number (1-99)
                    for token in tokens:
                        # Remove non-digits
                        clean_token = re.sub(r'[^0-9]', '', token)
                        
                        # Verify it looks like a player number (1 or 2 digits)
                        if clean_token.isdigit() and len(clean_token) <= 2:
                            val = clean_token
                            break # Found the top number (Starter), stop looking!
                
                row_data.append(val)
            except:
                row_data.append("?")
                
        # Filter out empty rows
        if all(x == "?" for x in row_data):
            return []
            
        return row_data

    def draw_full_grid(self, img, bx, by, w, h, off_x, off_y):
        draw = ImageDraw.Draw(img)
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
                st.success("Cleaned Data! Now identifying only the top number (Starter).")
            else:
                st.error("No data extracted.")

if __name__ == "__main__":
    main()
