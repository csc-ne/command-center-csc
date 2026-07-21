# =======================================================================
# VENEZA EQUIPAMENTOS SA
# CENTRO DE SOLUCOES CONECTADAS - CSC
# REPORT AUTOMATICO DE DESEMPENHO - RAD
# DESENVOLVIDO POR THIAGO BARROS - thiago.barros@venezanet.com - 2026.1
# VERSÃO ESTÁVEL - 0.2.6.4 - Data 04/06/2026 - Fluxo Contínuo Funcional
# =======================================================================
# 
# Módulo de Estatísticas
# =========================================

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm


class Estatistica:

    """
    Classe para cálculos estatísticos diversos aplicados em DataFrames.
    """

    # ----------------------------------------------------------------------
    # Estatísticas Descritivas
    # ----------------------------------------------------------------------

    def estatisticas_descritivas(df: pd.DataFrame):

        """
        Retorna estatísticas descritivas tradicionais da base.
        """
        return df.describe(include="all").T

    # ----------------------------------------------------------------------
    # Detecção de Outliers (Método do IQR)
    # ----------------------------------------------------------------------

    def detectar_outliers(df: pd.DataFrame, coluna: str):

        """
        Retorna os valores considerados outliers pelo método do IQR.
        Outlier = valor < Q1 - 1.5*IQR ou valor > Q3 + 1.5*IQR
        """
        q1 = df[coluna].quantile(0.25)
        q3 = df[coluna].quantile(0.75)
        iqr = q3 - q1

        lim_inf = q1 - 1.5 * iqr
        lim_sup = q3 + 1.5 * iqr

        return df[(df[coluna] < lim_inf) | (df[coluna] > lim_sup)]

    # ----------------------------------------------------------------------
    # Teste de Normalidade (Shapiro-Wilk)
    # ----------------------------------------------------------------------

    def teste_normalidade(df: pd.DataFrame, coluna: str):
        """
        Executa o teste de Shapiro-Wilk para verificar normalidade.
        Retorna estatística e p-valor.
        """
        serie = df[coluna].dropna()
        stat, pvalue = stats.shapiro(serie)

        return {
            "estatistica": stat,
            "pvalor": pvalue,
            "normal": pvalue > 0.05  # True se não rejeita H0 (normalidade)
        }

    # ----------------------------------------------------------------------
    # Correlação
    # ----------------------------------------------------------------------

    def correlacao(df: pd.DataFrame, metodo: str = "pearson"):
        """
        Retorna a matriz de correlação usando Pearson ou Spearman.
        """
        return df.corr(method=metodo)

    # ----------------------------------------------------------------------
    # Regressão Linear Múltipla
    # ----------------------------------------------------------------------

    def regressao_multipla(df: pd.DataFrame, y: str, X: list):

        """
        Executa regressão linear múltipla usando Statsmodels (OLS).
        - y: variável dependente (string)
        - X: lista de variáveis independentes (strings)
        
        Retorna:
            - resumo do modelo
            - coeficientes
            - pvalores
            - R²
            - modelo treinado
        """
        
        df = df.dropna(subset=[y] + X).copy()

        # Monta matrizes
        X_matrix = sm.add_constant(df[X])   # adiciona intercepto
        y_vector = df[y]

        # Ajusta modelo
        modelo = sm.OLS(y_vector, X_matrix).fit()

        return {
            "modelo": modelo,
            "resumo": modelo.summary().as_text(),
            "coeficientes": modelo.params,
            "pvalores": modelo.pvalues,
            "r2": modelo.rsquared,
            "r2_ajustado": modelo.rsquared_adj
        }
