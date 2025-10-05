# server.py

import sqlite3
import json
import random
import string 
import os # <--- AÑADIDO: Para acceder a las variables de entorno
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, JWTManager
import requests as api_requests
from urllib.parse import urlencode
from datetime import date
from dotenv import load_dotenv # <--- AÑADIDO: Para cargar el archivo .env

# Librerías de Google
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Importa la librería de Flask-Mail
from flask_mail import Mail, Message

# Carga las variables de entorno del archivo .env
load_dotenv() # <--- AÑADIDO: Esta línea lee tu archivo .env

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# --- CONFIGURACIÓN DE SEGURIDAD Y JUEGO (AHORA DESDE VARIABLES DE ENTORNO) ---
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_CSRF_IN_COOKIES"] = False
jwt = JWTManager(app)

# --- CONFIGURACIÓN DE FLASK-MAIL (AHORA DESDE VARIABLES DE ENTORNO) ---
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT')) # Convertir a entero
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS').lower() in ('true', '1', 't') # Convertir a booleano
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL').lower() in ('true', '1', 't') # Convertir a booleano
mail = Mail(app)


@app.after_request
def add_security_headers(response):
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'
    return response

# --- CONFIGURACIÓN GENERAL (AHORA DESDE VARIABLES DE ENTORNO) ---
YOUR_SERVER_BASE_URL = os.getenv("SERVER_BASE_URL")
RISKPAY_PAYOUT_WALLET = os.getenv("RISKPAY_PAYOUT_WALLET")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
DATABASE_FILE = os.getenv("DATABASE_FILE")
FOOD_TO_REACH_GOAL = 300.0
FOOD_BAG_CAPACITY = 5
MAX_COMIDAS_DIARIAS = 15
PRICES_USDC = {"1": 35.0, "2": 120.0, "3": 200.0, "food_pack": 10.0}
PRIZES_MAP = {"1": "Premio: 500 Soles", "2": "Premio: 870 Soles", "3": "Premio: 1230 Soles"}

# --- GESTIÓN DE LA BASE DE DATOS ---
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE_FILE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone() is None:
            cursor.execute('''CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password_hash TEXT, 
                google_id TEXT UNIQUE, referral_code TEXT UNIQUE, is_verified INTEGER DEFAULT 0,
                verification_code TEXT, referred_by_user_id INTEGER 
            )''')
        else:
            try: cursor.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
            except: pass
            try: cursor.execute("ALTER TABLE users ADD COLUMN verification_code TEXT")
            except: pass
            try: cursor.execute("ALTER TABLE users ADD COLUMN referred_by_user_id INTEGER")
            except: pass
            try: cursor.execute("ALTER TABLE users ADD COLUMN referral_code TEXT UNIQUE")
            except: pass

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='players'")
        if cursor.fetchone() is None:
            cursor.execute('''
                CREATE TABLE players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'pending_payment',
                    crecimiento REAL, comida_disponible INTEGER,
                    comida_en_bolsa INTEGER, comida_total_consumida INTEGER,
                    premio_elegido TEXT,
                    chest_visible INTEGER DEFAULT 0, chest_x INTEGER, chest_y INTEGER,
                    chest_task_id TEXT,
                    comida_hoy INTEGER DEFAULT 0, ultima_alimentacion TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        else:
            try: cursor.execute("ALTER TABLE players ADD COLUMN chest_task_id TEXT")
            except: pass

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shares'")
        if cursor.fetchone() is None:
            cursor.execute('''CREATE TABLE shares (
                user_id INTEGER PRIMARY KEY,
                share_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )''')

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='referral_purchases'")
        if cursor.fetchone() is None:
            cursor.execute('''CREATE TABLE referral_purchases (id INTEGER PRIMARY KEY, referrer_user_id INTEGER NOT NULL, new_user_id INTEGER NOT NULL, fish_choice_id TEXT NOT NULL, FOREIGN KEY (referrer_user_id) REFERENCES users (id), FOREIGN KEY (new_user_id) REFERENCES users (id))''')
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='unlocked_fish'")
        if cursor.fetchone() is None:
            cursor.execute('''CREATE TABLE unlocked_fish (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, fish_choice_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'available', FOREIGN KEY (user_id) REFERENCES users (id))''')

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='claimed_task_rewards'")
        if cursor.fetchone() is None:
            cursor.execute('''CREATE TABLE claimed_task_rewards (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, task_id TEXT NOT NULL, UNIQUE(user_id, task_id), FOREIGN KEY (user_id) REFERENCES users (id))''')
            
        db.commit()

def generate_unique_referral_code(db):
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if not db.execute('SELECT id FROM users WHERE referral_code = ?', (code,)).fetchone():
            return code

def send_verification_email(user_email, code):
    try:
        msg = Message('Tu Código de Verificación para Acuario Virtual',
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[user_email])
        msg.body = f'¡Bienvenido a Acuario Virtual!\n\nUsa este código para activar tu cuenta: {code}\n\nGracias por unirte.'
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error al enviar email: {e}")
        return False

# --- ENDPOINTS DE AUTENTICACIÓN ---
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    referral_code_from_input = data.get("referral_code")
    if not email or not password: return jsonify({"message": "Faltan datos"}), 400
    db = get_db()
    
    existing_user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if existing_user:
        if not existing_user['is_verified']:
            verification_code = str(random.randint(100000, 999999))
            password_hash = generate_password_hash(password)
            db.execute('UPDATE users SET password_hash = ?, verification_code = ? WHERE email = ?', (password_hash, verification_code, email))
            db.commit()
            send_verification_email(email, verification_code)
            return jsonify({"success": True, "message": "Ya existe una cuenta no verificada. Te hemos enviado un nuevo código."})
        else:
            return jsonify({"message": "El email ya está registrado y verificado."}), 409

    referred_by_id = None
    if referral_code_from_input:
        owner = db.execute('SELECT id FROM users WHERE referral_code = ?', (referral_code_from_input.upper(),)).fetchone()
        if owner:
            referred_by_id = owner['id']

    password_hash = generate_password_hash(password)
    new_user_referral_code = generate_unique_referral_code(db)
    verification_code = str(random.randint(100000, 999999))
    db.execute('INSERT INTO users (email, password_hash, referral_code, verification_code, is_verified, referred_by_user_id) VALUES (?, ?, ?, ?, 0, ?)', (email, password_hash, new_user_referral_code, verification_code, referred_by_id))
    db.commit()
    send_verification_email(email, verification_code)
    return jsonify({"success": True, "message": "¡Registro exitoso! Revisa tu email para verificar."})

@app.route("/verify", methods=["POST"])
def verify_email():
    email = request.json.get("email")
    code = request.json.get("code")
    if not email or not code: return jsonify({"message": "Faltan email o código."}), 400
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if not user: return jsonify({"message": "Usuario no encontrado."}), 404
    if user['is_verified']: return jsonify({"message": "La cuenta ya está verificada."}), 400
    if user['verification_code'] != code: return jsonify({"message": "Código de verificación incorrecto."}), 400
    db.execute('UPDATE users SET is_verified = 1, verification_code = NULL WHERE email = ?', (email,))
    db.commit()
    return jsonify({"success": True, "message": "¡Cuenta verificada! Ya puedes iniciar sesión."})

@app.route("/login", methods=["POST"])
def login():
    email = request.json.get("email")
    password = request.json.get("password")
    user = get_db().execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if user and user['password_hash']:
        if not user['is_verified']:
            return jsonify({"message": "Tu cuenta no está verificada. Por favor, revisa tu email.", "code": "ACCOUNT_NOT_VERIFIED"}), 401
        if check_password_hash(user['password_hash'], password):
            access_token = create_access_token(identity=str(user['id']))
            return jsonify(access_token=access_token)
    return jsonify({"message": "Credenciales inválidas"}), 401

@app.route("/google-login", methods=["POST"])
def google_login():
    try:
        id_info = id_token.verify_oauth2_token(request.get_json().get('credential'), google_requests.Request(), GOOGLE_CLIENT_ID)
        google_user_id, email = id_info['sub'], id_info['email']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE google_id = ?', (google_user_id,)).fetchone()
        if not user:
            user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            if user:
                db.execute('UPDATE users SET google_id = ?, is_verified = 1 WHERE email = ?', (google_user_id, email))
            else:
                referral_code = generate_unique_referral_code(db)
                db.execute('INSERT INTO users (email, google_id, referral_code, is_verified) VALUES (?, ?, ?, 1)', (email, google_user_id, referral_code))
            db.commit()
            user = db.execute('SELECT * FROM users WHERE google_id = ?', (google_user_id,)).fetchone()
        access_token = create_access_token(identity=str(user['id']))
        return jsonify(access_token=access_token)
    except Exception as e:
        return jsonify({"message": f"Error en el servidor: {e}"}), 500

# --- ENDPOINTS DE PAGO Y WEBHOOKS ---
@app.route("/generate_payment_link", methods=["POST"])
@jwt_required()
def generate_payment_link():
    user_id = get_jwt_identity()
    choice_id = str(request.json.get("choice_id"))
    user_email = get_db().execute('SELECT email FROM users WHERE id = ?', (user_id,)).fetchone()['email']
    amount_usd = PRICES_USDC[choice_id]
    callback_url = f"{YOUR_SERVER_BASE_URL}/webhook/riskpay?user_id={user_id}&choice_id={choice_id}"
    try:
        response = api_requests.get("https://api.riskpay.biz/control/wallet.php", params={"address": RISKPAY_PAYOUT_WALLET, "callback": callback_url})
        response.raise_for_status()
        encrypted_address = response.json().get("address_in")
        params_to_encode = {"email": user_email, "provider": "rampnetwork", "amount": amount_usd, "currency": "usd"}
        final_link = f"https://checkout.riskpay.biz/process-payment.php?address={encrypted_address}&{urlencode(params_to_encode)}"
        return jsonify({"success": True, "payment_url": final_link})
    except api_requests.exceptions.RequestException as e:
        return jsonify({"message": "Error con el servicio de pagos"}), 503

@app.route("/generate_food_payment_link", methods=["POST"])
@jwt_required()
def generate_food_payment_link():
    user_id = get_jwt_identity()
    choice_id = "food_pack"
    user_email = get_db().execute('SELECT email FROM users WHERE id = ?', (user_id,)).fetchone()['email']
    amount_usd = PRICES_USDC[choice_id]
    callback_url = f"{YOUR_SERVER_BASE_URL}/webhook/riskpay?user_id={user_id}&choice_id={choice_id}"
    try:
        response = api_requests.get("https://api.riskpay.biz/control/wallet.php", params={"address": RISKPAY_PAYOUT_WALLET, "callback": callback_url})
        response.raise_for_status()
        encrypted_address = response.json().get("address_in")
        params_to_encode = {"email": user_email, "provider": "rampnetwork", "amount": amount_usd, "currency": "usd"}
        final_link = f"https://checkout.riskpay.biz/process-payment.php?address={encrypted_address}&{urlencode(params_to_encode)}"
        return jsonify({"success": True, "payment_url": final_link})
    except api_requests.exceptions.RequestException as e:
        return jsonify({"message": "Error con el servicio de pagos"}), 503

@app.route("/webhook/riskpay", methods=["GET"])
def riskpay_webhook():
    data = request.args
    user_id, choice_id = data.get('user_id'), data.get('choice_id')
    if float(data.get('value_coin', 0)) < PRICES_USDC.get(choice_id, 9999) * 0.98: return "", 400
    db = get_db()
    if choice_id == "food_pack":
        db.execute('UPDATE players SET comida_disponible = comida_disponible + 50 WHERE user_id = ?', (user_id,))
    else:
        if not db.execute('SELECT id FROM players WHERE user_id = ?', (user_id,)).fetchone():
            db.execute('''INSERT INTO players (user_id, status, crecimiento, comida_disponible, comida_en_bolsa, comida_total_consumida, premio_elegido, chest_visible) VALUES (?, 'active', 0, 25, 0, 0, ?, 0)''', (user_id, PRIZES_MAP.get(choice_id)))
        else:
            db.execute('''UPDATE players SET status = 'active', crecimiento = 0, comida_disponible = 25, comida_en_bolsa = 0, comida_total_consumida = 0, premio_elegido = ?, chest_visible = 0, chest_task_id = NULL WHERE user_id = ?''', (PRIZES_MAP.get(choice_id), user_id))
        
        new_user = db.execute('SELECT referred_by_user_id FROM users WHERE id = ?', (user_id,)).fetchone()
        if new_user and new_user['referred_by_user_id'] and not db.execute('SELECT id FROM referral_purchases WHERE new_user_id = ?', (user_id,)).fetchone():
            referrer_id = new_user['referred_by_user_id']
            db.execute('INSERT INTO referral_purchases (referrer_user_id, new_user_id, fish_choice_id) VALUES (?, ?, ?)',(referrer_id, user_id, choice_id))
            db.execute('UPDATE players SET comida_disponible = comida_disponible + 50 WHERE user_id = ?', (referrer_id,))
    db.commit()
    return "", 200

# --- LÓGICA CENTRAL DEL JUEGO ---

@app.route("/track_share", methods=["POST"])
@jwt_required()
def track_share():
    user_id = get_jwt_identity()
    db = get_db()
    db.execute('INSERT OR IGNORE INTO shares (user_id, share_count) VALUES (?, 0)', (user_id,))
    db.execute('UPDATE shares SET share_count = share_count + 1 WHERE user_id = ?', (user_id,))
    db.commit()
    return jsonify({"success": True, "new_state": get_player_data_for_user(user_id)})

def get_player_data_for_user(user_id):
    db = get_db()
    player_row = db.execute('SELECT * FROM players WHERE user_id = ?', (user_id,)).fetchone()
    if not player_row: return None
    
    player_data = dict(player_row)
    user_row = db.execute('SELECT referral_code FROM users WHERE id = ?', (user_id,)).fetchone()
    player_data['referral_code'] = user_row['referral_code'] if user_row else "..."

    # Obtener progreso de todas las tareas
    share_row = db.execute('SELECT share_count FROM shares WHERE user_id = ?', (user_id,)).fetchone()
    share_count = share_row['share_count'] if share_row else 0
    
    referral_purchases = db.execute('SELECT fish_choice_id FROM referral_purchases WHERE referrer_user_id = ?', (user_id,)).fetchall()
    claimed_rewards = [row['task_id'] for row in db.execute('SELECT task_id FROM claimed_task_rewards WHERE user_id = ?', (user_id,)).fetchall()]
    
    fish1_count = len([p for p in referral_purchases if p['fish_choice_id'] == '1'])
    fish2_count = len([p for p in referral_purchases if p['fish_choice_id'] == '2'])
    fish3_count = len([p for p in referral_purchases if p['fish_choice_id'] == '3'])
    progress_equivalente = fish1_count + (fish2_count * 2) + (fish3_count * 3.3)

    # Definir todas las tareas
    tasks_definitions = [
        {"id": "whatsapp_share", "name": "Compartir 15 veces en WhatsApp", "reward_text": "+15 Comida", "progress": share_count, "goal": 15},
        {"id": "ref_5_peces", "name": "Invita a 5 amigos a comprar un pez", "reward_text": "Gana 1 Pez (S/ 170)", "progress": len(referral_purchases), "goal": 5, "reward_fish_id": "1"},
        {"id": "ref_10_simples", "name": "Invita a comprar 10 peces simples (o eq.)", "reward_text": "Gana 1 Pez (S/ 450)", "progress": progress_equivalente, "goal": 10, "reward_fish_id": "2"},
        {"id": "ref_20_simples", "name": "Invita a comprar 20 peces simples (o eq.)", "reward_text": "Gana 1 Pez (S/ 750)", "progress": progress_equivalente, "goal": 20, "reward_fish_id": "3"}
    ]
    
    for task in tasks_definitions:
        task['is_claimed'] = task['id'] in claimed_rewards

    player_data['tasks_definitions'] = tasks_definitions
    
    if not player_data['chest_visible']:
        task_to_reward = next((task for task in tasks_definitions if task['progress'] >= task['goal'] and not task['is_claimed']), None)
        if task_to_reward:
            new_x, new_y = random.randint(100, 700), random.randint(200, 500)
            db.execute('UPDATE players SET chest_visible = 1, chest_x = ?, chest_y = ?, chest_task_id = ? WHERE user_id = ?', (new_x, new_y, task_to_reward['id'], user_id))
            db.commit()
            player_data = dict(db.execute('SELECT * FROM players WHERE user_id = ?', (user_id,)).fetchone())

    return player_data

@app.route("/get_game_state", methods=["GET"])
@jwt_required()
def get_game_state():
    user_id = get_jwt_identity()
    player_data = get_db().execute("SELECT * FROM players WHERE user_id = ? AND status = 'active'", (user_id,)).fetchone()
    unlocked_fish_ids = [row['fish_choice_id'] for row in get_db().execute("SELECT fish_choice_id FROM unlocked_fish WHERE user_id = ? AND status = 'available'", (user_id,)).fetchall()]

    if not player_data: 
        return jsonify({"game_exists": False, "unlocked_fish_ids": unlocked_fish_ids})

    player_data_dict = get_player_data_for_user(user_id)
    player_data_dict['unlocked_fish_ids'] = unlocked_fish_ids
    prize_to_id = {"Premio: 500 Soles": "1", "Premio: 870 Soles": "2", "Premio: 1230 Soles": "3"}
    player_data_dict['active_fish_id'] = prize_to_id.get(player_data_dict['premio_elegido'])
    return jsonify({"game_exists": True, "state": player_data_dict})

@app.route("/claim_chest", methods=["POST"])
@jwt_required()
def claim_chest():
    user_id = get_jwt_identity()
    db = get_db()
    player = db.execute('SELECT chest_visible, chest_task_id FROM players WHERE user_id = ?', (user_id,)).fetchone()

    if not player or not player['chest_visible'] or not player['chest_task_id']:
        return jsonify({"success": False, "message": "No hay un cofre de recompensa activo."})

    task_id_to_claim = player['chest_task_id']
    message = "Error desconocido."

    # --- CORRECCIÓN: Lógica de recompensa completa para todas las tareas ---
    if task_id_to_claim == 'whatsapp_share':
        db.execute('UPDATE players SET comida_disponible = comida_disponible + 15 WHERE user_id = ?', (user_id,))
        message = "¡Felicidades! Has ganado +15 de comida."
    elif task_id_to_claim == 'ref_5_peces':
        db.execute('INSERT INTO unlocked_fish (user_id, fish_choice_id, status) VALUES (?, "1", "available")', (user_id,))
        message = "¡Felicidades! Has desbloqueado un nuevo pez (Premio: 500 Soles)."
    elif task_id_to_claim == 'ref_10_simples':
        db.execute('INSERT INTO unlocked_fish (user_id, fish_choice_id, status) VALUES (?, "2", "available")', (user_id,))
        message = "¡Increíble! Has desbloqueado un nuevo pez (Premio: 870 Soles)."
    elif task_id_to_claim == 'ref_20_simples':
        db.execute('INSERT INTO unlocked_fish (user_id, fish_choice_id, status) VALUES (?, "3", "available")', (user_id,))
        message = "¡Eres una leyenda! Has desbloqueado el mejor pez (Premio: 1230 Soles)."
    
    db.execute('INSERT OR IGNORE INTO claimed_task_rewards (user_id, task_id) VALUES (?, ?)', (user_id, task_id_to_claim))
    db.execute('UPDATE players SET chest_visible = 0, chest_task_id = NULL WHERE user_id = ?', (user_id,))
    db.commit()
    return jsonify({"success": True, "message": message, "new_state": get_player_data_for_user(user_id)})

@app.route("/start_free_game", methods=["POST"])
@jwt_required()
def start_free_game():
    user_id, choice_id = get_jwt_identity(), str(request.json.get("choice_id"))
    db = get_db()
    if db.execute("SELECT id FROM players WHERE user_id = ? AND status = 'active'", (user_id,)).fetchone(): return jsonify({"success": False, "message": "Ya tienes una partida en curso."})
    unlocked_fish = db.execute("SELECT id FROM unlocked_fish WHERE user_id = ? AND fish_choice_id = ? AND status = 'available'", (user_id, choice_id)).fetchone()
    if not unlocked_fish: return jsonify({"success": False, "message": "No tienes este pez desbloqueado."})
    db.execute("UPDATE unlocked_fish SET status = 'in_use' WHERE id = ?", (unlocked_fish['id'],))
    
    if db.execute('SELECT id FROM players WHERE user_id = ?', (user_id,)).fetchone():
        db.execute('''UPDATE players SET status = 'active', crecimiento = 0, comida_disponible = 25, comida_en_bolsa = 0, comida_total_consumida = 0, premio_elegido = ?, chest_visible = 0 WHERE user_id = ?''', (PRIZES_MAP.get(choice_id), user_id))
    else:
        db.execute('''INSERT INTO players (user_id, status, crecimiento, comida_disponible, comida_en_bolsa, comida_total_consumida, premio_elegido, chest_visible) VALUES (?, 'active', 0, 25, 0, 0, ?, 0)''', (user_id, PRIZES_MAP.get(choice_id)))

    db.commit()
    return jsonify({"success": True, "new_state": get_player_data_for_user(user_id)})

@app.route("/feed_fish", methods=["POST"])
@jwt_required()
def feed_fish_action():
    user_id = get_jwt_identity()
    db = get_db()
    player = db.execute('SELECT * FROM players WHERE user_id = ?', (user_id,)).fetchone()
    if player['comida_en_bolsa'] <= 0: return jsonify({"success": False, "message": "Bolsa vacía."}), 400
    today_str = str(date.today())
    if player['ultima_alimentacion'] != today_str:
        db.execute('UPDATE players SET comida_hoy = 0, ultima_alimentacion = ? WHERE user_id = ?', (today_str, user_id))
        player = db.execute('SELECT * FROM players WHERE user_id = ?', (user_id,)).fetchone()
    if player['comida_hoy'] >= MAX_COMIDAS_DIARIAS: return jsonify({"success": False, "message": "Límite de alimentación diario."}), 403
    new_crecimiento = min(100, ((player['comida_total_consumida'] + 1) / FOOD_TO_REACH_GOAL) * 100)
    db.execute('''UPDATE players SET crecimiento = ?, comida_en_bolsa = ?, comida_total_consumida = ?, comida_hoy = ? WHERE user_id = ?''', (new_crecimiento, player['comida_en_bolsa'] - 1, player['comida_total_consumida'] + 1, player['comida_hoy'] + 1, user_id))
    db.commit()
    return jsonify({"success": True, "new_state": get_player_data_for_user(user_id)})

@app.route("/load_food_bag", methods=["POST"])
@jwt_required()
def load_food_bag():
    user_id = get_jwt_identity()
    db = get_db()
    player = db.execute('SELECT * FROM players WHERE user_id = ?', (user_id,)).fetchone()
    food_to_move = min(player['comida_disponible'], FOOD_BAG_CAPACITY - player['comida_en_bolsa'])
    if food_to_move <= 0: return jsonify({"success": False, "message": "Bolsa llena o no tienes comida."})
    db.execute('UPDATE players SET comida_disponible = ?, comida_en_bolsa = ? WHERE user_id = ?', (player['comida_disponible'] - food_to_move, player['comida_en_bolsa'] + food_to_move, user_id))
    db.commit()
    return jsonify({"success": True, "message": f"+{food_to_move} de comida a la bolsa", "new_state": get_player_data_for_user(user_id)})

@app.route("/request_withdrawal", methods=["POST"])
@jwt_required()
def request_withdrawal():
    user_id = get_jwt_identity()
    player = get_db().execute('SELECT crecimiento FROM players WHERE user_id = ?', (user_id,)).fetchone()
    if player and player['crecimiento'] >= 100: return jsonify({"success": True})
    return jsonify({"success": False, "message": f"Progreso: {int(player['crecimiento'] if player else 0)}%."}), 403

@jwt.invalid_token_loader
def invalid_token_callback(error): return jsonify(message=f"Token inválido: {error}"), 422
@jwt.unauthorized_loader
def missing_token_callback(error): return jsonify(message=f"Falta token: {error}"), 401

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)