# VENEZA EQUIPAMENTOS PESADOS S/A
# CENTRO DE SOLUÇÕES CONECTADAS - CSC VENEZA NORDESTE
# MÓDULO DE REQUISIÇÕES DE ALERTAS VIA API DE NOTIFICAÇÕES DA JOHN DEERE
# DESENVOLVIDO POR ROBERT ARAÚJO

"""

# ==== Modificação da Função get_alerts e criação da função HTTP_code - Thiago Barros - 15/04/2025 - Linhas 197 a 301
# ==== Modificação da resposta para extração do título do alerta sem apostrófo antes de entrar no banco de dados  - 
# ==== Descontinuidade da Resposta extract_info(titulo) - Thiago Barros - 16/04/2025 - Linha 352
# === Descontinuidade do parâmetro pt_BR para pt-BR em api_get - 29/08/2025 - Linha 87
# === Alteração dos endpoints para o padrão de produção. - 29/08/2025 - Funções - get alerts
"""

import os.path
import requests
import json
import re
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

#Constantes
URL_SERVIDOR = 'http://127.0.0.1:5000'
#URL_SERVIDOR = 'http://127.0.0.1:9090'

def retry_request(method, **kwargs):

    if method == None:
        raise ValueError("Invalid method. Use 'GET' or 'POST'")
    
    success = False
    c = 0

    print("Tentando novamente...")

    while success == False and c < 1000:
        timer = 120
        time.sleep(timer)
        c += 1
        print(f'Aguardando {timer} segundos')
        print("Tentativa: ", c)
        
        try:
            if method == "GET":
                new_response = requests.get(**kwargs)
            elif method == "POST":
                new_response = requests.post(**kwargs)
            else:
                print("Método não reconhecido. Programa encerrado.")
                return None
        except Exception as error:
            print(error)
            continue
        else:
            if new_response.status_code == 200:
                success = True
                return new_response

            print(f"Response Status: {new_response.status_code}")
            print(f"Response Text: {new_response.text}")
            print("Trying again... \n\n")
    
    return None

def format_time(date_alert):
    # A API devolve o horário em um fuso horário diferente do Brasil
    # Então, é preciso tirar 3 horas do tempo que aparece para corrigir isso
    date_to_object = (datetime.strptime(date_alert, '%Y-%m-%dT%H:%M:%S.%fZ') + timedelta(hours=-3))
    date_formatted = date_to_object.date().strftime('%d/%m/%Y')
    time_formatted = date_to_object.time().strftime('%H:%M')
    date_to_db = date_to_object.date()

    return date_formatted, time_formatted, date_to_db


def token_get():
    """Retorna access_token da John Deere.

    Em modo headless (RTS_HEADLESS=1, container Docker) usa o
    `jd_token_manager` que faz refresh OAuth direto via Python (sem
    Selenium nem Flask local). Em modo GUI, mantem comportamento
    legado: scrape do Flask local em URL_SERVIDOR.
    """
    import os
    if os.environ.get("RTS_HEADLESS") == "1":
        try:
            from jd_token_manager import get_access_token
            return get_access_token()
        except Exception as e:
            # Fallback: ainda tenta o servidor local (caso esteja
            # acessivel via host.docker.internal por engano)
            import logging
            logging.error(
                "[token_get] jd_token_manager falhou (%s); "
                "tentando servidor local como fallback", e
            )
    url_servidor = URL_SERVIDOR
    html = requests.get(url_servidor)
    html_soup = BeautifulSoup(html.content, 'html.parser')
    token = [tk for tk in html_soup.find('p', {'class': 'token'})][0].text
    return token

def api_get(access_token, resource_url):
    headers = {
        'authorization': 'Bearer ' + access_token,
        'Accept': 'application/vnd.deere.axiom.v3+json',
        'Accept-Language': 'pt-BR'
    }
    try:
        response = requests.get(resource_url, headers=headers)
    except Exception as error:
        new_response = retry_request(url=resource_url,headers=headers, method="GET")
        if new_response == None:
            raise error
        return new_response.json()
    
    # Tratamento de status code != 200
    if response.status_code == 429 or response.status_code == 500:
        print("Status erro recebido: ", response.status_code)
        print("Iniciando recuperação do programa...")

        second_chance = {}
        for counter in range(1, 100, 1):
            print(f"Tentativa {counter}")
            second_chance = requests.get(resource_url, headers=headers)

            if second_chance.status_code == 200:
                print("Recuperação bem sucedida. Conexão reestabelecida.")
                break  # Encerra o loop

            time.sleep(10)  # 10 segundos de delay

        return second_chance.json()

    return response.json()


def search_element(name_key, name_value, the_list):
    return [element for element in the_list if element[name_key] == name_value]

def HTTP_code(id_org, access_token):

    endpoint = "/notifications/events?eventTypes=DTC_ALERT"
    #endpoint = "/notifications/events?eventTypes=DTC_ALERT,DTC_EVENT,MAINTENCE_ALERT"
    #url = f'https://sandboxapi.deere.com/platform/organizations/{id_org}' + endpoint
    url = f'https://partnerapi.deere.com/platform/organizations/{id_org}' + endpoint

    headers = {
    'authorization': 'Bearer ' + access_token,
    'Accept': 'application/vnd.deere.axiom.v3+json',
    'Accept-Language': 'pt-BR'
}

    response = requests.get(url, headers=headers)

    return int(response.status_code)

#Função Temporária para Testes
"""
def HTTP_code_2(id_org, access_token):

    endpoint = "/notifications/events?eventTypes=DTC_ALERT"
    #url = f'https://sandboxapi.deere.com/platform/organizations/{id_org}' + endpoint
    url = f'https://partnerapi.deere.com/platform/organizations/{id_org}' + endpoint

    headers = {
    'authorization': 'Bearer ' + access_token,
    'Accept': 'application/vnd.deere.axiom.v3+json',
    'Accept-Language': 'pt-BR'
}

    response = requests.get(url, headers=headers)

    return response.text
""" 

def get_alerts(id_org): #01/09/2025 - Modificado para Testes de Requisição

    endpoint = "/notifications/events?eventTypes=DTC_ALERT,DTC_EVENT,MAINTENCE_ALERT"
    url = f'https://sandboxapi.deere.com/platform/organizations/{id_org}' + endpoint
    #endpoint = "/notifications/events?eventTypes=DTC_ALERT"
    #url = f'https://partnerapi.deere.com/platform/organizations/{id_org}' + endpoint

    #url = f'https://partnerapi.deere.com/platform/organizations/{id_org}/notifications/events?eventTypes=DTC_ALERT&startDate=2025-09-02T00:00:00Z&endDate=2025-09-02T23:59:00Z'

    dtcs = []
    response_code = HTTP_code(id_org, access_token=token_get())

    #Resposta Temporária par Testes e Verificação
    #response_code2 = HTTP_code_2(id_org, access_token=token_get())
    
    if response_code == 403 or id_org == None or id_org == "Não Encontrado" : # condição para o caso de resposta não retornar resposta devido ao bloqueio de de requisição
        #print(id_org, response_code, response_code2)
        return dtcs

    elif response_code == 200: # <- Precisa de um filtro de resposta para indicar quais máquinas estão bloqueadas para resposta via api e quais máquinas não estão. O código estava pegando todos os id e estava parando em ids que retornavam erro diferente de 200 - - Thiago Barros - 16/04/2025

        #print(id_org)
        
        resposta = api_get(access_token=token_get(), resource_url=url)
        #print(id_org, response_code, response_code2[:250])
    
        for keys, values in resposta.items():
            
            if type(values) is int or keys == 'links' or keys == 'total':
                continue
                
            for alertas in values:
                
                titulo = alertas['title']
                
                if "Manutenção -" in titulo:
                    pattern_str = r'^\d{2}-\d{2}-\d{4}$'
                    if re.match(pattern_str, titulo[13:]):
                        continue
    
                info_alerta = alertas['minimizedNotifications']
                
                try:
                    geometries = json.loads(alertas['geometries'])[0]
                    latitude = geometries['coordinates'][1]
                    longitude = geometries['coordinates'][0]
                    
                except KeyError:
                    latitude = 0
                    longitude = 0
    
    
                for minimizedNotifications in info_alerta:
                    detalhes_adicionais = minimizedNotifications['additionalDetails']
                    data_alerta = format_time(minimizedNotifications['dateCreated'])
                    machine_type = search_element('name', 'machineType', detalhes_adicionais)
    
                    match machine_type[0]['value'].upper():
                       
                        case 'BACKHOES' | '4WD LOADERS' | '4WD LOADER' | 'EXCAVATOR' | 'CRAWLER' | 'MOTOR GRADERS' | 'CRAWLER EXCAVATOR' | 'COLD RECYCLER' | 'COMPACT MILLING MACHINE' | 'COMPACTOR' | 'LARGE MILLING MACHINE' | 'MOBILE COLD RECYCLING MIXING PLANT' | 'PNEUMATIC TIRE ROLLER' | 'SLIPFORM PAVER' | 'SMALL MILLING MACHINE' | 'TANDEM ROLLER':
                            pass
                        case _:   
                            break
    
                    try:
                        find_chassi = search_element('name', 'machinePin', detalhes_adicionais)
                        
                    except KeyError:
                        find_chassi = search_element('name', 'machineVin', detalhes_adicionais)
                    
                    find_horimetro = search_element('name', 'engineHours', detalhes_adicionais)
                    chassi = find_chassi[0]['value']
                    
                    if len(find_horimetro) == 0:
                        horimetro = 0
                        
                    else:
                        horimetro = round(float(find_horimetro[0]['value']), 1)
                    
    
                    dtcs.append(
                        {
                            'Alerta': titulo.replace("'"," "), # <- Precisa entrar na base de dados sem o apostrofo. Caso contrário, o título entrar com o formato incompatível com MYSQL retornando "erro mysql.connector.errors.ProgrammingError: 1064 (42000)"" - Thiago Barros - 16/04/2025
                            'Chassi': chassi,
                            'Data': data_alerta[2],
                            'Hora': data_alerta[1],
                            'Horimetro': horimetro,
                            'Latitude': latitude,
                            'Longitude': longitude
                        }
                    )
        
        #if dtcs != []:
        #   print(dtcs[0])
        return dtcs
    
    else:
        return dtcs

def get_alerts_veneza(id_org):
  #Função para monitorar os alertas da conta da Veneza Projeto
    
    dtcs = []
   
    url = f'https://partnerapi.deere.com/platform/organizations/{id_org}/notifications/events?eventTypes=DTC_ALERT,DTC_EVENT,MAINTENCE_ALERT'
    
    #url = f'https://partnerapi.deere.com/platform/organizations/{id_org}/notifications/events?eventTypes=DTC_ALERT&startDate=2025-09-02T00:00:00Z&endDate=2025-09-02T23:59:00Z'
    
    resposta = api_get(access_token=token_get(), resource_url=url)

    for keys, values in resposta.items():
        if type(values) is int or keys == 'links' or keys == 'total':
            continue

        # Pega os itens que fica na chave "values" do dict
        for alertas in values:
            titulo = alertas['title']
            severidade = alertas['severity']
            info_alerta = alertas['minimizedNotifications']
            try:
                geometries = json.loads(alertas['geometries'])[0]
                latitude = geometries['coordinates'][1]
                longitude = geometries['coordinates'][0]
            except KeyError:
                latitude = 0
                longitude = 0
            
            if titulo == "Low Fuel":
                titulo = "Nível de combustível baixo"


            # Pega os itens que fica na chave "minimizedNotifications" do dict
            for minimizedNotifications in info_alerta:
                detalhes_adicionais = minimizedNotifications['additionalDetails']
                machine_type = search_element('name', 'machineType', detalhes_adicionais)
                machine_model = search_element('name', 'machineModel', detalhes_adicionais)

                if len(machine_type) == 0:
                    machine_type = [{'value': "Não identificado"}]
                    machine_model = [{'value': "Não identificado"}]

                # Filtro de máquinas agrícolas.
                match machine_type[0]['value'].upper():
                    case 'TRACTOR' | 'SUGAR HARVESTING' | 'COMBINE HARVESTING' | 'SPRAYER':
                        break
                    case _:
                        pass

                data_alerta = format_time(minimizedNotifications['dateCreated'])
                
                # Pega o nome da controladora e o código do alerta
                titulo = " ".join(titulo.split())
                #dados_adicionais = extract_info(titulo) <- Onde está essa função? - - Thiago Barros - 16/04/2025

                #if dados_adicionais[1].split('.')[0] not in ['000110', '000100']:
                #     break

                # Às vezes a API entrega 2 nomes diferentes de chaves para o chassi
                try:
                    find_chassi = search_element('name', 'machinePin', detalhes_adicionais)

                except KeyError:
                    find_chassi = search_element('name', 'machineVin', detalhes_adicionais)

                find_horimetro = search_element('name', 'engineHours', detalhes_adicionais)

                chassi = find_chassi[0]['value']
                horimetro = round(float(find_horimetro[0]['value']), 1)

                dtcs.append(
                    {
                        'Alerta': titulo.replace("'"," "),
                        'Chassi': chassi,
                        'Data': data_alerta[2],
                        'Hora': data_alerta[1],
                        'Horimetro': horimetro,
                        'Latitude': latitude,
                        'Longitude': longitude,
                        'Modelo': machine_model[0]['value'],
                        'Severidade': severidade
                        #'Controladora': dados_adicionais[0], É necessário pegar informações dessa conta da veneza? <- - Thiago Barros - 16/04/2025
                        #'Código do alerta': dados_adicionais[1]
                    }
                )

    return dtcs


def organizations():
    begin = 0
    all_customers = {}

    try:
        with open('data_customers.json', 'r') as dt_customers:
            # Pega a última data de modificação do arquivo JSON
            last_modif = datetime.fromtimestamp(os.path.getmtime('data_customers.json')).date()

            # Se a data da última modificação for igual a data de execução do app,
            # não será atualizado o banco de dados.
            # Isso reduzirá o tempo de execução do app.
            if last_modif == datetime.today().date():
                all_customers = json.load(dt_customers)
                return all_customers

    except FileNotFoundError:
        pass

    # Atualizar o total de clientes:
    url_1 = 'https://sandboxapi.deere.com/platform/organizations/'
    resposta_1 = api_get(access_token=token_get(), resource_url=url_1)
    total_clientes = resposta_1['total']

    while begin < total_clientes:
        url_org = f'https://sandboxapi.deere.com/platform/organizations/;start={begin};count=100'
        response = api_get(access_token=token_get(), resource_url=url_org)

        # Sai do código quando a página não mostrar mais clientes
        if len(response['values']) == 0:
            break

        for ch, valores in response.items():
            if type(valores) is int:  # Pula o total
                continue
            for customers in valores:
                if 'rel' in customers.keys():  # Pula os dicts de páginas
                    continue

                customer_name = customers['name']
                customer_id = customers['id']
                all_customers[customer_name] = customer_id
                # print(customers)

        begin += 100

    with open('data_customers.json', 'w+') as dt_customers:
        json.dump(all_customers, dt_customers, indent=4)
        return all_customers


def loop_machines(response_api, customer_name):
    for chave_m, valor_m in response_api.items():
        if chave_m != 'values':
            continue
        for maquinas in valor_m:
            id_maquinas = maquinas['id']
            try:  # Nem todas as máquinas tem o "vin" atrelado a ela
                pin = maquinas['vin']
                print(customer_name, pin, id_maquinas)
            except KeyError:
                pass


def machines():
    begin_1 = 0
    begin_2 = 0
    url_1 = 'https://sandboxapi.deere.com/platform/organizations/'

    # Total de clientes. A informação será atualizada sempre
    resposta_1 = api_get(access_token=token_get(), resource_url=url_1)
    total_clientes = resposta_1['total']

    # O loop passará página por página pegando o id de cada cliente
    while begin_1 < total_clientes:
        url_2 = f'https://sandboxapi.deere.com/platform/organizations/;start={begin_1};count=100'
        resposta_2 = api_get(access_token=token_get(), resource_url=url_2)

        for chave, valor in resposta_2.items():
            if chave != 'values':
                continue
            for cliente in valor:
                id_cliente = cliente['id']
                nome = cliente['name']

                url_3 = f'https://sandboxapi.deere.com/platform/organizations/;start={begin_2};count=100'
                resposta_3 = api_get(access_token=token_get(), resource_url=url_3)

                total_maquinas = resposta_3['total']

                # Essa condição irá passar por cada cliente pegando o id e o chassi de cada máquina
                if total_maquinas > 100:
                    while begin_2 < total_maquinas:
                        url_4 = f'https://sandboxapi.deere.com/platform/organizations/{id_cliente}/machines' \
                                f';start={begin_2};count=100'
                        resposta_4 = api_get(access_token=token_get(), resource_url=url_4)

                        loop_machines(resposta_4, nome)
                        begin_2 += 100
                    begin_2 = 0

                else:
                    url_5 = f'https://sandboxapi.deere.com/platform/organizations/{id_cliente}/machines' \
                            f';start={begin_2};count=100'
                    resposta_5 = api_get(access_token=token_get(), resource_url=url_5)

                    loop_machines(resposta_5, nome)

        begin_1 += 100


def get_alerts_from_pg(id_org):
    """Busca alertas da tabela opc_notifications_events no PostgreSQL.

    Substitui get_alerts() e get_alerts_veneza() — em vez de chamar a
    API JD, lê direto da tabela que a DAG já popula a cada 20 min.

    Filtros aplicados:
        - event_type IN ('DTC_ALERT', 'DTC_EVENT', 'MAINTENCE_ALERT')
        - org_id = id_org
        - date_created nos últimos 2 dias (mesma janela que a API retornava)
        - Exclui máquinas agrícolas: TRACTOR, SUGAR HARVESTING,
          COMBINE HARVESTING, SPRAYER (consistente com get_alerts_veneza)

    Retorna lista de dicts com as mesmas chaves que get_alerts() mais:
        notification_id, color_id, severity, three_letter_acronym, machine_model
    """
    from BD_alertas import ConnectionBD

    dtcs = []

    sql = """
        SELECT
            n.notification_id,
            n.title,
            n.serial_number,
            n.date_created,
            n.engine_hours,
            n.geom_coord_1 AS latitude,
            n.geom_coord_0 AS longitude,
            n.color_id,
            n.severity,
            n.three_letter_acronym,
            n.machine_model,
            n.machine_type,
            n.event_type
        FROM layer_bronze.opc_notifications_events n
        WHERE n.org_id = %s
          AND n.event_type IN ('DTC_ALERT', 'DTC_EVENT', 'MAINTENCE_ALERT')
          AND n.date_created >= (NOW() - INTERVAL '2 days')
        ORDER BY n.date_created DESC
    """

    try:
        c = ConnectionBD()
        c.conectar()
        c.cursor.execute(sql, (int(id_org),))
        rows = c.cursor.fetchall()
        c.desconectar()
    except Exception as e:
        print(f"[get_alerts_from_pg] Erro ao consultar PG: {e}")
        return dtcs

    # Máquinas agrícolas a excluir (uppercase)
    _EXCLUDED_TYPES = {
        'TRACTOR', 'SUGAR HARVESTING', 'COMBINE HARVESTING', 'SPRAYER'
    }

    for row in rows:
        (notification_id, titulo, chassi, date_created, engine_hours,
         latitude, longitude, color_id, severity,
         three_letter_acronym, machine_model, machine_type,
         event_type) = row

        # Filtro de máquinas agrícolas
        if machine_type and str(machine_type).strip().upper() in _EXCLUDED_TYPES:
            continue

        # Tratar título
        if titulo:
            titulo = " ".join(titulo.split()).replace("'", " ")
        else:
            titulo = ""

        # Filtro de manutenção genérica (mesmo do get_alerts original)
        if "Manutenção -" in titulo:
            import re
            pattern_str = r'^\d{2}-\d{2}-\d{4}$'
            if re.match(pattern_str, titulo[13:]):
                continue

        # Converter date_created (UTC) para BRT (-3h)
        if date_created:
            date_brt = date_created + timedelta(hours=-3)
            data_obj = date_brt.date()
            hora_str = date_brt.strftime('%H:%M')
        else:
            data_obj = datetime.today().date()
            hora_str = "00:00"

        # Horimetro
        try:
            horo = round(float(engine_hours), 1) if engine_hours else 0
        except (ValueError, TypeError):
            horo = 0

        # Coordenadas
        try:
            lat = float(latitude) if latitude else 0
            lng = float(longitude) if longitude else 0
        except (ValueError, TypeError):
            lat = 0
            lng = 0

        dtcs.append({
            'Alerta': titulo,
            'Chassi': chassi or "",
            'Data': data_obj,
            'Hora': hora_str,
            'Horimetro': horo,
            'Latitude': lat,
            'Longitude': lng,
            # Novos campos
            'notification_id': notification_id,
            'color_id': int(color_id) if color_id else None,
            'severity': severity or "",
            'three_letter_acronym': three_letter_acronym or "",
            'machine_model': machine_model or "",
            'event_type': event_type or "",
        })

    return dtcs


def get_all_alerts_from_pg(org_ids):
    """Busca alertas de TODOS os org_ids reutilizando UMA conexão PG.

    Abre uma única conexão e executa uma query por org_id.
    A tabela não tem índice utilizável para ANY() com 777+ valores,
    então iteramos individualmente — cada query individual é rápida.
    A conexão compartilhada elimina o overhead de N connects/disconnects.

    Retorna dict {org_id: [lista de alertas]}.
    """
    from BD_alertas import ConnectionBD
    from collections import defaultdict

    result = defaultdict(list)

    if not org_ids:
        return result

    sql = """
        SELECT
            n.notification_id,
            n.title,
            n.serial_number,
            n.date_created,
            n.engine_hours,
            n.geom_coord_1 AS latitude,
            n.geom_coord_0 AS longitude,
            n.color_id,
            n.severity,
            n.three_letter_acronym,
            n.machine_model,
            n.machine_type,
            n.event_type
        FROM layer_bronze.opc_notifications_events n
        WHERE n.org_id = %s
          AND n.event_type IN ('DTC_ALERT', 'DTC_EVENT', 'MAINTENCE_ALERT')
          AND n.date_created >= (NOW() - INTERVAL '2 days')
        ORDER BY n.date_created DESC
    """

    # Máquinas agrícolas a excluir (uppercase)
    _EXCLUDED_TYPES = {
        'TRACTOR', 'SUGAR HARVESTING', 'COMBINE HARVESTING', 'SPRAYER'
    }

    try:
        print(f"[get_all_alerts_from_pg] Conectando ao PG ({len(org_ids)} org_ids)...", flush=True)
        c = ConnectionBD()
        c.conectar()
        print(f"[get_all_alerts_from_pg] Conexao OK. Iterando org_ids...", flush=True)

        total_rows = 0
        for idx, oid in enumerate(org_ids):
            try:
                c.cursor.execute(sql, (int(oid),))
                rows = c.cursor.fetchall()
            except Exception as eq:
                print(f"[get_all_alerts_from_pg] Erro org_id={oid}: {eq}", flush=True)
                try:
                    c.desconectar()
                except Exception:
                    pass
                c = ConnectionBD()
                c.conectar()
                continue

            total_rows += len(rows)

            for row in rows:
                (notification_id, titulo, chassi, date_created, engine_hours,
                 latitude, longitude, color_id, severity,
                 three_letter_acronym, machine_model, machine_type,
                 event_type) = row

                if machine_type and str(machine_type).strip().upper() in _EXCLUDED_TYPES:
                    continue

                if titulo:
                    titulo = " ".join(titulo.split()).replace("'", " ")
                else:
                    titulo = ""

                if "Manutenção -" in titulo:
                    pattern_str = r'^\d{2}-\d{2}-\d{4}$'
                    if re.match(pattern_str, titulo[13:]):
                        continue

                if date_created:
                    date_brt = date_created + timedelta(hours=-3)
                    data_obj = date_brt.date()
                    hora_str = date_brt.strftime('%H:%M')
                else:
                    data_obj = datetime.today().date()
                    hora_str = "00:00"

                try:
                    horo = round(float(engine_hours), 1) if engine_hours else 0
                except (ValueError, TypeError):
                    horo = 0

                try:
                    lat = float(latitude) if latitude else 0
                    lng = float(longitude) if longitude else 0
                except (ValueError, TypeError):
                    lat = 0
                    lng = 0

                org_id_key = int(oid)

                result[org_id_key].append({
                    'Alerta': titulo,
                    'Chassi': chassi or "",
                    'Data': data_obj,
                    'Hora': hora_str,
                    'Horimetro': horo,
                    'Latitude': lat,
                    'Longitude': lng,
                    'notification_id': notification_id,
                    'color_id': int(color_id) if color_id else None,
                    'severity': severity or "",
                    'three_letter_acronym': three_letter_acronym or "",
                    'machine_model': machine_model or "",
                    'event_type': event_type or "",
                })

            if (idx + 1) % 100 == 0:
                print(f"[get_all_alerts_from_pg] {idx+1}/{len(org_ids)} org_ids processados ({total_rows} alertas)...", flush=True)

        c.desconectar()
        print(f"[get_all_alerts_from_pg] Concluido: {len(org_ids)} org_ids, {total_rows} alertas totais.", flush=True)

    except Exception as e:
        print(f"[get_all_alerts_from_pg] Erro ao consultar PG: {e}", flush=True)

    return result


def get_rts_alerts():
    """Busca TODOS os alertas prontos para envio em UMA única query.

    Usa opc_machine_alerts (tabela leve) com JOINs para trazer:
    - dados do equipamento (serial_number, model_name)
    - cliente e telefone (rts_contatos)
    - localização (localizacao_maquinas)
    - organização (opc_organizations)

    Filtros já aplicados na query:
    - color = RED
    - model_name = lista de modelos JD + Wirtgen
    - regional <> 'FORA'
    - org_role_in_possession = true
    - DISTINCT ON definition_id (último alerta por definição)
    - Janela: últimas 24h (ontem até agora em BRT)

    Retorna lista de dicts prontos para envio (sem iterar por org_id).
    """
    from BD_alertas import ConnectionBD

    sql = """
        SELECT DISTINCT ON (om.serial_number, oma.definition_id)
          oma.id_alert,
          oma.definition_id,
          oma.principal_id,
          oma.color,
          (oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo' AS alert_time,
          TO_CHAR(
            (oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo',
            'DD/MM/YYYY, HH24:MI'
          ) AS horario_local,
          oma.severity,
          oma.engine_hours,
          oma.description AS alert_description,
          oma.latitude,
          oma.longitude,
          om.serial_number,
          om.model_name,
          om.principal_id AS equip_principal_id,
          tccp.a1_nome AS cliente_protheus,
          lm.estado,
          lm.cidade,
          lm.mesorregiao,
          lm.regional,
          CASE
            WHEN om.model_name IN (
              '444G','524K-II','544K-II','624K-II','644K','724K','744L','824L','844L',
              '620G','622G','670G','672G','310L','310K','310 P','700J','750J','850J',
              '130G','160G','200G','210G','250G','350G','470G','870G'
            ) THEN 'John deere'
            WHEN om.model_name IN (
              '3411','3412','3414','HC 110','HC 110 P','HC 200 P','W 100 F','W 150 CF','W 150 F',
              'W 200 F','W 100 HR','W 100 R','W 130 Hi','SP 64','SP 94','SUPER 1300','SUPER 1303',
              'SUPER 1400','SUPER 1800-3','SUPER 800','WR 200','WR 240','HD 90K','HD O90V','HP 280'
            ) THEN 'Wirtgen'
            ELSE 'outros'
          END AS tipo,
          om.organization_id,
          oo.name AS organization_name,
          rt.cliente AS cliente_rt,
          rt.telefone
        FROM layer_bronze.opc_machine_alerts oma
        LEFT JOIN layer_bronze.opc_equipment om
          ON om.principal_id = oma.principal_id::int
        LEFT JOIN localizacao_maquinas lm
          ON lm.principal_id = om.principal_id
        LEFT JOIN layer_bronze.tb_cliente_chassi_protheus tccp
          ON tccp.vv1_chassi = om.serial_number
        LEFT JOIN layer_bronze.opc_organizations oo
          ON om.organization_id = oo.id
        LEFT JOIN rts_contatos rt
          ON om.organization_id::text = rt.jdlink_id
        WHERE oma.alert_time >= (
            (CURRENT_DATE - INTERVAL '1 day')::timestamp
            AT TIME ZONE 'America/Sao_Paulo'
          ) AT TIME ZONE 'UTC'
          AND oma.alert_time < (
            CURRENT_DATE::timestamp
            AT TIME ZONE 'America/Sao_Paulo'
          ) AT TIME ZONE 'UTC'
          AND oma.color = 'RED'
          AND om.model_name IN (
            '3411','3412','3414','HC 110','HC 110 P','HC 200 P','W 100 F','W 150 CF','W 150 F',
            'W 200 F','W 100 HR','W 100 R','W 130 Hi','SP 64','SP 94','SUPER 1300','SUPER 1303',
            'SUPER 1400','SUPER 1800-3','SUPER 800','WR 200','WR 240','HD 90K','HD O90V','HP 280',
            '444G','524K-II','544K-II','624K-II','644K','724K','744L','824L','844L',
            '620G','622G','670G','672G','310L','310K','310 P','700J','750J','850J',
            '130G','160G','200G','210G','250G','350G','470G','870G'
          )
          AND lm.regional <> 'FORA'
          AND om.org_role_in_possession = 'true'
        ORDER BY
          om.serial_number,
          oma.definition_id,
          oma.alert_time DESC
    """

    alertas = []

    try:
        print("[get_rts_alerts] Conectando ao PG...", flush=True)
        c = ConnectionBD()
        c.conectar()
        print("[get_rts_alerts] Executando query unificada...", flush=True)
        c.cursor.execute(sql)
        rows = c.cursor.fetchall()
        c.desconectar()
        print(f"[get_rts_alerts] Query OK: {len(rows)} alertas retornados.", flush=True)
    except Exception as e:
        print(f"[get_rts_alerts] Erro: {e}", flush=True)
        return alertas

    for row in rows:
        (id_alert, definition_id, principal_id, color,
         alert_time, horario_local, severity, engine_hours,
         alert_description, latitude, longitude,
         serial_number, model_name, equip_principal_id,
         cliente_protheus, estado, cidade, mesorregiao, regional,
         tipo, organization_id, organization_name,
         cliente_rt, telefone) = row

        # Tratar título do alerta
        titulo = ""
        if alert_description:
            titulo = " ".join(alert_description.split()).replace("'", " ")

        # Horimetro
        try:
            horo = round(float(engine_hours), 1) if engine_hours else 0
        except (ValueError, TypeError):
            horo = 0

        # Coordenadas
        try:
            lat = float(latitude) if latitude else 0
            lng = float(longitude) if longitude else 0
        except (ValueError, TypeError):
            lat = 0
            lng = 0

        # Data/hora do alerta (já em BRT)
        if alert_time:
            data_obj = alert_time.date()
            hora_str = alert_time.strftime('%H:%M')
        else:
            data_obj = datetime.today().date()
            hora_str = "00:00"

        # Nome do cliente: prioriza rts_contatos, fallback organization_name
        nome_cliente = (cliente_rt or organization_name or "").strip()

        # Telefone
        tel = str(telefone).strip() if telefone else ""

        alertas.append({
            'id_alert': id_alert,
            'definition_id': definition_id,
            'principal_id': principal_id,
            'Alerta': titulo,
            'Chassi': serial_number or "",
            'Data': data_obj,
            'Hora': hora_str,
            'horario_local': horario_local or "",
            'Horimetro': horo,
            'Latitude': lat,
            'Longitude': lng,
            'color_id': 3,  # RED = 3 (query já filtra RED)
            'severity': severity or "",
            'machine_model': model_name or "",
            'tipo': tipo or "",
            'organization_id': organization_id,
            'organization_name': organization_name or "",
            'cliente': nome_cliente,
            'telefone': tel,
            'cliente_protheus': cliente_protheus or "",
            'estado': estado or "",
            'cidade': cidade or "",
            'regional': regional or "",
        })

    return alertas


if __name__ == '__main__':
    infos = get_alerts(577151)

    print(infos)
