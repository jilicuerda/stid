import streamlit as st
import pdfplumber
import pandas as pd
import re
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- OPTIMIZED IMAGE LOADER (100 DPI) ---
@st.cache_data(show_spinner=False)
def load_page_image(file_bytes):
    with pdfplumber.open(file_bytes) as pdf:
        page0 = pdf.pages[0]
        # 100 DPI is the sweet spot: Clear text, Low RAM
        img = page0.to_image(resolution=100).original
        return img, page0.width, page0.height

class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf_file = pdf_file

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y, p_height):
        match_data = []
        
        # Open PDF only for the split second we need to read text
        with pdfplumber.open(self.pdf_file) as pdf:
            page = pdf.pages[0]
            # Scale factor: PDF points (72) vs Image pixels (100)
            scale = 72 / 100
            
            for set_num in range(1, 6): 
                current_y = base_y + ((set_num - 1) * offset_y)
                
                # --- LEFT TEAM ---
                # We scale the PIXEL coordinates back to PDF POINTS for extraction
                row_l = self._extract_row(page, current_y, base_x, w, h, scale, p_height)
                if row_l: 
                    match_data.append({"Set": set_num, "Team": "Left Grid", "Starters": row_l})
                
                # --- RIGHT TEAM ---
                row_r = self._extract_row(page, current_y, base_x + offset_x, w, h, scale, p_height)
                if row_r:
                    match_data.append({"Set": set_num, "Team": "Right Grid", "Starters": row_r})
                    
        return match_data

    def _extract_row(self, page, top_y, start_x, w, h, scale, p_height):
        row_data = []
        
        # Convert Pixel Y to PDF Points Y for safety check
        if (top_y * scale) + (h * scale) > page.height: return None

        for i in range(6):
            # Calculate Pixel Box
            px_x = start_x + (i * w)
            px_y = top_y
            
            # Convert to PDF Points for Cropping
            # BBox = (x0, top, x1, bottom)
            pdf_x0 = px_x * scale
            pdf_top = px_y * scale
            pdf_x1 = (px_x + w) * scale
            # Strict Top 45% Crop to ignore bottom grid
            pdf_bottom = pdf_top + ((h * scale) * 0.45)
            
            bbox = (pdf_x0 + 1, pdf_top + 1, pdf_x1 - 1, pdf_bottom)
            
            try:
                text = page.crop(bbox).extract_text()
                val = "?"
                if text:
                    # Clean garbage characters
                    clean_text = text.replace("|", "").replace("\n", " ")
                    for token in clean_text.split():
                        digits = re.sub(r'[^0-9]', '', token)
                        # Valid numbers are 1-99. 
                        if digits.isdigit() and len(digits) <= 2:
                            val = digits
                            break
                row_data.append(val)
            except:
                row_data.append("?")
        
        if all(x == "?" for x in row_data): return None
        return row_data

def draw_grid_on_image(base_img, bx, by, w, h, off_x, off_y):
    img_copy = base_img.copy()
    draw = ImageDraw.Draw(img_copy)
    for s in range(4):
        cur_y = by + (s * off_y)
        # Left (Red)
        for i in range(6):
            draw.rectangle([bx + (i*w), cur_y, bx + (i*w) + w, cur_y + h], outline="red", width=2)
        # Right (Blue)
        if off_x > 0:
            cur_x = bx + off_x
            for i in range(6):
                draw.rectangle([cur_x + (i*w), cur_y, cur_x + (i*w) + w, cur_y + h], outline="blue", width=2)
    return img_copy

def main():
    st.title("🏐 VolleyStats: Ultra-Lite (100 DPI)")
    
    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")

    if not uploaded_file:
        st.info("Upload PDF to begin.")
        return

    # Load Image
    try:
        base_img, p_width, p_height = load_page_image(uploaded_file)
    except Exception as e:
        st.error(f"Error loading PDF: {e}")
        return

    extractor = VolleySheetExtractor(uploaded_file)

    tab1, tab2 = st.tabs(["📐 Align Grid", "📥 Extract Data"])

    with tab1:
        st.write("### Calibration (100 DPI)")
        st.info("Resolution increased for better accuracy. Coordinates recalculated.")
        
        c1, c2 = st.columns(2)
        with c1:
            # I have pre-calculated these for 100 DPI based on your previous success
            base_x = st.number_input("Start X", value=176, step=1)
            base_y = st.number_input("Start Y", value=124, step=1)
            w = st.number_input("Cell Width", value=33, step=1)
            h = st.number_input("Cell Height", value=33, step=1)
        with c2:
            offset_x = st.number_input("Right Offset", value=586, step=1) 
            offset_y = st.number_input("Down Offset", value=220, step=1)

        debug_img = draw_grid_on_image(base_img, base_x, base_y, w, h, offset_x, offset_y)
        st.image(debug_img, use_container_width=True)

    with tab2:
        if st.button("🚀 Extract All"):
            with st.spinner("Extracting..."):
                # Extract
                data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y, p_height)
                
            if data:
                df = pd.DataFrame(data)
                # Formatting: Join list into string "1 | 2 | 3..."
                df['Starters'] = df['Starters'].apply(lambda x: " | ".join(x))
                st.dataframe(df, use_container_width=True)
            else:
                st.error("No valid data found. Check Alignment.")

if __name__ == "__main__":
    main()
