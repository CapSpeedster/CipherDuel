from flask import Flask, jsonify, Response, request, send_file, redirect, render_template, make_response, flash
import database
import redis
import uuid
import json
import os
from pathlib import Path

# Connect to Redis
R_Server = redis.StrictRedis()
try:
    R_Server.ping()
except:
    print("REDIS: Not Running -- No Streams Available")
    R_Server = None

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

                resp = make_response(redirect(f'/profile/{username}'))
                resp.set_cookie('userid', str(sessionID))
                return resp

        #Authenticats and logs in existing user
        elif mode == 'login':
            if (database.db_auth_user(username, password)): 
                #Set the cookie
                sessionID = uuid.uuid4()
                profile = database.get_profile(username)
                R_Server.set(str(sessionID), json.dumps(profile))

                resp = make_response(redirect(f'/profile/{username}'))
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
                currentUser = json.loads(R_Server.get(userID))['username']
                readonly = True
                if json.loads(R_Server.get(userID))==profile:
                    readonly = False
                return render_template('profile.j2', profile=profile, username=user, readonly=readonly, cUser=currentUser)

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
            if mode == 'name':
                fname = request.form.get('fname')
                lname = request.form.get('lname')
                if fname == None or lname == None:
                    return 'ERROR: Incomplete Data'
                else:
                    profile = database.update_profile(user, fname, lname)
            if mode == 'avatar':
                avatar = request.files['avatar']
                if avatar == None:
                    return 'ERROR: Incomplete Data'
                else:
                    if Path(avatar.filename).suffix == '.jpeg' or Path(avatar.filename).suffix == '.png':
                        #adds uploaded file to the avatars folder and updates the name
                        avatar.save(os.path.join('static/avatars', avatar.filename))
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
    
    @blueprint.route('/profile/<user>', methods = ['PUT'])
    def putProfile(user):
        """
        Updates profile page and database based on fetch avtion:
        name: updates fname and lname
        picture: updates avatar if it's .jpeg or .png
        password: confirms current passwords and updates with new password
        """
        userID = request.cookies.get('userid')
        if userID == None:
            return jsonify({'status' : 'error', 'data' : 'user not logged in'})
        else: 
            body = request.get_json()
            if 'action' not in body or 'data' not in body:
                return jsonify({'status' : "error", 'data' : 'incomplete data'})
            action = body.get('action')
            data = body.get('data')

            if action == 'name':
                fname = data['fname']
                lname = data['lname']
                profile = database.update_profile(user, fname = fname, lname = lname)
                R_Server.set(userID, json.dumps(profile))
            if action == 'password':
                newpword = data['newpword']
                pconfirm = data['pconfirm']

                #Authenticate username and password and updates database with new password
                if database.db_auth_user(user, pconfirm):
                    profile=database.update_profile(user, password=newpword)
                else: 
                    return jsonify({'status' : 'error', 'data' : 'incorrect username or password'})
                R_Server.set(userID, json.dumps(profile))
            if action == 'picture':
                avatar = data['avatar']

                #adds uploaded file to the avatars folder and updates the name
                if Path(avatar.filename).suffix == '.jpeg' or Path(avatar.filename).suffix == '.png':
                    avatar.save(os.path.join('static/avatars', avatar.filename))
                    os.rename(f'static/avatars/{avatar.filename}', f'static/avatars/{user}_avatar.{Path(avatar.filename).suffix}')
                    profile = database.update_profile(user, avatar=avatar.filename)
                    R_Server.set(userID, json.dumps(profile))
                else:
                    return jsonify({'status' : 'error', 'data' : 'incorrect file format'})


            return jsonify({'status' : 'success', 'data' : f"updated {user}'s profile page"})