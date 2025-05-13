from flask import Flask, jsonify, Response, request, send_file, redirect, render_template, make_response, flash
from pathlib import Path
from datetime import datetime
import redis
import json
import uuid
import os
import database
import csv
import random
import codes


# app.run(threaded=True)

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
        isK2 = False

        if userID == None:
            return redirect('/login')
        else:
            if matchID == None:
                return redirect('/lobby')
            else:
                # Get match data or initialize new cryptogram for the match
                match_data = R_Server.get(f'match:{matchID}:cryptogram')
                
                if match_data is None:
                    # New match - generate cryptogram
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
                        return "You have completed all of our current ciphers. Wait for future updates to proceed."

                    # Generate new cryptogram for the match
                    randint = random.randint(0, len(newCiphers)-1)
                    plaintext = newCiphers[randint]['plaintext']
                    keyword = newCiphers[randint]['keyword']
                    if newCiphers[randint]['cipherType'] == 'k2':
                        isK2 = True
                    shift = random.randint(0, 25)

                    # Store match cryptogram data
                    match_data = {
                        'plaintext': plaintext,
                        'key': keyword,
                        'shift': shift,
                        'isK2': isK2
                    }
                    R_Server.set(f'match:{matchID}:cryptogram', json.dumps(match_data))
                else:
                    # Load existing match data
                    match_data = json.loads(match_data)
                    plaintext = match_data['plaintext']
                    keyword = match_data['key']
                    shift = match_data['shift']
                    isK2 = match_data['isK2']

                # Generate the cryptogram
                if isK2:
                    letters = list(codes.patristok2(plaintext, keyword, shift))
                    frequency = codes.get_frequency(codes.patristok2(plaintext, keyword, shift))
                else:
                    letters = list(codes.patristok1(plaintext, keyword, shift))
                    frequency = codes.get_frequency(codes.patristok1(plaintext, keyword, shift))

                LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                freqDict = dict()
                for i in range(0, 26):
                    freqDict[LETTERS[i]] = frequency[i]

                return render_template('cipherpage.j2', letters=letters, profile=json.loads(R_Server.get(userID)), route='/patristocrat', freqDict=freqDict, isK2=isK2, matchid=matchID)
   
    @blueprint.route('/patristocrat', methods=['PUT'])
    def putPat():
        userID = request.cookies.get('userid')
        matchID = request.cookies.get('matchid')

        if userID is None or matchID is None:
            return jsonify({'status': 'error', 'data': 'No user ID or match ID'})

        body = request.get_json()
        if 'action' not in body or 'data' not in body:
            return jsonify({'status': 'error', 'data': 'incomplete data'})
        
        action = body.get('action')

        if action == 'connect':
            # Get the match data
            match_data = R_Server.get(f'match:{matchID}:cryptogram')
            if match_data is None:
                return jsonify({'status': 'error', 'data': 'match not found'})
            
            match_data = json.loads(match_data)
            isK2 = match_data['isK2']
            plaintext = match_data['plaintext']
            keyword = match_data['key']
            shift = match_data['shift']

            # Generate cryptogram
            if isK2:
                letters = list(codes.patristok2(plaintext, keyword, shift))
                frequency = codes.get_frequency(codes.patristok2(plaintext, keyword, shift))
            else:
                letters = list(codes.patristok1(plaintext, keyword, shift))
                frequency = codes.get_frequency(codes.patristok1(plaintext, keyword, shift))

            LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            freqDict = dict()
            for i in range(0, 26):
                freqDict[LETTERS[i]] = frequency[i]

            # Publish updates to all clients in the match
            R_Server.publish(matchID, json.dumps({
                'event': 'updateCode',
                'letters': letters,
                'frequency': freqDict,
                'isK2': isK2
            }))
            
            return jsonify({'status': 'success', 'data': 'published server data'})
        
        return jsonify({'status': 'error', 'data': 'invalid action'})
    
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
        # Check user authentication
        userid = request.cookies.get('userid')
        if userid == None:
            return redirect('/login')
        
        # Get list of all available matches
        matches = R_Server.get('matches')
        matchDict = dict()
        if matches:
            matchDict = json.loads(matches)
            # Filter out full lobbies (with 2 players)
            matchDict = {k: v for k, v in matchDict.items() if len(v.get('players', [])) < 2}
            
        # Get username for display purposes
        username = json.loads(R_Server.get(userid))['username']
            
        return render_template('lobby.j2', matches=matchDict, username=username)
    
    @blueprint.route('/lobby', methods=['POST'])
    def lobbyDirect():
        # Check user authentication
        userid = request.cookies.get('userid')
        if userid == None:
            return redirect('/login')

        username = json.loads(R_Server.get(userid))['username']
        
        # Get or initialize matches dictionary
        matches_raw = R_Server.get('matches') or b'{}'
        matches = json.loads(matches_raw)

        mode = request.form['mode']
        
        if mode == 'create':
            # Create new lobby with a unique ID
            new_id = str(uuid.uuid4())[:8]
            matches[new_id] = {
                'host': username,
                'id': new_id,
                'created_at': str(datetime.now()),
                'players': [username]  # Initialize players list with host
            }
            R_Server.set('matches', json.dumps(matches))
            
            # Redirect to game with lobby cookie
            resp = make_response(redirect('/patristocrat'))
            resp.set_cookie('matchid', new_id)
            return resp

        elif mode == 'join':
            # Get lobby ID from form
            lobby_id = request.form.get('lobby_id')
            if lobby_id in matches:
                # Check if lobby is full
                if len(matches[lobby_id]['players']) >= 2:
                    flash("This lobby is full.", "error")
                    return redirect('/lobby')
                    
                # Add player to the lobby
                if username not in matches[lobby_id]['players']:
                    matches[lobby_id]['players'].append(username)
                    R_Server.set('matches', json.dumps(matches))
                
                # Set match cookie and redirect to game
                resp = make_response(redirect('/patristocrat'))
                resp.set_cookie('matchid', lobby_id)
                return resp
            else:
                flash("No such lobby exists.", "error")
                return redirect('/lobby')

        flash("Invalid action.", "error")
        return redirect('/lobby')

    # @blueprint.route('/stream')
    # def multiStream():
    #     if R_Server == None:
    #         return "ERROR: Updates Not Available"

    #     matchid = request.cookies.get('matchid')
    #     if matchid == None:
    #         return "ERROR: Game Does Not Exist"

    #     def emitter():
    #         if R_Server == None:
    #             return 'data: Streaming Down\n\n'
            
    #         pubsub = R_Server.pubsub()
    #         pubsub.subscribe(matchid)
    #         for message in pubsub.listen():
    #             data = message['data']
    #             if type(data) == bytes:
    #                 yield f'data: {data.decode()}\n\n'
        
    #     res = Response(emitter(), mimetype='text/event-stream')
    #     return res


    @blueprint.route('/stream')
    def multiStream():
        def event_stream():
            pub = R_Server.pubsub(ignore_subscribe_messages=True)
            pub.subscribe(request.cookies.get('matchid'))
            for msg in pub.listen():
                if isinstance(msg['data'], bytes):
                    yield f"data: {msg['data'].decode()}\n\n"
        return Response(event_stream(),
                        mimetype="text/event-stream")