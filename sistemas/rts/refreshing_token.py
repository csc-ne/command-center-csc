from selenium.webdriver.common.by import By
from selenium import webdriver
from bs4 import BeautifulSoup
from datetime import timedelta, datetime
import json
import requests

# URL do Servidor que está hospedada a autenticação John Deere
url = 'http://127.0.0.1:5000'


def exp_time():
    # Scraping do html
    html = requests.get(url)
    html_soup = BeautifulSoup(html.content, 'html.parser')

    # Scraping da data e hora de expiração
    language_json = [exptime for exptime in html_soup.find('code', {'class', 'language-json'})][0]
    expiration_time = json.loads(language_json)['exp']

    # Correção do fuso horário
    unix_to_date = datetime.utcfromtimestamp(expiration_time) + timedelta(hours=-3)

    return unix_to_date


def update_token():
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # opera o chrome em segundo plano

        # Acessa o site
        driver = webdriver.Chrome(options=options)
        driver.get(url)

        # Procura o botão pelo id html
        button = driver.find_element(By.LINK_TEXT, 'Refresh The Access Token')
        button.click()
        print('Token atualizado')

    except Exception as e:
        print('Não foi possível atualizar o token')
        print(f'Error: {e}')


if __name__ == '__main__':
    update_token()
