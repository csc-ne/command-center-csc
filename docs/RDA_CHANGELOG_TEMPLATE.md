# RDA — Registro de Alterações para Integração

**Preencha este documento a cada entrega de nova versão.**
Ele permite que a equipe de integração (Command Center) aplique suas mudanças sem perder funcionalidades já existentes (SSO, Docker, paralelismo de queries, etc).

---

## Informações da Entrega

| Campo | Valor |
|---|---|
| **Desenvolvedor** | |
| **Email** | |
| **Data da entrega** | |
| **Versão anterior** | ex: report_0.3.py |
| **Versão nova** | ex: report_0.4.py |

---

## Arquivos Alterados

Liste **todos** os arquivos que foram modificados, criados ou removidos.
Marque com o tipo de alteração.

| Arquivo | Alterado | Novo | Removido | Descrição curta da mudança |
|---|:---:|:---:|:---:|---|
| `backend/report_X.Y.py` | | | | |
| `kernel/modulo_sql_rev2.py` | | | | |
| `kernel/modulo_grafico.py` | | | | |
| `kernel/modulo_consulta.py` | | | | |
| `kernel/modulo_estatistico.py` | | | | |
| `kernel/texts.py` | | | | |
| `pdf/modulo_pdf.py` | | | | |
| `labels/...` | | | | |
| `fonts/...` | | | | |
| `icons/...` | | | | |
| (adicione linhas conforme necessário) | | | | |

---

## Mudanças Detalhadas

Para **cada arquivo alterado**, descreva:

### Arquivo: `(nome do arquivo)`

**O que mudou:**
(Descreva as alterações feitas — funções novas, funções modificadas, parâmetros alterados, lógica removida)

**Por que mudou:**
(Qual problema estava resolvendo ou qual funcionalidade nova foi adicionada)

**Funções novas:**
(Liste as funções/métodos novos com assinatura e propósito)

**Funções modificadas:**
(Liste quais funções tiveram sua assinatura ou comportamento alterado)

**Funções removidas:**
(Liste quais foram removidas e por quê)

**Dependências novas:**
(Alguma lib Python nova foi necessária? Se sim, qual e qual versão mínima?)

---

## Novas Queries SQL

Se adicionou ou alterou queries ao banco PostgreSQL:

| Método | Schema/Tabela | Tipo (SELECT/INSERT/etc) | Descrição |
|---|---|---|---|
| | | | |

---

## Novos Assets (labels, fonts, icons)

Liste novos arquivos de arte/label adicionados:

| Arquivo | Descrição |
|---|---|
| | |

---

## Alterações em Estrutura de Dados

Se mudou o formato de dados que alguma função recebe ou retorna (DataFrames, dicionários), descreva:

| Função | Antes | Depois |
|---|---|---|
| | | |

---

## Testes Realizados

Descreva como você testou as alterações:

| Teste | Resultado | Observação |
|---|---|---|
| Relatório por cliente (ID JD) | OK / Falha | |
| Relatório por PIN (chassi) | OK / Falha | |
| Cliente sem dados | OK / Falha | |
| Período sem alertas | OK / Falha | |
| (adicione cenários conforme necessário) | | |

**Clientes usados para teste:**
(Liste os IDs JD ou PINs usados)

**Período de datas usado:**
(ex: 2026-01-01 a 2026-06-01)

---

## Pontos de Atenção

Algo que a equipe de integração precisa saber:

- [ ] Alguma dependência Python nova?
- [ ] Alguma tabela/coluna nova no banco?
- [ ] Algum comportamento que mudou em relação à versão anterior?
- [ ] Algum arquivo que deve ser deletado da versão anterior?
- [ ] Algo que funciona diferente quando executado no Docker vs local?

---

## Impacto na Geração Automática Mensal

O RDA possui um sistema de **geração automática de relatórios** que roda todo dia 01 de cada mês. Ele gera relatórios de frota para uma lista de IDs JD configurados no `.env` (`RDA_BATCH_IDS`).

Esse sistema usa as **mesmas funções** `rda_py_data_movel()` e `rda_py_by_pin()` do report. Portanto, qualquer mudança nessas funções afeta tanto a geração manual (pelo usuário na página) quanto a geração automática mensal.

Responda:

- [ ] Sua alteração muda a assinatura (parâmetros) de `rda_py_data_movel()` ou `rda_py_by_pin()`?
- [ ] Sua alteração muda o nome do PDF retornado por essas funções?
- [ ] Sua alteração adiciona algum novo `input()` ou interação que depende de terminal/tela?
- [ ] Sua alteração usa `os.chdir()` em algum ponto? (Se sim, descreva onde e por quê)

> **Se respondeu SIM a qualquer item acima, sinalize explicitamente na entrega.**
> A equipe de integração precisa adaptar o `app.py` para manter compatibilidade com o batch automático.

---

## NÃO ALTERAR (Mantidos pela equipe de integração)

Os seguintes módulos/padrões são mantidos pela equipe do Command Center.
**Não modifique esses itens** — se precisar de mudanças neles, sinalize neste documento.

| Item | Motivo |
|---|---|
| `kernel/modulo_consulta.py` — classe `BancoService` | Thread-safe com `threading.local()` para queries paralelas em Docker |
| Importação via `ThreadPoolExecutor` em `report_X.py` | Paralelismo de 9 queries ao banco — reduz tempo de 30min para 5min |
| `backend/app.py` | Integração SSO, Docker, tracking de progresso, batch mensal automático |
| `docker/Dockerfile.rda-backend` | Build config, gunicorn, healthcheck |
| `docker/docker-compose.yml` | Rede, volumes, variáveis de ambiente |
| `.env` | Credenciais, configs SSO e lista de IDs do batch mensal (`RDA_BATCH_IDS`) |
| `frontend/server.js` | Proxy, SSO, rotas do batch mensal |
| `frontend/index.html` | Interface completa incluindo indicador de progresso do batch mensal |
| `relatorios_mensais/` | Pasta de saída do batch automático — não remover nem renomear |

Se sua versão inclui um `modulo_consulta.py` diferente, **envie-o separado** mas saiba que a versão thread-safe será mantida. Novas queries devem ser adicionadas em `modulo_sql_rev2.py`.

### Contrato das funções de geração (não quebrar)

As funções abaixo são chamadas pelo `app.py` tanto no fluxo manual quanto no batch automático. **Mantenha a assinatura e o comportamento de retorno:**

```python
# Relatório de frota (por ID JD / organização)
def rda_py_data_movel(cliente_id: int, data_inicial: str, data_final: str) -> str:
    # Retorna: nome do arquivo PDF gerado (ex: "relatorio_5766479_01_06_2026_01_07_2026.pdf")

# Relatório individual (por chassi)
def rda_py_by_pin(chassi: str, data_inicial: str, data_final: str) -> str:
    # Retorna: nome do arquivo PDF gerado
```

- `data_inicial` e `data_final` sempre no formato `"YYYY-MM-DD"`
- O PDF deve ser gerado **no diretório de trabalho atual** (`os.getcwd()`)
- A função **não deve chamar** `os.chdir()` — o `app.py` já controla o CWD
- A função **não deve usar** `print()` para interação — apenas para log

---

## Exemplo Preenchido (referência)

<details>
<summary>Clique para ver um exemplo</summary>

### Arquivo: `backend/report_0.4.py`

**O que mudou:**
- Adicionada função `func_desempenho_modelo_possui_dados_validos()` que valida se um modelo de equipamento tem dados suficientes para aparecer no relatório
- Filtro de garantia alterado para mostrar apenas garantias VIGENTE (antes mostrava todas)
- Eliminação de páginas vazias — seções sem dados são puladas automaticamente
- Função `formatar_kpi()` adicionada para formatação padronizada de indicadores
- Correção de acentos em textos (ex: "Utilizacao" → "Utilização")

**Por que mudou:**
- Relatórios estavam gerando páginas em branco para modelos sem dados
- Garantias vencidas apareciam e confundiam o cliente

**Funções novas:**
- `func_desempenho_modelo_possui_dados_validos(df, modelo) -> bool`
- `formatar_kpi(valor, tipo="percentual") -> str`
- `rda_py_by_pin(chassi, data_inicial, data_final) -> str`

**Dependências novas:**
- Nenhuma

</details>
