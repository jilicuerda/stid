import streamlit as st
import pdfplumber
import pandas as pd
import pypdfium2 as pdfium
import re
import gc
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- 1. IMAGE ENGINE ---
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

# --- 2. EXTRACTION ENGINE ---
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
                    if row_l: 
                        match_data.append({"Set": set_num, "Team": "Home (Left)", "Starters": row_l})
                
                # RIGHT
                if current_y + h < p_height:
                    row_r = self._extract_row(page, current_y, base_x + offset_x, w, h)
                    if row_r: 
                        match_data.append({"Set": set_num, "Team": "Away (Right)", "Starters": row_r})
        gc.collect()
        return match_data

    def _extract_row(self, page, top_y, start_x, w, h):
        row_data = []
        for i in range(6):
            drift = i * 0.3
            px_x = start_x + (i * w) + drift
            px_y = top_y
            
            # Box: Expanded 3px, Height 80%
            bbox = (px_x - 3, px_y, px_x + w + 3, px_y + (h * 0.8))
            
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
        # Left
        for i in range(6):
            drift = i * 0.3
            x = bx + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="red", width=2)
        # Right
        cur_x = bx + off_x
        for i in range(6):
            drift = i * 0.3
            x = cur_x + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="blue", width=2)
    return img

# --- 4. APP UI ---
def main():
    st.title("🏐 VolleyStats Pro")
    st.markdown("Upload an official **FFVolley Scoresheet** to extract starting lineups automatically.")

    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")
        
        with st.expander("⚙️ Advanced Calibration"):
            st.info("Only change if extraction fails.")
            # YOUR GOLDEN COORDINATES (Hidden by default)
            base_x = st.number_input("Start X", value=123)
            base_y = st.number_input("Start Y", value=88)
            w = st.number_input("Cell Width", value=23)
            h = st.number_input("Cell Height", value=20)
            offset_x = st.number_input("Right Offset", value=492) 
            offset_y = st.number_input("Down Offset", value=151)

    if not uploaded_file:
        st.info("Waiting for file...")
        return

    try:
        file_bytes = uploaded_file.getvalue() 
        base_img, scale = get_page_image(file_bytes)
        
        # Show Preview
        st.subheader("1. Verify Alignment")
        debug_img = draw_grid(base_img, base_x, base_y, w, h, offset_x, offset_y)
        st.image(debug_img, use_container_width=True)
        
    except:
        st.error("Error reading PDF.")
        return

    # Extract Button
    st.divider()
    if st.button("🚀 Extract & Process Data", type="primary"):
        extractor = VolleySheetExtractor(uploaded_file)
        p_height = 842 
        
        with st.spinner("Scanning document..."):
            data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y, p_height)
        
        if data:
            # --- DATA REFINEMENT ---
            df = pd.DataFrame(data)
            
            # Split list into 6 columns
            roster_cols = pd.DataFrame(df['Starters'].tolist(), columns=['Zone 1', 'Zone 2', 'Zone 3', 'Zone 4', 'Zone 5', 'Zone 6'])
            
            # Combine
            final_df = pd.concat([df[['Set', 'Team']], roster_cols], axis=1)
            
            st.success("✅ Extraction Complete!")
            st.dataframe(final_df, use_container_width=True)
            
            # CSV Download
            csv = final_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Excel/CSV",
                data=csv,
                file_name="match_lineups.csv",
                mime="text/csv"
            )
        else:
            st.error("No data found. Please check the Calibration settings.")

if __name__ == "__main__":
    main()
