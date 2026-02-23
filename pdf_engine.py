import tabula
import pandas as pd
import numpy as np
import io
import base64
import matplotlib
matplotlib.use('Agg') # OBLIGATOIRE POUR LE WEB (Évite de faire planter le serveur avec des fenêtres graphiques)
import matplotlib.pyplot as plt

# ======================================================================
# CONSTANTES GLOBALES (DU COLLÈGUE)
# ======================================================================
TARGET_ROWS = 12
TARGET_COLS = 6
TARGET_COLS_COUNT = 6

def extract_raw_nom_equipe(pdf_path):
    zone_quart_haut = [0, 0, 210, 600]
    try:
        liste_tables = tabula.read_pdf(pdf_path, pages='all', area=zone_quart_haut, multiple_tables=True, pandas_options={'header': None})
        return liste_tables
    except:
        return None

def process_and_structure_noms_equipes(pdf_path):
    tables = extract_raw_nom_equipe(pdf_path)
    equipe_a = "Équipe A"
    equipe_b = "Équipe B"
    if tables:
        df = tables[0]
        try:
            raw_a = str(df.iloc[4, 1]).replace('\r', ' ').strip()
            raw_b = str(df.iloc[4, 2]).replace('\r', ' ').strip()
            clean_a = raw_a[2:].split("Début")[0].strip() if "Début" in raw_a[2:] else raw_a[2:].strip()
            clean_b = raw_b[2:].split("Début")[0].strip() if "Début" in raw_b[2:] else raw_b[2:].strip()
            equipe_a = clean_a if clean_a else "Équipe A"
            equipe_b = clean_b if clean_b else "Équipe B"
        except:
            pass
    return equipe_a, equipe_b

def analyze_data(pdf_file_path: str):
    COORD_SCORES = [300, 140, 842, 595]
    try:
        tables = tabula.read_pdf(pdf_file_path, pages=1, area=COORD_SCORES, lattice=True, multiple_tables=False, pandas_options={'header': None})
        if tables and not tables[0].empty:
            return tables[0].fillna('').astype(str)
    except:
        pass
    return None

def process_and_structure_scores(raw_df_data: pd.DataFrame):
    if raw_df_data is None: return None
    try:
        scores_gauche = [str(raw_df_data.iloc[28, 3]), str(raw_df_data.iloc[29, 3]), str(raw_df_data.iloc[30, 3]), str(raw_df_data.iloc[31, 3]), str(raw_df_data.iloc[32, 3])]
        scores_droite = [str(raw_df_data.iloc[28, 5]), str(raw_df_data.iloc[29, 4]), str(raw_df_data.iloc[30, 4]), str(raw_df_data.iloc[31, 4]), str(raw_df_data.iloc[32, 4])]
        return pd.DataFrame({'Scores Gauche': scores_gauche, 'Scores Droite': scores_droite}, index=[f'Set {i}' for i in range(1, 6)])
    except:
        return pd.DataFrame()

# Méthodes d'extraction de zones pour les sets 
def extract_raw_set_1_a(pdf): return _extract(pdf, [80, 10, 170, 250])
def extract_raw_set_1_b(pdf): return _extract(pdf, [80, 240, 170, 460])
def extract_raw_set_2_b(pdf): return _extract(pdf, [80, 460, 170, 590])
def extract_raw_set_2_a(pdf): return _extract(pdf, [80, 590, 170, 850])

def _extract(pdf, coords):
    try:
        tables = tabula.read_pdf(pdf, pages=1, area=coords, lattice=True, multiple_tables=False, pandas_options={'header': None})
        return tables[0].fillna('').astype(str) if tables else None
    except:
        return None

def tracer_duel_equipes_web(df_g, df_d, titre, nom_g, nom_d):
    """Génère le graphique et le retourne en Base64 pour l'interface web."""
    if df_g is None or df_d is None or df_g.empty or df_d.empty: return None
    
    fig, ax = plt.subplots(figsize=(22, 10))
    current_score_g, current_score_d = 0, 0
    x_labels, x_colors = [], []
    pos_x = 0
    
    color_g = '#3498db'
    color_d = '#e67e22'

    try:
        val_g_start = str(df_g.iloc[4, 0]).upper().strip()
        ordre_equipes = ['G', 'D'] if val_g_start == 'X' else ['D', 'G']
        
        for ligne_idx in range(4, 12):
            ligne_g = df_g.iloc[ligne_idx, 0:6]
            ligne_d = df_d.iloc[ligne_idx, 0:6]
            
            if ligne_g.apply(lambda x: str(x).upper().strip() in ['NAN', '', 'NONE']).all() and \
               ligne_d.apply(lambda x: str(x).upper().strip() in ['NAN', '', 'NONE']).all():
                continue

            for col_idx in range(6):
                for equipe in ordre_equipes:
                    target_df = df_g if equipe == 'G' else df_d
                    this_color = color_g if equipe == 'G' else color_d
                    
                    joueur_num = str(target_df.iloc[0, col_idx])
                    score_val = target_df.iloc[ligne_idx, col_idx]
                    s_str = str(score_val).upper().strip()

                    x_labels.append(joueur_num)
                    x_colors.append(this_color)

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
            
        ax.set_ylim(0, 35)
        ax.set_yticks(range(0, 36))
        ax.set_xticks(range(len(x_labels)))
        xtick_labels = ax.set_xticklabels(x_labels, fontsize=10, fontweight='bold')
        for i, text_label in enumerate(xtick_labels):
            text_label.set_color(x_colors[i])
        
        custom_lines = [plt.Line2D([0], [0], color=color_g, lw=4), plt.Line2D([0], [0], color=color_d, lw=4)]
        ax.legend(custom_lines, [nom_g, nom_d], loc='upper left', fontsize=12)
        ax.set_title(titre, fontsize=16, fontweight='bold', pad=25)
        plt.subplots_adjust(bottom=0.2)
        
    except Exception as e:
        print(f"Graph generation error: {e}")
        ax.text(0.5, 0.5, f"Erreur de génération : {e}", ha='center', va='center')

    # Conversion en Base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

# ======================================================================
# FONCTION PRINCIPALE APPELÉE PAR LE SERVEUR WEB
# ======================================================================
def process_pdf_for_web(filepath):
    """Exécute l'analyse et retourne un dictionnaire formaté pour le front-end."""
    equipe_a, equipe_b = process_and_structure_noms_equipes(filepath)
    raw_scores = analyze_data(filepath)
    final_scores = process_and_structure_scores(raw_scores)
    
    # Exécution Set 1
    df_1_a = extract_raw_set_1_a(filepath)
    df_1_b = extract_raw_set_1_b(filepath)
    
    # Exécution Set 2
    df_2_b = extract_raw_set_2_b(filepath)
    df_2_a = extract_raw_set_2_a(filepath)
    
    # Génération des images
    graph_set_1 = tracer_duel_equipes_web(df_1_a, df_1_b, f"Duel Set 1 : {equipe_a} vs {equipe_b}", equipe_a, equipe_b)
    graph_set_2 = tracer_duel_equipes_web(df_2_b, df_2_a, f"Duel Set 2 : {equipe_b} vs {equipe_a}", equipe_b, equipe_a)

    return {
        "equipe_a": equipe_a,
        "equipe_b": equipe_b,
        "scores_recap": final_scores.to_dict() if final_scores is not None else "Scores introuvables",
        "graphs": [
            {"set": 1, "image_base64": graph_set_1},
            {"set": 2, "image_base64": graph_set_2}
        ]
    }
