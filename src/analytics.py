import pandas as pd

def calculate_real_stats(df, scores):
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
    
    # Formatter en DataFrame
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

def format_export_data(df_lineups):
    """Prépare le CSV final avec les 6 zones séparées."""
    export = df_lineups.copy()
    # Séparer la liste [1, 7, 5...] en colonnes Z1, Z2...
    cols = pd.DataFrame(export['Starters'].tolist(), columns=[f'Zone {i+1}' for i in range(6)])
    return pd.concat([export[['Set', 'Team']], cols], axis=1)