# coding:utf-8
# Configure logging format
import locale
import logging
from logging.handlers import RotatingFileHandler

# use current locale for date/time formatting in logs
locale.setlocale(locale.LC_ALL, '')

logging.basicConfig(  # format='%(asctime)s [%(levelname)s] %(message)s in %(pathname)s:%(lineno)d',
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler("log.log", maxBytes=1000000, backupCount=0),  # Log in textfile max 1MB
        logging.StreamHandler()  # Log also in console
    ],
    datefmt='%x %X')

logger = logging.getLogger('turing')
logger.setLevel(logging.INFO)  