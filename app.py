import streamlit as st
import pdfplumber
import pandas as pd
import pypdfium2 as pdfium
import re
import gc
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro: Final", page_icon="🏐", layout="wide")

# --- 1. IMAGE LOADER ---
@st.cache_data(show_spinner=False)
def get_page_image(file_bytes):
    pdf = pdfium.PdfDocument(file_bytes)
    page = pdf[0]
    scale = 1.0 # 72 DPI
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()
    page.close()
    pdf.close()
    gc.collect()
    return pil_image, scale

# --- 2. EXTRACTOR ---
class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf_file = pdf_file

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y, p_height):
        match_data = []
        with pdfplumber.open(self.pdf_file) as pdf:
            page = pdf.pages[0]
            for set_num in range(1, 6): 
                current_y = base_y + ((set_num - 1) * offset_y)
                
                # LEFT
                if current_y + h < p_height:
                    row_l = self._extract_row(page, current_y, base_x, w, h)
                    if row_l: match_data.append({"Set": set_num, "Team": "Left Grid", "Starters": row_l})
                
                # RIGHT
                if current_y + h < p_height:
                    row_r = self._extract_row(page, current_y, base_x + offset_x, w, h)
                    if row_r: match_data.append({"Set": set_num, "Team": "Right Grid", "Starters": row_r})
        gc.collect()
        return match_data

    def _extract_row(self, page, top_y, start_x, w, h):
        row_data = []
        for i in range(6):
            drift = i * 0.5  # Increased drift correction slightly
            px_x = start_x + (i * w) + drift
            px_y = top_y
            
            # EXPANDED BOX: +3px width to catch drifting numbers
            # RESTRICTED HEIGHT: Top 70% only
            bbox = (px_x - 2, px_y, px_x + w + 3, px_y + (h * 0.7))
            
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

# --- 3. VISUALIZER ---
def draw_grid(base_img, bx, by, w, h, off_x, off_y):
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    for s in range(4): 
        cur_y = by + (s * off_y)
        # Left (Red)
        for i in range(6):
            drift = i * 0.5
            x = bx + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="red", width=2)
        # Right (Blue)
        cur_x = bx + off_x
        for i in range(6):
            drift = i * 0.5
            x = cur_x + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="blue", width=2)
    return img

# --- 4. UI ---
def main():
    st.title("🏐 VolleyStats Pro: Final")
    
    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")

    if not uploaded_file:
        st.info("Upload PDF to begin.")
        return

    try:
        file_bytes = uploaded_file.getvalue() 
        base_img, scale = get_page_image(file_bytes)
    except:
        st.error("Error reading PDF.")
        return

    extractor = VolleySheetExtractor(uploaded_file)

    tab1, tab2 = st.tabs(["📐 Alignment", "🚀 Results"])

    with tab1:
        st.write("### 1. Align the Grids")
        st.info("Goal: Red Boxes on Left Team, Blue Boxes on Right Team.")
        
        c1, c2 = st.columns(2)
        with c1:
            # ADJUSTED DEFAULTS
            base_x = st.number_input("Start X", value=123, step=1)
            base_y = st.number_input("Start Y", value=88, step=1)
            w = st.number_input("Cell Width", value=24, step=1) # Increased to 24
            h = st.number_input("Cell Height", value=20, step=1)
        with c2:
            offset_x = st.number_input("Right Offset", value=493, step=5) 
            offset_y = st.number_input("Down Offset", value=151, step=1)

        debug_img = draw_grid(base_img, base_x, base_y, w, h, offset_x, offset_y)
        st.image(debug_img, use_container_width=True)

    with tab2:
        if st.button("Extract Match Data"):
            p_height = 842 
            data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y, p_height)
            
            if data:
                df = pd.DataFrame(data)
                
                # --- GHOST DETECTOR ---
                # Check if Set 1 Left == Set 1 Right
                try:
                    s1_l = df[(df['Set'] == 1) & (df['Team'] == 'Left Grid')]['Starters'].iloc[0]
                    s1_r = df[(df['Set'] == 1) & (df['Team'] == 'Right Grid')]['Starters'].iloc[0]
                    
                    # Count matches
                    matches = sum(1 for a, b in zip(s1_l, s1_r) if a == b and a != "?")
                    if matches >= 4:
                        st.error("⚠️ GHOST DATA DETECTED! Left and Right grids are identical.")
                        st.warning("👉 Go to 'Alignment' and increase 'Right Offset' until Blue Boxes are on the Opponent.")
                except:
                    pass

                df['Starters'] = df['Starters'].apply(lambda x: " | ".join(x))
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("No data found.")

if __name__ == "__main__":
    main()
