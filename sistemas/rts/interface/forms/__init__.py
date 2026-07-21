from forms.utils.modals.ModalAlert import *
from forms.utils.modals.ModalTable import TableCustomers
from forms.utils.logs.src.logger import InterfaceLogger
from forms.utils.buttons.CustomButton import ButtonComponent
from dotenv import load_dotenv
import psycopg2
import selenium.common.exceptions
from selenium.webdriver.common.by import By
from selenium import webdriver
from bs4 import BeautifulSoup
from datetime import timedelta, datetime
import json
import requests

