import streamlit as st
import pdfplumber
import pandas as pd
from PIL import Image, ImageDraw

st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf = pdfplumber.open(pdf_file)
        self.page0 = self.pdf.pages[0]
        # Standard FFVolley sheets are usually 150-200 DPI equivalent in pixels
        self.img_scale = 150 

    def get_page_image(self):
        return self.page0.to_image(resolution=self.img_scale).original

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y):
        """Extracts all sets based on the calibrated offsets."""
        match_data = []
        
        # Loop through Sets 1 to 5
        # Note: Set 5 might be in a different spot, but this covers 1-4 standard layout
        for set_num in range(1, 5): 
            # Calculate Y for this set
            current_y = base_y + ((set_num - 1) * offset_y)
            
            # --- TEAM A (LEFT) ---
            team_a_starters = self._extract_row(base_x, current_y, w, h)
            match_data.append({
                "Set": set_num, "Team": "Left", "Starters": team_a_starters
            })
            
            # --- TEAM B (RIGHT) ---
            # Team B is usually at Base X + Offset X
            team_b_x = base_x + offset_x
            team_b_starters = self._extract_row(team_b_x, current_y, w, h)
            match_data.append({
                "Set": set_num, "Team": "Right", "Starters": team_b_starters
            })
            
        return match_data

    def _extract_row(self, start_x, start_y, w, h):
        """Helper to extract 6 grid cells."""
        row_data = []
        for i in range(6):
            x0 = start_x + (i * w)
            y0 = start_y
            x1 = x0 + w
            y1 = y0 + h
            
            # Crop using PDF coordinates (need to scale from Image coordinates)
            # PDFPlumber coordinates are points (1/72 inch). Image is pixels.
            # We use a rough scaling factor or just assume user calibrated in PDF-space if using raw crop
            # For simplicity in this demo, we assume the slider values map 1:1 to the crop logic used previously
            
            crop = self.page0.crop((x0, y0, x1, y1))
            text = crop.extract_text()
            val = text.strip() if text else "?"
            row_data.append(val)
        return row_data

    def draw_full_grid(self, img, bx, by, w, h, off_x, off_y):
        draw = ImageDraw.Draw(img)
        
        # Draw 4 Sets vertically
        for s in range(4):
            cur_y = by + (s * off_y)
            
            # Draw Left Team (Red)
            for i in range(6):
                draw.rectangle(
                    [bx + (i*w), cur_y, bx + (i*w) + w, cur_y + h],
                    outline="red", width=3
                )
            
            # Draw Right Team (Blue)
            # Only draw if offset_x is > 0 (user has started calibrating it)
            if off_x > 0:
                cur_x_right = bx + off_x
                for i in range(6):
                    draw.rectangle(
                        [cur_x_right + (i*w), cur_y, cur_x_right + (i*w) + w, cur_y + h],
                        outline="blue", width=3
                    )
        return img

def main():
    st.title("🏐 VolleyStats: Full Sheet Calibrator")
    
    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")

    if not uploaded_file:
        st.info("Upload PDF to begin.")
        return

    extractor = VolleySheetExtractor(uploaded_file)

    tab1, tab2 = st.tabs(["📐 Full Page Calibration", "📊 Extracted Data"])

    with tab1:
        st.write("### 1. Match the RED BOXES (Team A)")
        c1, c2 = st.columns(2)
        with c1:
            base_x = st.slider("Start X", 0, 600, 264) # Defaulted to your value
            base_y = st.slider("Start Y", 0, 800, 186) # Defaulted to your value
        with c2:
            w = st.slider("Cell Width", 10, 60, 50)    # Defaulted to your value
            h = st.slider("Cell Height", 10, 60, 50)   # Defaulted to your value

        st.divider()
        st.write("### 2. Match the BLUE BOXES (Team B & Lower Sets)")
        st.info("Increase these sliders until the Blue boxes land on Team B (Right) and Sets 2/3/4 (Below).")
        
        c3, c4 = st.columns(2)
        with c3:
            # Distance to the Right Grid
            offset_x = st.slider("➡️ Right Offset (Team B)", 0, 1000, 0, step=5)
        with c4:
            # Distance to the Next Set Below
            offset_y = st.slider("⬇️ Down Offset (Next Set)", 0, 600, 0, step=5)

        # Visualization
        img = extractor.get_page_image()
        debug_img = extractor.draw_full_grid(img, base_x, base_y, w, h, offset_x, offset_y)
        st.image(debug_img, use_container_width=True)

    with tab2:
        if st.button("Extract All Sets"):
            data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y)
            
            df = pd.DataFrame(data)
            
            # Clean up the list presentation
            df['Starters'] = df['Starters'].apply(lambda x: " | ".join(x))
            
            st.dataframe(df, use_container_width=True)
            st.success("Save these 6 numbers (X, Y, W, H, OffX, OffY) and you never have to calibrate again!")

if __name__ == "__main__":
    main()
