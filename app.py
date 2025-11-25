import streamlit as st
import pdfplumber
import pandas as pd
import re
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- CRITICAL FIX: CACHING TO PREVENT CRASHES ---
@st.cache_data
def get_pdf_page_image(file_content):
    """
    Converts PDF to image ONCE and caches it.
    We use 72 DPI (Standard) to save RAM.
    """
    with pdfplumber.open(file_content) as pdf:
        page0 = pdf.pages[0]
        # 72 DPI matches PDF points exactly (Scale = 1.0)
        # This simplifies math and saves massive memory
        return page0.to_image(resolution=72).original

class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf = pdfplumber.open(pdf_file)
        self.page0 = self.pdf.pages[0]
        # Since we use 72 DPI, Pixels == Points. Scale factor is 1.
        self.scale_factor = 1.0 

    def get_cell_debug(self, base_img, base_x, base_y, w, h, offset_x, offset_y, target_set, target_team, target_pos_idx):
        set_y_px = base_y + ((target_set - 1) * offset_y)
        team_x_px = base_x if target_team == "Left" else base_x + offset_x
        cell_x_px = team_x_px + (target_pos_idx * w)
        
        # Crop Box (Top 40% to ignore points grid)
        bbox = (cell_x_px, set_y_px, cell_x_px + w, set_y_px + (h * 0.4))
        
        # Visual Crop
        img_bbox = (cell_x_px, set_y_px, cell_x_px + w, set_y_px + h)
        try:
            cell_img = base_img.crop(img_bbox)
        except:
            cell_img = Image.new('RGB', (50, 50), color='gray')

        try:
            crop = self.page0.crop(bbox)
            raw_text = crop.extract_text()
        except:
            raw_text = "Error"
            
        return cell_img, raw_text

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y):
        match_data = []
        for set_num in range(1, 6): 
            current_y = base_y + ((set_num - 1) * offset_y)
            
            # LEFT
            row_l = self._extract_row(base_x, current_y, w, h)
            if row_l: 
                match_data.append({"Set": set_num, "Team": "Left Grid", "Starters": row_l})
            
            # RIGHT
            row_r = self._extract_row(base_x + offset_x, current_y, w, h)
            if row_r:
                match_data.append({"Set": set_num, "Team": "Right Grid", "Starters": row_r})
            
        return match_data

    def _extract_row(self, start_x, start_y, w, h):
        row_data = []
        
        if start_y + h > self.page0.height: return None

        for i in range(6):
            x = start_x + (i * w)
            
            # Strict top 40% crop
            bbox = (x + 1, start_y + 1, x + w - 1, start_y + (h * 0.4))
            
            try:
                text = self.page0.crop(bbox).extract_text()
                val = "?"
                if text:
                    tokens = text.split()
                    for token in tokens:
                        clean = re.sub(r'[^0-9]', '', token)
                        if clean.isdigit() and len(clean) <= 2:
                            val = clean
                            break
                row_data.append(val)
            except:
                row_data.append("?")
        
        if all(x == "?" for x in row_data): return None
        return row_data

    def draw_full_grid(self, img, bx, by, w, h, off_x, off_y):
        # Create a copy to draw on so we don't mutate the cached image
        img_copy = img.copy()
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
    st.title("🏐 VolleyStats: Visual Calibrator")
    
    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")

    if not uploaded_file:
        st.info("Upload PDF to begin.")
        return

    # Initialize Extractor
    extractor = VolleySheetExtractor(uploaded_file)
    
    # --- CACHED IMAGE GENERATION (CRITICAL FOR PERFORMANCE) ---
    # We pass the file object wrapper to cache properly
    base_img = get_pdf_page_image(uploaded_file)

    tab1, tab2, tab3 = st.tabs(["📐 Align Grid", "🔍 X-Ray Inspector", "📥 Extract Data"])

    with tab1:
        st.write("### 1. Global Calibration")
        st.info("Resolution set to 72 DPI for stability. Values are now 1:1 with PDF points.")
        
        c1, c2 = st.columns(2)
        with c1:
            # Note: Default values adjusted for 72 DPI (approx half of 150 DPI values)
            # Previous X=264 (at 150DPI) -> ~127 (at 72DPI)
            base_x = st.number_input("Start X", value=127, step=1)
            base_y = st.number_input("Start Y", value=90, step=1)
            w = st.number_input("Cell Width", value=24, step=1)
            h = st.number_input("Cell Height", value=24, step=1)
        with c2:
            offset_x = st.number_input("Right Offset", value=422, step=1) 
            offset_y = st.number_input("Down Offset", value=158, step=1)

        debug_img = extractor.draw_full_grid(base_img, base_x, base_y, w, h, offset_x, offset_y)
        st.image(debug_img, width=None) # Let Streamlit handle width

    with tab2:
        st.write("### 2. Check Specific Cells")
        
        c_set, c_team, c_pos = st.columns(3)
        inspect_set = c_set.number_input("Inspect Set #", 1, 4, 1)
        inspect_team = c_team.selectbox("Inspect Team", ["Left", "Right"])
        inspect_pos = c_pos.selectbox("Inspect Position", ["I", "II", "III", "IV", "V", "VI"])
        
        pos_map = {"I": 0, "II": 1, "III": 2, "IV": 3, "V": 4, "VI": 5}
        
        cell_img, raw_txt = extractor.get_cell_debug(
            base_img, base_x, base_y, w, h, offset_x, offset_y, 
            inspect_set, inspect_team, pos_map[inspect_pos]
        )
        
        c_img, c_txt = st.columns(2)
        with c_img:
            st.image(cell_img, width=100, caption="Cell View")
        with c_txt:
            st.metric("Cleaned Text", f"'{raw_txt}'")
            if raw_txt.strip().isdigit():
                st.success("✅ Valid!")
            else:
                st.warning("⚠️ Empty/Garbage")

    with tab3:
        if st.button("🚀 Extract All"):
            data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y)
            if data:
                df = pd.DataFrame(data)
                df['Starters'] = df['Starters'].apply(lambda x: " | ".join(x))
                st.dataframe(df, use_container_width=True)
            else:
                st.error("No valid data found. Check Alignment.")

if __name__ == "__main__":
    main()
