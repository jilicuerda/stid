import os
import json
import tempfile
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_cors import CORS
from sqlalchemy import create_engine, text
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from pdf_engine import process_pdf_for_web

app = Flask(__name__)
CORS(app)

app.secret_key = os.getenv("SECRET_KEY", "une_cle_secrete_tres_longue_et_aleatoire")
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres.zuepinzkfajzlhpsmxql:2026%2FSTIDVOLL@aws-1-eu-central-1.pooler.supabase.com:6543/postgres")
engine = create_engine(DB_URL)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'superadmin':
            return "Accès refusé.", 403
        return f(*args, **kwargs)
    return decorated_function

# --- AUTHENTIFICATION ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, username, password_hash, club_id, role FROM users WHERE username = :u"), {"u": username})
            user = result.fetchone()
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['club_id'] = user[3]
                session['role'] = user[4]
                if session['role'] == 'superadmin': return redirect(url_for('admin_dashboard'))
                return redirect(url_for('index'))
            else:
                return render_template('login.html', error="Identifiants invalides")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- MATCH EN DIRECT (TABLETTE SAISIE) ---
@app.route('/')
@login_required
def index(): 
    return render_template('index.html')

@app.route('/api/go_live', methods=['POST'])
@login_required
def go_live():
    data = request.json
    club_id = session.get('club_id')
    with engine.connect() as conn:
        trans = conn.begin()
        result = conn.execute(text("""
            INSERT INTO matches (club_id, team_home, team_away, current_set, score_home, score_away, sets_home, sets_away, is_live)
            VALUES (:cid, :th, :ta, :cs, :sh, :sa, :setsh, :setsa, TRUE)
            RETURNING id
        """), {
            "cid": club_id, "th": data['homeName'], "ta": data['awayName'],
            "cs": data['set'], "sh": data['scoreHome'], "sa": data['scoreAway'],
            "setsh": data['setsHome'], "setsa": data['setsAway']
        })
        match_id = result.fetchone()[0]
        trans.commit()
        return jsonify({"status": "success", "match_id": match_id})

@app.route('/api/update_live', methods=['POST'])
@login_required
def update_live():
    data = request.json
    match_id = data.get('match_id')
    if not match_id: return jsonify({"error": "No match ID"}), 400
    with engine.connect() as conn:
        trans = conn.begin()
        conn.execute(text("""
            UPDATE matches 
            SET current_set = :cs, score_home = :sh, score_away = :sa, sets_home = :setsh, sets_away = :setsa
            WHERE id = :mid
        """), {
            "cs": data['set'], "sh": data['scoreHome'], "sa": data['scoreAway'],
            "setsh": data['setsHome'], "setsa": data['setsAway'], "mid": match_id
        })
        trans.commit()
        return jsonify({"status": "success"})

@app.route('/api/save_match', methods=['POST'])
@login_required
def save_match():
    data = request.json
    club_id = session.get('club_id')
    match_id = data.get('match_id') # Peut être null si on a pas cliqué sur Go Live
    
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            
            if match_id:
                # Si le match est déjà en DB (car il était en Live), on le met à jour et on le ferme (is_live = FALSE)
                conn.execute(text("""
                    UPDATE matches SET sets_home=:sh, sets_away=:sa, winner=:w, is_live=FALSE WHERE id=:mid
                """), {"sh": data['setsHome'], "sa": data['setsAway'], "w": data['winner'], "mid": match_id})
                # On nettoie les points précédents pour éviter les doublons lors des clics multiples sur "Sync"
                conn.execute(text("DELETE FROM points WHERE match_id = :mid"), {"mid": match_id})
            else:
                # Si le match n'a pas été mis en Live, on le crée
                result = conn.execute(text("""
                    INSERT INTO matches (club_id, team_home, team_away, sets_home, sets_away, winner)
                    VALUES (:cid, :h, :a, :sh, :sa, :w) RETURNING id
                """), {"cid": club_id, "h": data['homeName'], "a": data['awayName'], "sh": data['setsHome'], "sa": data['setsAway'], "w": data['winner']})
                match_id = result.fetchone()[0]

            # Insertion des points
            if data['history']:
                points_values = []
                for p in data['history']:
                    points_values.append({
                        "mid": match_id, "set": p['set'], "sh": p['score_dom'], "sa": p['score_ext'],
                        "wp": p['winner_team'], "pt": p['point_type'], "act": p['action'], "pnum": str(p['actor_num']),
                        "pteam": p['actor_team'], "snum": str(p['server_num']), "rh": p['rot_home'], "ra": p['rot_away']
                    })
                conn.execute(text("""
                    INSERT INTO points (match_id, set_number, score_home, score_away, winner_point, point_type, action_type, player_num, player_team, server_num, rotation_home, rotation_away)
                    VALUES (:mid, :set, :sh, :sa, :wp, :pt, :act, :pnum, :pteam, :snum, :rh, :ra)
                """), points_values)
            trans.commit()
            return jsonify({"status": "success", "message": "Match sauvegardé !"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# --- ECRAN SPECTATEUR / COACH (NOUVEAU) ---
@app.route('/live')
@login_required
def live_page():
    return render_template('live.html')

@app.route('/api/live_matches')
@login_required
def live_matches_api():
    club_id = session.get('club_id')
    with engine.connect() as conn:
        # Récupère tous les matchs marqués "is_live = TRUE" pour ce club
        matches = conn.execute(text("""
            SELECT id, team_home, team_away, current_set, score_home, score_away, sets_home, sets_away 
            FROM matches WHERE club_id = :cid AND is_live = TRUE
        """), {"cid": club_id}).fetchall()
        
        result = [{"id": m[0], "team_home": m[1], "team_away": m[2], "current_set": m[3], 
                   "score_home": m[4], "score_away": m[5], "sets_home": m[6], "sets_away": m[7]} for m in matches]
    return jsonify(result)

# --- ROUTES EXTRACTION PDF ---
@app.route('/extraction')
@login_required
def extraction_page(): return render_template('extraction.html')

@app.route('/api/upload_pdf', methods=['POST'])
@login_required
def upload_pdf():
    if 'file' not in request.files: return jsonify({"error": "Aucun fichier envoyé"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"error": "Fichier vide"}), 400
    if file and file.filename.endswith('.pdf'):
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)
        try:
            result_data = process_pdf_for_web(temp_path)
            os.remove(temp_path)
            return jsonify({"status": "success", "data": result_data})
        except Exception as e: return jsonify({"error": str(e)}), 500
    return jsonify({"error": "Format invalide."}), 400

@app.route('/api/save_pdf_report', methods=['POST'])
@login_required
def save_pdf_report():
    data = request.json
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            conn.execute(text("INSERT INTO pdf_reports (club_id, team_home, team_away, report_data) VALUES (:cid, :h, :a, :rd)"), 
                         {"cid": session.get('club_id'), "h": data.get('equipe_a', ''), "a": data.get('equipe_b', ''), "rd": json.dumps(data)})
            trans.commit()
            return jsonify({"status": "success", "message": "Sauvegardé !"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

# --- ROUTES ADMINISTRATION ---
@app.route('/admin')
@superadmin_required
def admin_dashboard():
    with engine.connect() as conn:
        clubs = conn.execute(text("SELECT id, name FROM clubs ORDER BY id")).fetchall()
        users = conn.execute(text("SELECT u.id, u.username, u.role, c.name as club_name FROM users u LEFT JOIN clubs c ON u.club_id = c.id ORDER BY u.id")).fetchall()
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
                flash("Club ajouté.", "success")
        except: flash("Erreur: Club existant.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_user', methods=['POST'])
@superadmin_required
def add_user():
    username, password, role, club_id = request.form.get('username'), request.form.get('password'), request.form.get('role'), request.form.get('club_id')
    if username and password and role and club_id:
        try:
            with engine.connect() as conn:
                trans = conn.begin()
                conn.execute(text("INSERT INTO users (username, password_hash, role, club_id) VALUES (:u, :p, :r, :c)"), 
                             {"u": username, "p": generate_password_hash(password), "r": role, "c": club_id})
                trans.commit()
                flash("Utilisateur créé.", "success")
        except: flash("Erreur: Pseudo pris.", "error")
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
