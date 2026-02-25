import tabula
import pandas as pd
import numpy as np
import pdfplumber
import re
import io
import base64

import matplotlib
matplotlib.use('Agg') # OBLIGATOIRE POUR LE WEB : Empêche l'ouverture de fenêtres pop-up qui feraient crasher le serveur
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D

# ======================================================================
# CONSTANTES GLOBALES
# ======================================================================
TARGET_ROWS = 12
TARGET_COLS = 6
TARGET_COLS_COUNT = 6

def fig_to_base64(fig):
    """Convertit un graphique matplotlib en image lisible par le web"""
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def extract_raw_nom_equipe(pdf_path):
    zone_quart_haut = [0, 0, 210, 600]
    try:
        return tabula.read_pdf(pdf_path, pages='all', area=zone_quart_haut, multiple_tables=True, pandas_options={'header': None})
    except: return None

def process_and_structure_noms_equipes(pdf_path):
    tables = extract_raw_nom_equipe(pdf_path)
    equipe_a, equipe_b = "Équipe A", "Équipe B"
    if tables:
        df = tables[0]
        try:
            raw_a = str(df.iloc[4, 1]).replace('\r', ' ').strip()
            raw_b = str(df.iloc[4, 2]).replace('\r', ' ').strip()
            clean_a = raw_a[2:].split("Début")[0].strip() if "Début" in raw_a[2:] else raw_a[2:].strip()
            clean_b = raw_b[2:].split("Début")[0].strip() if "Début" in raw_b[2:] else raw_b[2:].strip()
            if clean_a: equipe_a = clean_a
            if clean_b: equipe_b = clean_b
        except: pass
    return equipe_a, equipe_b

def analyze_data(pdf_file_path: str):
    COORD_SCORES = [300, 140, 842, 595]
    try:
        tables = tabula.read_pdf(pdf_file_path, pages=1, area=COORD_SCORES, lattice=True, multiple_tables=False, pandas_options={'header': None})
        if tables and not tables[0].empty: return tables[0].fillna('').astype(str)
    except: pass
    return None

def process_and_structure_scores(raw_df_data: pd.DataFrame):
    if raw_df_data is None: return None
    try:
        scores_gauche = [str(raw_df_data.iloc[28, 3]), str(raw_df_data.iloc[29, 3]), str(raw_df_data.iloc[30, 3]), str(raw_df_data.iloc[31, 3]), str(raw_df_data.iloc[32, 3])]
        scores_droite = [str(raw_df_data.iloc[28, 5]), str(raw_df_data.iloc[29, 4]), str(raw_df_data.iloc[30, 4]), str(raw_df_data.iloc[31, 4]), str(raw_df_data.iloc[32, 4])]
        # Nettoyage des None ou nan
        scores_gauche = [s if s.lower() not in ['nan', 'none'] else '' for s in scores_gauche]
        scores_droite = [s if s.lower() not in ['nan', 'none'] else '' for s in scores_droite]
        return pd.DataFrame({'Scores Gauche': scores_gauche, 'Scores Droite': scores_droite}, index=[f'Set {i}' for i in range(1, 6)])
    except: return pd.DataFrame()

def check_set_exists(df_scores, row_idx):
    try:
        if df_scores is None or row_idx >= len(df_scores): return False
        val = str(df_scores.iloc[row_idx, 0]).upper().strip()
        return val != 'NAN' and val != '' and val != 'NONE'
    except: return False

def extraire_liberos_df(pdf_path):
    motif = re.compile(r'(\d{2})\s+([A-ZÀ-ÿ\s\-]+?)\s+(\d{5,7})')
    liberos_data = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                texte = page.extract_text()
                if texte and "LIBEROS" in texte:
                    apres = texte.split("LIBEROS")[1]
                    zone = apres.split("APPROBATION RESULTATS")[0] if "APPROBATION RESULTATS" in apres else apres
                    matches = motif.findall(zone)
                    for num, identite, licence in matches:
                        liberos_data.append({"Numero": num, "Identite": identite.strip(), "Licence": licence})
        return pd.DataFrame(liberos_data).drop_duplicates(subset=['Licence'])
    except: return pd.DataFrame(columns=["Numero", "Identite", "Licence"])

def extraire_staff_df(pdf_path):
    motif_staff = re.compile(r'(E[ABC])\s+([A-ZÀ-ÿ\s\-]+?)\s+(\d{5,7})')
    staff_data = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                texte = page.extract_text()
                if texte and "APPROBATION RESULTATS" in texte:
                    zone = texte.split("APPROBATION RESULTATS")[1]
                    matches = motif_staff.findall(zone)
                    for code, identite, licence in matches:
                        staff_data.append({"Code": code, "Identite": identite.strip(), "Licence": licence})
        return pd.DataFrame(staff_data).drop_duplicates(subset=['Licence'])
    except: return pd.DataFrame(columns=["Code", "Identite", "Licence"])

# --- FONCTIONS D'EXTRACTION BRUTE PAR SET (Simplifiées pour gain de place, logique conservée) ---
def _extract(pdf, coords):
    try:
        tables = tabula.read_pdf(pdf, pages=1, area=coords, lattice=True, multiple_tables=False, pandas_options={'header': None})
        return tables[0].fillna('').astype(str) if tables else None
    except: return None

def extract_raw_set_1_a(pdf): return _extract(pdf, [80, 10, 170, 250])
def extract_raw_set_1_b(pdf): return _extract(pdf, [80, 240, 170, 460])
def extract_raw_set_2_b(pdf): return _extract(pdf, [80, 460, 170, 590])
def extract_raw_set_2_a(pdf): return _extract(pdf, [80, 590, 170, 850])
def extract_raw_set_3_a(pdf): return _extract(pdf, [170, 10, 260, 250])
def extract_raw_set_3_b(pdf): return _extract(pdf, [170, 240, 260, 470])
def extract_raw_set_4_b(pdf): return _extract(pdf, [170, 400, 260, 590])
def extract_raw_set_4_a(pdf): return _extract(pdf, [170, 580, 260, 860])
def extract_raw_set_5_a(pdf): return _extract(pdf, [280, 0, 360, 200])
def extract_raw_set_5_b(pdf): return _extract(pdf, [280, 140, 360, 480])

# --- TEMPS MORTS ---
def extract_temps_mort_set_1(pdf):
    df = extract_raw_set_1_b(pdf)
    if df is not None and len(df) > 9 and len(df.columns) > 14:
        return (str(df.iloc[8,1]).strip(), str(df.iloc[9,1]).strip(), str(df.iloc[8,14]).strip(), str(df.iloc[9,14]).strip())
    return None, None, None, None

def extract_temps_mort_set_2(pdf):
    df = extract_raw_set_2_a(pdf)
    if df is not None and len(df) > 9 and len(df.columns) > 13:
        return (str(df.iloc[8,0]).strip(), str(df.iloc[9,0]).strip(), str(df.iloc[8,13]).strip(), str(df.iloc[9,13]).strip())
    return None, None, None, None

def extract_temps_mort_set_3(pdf):
    df = extract_raw_set_3_b(pdf)
    if df is not None and len(df) > 9 and len(df.columns) > 14:
        return (str(df.iloc[8,1]).strip(), str(df.iloc[9,0]).strip(), str(df.iloc[8,14]).strip(), str(df.iloc[9,13]).strip())
    return None, None, None, None

def extract_temps_mort_set_4(pdf):
    df = extract_raw_set_4_a(pdf)
    if df is not None and len(df) > 9 and len(df.columns) > 13:
        return (str(df.iloc[8,0]).strip(), str(df.iloc[9,0]).strip(), str(df.iloc[8,13]).strip(), str(df.iloc[9,13]).strip())
    return None, None, None, None

def extract_temps_mort_set_5(pdf):
    df = extract_raw_set_5_b(pdf)
    if df is not None and len(df) > 8 and len(df.columns) > 14:
        # Simplification de la logique de secours pour l'exemple
        a1 = str(df.iloc[7,1]).strip()
        if not a1 or a1=='None': a1 = str(df.iloc[16,12]).strip() if len(df)>16 and len(df.columns)>12 else ''
        a2 = str(df.iloc[8,1]).strip()
        if not a2 or a2=='None': a2 = str(df.iloc[17,12]).strip() if len(df)>17 and len(df.columns)>12 else ''
        return (a1, a2, str(df.iloc[7,14]).strip(), str(df.iloc[8,14]).strip())
    return None, None, None, None

# --- STRUCTURATION DES DONNÉES DE SETS (Logique exacte du collègue) ---
def _structure(raw_df, col_start, even_cols, odd_cols, offset=0):
    new_data = np.full((12, 6), '', dtype=object)
    df = pd.DataFrame(new_data, columns=[f'C{i}' for i in range(6)])
    if raw_df is None or len(raw_df) < 6: return df
    
    # 0-3 (Formation, Subs, Score, Action1)
    for t_row, s_row in enumerate(range(2, 6)):
        if len(raw_df) > s_row:
            data = raw_df.iloc[s_row, col_start:col_start+6].values
            if len(data) == 6: df.iloc[t_row, 0:6] = data
            
    # Rotations (Lignes 4-7)
    for t_row, s_row in enumerate(range(6, 10), start=4):
        cols = even_cols if (s_row-offset) % 2 != 0 else odd_cols
        if len(raw_df) > s_row and len(raw_df.columns) > max(cols):
            data = raw_df.iloc[s_row, cols].values
            if len(data) == 6: df.iloc[t_row, 0:6] = data
            
    # Actions (Lignes 8-11)
    for t_row, s_row in enumerate(range(6, 10), start=8):
        # Inversion par rapport aux rotations
        cols = odd_cols if (s_row-offset) % 2 != 0 else even_cols
        if len(raw_df) > s_row and len(raw_df.columns) > max(cols):
            data = raw_df.iloc[s_row, cols].values
            if len(data) == 6: df.iloc[t_row, 0:6] = data
            
    return df

def process_and_structure_set_1_a(df): return _structure(df, 1, [2,4,6,8,10,12], [3,5,7,9,11,13])
def process_and_structure_set_1_b(df): return _structure(df, 1, [2,4,6,8,10,12], [1,3,5,7,9,11]) # C1-C11
def process_and_structure_set_2_b(df): return _structure(df, 0, [0,2,4,6,8,10], [1,3,5,7,9,11])
def process_and_structure_set_2_a(df): return _structure(df, 1, [2,4,6,8,10,12], [1,3,5,7,9,11])
def process_and_structure_set_3_a(df): return _structure(df, 1, [2,4,6,8,10,12], [3,5,7,9,11,13])
def process_and_structure_set_3_b(df): return _structure(df, 1, [2,4,6,8,10,12], [1,3,5,7,9,11]) # Adapté
def process_and_structure_set_4_b(df): return _structure(df, 1, [2,4,6,8,10,12], [1,3,5,7,9,11])
def process_and_structure_set_4_a(df): return _structure(df, 1, [2,4,6,8,10,12], [1,3,5,7,9,11])
def process_and_structure_set_5_a(df): return _structure(df, 0, [0,2,4,6,8,10], [1,3,5,7,9,11], offset=1) # S_row 5=Rot1
def process_and_structure_set_5_b(df): return _structure(df, 1, [2,4,6,8,10,12], [1,3,5,7,9,11], offset=1)

# --- GRAPHIQUES ---
def tracer_duel_equipes(df_g, df_d, titre, nom_g, nom_d):
    if df_g is None or df_d is None or df_g.empty or df_d.empty: return None
    fig, ax = plt.subplots(figsize=(15, 6)) # Taille adaptée web
    current_score_g, current_score_d = 0, 0
    x_labels, x_colors = [], []
    pos_x = 0
    color_g, color_d = '#3498db', '#e67e22'

    try:
        val_g_start = str(df_g.iloc[4, 0]).upper().strip()
        ordre_equipes = ['G', 'D'] if val_g_start == 'X' else ['D', 'G']
        compteur = 1
        
        for ligne_idx in range(4, 12):
            ligne_g = df_g.iloc[ligne_idx, 0:6]
            ligne_d = df_d.iloc[ligne_idx, 0:6]
            if ligne_g.apply(lambda x: str(x).upper().strip() in ['NAN', '', 'NONE']).all() and \
               ligne_d.apply(lambda x: str(x).upper().strip() in ['NAN', '', 'NONE']).all(): continue
               
            debut_bloc = pos_x
            for col_idx in range(6):
                for equipe in ordre_equipes:
                    target_df = df_g if equipe == 'G' else df_d
                    this_color = color_g if equipe == 'G' else color_d
                    x_labels.append(str(target_df.iloc[0, col_idx]))
                    x_colors.append(this_color)
                    
                    s_str = str(target_df.iloc[ligne_idx, col_idx]).upper().strip()
                    if s_str != 'X' and s_str not in ['NAN', '', 'NONE']:
                        try:
                            score_fin = int(float(s_str))
                            last_score = current_score_g if equipe == 'G' else current_score_d
                            height = score_fin - last_score
                            if height > 0:
                                ax.bar(pos_x, height, bottom=last_score, color=this_color, edgecolor='black', width=0.4)
                            if equipe == 'G': current_score_g = score_fin
                            else: current_score_d = score_fin
                        except: pass
                    pos_x += 1
            ax.axvline(x=pos_x - 0.5, color='black', linestyle='-', alpha=0.15)
            ax.text((debut_bloc + pos_x - 1) / 2, -1, f"Seq {compteur}", ha='center', fontsize=8)
            compteur += 1

        ax.set_ylim(0, 30); ax.set_xticks(range(len(x_labels)))
        xtick_labels = ax.set_xticklabels(x_labels, fontsize=8, rotation=90)
        for i, text_label in enumerate(xtick_labels): text_label.set_color(x_colors[i])
        ax.legend([Line2D([0], [0], color=color_g, lw=4), Line2D([0], [0], color=color_d, lw=4)], [nom_g, nom_d])
        ax.set_title(titre)
    except Exception as e: print(f"Graph error: {e}")
    
    return fig_to_base64(fig)

def preparer_positions(df):
    if df is not None and not df.empty:
        ligne = df.iloc[0].values
        return {'I': ligne[0], 'II': ligne[1], 'III': ligne[2], 'IV': ligne[3], 'V': ligne[4], 'VI': ligne[5]}
    return {}

def dessiner_terrain_phase(ax, nom_a, pos_a, nom_b, pos_b, serveur='B'):
    ax.add_patch(patches.Rectangle((0, 0), 18, 9, linewidth=2, edgecolor='black', facecolor='#fafafa'))
    ax.plot([9, 9], [0, 9], color='black', linewidth=3)
    ax.plot([6, 6], [0, 9], color='gray', linestyle='--')
    ax.plot([12, 12], [0, 9], color='gray', linestyle='--')

    cb = {'IV': (7.5, 7.5), 'III': (7.5, 4.5), 'II': (7.5, 1.5), 'V': (3.0, 7.5), 'VI': (3.0, 4.5), 'I': (3.0, 1.5)}
    ca = {'II': (10.5, 7.5), 'III': (10.5, 4.5), 'IV': (10.5, 1.5), 'I': (15.0, 7.5), 'VI': (15.0, 4.5), 'V': (15.0, 1.5)}

    if serveur == 'B':
        pb, pa = pos_b, {k: v for k, v in pos_a.items() if k != 'I'}
        ax.text(19.5, 1.5, str(pos_a.get('I', '')), fontsize=14, weight='bold', color='salmon', ha='center')
        ax.set_title(f"SERVICE : {nom_b}", fontsize=10)
    else:
        pa, pb = pos_a, {k: v for k, v in pos_b.items() if k != 'I'}
        ax.text(-1.5, 7.5, str(pos_b.get('I', '')), fontsize=14, weight='bold', color='royalblue', ha='center')
        ax.set_title(f"SERVICE : {nom_a}", fontsize=10)

    for p, n in pb.items(): ax.text(cb[p][0], cb[p][1], str(n), fontsize=14, weight='bold', color='royalblue', ha='center')
    for p, n in pa.items(): ax.text(ca[p][0], ca[p][1], str(n), fontsize=14, weight='bold', color='salmon', ha='center')
    ax.set_xlim(-3, 21); ax.set_ylim(-1, 10); ax.axis('off')

def afficher_les_deux_rotations(nom_a, df_a, nom_b, df_b):
    if df_a is None or df_b is None or df_a.empty or df_b.empty: return None
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8))
    dessiner_terrain_phase(ax1, nom_a, preparer_positions(df_a), nom_b, preparer_positions(df_b), serveur='B')
    dessiner_terrain_phase(ax2, nom_a, preparer_positions(df_a), nom_b, preparer_positions(df_b), serveur='A')
    plt.tight_layout()
    return fig_to_base64(fig)

# ======================================================================
# FONCTION PRINCIPALE APPELÉE PAR L'API
# ======================================================================
def process_pdf_for_web(filepath):
    equipe_a, equipe_b = process_and_structure_noms_equipes(filepath)
    scores_df = process_and_structure_scores(analyze_data(filepath))
    
    liberos = extraire_liberos_df(filepath).to_dict('records')
    staff = extraire_staff_df(filepath).to_dict('records')
    
    sets_data = []
    
    # Moteur de génération des sets
    def process_set(set_num, func_raw_a, func_raw_b, func_struct_a, func_struct_b, team_left, team_right, func_tm):
        if check_set_exists(scores_df, set_num - 1):
            df_raw_l = func_raw_a(filepath)
            df_raw_r = func_raw_b(filepath)
            if df_raw_l is not None and df_raw_r is not None:
                df_l = func_struct_a(df_raw_l)
                df_r = func_struct_b(df_raw_r)
                tm = func_tm(filepath)
                
                g_duel = tracer_duel_equipes(df_l, df_r, f"Set {set_num}: {team_left} vs {team_right}", team_left, team_right)
                g_rot = afficher_les_deux_rotations(team_left, df_l, team_right, df_r)
                
                sets_data.append({
                    "set": set_num, "score_a": str(scores_df.iloc[set_num-1, 0]), "score_b": str(scores_df.iloc[set_num-1, 1]),
                    "tm_a": [tm[0], tm[1]], "tm_b": [tm[2], tm[3]],
                    "graph_duel": g_duel, "graph_rot": g_rot
                })

    # Set 1 (A gauche, B droite)
    process_set(1, extract_raw_set_1_a, extract_raw_set_1_b, process_and_structure_set_1_a, process_and_structure_set_1_b, equipe_a, equipe_b, extract_temps_mort_set_1)
    # Set 2 (B gauche, A droite)
    process_set(2, extract_raw_set_2_b, extract_raw_set_2_a, process_and_structure_set_2_b, process_and_structure_set_2_a, equipe_b, equipe_a, extract_temps_mort_set_2)
    # Set 3 (A gauche, B droite)
    process_set(3, extract_raw_set_3_a, extract_raw_set_3_b, process_and_structure_set_3_a, process_and_structure_set_3_b, equipe_a, equipe_b, extract_temps_mort_set_3)
    # Set 4 (B gauche, A droite)
    process_set(4, extract_raw_set_4_b, extract_raw_set_4_a, process_and_structure_set_4_b, process_and_structure_set_4_a, equipe_b, equipe_a, extract_temps_mort_set_4)
    # Set 5 (A gauche, B droite)
    process_set(5, extract_raw_set_5_a, extract_raw_set_5_b, process_and_structure_set_5_a, process_and_structure_set_5_b, equipe_a, equipe_b, extract_temps_mort_set_5)

    # Nettoyage NaN dans le récapitulatif
    scores_recap = []
    if scores_df is not None:
        for idx, row in scores_df.iterrows():
            scores_recap.append({"Set": idx, "Gauche": str(row[0]), "Droite": str(row[1])})

    return {
        "equipe_a": equipe_a, "equipe_b": equipe_b,
        "liberos": liberos, "staff": staff,
        "scores_recap": scores_recap,
        "sets": sets_data
    }
