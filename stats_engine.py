import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D
import io
import base64
import math
import gc

# Configuration des actions considérées comme des fautes d'attaque/jeu
FAUTES_ATT_LISTE = ["Attaque Out", "Attaque Filet", "Faute Filet / Arbitre", "Faute (Jeu/Récep)"]

# Traducteur des postes Anglais -> Français
ROLE_FR = {
    "OH": "R4", 
    "MB": "Central", 
    "S": "Passeur", 
    "OPP": "Pointu", 
    "L": "Libéro", 
    "?": "Inconnu"
}

def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=80)
    plt.close(fig)
    plt.close('all')
    gc.collect()
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
        changement_indices = []

        for pt in history_set:
            s_team = pt.get("server_team")
            s_num = str(pt.get("server_num", "?"))
            
            if s_num != c_num or s_team != c_team:
                sequences.append({"team": c_team, "player": c_num, "pts": pts_serie, "start": start_score})
                if (s_team, s_num) in serveurs_vus:
                    serveurs_vus = set()
                    changement_indices.append(len(sequences)) 
                serveurs_vus.add((s_team, s_num))
                start_score = curr_h if s_team == nom_h else curr_a
                c_team, c_num, pts_serie = s_team, s_num, 1 

            if pt.get("winner_team") == s_team:
                pts_serie += 1
            curr_h, curr_a = pt.get("score_dom", 0), pt.get("score_ext", 0)

        sequences.append({"team": c_team, "player": c_num, "pts": pts_serie, "start": start_score})

        fig, ax = plt.subplots(figsize=(20, 7))
        x_pos, max_s = 0, 0
        labels, colors = [], []
        
        for seq in sequences:
            col = color_h if seq["team"] == nom_h else color_a
            ax.bar(x_pos, seq["pts"], bottom=seq["start"], color=col, edgecolor='black', alpha=0.8, width=0.7)
            labels.append(seq["player"])
            colors.append(col)
            max_s = max(max_s, seq["start"] + seq["pts"])
            x_pos += 1

        ax.set_ylim(0, max(25, max_s + 1))
        ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
        
        ax.set_xticks(range(len(labels)))
        xtick_labels = ax.set_xticklabels(labels, fontweight='bold', fontsize=11)
        for i, lbl in enumerate(xtick_labels): lbl.set_color(colors[i])

        lims = [0] + changement_indices + [len(sequences)]
        for i in range(len(lims) - 1):
            debut_idx = lims[i]
            fin_idx = lims[i+1]
            ax.text((debut_idx + fin_idx - 1) / 2, -2, f"Tour {i+1}", ha='center', va='top', fontweight='bold', color='#555')
            if i < len(lims) - 2: ax.axvline(x=fin_idx - 0.5, color='grey', linestyle='--', alpha=0.5)

        ax.legend(handles=[Line2D([0],[0],color=color_h,lw=6,label=nom_h), Line2D([0],[0],color=color_a,lw=6,label=nom_a)], loc='upper left')
        ax.set_title(f"ÉVOLUTION DU SCORE - SET {num_set}", fontsize=14, fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.2)
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.15)
        
        return fig_to_base64(fig)
    except: return None

def dessiner_un_terrain(ax, config_point, stats, couleur, nom_h, nom_a, equipe_au_service):
    ax.add_patch(patches.Rectangle((0, 0), 18, 9, linewidth=2, edgecolor='black', facecolor='#fafafa'))
    ax.plot([9, 9], [0, 9], color='black', linewidth=3)
    coords_g = {'I':(3,1.5), 'VI':(3,4.5), 'V':(3,7.5), 'II':(7.5,1.5), 'III':(7.5,4.5), 'IV':(7.5,7.5)}
    coords_d = {'I':(15,7.5), 'VI':(15,4.5), 'V':(15,1.5), 'II':(10.5,7.5), 'III':(10.5,4.5), 'IV':(10.5,1.5)}
    pos_h, pos_a = extraire_positions(config_point['rot_home']), extraire_positions(config_point['rot_away'])
    
    for p, n in pos_h.items():
        c = 'royalblue' if not (equipe_au_service == nom_h and p == 'I') else 'blue'
        if equipe_au_service == nom_h and p == 'I': ax.text(-1.5, 1.5, str(n), fontsize=18, weight='bold', color=c, ha='center')
        else: ax.text(coords_g[p][0], coords_g[p][1], str(n), fontsize=15, weight='bold', color=c, ha='center', va='center')
    for p, n in pos_a.items():
        c = 'darkorange' if not (equipe_au_service == nom_a and p == 'I') else 'red'
        if equipe_au_service == nom_a and p == 'I': ax.text(19.5, 7.5, str(n), fontsize=18, weight='bold', color=c, ha='center')
        else: ax.text(coords_d[p][0], coords_d[p][1], str(n), fontsize=15, weight='bold', color=c, ha='center', va='center')
    
    diff = stats['m'] - stats['e']
    ax.text(9, -1.5, f"Points gagnés: {stats['m']} | Perdus: {stats['e']}\nBilan: {diff:+d}", fontsize=9, ha='center', weight='bold', bbox=dict(facecolor='white', alpha=0.7, edgecolor=couleur))
    ax.axis('off')

def afficher_grille_rotations(liste_stats, nom_h, nom_a, equipe_service, couleur_theme, titre):
    n_rot = len(liste_stats)
    if n_rot == 0: return None
    try:
        n_rows = math.ceil(n_rot / 3)
        fig, axes = plt.subplots(n_rows, 3, figsize=(18, 4.5 * n_rows), squeeze=False)
        plt.subplots_adjust(hspace=0.5)
        axes_flat = axes.flatten()
        for i, ax in enumerate(axes_flat):
            if i < n_rot: dessiner_un_terrain(ax, liste_stats[i]['point'], liste_stats[i], couleur_theme, nom_h, nom_a, equipe_service)
            else: ax.axis('off')
        fig.suptitle(titre, fontsize=18, fontweight='bold', y=1.02)
        return fig_to_base64(fig)
    except: return None

def tracer_repartition_roles_base64(stats_dict, mapping_roles, nom_equipe):
    try:
        repart = {}
        for num, s in stats_dict.items():
            r_raw = mapping_roles.get(str(num), "?")
            r_fr = ROLE_FR.get(r_raw, r_raw) # Traduction ici
            repart[r_fr] = repart.get(r_fr, 0) + s["Pts"]
        roles = [r for r in repart.keys() if repart[r] > 0]
        if not roles: return None
        
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.pie([repart[r] for r in roles], labels=roles, autopct='%1.1f%%', startangle=140, colors=plt.cm.Paired.colors)
        ax.set_title(f"RÉPARTITION DES POINTS\n{nom_equipe.upper()}", fontweight='bold')
        return fig_to_base64(fig)
    except: return None

def calculer_stats_individuelles(tous_points, roster_home, roster_away, nom_h, nom_a):
    s_h, s_a = {}, {}
    licences_h = {str(p.get('num', '')): p.get('licence', 'N/A') for p in roster_home.get('all', []) if p.get('num')}
    roles_h = {str(p.get('num', '')): p.get('role', '?') for p in roster_home.get('all', []) if p.get('num')}
    roles_a = {str(p.get('num', '')): p.get('role', '?') for p in roster_away.get('all', []) if p.get('num')}
    
    for pt in tous_points:
        act_n, act_s, action, win = pt.get("actor_num"), pt.get("actor_team"), pt.get("action"), pt.get("winner_team")
        srv_n, srv_t = pt.get("server_num"), pt.get("server_team")
        
        if act_n and act_s and act_n != 'None':
            t = s_h if act_s == "home" else s_a
            if act_n not in t: t[act_n] = {"Pts":0, "Ace":0, "Bloc":0, "Att":0, "Feinte":0, "Serv_T":0, "Serv_F":0, "Err_Att":0}
            team_name = nom_h if act_s == "home" else nom_a
            if win == team_name:
                t[act_n]["Pts"] += 1
                if action == "Ace": t[act_n]["Ace"] += 1
                elif action == "Block": t[act_n]["Bloc"] += 1
                elif action == "Attaque": t[act_n]["Att"] += 1
                elif action == "Feinte": t[act_n]["Feinte"] += 1
            elif action in FAUTES_ATT_LISTE:
                t[act_n]["Err_Att"] += 1
                
        if srv_n and srv_t and srv_n != 'None':
            side = "home" if srv_t == nom_h else "away"
            t = s_h if side == "home" else s_a
            if srv_n not in t: t[srv_n] = {"Pts":0, "Ace":0, "Bloc":0, "Att":0, "Feinte":0, "Serv_T":0, "Serv_F":0, "Err_Att":0}
            t[srv_n]["Serv_T"] += 1
            if action in ["Faute Service", "Service Raté"]: t[srv_n]["Serv_F"] += 1

    res_h = []
    for n, s in s_h.items():
        s["num"] = n
        raw_role = roles_h.get(n, "?")
        s["poste"] = ROLE_FR.get(raw_role, raw_role) # Traduction Français
        s["licence"] = licences_h.get(n, "N/A")
        s["ratio_pf"] = round(s["Pts"] / s["Err_Att"], 2) if s["Err_Att"] > 0 else s["Pts"]
        s["srv_pct"] = round((s["Serv_T"] - s["Serv_F"]) / s["Serv_T"] * 100, 1) if s["Serv_T"] > 0 else 0
        res_h.append(s)
        
    res_a = []
    for n, s in s_a.items():
        s["num"] = n
        raw_role = roles_a.get(n, "?")
        s["poste"] = ROLE_FR.get(raw_role, raw_role) # Traduction Français
        s["ratio_pf"] = round(s["Pts"] / s["Err_Att"], 2) if s["Err_Att"] > 0 else s["Pts"]
        s["srv_pct"] = round((s["Serv_T"] - s["Serv_F"]) / s["Serv_T"] * 100, 1) if s["Serv_T"] > 0 else 0
        res_a.append(s)

    pie_h = tracer_repartition_roles_base64(s_h, roles_h, nom_h)
    pie_a = None # Désactivé pour l'adversaire (Demande utilisateur)
    
    return sorted(res_h, key=lambda x: x["Pts"], reverse=True), sorted(res_a, key=lambda x: x["Pts"], reverse=True), pie_h, pie_a

def calculer_efficacite_rotations(tous_points, nom_h, nom_a):
    r_h, r_a = [], []
    for pt in tous_points:
        kh, ka = pt.get('rot_home'), pt.get('rot_away')
        win, srv_t, action = pt.get('winner_team'), pt.get('server_team'), pt.get('action')
        act_s = pt.get('actor_team')
        
        # Home
        trouve = False
        for r in r_h:
            if sont_similaires(r['key'], kh):
                if srv_t == nom_h: 
                    r['ts'] += 1
                    if win == nom_h: r['ms'] += 1
                else:
                    r['tr'] += 1
                    if win == nom_h: r['mr'] += 1
                if act_s == "home" and win != nom_h and action in FAUTES_ATT_LISTE: r['fa'] += 1
                trouve = True; break
        if not trouve:
            is_s = (srv_t == nom_h)
            r_h.append({'key': kh, 'ms': 1 if (is_s and win==nom_h) else 0, 'mr': 1 if (not is_s and win==nom_h) else 0,
                        'ts': 1 if is_s else 0, 'tr': 1 if not is_s else 0, 'fa': 1 if (act_s == "home" and win != nom_h and action in FAUTES_ATT_LISTE) else 0})
            
        # Away
        trouve = False
        for r in r_a:
            if sont_similaires(r['key'], ka):
                if srv_t == nom_a: 
                    r['ts'] += 1
                    if win == nom_a: r['ms'] += 1
                else:
                    r['tr'] += 1
                    if win == nom_a: r['mr'] += 1
                if act_s == "away" and win != nom_a and action in FAUTES_ATT_LISTE: r['fa'] += 1
                trouve = True; break
        if not trouve:
            is_s = (srv_t == nom_a)
            r_a.append({'key': ka, 'ms': 1 if (is_s and win==nom_a) else 0, 'mr': 1 if (not is_s and win==nom_a) else 0,
                        'ts': 1 if is_s else 0, 'tr': 1 if not is_s else 0, 'fa': 1 if (act_s == "away" and win != nom_a and action in FAUTES_ATT_LISTE) else 0})

    for l in [r_h, r_a]:
        for r in l:
            m_tot = r['ms'] + r['mr']
            r['recep_pct'] = round(r['mr'] / r['tr'] * 100, 1) if r['tr'] > 0 else 0
            r['serv_pct'] = round(r['ms'] / r['ts'] * 100, 1) if r['ts'] > 0 else 0
            r['ratio_pf'] = round(m_tot / r['fa'], 2) if r['fa'] > 0 else m_tot
            r['bilan'] = m_tot - ((r['ts'] - r['ms']) + (r['tr'] - r['mr']))

    return sorted(r_h, key=lambda x: x['bilan'], reverse=True), sorted(r_a, key=lambda x: x['bilan'], reverse=True)
