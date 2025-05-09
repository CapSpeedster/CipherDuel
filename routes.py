from flask import Flask, jsonify, Response, request, send_file, redirect, render_template, make_response, flash
import database
import redis
import uuid
import json
import os
from pathlib import Path
import csv
import random
import codes

# Connect to Redis
R_Server = redis.StrictRedis()
try:
    R_Server.ping()
except:
    print("REDIS: Not Running -- No Streams Available")
    R_Server = None

if R_Server.get('matches'):
    R_Server.delete('matches')

#Routes to be connected in app.py
def connect_routes(blueprint):
    @blueprint.route("/")
    def index():
        #Redirects to login or profile depending on user login status
        userID = request.cookies.get('userid')
        if userID == None:
            return redirect('/login')
        else:
            user = json.loads(R_Server.get(userID))['username']
            return redirect(f'/profile/{user}')

    @blueprint.route("/form", methods=['GET', 'POST'])
    def postIndex():
        print( request.args.get('user') )
        print( request.form.get('user') )   
        return send_file('static/form.html')


    @blueprint.route("/login", methods=["GET", "POST"])
    def loginPage():
        """
        GET: returns login template if not logged in or redirects to the logged in user's profile
        POST: registers user to database or authorizes user login and redirects to user's profile with a session cookie
        """
        if request.method == "GET":
            userID = request.cookies.get('userid')
            if userID == None:
                return render_template('login.j2')
            else:
                return redirect(f'/profile/{json.loads(R_Server.get(userID))['username']}')
    
        fields = ['username', 'password', 'mode']
        for field in fields:
            if field not in request.form:
                return "ERROR 1"
            if len(str(request.form.get(field)).strip()) == 0:
                return "ERROR 2"
    
        if request.form.get('mode') not in ['login', 'register']:
            return "ERROR 3"
        
        username = request.form.get('username')
        password = request.form.get('password')
        mode = request.form.get('mode')

        print(request.form.get('username'))
        print(request.form.get('password'))
        print('MODE:', str(request.form.get('mode')).upper())

        database.db_connect()
        
        #Registers new user to database
        if mode == 'register':
            if(database.db_user_create(username, password)==False):
                flash('ERROR: Account already exists. The username must be unique', 'error')
                return redirect('/login')
            else:
                #Set the cookie
                sessionID = uuid.uuid4()
                profile = database.get_profile(username)
                R_Server.set(str(sessionID), json.dumps(profile))

                resp = make_response(redirect('/cipherselection'))
                resp.set_cookie('userid', str(sessionID))
                return resp

        #Authenticats and logs in existing user
        elif mode == 'login':
            if (database.db_auth_user(username, password)): 
                #Set the cookie
                sessionID = uuid.uuid4()
                profile = database.get_profile(username)
                R_Server.set(str(sessionID), json.dumps(profile))

                resp = make_response(redirect('/cipherselection'))
                resp.set_cookie('userid', str(sessionID))
                return resp
            else:
                flash('ERROR: Incorrect username or password', 'error')
                return redirect('/login')
    
    @blueprint.route("/profile")
    def profilePage():
        #Returns list of all usernames and respective profile pages in the database 
        userID = request.cookies.get('userid')
        names = database.get_all_usernames()
        print(names)
        if userID == None:
            return redirect('/login')
        else:
            return render_template('profilelist.j2', names=names)
    
    @blueprint.route("/profile/<user>", methods=['GET'])
    def userProfile(user):
        """
        Returns user's profile page
        in read only if the current user is not the subject of the page
        else return editable profile
        """
        userID = request.cookies.get('userid')
        if userID == None: 
            return redirect('/login')
        else: 
            profile = database.get_profile(user)
            if profile == False:
                return redirect('/profile')
            else: 
                #check if current user is the same as the profile page's user
                bestTime=profile['times']
                if bestTime != None:
                    for i in profile:
                        if bestTime>i:
                            bestTime=i
                currentUser = json.loads(R_Server.get(userID))['username']
                readonly = True
                if json.loads(R_Server.get(userID))==profile:
                    readonly = False
                return render_template('profile.j2', profile=profile, username=user, readonly=readonly, cUser=currentUser, bestTime=bestTime)

    @blueprint.route("/profile/<user>", methods = ['POST'])
    def changeProfile(user):
        """
        Updates profile page and database based on form data:
        name: updates fname and lname
        avatar: updates avatar if it's .jpeg or .png
        pword: confirms current passwords and updates with new password
        """
        userID = request.cookies.get('userid')
        if userID == None: 
            return redirect('/login')
        else:
            mode = request.form.get('mode')
            profile=dict()
            if mode == 'avatar':
                avatar = request.files['avatar']
                if avatar == None:
                    return 'ERROR: Incomplete Data'
                else:
                    if Path(avatar.filename).suffix == '.jpeg' or Path(avatar.filename).suffix == '.png':
                        #adds uploaded file to the avatars folder and updates the name
                        avatar.save(os.path.join('static/avatars', avatar.filename))
                        if os.path.isfile(f'static/avatars/{user}_avatar{Path(avatar.filename).suffix}'):
                            os.remove(f'static/avatars/{user}_avatar{Path(avatar.filename).suffix}')
                        os.rename(f'static/avatars/{avatar.filename}', f'static/avatars/{user}_avatar{Path(avatar.filename).suffix}')
                        profile = database.update_profile(user, avatar=f'{user}_avatar{Path(avatar.filename).suffix}')
                    else:
                        profile = database.get_profile(user)
                        flash('ERROR: Incorrect File Type. Needs to be .png or .jpeg', 'error')
            if mode == 'pword':
                pconfirm = request.form.get('pconfirm')
                pword = request.form.get('newpword')
                if pconfirm == None or pword == None:
                    return 'ERROR: Incomplete Data'
                else: 
                    #Authenticate username and password and updates database with new password
                    if database.db_auth_user(user, pconfirm):
                        profile=database.update_profile(user, password=pword)
                    else: 
                        profile = database.get_profile(user)
                        flash('ERROR: Incorrect Username or Password', 'error')

            R_Server.set(userID, json.dumps(profile))

            return redirect(f'/profile/{user}')

    @blueprint.route("/logout")
    def logout():
        #terminates user's session cookie and logs them out
        userID = request.cookies.get('userid')
        if userID == None:
            return redirect('/login')
        else:
            resp = make_response(redirect('/login'))
            resp.set_cookie('userid', '', expires=1)
            return resp
    
    @blueprint.route("/profile/<user>", methods = ['DELETE'])
    def deleteProfile(user):
        #Deletes user's profile on the database and removes their avatar from the avatars folder
        userID = request.cookies.get('userid')
        if userID == None:
            return jsonify({'status' : 'error', 'data' : 'user not logged in'})
        else: 
            database.delete_user(user)
            os.remove(f'static/avatars/{json.loads(R_Server.get(userID))['avatar']}')
            resp = make_response(jsonify({'status' : 'success', 'data' : f'{user} has been deleted'}))
            resp.set_cookie('userid', '', expires=0)
            return resp
    
    @blueprint.route("/patristocrat")
    def getPat():
        userID = request.cookies.get('userid')
        matchID = request.cookies.get('matchid')
        if userID == None:
            return redirect('/login')
        else:
            if matchID == None:
                return redirect('/lobby')
            else:
                with open('static/ciphers.csv', mode='r') as file:
                    csv_reader = csv.DictReader(file)
                    ciphers = []
                    for i in csv_reader:
                        ciphers.append(i)

                solvedCodes = json.loads(json.loads(R_Server.get(userID))['solvedCodes'])

                newCiphers = []
                for i in ciphers:
                    if i['plaintext'] not in solvedCodes:
                        newCiphers.append(i)
                if len(newCiphers) == 0:
                    return "You have completed all of our current ciphers. Wait for future updates to proceed." #Create j2 file with button to return to profile

                else: 
                    keys=R_Server.get(userID+'pat1')
                    if keys==None:
                        randint = random.randint(0, len(newCiphers)-1)
                        plaintext = newCiphers[randint]['plaintext']
                        keyword = newCiphers[randint]['keyword']
                        isK2=False
                        if newCiphers[randint]['cipherType'] == 'k2':
                            isK2=True
                        shift = random.randint(0, 25)
                        currentCode = dict(
                            {
                                'plaintext': plaintext,
                                'key': keyword, 
                                'shift': shift
                             })
                        R_Server.set(userID+'pat1', json.dumps(currentCode))
                    else:
                        plaintext = json.loads(keys)['plaintext']
                        keyword = json.loads(keys)['key']
                        shift = json.loads(keys)['shift']

                    if isK2:
                        letters = list(codes.patristok2(plaintext, keyword, shift))
                        frequency = codes.get_frequency(codes.patristok2(plaintext, keyword, shift))
                    else:
                        letters = list(codes.patristok1(plaintext, keyword, shift))
                        frequency = codes.get_frequency(codes.patristok1(plaintext, keyword, shift))
                    
                    LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                    freqDict = dict()
                    for i in range(0, 26):
                        freqDict[LETTERS[i]]=frequency[i]

                    return render_template('cipherpage.j2', letters=letters, profile=json.loads(R_Server.get(userID)), route='/patristocrat', freqDict=freqDict, isK2=isK2)
   
    
    @blueprint.route('/patristocrat-k1-solo')
    def soloPat():
        userID = request.cookies.get('userid')
        if userID == None:
            return redirect('/login')
        else:
            userID = request.cookies.get('userid')
        if userID == None:
            return redirect('/login')
        else:
            with open('static/ciphers.csv', mode='r') as file:
                csv_reader = csv.DictReader(file)
                ciphers = []
                for i in csv_reader:
                    ciphers.append(i)
            
            patCiphers = []
            for i in range(len(ciphers)):
                if ciphers[i]['cipherType']=='k1':
                    patCiphers.append(ciphers[i])

            solvedCodes = json.loads(json.loads(R_Server.get(userID))['solvedCodes'])
            
            newCiphers = []
            for i in patCiphers:
                if i['plaintext'] not in solvedCodes:
                    newCiphers.append(i)
            
            if len(newCiphers) == 0:
                return "You have completed all of our current ciphers. Wait for future updates to proceed." #Create j2 file with button to return to profile

            else: 
                keys=R_Server.get(userID+'pat1s')
                if keys==None:
                    randint = random.randint(0, len(newCiphers)-1)
                    plaintext = newCiphers[randint]['plaintext']
                    keyword = newCiphers[randint]['keyword']
                    shift = random.randint(0, 25)
                    currentCode = dict(
                        {
                            'plaintext': plaintext,
                            'key': keyword, 
                            'shift': shift
                         })
                    R_Server.set(userID+'pat1s', json.dumps(currentCode))
                else:
                    plaintext = json.loads(keys)['plaintext']
                    keyword = json.loads(keys)['key']
                    shift = json.loads(keys)['shift']
                letters = list(codes.patristok1(plaintext, keyword, shift))
                frequency = codes.get_frequency(codes.patristok1(plaintext, keyword, shift))
                LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                freqDict = dict()

                for i in range(0, 26):
                    freqDict[LETTERS[i]]=frequency[i]

                return render_template('cipherpage.j2', letters=letters, profile=json.loads(R_Server.get(userID)), route='/patristocrat-k1-solo', freqDict=freqDict, isK2=False)
    
    @blueprint.route("/patristocrat-k1-solo", methods=['POST'])
    def checkPat():
        userID = request.cookies.get('userid')
        username = json.loads(R_Server.get(userID))['username']
        keys = json.loads(R_Server.get(userID+'pat1s'))
        cipherbet=codes.form_cipher(keys['key'], int(keys['shift']))
        inputLetters = request.form
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        correct = True

        for i in list(codes.text_clean(codes.patristok1(keys['plaintext'], keys['key'], keys['shift']))):
            index=cipherbet.index(i)
            if inputLetters.get(i) == None or inputLetters.get(i)==alphabet[index]:
                continue
            else:
                correct = False
                break
        
        if correct:
            flash('Correct Solution!', 'check')
            R_Server.set(userID, json.dumps(database.correctCodes(username, keys['plaintext'])))
            R_Server.delete(userID+'pat1s')
        else:
            flash("Incorrect Solution. Please try again.", 'check')

        return redirect('/patristocrat-k1-solo')

    @blueprint.route("/patristocrat-k2-solo")
    def soloAri():
        userID = request.cookies.get('userid')
        if userID == None:
            return redirect('/login')
        else:
            with open('static/ciphers.csv', mode='r') as file:
                csv_reader = csv.DictReader(file)
                ciphers = []
                for i in csv_reader:
                    ciphers.append(i)
            
            k2Ciphers = []
            for i in range(len(ciphers)):
                if ciphers[i]['cipherType']=='k2':
                    k2Ciphers.append(ciphers[i])

            solvedCodes = json.loads(json.loads(R_Server.get(userID))['solvedCodes'])
            
            newCiphers = []
            for i in k2Ciphers:
                if i['plaintext'] not in solvedCodes:
                    newCiphers.append(i)
            
            if len(newCiphers) == 0:
                return "You have completed all of our current ciphers. Wait for future updates to proceed." #Create j2 file with button to return to profile

            else: 
                keys=R_Server.get(userID+'pat2s')
                if keys==None:
                    randint = random.randint(0, len(newCiphers)-1)
                    plaintext = newCiphers[randint]['plaintext']
                    keyword = newCiphers[randint]['keyword']
                    shift = random.randint(0, 25)
                    currentCode = dict(
                        {
                            'plaintext': plaintext,
                            'key': keyword, 
                            'shift': shift
                         })
                    R_Server.set(userID+'pat2s', json.dumps(currentCode))
                else:
                    plaintext = json.loads(keys)['plaintext']
                    keyword = json.loads(keys)['key']
                    shift = json.loads(keys)['shift']
                letters = list(codes.patristok2(plaintext, keyword, shift))
                frequency = codes.get_frequency(codes.patristok2(plaintext, keyword, shift))
                LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                freqDict = dict()

                for i in range(0, 26):
                    freqDict[LETTERS[i]]=frequency[i]

                return render_template('cipherpage.j2', letters=letters, profile=json.loads(R_Server.get(userID)), route='/patristocrat-k2-solo', freqDict=freqDict, isK2=True)

    @blueprint.route("/patristocrat-k2-solo", methods=['POST'])
    def checkPat2():
        userID = request.cookies.get('userid')
        username = json.loads(R_Server.get(userID))['username']
        keys = json.loads(R_Server.get(userID+'pat1s'))
        cipherbet=codes.form_cipher(keys['key'], int(keys['shift']))
        inputLetters = request.form
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        correct = True

        for i in list(codes.text_clean(codes.patristok1(keys['plaintext'], keys['key'], keys['shift']))):
            index=cipherbet.index(i)
            if inputLetters.get(i) == None or inputLetters.get(i)==alphabet[index]:
                continue
            else:
                correct = False
                break
        
        if correct:
            flash('Correct Solution!', 'check')
            R_Server.set(userID, json.dumps(database.correctCodes(username, keys['plaintext'])))
            R_Server.delete(userID+'pat2s')
        else:
            flash("Incorrect Solution. Please try again.", 'check')

        return redirect('/patristocrat-k2-solo')

    @blueprint.route("/cipherselection")
    def gCode():
        userID = request.cookies.get('userid')
        if userID == None:
            return redirect('/login')
        else:
            return render_template('cipherselection.j2', profile = json.loads(R_Server.get(userID)))
        
    @blueprint.route("/cipherselection", methods=['POST'])
    def postSelect():
        mode = request.form.get('mode')

        if mode == 'patristocrat':
            return redirect('/lobby')
        elif mode == 'soloPat1':
            return redirect('/patristocrat-k1-solo')
        elif mode == 'soloPat2':
            return redirect('/patristocrat-k2-solo')
        else:
            return 'ERROR: Incorrect Data'    
    
    @blueprint.route('/lobby')
    def joinOrCreateLobby():
        userid = request.cookies.get('userid')
        matches = R_Server.get('matches')
        matchDict = dict()
        if matches:
            matchDict = json.loads(matches)

        if userid == None:
            return redirect('/login')
        else:
            return render_template('lobby.j2', values=list(matchDict.values()), keys=list(matchDict.keys()))
        
    @blueprint.route('/lobby', methods=['POST'])
    def lobbyDirect():
        mode = request.form.get('mode')
        userID = request.cookies.get('userid')
        matches = R_Server.get('matches')

        if userID == None:
            return redirect('/login')
        else:
            if mode == 'create':
                matchID = str(uuid.uuid4())
                if matches:
                    matchDict = json.loads(matches)
                    matchDict[userID]=matchID
                    R_Server.set('matches', json.dumps(matchDict))
                else:
                    R_Server.set('matches', json.dumps({json.loads(R_Server.get(userID))['username']:matchID}))

                resp = make_response(redirect('/waiting-room'))
                resp.set_cookie('matchid', matchID)
                return resp
            if mode in list(json.loads(matches).values()):
                matchID = mode
                matchDict = json.loads(matches)
                host = list(matchDict.keys())[list(matchDict.values()).index(matchID)]
                del matchDict[host]
                R_Server.set('matches', json.dumps(matchDict))

                resp = make_response(redirect('/waiting-room'))
                resp.set_cookie('matchid', matchID)
                return resp
            else: 
                return 'ERROR: Incomplete Data'
    
    @blueprint.route('/waiting-room')
    def setUp():
        matchID = request.cookies.get('matchid')
        userID = request.cookies.get('userid')
        if matchID == None:
            return redirect('/lobby')
        else:
            if R_Server.get(matchID+'users'):
                users = json.loads(R_Server.get(matchID+'users'))
                print(users)
                if len(users) == 2:
                    return redirect('/patristocrat')
                else:
                    return render_template('waiting-room.j2', matchID=matchID, userID=userID)
            else:
                return render_template('waiting-room.j2', matchID=matchID, userID=userID)
    
    @blueprint.route('/waiting-room', methods=['PUT'])
    def putInGame():
        matchID = request.cookies.get('matchid')

        body = request.get_json()
        if 'action' not in body or 'data' not in body:
            return jsonify({'status' : 'error', 'data' : 'incomplete data'})
        action = body.get('action')
        data = body.get('data')

        if action == 'connection':
            lobbyUser = data['user']
            if R_Server.get(matchID+'users'):
                users = json.loads(R_Server.get(matchID+'users'))
                users.append(lobbyUser)
                R_Server.set(matchID+'users', users)
            else:
                users = [lobbyUser]
                R_Server.set(matchID+'users', users)
        else:
            return jsonify({'status' : 'error', 'data' : 'incomplete data'})
        
        return redirect('/waiting-room')



    @blueprint.route('/stream')
    def multiStream():
        if R_Server == None:
            return "ERROR: Updates Not Available"

        matchid = request.cookies.get('matchid')
        if matchid == None:
            return "ERROR: Game Does Not Exist"

        def emitter():
            if R_Server == None:
                return 'data: Streaming Down\n\n'
            
            pubsub = R_Server.pubsub()
            pubsub.subscribe(matchid)
            for message in pubsub.listen():
                data = message['data']
                if type(data) == bytes:
                    yield f'data: {data.decode()}\n\n'
        
        res = Response(emitter(), mimetype='text/event-stream')
        return res