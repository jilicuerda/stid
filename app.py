import os
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text

app = Flask(__name__)

# --- CONFIGURATION BASE DE DONNÉES (CLOUD & LOCAL) ---
# Le serveur cherche la variable 'DATABASE_URL'.
# Si elle n'existe pas, il utilise votre lien Supabase (le pooler aws-1).
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres.zuepinzkfajzlhpsmxql:2026%2FSTIDVOLL@aws-1-eu-central-1.pooler.supabase.com:6543/postgres")

# Création du moteur de base de données
engine = create_engine(DB_URL)

# --- ROUTES (LES PAGES DU SITE) ---

@app.route('/')
def index():
    """Affiche la page principale (le fichier index.html dans le dossier templates)"""
    return render_template('index.html')

@app.route('/api/save_match', methods=['POST'])
def save_match():
    """Reçoit les données du match et les sauvegarde dans Supabase"""
    data = request.json
    try:
        with engine.connect() as conn:
            # 1. Insérer le Match global
            trans = conn.begin()
            
            result = conn.execute(text("""
                INSERT INTO matches (team_home, team_away, sets_home, sets_away, winner)
                VALUES (:h, :a, :sh, :sa, :w)
                RETURNING id
            """), {
                "h": data['homeName'], 
                "a": data['awayName'],
                "sh": data['setsHome'], 
                "sa": data['setsAway'],
                "w": data['winner']
            })
            
            match_id = result.fetchone()[0]

            # 2. Insérer tous les Points (Historique complet)
            if data['history']:
                points_values = []
                for p in data['history']:
                    points_values.append({
                        "mid": match_id,
                        "set": p['set'],
                        "sh": p['score_dom'], "sa": p['score_ext'],
                        "wp": p['winner_team'],
                        "pt": p['point_type'],
                        "act": p['action'],
                        "pnum": str(p['actor_num']),
                        "pteam": p['actor_team'],
                        "snum": str(p['server_num']),
                        "rh": p['rot_home'], "ra": p['rot_away']
                    })
                
                conn.execute(text("""
                    INSERT INTO points 
                    (match_id, set_number, score_home, score_away, winner_point, point_type, action_type, player_num, player_team, server_num, rotation_home, rotation_away)
                    VALUES (:mid, :set, :sh, :sa, :wp, :pt, :act, :pnum, :pteam, :snum, :rh, :ra)
                """), points_values)
            
            trans.commit()
            return jsonify({"status": "success", "message": "Match sauvegardé dans Supabase !"})
            
    except Exception as e:
        print(f"Erreur SQL : {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Configuration pour Render (utilise le port défini par le cloud)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
