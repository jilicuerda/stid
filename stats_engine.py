import matplotlib
matplotlib.use('Agg') # Obligatoire pour le web
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D
import io
import base64
import math

# ======================================================================
# 1. FONCTIONS UTILITAIRES
# ======================================================================
def fig_to_base64(fig):
    """Convertit le graphique en image pour le site web."""
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def extraire_positions(rot_str):
    if not rot_str or rot_str == 'None': return {p: '?' for p in ['I', 'II', 'III', 'IV', 'V', 'VI']}
    nums = str(rot_str).split('-')
    while len(nums) < 6: nums.append('?')
    mapping = ['I', 'II', 'III', 'IV', 'V', 'VI']
    return {mapping[i]: nums[i] for i in range(6)}

def sont_similaires(rot1_str, rot2_str, seuil=4):
    if not rot1_str or not rot2_str: return False
    r1, r2 = str(rot1_str).split('-'), str(rot2_str).split('-')
    if len(r1) != 6 or len(r2) != 6: return False
    communs = sum(1 for a, b in zip(r1, r2) if a == b)
    return communs >= seuil

# ======================================================================
# 2. GRAPHIQUES (Code du coéquipier adapté)
# ======================================================================
def tracer_duel_chronologique_annote(history_set, nom_h, nom_a, num_set):
    if not history_set: return None
    
    try:
        color_h, color_a = '#3498db', '#e67e22' 
        sequences, curr_h, curr_a = [], 0, 0
        c_team = history_set[0].get("server_team")
        c_num = str(history_set[0].get("server_num", "?"))
        pts_serie = 1 
        start_score = 0 

        serveurs_vus = set()
        serveurs_vus.add((c_team, c_num))
        changement_sequence_indices = []

        for pt in history_set:
            s_team = pt.get("server_team")
            s_num = str(pt.get("server_num", "?"))
            
            if s_num != c_num or s_team != c_team:
                sequences.append({"team": c_team, "player": c_num, "pts": pts_serie, "start": start_score})
                
                if (s_team, s_num) in serveurs_vus:
                    serveurs_vus = set()
                    changement_sequence_indices.append(len(sequences)) 

                serveurs_vus.add((s_team, s_num))
                start_score = curr_h if s_team == nom_h else curr_a
                c_team, c_num = s_team, s_num
                pts_serie = 1 

            if pt.get("winner_team") == s_team:
                pts_serie += 1
                
            curr_h, curr_a = pt.get("score_dom", 0), pt.get("score_ext", 0)

        sequences.append({"team": c_team, "player": c_num, "pts": pts_serie, "start": start_score})

        fig, ax = plt.subplots(figsize=(20, 8))
        x_pos, max_score = 0, 0
        labels, colors = [], []
        
        for seq in sequences:
            col = color_h if seq["team"] == nom_h else color_a
            ax.bar(x_pos, seq["pts"], bottom=seq["start"], color=col, edgecolor='black', alpha=0.85, width=0.7)
            labels.append(seq["player"])
            colors.append(col)
            max_score = max(max_score, seq["start"] + seq["pts"])
            x_pos += 1

        lim_y = max(25, max_score + 2)
        ax.set_ylim(0, lim_y)
        ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
        ax.set_ylabel("Score Cumulé", fontsize=12, fontweight='bold')
        
        ax.set_xticks(range(len(labels)))
        xtick_labels = ax.set_xticklabels(labels, fontweight='bold', fontsize=11)
        for i, lbl in enumerate(xtick_labels): lbl.set_color(colors[i])

        limites_completes = [0] + changement_sequence_indices + [len(sequences)]
        for i in range(len(limites_completes) - 1):
            debut_idx = limites_completes[i]
            fin_idx = limites_completes[i+1]
            pos_texte_x = (debut_idx + fin_idx - 1) / 2
            
            ax.text(pos_texte_x, -2.5, f"{i+1}ère séquence" if i==0 else f"{i+1}ème séquence", ha='center', va='top', fontsize=10, fontweight='bold', color='#555')
            if i < len(limites_completes) - 2:
                ax.axvline(x=fin_idx - 0.5, color='grey', linestyle='--', linewidth=1, alpha=0.6)

        legend_elements = [Line2D([0], [0], color=color_h, lw=6, label=f" {nom_h} "), Line2D([0], [0], color=color_a, lw=6, label=f" {nom_a} ")]
        ax.legend(handles=legend_elements, loc='upper left', fontsize=11, frameon=True, shadow=True, borderpad=1)

        ax.set_title(f"ÉVOLUTION DU SCORE - SET {num_set}", fontsize=16, fontweight='bold', pad=25)
        ax.grid(axis='y', linestyle='-', alpha=0.2) 
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.15)
        
        return fig_to_base64(fig)
    except Exception as e:
        print(f"Erreur graphe chrono : {e}")
        return None

def dessiner_un_terrain(ax, config_point, stats, couleur, nom_h, nom_a, equipe_au_service):
    ax.add_patch(patches.Rectangle((0, 0), 18, 9, linewidth=2, edgecolor='black', facecolor='#fafafa'))
    ax.plot([9, 9], [0, 9], color='black', linewidth=3)
    coords_g = {'I':(3,1.5), 'VI':(3,4.5), 'V':(3,7.5), 'II':(7.5,1.5), 'III':(7.5,4.5), 'IV':(7.5,7.5)}
    coords_d = {'I':(15,7.5), 'VI':(15,4.5), 'V':(15,1.5), 'II':(10.5,7.5), 'III':(10.5,4.5), 'IV':(10.5,1.5)}
    pos_h, pos_a = extraire_positions(config_point['rot_home']), extraire_positions(config_point['rot_away'])
    
    for p, n in pos_h.items():
        if equipe_au_service == nom_h and p == 'I': ax.text(-1.5, 1.5, str(n), fontsize=18, weight='bold', color='royalblue', ha='center')
        else: ax.text(coords_g[p][0], coords_g[p][1], str(n), fontsize=16, weight='bold', color='royalblue', ha='center', va='center')
    for p, n in pos_a.items():
        if equipe_au_service == nom_a and p == 'I': ax.text(19.5, 7.5, str(n), fontsize=18, weight='bold', color='darkorange', ha='center')
        else: ax.text(coords_d[p][0], coords_d[p][1], str(n), fontsize=16, weight='bold', color='darkorange', ha='center', va='center')

    diff = stats['m'] - stats['e']
    txt = f"pts marqués: {stats['m']} | encaissés: {stats['e']}\ndifférence: {diff:+d}"
    ax.text(9, -2, txt, fontsize=10, ha='center', va='top', weight='bold', bbox=dict(facecolor='white', alpha=0.8, edgecolor=couleur, boxstyle='round'))
    ax.axis('off')

def afficher_grille_rotations(liste_stats, nom_h, nom_a, equipe_service, couleur_theme, titre):
    n_rot = len(liste_stats)
    if n_rot == 0: return None
    try:
        n_cols = 3
        n_rows = math.ceil(n_rot / n_cols)
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 5 * n_rows), squeeze=False)
        plt.subplots_adjust(hspace=0.5)
        axes_flat = axes.flatten()
        for i in range(len(axes_flat)):
            if i < n_rot: dessiner_un_terrain(axes_flat[i], liste_stats[i]['point'], liste_stats[i], couleur_theme, nom_h, nom_a, equipe_service)
            else: axes_flat[i].axis('off')
        
        # Ajout d'un titre global pour la grille
        fig.suptitle(titre, fontsize=18, fontweight='bold', y=1.02)
        return fig_to_base64(fig)
    except Exception as e:
        print(f"Erreur grille rotation : {e}")
        return None

# ======================================================================
# 3. STATISTIQUES GLOBALES (Calcul pur, pas de matplotlib ici)
# ======================================================================
def calculer_stats_individuelles(tous_points, roster_home, roster_away, nom_h, nom_a):
    stats_home = {}
    stats_away = {}
    
    licences_home = {str(p.get('num', '')): p.get('licence', 'N/A') for p in roster_home.get('all', []) if p.get('num')}

    for pt in tous_points:
        actor_num = str(pt.get("actor_num", ""))
        actor_side = pt.get("actor_team")
        action = pt.get("action")
        winner_team = pt.get("winner_team")

        if actor_num and actor_side and actor_num != 'None':
            target_stats = stats_home if actor_side == 'home' else stats_away
            target_team_name = nom_h if actor_side == 'home' else nom_a
            
            if winner_team == target_team_name:
                if actor_num not in target_stats: target_stats[actor_num] = {"num": actor_num, "Pts":0, "Ace":0, "Bloc":0, "Att":0, "Feinte":0, "Serv_T":0, "Serv_F":0}
                s = target_stats[actor_num]
                s["Pts"] += 1
                if action == "Ace": s["Ace"] += 1
                elif action == "Block": s["Bloc"] += 1
                elif action == "Attaque": s["Att"] += 1
                elif action == "Feinte": s["Feinte"] += 1

        serv_num = str(pt.get("server_num", ""))
        serv_team_name = pt.get("server_team")

        if serv_num and serv_team_name and serv_num != 'None':
            is_home = (serv_team_name == nom_h)
            target_stats = stats_home if is_home else stats_away
            
            if serv_num not in target_stats: target_stats[serv_num] = {"num": serv_num, "Pts":0, "Ace":0, "Bloc":0, "Att":0, "Feinte":0, "Serv_T":0, "Serv_F":0}
            
            target_stats[serv_num]["Serv_T"] += 1
            if action == "Faute Service":
                target_stats[serv_num]["Serv_F"] += 1

    # Formatage final
    res_home = list(stats_home.values())
    res_away = list(stats_away.values())
    
    for r in res_home: 
        r["licence"] = licences_home.get(r["num"], "N/A")
        r["ace_pct"] = round((r['Ace']/r['Serv_T']*100), 1) if r["Serv_T"] > 0 else 0
        r["srv_pct"] = round(((r['Serv_T'] - r['Serv_F'])/r['Serv_T']*100), 1) if r["Serv_T"] > 0 else 0
        
    for r in res_away: 
        r["ace_pct"] = round((r['Ace']/r['Serv_T']*100), 1) if r["Serv_T"] > 0 else 0
        r["srv_pct"] = round(((r['Serv_T'] - r['Serv_F'])/r['Serv_T']*100), 1) if r["Serv_T"] > 0 else 0

    return sorted(res_home, key=lambda x: x["Pts"], reverse=True), sorted(res_away, key=lambda x: x["Pts"], reverse=True)

def calculer_efficacite_rotations(tous_points, nom_h, nom_a):
    stats_rot_h, stats_rot_a = [], []

    for pt in tous_points:
        kh, ka = str(pt.get('rot_home', '')), str(pt.get('rot_away', ''))
        win, serv_team = pt.get('winner_team'), pt.get('server_team')

        # Home
        trouve_h = False
        for s in stats_rot_h:
            if sont_similaires(s['key'], kh):
                if win == nom_h:
                    if serv_team == nom_h: s['ms'] += 1 
                    else: s['mr'] += 1                  
                else:
                    if serv_team == nom_h: s['es'] += 1 
                    else: s['er'] += 1                  
                trouve_h = True; break
        if not trouve_h:
            new_rot = {'key': kh, 'ms': 0, 'mr': 0, 'es': 0, 'er': 0}
            if win == nom_h:
                if serv_team == nom_h: new_rot['ms'] = 1
                else: new_rot['mr'] = 1
            else:
                if serv_team == nom_h: new_rot['es'] = 1
                else: new_rot['er'] = 1
            stats_rot_h.append(new_rot)

        # Away
        trouve_a = False
        for s in stats_rot_a:
            if sont_similaires(s['key'], ka):
                if win == nom_a:
                    if serv_team == nom_a: s['ms'] += 1
                    else: s['mr'] += 1
                else:
                    if serv_team == nom_a: s['es'] += 1
                    else: s['er'] += 1
                trouve_a = True; break
        if not trouve_a:
            new_rot = {'key': ka, 'ms': 0, 'mr': 0, 'es': 0, 'er': 0}
            if win == nom_a:
                if serv_team == nom_a: new_rot['ms'] = 1
                else: new_rot['mr'] = 1
            else:
                if serv_team == nom_a: new_rot['es'] = 1
                else: new_rot['er'] = 1
            stats_rot_a.append(new_rot)

    # Ajout du total pour affichage
    for s in stats_rot_h: s['diff'] = (s['ms'] + s['mr']) - (s['es'] + s['er'])
    for s in stats_rot_a: s['diff'] = (s['ms'] + s['mr']) - (s['es'] + s['er'])

    return sorted(stats_rot_h, key=lambda x: x['diff'], reverse=True), sorted(stats_rot_a, key=lambda x: x['diff'], reverse=True)
