import streamlit as st
import pdfplumber
import pandas as pd
import io
from PIL import Image, ImageDraw

# --- CONFIGURATION ---
st.set_page_config(page_title="VolleyStats Pro", page_icon="🏐", layout="wide")

# --- CLASS: THE GRID EXTRACTOR ---
class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf = pdfplumber.open(pdf_file)
        self.page0 = self.pdf.pages[0]

    def get_page_image(self):
        """Converts PDF page to image for visualization."""
        return self.page0.to_image(resolution=150).original

    def extract_grid_data(self, anchor_x, anchor_y, cell_w, cell_h):
        """
        Extracts data starting from the anchor point (Top-Left of Zone I).
        We assume standard FFVolley spacing.
        """
        data = {}
        
        # 1. Extract Starters (Row 1)
        # Zones: I, II, III, IV, V, VI
        starters = []
        for i in range(6):
            # Calculate box for each zone
            x0 = anchor_x + (i * cell_w)
            y0 = anchor_y
            x1 = x0 + cell_w
            y1 = y0 + cell_h
            
            # Crop and Extract
            crop = self.page0.crop((x0, y0, x1, y1))
            text = crop.extract_text()
            val = text.strip() if text else "?"
            starters.append(val)
        
        data['Starters'] = starters

        # 2. Extract Substitutes (Row 2 - roughly 20px below starters)
        # Note: In your image, subs are directly below starters
        subs = []
        sub_offset_y = cell_h  # The row immediately below
        
        for i in range(6):
            x0 = anchor_x + (i * cell_w)
            y0 = anchor_y + sub_offset_y
            x1 = x0 + cell_w
            y1 = y0 + sub_offset_y + cell_h
            
            crop = self.page0.crop((x0, y0, x1, y1))
            text = crop.extract_text()
            val = text.strip() if text else ""
            subs.append(val)
            
        data['Subs'] = subs
        
        return data

    def draw_debug_grid(self, img, anchor_x, anchor_y, cell_w, cell_h):
        """Draws the grid on top of the image so user can see alignment."""
        draw = ImageDraw.Draw(img)
        
        # Draw Starters Row (Red)
        for i in range(6):
            x0 = anchor_x + (i * cell_w)
            y0 = anchor_y
            x1 = x0 + cell_w
            y1 = y0 + cell_h
            draw.rectangle([x0, y0, x1, y1], outline="red", width=2)

        # Draw Subs Row (Blue)
        sub_offset_y = cell_h
        for i in range(6):
            x0 = anchor_x + (i * cell_w)
            y0 = anchor_y + sub_offset_y
            x1 = x0 + cell_w
            y1 = y0 + sub_offset_y + cell_h
            draw.rectangle([x0, y0, x1, y1], outline="blue", width=2)
            
        return img

# --- FRONTEND ---
def main():
    st.title("🏐 VolleyStats: Grid Slicer")

    with st.sidebar:
        uploaded_file = st.file_uploader("Upload Score Sheet", type="pdf")
    
    if not uploaded_file:
        st.info("Upload a file to start calibrating.")
        return

    # Initialize Extractor
    extractor = VolleySheetExtractor(uploaded_file)
    
    tab1, tab2 = st.tabs(["📐 Grid Calibrator", "📊 Extracted Data"])

    # --- TAB 1: CALIBRATOR ---
    with tab1:
        st.markdown("### Calibrate Grid Position")
        st.markdown("Adjust these sliders until the **Red Boxes** align perfectly with the **Starting Lineup** numbers.")

        c1, c2 = st.columns(2)
        with c1:
            # Default values are guesses for standard FFVolley A4
            anchor_x = st.slider("X Position (Left-Right)", 0, 600, 75, step=1)
            anchor_y = st.slider("Y Position (Up-Down)", 0, 800, 160, step=1)
        with c2:
            cell_w = st.slider("Cell Width", 10, 50, 22, step=1)
            cell_h = st.slider("Cell Height", 10, 50, 18, step=1)

        # Draw the visual feedback
        base_img = extractor.get_page_image()
        debug_img = extractor.draw_debug_grid(base_img, anchor_x, anchor_y, cell_w, cell_h)
        st.image(debug_img, caption="Red = Starters, Blue = Subs", use_column_width=True)

        # Live Preview of Extraction
        try:
            live_data = extractor.extract_grid_data(anchor_x, anchor_y, cell_w, cell_h)
            st.write("### Live Preview:")
            st.json(live_data)
        except Exception as e:
            st.error(f"Extraction Error: {e}")

    # --- TAB 2: RESULTS ---
    with tab2:
        st.subheader("Final Extracted Roster")
        if 'live_data' in locals():
            df = pd.DataFrame({
                "Position": ["I", "II", "III", "IV", "V", "VI"],
                "Starter": live_data['Starters'],
                "Substitute": live_data['Subs']
            })
            st.table(df)
            
            st.success("✅ Once you have these coordinates, you can hardcode them for all future files!")

if __name__ == "__main__":
    main()
