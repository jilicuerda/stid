import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_cors import CORS
from sqlalchemy import create_engine, text
from werkzeug.security import check_password_hash, generate_password_hash # Ajout de generate_password_hash
from functools import wraps

app = Flask(__name__)
CORS(app)

app.secret_key = os.getenv("SECRET_KEY", "une_cle_secrete_tres_longue_et_aleatoire")

# --- CONFIGURATION BASE DE DONNÉES ---
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres.zuepinzkfajzlhpsmxql:2026%2FSTIDVOLL@aws-1-eu-central-1.pooler.supabase.com:6543/postgres")
engine = create_engine(DB_URL)

# --- DÉCORATEURS DE SÉCURITÉ ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'superadmin':
            return "Accès refusé. Privilèges Super Admin requis.", 403
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES D'AUTHENTIFICATION ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, username, password_hash, club_id, role 
                FROM users WHERE username = :u
            """), {"u": username})
            user = result.fetchone()
            
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['club_id'] = user[3]
                session['role'] = user[4]
                
                # Redirection intelligente selon le rôle
                if session['role'] == 'superadmin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('index'))
            else:
                return render_template('login.html', error="Identifiants invalides")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ROUTES DE L'APPLICATION (MATCH) ---
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/api/save_match', methods=['POST'])
@login_required
def save_match():
    data = request.json
    club_id = session.get('club_id')
    
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            
            # 1. Match
            result = conn.execute(text("""
                INSERT INTO matches (club_id, team_home, team_away, sets_home, sets_away, winner)
                VALUES (:cid, :h, :a, :sh, :sa, :w)
                RETURNING id
            """), {
                "cid": club_id,
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
            return jsonify({"status": "success", "message": "Match sauvegardé pour votre club !"})
            
    except Exception as e:
        print(f"Erreur SQL : {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- ROUTES D'ADMINISTRATION ---
@app.route('/admin')
@superadmin_required
def admin_dashboard():
    with engine.connect() as conn:
        # Récupérer tous les clubs
        clubs = conn.execute(text("SELECT id, name FROM clubs ORDER BY id")).fetchall()
        
        # Récupérer tous les utilisateurs avec le nom de leur club
        users = conn.execute(text("""
            SELECT u.id, u.username, u.role, c.name as club_name 
            FROM users u 
            LEFT JOIN clubs c ON u.club_id = c.id 
            ORDER BY u.id
        """)).fetchall()
        
    return render_template('admin.html', clubs=clubs, users=users)

@app.route('/admin/add_club', methods=['POST'])
@superadmin_required
def add_club():
    name = request.form.get('name')
    if name:
        try:
            with engine.connect() as conn:
                trans = conn.begin()
                conn.execute(text("INSERT INTO clubs (name) VALUES (:n)"), {"n": name})
                trans.commit()
                flash("Le club a été ajouté avec succès.", "success")
        except Exception as e:
            flash("Erreur : Ce club existe peut-être déjà.", "error")
            print(e)
            
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_user', methods=['POST'])
@superadmin_required
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')
    club_id = request.form.get('club_id')
    
    if username and password and role and club_id:
        try:
            hashed_pw = generate_password_hash(password)
            with engine.connect() as conn:
                trans = conn.begin()
                conn.execute(text("""
                    INSERT INTO users (username, password_hash, role, club_id) 
                    VALUES (:u, :p, :r, :c)
                """), {"u": username, "p": hashed_pw, "r": role, "c": club_id})
                trans.commit()
                flash("L'utilisateur a été créé avec succès.", "success")
        except Exception as e:
            flash("Erreur : Ce nom d'utilisateur est peut-être déjà pris.", "error")
            print(e)
            
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
