# =======================================================================
# VENEZA EQUIPAMENTOS SA
# CENTRO DE SOLUCOES CONECTADAS - CSC
# REPORT AUTOMATICO DE DESEMPENHO - RAD
# DESENVOLVIDO POR THIAGO BARROS - thiago.barros@venezanet.com - 2026.1
# VERSÃO ESTÁVEL - 0.2.6.4 - Data 04/06/2026 - Fluxo Contínuo Funcional
# =======================================================================

# === Bibliotecas para Funcionamento de Fluxos Internos

import gc
import sys
import pandas as pd
from copy import deepcopy
from time import sleep
from datetime import datetime, timedelta
from pathlib import Path
from matplotlib import font_manager
from matplotlib import pyplot as plt
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.units import cm
from PyPDF2 import PdfMerger
from kernel.texts import *
from kernel.modulo_consulta import BancoService
from kernel.modulo_sql_rev2 import Resultados
from kernel.modulo_grafico import Graficos
from kernel.modulo_estatistico import Estatistica
from pdf.modulo_pdf import Relatorio
from tqdm import tqdm


#NOVO - LISTA DE CLIENTES PARA EXTRAÇÃO DE RELATÓRIOS - 04/05/2026

valores = [
    5975148,
    598163,
    496030,
    5926509,
    607841,
    571071,
    554489,
    450654,
    581612,
    5917416,
    6117790,
    7061243,
    621325,
    5840771,
    5766479,
    6003041,
    600536,
    5844161,
    560675,
    5921408,
    551817,
    1621661,
    550231,
    454791,
    491634,
    4555181,
    4515901,
    450059,
    326042,
    536521,
    624203,
    584175,
    3502241,
    482536,
    321762,
    440795,
    291331,
    294172,
    3801681,
    442254,
    577151,
    623142
]

# ============================================================================
# 1. PARÂMETROS GERAIS 
# ============================================================================

# === Fonte Heveltica

ARQUIVO_FONTE_HELVETICA = Path("fonts/helvetica-255/Helvetica.ttf")

try:
    ARQUIVO_FONTE_HELVETICA.exists()
    print("Arquivo de Fonte Localizado")

except:
    print("Erro de Execução, Arquivo de Fonte Não Encontrado")
    sys.exit(1)
    
# === Constantes

ESPACAMENTO_TABELA_A3 = 5

# === Paleta de Cores Padrão

AMARELO_JOHN_DEERE = "#F0AB00"
CINZA_JOHN_DEERE = "#5E6A71"
PRETO_JOHN_DEERE = "#1E1E1E"
CINZA_ESCURO = "#555454"
VERMELHO = "#FF0000"
AZUL = "#302AC9"
BRANCO = "#E6E6E6"
AMARELO_ALERTA = "#BCBC16"

# === Formatação - CARD KPI:

KPI_FMT = {"largura": 5, 
           "altura": 2.5, 
           "tamanho": 9}

# === Meses Por Extenso:

MESES = [
    "JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
]

# === Formatação - Rótulos

#Severidade de Alertas

MAP_SEVERITY = {
    "INFO": "Alertas Informativos",
    "MEDIUM": "Alertas de Atencao",
    "HIGH": "Alertas Criticos",
    "UNKNOWN": "Alertas Não Identificados"
}

#Modelo de Equipamentos (Tabela de Alertas)

MAP_MODELOS_ALERTA = {
    "4wd Loader": "Carregadeiras",
    "Crawler Dozer": "Tratores de Esteiras",
    "Crawler Excavator": "Escavadeiras",
    "Motor Grader": "Motoniveladora",
    "Backhoes": "Retroescavadeiras",
    "Two-wheel Drive Tractors - 90 Hp To Under 140 Hp": "Trator Agricola",
}

#Modelo de Equipamentos (Demais Tabelas)

MAP_TIPOS_PT_EN = {
    "Motoniveladora": "Motor Grader",
    "Escavadeira": "Excavator",
    "Trator de Esteiras": "Dozer",
    "Retroescavadeira": "Backhoe",
    "Carregadeira": "Loader",
}

#Modelo de Equipamentos (ISG)

MAP_FILTROS_ISG = {
    "retro": "Backhoe",
    "carreg": "Loader",
    "moto": "Motor Grader",
    "trator": "Dozer",
    "esc": "Excavator",
}

# === Formatação - Cores Alertas

CORES_ALERTA = {
    "Alertas Informativos": AZUL,
    "Alertas de Atencao": AMARELO_ALERTA,
    "Alertas Criticos": VERMELHO,
}

# === Arquivos temporarios e caminhos padronizados de saída

ARQUIVO_A3_DESEMPENHO = "ARQUIVO_1_DESEMPENHO.pdf"
ARQUIVO_A3_ALERTAS = "ARQUIVO_2_ALERTAS.pdf"
ARQUIVO_A3_GARANTIA = "ARQUIVO_3_GARANTIA.pdf"

# === PDFs temporarios por seção do relatório principal

ARQUIVOS_SECOES_PDF = {
    "capa": "SEC_01_CAPA.pdf",
    "introducao": "SEC_02_INTRODUCAO.pdf",
    "indicadores": "SEC_03_INDICADORES.pdf",
    "comunicacao": "SEC_04_COMUNICACAO.pdf",
    "geolocalizacao": "SEC_05_GEOLOCALIZACAO.pdf",
    "utilizacao_resumo": "SEC_06_UTILIZACAO_RESUMO.pdf",
    "alertas_abertura": "SEC_07_ALERTAS_ABERTURA.pdf",
    "analises_oleo": "SEC_08_ANALISES_OLEO.pdf",
    "analise_garantia": "SEC_09_GARANTIA.pdf",
    "encerramento": "SEC_10_ENCERRAMENTO.pdf",
}


# === Caminhos padronizados dos gráficos de alertas

PATH_ALERTAS_IMAGENS = {
    "distribuicao": "alertas_0.png",
    "criticidade": "alertas_1.png",
    "criticidade_maquina": "alertas_2.png",
    "criticidade_temporal": "alertas_3.png",
    "info_temporal": "alertas_4.png",
    "atencao_temporal": "alertas_5.png",
    "critico_temporal": "alertas_6.png",
    "critico_descritivo": "alertas_7.png",
}

# === Caminhos padronizados dos gráficos de performance

PATH_PERFORMANCE_IMAGENS = {
    "retro_1": "fig1.png",
    "retro_2": "fig2.png",
    "trator_1": "fig3.png",
    "trator_2": "fig4.png",
    "escava_1": "fig5.png",
    "escava_2": "fig6.png",
    "moto_1": "fig7.png",
    "moto_2": "fig8.png",
    "carreg_1": "fig9.png",
    "carreg_2": "fig10.png",
}

# === Páginas auxiliares da seção de alertas e seções complementares

PATH_PAGINAS_ALERTAS = {
    "grafico_1": "labels/8_1_pag.png",
    "grafico_2": "labels/8_2_pag.png",
    "grafico_3": "labels/8_3_pag.png",
    "grafico_4": "labels/8_4_pag.png",
    "tabelas_criticas": "labels/8_5_pag.png",
}

PATH_PAGINAS_COMPLEMENTARES = {
    "amostras_com_resultado": "labels/9_1_pag.png",
    "amostras_com_resultado_detalhamento": "labels/9_1_1_pag.png",
    "amostras_sem_resultado": "labels/9_2_pag.png",
}

# === Páginas auxiliares da seção de garantia em A3
PATH_PAGINAS_GARANTIA = {
    "tabela_basica": "labels/10_1_pag.png",
    "tabela_estendida": "labels/10_2_pag.png",
}

# ============================================================================
# 2. IMPORTAÇÃO DAS CLASSES
# ===========================================================================

kernel_banco = BancoService()
kernel_consulta = Resultados()
kernel_graficos = Graficos()
kernel_estatisticas = Estatistica()

# ============================================================================
# 3. FORMATAÇÃO NUMÉRICA
# ===========================================================================

# === Converter números para tipo numérico

def func_formatacao_tipo_numerico(
    df: pd.DataFrame,
    colunas: list[str],
    decimal: str = ".",
) -> pd.DataFrame:
    """Converte colunas para numerico preservando casas decimais."""
    df = df.copy()

    for coluna in colunas:
        if coluna not in df.columns:
            continue

        serie = df[coluna]

        if pd.api.types.is_numeric_dtype(serie):
            df[coluna] = pd.to_numeric(serie, errors="coerce")
            continue

        serie = (
            serie.astype(str)
            .str.strip()
            .replace({
                "": pd.NA,
                "nan": pd.NA,
                "None": pd.NA,
                "SEM DADOS": pd.NA,
                "Sem Dados": pd.NA,
                "SEM_DADOS": pd.NA,
            })
        )

        if decimal == ",":
            serie = serie.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        else:
            serie = serie.str.replace(",", ".", regex=False)

        df[coluna] = pd.to_numeric(serie, errors="coerce")

    return df

# === Formatação de valores no padrão M.CDD, ddd

def func_formatacao_numero(valor) -> str:
    """Formata numeros no padrao brasileiro sem quebrar valores nulos."""
    
    if pd.isna(valor):
        return ""
    
    else:
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    

# === Formatação Percentual - decimal com vírgula e retorno zero quando indeterminação
    
def func_formatacao_percentual(parte, total, casas: int = 2) -> float:
    """Calcula percentual protegendo contra divisao por zero."""
    
    if total in (0, None) or pd.isna(total):
        return 0.0
    
    else:
        return round((parte / total) * 100, casas)
    

# ============================================================================
# 4. FORMATAÇÃO DE GRÁFICO
# ===========================================================================
    
# === Formatação padrão de gráficos

def func_formatacao_graficos(fmt: dict, figsize=(50, 18), alpha=0, eixos=50, ticks=50, rotulo_dados=50) -> dict:

    """Aplica configuracao visual padrao aos formatos graficos."""
    
    fmt["figura"]["figsize"] = figsize
    fmt["figura"]["alpha"] = alpha
    fmt["fonte"]["family"] = "Helvetica"
    fmt["fonte"]["rotulo_dados"] = rotulo_dados
    fmt["fonte"]["eixos"] = eixos
    fmt["fonte"]["ticks"] = ticks

    return fmt

# === Formatação padrão de gráficos de barras horizontais

fmt_barras = func_formatacao_graficos(kernel_graficos.fmt_barras_horizontais(), figsize=(45, 18))
fmt_barras["barras"]["largura"] = 0.5
fmt_barras["eixos"]["mostrar_linha_x"] = False
fmt_barras["eixos"]["cor_linha_x"] = BRANCO
fmt_barras["rotulos"]["mostrar"] = True

# === Formatação padrão de gráficos de barras empilhadas

fmt_empilhadas = func_formatacao_graficos(kernel_graficos.fmt_barras_empilhadas_percentual())
fmt_empilhadas["barras"]["cores_por_categoria"] = CORES_ALERTA
fmt_empilhadas["legenda"]["mostrar"] = False
fmt_empilhadas["eixos"]["mostrar_grade_vertical"] = False
fmt_empilhadas["eixos"]["mostrar_grade_horizontal"] = False


# === Formatação padrão de gráficos de barras verticais

fmt_vertical = func_formatacao_graficos(kernel_graficos.fmt_barras_verticais(), eixos=30)
fmt_vertical["eixos"]["mostrar_grade_vertical"] = False
fmt_vertical["eixos"]["mostrar_grade_horizontal"] = False
fmt_vertical["eixos"]["angulo_rotulo_x"] = 90
fmt_vertical["rotulos"]["mostrar"] = True
fmt_vertical["eixos"]["mostrar_linha_x"] = False
fmt_vertical["eixos"]["mostrar_linha_y"] = False
fmt_vertical["rotulos"]["casas_decimais"] = 0

# Reaproveita o formato vertical base e altera apenas o que muda.

fmt_vertical_longa = deepcopy(fmt_vertical)
fmt_vertical_longa["eixos"]["angulo_rotulo_x"] = 0

# === Formatação padrão de gráficos de barras múltiplas

fmt_barras_mult = func_formatacao_graficos(kernel_graficos.fmt_barras_multiplas(), figsize=(45, 18))
fmt_barras_mult["barras"]["largura"] = 0.5
fmt_barras_mult["eixos"]["mostrar_linha_x"] = False
fmt_barras_mult["eixos"]["cor_linha_x"] = BRANCO
fmt_barras_mult["rotulos"]["mostrar"] = True
fmt_barras_mult["rotulos"]["casas_decimais"] = 0
fmt_barras_mult["barras"]["raio"] = 0.8
fmt_barras_mult["legenda"]["mostrar"] = False

# === Formatação padrão de gráficos de pizza

fmt_pizza = kernel_graficos.fmt_pizza()
fmt_pizza["figura"]["figsize"] = (45, 18)
fmt_pizza["figura"]["alpha"] = 0
fmt_pizza["fonte"]["family"] = "Helvetica"
fmt_pizza["fonte"]["color"] = PRETO_JOHN_DEERE
fmt_pizza["fonte"]["rotulo_dados"] = 50
fmt_pizza["fonte"]["ticks"] = 50
fmt_pizza["pizza"]["cores"] = [AZUL, AMARELO_ALERTA, VERMELHO]

# === Formatação padrão de tabelas

def func_formatacao_tabelas(**kwargs) -> dict:
    """Retorna formato base para tabelas e permite sobrescritas."""
   
    fmt = {
        "fonte": "Helvetica",
        "fonte_cabecalho": "Helvetica-Bold",
        "tamanho_valores": 12,
        "tamanho_cabecalhos": 12,
        "nomes_colunas": None,
        "cor_texto": PRETO_JOHN_DEERE,
        "cor_texto_cabecalho": AMARELO_JOHN_DEERE,
        "cor_fundo_cabecalho": PRETO_JOHN_DEERE,
        "cor_fundo_linhas": BRANCO,
        "alinhamento_texto": "center",
        "alinhamento_tabela": "center",
        "entre_linhas": 13,
        "espacamento_apos": 13,
        "larguras_colunas": None,
    }
    fmt.update(kwargs)
    return fmt

# === Formatação de datas no padrão BR ordena a tabela automáticamente

def func_formatacao_data(
    df: pd.DataFrame,
    coluna: str,
    formato_entrada: str,
    formato_saida: str = "%d-%m-%Y",
    ascending: bool = False,
) -> pd.DataFrame:
    
    """Converte, ordena e devolve a coluna de data em formato textual."""
    
    df = df.copy()
    df[coluna] = pd.to_datetime(df[coluna], format=formato_entrada, errors="coerce")
    df = df.sort_values(by=coluna, ascending=ascending).reset_index(drop=True)
    df[coluna] = df[coluna].dt.strftime(formato_saida)
    return df

# === Formatação de espaço vazio

def func_formatacao_vazio(pdf: Relatorio, font_size: int = 12) -> None:

    """Insere duas linhas vazias padrao."""
    
    pdf.add_paragraph(text=" ", font_size=font_size, leading_cm=1, align="justify")
    pdf.add_paragraph(text=" ", font_size=font_size, leading_cm=1, align="justify")


# ============================================================================
# 5. FORMATAÇÃO DE TABELAS (EM MODIFICAÇÃO)
# ===========================================================================

def func_formatacao_tabelas(**kwargs) -> dict:
    """Retorna formato base para tabelas e permite sobrescritas."""
   
    fmt = {
        "fonte": "Helvetica",
        "fonte_cabecalho": "Helvetica-Bold",
        "tamanho_valores": 12,
        "tamanho_cabecalhos": 12,
        "nomes_colunas": None,
        "cor_texto": PRETO_JOHN_DEERE,
        "cor_texto_cabecalho": AMARELO_JOHN_DEERE,
        "cor_fundo_cabecalho": PRETO_JOHN_DEERE,
        "cor_fundo_linhas": BRANCO,
        "alinhamento_texto": "center",
        "alinhamento_tabela": "center",
        "entre_linhas": 13,
        "espacamento_apos": 13,
        "larguras_colunas": None,
    }
    fmt.update(kwargs)
    return fmt


# === TABELA 1 - Formatação de rótulos: tabela de comunicação

fmt_tabela_1= func_formatacao_tabelas(
    nomes_colunas={
        "chassi": "Chassi",
        "modelo": "Modelo",
        "data_comunicacao": "Última Data de Comunicação",
        "status_comunicacao": "Status da Comunicação",
    }
)

# === TABELA 2 - Formatação de rótulos: tabela de geolocalização

fmt_tabela_2 = func_formatacao_tabelas(
    tamanho_valores=10,
    tamanho_cabecalhos=10,
    nomes_colunas={
        "chassi": "Chassi",
        "estado": "Estado",
        "cidade": "Municipio",
    },
)

# === TABELA 3 - Formatação de rótulos: tabela de utilização

fmt_tabela_3 = func_formatacao_tabelas(
    nomes_colunas={
        "pin": "Chassi",
        "model_clean": "Modelo do Equipamento",
        "horas_trabalhadas": "Total de Horas em Trabalho",
        "horas_ociosas": "Total de Horas em Ociosidade",
        "eficiencia_pct": "Percentual de Utilizacao em Trabalho",
        "ociosidade_pct": "Percentual de Utilizacao em Ociosidade",
    }
)

# === TABELA 4 - Formatação de rótulos: tabela de alertas

fmt_tabela_4 = func_formatacao_tabelas(
    nomes_colunas={
        "serial_number": "Chassi",
        "model_name": "Modelo do Equipamento",
        "alert_data": "Data do Alerta",
        "description": "Descrição do Alerta",
        "severity": "Severidade",
    }
)

# === TABELA 6 - Formatação de rótulos: tabela de análise de óleos

"""
em desenvolvimento

"""

# === TABELA 5 - Formatação de rótulos: tabela de garantias

fmt_tabela_5 = func_formatacao_tabelas(
    nomes_colunas={
        "pin": "Chassi",
        "status_garantia_basica": "Condição da Garantia Básica",
        "dias_para_vencimento_basica": "Dias Restantes da Garantia Básica",
        "data_vencimento_garantia_basica": "Data de Vencimento da Garantia Básica",})

fmt_tabela_6 = func_formatacao_tabelas(
    nomes_colunas={
        "pin": "Chassi",
        "status_garantia_estendida": "Condição da Garantia Estendida",
        "dias_para_vencimento_estendida": "Dias Restantes da Garantia Estendida",
        "tipo_garantia_estendida": "Tipo de Garantia Estendida",
        "data_vencimento_garantia_estendida": "Data de Vencimento da Garantia Estendida",})

gara_valores = ["VIGENTE", "A VENCER", "VENCIDA", "VENCIDO"]
gara_cores = ["#C6EFCE", CINZA_JOHN_DEERE, "#FFC7CE", "#FFC7CE"]


#============================================================================
# 4. VALIDAÇÃO
# ===========================================================================

# === Validação de Colunas - retorna zero no registro vazio

def func_validacao_colu(df: pd.DataFrame, colunas: list[str], valor_padrao=0) -> pd.DataFrame:
    """Garante a existencia das colunas informadas."""
   
    df = df.copy()

    for coluna in colunas:

        if coluna not in df.columns:
            df[coluna] = valor_padrao
    
    return df

# === Validação de dados: Evitar erro nos gráficos

def func_validacao_dataframe_dados(df: pd.DataFrame, colunas=None) -> bool:
    
    """
    Verifica se o dataframe possui dados válidos para geração do gráfico.
    Se colunas for informado, exige que ao menos uma delas tenha valor numérico
    não nulo e soma diferente de zero.
    """
    
    if df is None:
        return False

    if not colunas:
        return True

    colunas_existentes = [col for col in colunas if col in df.columns]
    
    if not colunas_existentes:
        return False

    for coluna in colunas_existentes:
       
        serie = pd.to_numeric(df[coluna], errors="coerce").fillna(0)
       
        if serie.abs().sum() > 0:
            return True

    return False

def func_validacao_alertas(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona a coluna Total Alertas de forma segura."""
    
    colunas_alerta = [
        "Alertas Criticos",
        "Alertas Informativos",
        "Alertas de Atencao",
    ]
    df = func_validacao_colu(df, colunas_alerta, 0)
    df["Total Alertas"] = df[colunas_alerta].sum(axis=1)
    return df

def func_validacao_valores_graficos(
    func_grafico,
    df: pd.DataFrame,
    mensagem: str = "Sem informação no período",
    colunas_validacao=None,
    **kwargs,
):
    """
    Gera gráfico quando houver dados válidos.
    Caso contrário, retorna um objeto textual padronizado.
    """

    if not func_validacao_dataframe_dados(df, colunas_validacao):
        return {"tipo": "texto", "conteudo": mensagem}

    try:
        grafico = func_grafico(df=df, **kwargs)
        return {"tipo": "grafico", "conteudo": grafico}
    
    except Exception:
        return {"tipo": "texto", "conteudo": mensagem}
    
# ============================================================================
# 5. FUNÇÕES DE OUTPUT 
# ===========================================================================

def func_output_data(dias: int = 30) -> dict:
    """Retorna todas as representacoes de data usadas no relatorio."""

    agora = datetime.now()

    inicio = agora - timedelta(days=dias)

    info_datas = {

        "agora": agora,
        "inicio": inicio,
        "data_inicial": inicio.strftime("%d-%m-%Y"),
        "data_final": agora.strftime("%d-%m-%Y"),
        "data_inicial_formatada": inicio.strftime("%d_%m_%Y"),
        "data_final_formatada": agora.strftime("%d_%m_%Y"),
        "data_inicial_texto": inicio.strftime("%d-%m-%Y"),
        "data_final_texto": agora.strftime("%d-%m-%Y"),
        "data_capa": f"{MESES[agora.month - 1]}/{agora.year}",

    }

    return info_datas


def func_output_data_custom(data_inicial_iso: str, data_final_iso: str) -> dict:
    """
    Retorna o mesmo dict de func_output_data, mas a partir de datas
    customizadas no formato ISO (YYYY-MM-DD) vindas do formulário web.
    """
    inicio = datetime.strptime(data_inicial_iso, "%Y-%m-%d")
    fim = datetime.strptime(data_final_iso, "%Y-%m-%d")

    info_datas = {
        "agora": fim,
        "inicio": inicio,
        "data_inicial": inicio.strftime("%d-%m-%Y"),
        "data_final": fim.strftime("%d-%m-%Y"),
        "data_inicial_formatada": inicio.strftime("%d_%m_%Y"),
        "data_final_formatada": fim.strftime("%d_%m_%Y"),
        "data_inicial_texto": inicio.strftime("%d-%m-%Y"),
        "data_final_texto": fim.strftime("%d-%m-%Y"),
        "data_capa": f"{MESES[fim.month - 1]}/{fim.year}",
    }

    return info_datas


def func_output_tabela(df: pd.DataFrame) -> pd.DataFrame:
    """Cria copia formatada para tabela, sem destruir o dataframe numerico."""
    
    df_fmt = df.copy()
    
    for coluna in df_fmt.select_dtypes(include="number"):
        df_fmt[coluna] = df_fmt[coluna].map(func_formatacao_numero)
    
    return df_fmt


def func_output_pag_alertas(pdf: Relatorio, secoes: list[dict], fmt: dict) -> None:
    """Monta as paginas A3 de alertas criticos, evitando pagina extra ao final."""
    
    total = len(secoes)
    
    for indice, secao in enumerate(secoes):
        df_alerta = secao["df"]
        possui_dados = not df_alerta.empty

        pdf.set_background_image(secao["bg"])
        func_formatacao_vazio(pdf)
        pdf.spacer_cm(3)

        if possui_dados:
            pdf.add_dataframe(
                df_alerta,
                fmt=fmt,
                table_align="center",
                text_align="center",
            )
        else:
            pdf.add_paragraph(
                text="Sem alertas criticos no periodo.",
                font_size=30,
                leading_cm=1,
                align="center",
            )

        if indice < total - 1:
            pdf.new_page()


def func_output_fig_pdf_texto(
    pdf: Relatorio,
    obj,
    width_cm: float,
    height_cm: float,
    font_size: int = 12,
) -> None:
    """
    Insere gráfico no PDF ou, quando não houver dados, exibe texto substituto.
    """
    if isinstance(obj, dict) and obj.get("tipo") == "texto":
        pdf.spacer_cm(max(height_cm / 4, 1.5))
        pdf.add_paragraph(
            text=obj["conteudo"],
            font_size=font_size,
            leading_cm=1,
            align="center",
        )
        pdf.spacer_cm(max(height_cm / 4, 1.5))
        return

    conteudo = obj["conteudo"] if isinstance(obj, dict) else obj
    pdf.add_figure(
        conteudo,
        width_cm=width_cm,
        height_cm=height_cm,
        align="center",
    )

def func_output_pag_formato_a3(
    pdf: Relatorio,
    bg_tabela: str,
    bg_graficos: str,
    df_tabela: pd.DataFrame,
    figura_1,
    figura_2,
    fmt_tabela: dict,
) -> None:
    
    """Cria a sequencia padrao: pagina de tabela + pagina de dois graficos."""
    
    pdf.set_background_image(bg_tabela)
    func_formatacao_vazio(pdf)
    pdf.spacer_cm(ESPACAMENTO_TABELA_A3)

    if df_tabela is not None and not df_tabela.empty:
        pdf.add_dataframe(df_tabela, fmt=fmt_tabela, table_align="center", text_align="center")
    else:
        pdf.add_paragraph(
            text="Sem informação no período",
            font_size=12,
            leading_cm=1,
            align="center",
        )

    pdf.new_page()

    pdf.set_background_image(bg_graficos)
    pdf.add_paragraph(text=" ", font_size=5, leading_cm=1, align="justify")
    pdf.spacer_cm(0.8)
    func_output_fig_pdf_texto(pdf, figura_1, 29, 15)
    func_output_fig_pdf_texto(pdf, figura_2, 29, 11)
    pdf.spacer_cm(0.1)

    pdf.new_page()

    
def func_output_graficos(
    func_grafico,
    df: pd.DataFrame,
    mensagem: str = "Sem informação no período",
    colunas_validacao=None,
    **kwargs,
):
    """
    Gera gráfico quando houver dados válidos.
    Caso contrário, retorna um objeto textual padronizado.
    """
    return func_validacao_valores_graficos(
        func_grafico=func_grafico,
        df=df,
        mensagem=mensagem,
        colunas_validacao=colunas_validacao,
        **kwargs,
    )

# ============================================================================
# 7. FUNÇÕES DE CACHE
# ===========================================================================

def func_cache_temporarios(caminhos: list[str]) -> None:
    """
    Remove imagens e PDFs temporários gerados durante o processamento.
    Também limpa caches de figuras do matplotlib e executa garbage collection.
    """
    for caminho in caminhos:
       
        try:
            arquivo = Path(caminho)
            if arquivo.exists() and arquivo.is_file():
                arquivo.unlink()
        except Exception as exc:
            print(f"Falha ao remover artefato temporário {caminho}: {exc}")

    try:
        plt.close("all")
    except Exception:
        pass

    gc.collect()


def func_cache_lotes(especificacoes: list[dict]) -> dict:
    """Gera vários gráficos com uma única estrutura declarativa."""
    resultados = {}
    
    for spec in especificacoes:
       
        kwargs = spec.get("kwargs", {}).copy()
        
        resultados[spec["nome"]] = func_output_graficos(
            spec["func"],
            spec["df"],
            mensagem=spec.get("mensagem", "Sem informação no período"),
            colunas_validacao=spec.get("colunas_validacao"),
            **kwargs,
        )
    return resultados

# ============================================================================
# 8. FUNÇÕES DE GERAÇÃO
# ===========================================================================

# Páginas com gráficos
def func_adicionar_paginas_graficos(
    pdf: Relatorio,
    secoes: list[dict],
    espaco_inicial_cm: float = 1.3
) -> None:
    """Adiciona páginas compostas por pares de gráficos ou textos substitutos."""
    total = len(secoes)

    for indice, secao in enumerate(secoes):
        pdf.set_background_image(secao["bg"])
        pdf.spacer_cm(espaco_inicial_cm)

        for figura in secao["figuras"]:
            func_output_fig_pdf_texto(
                pdf,
                figura["fig"],
                figura["width_cm"],
                figura["height_cm"],
            )

        if indice < total - 1:
            pdf.new_page()

# Páginas personalizada com comunicação da frota

def func_preparar_pagina_comunicacao(
    pdf: Relatorio,
    texto: str,
    bg: str,
) -> None:
    """Prepara a página de comunicação com fundo e texto."""
    pdf.set_background_image(bg)
    pdf.spacer_cm(6)
    pdf.add_paragraph(text=texto, font_size=12, leading_cm=1, align="justify")
    pdf.spacer_cm(0.2)


def func_adicionar_tabela_comunicacao(
    pdf: Relatorio,
    df: pd.DataFrame,
    fmt: dict,
    cond_col: str,
    cond_values: list[str],
    cond_colors: list[str],
) -> None:
    """Adiciona a tabela de comunicação à página já preparada."""
    if df is None or df.empty:
        pdf.spacer_cm(2)
        pdf.add_paragraph(
            text="Sem informação no período",
            font_size=12,
            leading_cm=1,
            align="center",
        )
        return

    pdf.add_dataframe(
        df,
        fmt=fmt,
        table_align="center",
        text_align="center",
        cond_col=cond_col,
        cond_values=cond_values,
        cond_colors=cond_colors,
    )


def func_adicionar_pagina_comunicacao(
    pdf: Relatorio,
    df: pd.DataFrame,
    texto: str,
    fmt: dict,
    bg: str,
    cond_col: str,
    cond_values: list[str],
    cond_colors: list[str],
) -> None:
    """Concentra a montagem da página de comunicação da frota."""
    func_preparar_pagina_comunicacao(
        pdf=pdf,
        texto=texto,
        bg=bg,
    )

    func_adicionar_tabela_comunicacao(
        pdf=pdf,
        df=df,
        fmt=fmt,
        cond_col=cond_col,
        cond_values=cond_values,
        cond_colors=cond_colors,
    )

def salvar_pdf_a3_desempenho(nome_arquivo: str, secoes: list[dict], fmt_tabela: dict) -> None:
    """Gera o PDF auxiliar A3 de desempenho sem repetir a estrutura das páginas."""
    pdf = Relatorio(
        nome_arquivo=nome_arquivo,
        formato_pagina=landscape(A3),
        margins=(1 * cm, 1 * cm, 1 * cm, 1 * cm),
    )

    for secao in secoes[:-1]:
        func_output_pag_formato_a3(
            pdf,
            secao["bg_tabela"],
            secao["bg_graficos"],
            secao["df_tabela"],
            secao["figura_1"],
            secao["figura_2"],
            fmt_tabela,
        )

    ultima = secoes[-1]
    pdf.set_background_image(ultima["bg_tabela"])
    func_formatacao_vazio(pdf)
    pdf.spacer_cm(ESPACAMENTO_TABELA_A3)

    if ultima["df_tabela"] is not None and not ultima["df_tabela"].empty:
        pdf.add_dataframe(ultima["df_tabela"], fmt=fmt_tabela, table_align="center", text_align="center")
    else:
        pdf.spacer_cm(12)
        pdf.add_paragraph(text="Sem informação no período", font_size=12, leading_cm=1, align="center")

    pdf.new_page()
    pdf.set_background_image(ultima["bg_graficos"])
    pdf.add_paragraph(text=" ", font_size=5, leading_cm=1, align="justify")
    pdf.spacer_cm(0.8)
    func_output_fig_pdf_texto(pdf, ultima["figura_1"], 29, 15)
    func_output_fig_pdf_texto(pdf, ultima["figura_2"], 29, 11)
    pdf.spacer_cm(0.1)
    pdf.save()



def func_output_pag_tabela_a3(
    pdf: Relatorio,
    bg_tabela: str,
    df_tabela: pd.DataFrame,
    fmt_tabela: dict,
    cond_col: str | None = None,
    cond_values: list[str] | None = None,
    cond_colors: list[str] | None = None,
) -> None:
    """Cria uma pagina A3 com fundo e tabela centralizada."""

    pdf.set_background_image(bg_tabela)
    func_formatacao_vazio(pdf)
    pdf.spacer_cm(ESPACAMENTO_TABELA_A3)

    if df_tabela is None or df_tabela.empty:
        pdf.spacer_cm(12)
        pdf.add_paragraph(text="Sem informação no período", font_size=12, leading_cm=1, align="center")
        return

    kwargs_condicionais = {}
    if cond_col and cond_values and cond_colors:
        kwargs_condicionais = {
            "cond_col": cond_col,
            "cond_values": cond_values,
            "cond_colors": cond_colors,
        }

    pdf.add_dataframe(
        df_tabela,
        fmt=fmt_tabela,
        table_align="center",
        text_align="center",
        **kwargs_condicionais,
    )


def salvar_pdf_a3_garantia(nome_arquivo: str, secoes: list[dict]) -> None:
    """Gera o PDF auxiliar A3 da seção de garantia."""

    pdf = Relatorio(
        nome_arquivo=nome_arquivo,
        formato_pagina=landscape(A3),
        margins=(1 * cm, 1 * cm, 1 * cm, 1 * cm),
    )

    total = len(secoes)
    for indice, secao in enumerate(secoes):
        func_output_pag_tabela_a3(
            pdf=pdf,
            bg_tabela=secao["bg_tabela"],
            df_tabela=secao["df_tabela"],
            fmt_tabela=secao["fmt_tabela"],
            cond_col=secao.get("cond_col"),
            cond_values=secao.get("cond_values"),
            cond_colors=secao.get("cond_colors"),
        )
        if indice < total - 1:
            pdf.new_page()

    pdf.save()

# ============================================================================
# 9. SALVAMENTO - USAR EM CASO DE NÃO IMPORTAÇÃO DE PDF
# ===========================================================================

def salvar_relatorio(principal: Relatorio) -> None:
    """Salva o PDF principal."""
    principal.save()


def func_criar_pdf_a4(nome_arquivo: str) -> Relatorio:
    """Cria um PDF A4 temporario de uma secao do relatorio."""
    return Relatorio(
        nome_arquivo=nome_arquivo,
        formato_pagina=A4,
        margins=(3 * cm, 2 * cm, 2 * cm, 2 * cm),
    )


def func_salvar_secao_pdf(pdf: Relatorio) -> None:
    """Centraliza o salvamento de uma secao em PDF."""
    pdf.save()


def func_compilar_pdfs(nome_saida: str, arquivos: list[str]) -> None:
    """Compila PDFs ja gerados na ordem informada."""
    merger = PdfMerger()

    try:
        for arquivo in arquivos:
            caminho = Path(arquivo)
            if caminho.exists() and caminho.is_file():
                merger.append(str(caminho))
            else:
                print(f"Arquivo nao encontrado para compilacao: {arquivo}")

        with open(nome_saida, "wb") as saida:
            merger.write(saida)

    finally:
        merger.close()


# ======================================================================#
# EXECUÇÃO DA APLICAÇÃO - RDA - RELATÓRIOS DE DESEMPENHO AUTOMÁTICOS    #
# ======================================================================#


def rda_py_data_fixa(cliente_id: int, info_datas: dict = None, output_dir: str = None):
    """
    Gera relatório de desempenho para um cliente.

    Args:
        cliente_id: ID da organização no Operations Center.
        info_datas: dict de datas (de func_output_data ou func_output_data_custom).
                    Se None, usa func_output_data() padrão (30 dias).
        output_dir: diretório de saída para o PDF final. Se None, salva no cwd.

    Returns:
        str: caminho absoluto do PDF gerado.
    """
    if info_datas is None:
        info_datas = func_output_data()

    data_inicial = info_datas["data_inicial"]
    data_final   = info_datas["data_final"]

    print("# == (CONSULTA 1) - IDENTIFICAÇÃO DO CLIENTE")
    nome_cliente = kernel_consulta.consultar_nome_cliente(id_client=cliente_id)
    nome_cliente = str(nome_cliente.iloc[0, 0]) if not nome_cliente.empty else "Não Identificado"
    
    print(f"Nome do Cliente: {nome_cliente}")
    print(f"Client ID: {cliente_id}")

    print("# == (CONSULTA 2) - FROTA E GEOLOCALIZAÇÃO")
    cliente_frota = kernel_consulta.consultar_geolocalizacao(id_client=cliente_id)

    print("# == (CONSULTA 3) - FROTA E HORÍMETROS")
    cliente_horimetros = kernel_consulta.consultar_horimetros(id_client=cliente_id)

    print("# == (CONSULTA 4) - FROTA E COMUNICAÇÃO")
    cliente_comunicacao = kernel_consulta.consultar_status_comunicacao(id_client=cliente_id)

    print("# == (CONSULTA 5) - FROTA E UTILIZAÇÃO DIÁRIA")
    cliente_uso_diario = kernel_consulta.consultar_utilizacao_frota_diaria(id_client=cliente_id, 
                                                                            data_inicial=data_inicial, 
                                                                            data_final=data_final)
    
    print("# == (CONSULTA 6) - FROTA E UTILIZAÇÃO TOTAL PERIODO")
    cliente_uso_periodo = kernel_consulta.consultar_utilizacao_frota_acumulada(id_client=cliente_id, 
                                                                            data_inicial=data_inicial, 
                                                                            data_final=data_final)
    
    print("# == (CONSULTA 7) - FROTA E ALERTAS")
    cliente_alertas = kernel_consulta.consultar_alertas(id_client=cliente_id, 
                                                                            data_inicial=data_inicial, 
                                                                            data_final=data_final)

    print("# == (CONSULTA 8) - FROTA E ANÁLISES QUÍMICAS")
    cliente_analises_quimicas = kernel_consulta.consultar_analises_quimicas(id_client=cliente_id, 
                                                                            data_inicial=data_inicial, 
                                                                            data_final=data_final)

    print("# == (CONSULTA 9) - GARANTIA")
    cliente_garantia = kernel_consulta.consultar_garantia(id_client=cliente_id)

    # ======================================================================#
    # ETAPA 1 - GERAÇÃO DE TABELAS PADRONIZADAS
    # ======================================================================#

    print("# == NORMATIZANDO TABELAS")

    # OBS: Vou copiar as tabelas das consultas para tratar separadamente sem alterar o resultado inicial

    geolocalizacao_frota = cliente_frota.copy()
    horimetro_frota = cliente_horimetros.copy()
    comunicacao_frota = cliente_comunicacao.copy()
    utilizacao_diario_frota = cliente_uso_diario.copy()
    utilizacao_mensal_frota = cliente_uso_periodo.copy()
    alertas_frota = cliente_alertas.copy()
    quimica_frota = cliente_analises_quimicas.copy()
    garantia_frota = cliente_garantia.copy()

    # ======================================================================#
    # ETAPA 2 - MÉTRICAS DE COMUNICAÇÃO
    # ======================================================================#

    print("# == CALCULANDO INDICADORES DE COMUNICAÇÃO")

    contagem_status = cliente_comunicacao["status_comunicacao"].value_counts(dropna=False)

    tamanho_frota = int(contagem_status.sum())

    #Indicadores de Comunicação - Valor Decimal
    maquinas_comunicando = int(contagem_status.get("ONLINE", 0))
    maquinas_nao_comunicando = int(contagem_status.get("OFFLINE", 0))
    maquinas_comunicacao_desconhecida = int(contagem_status.get("SEM DADOS", 0))

    #Indicadores de Comunicação - Valor Percentual
    perce_comu = func_formatacao_percentual(maquinas_comunicando, tamanho_frota)
    perce_nao_comu = func_formatacao_percentual(maquinas_nao_comunicando+maquinas_comunicacao_desconhecida, tamanho_frota)


    #Tabelas para Detalhamento (MÁQUINAS COMUNICANDO E MÁQUINAS NÃO COMUNICANDO)
    
    df_maquinas_online = func_formatacao_data(
        comunicacao_frota.loc[comunicacao_frota["status_comunicacao"] == "ONLINE"],
        coluna="data_comunicacao",
        formato_entrada="%d-%m-%Y",
        ascending=False,
    )

    df_maquinas_offline = func_formatacao_data(
        comunicacao_frota.loc[
            comunicacao_frota["status_comunicacao"].isin(["OFFLINE", "SEM DADOS"])
        ].copy(),
        coluna="data_comunicacao",
        formato_entrada="%d-%m-%Y",
        ascending=False,
    )


    # ======================================================================#
    # ETAPA 3 - MÉTRICAS DE UTILIZAÇÃO E CONSUMO DA FROTA
    # ======================================================================#

    print("# == CALCULANDO INDICADORES DE UTILIZAÇÃO")

    #Indicadores de Utilização da Frota (Período Completo)

    #Filtrando apenas registros com dados 
    utilizacao_mensal_frota_com_dados = utilizacao_mensal_frota.loc[
        ~utilizacao_mensal_frota["work_hours"].astype(str).str.strip().isin(["SEM DADOS", "nan", "None", ""])
    ].copy()

    utilizacao_mensal_frota_com_dados = func_formatacao_tipo_numerico(
        utilizacao_mensal_frota_com_dados,
        ["work_hours", "idle_hours", "fuel_consumed", "fuel_rate", "fuel_rate_reference"],
        decimal=".",
    )

    #Total de Horas em Operação
    horas_trabalhadas = round(utilizacao_mensal_frota_com_dados["work_hours"].sum(), 2)
    horas_ociosas = round(utilizacao_mensal_frota_com_dados["idle_hours"].sum(), 2)
    total_horas = round(horas_trabalhadas + horas_ociosas, 2)

    #Percentual de Utilização
    perce_trabalhadas = func_formatacao_percentual(horas_trabalhadas, total_horas)
    perce_ociosas = func_formatacao_percentual(horas_ociosas, total_horas)

    #Eficiência Operacional
    eficiencia = func_formatacao_percentual(horas_trabalhadas, total_horas)

    # Taxa Média de Consumo por Equipamento - Em Litros/Hora
    media_consumo_modelo = (
        utilizacao_mensal_frota_com_dados.groupby("pin")[["fuel_rate", "fuel_rate_reference"]]
        .mean()
        .assign(
            fuel_rate_difference=lambda df: df["fuel_rate"] - df["fuel_rate_reference"],
            fuel_use=lambda df: pd.cut(
                df["fuel_rate_difference"],
                bins=[-float("inf"), -2, 0.2, float("inf")],
                labels=["LOW_CONSUMPTION", "NORMAL_CONSUMPTION", "HIGH_CONSUMPTION"],
                right=True,
            ),
        )
        .sort_values(by="fuel_rate_difference")
        .reset_index()
    )   

    # Total de Combustível Consumido por Equipamento
    combustivel_consumido = utilizacao_mensal_frota_com_dados.groupby("pin")["fuel_consumed"].sum().sum()

    #Máquinas com dados de Consumo
    maquinas_com_dados_de_consumo = media_consumo_modelo["pin"].shape[0]

    #Total de Máquinas com Consumo Adequado
    fuel_rate_ok = media_consumo_modelo.loc[media_consumo_modelo["fuel_use"].isin(["NORMAL_CONSUMPTION", "LOW_CONSUMPTION"])].shape[0]

    #Total de Máquinas com Consumo Acima
    fuel_rate_high = maquinas_com_dados_de_consumo - fuel_rate_ok

    #Percentual de Máquinas com Consumo Normal e Acima na Frota
    perce_consumo_alto = func_formatacao_percentual(fuel_rate_high, maquinas_com_dados_de_consumo)
    perce_consumo_normal = func_formatacao_percentual(fuel_rate_ok, maquinas_com_dados_de_consumo)

    #Formatação de Tabela para Consumo

    colunas_base_resumo = [
        "pin",
        "data_final",
        "work_hours",
        "idle_hours",
        "fuel_consumed",
        "model_clean",
        "fuel_rate_reference",
        "isg_type_name",
    ]

    df_equipamentos = utilizacao_diario_frota[colunas_base_resumo].copy()


    df_equipamentos["equipamento"] = df_equipamentos["isg_type_name"].map({v: k for k, v in MAP_TIPOS_PT_EN.items()})
    df_equipamentos = df_equipamentos.dropna(subset=["equipamento"])
    df_equipamentos = func_formatacao_tipo_numerico(
        df_equipamentos,
        ["work_hours", "idle_hours", "fuel_consumed", "fuel_rate_reference"],
        decimal=".",
    )

    #Formatação de Tabela para Consumo por Família - Em Litros por Hora

    df_consumo_familia = (
        df_equipamentos.groupby("equipamento", as_index=False)
        .agg(
            combustivel=("fuel_consumed", "sum"),
            work_hours=("work_hours", "sum"),
            idle_hours=("idle_hours", "sum"),
            fuel_rate_reference=("fuel_rate_reference", "first"),
        )
    )

    df_consumo_familia = func_formatacao_tipo_numerico(
        df_consumo_familia,
        ["combustivel", "work_hours", "idle_hours", "fuel_rate_reference"],
        decimal=".",
    )

    df_consumo_familia["horas_totais"] = df_consumo_familia["work_hours"] + df_consumo_familia["idle_hours"]

    df_consumo_familia["fuel_rate"] = df_consumo_familia["combustivel"].div(
        df_consumo_familia["horas_totais"].replace(0, pd.NA)
    )
    df_consumo_familia["fuel_rate"] = pd.to_numeric(
        df_consumo_familia["fuel_rate"], errors="coerce"
    ).round(2)

    consumos = df_consumo_familia.set_index("equipamento")["fuel_rate"].to_dict() if not df_consumo_familia.empty else {}


    consumo_retro = consumos.get("Retroescavadeira", 0)
    consumo_esca = consumos.get("Escavadeira", 0)
    consumo_moto = consumos.get("Motoniveladora", 0)
    consumo_trator = consumos.get("Trator de Esteiras", 0)
    consumo_carreg = consumos.get("Carregadeira", 0)

    # Detalhamento da Perfomance por Modelo de Equipamento

    colunas_resumo_detalhado = [
        "isg_type_name",
        "model_clean",
        "pin",
        "work_hours",
        "idle_hours",
        "fuel_consumed",
        "fuel_rate_reference",
    ]

    colunas_numericas = [
        "work_hours",
        "idle_hours",
        "fuel_consumed",
        "fuel_rate_reference",
    ]

    df_performance = utilizacao_mensal_frota[colunas_resumo_detalhado].copy()

    df_performance = func_formatacao_tipo_numerico(
        df_performance,
        colunas_numericas,
        decimal=".",
    )

    df_resumo = (
        df_performance
        .groupby(["isg_type_name", "model_clean", "pin"], as_index=False)
        .agg(
            combustivel_consumido=("fuel_consumed", "sum"),
            horas_trabalhadas=("work_hours", "sum"),
            horas_ociosas=("idle_hours", "sum"),
            referencia_consumo=("fuel_rate_reference", "first"),
        )
    )

    colunas_resumo_numericas = [
        "combustivel_consumido",
        "horas_trabalhadas",
        "horas_ociosas",
        "referencia_consumo",
    ]

    df_resumo = func_formatacao_tipo_numerico(
        df_resumo,
        colunas_resumo_numericas,
        decimal=".",
    )

    df_resumo["horas_totais"] = df_resumo["horas_trabalhadas"] + df_resumo["horas_ociosas"]
    horas_validas = df_resumo["horas_totais"].replace(0, pd.NA)

    df_resumo["eficiencia"] = df_resumo["horas_trabalhadas"].div(horas_validas)
    df_resumo["ociosidade"] = 1 - df_resumo["eficiencia"]
    df_resumo["taxa_consumo"] = df_resumo["combustivel_consumido"].div(horas_validas)
    df_resumo["diferenca"] = df_resumo["taxa_consumo"] - df_resumo["referencia_consumo"]
    df_resumo["limite_superior"] = df_resumo["referencia_consumo"] * 1.20
    df_resumo["dif_limite"] = df_resumo["taxa_consumo"] - df_resumo["limite_superior"]

    df_resumo = func_formatacao_tipo_numerico(
        df_resumo,
        [
            "eficiencia",
            "ociosidade",
            "taxa_consumo",
            "diferenca",
            "limite_superior",
            "dif_limite",
        ],
        decimal=".",
    )

    df_resumo["eficiencia_pct"] = df_resumo["eficiencia"].mul(100).round(2)
    df_resumo["ociosidade_pct"] = df_resumo["ociosidade"].mul(100).round(2)
    df_resumo["taxa_consumo"] = df_resumo["taxa_consumo"].round(2)
    df_resumo["diferenca"] = df_resumo["diferenca"].round(2)
    df_resumo["limite_superior"] = df_resumo["limite_superior"].round(2)
    df_resumo["dif_limite"] = df_resumo["dif_limite"].round(2)

    dfs_tipo = {
        chave: (
            df_resumo.loc[df_resumo["isg_type_name"] == valor]
            .sort_values(by="horas_trabalhadas", ascending=True, ignore_index=True)
            .copy()
        )
        for chave, valor in MAP_FILTROS_ISG.items()
    }

    tabelas_tipo = {
        chave: func_output_tabela(df_tipo)
        for chave, df_tipo in dfs_tipo.items()
    }

    df_resumo_retro = dfs_tipo.get("retro", pd.DataFrame())
    df_resumo_trator = dfs_tipo.get("trator", pd.DataFrame())
    df_resumo_moto = dfs_tipo.get("moto", pd.DataFrame())
    df_resumo_carrega = dfs_tipo.get("carreg", pd.DataFrame())
    df_resumo_escava = dfs_tipo.get("esc", pd.DataFrame())

    df_resumo_retro_tbl = tabelas_tipo.get("retro", pd.DataFrame())
    df_resumo_trator_tbl = tabelas_tipo.get("trator", pd.DataFrame())
    df_resumo_moto_tbl = tabelas_tipo.get("moto", pd.DataFrame())
    df_resumo_carrega_tbl = tabelas_tipo.get("carreg", pd.DataFrame())
    df_resumo_escava_tbl = tabelas_tipo.get("esc", pd.DataFrame())

    #Métricas de Envelhecimento da Frota
    
    idade_media = round(cliente_horimetros["horimetro"].median(), 2) if not cliente_horimetros.empty else 0
    maior_horimetro = cliente_horimetros["horimetro"].max() if not cliente_horimetros.empty else 0
    menor_horimetro = cliente_horimetros["horimetro"].min() if not cliente_horimetros.empty else 0

    # ======================================================================#
    # ETAPA 4 - MÉTRICA DE ALERTAS - GERAL DA FROTA
    # ======================================================================#

    print("# == CALCULANDO MÉTRICAS DE ALERTAS")


    alertas_frota["type_name"] = alertas_frota["type_name"].map(MAP_MODELOS_ALERTA).fillna(alertas_frota["type_name"])
    alertas_frota["severity"] = alertas_frota["severity"].map(MAP_SEVERITY).fillna(alertas_frota["severity"])

    # Contagem de de Alertas por Criticidade
    contagem_alertas_criticidade = (
    alertas_frota["severity"]
    .value_counts().reindex(["Alertas Informativos", "Alertas de Atencao", "Alertas Criticos"])
    .fillna(0).astype(int).reset_index())

    contagem_alertas_criticidade.columns = ["severity", "quantidade"]
    soma_alertas_total = contagem_alertas_criticidade['quantidade'].sum()

    # Calculando Percentual de Alertas por Criticidade
    contagem_alertas_criticidade["percentual"] = (contagem_alertas_criticidade["quantidade"] / soma_alertas_total * 100).fillna(0).round(2)

    #Total de Alertas Por Nível de Criticidade

    sum_alertas_info = (
    contagem_alertas_criticidade.loc[
        contagem_alertas_criticidade["severity"] == "Alertas Informativos",
        "quantidade"
    ]
    .sum())

    sum_alertas_medium = (
    contagem_alertas_criticidade.loc[
        contagem_alertas_criticidade["severity"] == "Alertas de Atencao",
        "quantidade"
    ]
    .sum())

    sum_alertas_criticos = (
    contagem_alertas_criticidade.loc[
        contagem_alertas_criticidade["severity"] == "Alertas Criticos",
        "quantidade"
    ]
    .sum())

    sum_alertas_desconhecido = (
    contagem_alertas_criticidade.loc[
        contagem_alertas_criticidade["severity"] == "Alertas Não Identificados",
        "quantidade"
    ]
    .sum())

    #Percentual de Alertas Por Nível de Criticidade
   
    per_alertas_info = (
    contagem_alertas_criticidade.loc[
        contagem_alertas_criticidade["severity"] == "Alertas Informativos",
        "percentual"
    ]
    .sum())

    per_alertas_medium = (
    contagem_alertas_criticidade.loc[
        contagem_alertas_criticidade["severity"] == "Alertas de Atencao",
        "percentual"
    ]
    .sum())

    per_alertas_critico = (
    contagem_alertas_criticidade.loc[
        contagem_alertas_criticidade["severity"] == "Alertas Criticos",
        "percentual"
    ]
    .sum())

    per_alertas_desconhecido = (
    contagem_alertas_criticidade.loc[
        contagem_alertas_criticidade["severity"] == "Alertas Não Identificados",
        "percentual"
    ]
    .sum())

    # ======================================================================#
    # ETAPA 5 - MÉTRICA DE ALERTAS - DETALHADO POR DIA
    # ======================================================================#
    
    alertas_por_dia = (
    alertas_frota
    .groupby(["alert_data", "severity"])
    .size()
    .unstack(fill_value=0)
    .pipe(func_validacao_alertas)
    )
    
    colunas = [
        "Alertas Informativos",
        "Alertas de Atencao",
        "Alertas Criticos",
    ]

    alertas_por_dia = (
        alertas_por_dia
        .reset_index()
        .sort_values(by="alert_data", ascending=True, ignore_index=True)
    )

    alertas_por_dia = func_formatacao_data(
        df = alertas_por_dia,
        coluna="alert_data",
        formato_entrada="%d-%m-%Y",
        ascending=True,
    )

    # Tabela de Contagem de Alertas por Criticidade - Por Dia

    # ======================================================================#
    # ETAPA 6 - MÉTRICA DE ALERTAS - DETALHADO POR MODELO
    # ======================================================================#


    alertas_criticos = alertas_frota.loc[
            alertas_frota["severity"] == "Alertas Criticos",
            ["serial_number", "model_name", "type_name", "alert_data", "description", "severity"],
        ].copy()
    
    alertas_criticos["description"] = alertas_criticos["description"].str.split(r"[.-]", n=1).str[0]

    mapas_alertas_criticos = {
        "Retroescavadeiras": "alertas_criticos_retro",
        "Tratores de Esteiras": "alertas_criticos_trator",
        "Motoniveladora": "alertas_criticos_moto",
        "Escavadeiras": "alertas_criticos_escav",
        "Carregadeiras": "alertas_criticos_carreg",
    }
    alertas_criticos_por_tipo = {
        chave_saida: alertas_criticos.loc[alertas_criticos["type_name"] == tipo].copy()
        for tipo, chave_saida in mapas_alertas_criticos.items()
    }

    alertas_criticos_retro = alertas_criticos_por_tipo["alertas_criticos_retro"]
    alertas_criticos_trator = alertas_criticos_por_tipo["alertas_criticos_trator"]
    alertas_criticos_moto = alertas_criticos_por_tipo["alertas_criticos_moto"]
    alertas_criticos_escav = alertas_criticos_por_tipo["alertas_criticos_escav"]
    alertas_criticos_carreg = alertas_criticos_por_tipo["alertas_criticos_carreg"]


    # ======================================================================#
    # ETAPA 6 - MÉTRICA DE ALERTAS - DETALHADO POR FAMILIA
    # ======================================================================#

    alertas_por_familia = (
        alertas_frota
        .groupby(["type_name", "severity"])
        .size()
        .unstack(fill_value=0)
        .pipe(func_validacao_alertas)
    )

    colunas = [
        "Alertas Informativos",
        "Alertas de Atencao",
        "Alertas Criticos",
    ]

    alertas_por_familia["Total Alertas"] = alertas_por_familia[colunas].sum(axis=1)

    alertas_por_familia[["perc_info", "perc_aten", "perc_critico"]] = (
        alertas_por_familia[
            ["Alertas Informativos", "Alertas de Atencao", "Alertas Criticos"]
        ]
        .div(alertas_por_familia["Total Alertas"].replace(0, pd.NA), axis=0)
        .fillna(0)
        .mul(100)           
        .round(2)           
    )

    alertas_por_familia = alertas_por_familia.reset_index()

    # ======================================================================#
    # ETAPA 7 - MÉTRICA DE ALERTAS - DETALHADO POR TIPO DE ALERTA
    # ======================================================================#

    alertas_por_descricao = (
        alertas_frota
        .assign(
            description=lambda df: (
                df["description"]
                .astype(str)
                .str.split(r"[.-]", n=1)
                .str[0]
                .str.strip()
            )
        )
        .groupby(["description", "severity"])
        .size()
        .unstack(fill_value=0)
        .pipe(func_validacao_alertas)
        .reset_index()
    )

    alertas_por_descricao = (
        alertas_por_descricao[["description", "Alertas Criticos"]]
        .loc[lambda df: df["Alertas Criticos"] != 0]
        .sort_values(by="Alertas Criticos", ascending=False)
        .reset_index(drop=True)
    )

    # ======================================================================#
    # ETAPA 8 - MÉTRICAS DE ANÁLISES QUÍMICAS
    # ======================================================================#

    print("# == GERANDO CARDS DE ANÁLISES QUÍMICAS")

    amostras_periodo = quimica_frota["numero_amostra"].count()

    total_amostras_criticas = quimica_frota.loc[quimica_frota["status_amostra"] == "CRITICO", "numero_amostra"].count()
    total_amostras_atencao = quimica_frota.loc[quimica_frota["status_amostra"] == "ATENCAO", "numero_amostra"].count()
    total_amostras_anormal = quimica_frota.loc[quimica_frota["status_amostra"] == "ANORMAL", "numero_amostra"].count()
    total_amostras_normal = quimica_frota.loc[quimica_frota["status_amostra"] == "NORMAL", "numero_amostra"].count()

    perce_criticas = func_formatacao_percentual(total_amostras_criticas, amostras_periodo)
    perce_atencao = func_formatacao_percentual(total_amostras_atencao, amostras_periodo)
    perce_anormal = func_formatacao_percentual(total_amostras_anormal, amostras_periodo)
    perce_normal = func_formatacao_percentual(total_amostras_normal, amostras_periodo)

    #======================================================================#
    # ETAPA 9 - GEOLOCALIZACAO
    #======================================================================#
    
    print("# == DETERMINANDO GEOLOCALIZAÇÃO DAS MÁQUINAS")
    
    geolocalizacao = cliente_frota[["chassi", "estado", "cidade", "latitude", "longitude"]].copy()
    pa_distribuicao = geolocalizacao.groupby("estado").size().reset_index(name="chassi")

    #======================================================================#
    # ETAPA 10 - GERAÇÃO DE CURVAS
    #======================================================================#

    graficos = func_cache_lotes([
        {
            "nome": "alertas_distr",
            "func": kernel_graficos.grafico_pizza,
            "df": contagem_alertas_criticidade,
            "colunas_validacao": ["quantidade"],
            "kwargs": {
                "coluna_rotulo": "severity",
                "coluna_valor": "quantidade",
                "fmt": fmt_pizza,
                "titulo": " ",
                "caminho_imagem": PATH_ALERTAS_IMAGENS["distribuicao"],
            },
        },
        {
            "nome": "alertas_criticidade",
            "func": kernel_graficos.grafico_barras_multiplas,
            "df": contagem_alertas_criticidade,
            "colunas_validacao": ["quantidade"],
            "kwargs": {
                "coluna_categoria": "severity",
                "colunas_valores": ["quantidade"],
                "titulo": " ",
                "cores": {
                    "Alertas Informativos": {"quantidade": AZUL},
                    "Alertas de Atencao": {"quantidade": AMARELO_ALERTA},
                    "Alertas Criticos": {"quantidade": VERMELHO},
                },
                "nome_eixo_x": " ",
                "nome_eixo_y": " ",
                "caminho_imagem": PATH_ALERTAS_IMAGENS["criticidade"],
                "fmt": fmt_barras_mult,
            },
        },
        {
            "nome": "alertas_criticidade_maquina",
            "func": kernel_graficos.grafico_barras_empilhadas_percentual,
            "df": alertas_por_familia,
            "colunas_validacao": ["Alertas Criticos", "Alertas Informativos", "Alertas de Atencao"],
            "kwargs": {
                "coluna_categoria": "type_name",
                "colunas_valores": ["Alertas Criticos", "Alertas Informativos", "Alertas de Atencao"],
                "titulo": " ",
                "orientacao": "v",
                "caminho_imagem": PATH_ALERTAS_IMAGENS["criticidade_maquina"],
                "fmt": fmt_empilhadas,
            },
        },
        {
            "nome": "alertas_criticidade_temporal",
            "func": kernel_graficos.grafico_barras_verticais,
            "df": alertas_por_dia,
            "colunas_validacao": ["Total Alertas"],
            "kwargs": {
                "coluna_categoria": "alert_data",
                "coluna_valor": "Total Alertas",
                "titulo": " ",
                "caminho_imagem": PATH_ALERTAS_IMAGENS["criticidade_temporal"],
                "fmt": fmt_vertical,
                "cores": AMARELO_JOHN_DEERE,
                "nome_eixo_x": " ",
                "nome_eixo_y": " ",
            },
        },
        {
            "nome": "alertas_info_temporal",
            "func": kernel_graficos.grafico_barras_verticais,
            "df": alertas_por_dia,
            "colunas_validacao": ["Alertas Informativos"],
            "kwargs": {
                "coluna_categoria": "alert_data",
                "coluna_valor": "Alertas Informativos",
                "titulo": " ",
                "caminho_imagem": PATH_ALERTAS_IMAGENS["info_temporal"],
                "fmt": fmt_vertical,
                "cores": AZUL,
                "nome_eixo_x": " ",
                "nome_eixo_y": " ",
            },
        },
        {
            "nome": "alertas_medium_temporal",
            "func": kernel_graficos.grafico_barras_verticais,
            "df": alertas_por_dia,
            "colunas_validacao": ["Alertas de Atencao"],
            "kwargs": {
                "coluna_categoria": "alert_data",
                "coluna_valor": "Alertas de Atencao",
                "titulo": " ",
                "caminho_imagem": PATH_ALERTAS_IMAGENS["atencao_temporal"],
                "fmt": fmt_vertical,
                "cores": AMARELO_ALERTA,
                "nome_eixo_x": " ",
                "nome_eixo_y": " ",
            },
        },
        {
            "nome": "alertas_high_temporal",
            "func": kernel_graficos.grafico_barras_verticais,
            "df": alertas_por_dia,
            "colunas_validacao": ["Alertas Criticos"],
            "kwargs": {
                "coluna_categoria": "alert_data",
                "coluna_valor": "Alertas Criticos",
                "titulo": " ",
                "caminho_imagem": PATH_ALERTAS_IMAGENS["critico_temporal"],
                "fmt": fmt_vertical,
                "cores": VERMELHO,
                "nome_eixo_x": " ",
                "nome_eixo_y": " ",
            },
        },
        {
            "nome": "alertas_high_descritivo",
            "func": kernel_graficos.grafico_barras_verticais,
            "df": alertas_por_descricao.head(10),
            "colunas_validacao": ["Alertas Criticos"],
            "kwargs": {
                "coluna_categoria": "description",
                "coluna_valor": "Alertas Criticos",
                "titulo": " ",
                "caminho_imagem": PATH_ALERTAS_IMAGENS["critico_descritivo"],
                "fmt": fmt_vertical_longa,
                "cores": VERMELHO,
                "nome_eixo_x": " ",
                "nome_eixo_y": " ",
            },
        },
    ])

    specs_performance = []
    familias_performance = [
        ("retro", df_resumo_retro, PATH_PERFORMANCE_IMAGENS["retro_1"], PATH_PERFORMANCE_IMAGENS["retro_2"]),
        ("trator", df_resumo_trator, PATH_PERFORMANCE_IMAGENS["trator_1"], PATH_PERFORMANCE_IMAGENS["trator_2"]),
        ("escava", df_resumo_escava, PATH_PERFORMANCE_IMAGENS["escava_1"], PATH_PERFORMANCE_IMAGENS["escava_2"]),
        ("moto", df_resumo_moto, PATH_PERFORMANCE_IMAGENS["moto_1"], PATH_PERFORMANCE_IMAGENS["moto_2"]),
        ("carreg", df_resumo_carrega, PATH_PERFORMANCE_IMAGENS["carreg_1"], PATH_PERFORMANCE_IMAGENS["carreg_2"]),
    ]
    for nome_familia, df_familia, arquivo_ociosidade, arquivo_consumo in familias_performance:
        base_df = df_familia.head(10)
        specs_performance.extend([
            {
                "nome": f"{nome_familia}_1",
                "func": kernel_graficos.grafico_barras_horizontais,
                "df": base_df,
                "colunas_validacao": ["ociosidade_pct"],
                "kwargs": {
                    "coluna_categoria": "pin",
                    "coluna_valor": "ociosidade_pct",
                    "titulo": " ",
                    "nome_eixo_x": " ",
                    "nome_eixo_y": " ",
                    "caminho_imagem": arquivo_ociosidade,
                    "fmt": fmt_barras,
                },
            },
            {
                "nome": f"{nome_familia}_2",
                "func": kernel_graficos.grafico_barras_horizontais,
                "df": base_df,
                "colunas_validacao": ["taxa_consumo"],
                "kwargs": {
                    "coluna_categoria": "pin",
                    "coluna_valor": "taxa_consumo",
                    "titulo": " ",
                    "nome_eixo_x": " ",
                    "nome_eixo_y": " ",
                    "caminho_imagem": arquivo_consumo,
                    "fmt": fmt_barras,
                },
            },
        ])
    
    graficos.update(func_cache_lotes(specs_performance))

    alertas_distr = graficos["alertas_distr"]
    alertas_criticidade = graficos["alertas_criticidade"]
    alertas_criticidade_maquina = graficos["alertas_criticidade_maquina"]
    alertas_criticidade_temporal = graficos["alertas_criticidade_temporal"]
    alertas_info_temporal = graficos["alertas_info_temporal"]
    alertas_medium_temporal = graficos["alertas_medium_temporal"]
    alertas_high_temporal = graficos["alertas_high_temporal"]
    alertas_high_descritivo = graficos["alertas_high_descritivo"]

    retro_1 = graficos["retro_1"]
    retro_2 = graficos["retro_2"]
    trator_1 = graficos["trator_1"]
    trator_2 = graficos["trator_2"]
    escava_1 = graficos["escava_1"]
    escava_2 = graficos["escava_2"]
    moto_1 = graficos["moto_1"]
    moto_2 = graficos["moto_2"]
    carreg_1 = graficos["carreg_1"]
    carreg_2 = graficos["carreg_2"]

   # ------------------------------------------------------------------------
    # ETAPA 9 - PDF AUXILIAR A3 DE PERFORMANCE
    # ------------------------------------------------------------------------

    print("# == GERANDO PDF DE PERFOMANCE")

    arquivo_a3_desempenho = ARQUIVO_A3_DESEMPENHO

    secoes_a3_desempenho = [
        {
            "bg_tabela": "labels/7_1_pag.png",
            "bg_graficos": "labels/7_2_pag.png",
            "df_tabela": df_resumo_retro_tbl,
            "figura_1": retro_1,
            "figura_2": retro_2,
        },
        {
            "bg_tabela": "labels/7_3_pag.png",
            "bg_graficos": "labels/7_4_pag.png",
            "df_tabela": df_resumo_escava_tbl,
            "figura_1": escava_1,
            "figura_2": escava_2,
        },
        {
            "bg_tabela": "labels/7_5_pag.png",
            "bg_graficos": "labels/7_6_pag.png",
            "df_tabela": df_resumo_trator_tbl,
            "figura_1": trator_1,
            "figura_2": trator_2,
        },
        {
            "bg_tabela": "labels/7_7_pag.png",
            "bg_graficos": "labels/7_8_pag.png",
            "df_tabela": df_resumo_moto_tbl,
            "figura_1": moto_1,
            "figura_2": moto_2,
        },
        {
            "bg_tabela": "labels/7_9_pag.png",
            "bg_graficos": "labels/7_10_pag.png",
            "df_tabela": df_resumo_carrega_tbl,
            "figura_1": carreg_1,
            "figura_2": carreg_2,
        },
    ]
    salvar_pdf_a3_desempenho(arquivo_a3_desempenho, secoes_a3_desempenho, fmt_tabela_3)

    # ------------------------------------------------------------------------
    # ETAPA 10 - PDF AUXILIAR A3 DE ALERTAS
    # Monta primeiro as paginas de graficos e depois as paginas com tabelas
    # de alertas criticos por familia de equipamento.
    # ------------------------------------------------------------------------

    print("# == GERANDO PDF DE ALERTAS")

    secoes_a3_alertas = Relatorio(
        nome_arquivo=ARQUIVO_A3_ALERTAS,
        formato_pagina=landscape(A3),
        margins=(1 * cm, 1 * cm, 1 * cm, 1 * cm),
    )

    secoes_graficos_alerta = [
        {
            "bg": PATH_PAGINAS_ALERTAS["grafico_1"],
            "figuras": [
                {"fig": alertas_distr, "width_cm": 29, "height_cm": 15},
                {"fig": alertas_criticidade, "width_cm": 29, "height_cm": 11},
            ],
        },
        {
            "bg": PATH_PAGINAS_ALERTAS["grafico_2"],
            "figuras": [
                {"fig": alertas_criticidade_maquina, "width_cm": 29, "height_cm": 15},
                {"fig": alertas_criticidade_temporal, "width_cm": 29, "height_cm": 11},
            ],
        },
        {
            "bg": PATH_PAGINAS_ALERTAS["grafico_3"],
            "figuras": [
                {"fig": alertas_info_temporal, "width_cm": 29, "height_cm": 15},
                {"fig": alertas_medium_temporal, "width_cm": 29, "height_cm": 11},
            ],
        },
        {
            "bg": PATH_PAGINAS_ALERTAS["grafico_4"],
            "figuras": [
                {"fig": alertas_high_temporal, "width_cm": 29, "height_cm": 15},
                {"fig": alertas_high_descritivo, "width_cm": 29, "height_cm": 11},
            ],
        },
    ]
    func_adicionar_paginas_graficos(secoes_a3_alertas, secoes_graficos_alerta, espaco_inicial_cm=1.3)
    secoes_a3_alertas.new_page()

    secoes_alertas = [
        {"df": alertas_criticos_retro, "bg": PATH_PAGINAS_ALERTAS["tabelas_criticas"]},
        {"df": alertas_criticos_trator, "bg": PATH_PAGINAS_ALERTAS["tabelas_criticas"]},
        {"df": alertas_criticos_moto, "bg": PATH_PAGINAS_ALERTAS["tabelas_criticas"]},
        {"df": alertas_criticos_escav, "bg": PATH_PAGINAS_ALERTAS["tabelas_criticas"]},
        {"df": alertas_criticos_carreg, "bg": PATH_PAGINAS_ALERTAS["tabelas_criticas"]},
    ]
    func_output_pag_alertas(secoes_a3_alertas, secoes_alertas, fmt_tabela_4)
    secoes_a3_alertas.save()

    # ------------------------------------------------------------------------
    # ETAPA 11 - PDFs EXTERNOS POR SECAO E COMPILADO FINAL
    # ------------------------------------------------------------------------
    print(f'GERANDO RELATORIO USUARIO {nome_cliente}')

    arquivo_principal = f"relatorio_{cliente_id}_{info_datas['data_inicial_formatada']}_{info_datas['data_final_formatada']}.pdf"
    if output_dir:
        arquivo_principal = str(Path(output_dir) / arquivo_principal)


    #======================================================================#
    # ETAPA 12 - RELATÓRIOS
    #======================================================================#

    cliente_garantia = func_formatacao_data(
        df = cliente_garantia,
        coluna="data_vencimento_garantia_basica",
        formato_entrada="%d-%m-%Y",
        ascending=False,
    )
    cliente_garantia = func_formatacao_data(
        df = cliente_garantia,
        coluna="data_vencimento_garantia_estendida",
        formato_entrada="%d-%m-%Y",
        ascending=False,
    )

    total_maquinas_garantia = len(cliente_garantia['pin'])
    total_vigente_basica = len(cliente_garantia[cliente_garantia['status_garantia_basica'] == 'VIGENTE'])
    total_avencer_basica = len(cliente_garantia[cliente_garantia['status_garantia_basica'] == 'A VENCER'])
    total_vencida_basica = len(cliente_garantia[cliente_garantia['status_garantia_basica'] == 'VENCIDO'])
    total_vigente_estendida = len(cliente_garantia[cliente_garantia['status_garantia_estendida'] == 'VIGENTE'])
    total_avencer_estendida = len(cliente_garantia[cliente_garantia['status_garantia_estendida'] == 'A VENCER'])
    total_vencida_estendida = len(cliente_garantia[cliente_garantia['status_garantia_estendida'] == 'VENCIDO'])
    total_sem_estendida = len(cliente_garantia[cliente_garantia['status_garantia_estendida'] == 'SEM GARANTIA ESTENDIDA'])
    
    # --------------------------------------------------------------------
    # SECAO 01 - CAPA
    # --------------------------------------------------------------------
    print('CARREGAMENTO: SECAO CAPA')

    pdf_capa = func_criar_pdf_a4(ARQUIVOS_SECOES_PDF["capa"])
    pdf_capa.set_background_image("labels/1_capa.png")
    func_salvar_secao_pdf(pdf_capa)

    # --------------------------------------------------------------------
    # SECAO 02 - INTRODUCAO
    # --------------------------------------------------------------------
    print('CARREGAMENTO: SECAO INTRODUCAO')

    pdf_intro = func_criar_pdf_a4(ARQUIVOS_SECOES_PDF["introducao"])
    pdf_intro.set_background_image("labels/2_intro.png")
    pdf_intro.spacer_cm(3)
    pdf_intro.add_paragraph(text=TEX1 + "   " + nome_cliente + ".", font_size=12, leading_cm=1, align="justify")
    pdf_intro.spacer_cm(0.2)
    pdf_intro.add_paragraph(text=TEX2, font_size=12, leading_cm=1, align="justify")
    pdf_intro.spacer_cm(0.2)

    paragrafo_periodo = (
        f"O relatorio que voce esta recebendo abrange o periodo que vai de "
        f"{info_datas['data_inicial_texto']} ate {info_datas['data_final_texto']}."
    )

    pdf_intro.add_paragraph(text=TEX3 + " " + paragrafo_periodo, font_size=12, leading_cm=1, align="justify")
    pdf_intro.spacer_cm(0.2)
    pdf_intro.add_paragraph(text=TEX4, font_size=12, leading_cm=1, align="justify")
    pdf_intro.spacer_cm(0.2)
    func_salvar_secao_pdf(pdf_intro)

    # --------------------------------------------------------------------
    # SECAO 03 - INDICADORES
    # --------------------------------------------------------------------
    print('CARREGAMENTO: SECAO INDICADORES')

    pdf_indicadores = func_criar_pdf_a4(ARQUIVOS_SECOES_PDF["indicadores"])
    pdf_indicadores.set_background_image("labels/3_pag.png")
    pdf_indicadores.spacer_cm(3)
    pdf_indicadores.add_paragraph(text=" ", font_size=12, leading_cm=1, align="justify")
    pdf_indicadores.spacer_cm(0.2)

    pdf_indicadores.kpi_cards(
        titulos=["Maquinas Registradas", "Maquinas Comunicando", "Maquinas Nao Comunicando"],
        valores=[
            f"{tamanho_frota}",
            f"{maquinas_comunicando} | ({func_formatacao_numero(perce_comu)}%)",
            f"{maquinas_nao_comunicando + maquinas_comunicacao_desconhecida} | ({func_formatacao_numero(perce_nao_comu)}%)",
        ],
        rotulos=["na conta do Op. Center", "total e percentual no periodo", "total e percentual no periodo"],
        cores_valor=[PRETO_JOHN_DEERE, PRETO_JOHN_DEERE, PRETO_JOHN_DEERE],
        cores_titulo=[PRETO_JOHN_DEERE, PRETO_JOHN_DEERE, PRETO_JOHN_DEERE],
        cores_borda=[AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE],
        cores_fundo=[AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE],
        fmt=KPI_FMT,
        espacamento_cm=0.2,
        y_cm=10.4,
    )
    pdf_indicadores.kpi_cards(
        titulos=["Horas Totais", "Horas Trabalhadas", "Horas Ociosas"],
        valores=[
            func_formatacao_numero(total_horas),
            f"{func_formatacao_numero(horas_trabalhadas)} | ({func_formatacao_numero(perce_trabalhadas)}%)",
            f"{func_formatacao_numero(horas_ociosas)} | ({func_formatacao_numero(perce_ociosas)}%)",
        ],
        rotulos=["total de horas no periodo", "total e percentual no periodo", "total e percentual no periodo"],
        cores_valor=[PRETO_JOHN_DEERE, PRETO_JOHN_DEERE, PRETO_JOHN_DEERE],
        cores_titulo=[PRETO_JOHN_DEERE, PRETO_JOHN_DEERE, PRETO_JOHN_DEERE],
        cores_borda=[AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE],
        cores_fundo=[AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE],
        fmt=KPI_FMT,
        espacamento_cm=0.2,
        y_cm=16.9,
    )
    pdf_indicadores.kpi_cards(
        titulos=["Combustivel Consumido", "Frota com Consumo Normal", "Frota com Consumo Acima"],
        valores=[
            f"{func_formatacao_numero(combustivel_consumido)} L",
            f"{fuel_rate_ok} | ({func_formatacao_numero(perce_consumo_normal)}%)",
            f"{fuel_rate_high} | ({func_formatacao_numero(perce_consumo_alto)}%)",
        ],
        rotulos=["em litros", "total de maquinas no periodo", "total de maquinas no periodo"],
        cores_valor=[PRETO_JOHN_DEERE, PRETO_JOHN_DEERE, PRETO_JOHN_DEERE],
        cores_titulo=[PRETO_JOHN_DEERE, PRETO_JOHN_DEERE, PRETO_JOHN_DEERE],
        cores_borda=[AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE],
        cores_fundo=[AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE],
        fmt=KPI_FMT,
        espacamento_cm=0.2,
        y_cm=23.3,
    )
    pdf_indicadores.new_page()

    pdf_indicadores.set_background_image("labels/4_pag.png")
    pdf_indicadores.spacer_cm(3)
    pdf_indicadores.add_paragraph(text=" ", font_size=12, leading_cm=1, align="justify")
    pdf_indicadores.spacer_cm(0.2)
    pdf_indicadores.kpi_cards(
        titulos=["Total de Alertas", "Alertas de Atencao", "Alertas Criticos"],
        valores=[
            f"{sum_alertas_info + sum_alertas_medium + sum_alertas_criticos + sum_alertas_desconhecido}",
            f"{sum_alertas_medium} | ({func_formatacao_numero(per_alertas_medium)}%)",
            f"{sum_alertas_criticos} | ({func_formatacao_numero(per_alertas_critico)}%)",
        ],
        rotulos=["total de alertas medios e criticos", "total e percentual no periodo", "total e percentual no periodo"],
        cores_valor=[PRETO_JOHN_DEERE, PRETO_JOHN_DEERE, BRANCO],
        cores_titulo=[PRETO_JOHN_DEERE, PRETO_JOHN_DEERE, BRANCO],
        cores_borda=[AMARELO_JOHN_DEERE, AMARELO_ALERTA, VERMELHO],
        cores_fundo=[AMARELO_JOHN_DEERE, AMARELO_ALERTA, VERMELHO],
        cores_rotulo=[CINZA_JOHN_DEERE, CINZA_JOHN_DEERE, BRANCO],
        fmt=KPI_FMT,
        espacamento_cm=0.2,
        y_cm=10.5,
    )
    pdf_indicadores.kpi_cards(
        titulos=["Amostras de Oleo Analisadas", "Total de Amostras Normais", "Amostras Criticas"],
        valores=[
            f"{amostras_periodo}",
            f"{total_amostras_normal} | ({func_formatacao_numero(perce_normal)}%)",
            f"{total_amostras_criticas} | ({func_formatacao_numero(perce_criticas)}%)",
        ],
        rotulos=["total no periodo", "total e percentual no periodo", "total e percentual no periodo"],
        cores_valor=[PRETO_JOHN_DEERE, BRANCO, BRANCO],
        cores_titulo=[PRETO_JOHN_DEERE, BRANCO, BRANCO],
        cores_borda=[AMARELO_JOHN_DEERE, AZUL, VERMELHO],
        cores_fundo=[AMARELO_JOHN_DEERE, AZUL, VERMELHO],
        cores_rotulo=[CINZA_JOHN_DEERE, BRANCO, BRANCO],
        fmt=KPI_FMT,
        espacamento_cm=0.2,
        y_cm=13.5,
    )
    pdf_indicadores.spacer_cm(3)
    pdf_indicadores.add_paragraph(
        text=(
            f"*Dados estimados com base nos equipamentos comunicando e reportando informacoes. "
            f"Fonte: John Deere."
        ),
        font_size=12,
        leading_cm=1,
        align="justify",
    )
    func_salvar_secao_pdf(pdf_indicadores)

    # --------------------------------------------------------------------
    # SECAO 04 - COMUNICACAO DA FROTA
    # --------------------------------------------------------------------
    print('CARREGAMENTO: SECAO COMUNICACAO')

    pdf_comunicacao = func_criar_pdf_a4(ARQUIVOS_SECOES_PDF["comunicacao"])
    cond_colunas = "status_comunicacao"
    cond_valores = ["ONLINE", "OFFLINE", "SEM DADOS"]
    cond_cores = ["#C6EFCE", "#FFC7CE", CINZA_JOHN_DEERE]

    for indice, df_comunicacao in enumerate([df_maquinas_online, df_maquinas_offline]):
        func_adicionar_pagina_comunicacao(
            pdf_comunicacao,
            df=df_comunicacao,
            texto=" ",
            fmt=fmt_tabela_1,
            bg="labels/5_pag.png",
            cond_col=cond_colunas,
            cond_values=cond_valores,
            cond_colors=cond_cores,
        )
        if indice < 1:
            pdf_comunicacao.new_page()

    func_salvar_secao_pdf(pdf_comunicacao)

    # --------------------------------------------------------------------
    # SECAO 05 - GEOLOCALIZACAO
    # --------------------------------------------------------------------
    print('CARREGAMENTO: SECAO GEOLOCALIZACAO')

    pdf_geo = func_criar_pdf_a4(ARQUIVOS_SECOES_PDF["geolocalizacao"])
    pdf_geo.set_background_image("labels/6_pag.png")
    pdf_geo.spacer_cm(7)
    pdf_geo.add_paragraph(text=" ", font_size=12, leading_cm=1, align="justify")

    fmt_mapa = {
        "cor_marcador": AMARELO_JOHN_DEERE,
        "tamanho_marcador": 50,
        "tipo_marcador": "circulo",
        "zoom": 8,
        "distancia_mapa": 1.1,
        "fonte": "DejaVu Sans",
        "tamanho_fonte": 14,
        "tema": "dark",
        "alpha_marcador": 0.9,
    }
    mapa = kernel_graficos.plot_mapa(
        df=geolocalizacao,
        lat_col="latitude",
        lon_col="longitude",
        figsize=(7, 14),
        fmt=fmt_mapa,
    )
    pdf_geo.add_figure(fig=mapa, width_cm=17, height_cm=17, align="center")
    pdf_geo.new_page()

    pdf_geo.set_background_image("labels/6_pag.png")
    pdf_geo.spacer_cm(7)
    pdf_geo.add_paragraph(text=" ", font_size=12, leading_cm=1, align="justify")
    pdf_geo.add_dataframe(
        geolocalizacao[["chassi", "estado", "cidade"]],
        fmt=fmt_tabela_2,
        table_align="center",
        text_align="center",
    )
    func_salvar_secao_pdf(pdf_geo)

    # --------------------------------------------------------------------
    # SECAO 06 - UTILIZACAO DA FROTA - RESUMO A4
    # --------------------------------------------------------------------
    print('CARREGAMENTO: SECAO UTILIZACAO RESUMO')

    pdf_utilizacao = func_criar_pdf_a4(ARQUIVOS_SECOES_PDF["utilizacao_resumo"])
    pdf_utilizacao.set_background_image("labels/7_0_pag.png")
    pdf_utilizacao.spacer_cm(3)
    pdf_utilizacao.add_paragraph(text=" ", font_size=12, leading_cm=1, align="justify")
    pdf_utilizacao.spacer_cm(0.2)
    pdf_utilizacao.kpi_cards(
        titulos=["Idade Media da Frota", "Maior Horimetro da Frota", "Menor Horimetro da Frota"],
        valores=[func_formatacao_numero(idade_media), func_formatacao_numero(maior_horimetro), func_formatacao_numero(menor_horimetro)],
        rotulos=["em horas de operacao", "em horas de operacao", "em horas de operacao"],
        cores_valor=[PRETO_JOHN_DEERE, PRETO_JOHN_DEERE, PRETO_JOHN_DEERE],
        cores_titulo=[PRETO_JOHN_DEERE, PRETO_JOHN_DEERE, PRETO_JOHN_DEERE],
        cores_borda=[AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE],
        cores_fundo=[AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE, AMARELO_JOHN_DEERE],
        fmt=KPI_FMT,
        espacamento_cm=0.2,
        y_cm=11,
    )
    pdf_utilizacao.kpi_cards(
        titulos=["Retroescavadeiras", "Motoniveladoras", "Tratores de Esteiras", "Escavadeiras", "Carregadeiras"],
        valores=[
            func_formatacao_numero(consumo_retro),
            func_formatacao_numero(consumo_moto),
            func_formatacao_numero(consumo_trator),
            func_formatacao_numero(consumo_esca),
            func_formatacao_numero(consumo_carreg),
        ],
        rotulos=["media em Litros por Hora"] * 5,
        cores_valor=[PRETO_JOHN_DEERE] * 5,
        cores_titulo=[PRETO_JOHN_DEERE] * 5,
        cores_borda=[AMARELO_JOHN_DEERE] * 5,
        cores_fundo=[AMARELO_JOHN_DEERE] * 5,
        fmt=KPI_FMT,
        espacamento_cm=0.2,
        y_cm=18,
    )
    func_salvar_secao_pdf(pdf_utilizacao)

    # --------------------------------------------------------------------
    # SECAO 07 - ABERTURA DE ALERTAS A4
    # --------------------------------------------------------------------
    print('CARREGAMENTO: SECAO ALERTAS ABERTURA')

    pdf_alertas_abertura = func_criar_pdf_a4(ARQUIVOS_SECOES_PDF["alertas_abertura"])
    pdf_alertas_abertura.set_background_image("labels/8_0_pag.png")
    pdf_alertas_abertura.spacer_cm(5.5)
    pdf_alertas_abertura.add_paragraph(text=TEX10, font_size=12, leading_cm=1, align="justify")
    func_salvar_secao_pdf(pdf_alertas_abertura)

    # --------------------------------------------------------------------
    # SECAO 08 - ANALISES DE OLEO
    # --------------------------------------------------------------------
    print('CARREGAMENTO: SECAO ANALISES DE OLEO')

    arquivo_analises_oleo = (
        "labels/9_1_pag.pdf"
        if amostras_periodo > 0
        else "labels/9_2_pag.pdf"
    )

    # --------------------------------------------------------------------
    # SECAO 09 - GARANTIA
    # --------------------------------------------------------------------
    print('CARREGAMENTO: SECAO DE GARANTIA')

    arquivo_a3_garantia = ARQUIVO_A3_GARANTIA

    colunas_garantia_basica = [
        "pin",
        "status_garantia_basica",
        "dias_para_vencimento_basica",
        "data_vencimento_garantia_basica",
    ]
    colunas_garantia_estendida = [
        "pin",
        "status_garantia_estendida",
        'tipo_garantia_estendida',
        "dias_para_vencimento_estendida",
        "data_vencimento_garantia_estendida",
    ]

    df_garantia_basica = cliente_garantia[
        [coluna for coluna in colunas_garantia_basica if coluna in cliente_garantia.columns]
    ].copy()
    df_garantia_estendida = cliente_garantia[
        [coluna for coluna in colunas_garantia_estendida if coluna in cliente_garantia.columns]
    ].copy()

    secoes_a3_garantia = [
        {
            "bg_tabela": PATH_PAGINAS_GARANTIA["tabela_basica"],
            "df_tabela": df_garantia_basica,
            "fmt_tabela": fmt_tabela_5,
            "cond_col": "status_garantia_basica",
            "cond_values": gara_valores,
            "cond_colors": gara_cores,
        },
        {
            "bg_tabela": PATH_PAGINAS_GARANTIA["tabela_estendida"],
            "df_tabela": df_garantia_estendida,
            "fmt_tabela": fmt_tabela_6,
            "cond_col": "status_garantia_estendida",
            "cond_values": gara_valores,
            "cond_colors": gara_cores,
        },
    ]
    salvar_pdf_a3_garantia(arquivo_a3_garantia, secoes_a3_garantia)

    pdf_garantia = func_criar_pdf_a4(ARQUIVOS_SECOES_PDF["analise_garantia"])
    pdf_garantia.set_background_image("labels/10_0_pag.png")
    pdf_garantia.spacer_cm(5.5)
    pdf_garantia.add_paragraph(text=" ", font_size=12, leading_cm=1, align="justify")

    percentual_vigente_basica = func_formatacao_percentual(total_vigente_basica, total_maquinas_garantia)
    percentual_vigente_estendida = func_formatacao_percentual(total_vigente_estendida, total_maquinas_garantia)

    pdf_garantia.spacer_cm(0.2)
    pdf_garantia.kpi_cards(
        titulos=["Máquinas Avaliadas", "Máquinas em Garantia Básica", "Máquinas em Garantia estendida"],
        valores=[
            f"{total_maquinas_garantia}",
            f"{total_vigente_basica} | ({func_formatacao_numero(percentual_vigente_basica)}%)",
            f"{total_vigente_estendida} | ({func_formatacao_numero(percentual_vigente_estendida)}%)",
        ],
        rotulos=["total de maquinas", "total e percentual maquinas", "total e percentual maquinas"],
        cores_valor=[PRETO_JOHN_DEERE, PRETO_JOHN_DEERE, BRANCO],
        cores_titulo=[PRETO_JOHN_DEERE, PRETO_JOHN_DEERE, BRANCO],
        cores_borda=[AMARELO_JOHN_DEERE, AMARELO_ALERTA, VERMELHO],
        cores_fundo=[AMARELO_JOHN_DEERE, AMARELO_ALERTA, VERMELHO],
        cores_rotulo=[CINZA_JOHN_DEERE, CINZA_JOHN_DEERE, BRANCO],
        fmt=KPI_FMT,
        espacamento_cm=0.2,
        y_cm=10.5,
    )
    func_salvar_secao_pdf(pdf_garantia)

    # --------------------------------------------------------------------
    # SECAO 10 - ENCERRAMENTO
    # --------------------------------------------------------------------
    print('CARREGAMENTO: SECAO ENCERRAMENTO')
    arquivo_encerramento = "labels/11_pag.pdf"

    # --------------------------------------------------------------------
    # COMPILADO FINAL
    # --------------------------------------------------------------------
    print('CARREGAMENTO: COMPILANDO RELATORIO FINAL')

    secoes_compilado_final = [
        {"ordem": 1, "nome": "capa", "arquivo": ARQUIVOS_SECOES_PDF["capa"]},
        {"ordem": 2, "nome": "introducao", "arquivo": ARQUIVOS_SECOES_PDF["introducao"]},
        {"ordem": 3, "nome": "indicadores", "arquivo": ARQUIVOS_SECOES_PDF["indicadores"]},
        {"ordem": 4, "nome": "comunicacao", "arquivo": ARQUIVOS_SECOES_PDF["comunicacao"]},
        {"ordem": 5, "nome": "geolocalizacao", "arquivo": ARQUIVOS_SECOES_PDF["geolocalizacao"]},
        {"ordem": 6, "nome": "utilizacao_resumo", "arquivo": ARQUIVOS_SECOES_PDF["utilizacao_resumo"]},
        {"ordem": 7, "nome": "utilizacao_detalhada_a3", "arquivo": arquivo_a3_desempenho},
        {"ordem": 8, "nome": "alertas_abertura", "arquivo": ARQUIVOS_SECOES_PDF["alertas_abertura"]},
        {"ordem": 9, "nome": "alertas_detalhado_a3", "arquivo": ARQUIVO_A3_ALERTAS},
        {"ordem": 10, "nome": "analises_oleo", "arquivo": arquivo_analises_oleo},
        {"ordem": 11, "nome": "garantia_resumo", "arquivo": ARQUIVOS_SECOES_PDF["analise_garantia"]},
        {"ordem": 12, "nome": "garantia_detalhada_a3", "arquivo": arquivo_a3_garantia},
        {"ordem": 13, "nome": "encerramento", "arquivo": arquivo_encerramento},
    ]

    arquivos_compilado = [
        secao["arquivo"]
        for secao in sorted(secoes_compilado_final, key=lambda item: item["ordem"])
    ]

    func_compilar_pdfs(arquivo_principal, arquivos_compilado)

    artefatos_temporarios = [
        arquivo_a3_desempenho,
        ARQUIVO_A3_ALERTAS,
        arquivo_a3_garantia,
        *ARQUIVOS_SECOES_PDF.values(),
        *PATH_ALERTAS_IMAGENS.values(),
        *PATH_PERFORMANCE_IMAGENS.values(),
    ]
    func_cache_temporarios(artefatos_temporarios)
    print(f"Relatorio final gerado: {arquivo_principal}")

    return str(Path(arquivo_principal).resolve())


# --------------------------------------------------------------------
# GERAÇÃO DE RELATÓRIO - DATA MÓVEL
# --------------------------------------------------------------------

def rda_py_data_movel(
    client_id: int,
    data_inicial: str,
    data_final: str,
    output_dir: str = None,
) -> str:
    """
    Gera relatório com período customizado.

    Args:
        client_id: ID da organização no Operations Center.
        data_inicial: data inicial no formato ISO YYYY-MM-DD.
        data_final: data final no formato ISO YYYY-MM-DD.
        output_dir: diretório de saída para o PDF final. Se None, salva no cwd.

    Returns:
        str: caminho absoluto do PDF gerado.
    """
    info_datas = func_output_data_custom(data_inicial, data_final)
    return rda_py_data_fixa(
        cliente_id=client_id,
        info_datas=info_datas,
        output_dir=output_dir,
    )

# --------------------------------------------------------------------
# GERAÇÃO DE FLUXO
# --------------------------------------------------------------------

if __name__ == "__main__":

    print("""
          
          VENEZA EQUIPAMENTOS PESADOS - RDA - RELATÓRIOS DE DESEMPENHO AUTOMÁTICO - Versão 0.2.6.2 - 04/2026
          
          """)
    
    print("Defina o Fluxo de Que Deseja Executar: ")
    print("[1] - Data FIXA  - 30 Dias Antes da Execução ")
    print("[2] - Data Móvel - Consultas A Partir de 01/03/2025 ")
    print("[3] - Fluxo Fixo - Toda a Lista de Clietes Prioritários")
    print("    ")
    flow = int(input('Entre Com o Tipo de Execução: '))

    if flow == 1:

        print("Geração de Relatório Com Data Fixa em Execução:")
        id_cliente = int(input('Insira o Código do Cliente: ')) 
        rda_py_data_fixa(id_cliente)
        
    elif flow == 2:
        
        print("Geração de Relatório Com Data Móvel em Execução:")
        id_cliente = int(input('Insira o Código do Cliente: ')) 
        data_inicial = int(input('Insira a Data Inicial da Consulta: '))
        data_final = int(input('Insira a Data Final da Consulta: '))  
        rda_py_data_movel(id_cliente)

    elif flow == 3:

        print('Executando Fluxo Automático de Relatórios')
        for id_client in tqdm(valores, desc = 'Processando Relatórios'):

                try:
                    rda_py_data_fixa(id_client)
        
                except Exception as e:
                    print(f'Erro {e}')
                    artefatos_temporarios = [
                    ARQUIVO_A3_DESEMPENHO,
                    ARQUIVO_A3_ALERTAS,
                    ARQUIVO_A3_GARANTIA,
                    *ARQUIVOS_SECOES_PDF.values(),
                    *PATH_ALERTAS_IMAGENS.values(),
                    *PATH_PERFORMANCE_IMAGENS.values(),]
                    func_cache_temporarios(artefatos_temporarios)
                    sleep(10)
                    continue

    else:

        print('Valor Não Identificado - Saíndo da Aplicação')
        pass