import pypdfium2 as pdfium
import gc
from PIL import Image

def render_page_to_image(file_bytes, dpi=72):
    """
    Convertit la première page du PDF en image PIL.
    Utilise pypdfium2 pour la rapidité et la gestion mémoire (C++).
    """
    # Chargement du PDF depuis la mémoire
    pdf = pdfium.PdfDocument(file_bytes)
    page = pdf[0]
    
    # Calcul de l'échelle (72 DPI est le standard PDF)
    scale = dpi / 72
    
    # Rendu
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()
    
    # Nettoyage immédiat de la mémoire
    page.close()
    pdf.close()
    gc.collect()
    
    return pil_image, scale