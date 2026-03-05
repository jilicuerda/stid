@app.route('/api/match_stats/<int:match_id>')
@login_required
def get_match_stats(match_id):
    try:
        with engine.connect() as conn:
            match_info = conn.execute(text("SELECT team_home, team_away, roster_home, roster_away FROM matches WHERE id = :mid"), {"mid": match_id}).fetchone()
            if not match_info: return jsonify({"error": "Match non trouvé"}), 404
            
            team_home, team_away = match_info[0], match_info[1]
            try: roster_h = json.loads(match_info[2]) if isinstance(match_info[2], str) else (match_info[2] or {})
            except: roster_h = {}
            try: roster_a = json.loads(match_info[3]) if isinstance(match_info[3], str) else (match_info[3] or {})
            except: roster_a = {}
            
            points = conn.execute(text("""
                SELECT set_number, score_home, score_away, server_team, server_num, rotation_home, rotation_away, winner_point, action_type, player_num, player_team 
                FROM points WHERE match_id = :mid ORDER BY id ASC
            """), {"mid": match_id}).fetchall()
            
            if not points or len(points) == 0: return jsonify({"error": "Ce match ne contient aucun point. (Score 0-0)"}), 400
                
            tous_points = []
            sets_list = set()
            for p in points:
                sets_list.add(p[0])
                tous_points.append({
                    "set": p[0], "score_dom": p[1], "score_ext": p[2], "server_team": p[3], "server_num": p[4],
                    "rot_home": p[5], "rot_away": p[6], "winner_team": p[7], "action": p[8], "actor_num": p[9], "actor_team": p[10]
                })
            
            graphs_payload = []
            for n_set in sorted(list(sets_list)):
                pts_set = [p for p in tous_points if p['set'] == n_set]
                if not pts_set: continue
                
                b64_duel = tracer_duel_chronologique_annote(pts_set, team_home, team_away, n_set)
                st_h, st_a = [], []
                
                for pt in pts_set:
                    kh, ka, win = pt['rot_home'], pt['rot_away'], pt['winner_team']
                    
                    f_h = False
                    for s in st_h:
                        if sont_similaires(s['key'], kh):
                            if win == team_home: s['m'] += 1
                            else: s['e'] += 1
                            f_h = True; break
                    if not f_h: st_h.append({'key': kh, 'm': 1 if win == team_home else 0, 'e': 1 if win != team_home else 0, 'point': pt})
                    
                    f_a = False
                    for s in st_a:
                        if sont_similaires(s['key'], ka):
                            if win == team_away: s['m'] += 1
                            else: s['e'] += 1
                            f_a = True; break
                    if not f_a: st_a.append({'key': ka, 'm': 1 if win == team_away else 0, 'e': 1 if win != team_away else 0, 'point': pt})
                
                b64_rot_h = afficher_grille_rotations(st_h, team_home, team_away, team_home, 'royalblue', f"Positions de Service : {team_home}")
                b64_rot_a = afficher_grille_rotations(st_a, team_home, team_away, team_away, 'darkorange', f"Positions de Service : {team_away}")
                
                graphs_payload.append({
                    "set": n_set, "score": f"{pts_set[-1]['score_dom']} - {pts_set[-1]['score_ext']}",
                    "graph_duel": b64_duel, "graph_rot_h": b64_rot_h, "graph_rot_a": b64_rot_a
                })
            
            indiv_h, indiv_a, pie_h, pie_a = calculer_stats_individuelles(tous_points, roster_h, roster_a, team_home, team_away)
            eff_rot_h, eff_rot_a = calculer_efficacite_rotations(tous_points, team_home, team_away)
                
            return jsonify({
                "match_title": f"{team_home} vs {team_away}", 
                "sets": graphs_payload,
                "stats_indiv_h": indiv_h, "stats_indiv_a": indiv_a,
                "pie_h": pie_h, "pie_a": pie_a,
                "eff_rot_h": eff_rot_h, "eff_rot_a": eff_rot_a,
                "team_home": team_home, "team_away": team_away
            })
            
    except Exception as e:
        print(f"ERREUR GENERATION STATS : {e}")
        return jsonify({"error": f"Erreur de calcul des statistiques : {str(e)}"}), 500
