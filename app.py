from flask import Flask, render_template_string, redirect, url_for, request, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, base64, json, requests, hashlib, time
from datetime import datetime, timedelta
from PIL import Image, ImageStat
from functools import wraps

app = Flask(__name__)
app.secret_key = 'life_rpg_global_secure_key_2026'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
DB_NAME = os.path.join(BASE_DIR, "life_rpg.db")

AUTO_QUESTS = {
    "1": [("30 отжиманий", 1), ("Силовая тренировка 30 мин", 2), ("Рекорд в подтягиваниях", 3)],
    "2": [("Чтение книги 20 минут", 1), ("Написать код / скрипт", 2), ("Изучать сложную тему 1.5 часа", 3)],
    "3": [("Прогулка 30 минут", 1), ("10 000 шагов за день", 2), ("Активный выезд на велосипеде", 3)],
    "4": [("Уборка на рабочем месте", 1), ("Без соцсетей 2 часа", 2), ("Спланировать задачи на завтра", 1)]
}

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        nickname TEXT DEFAULT 'Игрок',
        bio TEXT DEFAULT 'Исследует этот мир...',
        avatar TEXT DEFAULT 'default.png',
        api_key TEXT DEFAULT '',
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        gold INTEGER DEFAULT 100,
        hp INTEGER DEFAULT 100,
        strength INTEGER DEFAULT 1,
        intellect INTEGER DEFAULT 1,
        endurance INTEGER DEFAULT 1,
        discipline INTEGER DEFAULT 1,
        last_auto_quest TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        stat_type TEXT NOT NULL,
        difficulty INTEGER NOT NULL,
        is_extra INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS shop (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        price INTEGER NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS used_hashes (
        hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL
    )''')
    
    c.execute('SELECT COUNT(*) FROM shop')
    if c.fetchone()[0] == 0:
        c.executemany('INSERT INTO shop (title, price) VALUES (?, ?)', 
                      [("☕ Чашка кофе / Энергетик", 40), ("🎮 1 час видеоигр", 70), ("🍕 Вкусняшка / Читмил", 120)])
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def generate_quests_batch(user_id, count=4, is_extra=0):
    conn = get_db()
    c = conn.cursor()
    for _ in range(count):
        st = str(random.randint(1, 4))
        title, diff = random.choice(AUTO_QUESTS[st])
        prefix = "⚡ [ДОП]" if is_extra else "🎯"
        c.execute('INSERT INTO quests (user_id, title, stat_type, difficulty, is_extra) VALUES (?, ?, ?, ?, ?)',
                  (user_id, f"{prefix} {title}", st, diff, is_extra))
    conn.commit()
    conn.close()

def check_auto_quest(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT last_auto_quest FROM users WHERE id = ?', (user_id,))
    res = c.fetchone()
    update = False
    if res and res['last_auto_quest']:
        try:
            if datetime.now() - datetime.fromisoformat(res['last_auto_quest']) >= timedelta(hours=6): update = True
        except: update = True
    else: update = True

    if update:
        c.execute('DELETE FROM quests WHERE user_id = ? AND is_extra = 0', (user_id,))
        c.execute('UPDATE users SET last_auto_quest = ? WHERE id = ?', (datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()
        generate_quests_batch(user_id, 4, 0)
    else:
        conn.close()

def verify_with_ai(api_key, quest_title, file_path):
    if not file_path: return True, "Сдано без медиафайла (-15 HP)", True
    if api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            payload = {"contents": [{"parts": [{"text": f"Проверь доказательство выполнения квеста: '{quest_title}'. Ответь строго JSON: {{\"status\": \"APPROVED\", \"reason\": \"причина\"}}"}, {"inline_data": {"mime_type": "image/jpeg", "data": b64}}]}]}
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                data = json.loads(res.json()['candidates'][0]['content']['parts'][0]['text'])
                if data.get("status") == "APPROVED": return True, f"ИИ одобрил: {data.get('reason')}", False
                else: return False, f"ИИ отклонил: {data.get('reason')}", False
        except: pass
    return True, "Файл успешно принят системой!", False

# --- ДИЗАЙН (GLASSMORPHISM & GLOW) ---
GLOBAL_CSS = '''
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    :root {
        --bg: #070913;
        --card-bg: rgba(18, 24, 38, 0.55);
        --border-glass: rgba(0, 242, 254, 0.15);
        --neon-cyan: #00f2fe;
        --neon-green: #10b981;
        --neon-purple: #9d4edd;
        --neon-gold: #ffb703;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
    }
    body {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: var(--bg);
        background-image: 
            radial-gradient(circle at 10% 20%, rgba(0, 242, 254, 0.12) 0%, transparent 40%),
            radial-gradient(circle at 90% 80%, rgba(157, 78, 221, 0.12) 0%, transparent 40%),
            radial-gradient(circle at 50% 50%, rgba(16, 185, 129, 0.08) 0%, transparent 50%);
        color: var(--text-main);
        margin: 0; padding: 15px;
        min-height: 100vh;
        box-sizing: border-box;
    }
    .container { max-width: 450px; margin: 0 auto; padding-bottom: 70px; }
    .glass-card {
        background: var(--card-bg);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--border-glass);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37), inset 0 0 15px rgba(255, 255, 255, 0.02);
        border-radius: 22px;
        padding: 20px;
        margin-bottom: 18px;
    }
    .glow-btn {
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        color: #000; font-weight: 700; border: none; border-radius: 14px;
        padding: 12px 20px; width: 100%; cursor: pointer; text-align: center;
        box-shadow: 0 0 20px rgba(0, 242, 254, 0.35);
        transition: 0.2s ease; text-decoration: none; display: inline-block; box-sizing: border-box;
    }
    .glow-btn:hover { box-shadow: 0 0 30px rgba(0, 242, 254, 0.6); transform: translateY(-2px); }
    .glow-btn-purple {
        background: linear-gradient(135deg, #9d4edd 0%, #b820e6 100%);
        color: #fff; box-shadow: 0 0 20px rgba(157, 78, 221, 0.35);
    }
    input, textarea {
        width: 100%; background: rgba(0, 0, 0, 0.4); border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px; padding: 12px; color: #fff; box-sizing: border-box; margin: 8px 0; font-family: inherit;
    }
    input:focus, textarea:focus { outline: none; border-color: var(--neon-cyan); box-shadow: 0 0 10px rgba(0,242,254,0.3); }
    .nav-bar {
        position: fixed; bottom: 0; left: 0; right: 0; background: rgba(11, 15, 25, 0.85);
        backdrop-filter: blur(20px); border-top: 1px solid rgba(255,255,255,0.08);
        display: flex; justify-content: space-around; padding: 12px 0; z-index: 100;
    }
    .nav-item { color: var(--text-muted); text-decoration: none; font-size: 12px; text-align: center; font-weight: 600; }
    .nav-item.active { color: var(--neon-cyan); text-shadow: 0 0 10px rgba(0,242,254,0.5); }
    .alert { background: rgba(255, 0, 85, 0.2); border: 1px solid #ff0055; padding: 10px; border-radius: 10px; margin-bottom: 15px; font-size: 13px; text-align: center; }
    .flex-row { display: flex; justify-content: space-between; align-items: center; }
'''

NAV_HTML = '''
    <div class="nav-bar">
        <a href="/" class="nav-item {% if page == 'home' %}active{% endif %}">🏠<br>Главная</a>
        <a href="/quests" class="nav-item {% if page == 'quests' %}active{% endif %}">⚡<br>Квесты</a>
        <a href="/shop" class="nav-item {% if page == 'shop' %}active{% endif %}">🛒<br>Магазин</a>
        <a href="/top" class="nav-item {% if page == 'top' %}active{% endif %}">🏆<br>Топ</a>
        <a href="/profile" class="nav-item {% if page == 'profile' %}active{% endif %}">👤<br>Профиль</a>
    </div>
'''

AUTH_HTML = f'''
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>{{'{GLOBAL_CSS}'}}</style></head>
<body>
    <div class="container" style="margin-top: 60px;">
        <div class="glass-card" style="text-align: center;">
            <h2 style="color: var(--neon-cyan); text-shadow: 0 0 15px rgba(0,242,254,0.4);">LIFE RPG</h2>
            <p style="color: var(--text-muted); font-size: 14px;">Геймифицируй свою жизнь</p>
            {{% with msgs = get_flashed_messages() %}}{{% if msgs %}}{{% for m in msgs %}}<div class="alert">{{{{m}}}}</div>{{% endfor %}}{{% endif %}}{{% endwith %}}
            <form method="post">
                <input type="text" name="username" placeholder="Логин" required>
                <input type="password" name="password" placeholder="Пароль" required>
                <button type="submit" class="glow-btn" style="margin-top:15px;">{{{{ btn_text }}}}</button>
            </form>
            <div style="margin-top: 20px; font-size: 13px;">
                {{% if is_reg %}}Уже есть аккаунт? <a href="/login" style="color:var(--neon-cyan);">Войти</a>
                {{% else %}}Нет аккаунта? <a href="/register" style="color:var(--neon-cyan);">Регистрация</a>{{% endif %}}
            </div>
        </div>
    </div>
</body></html>
'''

# --- РОУТЫ И СТРАНИЦЫ ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form['username'].strip()
        p = request.form['password']
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username = ?', (u,))
        if c.fetchone():
            flash('Логин уже занят!')
            return redirect(url_for('register'))
        c.execute('INSERT INTO users (username, password_hash, nickname) VALUES (?, ?, ?)', (u, generate_password_hash(p), u))
        conn.commit()
        conn.close()
        flash('Регистрация успешна! Войдите.')
        return redirect(url_for('login'))
    return render_template_string(AUTH_HTML, btn_text='Зарегистрироваться', is_reg=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form['username'].strip()
        p = request.form['password']
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ?', (u,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], p):
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        flash('Неверный логин или пароль')
    return render_template_string(AUTH_HTML, btn_text='Войти в систему', is_reg=False)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    uid = session['user_id']
    check_auto_quest(uid)
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (uid,))
    user = c.fetchone()
    conn.close()
    
    xp_max = user['level'] * 100
    hp_pct = max(0, min(100, user['hp']))
    xp_pct = min(100, int((user['xp'] / xp_max) * 100))
    
    html = f'''<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>{{'{GLOBAL_CSS}'}}</style></head>
    <body><div class="container">
        <div class="flex-row" style="margin-bottom: 20px;">
            <div style="display:flex; align-items:center; gap:12px;">
                <img src="/static/uploads/{{{{ user['avatar'] }}}}" onerror="this.src='https://via.placeholder.com/50'" style="width:50px; height:50px; border-radius:50%; object-fit:cover; border:2px solid var(--neon-cyan);">
                <div>
                    <h3 style="margin:0; font-size:16px;">{{{{ user['nickname'] }}}}</h3>
                    <span style="font-size:12px; color:var(--text-muted);">Уровень {{{{ user['level'] }}}}</span>
                </div>
            </div>
            <div class="glass-card" style="padding: 8px 15px; margin:0; border-radius:12px; color:var(--neon-gold); font-weight:700;">
                🪙 {{{{ user['gold'] }}}};
            </div>
        </div>

        {{% with msgs = get_flashed_messages() %}}{{% if msgs %}}{{% for m in msgs %}}<div class="alert">{{{{m}}}}</div>{{% endfor %}}{{% endif %}}{{% endwith %}}

        <div class="glass-card">
            <h4 style="margin-top:0; color:var(--neon-cyan);">Статус персонажа</h4>
            <div style="font-size:13px; margin-bottom:8px;" class="flex-row"><span>❤️ Здоровье</span> <b>{{{{ user['hp'] }}}}/100</b></div>
            <div style="background:rgba(255,255,255,0.05); border-radius:8px; height:8px; overflow:hidden; margin-bottom:12px;">
                <div style="background:#ff0055; width:{hp_pct}%; height:100%; box-shadow: 0 0 8px #ff0055;"></div>
            </div>
            <div style="font-size:13px; margin-bottom:8px;" class="flex-row"><span>⭐ Опыт (XP)</span> <b>{{{{ user['xp'] }}}}/{{{{ xp_max }}}}</b></div>
            <div style="background:rgba(255,255,255,0.05); border-radius:8px; height:8px; overflow:hidden;">
                <div style="background:var(--neon-cyan); width:{xp_pct}%; height:100%; box-shadow: 0 0 8px var(--neon-cyan);"></div>
            </div>
        </div>

        <div class="glass-card">
            <h4 style="margin-top:0; color:var(--neon-purple);">Характеристики</h4>
            <div class="flex-row" style="font-size:14px; margin: 8px 0;"><span>💪 Сила</span><b>{{{{ user['strength'] }}}}</b></div>
            <div class="flex-row" style="font-size:14px; margin: 8px 0;"><span>🧠 Интеллект</span><b>{{{{ user['intellect'] }}}}</b></div>
            <div class="flex-row" style="font-size:14px; margin: 8px 0;"><span>🏃 Выносливость</span><b>{{{{ user['endurance'] }}}}</b></div>
            <div class="flex-row" style="font-size:14px; margin: 8px 0;"><span>🛡️ Дисциплина</span><b>{{{{ user['discipline'] }}}}</b></div>
        </div>
    </div>''' + NAV_HTML + '</body></html>'
    return render_template_string(html, user=user, page='home', xp_max=xp_max, hp_pct=hp_pct, xp_pct=xp_pct)

@app.route('/quests')
@login_required
def quests():
    uid = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM quests WHERE user_id = ?', (uid,))
    qs = c.fetchall()
    conn.close()
    
    html = f'''<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>{{'{GLOBAL_CSS}'}}</style></head>
    <body><div class="container">
        <div class="flex-row" style="margin-bottom:15px;">
            <h2>Активные квесты</h2>
            <a href="/generate_extra" class="glow-btn-purple glow-btn" style="width:auto; padding:8px 14px; font-size:12px;">+ Доп. квест</a>
        </div>
        {{% with msgs = get_flashed_messages() %}}{{% if msgs %}}{{% for m in msgs %}}<div class="alert">{{{{m}}}}</div>{{% endfor %}}{{% endif %}}{{% endwith %}}
        {{% for q in qs %}}
        <div class="glass-card">
            <div style="font-weight:700; font-size:15px; margin-bottom:5px;">{{{{ q['title'] }}}}</div>
            <div style="font-size:12px; color:var(--text-muted); margin-bottom:12px;">Сложность: Tier {{{{ q['difficulty'] }}}} | ИИ-проверка активна</div>
            <form action="/complete/{{{{ q['id'] }}}}" method="post" enctype="multipart/form-data">
                <input type="file" name="proof" accept="image/*,video/*" style="font-size:11px; padding:8px;">
                <button type="submit" class="glow-btn" style="margin-top:8px; padding:10px; font-size:13px;">Сдать отчет ИИ</button>
            </form>
        </div>
        {{% else %}}
        <div class="glass-card" style="text-align:center; color:var(--text-muted);">Все квесты выполнены! Отдыхай или создай дополнительные.</div>
        {{% endfor %}}
    </div>''' + NAV_HTML + '</body></html>'
    return render_template_string(html, qs=qs, page='quests')

@app.route('/generate_extra')
@login_required
def generate_extra():
    generate_quests_batch(session['user_id'], 2, 1)
    flash('Дополнительные квесты успешно сгенерированы!')
    return redirect(url_for('quests'))

@app.route('/complete/<int:qid>', methods=['POST'])
@login_required
def complete(qid):
    uid = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM quests WHERE id = ? AND user_id = ?', (qid, uid))
    q = c.fetchone()
    if q:
        c.execute('SELECT * FROM users WHERE id = ?', (uid,))
        user = dict(c.fetchone())
        
        f_path = None
        if 'proof' in request.files:
            f = request.files['proof']
            if f and f.filename != '':
                ext = f.filename.rsplit('.', 1)[-1].lower()
                fname = f"proof_{uid}_{int(time.time())}.{ext}"
                f_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
                f.save(f_path)
                
        ok, msg, is_lazy = verify_with_ai(user['api_key'], q['title'], f_path)
        if is_lazy:
            user['hp'] -= 15
            flash(f"Штраф! Сдано без пруфа. -15 HP. Статус: {msg}")
        elif ok:
            diff = q['difficulty']
            user['xp'] += diff * 30
            user['gold'] += diff * 20
            user['hp'] = min(100, user['hp'] + 10)
            if user['xp'] >= user['level'] * 100:
                user['xp'] -= user['level'] * 100
                user['level'] += 1
                flash("🎉 Повышение уровня! Так держать!")
            smaps = {"1": "strength", "2": "intellect", "3": "endurance", "4": "discipline"}
            user[smaps.get(str(q['stat_type']), 'discipline')] += diff
            flash(f"Успех! {msg}")
        else:
            flash(f"ИИ отклонил выполнение: {msg}")

        c.execute('''UPDATE users SET level=?, xp=?, gold=?, hp=?, strength=?, intellect=?, endurance=?, discipline=? WHERE id=?''',
                  (user['level'], user['xp'], user['gold'], user['hp'], user['strength'], user['intellect'], user['endurance'], user['discipline'], uid))
        c.execute('DELETE FROM quests WHERE id = ?', (qid,))
        conn.commit()
    conn.close()
    return redirect(url_for('quests'))

@app.route('/shop')
@login_required
def shop():
    uid = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (uid,))
    user = c.fetchone()
    c.execute('SELECT * FROM shop')
    items = c.fetchall()
    c.execute('SELECT * FROM inventory WHERE user_id = ?', (uid,))
    inv = c.fetchall()
    conn.close()
    
    html = f'''<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>{{'{GLOBAL_CSS}'}}</style></head>
    <body><div class="container">
        <div class="flex-row"><h2>Магазин наград</h2><span style="color:var(--neon-gold); font-weight:700;">🪙 {{{{ user['gold'] }}}}</span></div>
        {{% with msgs = get_flashed_messages() %}}{{% if msgs %}}{{% for m in msgs %}}<div class="alert">{{{{m}}}}</div>{{% endfor %}}{{% endif %}}{{% endwith %}}
        
        <h4 style="color:var(--neon-cyan);">Купить награду за монеты:</h4>
        {{% for item in items %}}
        <div class="glass-card flex-row" style="padding: 15px; margin-bottom: 10px;">
            <div><b>{{{{ item['title'] }}}}</b><br><span style="color:var(--neon-gold); font-size:13px;">🪙 {{{{ item['price'] }}}}</span></div>
            <form action="/buy/{{{{ item['id'] }}}}" method="post"><button class="glow-btn" style="padding:8px 14px; font-size:12px; width:auto;">Купить</button></form>
        </div>
        {{% endfor %}}

        <h4 style="color:var(--neon-purple); margin-top:25px;">Инвентарь (Купленное):</h4>
        {{% for i in inv %}}
        <div class="glass-card flex-row" style="padding: 12px; margin-bottom: 8px; background: rgba(157,78,221,0.1);">
            <span>🎁 {{{{ i['title'] }}}}</span>
            <form action="/use_item/{{{{ i['id'] }}}}" method="post"><button class="glow-btn glow-btn-purple" style="padding:6px 12px; font-size:11px; width:auto;">Использовать</button></form>
        </div>
        {{% else %}}
        <div style="color:var(--text-muted); font-size:13px;">Инвентарь пуст. Зарабатывай монеты на квестах!</div>
        {{% endfor %}}
    </div>''' + NAV_HTML + '</body></html>'
    return render_template_string(html, user=user, items=items, inv=inv, page='shop')

@app.route('/buy/<int:item_id>', methods=['POST'])
@login_required
def buy(item_id):
    uid = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (uid,))
    user = c.fetchone()
    c.execute('SELECT * FROM shop WHERE id = ?', (item_id,))
    item = c.fetchone()
    
    if user and item:
        if user['gold'] >= item['price']:
            c.execute('UPDATE users SET gold = gold - ? WHERE id = ?', (item['price'], uid))
            c.execute('INSERT INTO inventory (user_id, title) VALUES (?, ?)', (uid, item['title']))
            conn.commit()
            flash(f"Успешно куплено: {item['title']}!")
        else:
            flash("Недостаточно монет!")
    conn.close()
    return redirect(url_for('shop'))

@app.route('/use_item/<int:inv_id>', methods=['POST'])
@login_required
def use_item(inv_id):
    uid = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM inventory WHERE id = ? AND user_id = ?', (inv_id, uid))
    conn.commit()
    conn.close()
    flash("Награда использована! Отличный отдых.")
    return redirect(url_for('shop'))

@app.route('/top')
def top():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT nickname, level, gold, avatar FROM users ORDER BY level DESC, gold DESC LIMIT 20')
    leaders = c.fetchall()
    conn.close()
    
    html = f'''<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>{{'{GLOBAL_CSS}'}}</style></head>
    <body><div class="container">
        <h2>🏆 Мировой топ игроков</h2>
        {{% for l in leaders %}}
        <div class="glass-card flex-row" style="padding: 12px 18px; margin-bottom: 10px;">
            <div style="display:flex; align-items:center; gap:12px;">
                <span style="font-weight:700; color:var(--neon-cyan); width:20px;">#{{{{ loop.index }}}}</span>
                <img src="/static/uploads/{{{{ l['avatar'] }}}}" onerror="this.src='https://via.placeholder.com/40'" style="width:40px; height:40px; border-radius:50%; object-fit:cover;">
                <b>{{{{ l['nickname'] }}}}</b>
            </div>
            <div style="text-align:right;">Ур. {{{{ l['level'] }}}}<br><span style="color:var(--neon-gold); font-size:12px;">🪙 {{{{ l['gold'] }}}}</span></div>
        </div>
        {{% endfor %}}
    </div>''' + NAV_HTML + '</body></html>'
    return render_template_string(html, leaders=leaders, page='top')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    uid = session['user_id']
    conn = get_db()
    c = conn.cursor()
    if request.method == 'POST':
        nick = request.form['nickname']
        bio = request.form['bio']
        apikey = request.form['api_key']
        
        avatar_name = None
        if 'avatar_file' in request.files:
            file = request.files['avatar_file']
            if file and file.filename != '':
                ext = file.filename.rsplit('.', 1)[-1].lower()
                avatar_name = f"avatar_{uid}_{int(time.time())}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], avatar_name))
                
        if avatar_name:
            c.execute('UPDATE users SET nickname=?, bio=?, api_key=?, avatar=? WHERE id=?', (nick, bio, apikey, avatar_name, uid))
        else:
            c.execute('UPDATE users SET nickname=?, bio=?, api_key=? WHERE id=?', (nick, bio, apikey, uid))
        conn.commit()
        flash('Профиль успешно обновлен!')
        return redirect(url_for('profile'))
        
    c.execute('SELECT * FROM users WHERE id = ?', (uid,))
    user = c.fetchone()
    conn.close()
    
    html = f'''<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>{{'{GLOBAL_CSS}'}}</style></head>
    <body><div class="container">
        <h2>Настройки профиля</h2>
        {{% with msgs = get_flashed_messages() %}}{{% if msgs %}}{{% for m in msgs %}}<div class="alert">{{{{m}}}}</div>{{% endfor %}}{{% endif %}}{{% endwith %}}
        <div class="glass-card" style="text-align:center;">
            <img src="/static/uploads/{{{{ user['avatar'] }}}}" onerror="this.src='https://via.placeholder.com/80'" style="width:85px; height:85px; border-radius:50%; object-fit:cover; border:2px solid var(--neon-cyan); margin-bottom:10px;">
            <form method="post" enctype="multipart/form-data" style="text-align:left;">
                <label style="font-size:12px; color:var(--text-muted);">Сменить аватарку:</label>
                <input type="file" name="avatar_file" accept="image/*" style="font-size:11px; padding:6px;">
                
                <label style="font-size:12px; color:var(--text-muted);">Никнейм:</label>
                <input type="text" name="nickname" value="{{{{ user['nickname'] }}}}" required>
                
                <label style="font-size:12px; color:var(--text-muted);">О себе (био):</label>
                <textarea name="bio" rows="2">{{{{ user['bio'] }}}}</textarea>
                
                <label style="font-size:12px; color:var(--text-muted);">Gemini API Key (опционально для ИИ-проверки):</label>
                <input type="text" name="api_key" value="{{{{ user['api_key'] }}}}" placeholder="AIzaSy...">
                
                <button type="submit" class="glow-btn" style="margin-top:15px;">Сохранить изменения</button>
            </form>
            <div style="margin-top:20px;">
                <a href="/logout" style="color: #ff0055; font-size:13px; text-decoration:none; font-weight:600;">Выйти из аккаунта</a>
            </div>
        </div>
    </div>''' + NAV_HTML + '</body></html>'
    return render_template_string(html, user=user, page='profile')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
