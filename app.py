from flask import Flask
import routes
import database

app = Flask(__name__)

#Secret keys for Flask.flashes()
app.secret_key = b'lemming'

#Connect to database and routes
database.db_connect()
routes.connect_routes(app)

#Run app
app.run(port=8080, debug=True)