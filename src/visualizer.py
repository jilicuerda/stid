from PIL import Image, ImageDraw
import plotly.express as px

def draw_calibration_grid(base_img, bx, by, w, h, off_x, off_y):
    """Dessine les grilles de calibration sur l'image."""
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    
    for s in range(4): 
        cur_y = by + (s * off_y)
        # Left (Red)
        for i in range(6):
            drift = i * 0.3
            x = bx + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="red", width=2)
        # Right (Blue)
        cur_x = bx + off_x
        for i in range(6):
            drift = i * 0.3
            x = cur_x + (i * w) + drift
            draw.rectangle([x, cur_y, x + w, cur_y + h], outline="blue", width=2)
    return img

def draw_court_view(starters):
    """Crée la Heatmap du terrain."""
    safe_starters = [s if s != "?" else "-" for s in starters]
    while len(safe_starters) < 6: safe_starters.append("-")

    # Mapping visuel (Front Row / Back Row)
    court_data = [
        [safe_starters[3], safe_starters[2], safe_starters[1]], 
        [safe_starters[4], safe_starters[5], safe_starters[0]]
    ]
    
    fig = px.imshow(court_data, 
                    text_auto=True, 
                    color_continuous_scale='Blues',
                    labels=dict(x="Zone", y="Row", color="Val"),
                    x=['Left (4/5)', 'Center (3/6)', 'Right (2/1)'],
                    y=['Front Row', 'Back Row'])
    fig.update_traces(textfont_size=24)
    fig.update_layout(coloraxis_showscale=False, width=400, height=300, margin=dict(l=20, r=20, t=20, b=20))
    return fig