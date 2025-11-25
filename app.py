import streamlit as st
import pdfplumber
import pandas as pd
import re
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Golden", page_icon="🏐", layout="wide")

# --- OPTIMIZED IMAGE LOADER (100 DPI) ---
@st.cache_data(show_spinner=False)
def load_page_image(file_bytes):
    with pdfplumber.open(file_bytes) as pdf:
        page0 = pdf.pages[0]
        # 100 DPI is the sweet spot we found
        img = page0.to_image(resolution=100).original
        return img, page0.width, page0.height

class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf_file = pdf_file
        self.scale_factor = 72 / 100 # Convert 100 DPI pixels to 72 DPI PDF points

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y, p_height):
        match_data = []
        
        with pdfplumber.open(self.pdf_file) as pdf:
            page = pdf.pages[0]
            
            for set_num in range(1, 6): 
                current_y = base_y + ((set_num - 1) * offset_y)
                
                # LEFT GRID
                if current_y + h < p_height:
                    row_l = self._extract_row(page, current_y, base_x, w, h)
                    if row_l: match_data.append({"Set": set_num, "Team": "Left Grid", "Starters": row_l})
                
                # RIGHT GRID
                if current_y + h < p_height:
                    row_r = self._extract_row(page, current_y, base_x + offset_x, w, h)
                    if row_r: match_data.append({"Set": set_num, "Team": "Right Grid", "Starters": row_r})
                    
        return match_data

    def _extract_row(self, page, top_y, start_x, w, h):
        row_data = []
        scale = self.scale_factor
        
        for i in range(6):
            # DRIFT CORRECTION: Add 0.5px per column to account for black grid lines
            drift = i * 0.5
            px_x = start_x + (i * w) + drift
            
            # Convert to PDF Points
            pdf_x0 = px_x * scale
            pdf_top = top_y * scale
            pdf_x1 = (px_x + w) * scale
            
            # STRICT HEIGHT: Ignore bottom half of box (only read top 28px converted)
            pdf_bottom = pdf_top + (28 * scale)
            
            bbox = (pdf_x0 + 1, pdf_top + 1, pdf_x1 - 1, pdf_bottom)
            
            try:
                text = page.crop(bbox).extract_text()
                val = "?"
                if text:
                    for token in text.split():
                        clean = re.sub(r'[^0-9]', '', token)
                        # Only accept 1 or 2 digit numbers (Player Jersey)
                        if clean.isdigit() and len(clean) <= 2:
                            val = clean
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
            drift = i * 0.5
            x = bx + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="red", width=2)
        # Right (Blue)
        if off_x > 0:
            cur_x = bx + off_x
            for i in range(6):
                drift = i * 0.5
                x = cur_x + (i * w) + drift
                draw.rectangle([x, cur_y, x + w, cur_y + h], outline="blue", width=2)
    return img_copy

def main():
    st.title("🏐 VolleyStats: Golden Config")
    
    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")
        
    if not uploaded_file:
        st.info("Upload PDF to begin.")
        return

    try:
        base_img, p_width, p_height = load_page_image(uploaded_file)
    except:
        st.error("Error loading PDF.")
        return

    extractor = VolleySheetExtractor(uploaded_file)

    tab1, tab2 = st.tabs(["✅ Verify Alignment", "📊 Match Data"])

    with tab1:
        st.write("### Golden Coordinates (Pre-Loaded)")
        st.info("These match your screenshots perfectly. Just verify the Red/Blue boxes.")
        
        c1, c2 = st.columns(2)
        with c1:
            # EXACT VALUES FROM YOUR SCREENSHOTS
            base_x = st.number_input("Start X", value=171) 
            base_y = st.number_input("Start Y", value=122)
            w = st.number_input("Cell Width", value=31)
            h = st.number_input("Cell Height", value=28) # Shortened to ignore points below
        with c2:
            offset_x = st.number_input("Right Offset", value=685) 
            offset_y = st.number_input("Down Offset", value=210)

        debug_img = draw_grid_on_image(base_img, base_x, base_y, w, h, offset_x, offset_y)
        st.image(debug_img, use_container_width=True)

    with tab2:
        if st.button("🚀 Extract All Data"):
            data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y, p_height)
            
            if data:
                df = pd.DataFrame(data)
                
                # Formatting
                df['Starters'] = df['Starters'].apply(lambda x: " | ".join(x))
                
                st.success("Extraction Successful!")
                st.dataframe(df, use_container_width=True)
                
                # Download CSV option
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("Download CSV", csv, "match_rotations.csv", "text/csv")
            else:
                st.error("No data found. Check Tab 1.")

if __name__ == "__main__":
    main()
