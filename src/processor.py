import pdfplumber
import re
import pandas as pd
import gc

def extract_match_info(file):
    """Extrait les noms des équipes et les scores via Regex."""
    text = ""
    with pdfplumber.open(file) as pdf:
        text = pdf.pages[0].extract_text()
    
    lines = text.split('\n')
    
    # 1. Détection des Noms (Logique 'Début')
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
    home = unique_names[1] if len(unique_names) > 1 else "Home Team"
    away = unique_names[0] if len(unique_names) > 0 else "Away Team"
    
    # 2. Détection des Scores
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
                            s_home = int(left[-2])
                            s_away = int(right[0])
                            if s_home > 0 and s_away > 0:
                                scores.append({"Home": s_home, "Away": s_away})
                        except: pass
    return home, away, scores

def calculate_stats(df, scores):
    """Calcule le Win % par joueur."""
    player_stats = {}
    set_winners = {i+1: ("Home" if s['Home'] > s['Away'] else "Away") for i, s in enumerate(scores)}

    for _, row in df.iterrows():
        team = row['Team']
        set_n = row['Set']
        if set_n in set_winners:
            did_win = (team == set_winners[set_n])
            for player in row['Starters']:
                if player.isdigit():
                    if player not in player_stats:
                        player_stats[player] = {'played': 0, 'won': 0, 'team': team}
                    player_stats[player]['played'] += 1
                    if did_win: player_stats[player]['won'] += 1
    
    stats_list = []
    for p, data in player_stats.items():
        win_pct = (data['won'] / data['played']) * 100 if data['played'] > 0 else 0
        stats_list.append({
            "Player": f"#{p}", "Team": data['team'], 
            "Sets": data['played'], "Win %": round(win_pct, 1)
        })
    
    if not stats_list: return pd.DataFrame()
    return pd.DataFrame(stats_list).sort_values(by=['Team', 'Win %'], ascending=False)

class VolleySheetExtractor:
    def __init__(self, pdf_file):
        self.pdf_file = pdf_file

    def extract_full_match(self, base_x, base_y, w, h, offset_x, offset_y, p_height):
        match_data = []
        with pdfplumber.open(self.pdf_file) as pdf:
            page = pdf.pages[0]
            for set_num in range(1, 6): 
                current_y = base_y + ((set_num - 1) * offset_y)
                # Left
                if current_y + h < p_height:
                    row_l = self._extract_row(page, current_y, base_x, w, h)
                    if row_l: match_data.append({"Set": set_num, "Team": "Home", "Starters": row_l})
                # Right
                if current_y + h < p_height:
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