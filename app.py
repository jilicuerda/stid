from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import re

app = Flask(__name__, template_folder='templates')
CORS(app)  # Permet au JS de communiquer avec Python

# ==========================================
# LOGIQUE DE PARSING (Le "Cerveau")
# ==========================================

class VolleyballSheetParser:
    def __init__(self, all_items):
        self.all_items = all_items
        self.metadata = self.parse_match_summary()

    def parse(self):
        anchors = []
        for item in self.all_items:
            if "Début" in item['text']:
                match = re.search(r'(\d{2}[:h]\d{2})', item['text'])
                if match:
                    anchors.append({'x': item['x'], 'y': item['y'], 'start': match.group(1)})
        
        # Tri Haut vers Bas
        anchors.sort(key=lambda k: -k['y']) 

        sets_data = []
        for i, anchor in enumerate(anchors):
            sets_data.append(self.extract_set_data(anchor, i + 1))
        return sets_data

    def extract_set_data(self, anchor, set_num):
        # Géométrie adaptée au PDF
        box_top = anchor['y'] + 60
        box_bottom = anchor['y'] - 380
        
        if anchor['x'] < 300: 
            home_box = {'min': 0, 'max': anchor['x'] - 5}
            away_box = {'min': anchor['x'] + 10, 'max': anchor['x'] + 500}
        else: 
            home_box = {'min': 300, 'max': anchor['x'] - 5}
            away_box = {'min': anchor['x'] + 10, 'max': anchor['x'] + 500}

        # Filtrage Spatial
        set_items = [i for i in self.all_items if box_bottom < i['y'] < box_top]
        home_items = [i for i in set_items if home_box['min'] < i['x'] < home_box['max']]
        away_items = [i for i in set_items if away_box['min'] < i['x'] < away_box['max']]

        home_lines = self.items_to_lines(home_items)
        away_lines = self.items_to_lines(away_items)

        # Extraction Données
        home_data = {
            "starters": self.extract_starters_strict(home_lines, home_items),
            "rotations": self.extract_rotations_spatial(home_lines)
        }
        away_data = {
            "starters": self.extract_starters_strict(away_lines, away_items),
            "rotations": self.extract_rotations_spatial(away_lines)
        }

        # Logique de Score (Priorité au Metadata)
        final_score = "0-0"
        if set_num <= len(self.metadata['setScores']):
            final_score = self.metadata['setScores'][set_num - 1]
        
        # Fallback Score
        if final_score == "0-0":
            h_max = self.get_max_score(home_data['rotations'])
            a_max = self.get_max_score(away_data['rotations'])
            if h_max + a_max > 10: final_score = f"{h_max}-{a_max}"

        return {
            "setNumber": set_num,
            "score": final_score,
            "home": {
                "name": "Home",
                "starters": home_data['starters'],
                "rotation_scores": home_data['rotations']
            },
            "away": {
                "name": "Away",
                "starters": away_data['starters'],
                "rotation_scores": away_data['rotations']
            }
        }

    # --- EXTRACTEURS ---
    def extract_starters_strict(self, lines, raw_items):
        all_flat = [x for line in lines for x in line]
        header_y = None
        
        for item in all_flat:
            if re.match(r'^(I|II|III|IV|V|VI)$', item['text'].strip()):
                header_y = item['y']
                break
        
        if header_y is None:
            for item in all_flat:
                if "Formation" in item['text']: header_y = item['y'] - 15; break
        
        if header_y is None:
            # Fallback aveugle pour Set 5
            y_groups = {}
            for i in raw_items:
                if i['text'].isdigit():
                    y = round(i['y'] / 5) * 5
                    if y not in y_groups: y_groups[y] = []
                    y_groups[y].append(i)
            
            sorted_ys = sorted(y_groups.keys(), reverse=True)
            for y in sorted_ys:
                if 5 <= len(y_groups[y]) <= 7:
                    row = sorted(y_groups[y], key=lambda x: x['x'])
                    return [int(x['text']) for x in row[:6]]
            return []

        y_min, y_max = header_y - 40, header_y - 5
        candidates = [x for x in all_flat if y_min < x['y'] < y_max and x['text'].isdigit()]
        candidates.sort(key=lambda k: k['x'])
        return [int(c['text']) for c in candidates][:6]

    def extract_rotations_spatial(self, lines):
        rotations = {}
        for line in lines:
            line.sort(key=lambda k: k['x'])
            rot_idx = None
            points = []
            for item in line:
                txt = item['text'].strip()
                if rot_idx is None and re.match(r'^[1-6]$', txt): rot_idx = txt
                elif rot_idx and txt.isdigit() and int(txt) <= 40: points.append(int(txt))
            
            if rot_idx and points:
                clean = []
                mx = -1
                for p in points:
                    if p > mx: clean.append(p); mx = p
                rotations[rot_idx] = clean
        return rotations

    def parse_match_summary(self):
        meta = {"winner": "Inconnu", "match_score": "0/0", "setScores": []}
        full_text = " ".join([i['text'] for i in self.all_items])
        
        winner_match = re.search(r'Vainqueur[:\s]+(.*?)\s+(\d\s?/\s?\d)', full_text)
        if winner_match:
            meta['winner'] = winner_match.group(1).strip()
            meta['match_score'] = winner_match.group(2).replace(" ", "")

        footer_items = [i for i in self.all_items if i['y'] < 200 and i['x'] < 600]
        lines = self.items_to_lines(footer_items)
        
        for line in lines:
            line.sort(key=lambda k: k['x'])
            nums = [int(x['text']) for x in line if x['text'].isdigit() and int(x['text']) <= 40]
            
            if len(nums) >= 2:
                s1, s2 = nums[0], nums[-1]
                if s1 >= 10 or s2 >= 10: meta['setScores'].append(f"{s1}-{s2}")
        return meta

    def items_to_lines(self, items):
        if not items: return []
        items.sort(key=lambda k: (-k['y'], k['x']))
        lines = []
        current = []
        last_y = items[0]['y']
        for item in items:
            if abs(item['y'] - last_y) > 5:
                lines.append(current)
                current = []
                last_y = item['y']
            current.append(item)
        if current: lines.append(current)
        return lines

    def get_max_score(self, rotations):
        mx = 0
        for v in rotations.values():
            if v: mx = max(mx, max(v))
        return mx

# ==========================================
# ROUTES DU SERVEUR
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/structure_data', methods=['POST'])
def structure_data():
    """Reçoit le JSON brut du JS, le nettoie via Python, et renvoie le résultat"""
    raw_json = request.json
    
    # Aplatir les pages (le JS envoie {pages: [{items: []}]})
    all_items = []
    for page in raw_json.get('pages', []):
        all_items.extend(page.get('items', []))
        
    # Lancer le Parseur Python
    parser = VolleyballSheetParser(all_items)
    sets_data = parser.parse()
    metadata = parser.metadata
    
    return jsonify({
        "metadata": metadata,
        "sets": sets_data
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
