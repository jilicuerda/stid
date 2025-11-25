import pdfplumber
import pypdfium2 as pdfium
import re
import gc
import streamlit as st

# --- CHARGEMENT IMAGE (CACHE) ---
@st.cache_data(show_spinner=False)
def get_page_image(file_bytes):
    """Convertit le PDF en Image (Haute performance)."""
    pdf = pdfium.PdfDocument(file_bytes)
    page = pdf[0]
    scale = 1.0 # 72 DPI
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()
    page.close()
    pdf.close()
    gc.collect()
    return pil_image, scale

def extract_match_info(file):
    """Extrait les Noms d'équipes et les Scores du texte."""
    text = ""
    with pdfplumber.open(file) as pdf:
        text = pdf.pages[0].extract_text()
    
    lines = text.split('\n')
    
    # 1. Noms des équipes
    potential_names = []
    for line in lines:
        if "Début:" in line:
            parts = line.split("Début:")
            for part in parts[:-1]:
                if "Fin:" in part: part = part.split("Fin:")[-1]
                part = re.sub(r'\d{2}:\d{2}\s*R?', '', part)
                clean_name = re.sub(r'\b(SA|SB|S|R)\b', '', part)
                clean_name = re.sub(r'^[^A-Z]+|[^A-Z]+$', '', clean_name).strip()
                if len(clean_name) > 3: potential_names.append(clean_name)

    unique_names = list(dict.fromkeys(potential_names))
    t_home = unique_names[1] if len(unique_names) > 1 else "Home Team"
    t_away = unique_names[0] if len(unique_names) > 0 else "Away Team"
    
    # 2. Scores
    scores = []
    duration_pattern = re.compile(r"(\d{1,3})\s*['’′`]")
    found_table = False
    
    for line in lines:
        if "RESULTATS" in line: found_table = True
        if "Vainqueur" in line: found_table = False
        
        if found_table:
            match = duration_pattern.search(line)
            if match and int(match.group(1)) < 60:
                parts = line.split(match.group(0))
                if len(parts) >= 2:
                    left = re.findall(r'\d+', parts[0])
                    right = re.findall(r'\d+', parts[1])
                    if len(left) >= 2 and len(right) >= 1:
                        try:
                            scores.append({"Home": int(left[-2]), "Away": int(right[0])})
                        except: pass
    return t_home, t_away, scores

class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf_file = pdf_file

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y, p_height):
        match_data = []
        with pdfplumber.open(self.pdf_file) as pdf:
            page = pdf.pages[0]
            for set_num in range(1, 6): 
                current_y = base_y + ((set_num - 1) * offset_y)
                
                if current_y + h < p_height:
                    # Left
                    row_l = self._extract_row(page, current_y, base_x, w, h)
                    if row_l: match_data.append({"Set": set_num, "Team": "Home", "Starters": row_l})
                    # Right
                    row_r = self._extract_row(page, current_y, base_x + offset_x, w, h)
                    if row_r: match_data.append({"Set": set_num, "Team": "Away", "Starters": row_r})
        gc.collect()
        return match_data

    def _extract_row(self, page, top_y, start_x, w, h):
        row_data = []
        for i in range(6):
            drift = i * 0.3
            px_x = start_x + (i * w) + drift
            bbox = (px_x - 3, top_y, px_x + w + 3, top_y + (h * 0.8))
            try:
                text = page.crop(bbox).extract_text()
                val = "?"
                if text:
                    for token in text.split():
                        clean = re.sub(r'[^0-9]', '', token)
                        if clean.isdigit() and len(clean) <= 2:
                            val = clean; break
                row_data.append(val)
            except: row_data.append("?")
        if all(x == "?" for x in row_data): return None
        return row_data