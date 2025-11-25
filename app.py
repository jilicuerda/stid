import streamlit as st
import pdfplumber
import pandas as pd
import pypdfium2 as pdfium
import re
import gc
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- MEMORY OPTIMIZED IMAGE LOADER ---
@st.cache_data(show_spinner=False)
def get_page_image(file_bytes):
    """
    Uses pypdfium2 (C++ binding) to render the page. 
    Much faster and lighter on RAM than pdfplumber.to_image().
    """
    # Load PDF from bytes
    pdf = pdfium.PdfDocument(file_bytes)
    page = pdf[0]
    
    # Render at 100 DPI (Scale ~1.39). Good balance of clarity vs RAM.
    # standard pdf points = 72 dpi. 100/72 = 1.388
    scale = 1.39 
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()
    
    # Clean up C++ objects immediately
    page.close()
    pdf.close()
    gc.collect() # Force RAM cleanup
    
    return pil_image, scale

class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf_file = pdf_file

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y, p_height):
        match_data = []
        
        # Open PDF only momentarily for text extraction
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
        
        gc.collect()
        return match_data

    def _extract_row(self, page, top_y, start_x, w, h):
        row_data = []
        
        for i in range(6):
            # Coordinates are already in PDF Points (from inputs)
            px_x = start_x + (i * w)
            px_y = top_y
            
            # STRICT crop (Top 45% only)
            bbox = (px_x + 1, px_y + 1, px_x + w - 1, px_y + (h * 0.45))
            
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

def draw_grid(base_img, scale, bx, by, w, h, off_x, off_y):
    # Draw on copy
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    
    # We must scale the PDF Point coordinates UP to match the 100 DPI Image
    sbx, sby = bx * scale, by * scale
    sw, sh = w * scale, h * scale
    soff_x, soff_y = off_x * scale, off_y * scale
    
    for s in range(4):
        cur_y = sby + (s * soff_y)
        # Left
        for i in range(6):
            draw.rectangle([sbx + (i*sw), cur_y, sbx + (i*sw) + sw, cur_y + sh], outline="red", width=2)
        # Right
        if off_x > 0:
            cur_x = sbx + soff_x
            for i in range(6):
                draw.rectangle([cur_x + (i*sw), cur_y, cur_x + (i*sw) + sw, cur_y + sh], outline="blue", width=2)
    return img

def main():
    st.title("🏐 VolleyStats: Stable Core")
    
    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")
        st.divider()
        if st.button("🧹 Clear Memory"):
            st.cache_data.clear()
            gc.collect()

    if not uploaded_file:
        st.info("Upload PDF to begin.")
        return

    # 1. Load Image (Optimized)
    try:
        # Convert uploaded file to bytes for pypdfium2
        file_bytes = uploaded_file.getvalue() 
        base_img, scale_factor = get_page_image(file_bytes)
    except Exception as e:
        st.error(f"Error loading image: {e}")
        return

    extractor = VolleySheetExtractor(uploaded_file)

    tab1, tab2 = st.tabs(["📐 Verify Alignment", "🚀 Extract Data"])

    with tab1:
        st.write("### Golden Coordinates (PDF Points)")
        st.info(f"Rendering at 100 DPI (Scale: {scale_factor:.2f}). Memory Optimized.")
        
        c1, c2 = st.columns(2)
        with c1:
            # VALUES FROM YOUR SUCCESSFUL CSV RUN
            base_x = st.number_input("Start X", value=171, step=1)
            base_y = st.number_input("Start Y", value=122, step=1)
            w = st.number_input("Cell Width", value=31, step=1)
            h = st.number_input("Cell Height", value=28, step=1)
        with c2:
            offset_x = st.number_input("Right Offset", value=685, step=1) 
            # Decreased slightly to catch Set 2
            offset_y = st.number_input("Down Offset", value=209, step=1) 

        # Draw
        debug_img = draw_grid(base_img, scale_factor, base_x, base_y, w, h, offset_x, offset_y)
        st.image(debug_img, use_container_width=True)

    with tab2:
        if st.button("Extract All Data"):
            # PDF Points for height check (approx A4 height in points)
            p_height = 842 
            
            data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y, p_height)
            
            if data:
                df = pd.DataFrame(data)
                df['Starters'] = df['Starters'].apply(lambda x: " | ".join(x))
                st.success("Extraction Successful!")
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("No data found. Check alignment tab.")

if __name__ == "__main__":
    main()
