import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_cors import CORS
from sqlalchemy import create_engine, text
from werkzeug.security import check_password_hash # NOUVEAU : Pour vérifier le mot de passe
from functools import wraps # NOUVEAU : Pour protéger les routes

app = Flask(__name__)
CORS(app)

# NOUVEAU : Clé secrète indispensable pour les sessions (cookies de connexion)
app.secret_key = os.getenv("SECRET_KEY", "une_cle_secrete_tres_longue_et_aleatoire")

# --- CONFIGURATION BASE DE DONNÉES ---
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres.zuepinzkfajzlhpsmxql:2026%2FSTIDVOLL@aws-1-eu-central-1.pooler.supabase.com:6543/postgres")
engine = create_engine(DB_URL)

# --- NOUVEAU : DÉCORATEUR DE SÉCURITÉ ---
# Cette fonction servira à protéger les pages
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---

# NOUVEAU : Page de Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        with engine.connect() as conn:
            # On cherche l'utilisateur
            result = conn.execute(text("SELECT id, username, password_hash FROM users WHERE username = :u"), {"u": username})
            user = result.fetchone()
            
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                return redirect(url_for('index'))
            else:
                return render_template('login.html', error="Identifiants invalides")
    
    return render_template('login.html')

# NOUVEAU : Déconnexion
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required # NOUVEAU : Cette ligne protège la page d'accueil !
def index():
    return render_template('index.html')

@app.route('/api/save_match', methods=['POST'])
@login_required # NOUVEAU : On protège aussi l'API
def save_match():
    data = request.json
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            
            # 1. Match
            result = conn.execute(text("""
                INSERT INTO matches (team_home, team_away, sets_home, sets_away, winner)
                VALUES (:h, :a, :sh, :sa, :w)
                RETURNING id
            """), {
                "h": data['homeName'], "a": data['awayName'],
                "sh": data['setsHome'], "sa": data['setsAway'], "w": data['winner']
            })
            match_id = result.fetchone()[0]

            # 2. Points
            if data['history']:
                points_values = []
                for p in data['history']:
                    points_values.append({
                        "mid": match_id, "set": p['set'],
                        "sh": p['score_dom'], "sa": p['score_ext'],
                        "wp": p['winner_team'], "pt": p['point_type'],
                        "act": p['action'], "pnum": str(p['actor_num']),
                        "pteam": p['actor_team'], "snum": str(p['server_num']),
                        "rh": p['rot_home'], "ra": p['rot_away']
                    })
                
                conn.execute(text("""
                    INSERT INTO points 
                    (match_id, set_number, score_home, score_away, winner_point, point_type, action_type, player_num, player_team, server_num, rotation_home, rotation_away)
                    VALUES (:mid, :set, :sh, :sa, :wp, :pt, :act, :pnum, :pteam, :snum, :rh, :ra)
                """), points_values)
            
            trans.commit()
            return jsonify({"status": "success", "message": "Match sauvegardé !"})
            
    except Exception as e:
        print(f"Erreur: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
