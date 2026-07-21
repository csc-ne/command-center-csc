def str_to_float(s):
    # Identifica o código do alerta
    try:
        float(s)
        return True
    except ValueError:
        return False
    

def extract_info(alert):
    if alert.upper() == "LOW FUEL":
        return "Não identificado", "Não identificado"
    
    controller = "" 
    code_alert = ""
    # Lista de todas as controladoras
    controllers = ['ECU', 'VCU', 'TCU', 'JDL', 'MCZ', 'PDU']

    # Formata o código de falha, retirando os espaços desnecessários
    alert_to_list = [string for string in alert.split(" ") if len(string) != 0]

    # Busca a controladora e o código do alerta no texto do alerta
    for item in alert_to_list:
        if item in controllers:
            controller = item
    

    if len(controller) != 0:
        controller_idx = alert_to_list.index(controller)
        code_alert = alert_to_list[controller_idx + 1]
        return controller, code_alert
    else:
        return "Não identificado", "Não identificado"

if __name__ == "__main__":
    alert = "INFO    ECU 000100.02    Engine oil pressure sensor circuit fault.  -  Troubleshooting required."
    alert2 = "INFO MCZ 011208.04  Pump 2 Flow Control Pressure Sensor Circuit Low Input"

    print(extract_info(alert2)[1].split('.')[0] in ['000110', '000100'])

    