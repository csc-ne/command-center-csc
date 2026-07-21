# =======================================================================
# VENEZA EQUIPAMENTOS SA
# CENTRO DE SOLUCOES CONECTADAS - CSC
# REPORT AUTOMATICO DE DESEMPENHO - RAD
# DESENVOLVIDO POR THIAGO BARROS - thiago.barros@venezanet.com - 2026.1
# VERSÃO ESTÁVEL - 0.2.6.4 - Data 04/06/2026 - Fluxo Contínuo Funcional
# =======================================================================


# Módulo de Configuração - Acessos


import os
import platform
from dotenv import load_dotenv

# .env centralizado em C:\env\.env no host Windows.
# No container Linux, o docker-compose monta esse arquivo em /app/.env.
_ENV_PATH = r"C:\env\.env" if platform.system() == "Windows" else "/app/.env"
load_dotenv(_ENV_PATH)

class Config:
    
    #===================================
    # Informações de Acesso ao Banco
    #===================================

    PG_HOST= os.getenv('PG_HOST')
    PG_PORT= os.getenv('PG_PORT')
    PG_DB=   os.getenv('PG_DB')
    PG_USER= os.getenv('PG_USER')
    PG_PASS= os.getenv('PG_PASS')
