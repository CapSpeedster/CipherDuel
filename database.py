import sqlite3
import hashlib
import uuid

__db = None

#connects to database and creates account and profile tables
def db_connect():
    __db=sqlite3.connect("user.db")

    __db.cursor().execute("""CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, username TEXT NOT NULL, password TEXT NOT NULL, salt TEXT)""")
    __db.cursor().execute("""CREATE TABLE IF NOT EXISTS profiles (userid INTEGER PRIMARY KEY NOT NULL, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, times JSON, solvedCodes JSON, avatar TEXT)""")
    # __db.cursor().execute("""CREATE TABLE IF NOT EXISTS ciphers (id INTEGER PRIMARY KEY, plaintext TEXT, keyword TEXT, cipherType TEXT)""")

    __db.commit()

#methods for creating new users

def db_user_create(user:str,pword:str):
    __db=sqlite3.connect("user.db")

    #check if user exists
    response = __db.cursor().execute("""SELECT count(*) FROM accounts WHERE username = ?""", (user,)).fetchone()
    copyNum=0
    for x in response:
        copyNum = int(x)
    if (copyNum>=1):
        return False
    else:
        #encrypt password
        salt = uuid.uuid4().hex[:10]
        p_hash=hashlib.sha256(pword.encode('utf-8')+salt.encode('utf-8')).hexdigest()

        #add row to accounts table
        __db.cursor().execute("""INSERT INTO accounts (username, password, salt) VALUES (?, ?, ?)""", (user, p_hash, salt))
        __db.cursor().execute("""SELECT * FROM accounts""")

        #add corresponding row to profiles table
        response = __db.cursor().execute("""SELECT id FROM accounts where username = ?""", (user,)).fetchone()
        idValue = 0
        for x in response:
            idValue = int(x)
        __db.cursor().execute("""INSERT INTO profiles (userid) VALUES (?)""", (idValue,))

        __db.commit()

#Authenticate username and pasword
def db_auth_user(user:str,pword:str) -> bool:
    __db = sqlite3.connect("user.db")
    
    #check if user exists
    response = __db.cursor().execute("""SELECT count(*) FROM accounts WHERE username = ?""", (user,)).fetchone()
    num=0
    for x in response:
        num = int(x)
    
    if (num>0):
        #create entered password hash with user salt
        response = __db.cursor().execute("""SELECT salt FROM accounts WHERE username = ?""", (user,)).fetchone()
        salt=''
        for x in response:
            salt=str(x)
        p_hash = hashlib.sha256(pword.encode('utf-8') + salt.encode('utf-8')).hexdigest()

        response = __db.cursor().execute("""SELECT password FROM accounts WHERE username = ?""", (user,)).fetchone()
        password=''
        for x in response:
            password=str(x)
        
        #athenticate passwords
        if (p_hash==password):
            return True
        else:
            return False
    else:
        return False
    

#Returns user profile
def get_profile(user:str) -> dict:
    __db = sqlite3.connect("user.db")

    #check if user exists
    response = __db.cursor().execute("""SELECT count(*) FROM accounts WHERE username = ?""", (user,)).fetchone()
    num=0
    for x in response:
        num = int(x)
    
    if (num>0):
        response = __db.cursor().execute("""SELECT id FROM accounts WHERE username = ?""", (user,)).fetchone()
        idValue=0
        for x in response:
            idValue = int(x)

        #Get user profile data
        response = __db.cursor().execute("""SELECT wins, losses, times, solvedCodes, avatar FROM profiles WHERE userid = ?""", (idValue,))
        profileDict = dict({
            'username' : user
        })
        for x in response:
            profileDict['wins'] = x[0]
            profileDict['losses'] = x[1]
            profileDict['times'] = x[2]
            profileDict['solvedCodes'] = x[3]
            profileDict['avatar'] = x[4]

        return profileDict
    else:
        return False

#Updates and returns new user profile
def update_profile(user:str, wins:int=None, losses:int=None, times:list=None, solvedCodes:list=None, avatar:str=None, password:str = None) -> dict:
    __db = sqlite3.connect("user.db")

    response = __db.cursor().execute("""SELECT id FROM accounts WHERE username = ?""", (user,)).fetchone()
    idValue=0
    for x in response:
        idValue=int(x)
    
    #update database
    if wins != None:
        __db.cursor().execute("""UPDATE profiles SET wins = ? WHERE userid = ?""", (wins, idValue))
    if losses != None:
        __db.cursor().execute("""UPDATE profiles SET losses = ? WHERE userid = ?""", (losses, idValue))
    if avatar != None:
        __db.cursor().execute("""UPDATE profiles SET avatar = ? WHERE userid = ?""", (avatar, idValue))
    if times != None:
        __db.cursor().execute("""UPDATE profiles SET times = ? WHERE userid = ?""", (times, idValue))
    if solvedCodes != None:
        __db.cursor().execute("""UPDATE profiles SET solvedCodes = ? WHERE userid = ?""", (solvedCodes, idValue))
    if password != None:
        #encrypt password
        response = __db.cursor().execute("""SELECT salt FROM accounts WHERE username = ?""", (user,)).fetchone()
        salt=''
        for x in response:
            salt=str(x)
        p_hash = hashlib.sha256(password.encode('utf-8') + salt.encode('utf-8')).hexdigest()

        __db.cursor().execute("""UPDATE accounts SET password = ? WHERE id = ?""", (p_hash, idValue))

    __db.commit()

    #get user profile
    response = __db.cursor().execute("""SELECT wins, losses, times, solvedCodes, avatar FROM profiles WHERE userid = ?""", (idValue,))
    profileDict = dict({
        'username' : user
    })
    for x in response:
        profileDict['wins'] = x[0]
        profileDict['losses'] = x[1]
        profileDict['times'] = x[2]
        profileDict['solvedCodes'] = x[3]
        profileDict['avatar'] = x[4]
    return profileDict

#returns list of all account usernames in database
def get_all_usernames() -> list:
    __db = sqlite3.connect("user.db")
    response = __db.cursor().execute("""SELECT username FROM accounts ORDER BY username""")
    usernames = []
    for x in response:
        usernames.append(x[0])
    
    return usernames

#removes user from database
def delete_user(user:str):
    __db = sqlite3.connect('user.db')
    
    response = __db.cursor().execute("""SELECT id FROM accounts WHERE username = ?""", (user,)).fetchone()
    idValue=0
    for x in response:
        idValue=int(x)
    
    __db.cursor().execute("""DELETE FROM accounts WHERE id = ?""", (idValue,))
    __db.cursor().execute("""DELETE FROM profiles WHERE userid = ?""", (idValue,))
    __db.commit()
