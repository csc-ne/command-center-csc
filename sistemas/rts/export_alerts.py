from sqlalchemy import create_engine
from dotenv import load_dotenv
from datetime import datetime
from BD_alertas import BancoDados
import os
import pandas as pd

directory = f'C:\\RTS {datetime.now().year}'


def create_folder_if_does_not_exists(month):
    # Verifica a existência da pasta
    if not os.path.isdir(f'{directory}/{month}'):
        os.makedirs(f'{directory}/{month}')


def export_table():
    db = BancoDados(nome_tabela='alertas')

    dt_create_table = db.dt_tabela()
    today = datetime.today().date()

    # Configuração das variáveis
    # .env centralizado em C:\env\.env no host Windows.
    import platform as _platform
    _env_path = r"C:\env\.env" if _platform.system() == "Windows" else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_env_path)
    pg_host = os.environ.get("PG_HOST")
    pg_port = os.environ.get("PG_PORT", "5432")
    pg_db = os.environ.get("PG_DB")
    pg_user = os.environ.get("PG_USER")
    pg_pass = os.environ.get("PG_PASS")

    # Conexão com o BD PostgreSQL
    engine = create_engine(f"postgresql+psycopg2://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}")
    conn = engine.raw_connection()

    # Comando SQL para pegar os alertas
    df = pd.read_sql(f"SELECT * FROM rts_alertas", conn)

    match dt_create_table.month:
        case 1:
            create_folder_if_does_not_exists('Janeiro')
            df.to_excel(f'{directory}/Janeiro/Alertas_{dt_create_table}_A_{today}.xlsx', index=False)
        case 2:
            create_folder_if_does_not_exists('Fevereiro')
            df.to_excel(f'{directory}/Fevereiro/Alertas_{dt_create_table}_A_{today}.xlsx', index=False)
        case 3:
            create_folder_if_does_not_exists('Março')
            df.to_excel(f'{directory}/Março/Alertas_{dt_create_table}_A_{today}.xlsx', index=False)
        case 4:
            create_folder_if_does_not_exists('Abril')
            df.to_excel(f'{directory}/Abril/Alertas_{dt_create_table}_A_{today}.xlsx', index=False)
        case 5:
            create_folder_if_does_not_exists('Maio')
            df.to_excel(f'{directory}/Maio/Alertas_{dt_create_table}_A_{today}.xlsx', index=False)
        case 6:
            create_folder_if_does_not_exists('Junho')
            df.to_excel(f'{directory}/Junho/Alertas_{dt_create_table}_A_{today}.xlsx', index=False)
        case 7:
            create_folder_if_does_not_exists('Julho')
            df.to_excel(f'{directory}/Julho/Alertas_{dt_create_table}_A_{today}.xlsx', index=False)
        case 8:
            create_folder_if_does_not_exists('Agost')
            df.to_excel(f'{directory}/Agosto/Alertas_{dt_create_table}_A_{today}.xlsx', index=False)
        case 9:
            create_folder_if_does_not_exists('Setembro')
            df.to_excel(f'{directory}/Setembro/Alertas_{dt_create_table}_A_{today}.xlsx', index=False)
        case 10:
            create_folder_if_does_not_exists('Outubro')
            df.to_excel(f'{directory}/Outubro/Alertas_{dt_create_table}_A_{today}.xlsx', index=False)
        case 11:
            create_folder_if_does_not_exists('Novembro')
            df.to_excel(f'{directory}/Novembro/Alertas_{dt_create_table}_A_{today}.xlsx', index=False)
        case 12:
            create_folder_if_does_not_exists('Dezembro')
            df.to_excel(f'{directory}/Dezembro/Alertas_{dt_create_table}_A_{today}.xlsx', index=False)


if __name__ == '__main__':
    export_table()