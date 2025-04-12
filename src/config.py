import os
from dotenv import load_dotenv
from os import environ as ENV, path
import logging

load_dotenv()

ENV_PATH = path.join(path.dirname(__file__), '.env')
if ENV.get('ENV_FILE') is not None:
    ENV_PATH = ENV.get('ENV_FILE')
logging.warning(f'Loading environment variables from {ENV_PATH}')
load_dotenv(ENV_PATH)

class Config:
    APP_ROOT = os.path.abspath(path.dirname(__file__))
    IMAGE_PATH = os.path.join(APP_ROOT, 'static' , 'uploads')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    FLASK_PORT = 3000
    FLASK_DEBUG = True
    FLASK_HOST = '0.0.0.0'
    SECRET_KEY = os.getenv('SECRET_KEY')
