import requests
from bs4 import BeautifulSoup

SERVER_URL='http://127.0.0.1:5000'
#SERVER_URL='http://127.0.0.1:9090'

def is_authenticate():
    # Acessa a página de autenticação
    response = requests.get(SERVER_URL)
    soup = BeautifulSoup(response.text, "html.parser")

    # Checa se o usuário logou
    has_token = len(soup.find_all("p", {"class": "token"})) != 0 if True else False

    if has_token:
        return True
