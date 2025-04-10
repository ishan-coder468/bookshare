import os
basedir = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = 'ehxhdjuiusjdjfjrikwikekfjkrtike'
SQLALCHEMY_DATABASE_URI = 'sqlite:///books.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Email Setup
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'ishanijjk@gmail.com'
MAIL_PASSWORD = 'vsoz bdui fyqb xdre'
MAIL_DEFAULT_SENDER = MAIL_USERNAME

# Google OAuth
GOOGLE_CLIENT_ID = '92749770213-smterg6ohlvn0k08o649t2b4g5eturij.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = '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'