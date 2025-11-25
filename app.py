import streamlit as st
import pdfplumber
import pandas as pd
import pypdfium2 as pdfium
import re
import gc
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- 1. CRASH-PROOF IMAGE LOADER ---
@st.cache_data(show_spinner=False)
def get_page_image(file_bytes):
    """
    Renders PDF page to image using C++ engine (Fast & Low RAM).
    Returns the image and the scale factor to map coordinates.
    """
    pdf = pdfium.PdfDocument(file_bytes)
    page = pdf[0]
    
    # Render at 72 DPI (1:1 with PDF Points) for perfect accuracy
    scale = 1.0 
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()
    
    page.close()
    pdf.close()
    gc.collect()
    
    return pil_image, scale

# --- 2. EXTRACTION LOGIC ---
class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf_file = pdf_file

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y, p_height):
        match_data = []
        
        # Open PDF only momentarily
        with pdfplumber.open(self.pdf_file) as pdf:
            page = pdf.pages[0]
            
            for set_num in range(1, 6): 
                current_y = base_y + ((set_num - 1) * offset_y)
                
                # LEFT GRID
                if current_y + h < p_height:
                    row_l = self._extract_row(page, current_y, base_x, w, h)
                    if row_l: 
                        match_data.append({"Set": set_num, "Team": "Left Grid", "Starters": row_l})
                
                # RIGHT GRID
                if current_y + h < p_height:
                    row_r = self._extract_row(page, current_y, base_x + offset_x, w, h)
                    if row_r: 
                        match_data.append({"Set": set_num, "Team": "Right Grid", "Starters": row_r})
        
        gc.collect()
        return match_data

    def _extract_row(self, page, top_y, start_x, w, h):
        row_data = []
        for i in range(6):
            # DRIFT FIX: Add 0.3pt per column to account for border thickness
            drift = i * 0.3
            px_x = start_x + (i * w) + drift
            px_y = top_y
            
            # STRICT CROP: Only look at top 60% of box to ignore points grid
            bbox = (px_x, px_y, px_x + w, px_y + (h * 0.6))
            
            try:
                text = page.crop(bbox).extract_text()
                val = "?"
                if text:
                    # Smart Clean: Find the first 1-2 digit number
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

# --- 3. VISUALIZATION HELPER ---
def draw_grid(base_img, bx, by, w, h, off_x, off_y):
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    
    for s in range(4): # Draw 4 sets
        cur_y = by + (s * off_y)
        # Left (Red)
        for i in range(6):
            drift = i * 0.3
            x = bx + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="red", width=1)
        # Right (Blue)
        cur_x = bx + off_x
        for i in range(6):
            drift = i * 0.3
            x = cur_x + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="blue", width=1)
    return img

# --- 4. FRONTEND ---
def main():
    st.title("🏐 VolleyStats Pro: Final")
    
    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")
        st.divider()
        if st.button("🧹 Reset"):
            st.cache_data.clear()

    if not uploaded_file:
        st.info("Upload PDF to begin.")
        return

    # Load Image
    try:
        file_bytes = uploaded_file.getvalue() 
        base_img, scale = get_page_image(file_bytes)
    except Exception as e:
        st.error("Error reading PDF. Please try a different file.")
        return

    extractor = VolleySheetExtractor(uploaded_file)

    tab1, tab2 = st.tabs(["📐 Alignment", "🚀 Results"])

    with tab1:
        st.write("### Check Alignment (PDF Points)")
        c1, c2 = st.columns(2)
        with c1:
            # CONVERTED COORDINATES (100 DPI -> 72 DPI)
            base_x = st.number_input("Start X", value=123, step=1)
            base_y = st.number_input("Start Y", value=88, step=1)
            w = st.number_input("Cell Width", value=23, step=1)
            h = st.number_input("Cell Height", value=20, step=1)
        with c2:
            offset_x = st.number_input("Right Offset", value=493, step=1) 
            offset_y = st.number_input("Down Offset", value=151, step=1)

        # Draw Grid
        debug_img = draw_grid(base_img, base_x, base_y, w, h, offset_x, offset_y)
        st.image(debug_img, use_container_width=True)

    with tab2:
        if st.button("Extract Match Data"):
            # A4 Height in Points
            p_height = 842 
            
            data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y, p_height)
            
            if data:
                df = pd.DataFrame(data)
                
                # Display formatted table
                display_df = df.copy()
                display_df['Starters'] = display_df['Starters'].apply(lambda x: " | ".join(x))
                st.dataframe(display_df, use_container_width=True)
                
                # CSV Download
                csv = display_df.to_csv(index=False).encode('utf-8')
                st.download_button("Download CSV", csv, "match_data.csv", "text/csv")
            else:
                st.warning("No data found. Check alignment in Tab 1.")

if __name__ == "__main__":
    main()
