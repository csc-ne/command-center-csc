# =========================================
# VENEZA EQUIPAMENTOS
# CENTRO DE SOLUCOES CONECTADAS - CSC
# RELATÓRIOS DE DESEMPENHO AUTOMÁTICOS - RDA - MODULO PDF
# -----------------------------------------
# CONTROLE DE VERSIONAMENTO
# v0.2.3 - 2026-03-25
# - Mantida a quebra automatica de pagina em tabelas grandes.
# - Ajustado o reinicio de secoes de tabela nas paginas seguintes com o
#   mesmo afastamento vertical da primeira pagina da tabela.
# - Mantida a repeticao do cabecalho em paginas subsequentes.
# - Atualizadas as docstrings das funcoes de tabela afetadas.

# v0.2.2 - 2026-03-25
# - Ajustada a renderizacao de tabelas para quebra automatica de pagina.
# - Mantida a repeticao do cabecalho em paginas subsequentes.
# - Adicionado suporte a espacamento antes da tabela via fmt e parametros.
# - Corrigido o tratamento de nomes_colunas quando nao informado.
# - Atualizadas as docstrings das funcoes de tabela afetadas.
# =========================================

"""
===============================================================================
REPORTLAB - (C) Copyright ReportLab Europe Ltd. 2000-2023.
===============================================================================

Descrição
---------
O ReportLab é uma biblioteca Python utilizada para geração dinâmica de
documentos PDF. A biblioteca permite criação de relatórios, tabelas,
gráficos, imagens, textos formatados, páginas customizadas e elementos
vetoriais de forma programática.

Aplicação no Projeto
--------------------
Nesta aplicação, o ReportLab é utilizado para:

- Geração automatizada de relatórios PDF
- Criação de layouts técnicos e corporativos
- Inserção de gráficos, tabelas e imagens
- Controle de paginação e formatação
- Exportação de documentos em padrão A4/A3
- Criação de relatórios personalizados para clientes

Licença
--------
O ReportLab é distribuído sob a licença BSD License.

Resumo da licença:
- Permite uso comercial
- Permite modificação
- Permite distribuição
- Permite uso privado
- Não exige abertura do código-fonte da aplicação

Documentação Oficial
--------------------
https://www.reportlab.com/documentation/

Repositório Oficial
-------------------
https://github.com/MrBitBucket/reportlab-mirror

Instalação
----------
Via pip:

    pip install reportlab

===============================================================================
"""

import io
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence

from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from typing import Optional
from PIL import Image


class Relatorio:
    """Classe utilitaria para geracao de documentos PDF com ReportLab.

    A classe encapsula configuracoes de pagina, controle de cursor,
    insercao de textos, tabelas, imagens, figuras e composicao de PDFs.

    Attributes:
        nome_arquivo: Caminho do arquivo PDF de saida.
        formato_pagina: Tamanho da pagina em pontos.
        width: Largura da pagina atual.
        height: Altura da pagina atual.
        margin_left: Margem esquerda em pontos.
        margin_right: Margem direita em pontos.
        margin_top: Margem superior em pontos.
        margin_bottom: Margem inferior em pontos.
        c: Canvas principal do ReportLab.
        cursor_y: Posicao vertical atual do fluxo de escrita.
        initial_cursor_y: Posicao vertical inicial da area util.
    """

    def __init__(
        self,
        nome_arquivo: str,
        formato_pagina=A4,
        margins=(2 * cm, 2 * cm, 3 * cm, 2 * cm),
    ) -> None:
        """Inicializa a estrutura base do relatorio.

        Args:
            nome_arquivo: Caminho do PDF a ser gerado.
            formato_pagina: Tamanho da pagina. O padrao e A4.
            margins: Tupla com margens na ordem
                (left, right, top, bottom), em pontos.
        """
        self.nome_arquivo = nome_arquivo
        self.formato_pagina = formato_pagina
        self.width, self.height = formato_pagina

        self.margin_left, self.margin_right, self.margin_top, self.margin_bottom = margins
        self.c = canvas.Canvas(nome_arquivo, pagesize=formato_pagina)

        self.cursor_y = self.height - self.margin_top
        self.initial_cursor_y = self.cursor_y

        self.background_color = None
        self.background_image = None

        self.cabecalho_imagem = None
        self.cabecalho_altura = None
        self.cabecalho_alinhamento = "left"

        self.rodape_imagem = None
        self.rodape_altura = None
        self.rodape_alinhamento = "left"

        try:
            from PIL import Image
            self._PIL_Image = Image
        except ImportError:
            self._PIL_Image = None

        self._draw_static_elements()

    # ---------------------------------------------------------------------
    # Helpers internos
    # ---------------------------------------------------------------------
    def _to_alignment(self, align: str) -> int:
        """Converte alinhamento textual para constante do ReportLab.

        Args:
            align: Valor textual entre ``left``, ``center``, ``right`` e
                ``justify``.

        Returns:
            Constante de alinhamento compativel com ParagraphStyle.
        """
        align_map = {
            "left": TA_LEFT,
            "center": TA_CENTER,
            "right": TA_RIGHT,
            "justify": TA_JUSTIFY,
        }
        return align_map.get(str(align).lower(), TA_LEFT)

    def _to_table_alignment(self, align: str) -> str:
        """Converte alinhamento textual para alinhamento de tabela.

        Args:
            align: Valor textual entre ``left``, ``center``, ``right`` e
                ``justify``.

        Returns:
            String de alinhamento compativel com TableStyle.
        """
        align_map = {
            "left": "LEFT",
            "center": "CENTER",
            "right": "RIGHT",
            "justify": "JUSTIFY",
        }
        return align_map.get(str(align).lower(), "LEFT")

    def _normalize_list(self, value: Any, total: int, default: Any) -> List[Any]:
        """Normaliza um valor escalar para lista.

        Args:
            value: Valor unico ou lista de valores.
            total: Quantidade final desejada.
            default: Valor padrao quando ``value`` for ``None``.

        Returns:
            Lista com ``total`` elementos.
        """
        if isinstance(value, list):
            return value
        if value is None:
            return [default] * total
        return [value] * total

    def _resolve_x_position(self, largura: float, align: str) -> float:
        """Calcula a posicao horizontal para um elemento.

        Args:
            largura: Largura do elemento em pontos.
            align: Alinhamento horizontal desejado.

        Returns:
            Coordenada X do inicio do elemento.
        """
        align = str(align).lower()
        if align == "left":
            return self.margin_left
        if align == "center":
            return (self.width - largura) / 2
        if align == "right":
            return self.width - largura - self.margin_right
        return self.margin_left

    def _build_paragraph_style(
        self,
        font: str = "Helvetica",
        font_size: int = 12,
        color: str = "#000000",
        align: str = "left",
        leading: Optional[float] = None,
        bold: bool = False,
        italic: bool = False,
        paragraph_style_name: str = "custom_style",
    ) -> ParagraphStyle:
        """Monta um ``ParagraphStyle`` padrao para textos.

        Args:
            font: Nome base da fonte.
            font_size: Tamanho da fonte.
            color: Cor do texto em hexadecimal.
            align: Alinhamento do paragrafo.
            leading: Espacamento entre linhas em pontos.
            bold: Indica se o texto deve usar negrito.
            italic: Indica se o texto deve usar italico.
            paragraph_style_name: Nome interno do estilo.

        Returns:
            Objeto ``ParagraphStyle`` configurado.
        """
        style = ParagraphStyle(
            name=paragraph_style_name,
            parent=getSampleStyleSheet()["Normal"],
            fontName=font,
            fontSize=font_size,
            leading=leading if leading is not None else font_size * 1.3,
            textColor=HexColor(color),
            alignment=self._to_alignment(align),
        )

        if bold and italic:
            style.fontName = f"{font}-BoldOblique"
        elif bold:
            style.fontName = f"{font}-Bold"
        elif italic:
            style.fontName = f"{font}-Oblique"

        return style

    def _draw_table(
        self,
        table: Table,
        table_align: str = "left",
        spacing_after: float = 10,
        spacing_before: float = 0,
    ) -> None:
        """Desenha uma tabela com quebra automatica de pagina.

        A tabela e renderizada a partir da posicao atual do cursor, respeitando
        margens, elementos textuais ja inseridos na pagina e espacamentos antes
        e depois da tabela. Quando nao houver altura suficiente, a tabela e
        dividida automaticamente por linha e o cabecalho e repetido nas paginas
        subsequentes quando configurado na propria ``Table``. Nas continuacoes,
        a secao da tabela reinicia com o mesmo afastamento vertical em relacao
        ao topo util observado na primeira pagina dessa tabela, mesmo quando o
        elemento textual que antecede a tabela nao existe nas paginas seguintes.

        Args:
            table: Tabela pronta para ser renderizada.
            table_align: Alinhamento externo da tabela.
            spacing_after: Espaco apos a tabela, em pontos.
            spacing_before: Espaco antes da tabela, em pontos.
        """
        self.cursor_y -= spacing_before
        available_width = self.width - self.margin_left - self.margin_right
        remaining_table = table

        initial_table_cursor_y = self.cursor_y
        continuation_offset = max(0, self.initial_cursor_y - initial_table_cursor_y)

        while True:
            available_height = self.cursor_y - self.margin_bottom
            if available_height <= 0:
                self.new_page()
                self.cursor_y = max(self.margin_bottom, self.initial_cursor_y - continuation_offset)
                continue

            parts = remaining_table.split(available_width, available_height)
            if not parts:
                self.new_page()
                self.cursor_y = max(self.margin_bottom, self.initial_cursor_y - continuation_offset)
                continue

            table_part = parts[0]
            largura, altura = table_part.wrapOn(self.c, available_width, available_height)
            table_x = self._resolve_x_position(largura, table_align)
            table_part.drawOn(self.c, table_x, self.cursor_y - altura)
            self.cursor_y -= altura

            if len(parts) == 1:
                break

            remaining_table = parts[1]
            self.new_page()
            self.cursor_y = max(self.margin_bottom, self.initial_cursor_y - continuation_offset)

        self.cursor_y -= spacing_after

    def _coerce_color(self, value: Any, default: Any = colors.white) -> Any:
        """Converte valor para cor compativel com ReportLab.

        Args:
            value: Cor em objeto do ReportLab, string hexadecimal ou ``None``.
            default: Valor padrao quando ``value`` for ``None``.

        Returns:
            Cor compativel com as APIs do ReportLab.
        """
        if value is None:
            return default
        if isinstance(value, str):
            return HexColor(value)
        return value

    # ---------------------------------------------------------------------
    # Elementos de pagina
    # ---------------------------------------------------------------------
    def set_background_color(self, color_hex: str, apply_now: bool = True) -> None:
        """Define uma cor de fundo para a pagina atual.

        Args:
            color_hex: Cor em hexadecimal.
            apply_now: Indica se o fundo deve ser redesenhado imediatamente.
        """
        self.background_color = HexColor(color_hex)
        if apply_now:
            self._draw_background()

    def set_background_image(self, image_path: str) -> None:
        """Define uma imagem de fundo para a pagina atual.

        Args:
            image_path: Caminho da imagem de fundo.
        """
        self.background_image = image_path
        self._draw_background()

    def _draw_background(self) -> None:
        """Desenha o fundo configurado na pagina atual."""
        if self.background_color:
            self.c.setFillColor(self.background_color)
            self.c.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        if self.background_image and os.path.isfile(self.background_image):
            self.c.drawImage(self.background_image, 0, 0, width=self.width, height=self.height)

    def set_cabecalho_imagem(self, image_path: str, height: Optional[float] = None, align: str = "left") -> None:
        """Configura a imagem de cabecalho.

        Args:
            image_path: Caminho da imagem.
            height: Altura do cabecalho em pontos.
            align: Alinhamento horizontal da imagem.
        """
        self.cabecalho_imagem = image_path
        self.cabecalho_altura = height
        self.cabecalho_alinhamento = align
        self._draw_header()

    def set_rodape_imagem(self, image_path: str, height: Optional[float] = None, align: str = "left") -> None:
        """Configura a imagem de rodape.

        Args:
            image_path: Caminho da imagem.
            height: Altura do rodape em pontos.
            align: Alinhamento horizontal da imagem.
        """
        self.rodape_imagem = image_path
        self.rodape_altura = height
        self.rodape_alinhamento = align
        self._draw_footer()

    def _draw_header(self) -> None:
        """Desenha o cabecalho configurado na pagina atual."""
        if not self.cabecalho_imagem:
            return

        img = ImageReader(self.cabecalho_imagem)
        iw, ih = img.getSize()
        h = self.cabecalho_altura if self.cabecalho_altura else 1.5 * cm
        w = (iw / ih) * h
        x = self._resolve_x_position(w, self.cabecalho_alinhamento)
        y = self.height - h

        self.c.drawImage(self.cabecalho_imagem, x, y, width=w, height=h)
        self.margin_top = max(self.margin_top, h + 0.5 * cm)
        self.cursor_y = self.height - self.margin_top
        self.initial_cursor_y = self.cursor_y

    def _draw_footer(self) -> None:
        """Desenha o rodape configurado na pagina atual."""
        if not self.rodape_imagem:
            return

        img = ImageReader(self.rodape_imagem)
        iw, ih = img.getSize()
        h = self.rodape_altura if self.rodape_altura else 1.5 * cm
        w = (iw / ih) * h
        x = self._resolve_x_position(w, self.rodape_alinhamento)

        self.c.drawImage(self.rodape_imagem, x, 0, width=w, height=h)
        self.margin_bottom = max(self.margin_bottom, h + 0.5 * cm)

    def _draw_static_elements(self) -> None:
        """Desenha os elementos fixos da pagina atual."""
        self._draw_background()
        self._draw_header()
        self._draw_footer()

    # ---------------------------------------------------------------------
    # Fluxo e pagina
    # ---------------------------------------------------------------------
    def spacer(self, px: float) -> None:
        """Move o cursor vertical para baixo em pontos.

        Args:
            px: Quantidade de pontos a deslocar.
        """
        self.cursor_y -= px

    def spacer_cm(self, value_cm: float) -> None:
        """Move o cursor vertical para baixo em centimetros.

        Args:
            value_cm: Quantidade em centimetros.
        """
        self.cursor_y -= value_cm * cm

    def _check_page_space(self, required_height: float) -> None:
        """Verifica se ha espaco suficiente para o proximo elemento.

        Args:
            required_height: Altura necessaria em pontos.
        """
        if self.cursor_y - required_height < self.margin_bottom:
            self.new_page()

    def new_page(self) -> None:
        """Cria uma nova pagina e reconstroi os elementos fixos."""
        self.c.showPage()
        self.cursor_y = self.height - self.margin_top
        self.initial_cursor_y = self.cursor_y
        self._draw_static_elements()

    # ---------------------------------------------------------------------
    # Texto
    # ---------------------------------------------------------------------
    def add_text(
        self,
        text: str,
        size: int = 12,
        font: str = "Helvetica",
        color: str = "#000000",
        x: Optional[float] = None,
        y: Optional[float] = None,
    ) -> None:
        """Adiciona texto simples ao documento.

        Quando ``x`` e ``y`` sao informados, o texto e desenhado em coordenadas
        absolutas. Quando omitidos, o texto e renderizado via ``add_paragraph``
        para manter um fluxo de texto unificado.

        Args:
            text: Conteudo textual a ser desenhado.
            size: Tamanho da fonte.
            font: Nome da fonte.
            color: Cor do texto em hexadecimal.
            x: Coordenada X absoluta.
            y: Coordenada Y absoluta.
        """
        if x is not None and y is not None:
            self.c.setFont(font, size)
            self.c.setFillColor(HexColor(color))
            self.c.drawString(x, y, text)
            return

        self.add_paragraph(
            text=text,
            font=font,
            font_size=size,
            color=color,
            paragraph_space_after=size * 0.3,
        )

    def add_paragraph(
        self,
        text: str,
        width: Optional[float] = None,
        font: str = "Helvetica",
        font_size: int = 12,
        color: str = "#000000",
        leading: Optional[float] = None,
        leading_cm: Optional[float] = None,
        align: str = "left",
        paragraph_space_after: float = 10,
        x_offset: float = 0,
        y_offset: float = 0,
        bold: bool = False,
        italic: bool = False,
    ) -> None:
        """Adiciona um paragrafo com quebra automatica de linha.

        Args:
            text: Conteudo do paragrafo. Aceita marcacao basica do ReportLab,
                como ``<b>`` e ``<i>``.
            width: Largura util do paragrafo em pontos. Quando omitida,
                utiliza a largura interna da pagina.
            font: Nome base da fonte.
            font_size: Tamanho da fonte.
            color: Cor do texto em hexadecimal.
            leading: Espacamento entre linhas em pontos.
            leading_cm: Espacamento entre linhas em centimetros.
            align: Alinhamento do texto.
            paragraph_space_after: Espaco apos o paragrafo, em pontos.
            x_offset: Deslocamento horizontal adicional.
            y_offset: Deslocamento vertical adicional.
            bold: Aplica negrito global no estilo.
            italic: Aplica italico global no estilo.
        """
        if leading_cm is not None:
            leading = leading_cm * cm

        width = width if width is not None else self.width - self.margin_left - self.margin_right
        style = self._build_paragraph_style(
            font=font,
            font_size=font_size,
            color=color,
            align=align,
            leading=leading,
            bold=bold,
            italic=italic,
        )

        paragraph = Paragraph(text, style)
        usable_height = self.cursor_y - self.margin_bottom
        _, altura = paragraph.wrap(width, usable_height)
        self._check_page_space(altura + y_offset)

        draw_x = self.margin_left + x_offset
        draw_y = self.cursor_y - altura - y_offset
        paragraph.drawOn(self.c, draw_x, draw_y)
        self.cursor_y = draw_y - paragraph_space_after

    def formated_text(
        self,
        text: str,
        font_size: int = 12,
        bold: bool = False,
        italic: bool = False,
        align: str = "left",
        x_offset: float = 0,
        y_offset: float = 0,
        leading: Optional[float] = None,
    ) -> None:
        """Adiciona texto formatado reaproveitando ``add_paragraph``.

        Args:
            text: Conteudo do texto. Aceita tags como ``<b>``, ``<i>`` e
                ``<super>``.
            font_size: Tamanho da fonte.
            bold: Aplica negrito ao estilo base.
            italic: Aplica italico ao estilo base.
            align: Alinhamento do texto.
            x_offset: Deslocamento horizontal adicional.
            y_offset: Deslocamento vertical adicional.
            leading: Espacamento entre linhas em pontos.
        """
        self.add_paragraph(
            text=text,
            font_size=font_size,
            bold=bold,
            italic=italic,
            align=align,
            x_offset=x_offset,
            y_offset=y_offset,
            leading=leading,
            paragraph_space_after=8,
        )

    def add_text_move(
        self,
        text: str,
        x_offset: float,
        y_offset: float,
        font: str = "Helvetica",
        size: int = 12,
        color: str = "#000000",
        italic: bool = False,
        superscript: bool = False,
        subscript: bool = False,
        superscript_offset: float = 4,
        subscript_offset: float = 3,
    ) -> None:
        """Adiciona texto em posicao absoluta com ajustes verticais.

        Args:
            text: Conteudo do texto.
            x_offset: Coordenada X a partir da origem do canvas.
            y_offset: Coordenada Y medida a partir do topo da pagina.
            font: Nome base da fonte.
            size: Tamanho da fonte.
            color: Cor do texto em hexadecimal.
            italic: Indica uso de italico.
            superscript: Aplica deslocamento de sobrescrito.
            subscript: Aplica deslocamento de subscrito.
            superscript_offset: Ajuste vertical do sobrescrito.
            subscript_offset: Ajuste vertical do subscrito.
        """
        font_to_use = f"{font}-Oblique" if italic else font
        self.c.setFont(font_to_use, size)
        self.c.setFillColor(HexColor(color))

        x = x_offset
        y = self.height - y_offset

        if superscript:
            y += superscript_offset
        elif subscript:
            y -= subscript_offset

        self.c.drawString(x, y, text)

    # ---------------------------------------------------------------------
    # Imagens e figuras
    # ---------------------------------------------------------------------
    def add_image(
        self,
        image_path: str,
        width: Optional[float] = None,
        height: Optional[float] = None,
        x_offset: Optional[float] = None,
        y_offset: Optional[float] = None,
    ) -> None:
        """Adiciona uma imagem a partir de um caminho de arquivo.

        Args:
            image_path: Caminho da imagem.
            width: Largura final em pontos.
            height: Altura final em pontos.
            x_offset: Coordenada X a partir da origem do canvas.
            y_offset: Coordenada Y medida a partir do topo da página.
        """

        if image_path is None or not os.path.isfile(image_path):
            # Asset ausente — pula silenciosamente em vez de crashar o relatório
            return

        img = Image.open(image_path).convert("RGBA")

        # Corrige PNG com transparência para evitar fundo preto
        if img.mode == "RGBA":
            background = Image.new("RGBA", img.size, (255, 255, 255, 255))
            background.alpha_composite(img)
            img = background.convert("RGB")
        else:
            img = img.convert("RGB")

        iw, ih = img.size

        if width and not height:
            height = (ih / iw) * width
        elif height and not width:
            width = (iw / ih) * height
        elif width is None and height is None:
            width = self.width - self.margin_left - self.margin_right
            height = (ih / iw) * width

        # Posição padrão: fluxo normal do documento
        x = self.margin_left if x_offset is None else x_offset

        if y_offset is None:
            self._check_page_space(height + 10)
            y = self.cursor_y - height
            self.cursor_y -= height + 10
        else:
            # y_offset é medido a partir do topo da página
            y = self.height - y_offset - height

        self.c.drawInlineImage(
            img,
            x,
            y,
            width=width,
            height=height,
        )

    def add_figure(
        self,
        fig: Any,
        width_cm: Optional[float] = None,
        height_cm: Optional[float] = None,
        align: str = "left",
    ) -> None:
        """Insere uma figura ou imagem no PDF.

        Aceita ``matplotlib.figure.Figure``, ``io.BytesIO``, ``bytes``, caminho
        de arquivo ou ``PIL.Image``.

        Args:
            fig: Objeto da figura ou origem da imagem.
            width_cm: Largura desejada em centimetros.
            height_cm: Altura desejada em centimetros.
            align: Alinhamento horizontal da figura.

        Raises:
            TypeError: Quando o tipo de ``fig`` nao e suportado.
            ValueError: Quando dimensoes ou alinhamento sao invalidos.
        """
        if width_cm is not None and not isinstance(width_cm, (int, float)):
            raise TypeError("width_cm deve ser numerico ou None.")
        if height_cm is not None and not isinstance(height_cm, (int, float)):
            raise TypeError("height_cm deve ser numerico ou None.")
        if align not in ("left", "center", "right"):
            raise ValueError('align deve ser "left", "center" ou "right".')

        buffer = None
        image_source = None

        try:
            if hasattr(fig, "savefig"):
                buffer = io.BytesIO()
                fig.savefig(buffer, format="png", dpi=300, bbox_inches="tight")
                buffer.seek(0)
                image_source = buffer
            elif isinstance(fig, io.BytesIO):
                fig.seek(0)
                image_source = fig
            elif isinstance(fig, (bytes, bytearray)):
                buffer = io.BytesIO(fig)
                buffer.seek(0)
                image_source = buffer
            elif isinstance(fig, (str, os.PathLike)):
                image_source = fig
            elif self._PIL_Image is not None and isinstance(fig, self._PIL_Image.Image):
                buffer = io.BytesIO()
                if fig.mode not in ("RGB", "RGBA"):
                    fig = fig.convert("RGB")
                fig.save(buffer, format="PNG")
                buffer.seek(0)
                image_source = buffer
            else:
                raise TypeError(
                    "A figura deve ser um Figure do matplotlib, io.BytesIO, bytes, caminho de arquivo ou PIL.Image.Image."
                )

            img = ImageReader(image_source)
            orig_w, orig_h = img.getSize()
            if orig_w <= 0 or orig_h <= 0:
                raise ValueError("A imagem possui dimensoes invalidas.")

            width = width_cm * cm if width_cm is not None else None
            height = height_cm * cm if height_cm is not None else None

            if width is not None and height is None:
                height = orig_h * (width / orig_w)
            elif height is not None and width is None:
                width = orig_w * (height / orig_h)
            elif width is None and height is None:
                width = self.width - self.margin_left - self.margin_right
                height = orig_h * (width / orig_w)

            x = self._resolve_x_position(width, align)
            self._check_page_space(height)
            self.c.drawImage(
                img,
                x,
                self.cursor_y - height,
                width=width,
                height=height,
                preserveAspectRatio=True,
                mask="auto",
            )
            self.cursor_y -= height + 10
        finally:
            if buffer is not None:
                buffer.close()

    # ---------------------------------------------------------------------
    # Tabelas
    # ---------------------------------------------------------------------
    
    def add_dataframe(
        self,
        df,
        col_widths: Optional[Sequence[float]] = None,
        font: str = "Helvetica",
        font_size: int = 10,
        header_font: str = "Helvetica-Bold",
        header_font_size: int = 11,
        text_color=colors.black,
        header_text_color=colors.white,
        header_background=colors.darkblue,
        row_background=None,
        text_align: str = "left",
        table_align: str = "left",
        line_spacing: Optional[float] = None,
        line_spacing_cm: Optional[float] = None,
        cond_col: Optional[str] = None,
        cond_values: Optional[Sequence[Any]] = None,
        cond_colors: Optional[Sequence[Any]] = None,
        fmt: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Adiciona uma tabela a partir de um DataFrame com quebra automatica.

        Este metodo concentra a geracao de tabelas simples e condicionais.
        Quando a tabela for continuada em paginas seguintes, o bloco reinicia
        no mesmo afastamento vertical da primeira pagina da propria tabela.
        O parametro ``fmt`` permite padronizar configuracoes em uma estrutura
        unica, semelhante ao uso do parametro ``fmt`` em outros metodos.

        Chaves aceitas em ``fmt``:
            - ``fonte``: fonte do corpo.
            - ``fonte_cabecalho``: fonte do cabecalho.
            - ``tamanho_valores``: tamanho do corpo.
            - ``tamanho_cabecalhos``: tamanho do cabecalho.
            - ``nomes_colunas``: lista ou dicionario com nomes exibidos.
            - ``cor_texto``: cor do corpo.
            - ``cor_texto_cabecalho``: cor do texto do cabecalho.
            - ``cor_fundo_cabecalho``: cor de fundo do cabecalho.
            - ``cor_fundo_linhas``: cor zebrada para linhas pares.
            - ``alinhamento_texto``: alinhamento interno das celulas.
            - ``alinhamento_tabela``: alinhamento externo da tabela.
            - ``entre_linhas``: leading interno.
            - ``larguras_colunas``: larguras das colunas.
            - ``espacamento_antes``: espacamento antes da tabela.
            - ``espacamento_apos``: espacamento apos a tabela.

        Args:
            df: DataFrame de origem.
            col_widths: Largura de colunas em pontos.
            font: Fonte do corpo.
            font_size: Tamanho da fonte do corpo.
            header_font: Fonte do cabecalho.
            header_font_size: Tamanho da fonte do cabecalho.
            text_color: Cor do texto do corpo.
            header_text_color: Cor do texto do cabecalho.
            header_background: Cor de fundo do cabecalho.
            row_background: Cor alternada das linhas.
            text_align: Alinhamento interno das celulas.
            table_align: Alinhamento externo da tabela.
            line_spacing: Espacamento entre linhas em pontos.
            line_spacing_cm: Espacamento entre linhas em centimetros.
            cond_col: Nome da coluna usada para coloracao condicional.
            cond_values: Valores que ativam a condicao.
            cond_colors: Cores aplicadas para cada valor condicional.
            fmt: Estrutura de configuracao complementar.
        """
        fmt = fmt or {}
        font = fmt.get("fonte", font)
        header_font = fmt.get("fonte_cabecalho", header_font)
        font_size = fmt.get("tamanho_valores", font_size)
        header_font_size = fmt.get("tamanho_cabecalhos", header_font_size)
        text_color = self._coerce_color(fmt.get("cor_texto", text_color), text_color)
        header_text_color = self._coerce_color(fmt.get("cor_texto_cabecalho", header_text_color), header_text_color)
        header_background = self._coerce_color(fmt.get("cor_fundo_cabecalho", header_background), header_background)
        row_background = self._coerce_color(fmt.get("cor_fundo_linhas", row_background), row_background) if fmt.get("cor_fundo_linhas", row_background) is not None else row_background
        text_align = fmt.get("alinhamento_texto", text_align)
        table_align = fmt.get("alinhamento_tabela", table_align)
        col_widths = fmt.get("larguras_colunas", col_widths)
        spacing_before = fmt.get("espacamento_antes", 0)
        spacing_after = fmt.get("espacamento_apos", 10)
        display_columns = fmt.get("nomes_colunas")

        if display_columns is None:
            source_columns = list(df.columns)
            header_labels = source_columns
        elif isinstance(display_columns, dict):
            source_columns = list(display_columns.keys())
            header_labels = list(display_columns.values())
        else:
            source_columns = list(display_columns)
            header_labels = source_columns

        missing_columns = [col for col in source_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Colunas nao encontradas no DataFrame: {missing_columns}")

        if line_spacing_cm is not None:
            line_spacing = line_spacing_cm * cm
        if fmt.get("entre_linhas") is not None:
            line_spacing = fmt.get("entre_linhas")
        if line_spacing is None:
            line_spacing = font_size * 1.3

        data = [header_labels] + df[source_columns].astype(str).values.tolist()
        if col_widths is None:
            col_widths = [None] * len(header_labels)

        table = Table(data, colWidths=col_widths, repeatRows=1, splitByRow=1)
        text_alignment = self._to_table_alignment(text_align)
        style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), header_background),
            ("TEXTCOLOR", (0, 0), (-1, 0), header_text_color),
            ("FONTNAME", (0, 0), (-1, 0), header_font),
            ("FONTSIZE", (0, 0), (-1, 0), header_font_size),
            ("TEXTCOLOR", (0, 1), (-1, -1), text_color),
            ("FONTNAME", (0, 1), (-1, -1), font),
            ("FONTSIZE", (0, 1), (-1, -1), font_size),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), text_alignment),
            ("LEADING", (0, 0), (-1, -1), line_spacing),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])

        if row_background is not None:
            for row in range(1, len(data)):
                if row % 2 == 0:
                    style.add("BACKGROUND", (0, row), (-1, row), row_background)

        if cond_col is not None and cond_values and cond_colors and cond_col in df.columns:
            color_map = {str(valor): self._coerce_color(cor) for valor, cor in zip(cond_values, cond_colors)}
            col_idx = source_columns.index(cond_col)
            for row_idx, valor in enumerate(df[cond_col].astype(str).tolist(), start=1):
                if valor in color_map:
                    style.add("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), color_map[valor])

        table.setStyle(style)
        self._draw_table(
            table,
            table_align=table_align,
            spacing_after=spacing_after,
            spacing_before=spacing_before,
        )

    def add_dataframe_cond(self, df, **kwargs) -> None:
        """Mantem compatibilidade para tabelas com coloracao condicional.

        Este metodo foi unificado internamente com ``add_dataframe`` e atua
        apenas como um alias de compatibilidade, preservando o mesmo suporte a
        quebra automatica de pagina, repeticao de cabecalho, espacamentos e
        reinicio consistente da tabela nas paginas subsequentes.

        Args:
            df: DataFrame de origem.
            **kwargs: Parametros encaminhados para ``add_dataframe``.
        """
        self.add_dataframe(df, **kwargs)

    def custom_table(
        self,
        headers: Sequence[str],
        data: Sequence[Sequence[Any]],
        col_widths: Optional[Sequence[float]] = None,
        header_font: str = "Helvetica-Bold",
        header_font_size: int = 11,
        header_colors: Optional[Sequence[Any]] = None,
        default_header_text_color=colors.white,
        default_header_background=colors.darkblue,
        row_font: str = "Helvetica",
        row_font_size: int = 10,
        row_colors: Optional[Sequence[Any]] = None,
        default_row_text_color=colors.black,
        default_row_background=None,
        zebra: bool = False,
        align: str = "left",
        cell_align: str = "left",
        header_align: str = "center",
        padding: float = 6,
        spacing_after: float = 12,
        spacing_before: float = 0,
    ) -> None:
        """Adiciona uma tabela customizada a partir de listas.

        A tabela e renderizada com quebra automatica de pagina e repeticao do
        cabecalho nas paginas seguintes, respeitando margens, cursor atual e
        espacamentos configurados antes e depois da tabela. Nas continuacoes,
        a secao seguinte inicia com o mesmo afastamento vertical observado na
        primeira pagina dessa tabela.

        Args:
            headers: Cabecalhos da tabela.
            data: Dados do corpo da tabela.
            col_widths: Larguras das colunas.
            header_font: Fonte do cabecalho.
            header_font_size: Tamanho da fonte do cabecalho.
            header_colors: Cores individuais do fundo do cabecalho.
            default_header_text_color: Cor padrao do texto do cabecalho.
            default_header_background: Cor padrao do fundo do cabecalho.
            row_font: Fonte do corpo.
            row_font_size: Tamanho da fonte do corpo.
            row_colors: Cores individuais de fundo para o corpo.
            default_row_text_color: Cor padrao do texto do corpo.
            default_row_background: Cor padrao de fundo do corpo.
            zebra: Ativa alternancia visual de linhas.
            align: Alinhamento externo da tabela.
            cell_align: Alinhamento interno das celulas do corpo.
            header_align: Alinhamento interno do cabecalho.
            padding: Espacamento interno das celulas.
            spacing_after: Espaco apos a tabela.
            spacing_before: Espaco antes da tabela.
        """
        table_data = [list(headers)] + [list(row) for row in data]
        if col_widths is None:
            col_widths = [None] * len(headers)

        table = Table(table_data, colWidths=col_widths, repeatRows=1, splitByRow=1)
        style = TableStyle([])

        for col_idx, _ in enumerate(headers):
            bg = default_header_background
            fg = default_header_text_color
            if header_colors and col_idx < len(header_colors):
                bg = header_colors[col_idx]
            style.add("BACKGROUND", (col_idx, 0), (col_idx, 0), bg)
            style.add("TEXTCOLOR", (col_idx, 0), (col_idx, 0), fg)
            style.add("FONTNAME", (col_idx, 0), (col_idx, 0), header_font)
            style.add("FONTSIZE", (col_idx, 0), (col_idx, 0), header_font_size)

        style.add("ALIGN", (0, 0), (-1, 0), self._to_table_alignment(header_align))

        for row_idx in range(1, len(table_data)):
            for col_idx in range(len(headers)):
                bg = default_row_background
                fg = default_row_text_color
                if zebra and row_idx % 2 == 0:
                    bg = colors.whitesmoke
                if row_colors and col_idx < len(row_colors):
                    bg = row_colors[col_idx]
                style.add("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), bg)
                style.add("TEXTCOLOR", (col_idx, row_idx), (col_idx, row_idx), fg)
                style.add("FONTNAME", (col_idx, row_idx), (col_idx, row_idx), row_font)
                style.add("FONTSIZE", (col_idx, row_idx), (col_idx, row_idx), row_font_size)

        style.add("ALIGN", (0, 1), (-1, -1), self._to_table_alignment(cell_align))
        style.add("VALIGN", (0, 0), (-1, -1), "MIDDLE")
        style.add("GRID", (0, 0), (-1, -1), 0.5, colors.grey)
        style.add("LEFTPADDING", (0, 0), (-1, -1), padding)
        style.add("RIGHTPADDING", (0, 0), (-1, -1), padding)
        style.add("TOPPADDING", (0, 0), (-1, -1), padding)
        style.add("BOTTOMPADDING", (0, 0), (-1, -1), padding)

        table.setStyle(style)
        self._draw_table(
            table,
            table_align=align,
            spacing_after=spacing_after,
            spacing_before=spacing_before,
        )

    # ---------------------------------------------------------------------
    # Elementos graficos e composicao
    # ---------------------------------------------------------------------
    def set_margin_color(
        self,
        color_hex: str,
        left: bool = False,
        right: bool = False,
        top: bool = False,
        bottom: bool = False,
    ) -> None:
        """Pinta as areas de margem da pagina atual.

        Args:
            color_hex: Cor em hexadecimal.
            left: Ativa margem esquerda.
            right: Ativa margem direita.
            top: Ativa margem superior.
            bottom: Ativa margem inferior.
        """
        color = HexColor(color_hex)
        self.c.setFillColor(color)

        if left:
            self.c.rect(0, 0, self.margin_left, self.height, fill=1, stroke=0)
        if right:
            self.c.rect(self.width - self.margin_right, 0, self.margin_right, self.height, fill=1, stroke=0)
        if top:
            self.c.rect(0, self.height - self.margin_top, self.width, self.margin_top, fill=1, stroke=0)
        if bottom:
            self.c.rect(0, 0, self.width, self.margin_bottom, fill=1, stroke=0)

    def insert_external_pdf(
        self,
        external_pdf_path: str,
        insert_at_page: int = 0,
        output_path: Optional[str] = None,
    ) -> str:
        """Insere paginas de um PDF externo dentro do PDF atual.

        Args:
            external_pdf_path: Caminho do PDF a ser inserido.
            insert_at_page: Indice da pagina onde o PDF externo sera inserido.
            output_path: Caminho do arquivo final. Quando omitido, sobrescreve
                o arquivo principal.

        Returns:
            Caminho do PDF final gerado.
        """
        try:
            self.save()
        except Exception:
            pass

        original_pdf_path = self.nome_arquivo
        final_path = output_path if output_path else original_pdf_path

        main_reader = PdfReader(original_pdf_path)
        ext_reader = PdfReader(external_pdf_path)
        writer = PdfWriter()

        total_pages = len(main_reader.pages)
        insert_at_page = max(0, min(insert_at_page, total_pages))

        for i in range(insert_at_page):
            writer.add_page(main_reader.pages[i])
        for page in ext_reader.pages:
            writer.add_page(page)
        for i in range(insert_at_page, total_pages):
            writer.add_page(main_reader.pages[i])

        with open(final_path, "wb") as file_obj:
            writer.write(file_obj)

        return final_path

    def kpi_cards(
        self,
        titulos,
        valores,
        rotulos=None,
        y_cm: Optional[float] = None,
        largura_cm: float = 4,
        altura_cm: float = 2.5,
        espacamento_cm: float = 1,
        fontes=None,
        tamanhos=None,
        cores_titulo="#444444",
        cores_valor="#000000",
        cores_rotulo="#666666",
        cores_fundo="#FFFFFF",
        cores_borda="#DDDDDD",
        border_radius_cm: float = 0.3,
        icon_paths=None,
        icon_pos: str = "left",
        icon_cm: float = 0.6,
        fmt: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Desenha uma grade de cards de indicadores.

        Args:
            titulos: Titulos dos cards.
            valores: Valores principais dos cards.
            rotulos: Subtitulos ou rotulos auxiliares.
            y_cm: Posicao inicial da linha de cards em centimetros.
            largura_cm: Largura de cada card.
            altura_cm: Altura de cada card.
            espacamento_cm: Espacamento entre cards.
            fontes: Fonte unica ou lista de fontes.
            tamanhos: Tamanho unico ou lista de tamanhos.
            cores_titulo: Cor do titulo por card ou unica.
            cores_valor: Cor do valor por card ou unica.
            cores_rotulo: Cor do rotulo por card ou unica.
            cores_fundo: Cor de fundo por card ou unica.
            cores_borda: Cor da borda por card ou unica.
            border_radius_cm: Arredondamento das bordas.
            icon_paths: Caminhos de icones.
            icon_pos: Posicao do icone dentro do card.
            icon_cm: Tamanho do icone em centimetros.
            fmt: Estrutura complementar de configuracao.
        """
        if not isinstance(titulos, list):
            titulos = [titulos]
        if not isinstance(valores, list):
            valores = [valores]

        total = len(titulos)
        if rotulos is None:
            rotulos = [""] * total
        elif not isinstance(rotulos, list):
            rotulos = [rotulos] * total

        fmt = fmt or {}
        largura_cm = fmt.get("largura", largura_cm)
        altura_cm = fmt.get("altura", altura_cm)
        espacamento_cm = fmt.get("espacamento", espacamento_cm)
        border_radius_cm = fmt.get("border_radius", border_radius_cm)

        fonte_default = fmt.get("fonte", "Helvetica")
        tamanho_default = fmt.get("tamanho", 11)

        fontes = self._normalize_list(fontes, total, fonte_default)
        tamanhos = self._normalize_list(tamanhos, total, tamanho_default)
        cores_titulo = self._normalize_list(cores_titulo, total, "#444444")
        cores_valor = self._normalize_list(cores_valor, total, "#000000")
        cores_rotulo = self._normalize_list(cores_rotulo, total, "#666666")
        cores_fundo = self._normalize_list(cores_fundo, total, "#FFFFFF")
        cores_borda = self._normalize_list(cores_borda, total, "#DDDDDD")
        border_radius = self._normalize_list(border_radius_cm, total, border_radius_cm)
        icon_paths = self._normalize_list(icon_paths, total, None)

        largura = largura_cm * cm
        altura = altura_cm * cm
        espacamento = espacamento_cm * cm
        largura_util = self.width - self.margin_left - self.margin_right

        max_por_linha = int((largura_util + espacamento) // (largura + espacamento))
        max_por_linha = max(max_por_linha, 1)
        y_base = self.cursor_y if y_cm is None else self.height - (y_cm * cm)

        linha = 0
        coluna = 0

        for i in range(total):
            if coluna == 0:
                restantes = total - i
                cards_linha = min(max_por_linha, restantes)
                largura_total = (cards_linha * largura) + ((cards_linha - 1) * espacamento)
                offset_x = self.margin_left + (largura_util - largura_total) / 2

            x = offset_x + coluna * (largura + espacamento)
            y = y_base - (linha * (altura + espacamento))

            self.c.setFillColor(HexColor(cores_fundo[i]))
            self.c.setStrokeColor(HexColor(cores_borda[i]))
            self.c.roundRect(x, y - altura, largura, altura, border_radius[i] * cm, fill=1, stroke=1)

            self.c.setFillColor(HexColor(cores_titulo[i]))
            self.c.setFont(fontes[i], tamanhos[i])
            self.c.drawString(x + 10, y - 20, str(titulos[i]))

            self.c.setFillColor(HexColor(cores_valor[i]))
            self.c.setFont(fontes[i], tamanhos[i] + 6)
            self.c.drawString(x + 10, y - 40, str(valores[i]))

            self.c.setFillColor(HexColor(cores_rotulo[i]))
            self.c.setFont(fontes[i], tamanhos[i] - 1)
            self.c.drawString(x + 10, y - 60, str(rotulos[i]))

            if icon_paths[i]:
                icon_size = icon_cm * cm
                icon_x = x + largura - icon_size - 10 if icon_pos == "right" else x + 10
                icon_y = y - icon_size - 10
                self.c.drawImage(icon_paths[i], icon_x, icon_y, width=icon_size, height=icon_size, mask="auto")

            coluna += 1
            if coluna >= max_por_linha:
                coluna = 0
                linha += 1

        linhas = linha + 1
        self.cursor_y = y_base - linhas * (altura + espacamento)
    # ---------------------------------------------------------------------
    # New add_dataframe
    # ---------------------------------------------------------------------
    def new_add_dataframe(
    self,
    df,
    col_widths: Optional[Sequence[float]] = None,
    font: str = "Helvetica",
    font_size: int = 10,
    header_font: str = "Helvetica-Bold",
    header_font_size: int = 11,
    text_color=colors.black,
    header_text_color=colors.white,
    header_background=colors.darkblue,
    row_background=None,
    text_align: str = "left",
    table_align: str = "left",
    line_spacing: Optional[float] = None,
    line_spacing_cm: Optional[float] = None,
    cond_col: Optional[str] = None,
    cond_values: Optional[Sequence[Any]] = None,
    cond_colors: Optional[Sequence[Any]] = None,
    fmt: Optional[Dict[str, Any]] = None,
    auto_wrap: bool = True,
    ) -> None:
        """
        Adiciona uma tabela PDF a partir de um DataFrame utilizando.

        Este método cria uma tabela formatada com suporte a:
        - estilização de cabeçalhos;
        - cores condicionais;
        - alinhamento interno e externo;
        - zebra striping;
        - controle de espaçamento;
        - quebra automática de texto em células;
        - renomeação de colunas;
        - repetição automática do cabeçalho em múltiplas páginas.

        Quando ``auto_wrap=True``, textos longos são automaticamente
        quebrados dentro da célula utilizando ``Paragraph`` do ReportLab,
        aumentando a altura da linha conforme necessário sem ultrapassar
        os limites da coluna.

        Parameters
        ----------
        df : pandas.DataFrame
            DataFrame utilizado como origem da tabela.

        col_widths : Sequence[float], optional
            Lista contendo as larguras das colunas em pontos.

        font : str, default="Helvetica"
            Fonte utilizada nas células do corpo da tabela.

        font_size : int, default=10
            Tamanho da fonte do corpo da tabela.

        header_font : str, default="Helvetica-Bold"
            Fonte utilizada no cabeçalho.

        header_font_size : int, default=11
            Tamanho da fonte do cabeçalho.

        text_color : Color, default=colors.black
            Cor do texto das células.

        header_text_color : Color, default=colors.white
            Cor do texto do cabeçalho.

        header_background : Color, default=colors.darkblue
            Cor de fundo do cabeçalho.

        row_background : Color, optional
            Cor alternada aplicada às linhas pares da tabela.

        text_align : str, default="left"
            Alinhamento interno do conteúdo das células.

            Valores aceitos:
            - "left"
            - "center"
            - "right"
            - "justify"

        table_align : str, default="left"
            Alinhamento horizontal da tabela no PDF.

            Valores aceitos:
            - "left"
            - "center"
            - "right"

        line_spacing : float, optional
            Espaçamento entre linhas em pontos.

        line_spacing_cm : float, optional
            Espaçamento entre linhas em centímetros.
            Caso informado, sobrescreve ``line_spacing``.

        cond_col : str, optional
            Nome da coluna utilizada para coloração condicional.

        cond_values : Sequence[Any], optional
            Valores que ativam a coloração condicional.

        cond_colors : Sequence[Any], optional
            Cores aplicadas para cada valor condicional.

        fmt : dict, optional
            Dicionário de configuração complementar.

            Chaves suportadas:
            ------------------
            fonte : str
                Fonte do corpo.

            fonte_cabecalho : str
                Fonte do cabeçalho.

            tamanho_valores : int
                Tamanho da fonte do corpo.

            tamanho_cabecalhos : int
                Tamanho da fonte do cabeçalho.

            nomes_colunas : list | dict
                Renomeação de colunas exibidas.

            cor_texto : Color | str
                Cor do texto do corpo.

            cor_texto_cabecalho : Color | str
                Cor do texto do cabeçalho.

            cor_fundo_cabecalho : Color | str
                Cor de fundo do cabeçalho.

            cor_fundo_linhas : Color | str
                Cor alternada das linhas.

            alinhamento_texto : str
                Alinhamento interno das células.

            alinhamento_tabela : str
                Alinhamento externo da tabela.

            entre_linhas : float
                Leading interno das células.

            larguras_colunas : Sequence[float]
                Largura das colunas.

            espacamento_antes : float
                Espaço antes da tabela.

            espacamento_apos : float
                Espaço após a tabela.

            quebra_texto_automatica : bool
                Ativa quebra automática de texto em células.

        auto_wrap : bool, default=True
            Ativa quebra automática de texto em células utilizando
            ``Paragraph`` do ReportLab.

            Quando habilitado:
            - textos longos quebram automaticamente;
            - a altura da linha aumenta dinamicamente;
            - evita overflow horizontal.

        Raises
        ------
        ValueError
            Caso alguma coluna especificada em ``nomes_colunas`` não exista
            no DataFrame.

        Notes
        -----
        Para melhor funcionamento da quebra automática de texto,
        recomenda-se definir explicitamente ``col_widths``.

        Example
        -------
        ```python
        pdf.add_dataframe(
            df=df_maquinas,
            col_widths=[80, 220, 100],

            fmt={
                "quebra_texto_automatica": True,
                "cor_fundo_cabecalho": "#1F3A5F",
                "cor_fundo_linhas": "#F5F5F5",
            },

            cond_col="status",

            cond_values=["CRÍTICO", "OK"],

            cond_colors=[
                colors.red,
                colors.green,
            ],
        )
        ```
        """

        fmt = fmt or {}
        font = fmt.get("fonte", font)
        header_font = fmt.get("fonte_cabecalho", header_font)
        font_size = fmt.get("tamanho_valores", font_size)
        header_font_size = fmt.get("tamanho_cabecalhos", header_font_size)

        text_color = self._coerce_color(fmt.get("cor_texto", text_color), text_color)
        header_text_color = self._coerce_color(
            fmt.get("cor_texto_cabecalho", header_text_color),
            header_text_color,
        )
        header_background = self._coerce_color(
            fmt.get("cor_fundo_cabecalho", header_background),
            header_background,
        )

        row_background = (
            self._coerce_color(fmt.get("cor_fundo_linhas", row_background), row_background)
            if fmt.get("cor_fundo_linhas", row_background) is not None
            else row_background
        )

        text_align = fmt.get("alinhamento_texto", text_align)
        table_align = fmt.get("alinhamento_tabela", table_align)
        col_widths = fmt.get("larguras_colunas", col_widths)
        spacing_before = fmt.get("espacamento_antes", 0)
        spacing_after = fmt.get("espacamento_apos", 10)
        display_columns = fmt.get("nomes_colunas")
        auto_wrap = fmt.get("quebra_texto_automatica", auto_wrap)

        if display_columns is None:
            source_columns = list(df.columns)
            header_labels = source_columns
        elif isinstance(display_columns, dict):
            source_columns = list(display_columns.keys())
            header_labels = list(display_columns.values())
        else:
            source_columns = list(display_columns)
            header_labels = source_columns

        missing_columns = [col for col in source_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Colunas nao encontradas no DataFrame: {missing_columns}")

        if line_spacing_cm is not None:
            line_spacing = line_spacing_cm * cm

        if fmt.get("entre_linhas") is not None:
            line_spacing = fmt.get("entre_linhas")

        if line_spacing is None:
            line_spacing = font_size * 1.3

        if col_widths is None:
            col_widths = [None] * len(header_labels)

        if auto_wrap:
            from reportlab.platypus import Paragraph
            from reportlab.lib.styles import ParagraphStyle

            alignment_map = {
                "left": 0,
                "center": 1,
                "right": 2,
                "justify": 4,
            }

            paragraph_alignment = alignment_map.get(str(text_align).lower(), 0)

            body_style = ParagraphStyle(
                name="TableBody",
                fontName=font,
                fontSize=font_size,
                leading=line_spacing,
                textColor=text_color,
                alignment=paragraph_alignment,
                wordWrap="CJK",
            )

            header_style = ParagraphStyle(
                name="TableHeader",
                fontName=header_font,
                fontSize=header_font_size,
                leading=line_spacing,
                textColor=header_text_color,
                alignment=paragraph_alignment,
                wordWrap="CJK",
            )

            data = [
                [Paragraph(str(label), header_style) for label in header_labels]
            ] + [
                [Paragraph(str(value), body_style) for value in row]
                for row in df[source_columns].astype(str).values.tolist()
            ]
        else:
            data = [header_labels] + df[source_columns].astype(str).values.tolist()

        table = Table(data, colWidths=col_widths, repeatRows=1, splitByRow=1)

        text_alignment = self._to_table_alignment(text_align)

        style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), header_background),
            ("TEXTCOLOR", (0, 0), (-1, 0), header_text_color),
            ("FONTNAME", (0, 0), (-1, 0), header_font),
            ("FONTSIZE", (0, 0), (-1, 0), header_font_size),
            ("TEXTCOLOR", (0, 1), (-1, -1), text_color),
            ("FONTNAME", (0, 1), (-1, -1), font),
            ("FONTSIZE", (0, 1), (-1, -1), font_size),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), text_alignment),
            ("LEADING", (0, 0), (-1, -1), line_spacing),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])

        if row_background is not None:
            for row in range(1, len(data)):
                if row % 2 == 0:
                    style.add("BACKGROUND", (0, row), (-1, row), row_background)

        if cond_col is not None and cond_values and cond_colors and cond_col in df.columns:
            color_map = {
                str(valor): self._coerce_color(cor)
                for valor, cor in zip(cond_values, cond_colors)
            }

            col_idx = source_columns.index(cond_col)

            for row_idx, valor in enumerate(df[cond_col].astype(str).tolist(), start=1):
                if valor in color_map:
                    style.add(
                        "BACKGROUND",
                        (col_idx, row_idx),
                        (col_idx, row_idx),
                        color_map[valor],
                    )

        table.setStyle(style)

        self._draw_table(
            table,
            table_align=table_align,
            spacing_after=spacing_after,
            spacing_before=spacing_before,
        )
    # ---------------------------------------------------------------------
    # Persistencia
    # ---------------------------------------------------------------------
    def save(self) -> None:
        """Finaliza e salva o documento PDF."""
        self.c.save()
