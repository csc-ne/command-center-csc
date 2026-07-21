import base64
import datetime
import json
import uuid
import logging
import dotenv
import os
from flask import Flask, render_template, request, redirect
import requests
import urllib.parse

app = Flask(__name__)

SERVER_URL='http://127.0.0.1:5000'
#SERVER_URL='http://127.0.0.1:9090'

# Carrega o arquivo .env centralizado em C:\env\.env (host Windows).
# Fallback para find_dotenv (busca ancestral) caso rode em outro SO.
import platform as _platform
if _platform.system() == "Windows":
    dotenv.load_dotenv(r"C:\env\.env")
else:
    dotenv.load_dotenv(dotenv.find_dotenv(".env"))
client_id = os.environ.get("clientId")
client_secret = os.environ.get("clientSecret")

# Caminho do cache de token — salvo na raiz do projeto
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_CACHE_PATH = os.path.join(_ROOT, '.token_cache.json')


def save_token_cache():
    """Persiste refresh token em disco para sobreviver a reinicializações."""
    try:
        cache = {
            'refreshToken': settings['refreshToken'],
            'savedAt': datetime.datetime.now().isoformat()
        }
        with open(TOKEN_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f)
    except Exception as e:
        logging.warning(f'Não foi possível salvar cache do token: {e}')


def load_token_cache():
    """Carrega refresh token do cache em disco, se existir."""
    try:
        if os.path.exists(TOKEN_CACHE_PATH):
            with open(TOKEN_CACHE_PATH, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            refresh_token = cache.get('refreshToken', '')
            if refresh_token:
                settings['refreshToken'] = refresh_token
                logging.info('Refresh token carregado do cache — renovando access token...')
                return True
    except Exception as e:
        logging.warning(f'Não foi possível carregar cache do token: {e}')
    return False

settings = {
    'apiUrl': 'https://sandboxapi.deere.com/platform',
    'clientId': client_id,
    'clientSecret': client_secret,
    'wellKnown': 'https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/.well-known/oauth-authorization-server',
    'callbackUrl': f"{SERVER_URL}/callback",
    'orgConnectionCompletedUrl': SERVER_URL,
    'scopes': 'ag1 ag2 ag3 eq1 eq2 org1 org2 files offline_access',
    'state': uuid.uuid1(),
    'idToken': '',
    'accessToken': '',
    'refreshToken': '',
    'apiResponse': '',
    'accessTokenDetails': '',
    'exp': ''
}

def populate(data):
    settings['clientId'] = data['clientId']
    settings['clientSecret'] = data['clientSecret']
    settings['wellKnown'] = data['wellKnown']
    settings['callbackUrl'] = data['callbackUrl']
    settings['scopes'] = data['scopes']
    settings['state'] = data['state']


def update_token_info(res):
    json_response = res.json()
    token = json_response['access_token']
    settings['accessToken'] = token
    settings['refreshToken'] = json_response['refresh_token']
    settings['exp'] = datetime.datetime.now() + datetime.timedelta(seconds=json_response['expires_in'])
    (header, payload, sig) = token.split('.')
    payload += '=' * (-len(payload) % 4)
    settings['accessTokenDetails'] = json.dumps(json.loads(base64.urlsafe_b64decode(payload).decode()), indent=4)
    # Persiste o refresh token para sobreviver a reinicializações do servidor
    save_token_cache()


def get_location_from_metadata(endpoint):
    response = requests.get(settings['wellKnown'])
    return response.json()[endpoint]


def get_basic_auth_header():
    return base64.b64encode(bytes(settings['clientId'] + ':' + settings['clientSecret'], 'utf-8'))

def api_get(access_token, resource_url):
    headers = {
        'authorization': 'Bearer ' + settings['accessToken'],
        'Accept': 'application/vnd.deere.axiom.v3+json'
    }
    return requests.get(resource_url, headers=headers)

def render_error(message):
    return render_template('error.html', title='John Deere API with Python', error=message)


def get_oidc_query_string():
    query_params = {
        "client_id": settings['clientId'],
        "response_type": "code",
        "scope": urllib.parse.quote(settings['scopes']),
        "redirect_uri": settings['callbackUrl'],
        "state": settings['state'],
    }
    params = [f"{key}={value}" for key, value in query_params.items()]
    return "&".join(params)


@app.route("/", methods=['POST'])
def start_oidc():
    populate(request.form)
    
    redirect_url = f"{get_location_from_metadata('authorization_endpoint')}?{get_oidc_query_string()}"

    return redirect(redirect_url, code=302)

def needs_organization_access():
    """Check if a another redirect is needed to finish the connection.

    Check to see if the 'connections' rel is present for any organization.
    If the rel is present it means the oauth application has not completed its
    access to an organization and must redirect the user to the uri provided
    in the link.
    """
    api_response = api_get(settings['accessToken'], settings['apiUrl']+'/organizations').json()
    for org in api_response['values']:
        for link in org['links']:
            if link['rel'] == 'connections':
                connectionsUri = link['uri']
                query = urllib.parse.urlencode({'redirect_uri': settings['orgConnectionCompletedUrl']})
                return f"{connectionsUri}?{query}"
    return None

@app.route("/callback")
def process_callback():
    try:
        code = request.args['code']
        headers = {
            'authorization': 'Basic ' + get_basic_auth_header().decode('utf-8'),
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        payload = {
            'grant_type': 'authorization_code',
            'redirect_uri': settings['callbackUrl'],
            'code': code,
            'scope': settings['scopes']
        }

        res = requests.post(get_location_from_metadata('token_endpoint'), data=payload, headers=headers)
        update_token_info(res)

        organization_access_url = needs_organization_access()
        if organization_access_url is not None:
            return redirect(organization_access_url, code=302)

        return index()
    except Exception as e:
        logging.exception(e)
        return render_error('Error getting token!')


@app.route("/call-api", methods=['POST'])
def call_the_api():
    try:
        url = request.form['url']
        res = api_get(settings['accessToken'], url)
        settings['apiResponse'] = json.dumps(res.json(), indent=4)
        return index()
    except Exception as e:
        logging.exception(e)
        return render_error('Error calling API!')


@app.route("/refresh-access-token")
def refresh_access_token():
    try:
        headers = {
            'authorization': 'Basic ' + get_basic_auth_header().decode('utf-8'),
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        payload = {
            'grant_type': 'refresh_token',
            'redirect_uri': settings['callbackUrl'],
            'refresh_token': settings['refreshToken'],
            'scope': settings['scopes']
        }

        res = requests.post(get_location_from_metadata('token_endpoint'), data=payload, headers=headers)
        update_token_info(res)

        return index()
    except Exception as e:
        logging.exception(e)
        return render_error('Error getting refresh token!')


@app.route("/")
def index():
    return render_template('main.html', title='John Deere API with Python', settings=settings)

def auto_refresh_on_startup():
    """
    Se existe um refresh token salvo em cache, renova o access token
    automaticamente ao iniciar — sem precisar de login manual.
    Chamado uma vez após o Flask subir.
    """
    if load_token_cache():
        try:
            headers = {
                'authorization': 'Basic ' + get_basic_auth_header().decode('utf-8'),
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            payload = {
                'grant_type': 'refresh_token',
                'redirect_uri': settings['callbackUrl'],
                'refresh_token': settings['refreshToken'],
                'scope': settings['scopes']
            }
            res = requests.post(get_location_from_metadata('token_endpoint'), data=payload, headers=headers)
            if res.status_code == 200:
                update_token_info(res)
                logging.info('Auto-refresh na inicialização: token renovado com sucesso.')
                print('[RTS] Token renovado automaticamente a partir do cache.')
            else:
                logging.warning(f'Auto-refresh falhou (status {res.status_code}). Login manual necessário.')
                print('[RTS] Cache de token expirado ou inválido. Faça login manual em http://127.0.0.1:5000')
        except Exception as e:
            logging.warning(f'Auto-refresh na inicialização falhou: {e}')
            print(f'[RTS] Falha no auto-refresh: {e}. Faça login manual em http://127.0.0.1:5000')
    else:
        print('[RTS] Nenhum token em cache. Faça login em http://127.0.0.1:5000 para autenticar.')


if __name__ == "__main__":
    # Tenta renovar token automaticamente antes de subir o servidor
    # (executa em thread separada para não bloquear o Flask)
    import threading
    threading.Timer(2.0, auto_refresh_on_startup).start()
    app.run(port=5000)
