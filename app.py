import os
import json
import tempfile
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_cors import CORS
from sqlalchemy import create_engine, text
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

# Imports des moteurs
from pdf_engine import process_pdf_for_web
from stats_engine import tracer_duel_chronologique_annote, afficher_grille_rotations, sont_similaires, calculer_stats_individuelles, calculer_efficacite_rotations

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

@app.route('/')
@login_required
def index(): 
    return render_template('index.html')

@app.route('/api/my_teams', methods=['GET'])
@login_required
def get_my_teams():
    try:
        with engine.connect() as conn:
            teams = conn.execute(text("SELECT id, name FROM teams WHERE club_id = :cid ORDER BY name"), {"cid": session.get('club_id')}).fetchall()
            return jsonify([{"id": t[0], "name": t[1]} for t in teams])
    except Exception as e: return jsonify([])

@app.route('/api/last_roster/<int:team_id>', methods=['GET'])
@login_required
def get_last_roster(team_id):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT roster_home, team_home FROM matches 
                WHERE team_id = :tid AND roster_home IS NOT NULL 
                ORDER BY created_at DESC LIMIT 1
            """), {"tid": team_id}).fetchone()
            if result and result[0]:
                roster_data = result[0]
                if isinstance(roster_data, str): roster_data = json.loads(roster_data)
                return jsonify({"status": "success", "roster": roster_data, "last_team_name": result[1]})
            return jsonify({"status": "empty"})
    except Exception as e: return jsonify({"status": "error", "message": "Erreur BDD"}), 200

@app.route('/api/go_live', methods=['POST'])
@login_required
def go_live():
    data = request.json
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            result = conn.execute(text("""
                INSERT INTO matches (club_id, team_id, team_home, team_away, current_set, score_home, score_away, sets_home, sets_away, is_live, roster_home, roster_away)
                VALUES (:cid, :tid, :th, :ta, :cs, :sh, :sa, :setsh, :setsa, TRUE, :rh, :ra) RETURNING id
            """), {
                "cid": session.get('club_id'), "tid": data.get('teamId'), "th": data.get('homeName'), "ta": data.get('awayName'),
                "cs": data.get('set', 1), "sh": data.get('scoreHome', 0), "sa": data.get('scoreAway', 0), "setsh": data.get('setsHome', 0), "setsa": data.get('setsAway', 0),
                "rh": json.dumps(data.get('rosterHome', {})), "ra": json.dumps(data.get('rosterAway', {}))
            })
            match_id = result.fetchone()[0]
            trans.commit()
            return jsonify({"status": "success", "match_id": match_id})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 200

@app.route('/api/update_live', methods=['POST'])
@login_required
def update_live():
    data = request.json
    if not data.get('match_id'): return jsonify({"error": "No match ID"}), 400
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            conn.execute(text("UPDATE matches SET current_set=:cs, score_home=:sh, score_away=:sa, sets_home=:setsh, sets_away=:setsa WHERE id=:mid"), 
                         {"cs": data.get('set', 1), "sh": data.get('scoreHome', 0), "sa": data.get('scoreAway', 0), "setsh": data.get('setsHome', 0), "setsa": data.get('setsAway', 0), "mid": data['match_id']})
            trans.commit()
            return jsonify({"status": "success"})
    except Exception: return jsonify({"status": "error"}), 200

@app.route('/api/save_match', methods=['POST'])
@login_required
def save_match():
    data = request.json
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            match_id = data.get('match_id')
            if match_id:
                conn.execute(text("UPDATE matches SET sets_home=:sh, sets_away=:sa, winner=:w, is_live=FALSE, roster_home=:rh, roster_away=:ra WHERE id=:mid"), 
                             {"sh": data.get('setsHome', 0), "sa": data.get('setsAway', 0), "w": data.get('winner', ''), "rh": json.dumps(data.get('rosterHome', {})), "ra": json.dumps(data.get('rosterAway', {})), "mid": match_id})
                conn.execute(text("DELETE FROM points WHERE match_id = :mid"), {"mid": match_id})
            else:
                result = conn.execute(text("INSERT INTO matches (club_id, team_id, team_home, team_away, sets_home, sets_away, winner, roster_home, roster_away) VALUES (:cid, :tid, :h, :a, :sh, :sa, :w, :rh, :ra) RETURNING id"), 
                                      {"cid": session.get('club_id'), "tid": data.get('teamId'), "h": data.get('homeName'), "a": data.get('awayName'), "sh": data.get('setsHome', 0), "sa": data.get('setsAway', 0), "w": data.get('winner', ''), "rh": json.dumps(data.get('rosterHome', {})), "ra": json.dumps(data.get('rosterAway', {}))})
                match_id = result.fetchone()[0]

            if data.get('history'):
                pts = [{
                    "mid": match_id, "set": p.get('set', 1), "sh": p.get('score_dom', 0), "sa": p.get('score_ext', 0), 
                    "wp": p.get('winner_team', ''), "pt": p.get('point_type', ''), "act": p.get('action', ''), 
                    "pnum": str(p.get('actor_num', '')), "pteam": p.get('actor_team', ''), 
                    "snum": str(p.get('server_num', '')), "steam": p.get('server_team', ''), # <-- AJOUTÉ ICI !
                    "rh": p.get('rot_home', ''), "ra": p.get('rot_away', ''), "alicence": p.get('actor_licence', ''), 
                    "slicence": p.get('server_licence', ''), "rhl": p.get('rot_home_licences', ''), "ral": p.get('rot_away_licences', '')
                } for p in data['history']]
                
                conn.execute(text("""
                    INSERT INTO points (
                        match_id, set_number, score_home, score_away, winner_point, point_type, 
                        action_type, player_num, player_team, server_num, server_team, 
                        rotation_home, rotation_away, player_licence, server_licence, 
                        rotation_home_licences, rotation_away_licences
                    ) VALUES (
                        :mid, :set, :sh, :sa, :wp, :pt, 
                        :act, :pnum, :pteam, :snum, :steam, 
                        :rh, :ra, :alicence, :slicence, 
                        :rhl, :ral
                    )
                """), pts)
            
            trans.commit()
            return jsonify({"status": "success", "message": "Match sauvegardé !"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 200

@app.route('/live')
@login_required
def live_page(): return render_template('live.html')

@app.route('/api/live_matches')
@login_required
def live_matches_api():
    try:
        with engine.connect() as conn:
            matches = conn.execute(text("SELECT id, team_home, team_away, current_set, score_home, score_away, sets_home, sets_away FROM matches WHERE club_id = :cid AND is_live = TRUE"), {"cid": session.get('club_id')}).fetchall()
            return jsonify([{"id": m[0], "team_home": m[1], "team_away": m[2], "current_set": m[3], "score_home": m[4], "score_away": m[5], "sets_home": m[6], "sets_away": m[7]} for m in matches])
    except Exception: return jsonify([])

@app.route('/extraction')
@login_required
def extraction_page(): return render_template('extraction.html')

@app.route('/api/upload_pdf', methods=['POST'])
@login_required
def upload_pdf():
    if 'file' not in request.files: return jsonify({"error": "Aucun fichier"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"error": "Fichier vide"}), 400
    if file and file.filename.endswith('.pdf'):
        t_path = os.path.join(tempfile.gettempdir(), file.filename)
        file.save(t_path)
        try:
            res = process_pdf_for_web(t_path)
            os.remove(t_path)
            return jsonify({"status": "success", "data": res})
        except Exception as e: return jsonify({"error": str(e)}), 500
    return jsonify({"error": "Format invalide."}), 400

@app.route('/api/save_pdf_report', methods=['POST'])
@login_required
def save_pdf_report():
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            conn.execute(text("INSERT INTO pdf_reports (club_id, team_home, team_away, report_data) VALUES (:cid, :h, :a, :rd)"), {"cid": session.get('club_id'), "h": request.json.get('equipe_a', ''), "a": request.json.get('equipe_b', ''), "rd": json.dumps(request.json)})
            trans.commit()
            return jsonify({"status": "success", "message": "Sauvegardé !"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stats')
@login_required
def stats_page(): return render_template('stats.html')

@app.route('/api/completed_matches')
@login_required
def get_completed_matches():
    try:
        with engine.connect() as conn:
            matches = conn.execute(text("SELECT id, team_home, team_away, created_at, winner FROM matches WHERE club_id = :cid ORDER BY created_at DESC"), {"cid": session.get('club_id')}).fetchall()
            result = []
            for m in matches:
                t_home = m[1] if m[1] else "Eq1"
                t_away = m[2] if m[2] else "Eq2"
                date_val = str(m[3])[:10] if m[3] else "?"
                winner = f" - Victoire: {m[4]}" if m[4] else ""
                result.append({"id": m[0], "title": f"{t_home} vs {t_away} ({date_val}){winner}"})
            return jsonify(result)
    except Exception as e:
        print(f"Erreur API Matchs: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/match_stats/<int:match_id>')
@login_required
def get_match_stats(match_id):
    try:
        with engine.connect() as conn:
            match_info = conn.execute(text("SELECT team_home, team_away FROM matches WHERE id = :mid"), {"mid": match_id}).fetchone()
            if not match_info: return jsonify({"error": "Match non trouvé"}), 404
            
            team_home, team_away = match_info[0], match_info[1]
            
            points = conn.execute(text("""
                SELECT set_number, score_home, score_away, server_team, server_num, rotation_home, rotation_away, winner_point 
                FROM points WHERE match_id = :mid ORDER BY id ASC
            """), {"mid": match_id}).fetchall()
            
            if not points or len(points) == 0:
                return jsonify({"error": "Ce match ne contient aucun point. (Score 0-0)"}), 400
                
            sets_data = {}
            for p in points:
                s_num = p[0]
                if s_num not in sets_data: sets_data[s_num] = []
                sets_data[s_num].append({
                    "score_home": p[1], "score_away": p[2], "server_team": p[3], 
                    "server_num": p[4], "rotation_home": p[5], "rotation_away": p[6], "winner_point": p[7]
                })
                
            graphs_payload = []
            for s_num, pts in sets_data.items():
                if not pts: continue
                
                stats_serveurs_home = {}
                stats_serveurs_away = {}
                
                for pt in pts:
                    s_team = pt['server_team']
                    s_num_val = pt['server_num']
                    w_team = pt['winner_point']
                    
                    if s_team == team_home:
                        if s_num_val not in stats_serveurs_home: stats_serveurs_home[s_num_val] = {'scored': 0, 'conceded': 0}
                        if w_team == team_home: stats_serveurs_home[s_num_val]['scored'] += 1
                        else: stats_serveurs_home[s_num_val]['conceded'] += 1
                    elif s_team == team_away:
                        if s_num_val not in stats_serveurs_away: stats_serveurs_away[s_num_val] = {'scored': 0, 'conceded': 0}
                        if w_team == team_away: stats_serveurs_away[s_num_val]['scored'] += 1
                        else: stats_serveurs_away[s_num_val]['conceded'] += 1

                home_efficiency = [{"num": k, "m": v['scored'], "e": v['conceded'], "d": v['scored']-v['conceded']} for k, v in stats_serveurs_home.items()]
                away_efficiency = [{"num": k, "m": v['scored'], "e": v['conceded'], "d": v['scored']-v['conceded']} for k, v in stats_serveurs_away.items()]
                
                home_efficiency = sorted(home_efficiency, key=lambda x: int(x['num']) if str(x['num']).isdigit() else 99)
                away_efficiency = sorted(away_efficiency, key=lambda x: int(x['num']) if str(x['num']).isdigit() else 99)

                score_final = f"{pts[-1]['score_home']} - {pts[-1]['score_away']}"
                
                graphs_payload.append({
                    "set": s_num, "score": score_final, 
                    "graph_duel": generate_duel_graph(pts, team_home, team_away, s_num), 
                    "graph_rot": generate_rotation_graph(pts, team_home, team_away),
                    "eff_home": home_efficiency,
                    "eff_away": away_efficiency
                })
                
            return jsonify({"match_title": f"{team_home} vs {team_away}", "sets": graphs_payload})
            
    except Exception as e:
        print(f"ERREUR GENERATION STATS : {e}")
        return jsonify({"error": f"Erreur de calcul des statistiques : {str(e)}"}), 500

@app.route('/admin')
@superadmin_required
def admin_dashboard():
    with engine.connect() as conn:
        clubs = conn.execute(text("SELECT id, name FROM clubs ORDER BY id")).fetchall()
        users = conn.execute(text("SELECT u.id, u.username, u.role, c.name FROM users u LEFT JOIN clubs c ON u.club_id = c.id ORDER BY u.id")).fetchall()
        teams = conn.execute(text("SELECT t.id, t.name, c.name FROM teams t LEFT JOIN clubs c ON t.club_id = c.id ORDER BY c.name, t.name")).fetchall()
    return render_template('admin.html', clubs=clubs, users=users, teams=teams)

@app.route('/admin/add_club', methods=['POST'])
@superadmin_required
def add_club():
    if request.form.get('name'):
        try:
            with engine.connect() as conn:
                trans = conn.begin()
                conn.execute(text("INSERT INTO clubs (name) VALUES (:n)"), {"n": request.form.get('name')})
                trans.commit()
                flash("Club ajouté.", "success")
        except: flash("Erreur: Club existant.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_user', methods=['POST'])
@superadmin_required
def add_user():
    u, p, r, c = request.form.get('username'), request.form.get('password'), request.form.get('role'), request.form.get('club_id')
    if u and p and r and c:
        try:
            with engine.connect() as conn:
                trans = conn.begin()
                conn.execute(text("INSERT INTO users (username, password_hash, role, club_id) VALUES (:u, :p, :r, :c)"), {"u": u, "p": generate_password_hash(p), "r": r, "c": c})
                trans.commit()
                flash("Utilisateur créé.", "success")
        except: flash("Erreur: Pseudo pris.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_team', methods=['POST'])
@superadmin_required
def add_team():
    n, c = request.form.get('name'), request.form.get('club_id')
    if n and c:
        try:
            with engine.connect() as conn:
                trans = conn.begin()
                conn.execute(text("INSERT INTO teams (name, club_id) VALUES (:n, :c)"), {"n": n, "c": c})
                trans.commit()
                flash("Collectif ajouté.", "success")
        except Exception as e: flash("Erreur lors de l'ajout.", "error")
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

