from app import app  # import the Flask instance

# Vercel expects a function named `handler`
def handler(environ, start_response):
    return app.wsgi_app(environ, start_response)