import os
import psycopg2
import psycopg2.extras
import hashlib
import uuid
import json

# Database connection URL from Render (set in env vars)
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# Create tables if they don’t exist
def db_connect():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            salt TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            userid INTEGER PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            times JSONB,
            solvedCodes JSONB,
            avatar TEXT
        )
    """)
    db.commit()
    cur.close()
    db.close()

# Create a new user
def db_user_create(user: str, pword: str):
    db = get_db()
    cur = db.cursor()

    # Check if user exists
    cur.execute("SELECT count(*) FROM accounts WHERE username = %s", (user,))
    if cur.fetchone()[0] >= 1:
        cur.close()
        db.close()
        return False

    # Encrypt password
    salt = uuid.uuid4().hex[:10]
    p_hash = hashlib.sha256(pword.encode('utf-8') + salt.encode('utf-8')).hexdigest()

    # Insert into accounts
    cur.execute("INSERT INTO accounts (username, password, salt) VALUES (%s, %s, %s) RETURNING id", (user, p_hash, salt))
    user_id = cur.fetchone()[0]

    # Insert profile row
    cur.execute("INSERT INTO profiles (userid, solvedCodes) VALUES (%s, %s)", (user_id, json.dumps([''])))

    db.commit()
    cur.close()
    db.close()
    return True

# Authenticate user
def db_auth_user(user: str, pword: str) -> bool:
    db = get_db()
    cur = db.cursor()
    
    cur.execute("SELECT salt, password FROM accounts WHERE username = %s", (user,))
    row = cur.fetchone()
    if not row:
        cur.close()
        db.close()
        return False

    salt, password = row
    p_hash = hashlib.sha256(pword.encode('utf-8') + salt.encode('utf-8')).hexdigest()

    cur.close()
    db.close()
    return p_hash == password

# Get profile
def get_profile(user: str) -> dict:
    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT id FROM accounts WHERE username = %s", (user,))
    row = cur.fetchone()
    if not row:
        cur.close()
        db.close()
        return False

    user_id = row[0]
    cur.execute("SELECT wins, losses, times, solvedCodes, avatar FROM profiles WHERE userid = %s", (user_id,))
    prof = cur.fetchone()

    cur.close()
    db.close()

    if prof:
        return {
            "username": user,
            "wins": prof["wins"],
            "losses": prof["losses"],
            "times": prof["times"],
            "solvedCodes": prof["solvedcodes"],
            "avatar": prof["avatar"]
        }
    return False

# Update profile
def update_profile(user: str, wins=None, losses=None, times=None, solvedCodes=None, avatar=None, password=None) -> dict:
    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT id FROM accounts WHERE username = %s", (user,))
    user_id = cur.fetchone()[0]

    if wins is not None:
        cur.execute("UPDATE profiles SET wins = %s WHERE userid = %s", (wins, user_id))
    if losses is not None:
        cur.execute("UPDATE profiles SET losses = %s WHERE userid = %s", (losses, user_id))
    if avatar is not None:
        cur.execute("UPDATE profiles SET avatar = %s WHERE userid = %s", (avatar, user_id))
    if times is not None:
        cur.execute("UPDATE profiles SET times = %s WHERE userid = %s", (json.dumps(times), user_id))
    if solvedCodes is not None:
        cur.execute("UPDATE profiles SET solvedCodes = %s WHERE userid = %s", (json.dumps(solvedCodes), user_id))
    if password is not None:
        cur.execute("SELECT salt FROM accounts WHERE username = %s", (user,))
        salt = cur.fetchone()[0]
        p_hash = hashlib.sha256(password.encode('utf-8') + salt.encode('utf-8')).hexdigest()
        cur.execute("UPDATE accounts SET password = %s WHERE id = %s", (p_hash, user_id))

    db.commit()

    cur.execute("SELECT wins, losses, times, solvedCodes, avatar FROM profiles WHERE userid = %s", (user_id,))
    prof = cur.fetchone()

    cur.close()
    db.close()

    return {
        "username": user,
        "wins": prof["wins"],
        "losses": prof["losses"],
        "times": prof["times"],
        "solvedCodes": prof["solvedcodes"],
        "avatar": prof["avatar"]
    }

# Get all usernames
def get_all_usernames() -> list:
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT username FROM accounts ORDER BY username")
    usernames = [row[0] for row in cur.fetchall()]
    cur.close()
    db.close()
    return usernames

# Delete user
def delete_user(user: str):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM accounts WHERE username = %s", (user,))
    db.commit()
    cur.close()
    db.close()

# Add correct code
def correctCodes(user: str, plaintext: str):
    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT id FROM accounts WHERE username = %s", (user,))
    user_id = cur.fetchone()[0]

    cur.execute("SELECT solvedCodes FROM profiles WHERE userid = %s", (user_id,))
    solvedCodes = cur.fetchone()[0] or []
    if isinstance(solvedCodes, str):  # in case JSON not parsed
        solvedCodes = json.loads(solvedCodes)

    solvedCodes.append(plaintext)

    cur.execute("UPDATE profiles SET solvedCodes = %s WHERE userid = %s", (json.dumps(solvedCodes), user_id))
    db.commit()

    cur.execute("SELECT wins, losses, times, solvedCodes, avatar FROM profiles WHERE userid = %s", (user_id,))
    prof = cur.fetchone()

    cur.close()
    db.close()

    return {
        "username": user,
        "wins": prof["wins"],
        "losses": prof["losses"],
        "times": prof["times"],
        "solvedCodes": prof["solvedcodes"],
        "avatar": prof["avatar"]
    }
