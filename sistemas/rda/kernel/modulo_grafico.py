# =======================================================================
# VENEZA EQUIPAMENTOS SA
# CENTRO DE SOLUCOES CONECTADAS - CSC
# REPORT AUTOMATICO DE DESEMPENHO - RAD
# DESENVOLVIDO POR THIAGO BARROS - thiago.barros@venezanet.com - 2026.1
# VERSÃO ESTÁVEL - 0.2.6.4 - Data 04/06/2026 - Fluxo Contínuo Funcional
# =======================================================================
# Módulo Gráfico - Criações de Figuras e Curvas

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter
from typing import Dict, List, Optional
import geopandas as gpd
import contextily as ctx
import copy
import numpy as np
import pandas as pd
import textwrap
import os

# ---------------------------------------------------------------------------
# Contextily — cache de tiles para evitar downloads lentos em Docker
# ---------------------------------------------------------------------------
_TILE_CACHE_DIR = os.environ.get(
    "CONTEXTILY_CACHE_DIR",
    os.path.join(os.path.expanduser("~"), ".cache", "contextily"),
)
os.makedirs(_TILE_CACHE_DIR, exist_ok=True)
ctx.set_cache_dir(_TILE_CACHE_DIR)

try:
    from scipy.interpolate import make_interp_spline
except Exception:
    make_interp_spline = None

class Graficos:
    """
    Classe utilitária para geração de gráficos com Matplotlib.

    A classe foi estruturada para uso em relatórios, com foco em gerar imagens
    PNG a partir de DataFrames do pandas. Cada tipo de gráfico possui seu próprio
    método e seu próprio dicionário de formatação padrão.

    Métodos principais
    ------------------
    - grafico_barras_verticais
    - grafico_barras_horizontais
    - grafico_barras_multiplas
    - grafico_pizza
    - grafico_dispersao
    - grafico_linhas_interpoladas
    - gráfico_barras_empilhadas

    """

    def __init__(self) -> None:
        """Inicializa a classe de gráficos."""
        self.fonte_padrao = "DejaVu Sans"

    # ============================================================
    # FORMATADORES E UTILITÁRIOS
    # ============================================================

    def _merge_dict(self, base: dict, extra: Optional[dict]) -> dict:
        """
        Mescla dois dicionários recursivamente.

        Parameters
        ----------
        base : dict
            Dicionário base.
        extra : dict | None
            Dicionário com sobrescritas.

        Returns
        -------
        dict
            Novo dicionário mesclado.
        """
        resultado = copy.deepcopy(base)
        if not extra:
            return resultado

        for chave, valor in extra.items():
            if isinstance(valor, dict) and isinstance(resultado.get(chave), dict):
                resultado[chave] = self._merge_dict(resultado[chave], valor)
            else:
                resultado[chave] = valor
        return resultado

    def _formatar_numero(self, valor: float, pos=None, casas_decimais: int = 2) -> str:
        """
        Formata números no padrão brasileiro.

        Parameters
        ----------
        valor : float
            Valor a ser formatado.
        pos : Any, optional
            Parâmetro de compatibilidade com FuncFormatter.
        casas_decimais : int, default=2
            Quantidade de casas decimais.

        Returns
        -------
        str
            Valor formatado com ponto para milhar e vírgula decimal.
        """
        texto = f"{valor:,.{casas_decimais}f}"
        return texto.replace(",", "X").replace(".", ",").replace("X", ".")

    def _formatter_factory(self, casas_decimais: int):
        """Cria um formatador numérico para eixos."""
        return FuncFormatter(lambda x, pos: self._formatar_numero(x, pos, casas_decimais))

    def _resolver_lista_cores(self, cores, tamanho: int, cor_padrao: str) -> List[str]:
        """
        Normaliza entrada de cores para uma lista compatível com a plotagem.

        Parameters
        ----------
        cores : None, str ou list
            Cor única, lista de cores ou None.
        tamanho : int
            Quantidade de elementos a colorir.
        cor_padrao : str
            Cor utilizada quando `cores` não for informado.

        Returns
        -------
        list[str]
            Lista de cores com comprimento igual a `tamanho`.
        """
        if cores is None:
            return [cor_padrao] * tamanho
        if isinstance(cores, str):
            return [cores] * tamanho
        if isinstance(cores, list):
            if not cores:
                return [cor_padrao] * tamanho
            if len(cores) >= tamanho:
                return cores[:tamanho]
            repeticoes = (tamanho // len(cores)) + 1
            return (cores * repeticoes)[:tamanho]
        raise ValueError("cores deve ser None, string ou lista de strings.")

    def _configurar_figura_e_eixos(self, fig, ax, fmt: dict) -> None:
        """
        Aplica a formatação comum de figura e eixos.

        Parameters
        ----------
        fig : matplotlib.figure.Figure
            Figura criada.
        ax : matplotlib.axes.Axes
            Eixo principal da figura.
        fmt : dict
            Dicionário de formatação do método correspondente.
        """
        fig.patch.set_facecolor(fmt["figura"]["facecolor"])
        fig.patch.set_alpha(fmt["figura"]["alpha"])
        ax.set_facecolor(fmt["figura"]["facecolor"])
        ax.patch.set_alpha(fmt["figura"]["alpha"])

        plt.rcParams["font.family"] = fmt["fonte"]["family"]

        ax.title.set_color(fmt["fonte"]["color"])
        ax.xaxis.label.set_color(fmt["fonte"]["color"])
        ax.yaxis.label.set_color(fmt["fonte"]["color"])
        ax.tick_params(axis="x", labelsize=fmt["fonte"]["ticks"], colors=fmt["fonte"]["color"])
        ax.tick_params(axis="y", labelsize=fmt["fonte"]["ticks"], colors=fmt["fonte"]["color"])

        ax.spines["bottom"].set_visible(fmt["eixos"]["mostrar_linha_x"])
        ax.spines["left"].set_visible(fmt["eixos"]["mostrar_linha_y"])
        ax.spines["top"].set_visible(fmt["eixos"]["mostrar_linha_top"])
        ax.spines["right"].set_visible(fmt["eixos"]["mostrar_linha_right"])

        ax.spines["bottom"].set_linewidth(fmt["eixos"]["largura_linha_x"])
        ax.spines["left"].set_linewidth(fmt["eixos"]["largura_linha_y"])
        ax.spines["bottom"].set_color(fmt["eixos"]["cor_linha_x"])
        ax.spines["left"].set_color(fmt["eixos"]["cor_linha_y"])
        ax.spines["top"].set_color(fmt["eixos"]["cor_linha_top"])
        ax.spines["right"].set_color(fmt["eixos"]["cor_linha_right"])

    def _aplicar_grade(self, ax, fmt: dict) -> None:
        """
        Aplica as grades horizontal e vertical conforme o dicionário de formatação.

        Parameters
        ----------
        ax : matplotlib.axes.Axes
            Eixo no qual a grade será aplicada.
        fmt : dict
            Dicionário de formatação.
        """
        ax.set_axisbelow(True)
        ax.xaxis.grid(
            fmt["eixos"]["mostrar_grade_vertical"],
            color=fmt["eixos"]["cor_grade_vertical"],
            linewidth=fmt["eixos"]["largura_grade_vertical"],
            alpha=fmt["eixos"]["alpha_grade_vertical"],
            linestyle=fmt["eixos"]["estilo_grade_vertical"],
        )
        ax.yaxis.grid(
            fmt["eixos"]["mostrar_grade_horizontal"],
            color=fmt["eixos"]["cor_grade_horizontal"],
            linewidth=fmt["eixos"]["largura_grade_horizontal"],
            alpha=fmt["eixos"]["alpha_grade_horizontal"],
            linestyle=fmt["eixos"]["estilo_grade_horizontal"],
        )

    def _salvar_figura(self, fig, caminho_imagem: str, dpi: int, facecolor: str) -> str:
        """
        Salva a figura em arquivo e fecha o objeto de figura.

        Parameters
        ----------
        fig : matplotlib.figure.Figure
            Figura a ser salva.
        caminho_imagem : str
            Caminho do arquivo de saída.
        dpi : int
            Resolução da imagem.
        facecolor : str
            Cor de fundo a ser usada na exportação.

        Returns
        -------
        str
            Caminho do arquivo salvo.
        """
        fig.tight_layout()
        fig.savefig(caminho_imagem, dpi=dpi, bbox_inches="tight", facecolor=facecolor)
        plt.close(fig)
        return caminho_imagem

    def _adicionar_rotulos_barras_verticais(self, ax, barras, fmt: dict) -> None:
        """Adiciona rótulos numéricos em barras verticais."""
        if not fmt["rotulos"]["mostrar"]:
            return
        offset = fmt["rotulos"]["offset"]
        for barra in barras:
            altura = barra.get_height()
            ax.text(
                barra.get_x() + barra.get_width() / 2,
                altura + offset,
                self._formatar_numero(altura, casas_decimais=fmt["rotulos"]["casas_decimais"]),
                ha="center",
                va="bottom",
                fontsize=fmt["fonte"]["rotulo_dados"],
                color=fmt["fonte"]["color"],
            )

    def _adicionar_rotulos_barras_horizontais(self, ax, barras, fmt: dict) -> None:
        """Adiciona rótulos numéricos em barras horizontais."""
        if not fmt["rotulos"]["mostrar"]:
            return
        offset = fmt["rotulos"]["offset"]
        for barra in barras:
            largura = barra.get_width()
            ax.text(
                largura + offset,
                barra.get_y() + barra.get_height() / 2,
                self._formatar_numero(largura, casas_decimais=fmt["rotulos"]["casas_decimais"]),
                ha="left",
                va="center",
                fontsize=fmt["fonte"]["rotulo_dados"],
                color=fmt["fonte"]["color"],
            )

    def _desenhar_barra_vertical_arredondada(self, ax, x_centro: float, altura: float, largura: float, cor: str, alpha: float, raio: float):
        """
        Desenha uma barra vertical com cantos arredondados usando `FancyBboxPatch`.

        Parameters
        ----------
        ax : matplotlib.axes.Axes
            Eixo no qual a barra será desenhada.
        x_centro : float
            Posição central da barra no eixo X.
        altura : float
            Altura da barra.
        largura : float
            Largura da barra.
        cor : str
            Cor de preenchimento da barra.
        alpha : float
            Transparência aplicada à barra.
        raio : float
            Tamanho do arredondamento das quinas.

        Returns
        -------
        matplotlib.patches.FancyBboxPatch
            Patch adicionado ao eixo.
        """
        y_base = min(0.0, altura)
        altura_patch = abs(altura)
        patch = FancyBboxPatch(
            (x_centro - largura / 2, y_base),
            largura,
            altura_patch,
            boxstyle=f"round,pad=0,rounding_size={raio}",
            linewidth=0,
            facecolor=cor,
            edgecolor='none',
            alpha=alpha,
            mutation_aspect=1,
        )
        ax.add_patch(patch)
        return patch

    def _desenhar_barra_horizontal_arredondada(self, ax, y_centro: float, largura_barra: float, altura: float, cor: str, alpha: float, raio: float):
        """
        Desenha uma barra horizontal com cantos arredondados usando `FancyBboxPatch`.

        Parameters
        ----------
        ax : matplotlib.axes.Axes
            Eixo no qual a barra será desenhada.
        y_centro : float
            Posição central da barra no eixo Y.
        largura_barra : float
            Comprimento da barra no eixo X.
        altura : float
            Altura da barra.
        cor : str
            Cor de preenchimento da barra.
        alpha : float
            Transparência aplicada à barra.
        raio : float
            Tamanho do arredondamento das quinas.

        Returns
        -------
        matplotlib.patches.FancyBboxPatch
            Patch adicionado ao eixo.
        """
        x_base = min(0.0, largura_barra)
        largura_patch = abs(largura_barra)
        patch = FancyBboxPatch(
            (x_base, y_centro - altura / 2),
            largura_patch,
            altura,
            boxstyle=f"round,pad=0,rounding_size={raio}",
            linewidth=0,
            facecolor=cor,
            edgecolor='none',
            alpha=alpha,
            mutation_aspect=1,
        )
        ax.add_patch(patch)
        return patch
    
    def _finalizar_figura(self, fig, ax, titulo: str, nome_eixo_x: str = None, nome_eixo_y: str = None):
        """Aplica elementos finais padronizados ao gráfico."""
        ax.set_title(titulo, loc="left")
        if nome_eixo_x:
            ax.set_xlabel(nome_eixo_x)
        if nome_eixo_y:
            ax.set_ylabel(nome_eixo_y)
        ax.grid(True, axis="both")
        fig.tight_layout()
        return fig, ax

    # ============================================================
    # DICIONÁRIOS PADRÃO POR MÉTODO
    # ============================================================

    def fmt_barras_verticais(self) -> dict:
        """
        Retorna o dicionário padrão do gráfico de barras verticais.

        Returns
        -------
        dict
            Configuração padrão para `grafico_barras_verticais`.
        """
        return {
            "figura": {"figsize": (10, 6), "dpi": 300, "facecolor": "#FFFFFF", "alpha": 1.0},
            "barras": {"cor": "#FFBD59", "largura": 0.65, "espacamento": 0.35, "alpha": 0.92, "raio": 0.12},
            "fonte": {
                "family": self.fonte_padrao,
                "color": "#000000",
                "titulo": 14,
                "eixos": 11,
                "ticks": 10,
                "rotulo_dados": 10,
            },
            "eixos": {
                "mostrar_grade_vertical": False,
                "mostrar_grade_horizontal": True,
                "cor_grade_vertical": "#D9D9D9",
                "cor_grade_horizontal": "#D9D9D9",
                "largura_grade_vertical": 0.8,
                "largura_grade_horizontal": 0.8,
                "alpha_grade_vertical": 0.8,
                "alpha_grade_horizontal": 0.8,
                "estilo_grade_vertical": "-",
                "estilo_grade_horizontal": "-",
                "mostrar_linha_x": False,
                "mostrar_linha_y": False,
                "mostrar_linha_top": False,
                "mostrar_linha_right": False,
                "cor_linha_x": "#000000",
                "cor_linha_y": "#000000",
                "cor_linha_top": "#000000",
                "cor_linha_right": "#000000",
                "largura_linha_x": 0.8,
                "largura_linha_y": 0.8,
                "angulo_rotulo_x": 0,
            },
            "rotulos": {
                "mostrar": True,
                "casas_decimais": 2,
                "offset": 0.0,
                "quebra_automatica": True,
                "largura_quebra": 12,
            },
        }

    def fmt_barras_horizontais(self) -> dict:
        """
        Retorna o dicionário padrão do gráfico de barras horizontais.

        Returns
        -------
        dict
            Configuração padrão para `grafico_barras_horizontais`.
        """
        return {
            "figura": {"figsize": (10, 6), "dpi": 300, "facecolor": "#FFFFFF", "alpha": 1.0},
            "barras": {"cor": "#FFBD59", "largura": 0.65, "espacamento": 0.35, "alpha": 0.92, "raio": 0.12},
            "fonte": {
                "family": self.fonte_padrao,
                "color": "#000000",
                "titulo": 14,
                "eixos": 11,
                "ticks": 10,
                "rotulo_dados": 10,
            },
            "eixos": {
                "mostrar_grade_vertical": True,
                "mostrar_grade_horizontal": False,
                "cor_grade_vertical": "#D9D9D9",
                "cor_grade_horizontal": "#D9D9D9",
                "largura_grade_vertical": 0.8,
                "largura_grade_horizontal": 0.8,
                "alpha_grade_vertical": 0.8,
                "alpha_grade_horizontal": 0.8,
                "estilo_grade_vertical": "-",
                "estilo_grade_horizontal": "-",
                "mostrar_linha_x": False,
                "mostrar_linha_y": False,
                "mostrar_linha_top": False,
                "mostrar_linha_right": False,
                "cor_linha_x": "#000000",
                "cor_linha_y": "#000000",
                "cor_linha_top": "#000000",
                "cor_linha_right": "#000000",
                "largura_linha_x": 0.8,
                "largura_linha_y": 0.8,
                "angulo_rotulo_x": 0,
            },
            "rotulos": {"mostrar": False, "casas_decimais": 2, "offset": 0.0},
        }

    def fmt_barras_multiplas(self) -> dict:
        """
        Retorna o dicionário padrão do gráfico de barras múltiplas.

        Returns
        -------
        dict
            Configuração padrão para `grafico_barras_multiplas`.
        """
        return {
            "figura": {"figsize": (11, 6), "dpi": 300, "facecolor": "#FFFFFF", "alpha": 1.0},
            "barras": {"cor": "#FFBD59", "largura": 0.32, "espacamento_series": 0.04, "espacamento_grupos": 0.45, "alpha": 0.92, "raio": 0.10},
            "fonte": {
                "family": self.fonte_padrao,
                "color": "#000000",
                "titulo": 14,
                "eixos": 11,
                "ticks": 10,
                "rotulo_dados": 10,
                "legenda": 11,
            },
            "eixos": {
                "mostrar_grade_vertical": False,
                "mostrar_grade_horizontal": True,
                "cor_grade_vertical": "#D9D9D9",
                "cor_grade_horizontal": "#D9D9D9",
                "largura_grade_vertical": 0.8,
                "largura_grade_horizontal": 0.8,
                "alpha_grade_vertical": 0.8,
                "alpha_grade_horizontal": 0.8,
                "estilo_grade_vertical": "-",
                "estilo_grade_horizontal": "-",
                "mostrar_linha_x": False,
                "mostrar_linha_y": False,
                "mostrar_linha_top": False,
                "mostrar_linha_right": False,
                "cor_linha_x": "#000000",
                "cor_linha_y": "#000000",
                "cor_linha_top": "#000000",
                "cor_linha_right": "#000000",
                "largura_linha_x": 0.8,
                "largura_linha_y": 0.8,
                "angulo_rotulo_x": 0,
            },
            "rotulos": {"mostrar": False, "casas_decimais": 2, "offset": 0.0},
            "legenda": {
                "mostrar": True,
                "posicao": "upper center",
                "bbox_to_anchor": (0.5, 1.08),
                "ncol": 2,
                "frameon": False,
            },
        }

    def fmt_pizza(self) -> dict:
        """
        Retorna o dicionário padrão do gráfico de pizza.

        Returns
        -------
        dict
            Configuração padrão para `grafico_pizza`.
        """
        return {
            "figura": {"figsize": (8, 8), "dpi": 300, "facecolor": "#FFFFFF", "alpha": 1.0},
            "pizza": {"cores": None, "startangle": 90, "autopct": lambda p: '{:.1f}%'.format(p).replace('.', ','), "explode": None},
            "fonte": {"family": self.fonte_padrao, "color": "#000000", "titulo": 14, "ticks": 10},
            "legenda": {
                "mostrar": False,
                "posicao": "upper center",
                "bbox_to_anchor": (0.5, 1.05),
                "ncol": 2,
                "frameon": False,
            },
        }

    def fmt_dispersao(self) -> dict:
        """
        Retorna o dicionário padrão do gráfico de dispersão.

        Returns
        -------
        dict
            Configuração padrão para `grafico_dispersao`.
        """
        return {
            "figura": {"figsize": (10, 6), "dpi": 300, "facecolor": "#FFFFFF", "alpha": 1.0},
            "dispersao": {"cor": "#FFBD59", "tamanho": 60, "alpha": 0.85},
            "fonte": {
                "family": self.fonte_padrao,
                "color": "#000000",
                "titulo": 14,
                "eixos": 11,
                "ticks": 10,
            },
            "eixos": {
                "mostrar_grade_vertical": True,
                "mostrar_grade_horizontal": True,
                "cor_grade_vertical": "#D9D9D9",
                "cor_grade_horizontal": "#D9D9D9",
                "largura_grade_vertical": 0.8,
                "largura_grade_horizontal": 0.8,
                "alpha_grade_vertical": 0.8,
                "alpha_grade_horizontal": 0.8,
                "estilo_grade_vertical": "-",
                "estilo_grade_horizontal": "-",
                "mostrar_linha_x": True,
                "mostrar_linha_y": True,
                "mostrar_linha_top": False,
                "mostrar_linha_right": False,
                "cor_linha_x": "#000000",
                "cor_linha_y": "#000000",
                "cor_linha_top": "#000000",
                "cor_linha_right": "#000000",
                "largura_linha_x": 0.8,
                "largura_linha_y": 0.8,
            },
        }

    def fmt_linhas_interpoladas(self) -> dict:
        """
        Retorna o dicionário padrão do gráfico de linhas interpoladas.

        Returns
        -------
        dict
            Configuração padrão para `grafico_linhas_interpoladas`.
        """
        return {
            "figura": {"figsize": (12, 5), "dpi": 300, "facecolor": "#FFFFFF", "alpha": 1.0},
            "linhas": {"cor": "#41535D", "largura": 2.2, "alpha": 0.95, "suavizar": True, "mostrar_pontos": True, "tamanho_pontos": 28},
            "fonte": {
                "family": self.fonte_padrao,
                "color": "#000000",
                "titulo": 14,
                "eixos": 11,
                "ticks": 10,
            },
            "eixos": {
                "mostrar_grade_vertical": False,
                "mostrar_grade_horizontal": True,
                "cor_grade_vertical": "#D9D9D9",
                "cor_grade_horizontal": "#D9D9D9",
                "largura_grade_vertical": 0.8,
                "largura_grade_horizontal": 0.8,
                "alpha_grade_vertical": 0.8,
                "alpha_grade_horizontal": 0.8,
                "estilo_grade_vertical": "-",
                "estilo_grade_horizontal": "-",
                "mostrar_linha_x": False,
                "mostrar_linha_y": True,
                "mostrar_linha_top": False,
                "mostrar_linha_right": False,
                "cor_linha_x": "#000000",
                "cor_linha_y": "#000000",
                "cor_linha_top": "#000000",
                "cor_linha_right": "#000000",
                "largura_linha_x": 0.8,
                "largura_linha_y": 0.8,
                "angulo_rotulo_x": 30,
            },
        }

    def fmt_barras_empilhadas_percentual(self) -> dict:
        """
        Retorna o dicionário padrão do gráfico de barras empilhadas percentual.

        Returns
        -------
        dict
            Configuração padrão para `grafico_barras_empilhadas_percentual`.
        """
        return {
            "figura": {
                "figsize": (10, 6),
                "dpi": 300,
                "facecolor": "#FFFFFF",
                "alpha": 1.0,
            },
            "barras": {
                "cor": "#FFBD59",
                "largura": 0.65,
                "espacamento": 0.35,
                "alpha": 0.92,
                "raio": 0.12,
                "cores_por_categoria": {
                    # Exemplo:
                    # "trabalho": "#4CAF50",
                    # "ociosidade": "#FF6B6B",
                    # "manutencao": "#FFC107",
                    # "parada": "#607D8B",
                },
                "ordem_categorias": None,
            },
            "fonte": {
                "family": self.fonte_padrao,
                "color": "#000000",
                "titulo": 14,
                "eixos": 11,
                "ticks": 10,
                "rotulo_dados": 10,
            },
            "eixos": {
                "mostrar_grade_vertical": True,
                "mostrar_grade_horizontal": False,
                "cor_grade_vertical": "#D9D9D9",
                "cor_grade_horizontal": "#D9D9D9",
                "largura_grade_vertical": 0.8,
                "largura_grade_horizontal": 0.8,
                "alpha_grade_vertical": 0.8,
                "alpha_grade_horizontal": 0.8,
                "estilo_grade_vertical": "-",
                "estilo_grade_horizontal": "-",
                "mostrar_linha_x": False,
                "mostrar_linha_y": False,
                "mostrar_linha_top": False,
                "mostrar_linha_right": False,
                "cor_linha_x": "#000000",
                "cor_linha_y": "#000000",
                "cor_linha_top": "#000000",
                "cor_linha_right": "#000000",
                "largura_linha_x": 0.8,
                "largura_linha_y": 0.8,
                "angulo_rotulo_x": 0,
                "limite_percentual": 100,
                "mostrar_ticks_percentual": True,
            },
            "rotulos": {
                "mostrar": False,
                "casas_decimais": 2,
                "offset": 0.0,
                "mostrar_percentual": True,
                "min_percentual_exibir": 3,
                "cor_texto_interno": "#FFFFFF",
                "cor_texto_externo": "#000000",
            },
            "legenda": {
                "mostrar": True,
                "posicao": "upper center",
                "bbox_to_anchor": (0.5, 1.15),
                "ncol": 4,
                "frameon": False,
            },
            "empilhado": {
                "normalizar": True,
                "limite_categorias": 4,
                "ordenar_por_total": False,
            },
        }

    # ============================================================
    # MÉTODOS PRINCIPAIS
    # ============================================================

    def grafico_barras_verticais(
        self,
        df: pd.DataFrame,
        coluna_categoria: str,
        coluna_valor: str,
        titulo: str,
        nome_eixo_x: Optional[str] = None,
        nome_eixo_y: Optional[str] = None,
        cores=None,
        fmt: Optional[dict] = None,
        caminho_imagem: str = "grafico_barras_verticais.png",
    ) -> str:
        """
        Gera um gráfico de barras verticais e salva a imagem em arquivo.

        Parameters
        ----------
        df : pandas.DataFrame
            Base de dados de entrada.
        coluna_categoria : str
            Coluna categórica utilizada no eixo X.
        coluna_valor : str
            Coluna numérica utilizada no eixo Y.
        titulo : str
            Título do gráfico.
        nome_eixo_x : str, optional
            Nome exibido no eixo X.
        nome_eixo_y : str, optional
            Nome exibido no eixo Y.
        cores : None, str ou list, optional
            Cor única ou lista de cores para as barras.
        fmt : dict, optional
            Dicionário de formatação do método. Em `fmt["barras"]`,
            o parâmetro `espacamento` controla a distância entre as barras.
        caminho_imagem : str, default="grafico_barras_verticais.png"
            Arquivo de saída.

        Returns
        -------
        str
            Caminho da imagem gerada.
        """
        import textwrap

        fmt = self._merge_dict(self.fmt_barras_verticais(), fmt)
        df_plot = df[[coluna_categoria, coluna_valor]].dropna().copy()
        df_plot[coluna_valor] = pd.to_numeric(df_plot[coluna_valor], errors="coerce")
        df_plot = df_plot.dropna(subset=[coluna_valor])

        if df_plot.empty:
            raise ValueError("Não há dados válidos para gerar o gráfico de barras verticais.")

        fig, ax = plt.subplots(figsize=fmt["figura"]["figsize"], dpi=fmt["figura"]["dpi"])
        self._configurar_figura_e_eixos(fig, ax, fmt)

        categorias = df_plot[coluna_categoria].astype(str).tolist()
        valores = df_plot[coluna_valor].astype(float).to_numpy()

        largura_barra = fmt["barras"]["largura"]
        espacamento = fmt["barras"].get("espacamento", 0.35)
        passo = largura_barra + espacamento
        posicoes = np.arange(len(categorias), dtype=float) * passo

        lista_cores = self._resolver_lista_cores(cores, len(df_plot), fmt["barras"]["cor"])

        barras = ax.bar(
            posicoes,
            valores,
            color="none",
            edgecolor="none",
            width=largura_barra,
        )

        for barra, cor in zip(barras, lista_cores):
            self._desenhar_barra_vertical_arredondada(
                ax=ax,
                x_centro=barra.get_x() + barra.get_width() / 2,
                altura=barra.get_height(),
                largura=barra.get_width(),
                cor=cor,
                alpha=fmt["barras"]["alpha"],
                raio=fmt["barras"]["raio"],
            )

        angulo = fmt["eixos"]["angulo_rotulo_x"]
        quebra_automatica = fmt["rotulos"].get("quebra_automatica", True)
        largura_quebra = fmt["rotulos"].get("largura_quebra", 12)

        if quebra_automatica and angulo % 90 == 0:
            categorias_formatadas = [
                "\n".join(textwrap.wrap(str(cat), width=largura_quebra)) if str(cat).strip() else str(cat)
                for cat in categorias
            ]
        else:
            categorias_formatadas = categorias

        ax.set_xticks(posicoes)
        ax.set_xticklabels(categorias_formatadas)

        ax.set_title(titulo, fontsize=fmt["fonte"]["titulo"], color=fmt["fonte"]["color"])
        ax.set_xlabel(nome_eixo_x or coluna_categoria, fontsize=fmt["fonte"]["eixos"])
        ax.set_ylabel(nome_eixo_y or coluna_valor, fontsize=fmt["fonte"]["eixos"])

        ax.yaxis.set_major_formatter(self._formatter_factory(fmt["rotulos"]["casas_decimais"]))
        plt.setp(ax.get_xticklabels(), rotation=angulo, fontsize=fmt["fonte"]["ticks"], color=fmt["fonte"]["color"])

        self._aplicar_grade(ax, fmt)
        self._adicionar_rotulos_barras_verticais(ax, barras, fmt)

        margem_lateral = max(largura_barra, espacamento)
        ax.set_xlim(posicoes[0] - margem_lateral, posicoes[-1] + margem_lateral)

        return self._salvar_figura(fig, caminho_imagem, fmt["figura"]["dpi"], fmt["figura"]["facecolor"])

    def grafico_barras_horizontais(
        self,
        df: pd.DataFrame,
        coluna_categoria: str,
        coluna_valor: str,
        titulo: str,
        nome_eixo_x: Optional[str] = None,
        nome_eixo_y: Optional[str] = None,
        cores=None,
        ordenar_decrescente: bool = True,
        fmt: Optional[dict] = None,
        caminho_imagem: str = "grafico_barras_horizontais.png",
    ) -> str:
        """
        Gera um gráfico de barras horizontais e salva a imagem em arquivo.

        Parameters
        ----------
        df : pandas.DataFrame
            Base de dados de entrada.
        coluna_categoria : str
            Coluna categórica utilizada no eixo Y.
        coluna_valor : str
            Coluna numérica utilizada no eixo X.
        titulo : str
            Título do gráfico.
        nome_eixo_x : str, optional
            Nome exibido no eixo X.
        nome_eixo_y : str, optional
            Nome exibido no eixo Y.
        cores : None, str ou list, optional
            Cor única ou lista de cores para as barras.
        ordenar_decrescente : bool, default=True
            Se verdadeiro, ordena as barras por valor decrescente.
        fmt : dict, optional
            Dicionário de formatação do método. Em `fmt["barras"]`,
            o parâmetro `espacamento` controla a distância entre as barras.
        caminho_imagem : str, default="grafico_barras_horizontais.png"
            Arquivo de saída.

        Returns
        -------
        str
            Caminho da imagem gerada.
        """
        fmt = self._merge_dict(self.fmt_barras_horizontais(), fmt)
        df_plot = df[[coluna_categoria, coluna_valor]].dropna().copy()
        df_plot[coluna_valor] = pd.to_numeric(df_plot[coluna_valor], errors="coerce")
        df_plot = df_plot.dropna(subset=[coluna_valor])
        if ordenar_decrescente:
            df_plot = df_plot.sort_values(by=coluna_valor, ascending=False).reset_index(drop=True)
        if df_plot.empty:
            raise ValueError("Não há dados válidos para gerar o gráfico de barras horizontais.")

        fig, ax = plt.subplots(figsize=fmt["figura"]["figsize"], dpi=fmt["figura"]["dpi"])
        self._configurar_figura_e_eixos(fig, ax, fmt)

        categorias = df_plot[coluna_categoria].astype(str).tolist()
        valores = df_plot[coluna_valor].astype(float).to_numpy()
        altura_barra = fmt["barras"]["largura"]
        espacamento = fmt["barras"].get("espacamento", 0.35)
        passo = altura_barra + espacamento
        posicoes = np.arange(len(categorias), dtype=float) * passo
        lista_cores = self._resolver_lista_cores(cores, len(df_plot), fmt["barras"]["cor"])
        barras = ax.barh(
            posicoes,
            valores,
            color="none",
            edgecolor="none",
            height=altura_barra,
        )

        for barra, cor in zip(barras, lista_cores):
            self._desenhar_barra_horizontal_arredondada(
                ax=ax,
                y_centro=barra.get_y() + barra.get_height() / 2,
                largura_barra=barra.get_width(),
                altura=barra.get_height(),
                cor=cor,
                alpha=fmt["barras"]["alpha"],
                raio=fmt["barras"]["raio"],
            )

        ax.set_yticks(posicoes)
        ax.set_yticklabels(categorias)
        ax.invert_yaxis()

        ax.set_title(titulo, fontsize=fmt["fonte"]["titulo"], color=fmt["fonte"]["color"])
        ax.set_xlabel(nome_eixo_x or coluna_valor, fontsize=fmt["fonte"]["eixos"])
        ax.set_ylabel(nome_eixo_y or coluna_categoria, fontsize=fmt["fonte"]["eixos"])
        ax.xaxis.set_major_formatter(self._formatter_factory(fmt["rotulos"]["casas_decimais"]))
        self._aplicar_grade(ax, fmt)
        self._adicionar_rotulos_barras_horizontais(ax, barras, fmt)
        margem_vertical = max(altura_barra, espacamento)
        ax.set_ylim(posicoes[-1] + margem_vertical, posicoes[0] - margem_vertical)

        return self._salvar_figura(fig, caminho_imagem, fmt["figura"]["dpi"], fmt["figura"]["facecolor"])

    def grafico_barras_multiplas(
        self,
        df: pd.DataFrame,
        coluna_categoria: str,
        colunas_valores: List[str],
        titulo: str,
        cores: Optional[Dict[str, Dict[str, str]]] = None,
        nome_eixo_x: Optional[str] = None,
        nome_eixo_y: Optional[str] = None,
        fmt: Optional[dict] = None,
        caminho_imagem: str = "grafico_barras_multiplas.png",
    ) -> str:
        """
        Gera um gráfico de barras agrupadas para múltiplas séries por categoria.

        Parameters
        ----------
        df : pandas.DataFrame
            Base de dados de entrada.
        coluna_categoria : str
            Coluna das categorias do eixo X.
        colunas_valores : list[str]
            Colunas numéricas que serão exibidas como séries.
        titulo : str
            Título do gráfico.
        cores : dict, optional
            Dicionário no formato {categoria: {serie: "#HEX"}}.
        nome_eixo_x : str, optional
            Nome exibido no eixo X.
        nome_eixo_y : str, optional
            Nome exibido no eixo Y.
        fmt : dict, optional
            Dicionário de formatação do método. Em `fmt["barras"]`,
            `largura` controla a largura de cada barra, `espacamento_series`
            controla a distância entre barras dentro do mesmo grupo e
            `espacamento_grupos` controla a distância entre grupos.
        caminho_imagem : str, default="grafico_barras_multiplas.png"
            Arquivo de saída.

        Returns
        -------
        str
            Caminho da imagem gerada.
        """
        fmt = self._merge_dict(self.fmt_barras_multiplas(), fmt)
        colunas_necessarias = [coluna_categoria] + list(colunas_valores)
        df_plot = df[colunas_necessarias].dropna().copy()
        if df_plot.empty:
            raise ValueError("Não há dados válidos para gerar o gráfico de barras múltiplas.")

        for coluna in colunas_valores:
            df_plot[coluna] = pd.to_numeric(df_plot[coluna], errors="coerce")
        df_plot = df_plot.dropna()

        categorias = df_plot[coluna_categoria].astype(str).tolist()
        n_series = len(colunas_valores)
        largura = fmt["barras"]["largura"]
        espacamento_series = fmt["barras"].get("espacamento_series", 0.04)
        espacamento_grupos = fmt["barras"].get("espacamento_grupos", 0.45)
        largura_grupo = (n_series * largura) + (max(n_series - 1, 0) * espacamento_series)
        passo_grupo = largura_grupo + espacamento_grupos
        x = np.arange(len(categorias), dtype=float) * passo_grupo

        fig, ax = plt.subplots(figsize=fmt["figura"]["figsize"], dpi=fmt["figura"]["dpi"])
        self._configurar_figura_e_eixos(fig, ax, fmt)
        lista_barras = []

        for i, serie in enumerate(colunas_valores):
            deslocamento = (-largura_grupo / 2) + (largura / 2) + i * (largura + espacamento_series)
            valores = df_plot[serie].astype(float).to_numpy()
            cores_barras = [
                (cores or {}).get(categoria, {}).get(serie, fmt["barras"]["cor"])
                for categoria in categorias
            ]
            barras = ax.bar(
                x + deslocamento,
                valores,
                width=largura,
                label=serie,
                color="none",
                edgecolor="none",
            )
            lista_barras.append(barras)

            for barra, cor in zip(barras, cores_barras):
                self._desenhar_barra_vertical_arredondada(
                    ax=ax,
                    x_centro=barra.get_x() + barra.get_width() / 2,
                    altura=barra.get_height(),
                    largura=barra.get_width(),
                    cor=cor,
                    alpha=fmt["barras"]["alpha"],
                    raio=fmt["barras"]["raio"],
                )

            if fmt["rotulos"]["mostrar"]:
                for barra in barras:
                    altura = barra.get_height()
                    ax.text(
                        barra.get_x() + barra.get_width() / 2,
                        altura + fmt["rotulos"]["offset"],
                        self._formatar_numero(altura, casas_decimais=fmt["rotulos"]["casas_decimais"]),
                        ha="center",
                        va="bottom",
                        fontsize=fmt["fonte"]["rotulo_dados"],
                        color=fmt["fonte"]["color"],
                    )

        ax.set_xticks(x)
        ax.set_xticklabels(categorias)
        plt.setp(ax.get_xticklabels(), rotation=fmt["eixos"]["angulo_rotulo_x"])
        ax.set_title(titulo, fontsize=fmt["fonte"]["titulo"], color=fmt["fonte"]["color"])
        ax.set_xlabel(nome_eixo_x or coluna_categoria, fontsize=fmt["fonte"]["eixos"])
        ax.set_ylabel(nome_eixo_y or "Valor", fontsize=fmt["fonte"]["eixos"])
        ax.yaxis.set_major_formatter(self._formatter_factory(fmt["rotulos"]["casas_decimais"]))
        self._aplicar_grade(ax, fmt)

        if fmt["legenda"]["mostrar"]:
            ax.legend(
                loc=fmt["legenda"]["posicao"],
                bbox_to_anchor=fmt["legenda"]["bbox_to_anchor"],
                ncol=fmt["legenda"]["ncol"],
                frameon=fmt["legenda"]["frameon"],
                fontsize=fmt["fonte"]["legenda"],
            )

        margem_lateral = max(largura, espacamento_grupos / 2 if espacamento_grupos > 0 else largura)
        ax.set_xlim(x[0] - largura_grupo / 2 - margem_lateral, x[-1] + largura_grupo / 2 + margem_lateral)

        return self._salvar_figura(fig, caminho_imagem, fmt["figura"]["dpi"], fmt["figura"]["facecolor"])

    def grafico_dispersao(
        self,
        df: pd.DataFrame,
        coluna_x: str,
        coluna_y: str,
        titulo: str,
        nome_eixo_x: Optional[str] = None,
        nome_eixo_y: Optional[str] = None,
        fmt: Optional[dict] = None,
        caminho_imagem: str = "grafico_dispersao.png",
    ) -> str:
  
        """        
        Gera um gráfico de dispersão e salva a imagem em arquivo.

        Parameters
        ----------
        df : pandas.DataFrame
            Base de dados de entrada.
        coluna_x : str
            Coluna numérica do eixo X.
        coluna_y : str
            Coluna numérica do eixo Y.
        titulo : str
            Título do gráfico.
        nome_eixo_x : str, optional
            Nome exibido no eixo X.
        nome_eixo_y : str, optional
            Nome exibido no eixo Y.
        fmt : dict, optional
            Dicionário de formatação do método.
        caminho_imagem : str, default="grafico_dispersao.png"
            Arquivo de saída.

        Returns
        -------
        str
            Caminho da imagem gerada.
        """
        
        fmt = self._merge_dict(self.fmt_dispersao(), fmt)
        df_plot = df[[coluna_x, coluna_y]].dropna().copy()
        df_plot[coluna_x] = pd.to_numeric(df_plot[coluna_x], errors="coerce")
        df_plot[coluna_y] = pd.to_numeric(df_plot[coluna_y], errors="coerce")
        df_plot = df_plot.dropna()
        if df_plot.empty:
            raise ValueError("Não há dados válidos para gerar o gráfico de dispersão.")

        fig, ax = plt.subplots(figsize=fmt["figura"]["figsize"], dpi=fmt["figura"]["dpi"])
        self._configurar_figura_e_eixos(fig, ax, fmt)
        ax.scatter(
            df_plot[coluna_x],
            df_plot[coluna_y],
            s=fmt["dispersao"]["tamanho"],
            color=fmt["dispersao"]["cor"],
            alpha=fmt["dispersao"]["alpha"],
        )
        ax.set_title(titulo, fontsize=fmt["fonte"]["titulo"], color=fmt["fonte"]["color"])
        ax.set_xlabel(nome_eixo_x or coluna_x, fontsize=fmt["fonte"]["eixos"])
        ax.set_ylabel(nome_eixo_y or coluna_y, fontsize=fmt["fonte"]["eixos"])
        self._aplicar_grade(ax, fmt)

        return self._salvar_figura(fig, caminho_imagem, fmt["figura"]["dpi"], fmt["figura"]["facecolor"])

    def grafico_pizza(
        self,
        df: pd.DataFrame,
        coluna_rotulo: str,
        coluna_valor: str,
        titulo: str,
        fmt: Optional[dict] = None,
        caminho_imagem: str = "grafico_pizza.png",
    ) -> str:
        """
        Gera um gráfico de pizza e salva a imagem em arquivo.
        """
        fmt = self._merge_dict(self.fmt_pizza(), fmt)

        df_plot = df[[coluna_rotulo, coluna_valor]].dropna().copy()
        df_plot[coluna_valor] = pd.to_numeric(df_plot[coluna_valor], errors="coerce")
        df_plot = df_plot.dropna(subset=[coluna_valor])

        # Remove valores zerados ou negativos para não exibir rótulos 0%
        df_plot = df_plot[df_plot[coluna_valor] > 0]

        if df_plot.empty:
            raise ValueError("Não há dados válidos para gerar o gráfico de pizza.")

        fig, ax = plt.subplots(
            figsize=fmt["figura"]["figsize"],
            dpi=fmt["figura"]["dpi"]
        )

        fig.patch.set_facecolor(fmt["figura"]["facecolor"])
        fig.patch.set_alpha(fmt["figura"]["alpha"])
        plt.rcParams["font.family"] = fmt["fonte"]["family"]

        cores = self._resolver_lista_cores(fmt["pizza"]["cores"], len(df_plot), "#FFBD59")

        explode = fmt["pizza"]["explode"]
        if explode is None or len(explode) != len(df_plot):
            explode = [0] * len(df_plot)

        valores = df_plot[coluna_valor].astype(float).values
        rotulos = df_plot[coluna_rotulo].astype(str).tolist()
        total = valores.sum()

        wedges, _ = ax.pie(
            valores,
            labels=None,
            colors=cores,
            startangle=fmt["pizza"]["startangle"],
            explode=explode,
            wedgeprops={"edgecolor": "white"},
        )

        anotacoes = []

        for i, wedge in enumerate(wedges):
            pct = 100 * valores[i] / total

            # Não mostra rótulo quando percentual for zero
            if pct <= 0:
                continue

            ang = (wedge.theta2 + wedge.theta1) / 2.0
            ang_rad = np.deg2rad(ang)

            x = np.cos(ang_rad)
            y = np.sin(ang_rad)

            if callable(fmt["pizza"]["autopct"]):
                pct_txt = fmt["pizza"]["autopct"](pct)
            elif isinstance(fmt["pizza"]["autopct"], str):
                pct_txt = fmt["pizza"]["autopct"] % pct
            else:
                pct_txt = f"{pct:.1f}%"

            anotacoes.append({
                "i": i,
                "x": x,
                "y": y,
                "lado": "direita" if x >= 0 else "esquerda",
                "texto": f"{rotulos[i]} ({pct_txt})"
            })

        def ajustar_y(lista, distancia_minima=0.16, limite_inf=-1.15, limite_sup=1.15):
            lista = sorted(lista, key=lambda item: item["y"])

            for idx in range(1, len(lista)):
                if lista[idx]["y"] - lista[idx - 1]["y"] < distancia_minima:
                    lista[idx]["y"] = lista[idx - 1]["y"] + distancia_minima

            excesso_sup = lista[-1]["y"] - limite_sup if lista else 0
            if excesso_sup > 0:
                for item in lista:
                    item["y"] -= excesso_sup

            excesso_inf = limite_inf - lista[0]["y"] if lista else 0
            if excesso_inf > 0:
                for item in lista:
                    item["y"] += excesso_inf

            return lista

        esquerda = ajustar_y([a for a in anotacoes if a["lado"] == "esquerda"])
        direita = ajustar_y([a for a in anotacoes if a["lado"] == "direita"])

        for item in esquerda + direita:
            x = item["x"]
            y = item["y"]

            x_texto = 1.35 if item["lado"] == "direita" else -1.35
            ha = "left" if item["lado"] == "direita" else "right"

            ax.annotate(
                item["texto"],
                xy=(item["x"], item["y"]),
                xytext=(x_texto, y),
                ha=ha,
                va="center",
                color=fmt["fonte"]["color"],
                fontsize=fmt["fonte"]["ticks"],
                arrowprops=dict(
                    arrowstyle="-",
                    color=fmt["fonte"]["color"],
                    lw=1,
                    connectionstyle="angle3,angleA=0,angleB=90",
                ),
            )

            ax.plot(
                [item["x"]],
                [item["y"]],
                marker="o",
                markersize=4,
                color=fmt["fonte"]["color"],
            )

        ax.axis("equal")

        ax.set_title(
            titulo,
            fontsize=fmt["fonte"]["titulo"],
            color=fmt["fonte"]["color"]
        )

        if fmt["legenda"]["mostrar"]:
            ax.legend(
                wedges,
                rotulos,
                loc=fmt["legenda"]["posicao"],
                bbox_to_anchor=fmt["legenda"]["bbox_to_anchor"],
                ncol=fmt["legenda"]["ncol"],
                frameon=fmt["legenda"]["frameon"],
            )

        return self._salvar_figura(
            fig,
            caminho_imagem,
            fmt["figura"]["dpi"],
            fmt["figura"]["facecolor"]
        )

    def grafico_linhas_interpoladas(
        self,
        df: pd.DataFrame,
        coluna_x: str,
        coluna_y: str,
        titulo: str,
        nome_eixo_x: Optional[str] = None,
        nome_eixo_y: Optional[str] = None,
        fmt: Optional[dict] = None,
        caminho_imagem: str = "grafico_linhas_interpoladas.png",
    ) -> str:
        """
        Gera um gráfico de linhas com interpolação suave e salva a imagem em arquivo.

        Quando a interpolação cúbica não for possível, a função recua
        automaticamente para a linha simples com os pontos originais.

        Parameters
        ----------
        df : pandas.DataFrame
            Base de dados de entrada.
        coluna_x : str
            Coluna do eixo X.
        coluna_y : str
            Coluna numérica do eixo Y.
        titulo : str
            Título do gráfico.
        nome_eixo_x : str, optional
            Nome exibido no eixo X.
        nome_eixo_y : str, optional
            Nome exibido no eixo Y.
        fmt : dict, optional
            Dicionário de formatação do método.
        caminho_imagem : str, default="grafico_linhas_interpoladas.png"
            Arquivo de saída.

        Returns
        -------
        str
            Caminho da imagem gerada.
        """
        fmt = self._merge_dict(self.fmt_linhas_interpoladas(), fmt)
        df_plot = df[[coluna_x, coluna_y]].dropna().copy().reset_index(drop=True)
        df_plot[coluna_y] = pd.to_numeric(df_plot[coluna_y], errors="coerce")
        df_plot = df_plot.dropna(subset=[coluna_y]).reset_index(drop=True)
        if df_plot.empty:
            raise ValueError("Não há dados válidos para gerar o gráfico de linhas interpoladas.")

        x_original = df_plot[coluna_x]
        y_original = df_plot[coluna_y].astype(float).to_numpy()
        x_numerico = np.arange(len(df_plot), dtype=float)

        fig, ax = plt.subplots(figsize=fmt["figura"]["figsize"], dpi=fmt["figura"]["dpi"])
        self._configurar_figura_e_eixos(fig, ax, fmt)

        if fmt["linhas"]["suavizar"] and len(df_plot) >= 4 and make_interp_spline is not None and len(np.unique(y_original)) > 1:
            x_suave = np.linspace(x_numerico.min(), x_numerico.max(), 300)
            spline = make_interp_spline(x_numerico, y_original, k=3)
            y_suave = spline(x_suave)
            ax.plot(
                x_suave,
                y_suave,
                color=fmt["linhas"]["cor"],
                linewidth=fmt["linhas"]["largura"],
                alpha=fmt["linhas"]["alpha"],
            )
        else:
            ax.plot(
                x_numerico,
                y_original,
                color=fmt["linhas"]["cor"],
                linewidth=fmt["linhas"]["largura"],
                alpha=fmt["linhas"]["alpha"],
            )

        if fmt["linhas"]["mostrar_pontos"]:
            ax.scatter(
                x_numerico,
                y_original,
                color=fmt["linhas"]["cor"],
                s=fmt["linhas"]["tamanho_pontos"],
                alpha=fmt["linhas"]["alpha"],
            )

        ax.set_xticks(x_numerico)
        ax.set_xticklabels(x_original.astype(str).tolist())
        plt.setp(ax.get_xticklabels(), rotation=fmt["eixos"]["angulo_rotulo_x"])
        ax.set_title(titulo, fontsize=fmt["fonte"]["titulo"], color=fmt["fonte"]["color"])
        ax.set_xlabel(nome_eixo_x or coluna_x, fontsize=fmt["fonte"]["eixos"])
        ax.set_ylabel(nome_eixo_y or coluna_y, fontsize=fmt["fonte"]["eixos"])
        self._aplicar_grade(ax, fmt)

        return self._salvar_figura(fig, caminho_imagem, fmt["figura"]["dpi"], fmt["figura"]["facecolor"])
    
    def grafico_barras_empilhadas_percentual(
        self,
        df,
        coluna_categoria: str,
        colunas_valores: list,
        titulo: str = "",
        orientacao: str = "v",
        fmt: dict | None = None,
        caminho_imagem: str = "grafico_barras_empilhadas_percentual.png",):
        """
        Gera um gráfico de barras empilhadas percentual (100%), com suporte de
        até quatro categorias empilhadas por barra.

        A função utiliza cores por rótulo por meio da chave
        `fmt["barras"]["cores_por_categoria"]`, permitindo que cada segmento
        mantenha sua identidade visual independentemente da ordem em
        `colunas_valores`.

        Parameters
        ----------
        df : pandas.DataFrame
            DataFrame de entrada contendo a coluna categórica e as colunas
            numéricas que compõem os percentuais.
        coluna_categoria : str
            Nome da coluna categórica que identifica cada barra.
        colunas_valores : list
            Lista com até 4 colunas numéricas que serão empilhadas.
            A soma de cada linha será normalizada para 100% quando
            `fmt["empilhado"]["normalizar"]` estiver ativo.
        titulo : str, default=""
            Título do gráfico.
        orientacao : str, default="v"
            Orientação do gráfico:
            - "v" para barras verticais
            - "h" para barras horizontais
        fmt : dict, optional
            Dicionário de formatação retornado por
            `fmt_barras_empilhadas_percentual`.
        caminho_imagem : str, default="grafico_barras_empilhadas_percentual.png"
            Caminho do arquivo de saída da imagem.

        Returns
        -------
        str
            Caminho da imagem gerada.

        Raises
        ------
        ValueError
            Se `colunas_valores` estiver vazia, exceder o limite de categorias
            suportado, se houver colunas ausentes no DataFrame, ou se a
            orientação for inválida.
        """

        def _formatar_numero_br(valor: float, casas: int = 0, sufixo: str = "") -> str:
            texto = f"{valor:.{casas}f}".replace(".", ",")
            return f"{texto}{sufixo}"

        def _formatter_percentual(casas: int = 0):
            return FuncFormatter(lambda x, pos: _formatar_numero_br(x, casas=casas, sufixo="%"))

        if fmt is None:
            fmt = self.fmt_barras_empilhadas_percentual()

        if not isinstance(colunas_valores, list) or not colunas_valores:
            raise ValueError("`colunas_valores` deve ser uma lista com pelo menos uma coluna.")

        limite_categorias = fmt.get("empilhado", {}).get("limite_categorias", 4)
        if len(colunas_valores) > limite_categorias:
            raise ValueError(
                f"O gráfico suporta no máximo {limite_categorias} categorias em `colunas_valores`."
            )

        if orientacao not in ("v", "h"):
            raise ValueError("`orientacao` deve ser 'v' para vertical ou 'h' para horizontal.")

        colunas_necessarias = [coluna_categoria] + colunas_valores
        colunas_ausentes = [col for col in colunas_necessarias if col not in df.columns]
        if colunas_ausentes:
            raise ValueError(f"As seguintes colunas não existem no DataFrame: {colunas_ausentes}")

        ordem_categorias = fmt["barras"].get("ordem_categorias")
        if ordem_categorias:
            colunas_valores = [col for col in ordem_categorias if col in colunas_valores]

        df_plot = df[colunas_necessarias].copy()
        df_plot[colunas_valores] = df_plot[colunas_valores].apply(pd.to_numeric, errors="coerce").fillna(0)

        if fmt["empilhado"].get("ordenar_por_total", False):
            df_plot["_total_temp"] = df_plot[colunas_valores].sum(axis=1)
            df_plot = (
                df_plot.sort_values("_total_temp", ascending=False)
                .drop(columns="_total_temp")
                .reset_index(drop=True)
            )

        if fmt["empilhado"].get("normalizar", True):
            total = df_plot[colunas_valores].sum(axis=1).replace(0, np.nan)
            for coluna in colunas_valores:
                df_plot[coluna] = (df_plot[coluna] / total) * fmt["eixos"].get("limite_percentual", 100)
            df_plot[colunas_valores] = df_plot[colunas_valores].fillna(0)

        categorias = df_plot[coluna_categoria].astype(str).tolist()
        n_barras = len(categorias)
        largura = fmt["barras"]["largura"]
        espacamento = fmt["barras"]["espacamento"]
        posicoes = np.arange(n_barras, dtype=float) * (largura + espacamento)

        plt.rcParams["font.family"] = fmt["fonte"]["family"]

        fig, ax = plt.subplots(
            figsize=fmt["figura"]["figsize"],
            dpi=fmt["figura"]["dpi"],
            facecolor=fmt["figura"]["facecolor"],
        )
        fig.patch.set_alpha(fmt["figura"].get("alpha", 1.0))
        ax.set_facecolor(fmt["figura"]["facecolor"])

        acumulado = np.zeros(n_barras, dtype=float)
        mapa_cores = fmt["barras"].get("cores_por_categoria", {})
        casas_rotulo = fmt["rotulos"].get("casas_decimais", 0)
        min_percentual_exibir = fmt["rotulos"].get("min_percentual_exibir", 0)

        for coluna in colunas_valores:
            valores = df_plot[coluna].to_numpy(dtype=float)
            cor = mapa_cores.get(coluna, fmt["barras"]["cor"])

            if orientacao == "v":
                ax.bar(
                    posicoes,
                    valores,
                    bottom=acumulado,
                    width=largura,
                    color=cor,
                    alpha=fmt["barras"]["alpha"],
                    label=coluna,
                )
            else:
                ax.barh(
                    posicoes,
                    valores,
                    left=acumulado,
                    height=largura,
                    color=cor,
                    alpha=fmt["barras"]["alpha"],
                    label=coluna,
                )

            if fmt["rotulos"].get("mostrar", False) or fmt["rotulos"].get("mostrar_percentual", False):
                for i, valor in enumerate(valores):
                    if valor <= 0 or valor < min_percentual_exibir:
                        continue

                    texto = _formatar_numero_br(valor, casas=casas_rotulo, sufixo="%")
                    cor_texto = fmt["rotulos"]["cor_texto_interno"]

                    if orientacao == "v":
                        ax.text(
                            posicoes[i],
                            acumulado[i] + (valor / 2),
                            texto,
                            ha="center",
                            va="center",
                            fontsize=fmt["fonte"]["rotulo_dados"],
                            color=cor_texto,
                            fontweight="bold",
                        )
                    else:
                        ax.text(
                            acumulado[i] + (valor / 2),
                            posicoes[i],
                            texto,
                            ha="center",
                            va="center",
                            fontsize=fmt["fonte"]["rotulo_dados"],
                            color=cor_texto,
                            fontweight="bold",
                        )

            acumulado += valores

        ax.set_title(
            titulo,
            fontsize=fmt["fonte"]["titulo"],
            color=fmt["fonte"]["color"],
        )

        if orientacao == "v":
            ax.set_xticks(posicoes)
            ax.set_xticklabels(
                categorias,
                rotation=fmt["eixos"]["angulo_rotulo_x"],
                fontsize=fmt["fonte"]["ticks"],
                color=fmt["fonte"]["color"],
            )
            ax.set_ylim(0, fmt["eixos"].get("limite_percentual", 100))
            if fmt["eixos"].get("mostrar_ticks_percentual", True):
                ax.yaxis.set_major_formatter(_formatter_percentual(casas=0))
            ax.tick_params(axis="y", labelsize=fmt["fonte"]["ticks"], colors=fmt["fonte"]["color"])
        else:
            ax.set_yticks(posicoes)
            ax.set_yticklabels(
                categorias,
                fontsize=fmt["fonte"]["ticks"],
                color=fmt["fonte"]["color"],
            )
            ax.set_xlim(0, fmt["eixos"].get("limite_percentual", 100))
            if fmt["eixos"].get("mostrar_ticks_percentual", True):
                ax.xaxis.set_major_formatter(_formatter_percentual(casas=0))
            ax.tick_params(axis="x", labelsize=fmt["fonte"]["ticks"], colors=fmt["fonte"]["color"])

        if fmt["eixos"]["mostrar_grade_vertical"]:
            ax.xaxis.grid(
                True,
                color=fmt["eixos"]["cor_grade_vertical"],
                linewidth=fmt["eixos"]["largura_grade_vertical"],
                alpha=fmt["eixos"]["alpha_grade_vertical"],
                linestyle=fmt["eixos"]["estilo_grade_vertical"],
            )
        else:
            ax.xaxis.grid(False)

        if fmt["eixos"]["mostrar_grade_horizontal"]:
            ax.yaxis.grid(
                True,
                color=fmt["eixos"]["cor_grade_horizontal"],
                linewidth=fmt["eixos"]["largura_grade_horizontal"],
                alpha=fmt["eixos"]["alpha_grade_horizontal"],
                linestyle=fmt["eixos"]["estilo_grade_horizontal"],
            )
        else:
            ax.yaxis.grid(False)

        ax.spines["bottom"].set_visible(fmt["eixos"]["mostrar_linha_x"])
        ax.spines["left"].set_visible(fmt["eixos"]["mostrar_linha_y"])
        ax.spines["top"].set_visible(fmt["eixos"]["mostrar_linha_top"])
        ax.spines["right"].set_visible(fmt["eixos"]["mostrar_linha_right"])

        ax.spines["bottom"].set_color(fmt["eixos"]["cor_linha_x"])
        ax.spines["left"].set_color(fmt["eixos"]["cor_linha_y"])
        ax.spines["top"].set_color(fmt["eixos"]["cor_linha_top"])
        ax.spines["right"].set_color(fmt["eixos"]["cor_linha_right"])

        ax.spines["bottom"].set_linewidth(fmt["eixos"]["largura_linha_x"])
        ax.spines["left"].set_linewidth(fmt["eixos"]["largura_linha_y"])

        if fmt["legenda"]["mostrar"]:
            ax.legend(
                loc=fmt["legenda"]["posicao"],
                bbox_to_anchor=fmt["legenda"]["bbox_to_anchor"],
                ncol=fmt["legenda"]["ncol"],
                frameon=fmt["legenda"]["frameon"],
                fontsize=fmt["fonte"]["ticks"],
            )

        plt.tight_layout()
        fig.savefig(
            caminho_imagem,
            dpi=fmt["figura"]["dpi"],
            facecolor=fmt["figura"]["facecolor"],
            bbox_inches="tight",
        )
        plt.close(fig)
    
        return self._salvar_figura(fig, caminho_imagem, fmt["figura"]["dpi"], fmt["figura"]["facecolor"])
    
    def plot_mapa(
        self,
        df,
        lat_col,
        lon_col,
        figsize=(10, 6),
        fmt=None,
    ):
        """
        Plota latitude x longitude sobre um mapa cartográfico real ocupando
        toda a área da figura (sem bordas ou margens).

        Parâmetros
        ----------
        df : pandas.DataFrame
            DataFrame com os dados geográficos.

        lat_col : str
            Nome da coluna de latitude.

        lon_col : str
            Nome da coluna de longitude.

        figsize : tuple
            Tamanho da figura (largura, altura).

        fmt : dict, optional
            Dicionário com parâmetros de formatação do mapa.

            Chaves aceitas:
                - "titulo"
                - "cor_marcador"
                - "tamanho_marcador"
                - "tipo_marcador"
                - "zoom"
                - "distancia_mapa"
                - "fonte"
                - "tamanho_fonte"
                - "tema"
                - "alpha_marcador"
        """

        fmt = fmt or {}

        titulo = fmt.get("titulo", None)
        cor_marcador = fmt.get("cor_marcador", "red")
        tamanho_marcador = fmt.get("tamanho_marcador", 80)
        tipo_marcador = fmt.get("tipo_marcador", "circulo")
        zoom = fmt.get("zoom", 5)
        distancia_mapa = fmt.get("distancia_mapa", 1.0)
        fonte = fmt.get("fonte", "DejaVu Sans")
        tamanho_fonte = fmt.get("tamanho_fonte", 12)
        tema = fmt.get("tema", "openstreetmap")
        alpha_marcador = fmt.get("alpha_marcador", 0.85)

        marker_map = {
            "circulo": "o",
            "triangulo": "^",
            "quadrado": "s",
            "losango": "D",
            "xis": "x",
            "estrela": "*",
        }

        tema_map = {
            "openstreetmap": ctx.providers.OpenStreetMap.Mapnik,
            "positron": ctx.providers.CartoDB.Positron,
            "dark": ctx.providers.CartoDB.DarkMatter,
            "voyager": ctx.providers.CartoDB.Voyager,
            "terrain": ctx.providers.Stadia.Outdoors,
            "satellite": ctx.providers.Esri.WorldImagery,
        }

        # ------------------------------------------------------------------
        # Validação
        # ------------------------------------------------------------------
        if lat_col not in df.columns:
            raise ValueError(f"Coluna de latitude não encontrada: {lat_col}")

        if lon_col not in df.columns:
            raise ValueError(f"Coluna de longitude não encontrada: {lon_col}")

        # ------------------------------------------------------------------
        # Limpeza
        # ------------------------------------------------------------------
        df_plot = df[[lat_col, lon_col]].copy()
        df_plot[lat_col] = pd.to_numeric(df_plot[lat_col], errors="coerce")
        df_plot[lon_col] = pd.to_numeric(df_plot[lon_col], errors="coerce")
        df_plot = df_plot.dropna()

        if df_plot.empty:
            raise ValueError("Não há coordenadas válidas para plotagem.")

        # ------------------------------------------------------------------
        # GeoDataFrame
        # ------------------------------------------------------------------
        gdf = gpd.GeoDataFrame(
            df_plot,
            geometry=gpd.points_from_xy(df_plot[lon_col], df_plot[lat_col]),
            crs="EPSG:4326",
        )

        gdf_web = gdf.to_crs(epsg=3857)

        # ------------------------------------------------------------------
        # Figura (100% ocupada)
        # ------------------------------------------------------------------
        plt.rcParams["font.family"] = fonte

        fig, ax = plt.subplots(figsize=figsize)

        # Remove TODAS as margens
        ax.set_position([0, 0, 1, 1])

        # ------------------------------------------------------------------
        # Plot
        # ------------------------------------------------------------------
        marker_plot = marker_map.get(str(tipo_marcador).lower(), "o")
        basemap_source = tema_map.get(str(tema).lower(), ctx.providers.OpenStreetMap.Mapnik)

        gdf_web.plot(
            ax=ax,
            color=cor_marcador,
            markersize=tamanho_marcador,
            marker=marker_plot,
            alpha=alpha_marcador,
        )

        # ------------------------------------------------------------------
        # Enquadramento
        # ------------------------------------------------------------------
        xmin, ymin, xmax, ymax = gdf_web.total_bounds

        span_x = max(xmax - xmin, 1)
        span_y = max(ymax - ymin, 1)

        fator_zoom = max(float(zoom), 1.0)
        fator_distancia = max(float(distancia_mapa), 0.1)

        margem_x = (span_x * (1.2 / fator_zoom)) * fator_distancia
        margem_y = (span_y * (1.2 / fator_zoom)) * fator_distancia

        ax.set_xlim(xmin - margem_x, xmax + margem_x)
        ax.set_ylim(ymin - margem_y, ymax + margem_y)

        # ------------------------------------------------------------------
        # Basemap
        # ------------------------------------------------------------------
        try:
            ctx.add_basemap(
                ax,
                source=basemap_source,
                zoom="auto",
            )
        except Exception:
            # Fallback: mapa sem basemap se tiles indisponíveis/timeout
            pass

        # ------------------------------------------------------------------
        # Visual final (mapa puro)
        # ------------------------------------------------------------------
        ax.set_axis_off()

        if titulo:
            ax.set_title(titulo, fontsize=tamanho_fonte, pad=10)

        return fig