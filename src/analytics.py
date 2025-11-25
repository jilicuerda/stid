import pandas as pd

def calculate_player_stats(df, scores):
    """Calcule le % de victoire par joueur titulaire."""
    stats = {}
    # Associer chaque set à un vainqueur
    set_winners = {i+1: ("Home" if s['Home'] > s['Away'] else "Away") for i, s in enumerate(scores)}

    for _, row in df.iterrows():
        team = row['Team']
        set_n = row['Set']
        
        if set_n in set_winners:
            won = (team == set_winners[set_n])
            for p in row['Starters']:
                if p.isdigit():
                    if p not in stats: stats[p] = {'team': team, 'played': 0, 'won': 0}
                    stats[p]['played'] += 1
                    if won: stats[p]['won'] += 1
    
    data = []
    for p, s in stats.items():
        pct = (s['won']/s['played'])*100 if s['played'] > 0 else 0
        data.append({
            "Joueur": f"#{p}", 
            "Équipe": s['team'], 
            "Sets Joués": s['played'], 
            "Victoire %": round(pct, 1)
        })
    
    if not data: return pd.DataFrame()
    return pd.DataFrame(data).sort_values(['Équipe', 'Victoire %'], ascending=[True, False])

def analyze_money_time(scores, t_home, t_away):
    """Analyse les fins de sets serrées (Score > 20, Écart <= 3)."""
    analysis = []
    clutch_stats = {t_home: 0, t_away: 0}
    
    for i, s in enumerate(scores):
        diff = abs(s['Home'] - s['Away'])
        winner = t_home if s['Home'] > s['Away'] else t_away
        
        # Critère Money Time
        if max(s['Home'], s['Away']) >= 20 and diff <= 3:
            clutch_stats[winner] += 1
            analysis.append(f"✅ Set {i+1} ({s['Home']}-{s['Away']}) : Gagné par **{winner}** au finish.")
        elif diff > 5:
            analysis.append(f"⚠️ Set {i+1} ({s['Home']}-{s['Away']}) : Victoire large de {winner} (Pas de suspense).")
        else:
            analysis.append(f"ℹ️ Set {i+1} ({s['Home']}-{s['Away']}) : Victoire standard de {winner}.")
            
    return analysis, clutch_stats

def format_export_data(df_lineups):
    """Prépare le CSV final."""
    export = df_lineups.copy()
    cols = pd.DataFrame(export['Starters'].tolist(), columns=[f'Zone {i+1}' for i in range(6)])
    return pd.concat([export[['Set', 'Team']], cols], axis=1)