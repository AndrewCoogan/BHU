from flask import Flask
import secrets

def create_app():
    app = Flask(__name__)
    app.config['BOOTSTRAP_BOOTSWATCH_THEME'] = 'zephyr'
    app.config['BOOTSTRAP_BTN_STYLE'] = 'primary'
    app.config['BOOTSTRAP_BTN_SIZE'] = 'sm'
    app.config['BOOTSTRAP_TABLE_VIEW_TITLE'] = 'Read'
    app.config['BOOTSTRAP_TABLE_EDIT_TITLE'] = 'Update'
    app.config['BOOTSTRAP_TABLE_DELETE_TITLE'] = 'Remove'
    app.config['BOOTSTRAP_TABLE_NEW_TITLE'] = 'Create'
    app.secret_key = secrets.token_hex()
    return app