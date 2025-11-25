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
        # REVERTED TO 150 DPI so your previous coordinates (264, 186) work again!
        self.img_scale = 150 
        self.scale_factor = 72 / 150

    def get_page_image(self):
        return self.page0.to_image(resolution=self.img_scale).original

    def _scale_coords(self, val):
        return val * self.scale_factor

    def get_cell_debug(self, base_x, base_y, w, h, offset_x, offset_y, target_set, target_team, target_pos_idx):
        set_y_px = base_y + ((target_set - 1) * offset_y)
        team_x_px = base_x if target_team == "Left" else base_x + offset_x
        cell_x_px = team_x_px + (target_pos_idx * w)
        
        pdf_x = self._scale_coords(cell_x_px)
        pdf_y = self._scale_coords(set_y_px)
        pdf_w = self._scale_coords(w)
        pdf_h = self._scale_coords(h)
        
        # Crop Box (Strict Top-Half Crop)
        bbox_text = (pdf_x, pdf_y, pdf_x + pdf_w, pdf_y + (pdf_h * 0.45))
        
        # Image Crop 
        img_bbox = (cell_x_px, set_y_px, cell_x_px + w, set_y_px + h)
        try:
            cell_img = self.get_page_image().crop(img_bbox)
        except:
            cell_img = Image.new('RGB', (50, 50), color='gray')

        try:
            crop = self.page0.crop(bbox_text)
            raw_text = crop.extract_text()
        except:
            raw_text = "Error"
            
        return cell_img, raw_text

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y):
        match_data = []
        for set_num in range(1, 6): 
            current_y_pixels = base_y + ((set_num - 1) * offset_y)
            
            # LEFT
            row_l = self._extract_row(base_x, current_y_pixels, w, h)
            if row_l: # Only add if we found data
                match_data.append({"Set": set_num, "Team": "Left Grid", "Starters": row_l})
            
            # RIGHT
            row_r = self._extract_row(base_x + offset_x, current_y_pixels, w, h)
            if row_r:
                match_data.append({"Set": set_num, "Team": "Right Grid", "Starters": row_r})
            
        return match_data

    def _extract_row(self, start_x_px, start_y_px, w_px, h_px):
        row_data = []
        pdf_y = self._scale_coords(start_y_px)
        pdf_h = self._scale_coords(h_px)
        
        if pdf_y + pdf_h > self.page0.height: return None # Stop if out of bounds

        for i in range(6):
            x_px = start_x_px + (i * w_px)
            pdf_x = self._scale_coords(x_px)
            pdf_w = self._scale_coords(w_px)
            
            # Top 45% crop
            bbox = (pdf_x + 1, pdf_y + 1, pdf_x + pdf_w - 1, pdf_y + (pdf_h * 0.45))
            
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
        
        # If the row is empty or all ?, return None
        if all(x == "?" for x in row_data):
            return None
            
        return row_data

    def draw_full_grid(self, img, bx, by, w, h, off_x, off_y):
        draw = ImageDraw.Draw(img)
        # Draw 4 sets (Set 5 layout is often different)
        for s in range(4):
            cur_y = by + (s * off_y)
            
            # Left Team (Red)
            for i in range(6):
                draw.rectangle([bx + (i*w), cur_y, bx + (i*w) + w, cur_y + h], outline="red", width=3)
            
            # Right Team (Blue)
            if off_x > 0:
                cur_x = bx + off_x
                for i in range(6):
                    draw.rectangle([cur_x + (i*w), cur_y, cur_x + (i*w) + w, cur_y + h], outline="blue", width=3)
        return img

def main():
    st.title("🏐 VolleyStats: Visual Calibrator")
    
    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")

    if not uploaded_file:
        st.info("Upload PDF to begin.")
        return

    extractor = VolleySheetExtractor(uploaded_file)

    tab1, tab2, tab3 = st.tabs(["📐 Align Grid", "🔍 X-Ray Inspector", "📥 Extract Data"])

    with tab1:
        st.write("### 1. Match the Red Boxes to Set 1 Starters")
        st.info("If the boxes are too far RIGHT, decrease 'Start X'.")
        c1, c2 = st.columns(2)
        with c1:
            base_x = st.number_input("Start X", value=264, step=2)
            base_y = st.number_input("Start Y", value=186, step=2)
            w = st.number_input("Cell Width", value=50)
            h = st.number_input("Cell Height", value=50)
        with c2:
            offset_x = st.number_input("Right Offset", value=880) 
            offset_y = st.number_input("Down Offset", value=330)

        img = extractor.get_page_image()
        debug_img = extractor.draw_full_grid(img, base_x, base_y, w, h, offset_x, offset_y)
        st.image(debug_img, use_container_width=True)

    with tab2:
        st.write("### 2. Check Specific Cells")
        
        c_set, c_team, c_pos = st.columns(3)
        inspect_set = c_set.number_input("Inspect Set #", 1, 4, 1)
        inspect_team = c_team.selectbox("Inspect Team", ["Left", "Right"])
        inspect_pos = c_pos.selectbox("Inspect Position", ["I", "II", "III", "IV", "V", "VI"])
        
        pos_map = {"I": 0, "II": 1, "III": 2, "IV": 3, "V": 4, "VI": 5}
        
        cell_img, raw_txt = extractor.get_cell_debug(
            base_x, base_y, w, h, offset_x, offset_y, 
            inspect_set, inspect_team, pos_map[inspect_pos]
        )
        
        c_img, c_txt = st.columns(2)
        with c_img:
            st.image(cell_img, width=150, caption=f"Computer View")
        with c_txt:
            st.metric("Detected Number", f"'{raw_txt}'")
            if raw_txt.strip().isdigit():
                st.success("✅ Valid!")
            else:
                st.warning("⚠️ Reading Garbage")

    with tab3:
        if st.button("🚀 Extract All"):
            data = extractor.extract_full_match(base_x, base_y, w, h, offset_x, offset_y)
            if data:
                df = pd.DataFrame(data)
                df['Starters'] = df['Starters'].apply(lambda x: " | ".join(x))
                st.dataframe(df, use_container_width=True)
            else:
                st.error("No valid data found. Check your alignment in Tab 1.")

if __name__ == "__main__":
    main()
