from PIL import Image, ImageDraw
import plotly.express as px

def draw_alignment_grid(base_img, bx, by, w, h, off_x, off_y):
    """Dessine les rectangles rouges/bleus sur l'image de calibration."""
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    
    for s in range(4): 
        cur_y = by + (s * off_y)
        # Gauche (Rouge)
        for i in range(6):
            drift = i * 0.3
            x = bx + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="red", width=2)
        # Droite (Bleu)
        cur_x = bx + off_x
        for i in range(6):
            drift = i * 0.3
            x = cur_x + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="blue", width=2)
    return img

def draw_court(starters):
    """Crée la heatmap du terrain de volley."""
    safe = [s if s != "?" else "-" for s in starters]
    while len(safe) < 6: safe.append("-")
    
    # Mapping : Avant (4,3,2) / Arrière (5,6,1)
    grid = [
        [safe[3], safe[2], safe[1]], 
        [safe[4], safe[5], safe[0]]
    ]
    
    fig = px.imshow(grid, text_auto=True, color_continuous_scale='Blues',
                    x=['Gauche', 'Centre', 'Droite'], 
                    y=['Filet (Avant)', 'Fond (Arrière)'])
    
    fig.update_layout(
        coloraxis_showscale=False, 
        height=300, 
        margin=dict(l=10, r=10, t=10, b=10),
        title="Positionnement au service"
    )
    fig.update_traces(textfont_size=24)
    return fig