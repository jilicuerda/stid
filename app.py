import streamlit as st
import pdfplumber
import pandas as pd
import re
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- OPTIMIZED IMAGE LOADER ---
@st.cache_data(show_spinner=False)
def load_page_image(file_bytes):
    """
    Loads the PDF from bytes, extracts Page 1 as a low-res image, 
    and returns the image + dimensions. 
    Crucially: It closes the PDF immediately to free RAM.
    """
    with pdfplumber.open(file_bytes) as pdf:
        page0 = pdf.pages[0]
        # 72 DPI is standard screen res. Low memory footprint.
        img = page0.to_image(resolution=72).original
        return img, page0.width, page0.height

class VolleySheetExtractor:
    def __init__(self, pdf_file):
        # We don't keep the PDF open in self. We open it on demand.
        self.pdf_file = pdf_file
        # Scale factor for 72 DPI is 1.0 (1 pt = 1 px)
        self.scale_factor = 1.0

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y, p_height):
        match_data = []
        
        # Open PDF only for extraction moment
        with pdfplumber.open(self.pdf_file) as pdf:
            page = pdf.pages[0]
            
            for set_num in range(1, 6): 
                current_y = base_y + ((set_num - 1) * offset_y)
                
                # Team A
                if current_y + h < p_height:
                    row_l = self._extract_row_from_page(page, base_x, current_y, w, h)
                    if row_l: match_data.append({"Set": set_num, "Team": "Left Grid", "Starters": row_l})
                
                # Team B
                if current_y + h < p_height:
                    row_r = self._extract_row_from_page(page, base_x + offset_x, current_y, w, h)
                    if row_r: match_data.append({"Set": set_num, "Team": "Right Grid", "Starters": row_r})
                    
        return match_data

    def _extract_row_from_page(self, page, start_x, start_y, w, h):
        row_data = []
        for i in range(6):
            x = start_x + (i * w)
            # Strict top 40% crop
            bbox = (x + 1, start_y + 1, x + w - 1, start_y + (h * 0.4))
            try:
                text = page.crop(bbox).extract_text()
                val = "?"
                if text:
                    for token in text.split():
                        clean = re.sub(r'[^0-9]', '', token)
                        if clean.isdigit() and len(clean) <= 2:
                            val = clean
                            break
                row_data.append(val)
            except:
                row_data.append("?")
        
        if all(x == "?" for x in row_data): return None
        return row_data

    def get_cell_debug(self, base_img, base_x, base_y, w, h, offset_x, offset_y, target_set, target_team, target_pos_idx):
        """Helper for the X-Ray Inspector"""
        set_y_px = base_y + ((target_set - 1) * offset_y)
        team_x_px = base_x if target_team == "Left" else base_x + offset_x
        cell_x_px = team_x_px + (target_pos_idx * w)
        
        # Visual Crop from Image
        img_bbox = (cell_x_px, set_y_px, cell_x_px + w, set_y_px + h)
        try:
            cell_img = base_img.crop(img_bbox)
        except:
            cell_img = Image.new('RGB', (50, 50), color='gray')
            
        return cell_img

def draw_grid_on_image(base_img, bx, by, w, h, off_x, off_y):
    # Draw on a copy to keep original clean
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
    st.title("🏐 VolleyStats: Ultra-Lite")
    
    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")

    if not uploaded_file:
        st.info("Upload PDF to begin.")
        return

    # Load Image Once (Cached)
    try:
        base_img, p_width, p_height = load_page_image(uploaded_file)
    except Exception as e:
        st.error(f"Error loading PDF: {e}")
        return

    extractor = VolleySheetExtractor(uploaded_file)

    tab1, tab2 = st.tabs(["📐 Align Grid", "📥 Extract Data"])

    with tab1:
        st.write("### Calibration (72 DPI)")
        c1, c2 = st.columns(2)
        with c1:
            base_x = st.number_input("Start X", value=127, step=1)
            base_y = st.number_input("Start Y", value=90, step=1)
            w = st.number_input("Cell Width", value=24, step=1)
            h = st.number_input("Cell Height", value=24, step=1)
        with c2:
            offset_x = st.number_input("Right Offset", value=422, step=1) 
            offset_y = st.number_input("Down Offset", value=158, step=1)

        # Draw grid on the cached image
        debug_img = draw_grid_on_image(base_img, base_x, base_y, w, h, offset_x, offset_y)
        
        # --- FIX: Removed width=None, used use_container_width=True ---
        st.image(debug_img, use_container_width=True)

    with tab2:
        if st.button("🚀 Extract All"):
            with st.spinner("Extracting..."):
                # Pass p_height to avoid out-of-bounds errors
                data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y, p_height)
                
            if data:
                df = pd.DataFrame(data)
                df['Starters'] = df['Starters'].apply(lambda x: " | ".join(x))
                st.dataframe(df, use_container_width=True)
            else:
                st.error("No valid data found.")

if __name__ == "__main__":
    main()
