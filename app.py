import os
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text

app = Flask(__name__)

# --- MODIFICATION CLOUD ---
# Le serveur va chercher la variable 'DATABASE_URL'. 
# Si elle n'existe pas (en local), il prend votre lien actuel.
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres.zuepinzkfajzlhpsmxql:2026%2FSTIDVOLL@aws-1-eu-central-1.pooler.supabase.com:6543/postgres")

engine = create_engine(DB_URL)

# ... le reste du code ne change pas ...

if __name__ == '__main__':
    # Modification pour que le Cloud puisse choisir le PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
