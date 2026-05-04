import os
import secrets
import datetime
import sqlite3
from functools import wraps
from flask import Flask, request, jsonify, session, render_template

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'qatar-admin-dev-secret-key-change-in-production')

DATABASE = os.path.join(os.path.dirname(__file__), 'instance', 'qatar.db')


# ─────────────────────────── DB helpers ────────────────────────────

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS admins (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name    TEXT    NOT NULL,
            email        TEXT    UNIQUE NOT NULL,
            password_hash TEXT   NOT NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS opportunities (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id            INTEGER NOT NULL,
            name                TEXT    NOT NULL,
            duration            TEXT    NOT NULL,
            start_date          TEXT    NOT NULL,
            description         TEXT    NOT NULL,
            skills              TEXT    NOT NULL,
            category            TEXT    NOT NULL,
            future_opportunities TEXT   NOT NULL,
            max_applicants      INTEGER,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_id) REFERENCES admins(id)
        );

        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id   INTEGER NOT NULL,
            token      TEXT    UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used       INTEGER DEFAULT 0,
            FOREIGN KEY (admin_id) REFERENCES admins(id)
        );
    ''')
    db.commit()
    db.close()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


def opp_row_to_dict(row):
    return {
        'id':                   row['id'],
        'name':                 row['name'],
        'duration':             row['duration'],
        'start_date':           row['start_date'],
        'description':          row['description'],
        'skills':               [s.strip() for s in row['skills'].split(',') if s.strip()],
        'category':             row['category'],
        'future_opportunities': row['future_opportunities'],
        'max_applicants':       row['max_applicants'],
    }


# ─────────────────────────── Routes ────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ---------- Auth ----------

@app.route('/api/me', methods=['GET'])
def me():
    """Return current session info so the frontend can restore state on reload."""
    if 'admin_id' not in session:
        return jsonify({'logged_in': False}), 200
    return jsonify({
        'logged_in': True,
        'admin': {
            'name':  session.get('admin_name'),
            'email': session.get('admin_email'),
        }
    })


@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json() or {}
    full_name = data.get('full_name', '').strip()
    email     = data.get('email', '').strip().lower()
    password  = data.get('password', '')

    if not full_name or not email or not password:
        return jsonify({'error': 'All fields are required'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    from werkzeug.security import generate_password_hash
    db = get_db()
    try:
        existing = db.execute('SELECT id FROM admins WHERE email = ?', (email,)).fetchone()
        if existing:
            return jsonify({'error': 'An account with this email already exists'}), 409
        db.execute(
            'INSERT INTO admins (full_name, email, password_hash) VALUES (?, ?, ?)',
            (full_name, email, generate_password_hash(password))
        )
        db.commit()
        return jsonify({'message': 'Account created successfully'}), 201
    finally:
        db.close()


@app.route('/api/login', methods=['POST'])
def login():
    data        = request.get_json() or {}
    email       = data.get('email', '').strip().lower()
    password    = data.get('password', '')
    remember_me = data.get('remember_me', False)

    from werkzeug.security import check_password_hash
    db    = get_db()
    admin = db.execute('SELECT * FROM admins WHERE email = ?', (email,)).fetchone()
    db.close()

    if not admin or not check_password_hash(admin['password_hash'], password):
        return jsonify({'error': 'Invalid email or password'}), 401

    session['admin_id']    = admin['id']
    session['admin_email'] = admin['email']
    session['admin_name']  = admin['full_name']

    if remember_me:
        app.permanent_session_lifetime = datetime.timedelta(days=30)
        session.permanent = True
    else:
        session.permanent = False

    return jsonify({
        'message': 'Login successful',
        'admin':   {'name': admin['full_name'], 'email': admin['email']}
    })


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})


@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    data  = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    db    = get_db()
    admin = db.execute('SELECT id FROM admins WHERE email = ?', (email,)).fetchone()

    if admin:
        token      = secrets.token_urlsafe(32)
        expires_at = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat()
        db.execute(
            'INSERT INTO password_reset_tokens (admin_id, token, expires_at) VALUES (?, ?, ?)',
            (admin['id'], token, expires_at)
        )
        db.commit()
        reset_link = f"http://localhost:5000/reset-password?token={token}"
        print(f"[PASSWORD RESET] Reset link for {email}: {reset_link}", flush=True)

    db.close()
    # Always return the same message to protect privacy
    return jsonify({'message': 'If this email is registered, a reset link has been sent'})


@app.route('/api/reset-password', methods=['GET'])
def validate_reset_token():
    token = request.args.get('token', '')
    db    = get_db()
    reset = db.execute(
        'SELECT * FROM password_reset_tokens WHERE token=? AND used=0 AND expires_at>?',
        (token, datetime.datetime.utcnow().isoformat())
    ).fetchone()
    db.close()
    if not reset:
        return jsonify({'error': 'Invalid or expired reset link'}), 400
    return jsonify({'message': 'Token is valid'})


@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    from werkzeug.security import generate_password_hash
    data         = request.get_json() or {}
    token        = data.get('token', '')
    new_password = data.get('password', '')

    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    db    = get_db()
    reset = db.execute(
        'SELECT * FROM password_reset_tokens WHERE token=? AND used=0 AND expires_at>?',
        (token, datetime.datetime.utcnow().isoformat())
    ).fetchone()

    if not reset:
        db.close()
        return jsonify({'error': 'Invalid or expired reset link'}), 400

    db.execute('UPDATE admins SET password_hash=? WHERE id=?',
               (generate_password_hash(new_password), reset['admin_id']))
    db.execute('UPDATE password_reset_tokens SET used=1 WHERE id=?', (reset['id'],))
    db.commit()
    db.close()
    return jsonify({'message': 'Password reset successfully'})


# ---------- Opportunities ----------

@app.route('/api/opportunities', methods=['GET'])
@login_required
def get_opportunities():
    db   = get_db()
    rows = db.execute(
        'SELECT * FROM opportunities WHERE admin_id=? ORDER BY created_at DESC',
        (session['admin_id'],)
    ).fetchall()
    db.close()
    return jsonify({'opportunities': [opp_row_to_dict(r) for r in rows]})


@app.route('/api/opportunities', methods=['POST'])
@login_required
def create_opportunity():
    data = request.get_json() or {}

    name                 = data.get('name', '').strip()
    duration             = data.get('duration', '').strip()
    start_date           = data.get('start_date', '').strip()
    description          = data.get('description', '').strip()
    skills               = data.get('skills', [])
    category             = data.get('category', '').strip()
    future_opportunities = data.get('future_opportunities', '').strip()
    max_applicants       = data.get('max_applicants') or None

    if not all([name, duration, start_date, description, skills, category, future_opportunities]):
        return jsonify({'error': 'All required fields must be filled'}), 400

    skills_str = ','.join(skills) if isinstance(skills, list) else skills

    db     = get_db()
    cursor = db.execute(
        '''INSERT INTO opportunities
           (admin_id,name,duration,start_date,description,skills,category,future_opportunities,max_applicants)
           VALUES (?,?,?,?,?,?,?,?,?)''',
        (session['admin_id'], name, duration, start_date, description,
         skills_str, category, future_opportunities, max_applicants)
    )
    new_id = cursor.lastrowid
    db.commit()
    row = db.execute('SELECT * FROM opportunities WHERE id=?', (new_id,)).fetchone()
    db.close()
    return jsonify({'message': 'Opportunity created', 'opportunity': opp_row_to_dict(row)}), 201


@app.route('/api/opportunities/<int:opp_id>', methods=['PUT'])
@login_required
def update_opportunity(opp_id):
    db  = get_db()
    opp = db.execute(
        'SELECT * FROM opportunities WHERE id=? AND admin_id=?',
        (opp_id, session['admin_id'])
    ).fetchone()
    if not opp:
        db.close()
        return jsonify({'error': 'Opportunity not found or access denied'}), 404

    data = request.get_json() or {}
    name                 = data.get('name', '').strip()
    duration             = data.get('duration', '').strip()
    start_date           = data.get('start_date', '').strip()
    description          = data.get('description', '').strip()
    skills               = data.get('skills', [])
    category             = data.get('category', '').strip()
    future_opportunities = data.get('future_opportunities', '').strip()
    max_applicants       = data.get('max_applicants') or None

    if not all([name, duration, start_date, description, skills, category, future_opportunities]):
        db.close()
        return jsonify({'error': 'All required fields must be filled'}), 400

    skills_str = ','.join(skills) if isinstance(skills, list) else skills

    db.execute(
        '''UPDATE opportunities SET name=?,duration=?,start_date=?,description=?,
           skills=?,category=?,future_opportunities=?,max_applicants=?
           WHERE id=? AND admin_id=?''',
        (name, duration, start_date, description, skills_str, category,
         future_opportunities, max_applicants, opp_id, session['admin_id'])
    )
    db.commit()
    row = db.execute('SELECT * FROM opportunities WHERE id=?', (opp_id,)).fetchone()
    db.close()
    return jsonify({'message': 'Opportunity updated', 'opportunity': opp_row_to_dict(row)})


@app.route('/api/opportunities/<int:opp_id>', methods=['DELETE'])
@login_required
def delete_opportunity(opp_id):
    db  = get_db()
    opp = db.execute(
        'SELECT * FROM opportunities WHERE id=? AND admin_id=?',
        (opp_id, session['admin_id'])
    ).fetchone()
    if not opp:
        db.close()
        return jsonify({'error': 'Opportunity not found or access denied'}), 404

    db.execute('DELETE FROM opportunities WHERE id=? AND admin_id=?',
               (opp_id, session['admin_id']))
    db.commit()
    db.close()
    return jsonify({'message': 'Opportunity deleted successfully'})


# ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
