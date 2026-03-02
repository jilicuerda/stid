import matplotlib
matplotlib.use('Agg') # Obligatoire pour le web
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D
import io
import base64

def fig_to_base64(fig):
    """Convertit le graphique en image pour le site web."""
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def generate_duel_graph(points_set, team_home_name, team_away_name, set_num):
    """Recrée le graphique en barres (séquences de points) à partir de la BDD."""
    if not points_set: return None
    
    try:
        fig, ax = plt.subplots(figsize=(15, 6))
        color_h, color_a = '#3498db', '#e67e22'
        
        current_score_h, current_score_a = 0, 0
        x_labels, x_colors = [], []
        pos_x = 0
        
        current_server_team = points_set[0].get('server_team', '')
        current_server_num = points_set[0].get('server_num', '')
        
        sequences = []
        
        for p in points_set:
            s_team = p.get('server_team', '')
            s_num = p.get('server_num', '')
            if s_team != current_server_team or s_num != current_server_num:
                sequences.append({
                    'team': current_server_team, 'server': current_server_num,
                    'score_h': current_score_h, 'score_a': current_score_a
                })
                current_server_team = s_team
                current_server_num = s_num
                
            current_score_h = p.get('score_home', 0)
            current_score_a = p.get('score_away', 0)
            
        sequences.append({
            'team': current_server_team, 'server': current_server_num,
            'score_h': current_score_h, 'score_a': current_score_a
        })

        last_h, last_a = 0, 0
        for seq in sequences:
            is_home = (seq['team'] == team_home_name)
            this_color = color_h if is_home else color_a
            
            x_labels.append(str(seq['server']))
            x_colors.append(this_color)
            
            score_fin = seq['score_h'] if is_home else seq['score_a']
            last_score = last_h if is_home else last_a
            height = score_fin - last_score
            
            if height > 0:
                ax.bar(pos_x, height, bottom=last_score, color=this_color, edgecolor='black', width=0.4)
                
            if is_home: last_h = score_fin
            else: last_a = score_fin
            
            ax.axvline(x=pos_x - 0.5, color='black', linestyle='-', alpha=0.15)
            pos_x += 1

        ax.set_ylim(0, max(current_score_h, current_score_a) + 5)
        ax.set_xticks(range(len(x_labels)))
        xtick_labels = ax.set_xticklabels(x_labels, fontsize=10, fontweight='bold')
        for i, text_label in enumerate(xtick_labels):
            text_label.set_color(x_colors[i])

        custom_lines = [Line2D([0], [0], color=color_h, lw=4), Line2D([0], [0], color=color_a, lw=4)]
        ax.legend(custom_lines, [team_home_name, team_away_name], loc='upper left', fontsize=10)
        ax.set_title(f"Séquences de points - Set {set_num}", fontsize=14, fontweight='bold', pad=15)
        
        return fig_to_base64(fig)
    except Exception as e:
        print(f"Erreur duel_graph : {e}")
        return None

def dessiner_terrain(ax, team_serve_name, pos_serve, team_recv_name, pos_recv, is_home_serving):
    """Dessine un terrain avec les positions"""
    ax.add_patch(patches.Rectangle((0, 0), 18, 9, linewidth=2, edgecolor='black', facecolor='#fafafa'))
    ax.plot([9, 9], [0, 9], color='black', linewidth=3)
    ax.plot([6, 6], [0, 9], color='gray', linestyle='--')
    ax.plot([12, 12], [0, 9], color='gray', linestyle='--')

    coords_left = {4: (3.0, 7.5), 3: (7.5, 7.5), 2: (7.5, 1.5), 5: (3.0, 4.5), 6: (7.5, 4.5), 1: (3.0, 1.5)}
    coords_right = {2: (10.5, 7.5), 3: (10.5, 4.5), 4: (10.5, 1.5), 1: (15.0, 7.5), 6: (15.0, 4.5), 5: (15.0, 1.5)}

    color_serve = '#3498db' if is_home_serving else '#e67e22'
    color_recv = '#e67e22' if is_home_serving else '#3498db'

    # Sécurisation: Si le tableau n'a pas 6 joueurs, on remplit avec des '?'
    pos_serve = pos_serve + ['?'] * (6 - len(pos_serve))
    pos_recv = pos_recv + ['?'] * (6 - len(pos_recv))

    ax.text(19.5, 1.5, str(pos_serve[0]), fontsize=16, weight='bold', color=color_serve, ha='center')
    ax.set_title(f"SERVICE : {team_serve_name} / RÉCEPTION : {team_recv_name}", fontsize=10)

    positions_order = [1, 2, 3, 4, 5, 6]
    
    for i, p_num in enumerate(pos_serve[1:6]): 
        pos = positions_order[i+1]
        c = coords_right[pos]
        ax.text(c[0], c[1], str(p_num), fontsize=14, weight='bold', color=color_serve, ha='center')
        
    for i, p_num in enumerate(pos_recv[:6]):
        pos = positions_order[i]
        c = coords_left[pos]
        ax.text(c[0], c[1], str(p_num), fontsize=14, weight='bold', color=color_recv, ha='center')

    ax.set_xlim(-3, 21); ax.set_ylim(-1, 10); ax.axis('off')

def generate_rotation_graph(points_set, team_home, team_away):
    """Dessine la rotation de départ du set."""
    if not points_set: return None
    
    try:
        first_point = points_set[0]
        # Sécurisation si la rotation est absente de la DB
        rot_home_str = str(first_point.get('rotation_home', '?-?-?-?-?-?'))
        rot_away_str = str(first_point.get('rotation_away', '?-?-?-?-?-?'))
        
        rot_home = rot_home_str.split('-') if '-' in rot_home_str else ['?']*6
        rot_away = rot_away_str.split('-') if '-' in rot_away_str else ['?']*6
        
        fig, ax = plt.subplots(1, 1, figsize=(10, 4))
        
        if first_point.get('server_team') == team_home:
            dessiner_terrain(ax, team_home, rot_home, team_away, rot_away, True)
        else:
            dessiner_terrain(ax, team_away, rot_away, team_home, rot_home, False)
            
        return fig_to_base64(fig)
    except Exception as e:
        print(f"Erreur rotation_graph : {e}")
        return None
