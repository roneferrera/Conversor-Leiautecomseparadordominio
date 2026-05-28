import re
import traceback
import unicodedata
import streamlit as st

# ==============================
# VERSÃO
# ==============================
VERSAO = "V1.6"

# ==============================
# TEMA TR
# ==============================
def apply_tr_theme():
    st.markdown("""
        <style>
        html, body, [class*="css"] {
            font-family: 'Segoe UI', 'Arial', sans-serif;
            color: #444444;
        }
        h1, h2, h3 { color: #FF8000; font-weight: 700; }
        section[data-testid="stSidebar"] { background-color: #444444; color: #FFFFFF; }
        section[data-testid="stSidebar"] * { color: #FFFFFF !important; }
        .stButton > button {
            background-color: #FF8000; color: #FFFFFF;
            border: none; border-radius: 4px; font-weight: bold;
        }
        .stButton > button:hover { background-color: #D64001; color: #FFFFFF; }
        .stDownloadButton > button {
            background-color: #FF8000; color: #FFFFFF;
            border: none; border-radius: 4px; font-weight: bold;
        }
        .stDownloadButton > button:hover { background-color: #D64001; color: #FFFFFF; }
        hr { border-color: #FF8000; }
        [data-testid="metric-container"] {
            background-color: #E9E9E9;
            border-left: 4px solid #FF8000;
            border-radius: 4px; padding: 10px;
        }
        .instrucoes-box {
            background-color: #E9E9E9; border-left: 4px solid #FF8000;
            border-radius: 4px; padding: 16px 20px; margin: 12px 0;
            color: #444444; font-family: 'Segoe UI', Arial, sans-serif;
        }
        .instrucoes-box h4 { color: #FF8000; margin-top: 14px; margin-bottom: 6px; }
        .instrucoes-box h4:first-child { margin-top: 0; }
        .stProgress > div > div > div > div { background-color: #FF8000 !important; }
        </style>
    """, unsafe_allow_html=True)


# ==============================
# ESTRUTURA DE DADOS
# ==============================
class SpedECD:
    def __init__(self):
        self.cnpj        = ""
        self.contas      = {}
        self.historicos  = {}
        self.lancamentos = []


# ==============================
# NORMALIZAÇÃO DE HISTÓRICO
# ==============================
_MAPA_ESPECIAIS = {
    "\u2018": "'", "\u2019": "'",
    "\u201C": '"', "\u201D": '"',
    "\u2013": "-", "\u2014": "-",
    "\u2026": "...",
    "\u00A0": " ",
    "\u00D7": "x", "\u00F7": "/",
    "\u20AC": "EUR",
    "\u00A7": "S/",
    "\u00AE": "(R)",
    "\u00A9": "(C)",
    "\u2122": "(TM)",
}


def normalizar_historico(texto):
    if not texto:
        return ""
    for orig, dest in _MAPA_ESPECIAIS.items():
        texto = texto.replace(orig, dest)
    texto = unicodedata.normalize("NFC", texto)
    resultado = []
    for ch in texto:
        if ord(ch) < 0x20 and ord(ch) not in (0x09, 0x0A, 0x0D):
            continue
        try:
            ch.encode("latin-1")
            resultado.append(ch)
        except (UnicodeEncodeError, UnicodeDecodeError):
            decomposto = unicodedata.normalize("NFD", ch)
            base = decomposto[0]
            try:
                base.encode("latin-1")
                resultado.append(base)
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    texto = "".join(resultado)
    texto = re.sub(r" {2,}", " ", texto).strip()
    return texto[:250]


# ==============================
# PARSE DO SPED ECD
# ==============================
def _split_pipe(linha):
    campos = linha.strip().split("|")
    if campos and campos[0] == "":
        campos = campos[1:]
    if campos and campos[-1] == "":
        campos = campos[:-1]
    return campos


def parse_sped_ecd(conteudo_bytes, log, progress_bar, status_text):
    ecd        = SpedECD()
    lote_atual = None
    erros      = 0

    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            texto = conteudo_bytes.decode(encoding, errors="strict")
            log.append(f"Encoding detectado: {encoding}")
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        texto = conteudo_bytes.decode("utf-8", errors="replace")
        log.append("Aviso: encoding não identificado; usando UTF-8 com substituição.")

    linhas_lista = texto.splitlines()
    total        = len(linhas_lista) or 1
    status_text.text("📖 Lendo registros do SPED ECD...")

    for num_linha, linha in enumerate(linhas_lista, start=1):
        if num_linha % 500 == 0 or num_linha == total:
            pct = int((num_linha / total) * 50)
            progress_bar.progress(pct)
            status_text.text(f"📖 Lendo linha {num_linha:,} de {total:,}...")

        linha = linha.strip()
        if not linha:
            continue

        campos   = _split_pipe(linha)
        registro = campos[0] if campos else ""

        try:
            if registro == "0000":
                if len(campos) > 5:
                    ecd.cnpj = campos[5].strip()

            elif registro == "I050":
                if len(campos) > 7:
                    cod  = campos[5].strip()
                    nome = campos[7].strip()
                    if cod:
                        ecd.contas[cod] = nome

            elif registro == "I075":
                if len(campos) > 2:
                    cod   = campos[1].strip()
                    descr = normalizar_historico(campos[2])
                    ecd.historicos[cod] = descr

            elif registro == "I200":
                if len(campos) > 3:
                    lote_atual = {
                        "num"     : campos[1].strip(),
                        "data"    : campos[2].strip(),
                        "valor"   : campos[3].strip(),
                        "partidas": [],
                    }
                    ecd.lancamentos.append(lote_atual)

            elif registro == "I250":
                if lote_atual is not None and len(campos) > 4:
                    partida = {
                        "conta"     : campos[1].strip(),
                        "valor"     : campos[3].strip(),
                        "dc"        : campos[4].strip().upper(),
                        "descr_hist": normalizar_historico(
                            campos[7] if len(campos) > 7 else ""
                        ),
                    }
                    lote_atual["partidas"].append(partida)

        except Exception as e:
            log.append(f"Aviso: erro na linha {num_linha} ({registro}): {e}")
            erros += 1
            if erros > 50:
                log.append("ERRO: muitos erros de parse. Abortando leitura.")
                return None

    progress_bar.progress(50)

    if not ecd.cnpj:
        log.append("ERRO: CNPJ não encontrado no registro 0000.")
        return None

    log.append(f"Leitura concluída — CNPJ: {ecd.cnpj}")
    log.append(f"  Contas carregadas : {len(ecd.contas)}")
    log.append(f"  Históricos (I075) : {len(ecd.historicos)}")
    log.append(f"  Lançamentos (I200): {len(ecd.lancamentos)}")
    return ecd


# ==============================
# FUNÇÕES AUXILIARES
# ==============================

def formatar_data_dominio(data_sped):
    d = data_sped.strip()
    if "/" in d:
        return d
    if len(d) == 8 and d.isdigit():
        return f"{d[0:2]}/{d[2:4]}/{d[4:8]}"
    return d


def formatar_valor(valor_str):
    """Garante separador decimal com vírgula e pelo menos duas casas decimais."""
    if isinstance(valor_str, float):
        return f"{valor_str:.2f}".replace(".", ",")
    v = str(valor_str).strip()
    if "." in v and "," not in v:
        v = v.replace(".", ",")
    elif "." in v and "," in v:
        if v.index(".") < v.index(","):
            v = v.replace(".", "").replace(",", ".")
            v = v.replace(".", ",")
    if "," not in v:
        v += ",00"
    else:
        partes = v.split(",")
        if len(partes[1]) < 2:
            partes[1] = partes[1].ljust(2, "0")
        v = ",".join(partes)
    return v


def _str_to_float(valor_str):
    """Converte string de valor (com vírgula ou ponto) para float."""
    if isinstance(valor_str, (int, float)):
        return float(valor_str)
    v = str(valor_str).strip()
    # Remove pontos de milhar e troca vírgula decimal por ponto
    if "." in v and "," in v:
        if v.index(".") < v.index(","):
            v = v.replace(".", "").replace(",", ".")
        else:
            v = v.replace(",", "")
    elif "," in v:
        v = v.replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return 0.0


def montar_historico(partida):
    return partida.get("descr_hist", "").strip()


def primeiro_historico(partidas):
    for p in partidas:
        h = montar_historico(p)
        if h:
            return h
    return ""


def agrupar_partidas_por_conta(partidas):
    """
    Agrupa partidas pelo código de conta, somando os valores.
    Retorna lista de dicts {conta, valor (float), dc, descr_hist}.
    """
    agrupado = {}
    for p in partidas:
        conta = p["conta"]
        if conta not in agrupado:
            agrupado[conta] = {
                "conta"     : conta,
                "valor"     : 0.0,
                "dc"        : p["dc"],
                "descr_hist": p.get("descr_hist", ""),
            }
        agrupado[conta]["valor"] += _str_to_float(p["valor"])
        if not agrupado[conta]["descr_hist"] and p.get("descr_hist"):
            agrupado[conta]["descr_hist"] = p["descr_hist"]

    return list(agrupado.values())


def classificar_lancamento(debitos, creditos):
    """
    Classifica o lançamento com base em contas DISTINTAS já agrupadas:
        X = 1 débito  × 1 crédito
        D = 1 débito  × N créditos
        C = N débitos × 1 crédito
        V = N débitos × N créditos
    """
    nd = len(debitos)   # já agrupados por conta → 1 entrada por conta
    nc = len(creditos)

    if nd == 1 and nc == 1:
        return "X"
    if nd == 1 and nc > 1:
        return "D"
    if nc == 1 and nd > 1:
        return "C"
    return "V"


# ==============================
# GERADOR DO LAYOUT DOMÍNIO
# ==============================

def gerar_dominio(ecd, log, progress_bar, status_text, gerar_6110=True):
    """
    Gera as linhas do layout Domínio Sistemas.
    Registros: 0000 / 6000 / 6100 / 6110

    V1.6 — Soma de valores por conta + opção de gerar 6110:
    ────────────────────────────────────────────────────────
    • Agrupa partidas I250 por conta e SOMA os valores antes de classificar.
    • O valor do 6100 é a soma real do lado principal (débito ou crédito).
    • O valor de cada 6110 é a soma da conta adicional correspondente.
    • Parâmetro gerar_6110: se False, omite os registros 6110 (lançamentos
      sem rateio de centro de custos — apenas 6000 + 6100 são emitidos).
    • Classificação D/C/X/V baseada em contas distintas após agrupamento.
    • Campo 6 do 6100 sempre vazio (evita 'histórico não cadastrado').
    • Arquivo de saída em latin-1.
    """
    linhas     = []
    total_6100 = 0
    total_6110 = 0
    ignorados  = 0

    cnpj_numerico = re.sub(r"\D", "", ecd.cnpj)
    linhas.append(f"|0000|{cnpj_numerico}|")

    total_lanc = len(ecd.lancamentos)
    status_text.text(f"⚙ Gerando layout Domínio — {total_lanc:,} lançamentos...")

    for idx, lanc in enumerate(ecd.lancamentos):

        if idx % 100 == 0 or idx == total_lanc - 1:
            pct = 50 + int(((idx + 1) / total_lanc) * 50)
            progress_bar.progress(min(pct, 99))
            status_text.text(
                f"⚙ Gerando lançamento {idx + 1:,} de {total_lanc:,}..."
            )

        partidas_brutas = lanc.get("partidas", [])
        if not partidas_brutas:
            ignorados += 1
            continue

        # ── Agrupa por conta (soma valores) ──────────────────────────────
        partidas = agrupar_partidas_por_conta(partidas_brutas)

        debitos  = [p for p in partidas if p["dc"] == "D"]
        creditos = [p for p in partidas if p["dc"] == "C"]

        if not debitos or not creditos:
            ignorados += 1
            continue

        data      = formatar_data_dominio(lanc["data"])
        tipo_lanc = classificar_lancamento(debitos, creditos)
        historico = primeiro_historico(partidas_brutas)

        # ── Registro 6000 ────────────────────────────────────────────────
        linhas.append(f"|6000|{tipo_lanc}||||")

        # ── Registros 6100 / 6110 ────────────────────────────────────────
        #
        # Tipo X: 1 débito × 1 crédito
        # ─────────────────────────────
        if tipo_lanc == "X":
            db  = debitos[0]
            cr  = creditos[0]
            # Usa o valor do débito (= crédito em lançamento balanceado)
            val = formatar_valor(db["valor"])
            dsc = montar_historico(db) or historico
            linhas.append(
                f"|6100|{data}|{db['conta']}|{cr['conta']}"
                f"|{val}||{dsc}|||"
            )
            total_6100 += 1
            # Tipo X não tem partidas adicionais → 6110 não se aplica

        # Tipo D: 1 débito × vários créditos
        # ────────────────────────────────────
        # Valor do 6100 = soma total do débito
        # Valor de cada 6110 = valor da conta de crédito adicional
        elif tipo_lanc == "D":
            db           = debitos[0]
            cr_principal = creditos[0]
            val = formatar_valor(db["valor"])   # soma total do único débito
            dsc = montar_historico(db) or historico
            linhas.append(
                f"|6100|{data}|{db['conta']}|{cr_principal['conta']}"
                f"|{val}||{dsc}|||"
            )
            total_6100 += 1
            if gerar_6110:
                for cr in creditos[1:]:
                    vr = formatar_valor(cr["valor"])
                    linhas.append(f"|6110||{cr['conta']}|{vr}|")
                    total_6110 += 1

        # Tipo C: vários débitos × 1 crédito
        # ────────────────────────────────────
        # Valor do 6100 = soma total do crédito
        # Valor de cada 6110 = valor da conta de débito adicional
        elif tipo_lanc == "C":
            cr           = creditos[0]
            db_principal = debitos[0]
            val = formatar_valor(cr["valor"])   # soma total do único crédito
            dsc = montar_historico(db_principal) or historico
            linhas.append(
                f"|6100|{data}|{db_principal['conta']}|{cr['conta']}"
                f"|{val}||{dsc}|||"
            )
            total_6100 += 1
            if gerar_6110:
                for db in debitos[1:]:
                    vr = formatar_valor(db["valor"])
                    linhas.append(f"|6110|{db['conta']}||{vr}|")
                    total_6110 += 1

        # Tipo V: vários débitos × vários créditos
        # ──────────────────────────────────────────
        # Valor do 6100 = valor do primeiro débito
        # Valor de cada 6110 = valor de cada partida adicional
        else:
            db_principal = debitos[0]
            cr_principal = creditos[0]
            val = formatar_valor(db_principal["valor"])
            dsc = montar_historico(db_principal) or historico
            linhas.append(
                f"|6100|{data}|{db_principal['conta']}|{cr_principal['conta']}"
                f"|{val}||{dsc}|||"
            )
            total_6100 += 1
            if gerar_6110:
                for db in debitos[1:]:
                    vr = formatar_valor(db["valor"])
                    linhas.append(f"|6110|{db['conta']}||{vr}|")
                    total_6110 += 1
                for cr in creditos[1:]:
                    vr = formatar_valor(cr["valor"])
                    linhas.append(f"|6110||{cr['conta']}|{vr}|")
                    total_6110 += 1

    log.append(f"Registros 6100 gerados        : {total_6100}")
    log.append(f"Registros 6110 gerados        : {total_6110}")
    log.append(f"Registros 6110 {'habilitados' if gerar_6110 else 'DESABILITADOS (opção do usuário)'}")
    if ignorados:
        log.append(f"Lançamentos ignorados (sem D/C): {ignorados}")
    log.append(f"Total de linhas geradas       : {len(linhas)}")
    return linhas


# ==============================
# PIPELINE PRINCIPAL
# ==============================
def converter_sped_ecd(conteudo_bytes, log, progress_bar, status_text, gerar_6110=True):
    try:
        log.append("Iniciando leitura do SPED ECD...")
        ecd = parse_sped_ecd(conteudo_bytes, log, progress_bar, status_text)

        if ecd is None:
            log.append("ERRO: Leitura do SPED ECD falhou. Abortando.")
            return None, None

        log.append(f"Gerando layout Domínio Sistemas (6110: {'SIM' if gerar_6110 else 'NÃO'})...")
        linhas = gerar_dominio(ecd, log, progress_bar, status_text, gerar_6110=gerar_6110)

        if not linhas:
            log.append("ERRO: Nenhuma linha foi gerada.")
            return None, None

        return linhas, ecd

    except Exception:
        log.append("ERRO FATAL durante a conversão.")
        log.append(traceback.format_exc())
        return None, None


# ==============================
# INTERFACE STREAMLIT
# ==============================
def main():
    st.set_page_config(
        page_title="Domínio Sistemas | Thomson Reuters",
        page_icon="🟠",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_tr_theme()

    # ---- Cabeçalho ----
    st.markdown(
        f"""
        <div style="background:#444444; padding:24px 28px 18px 28px; border-radius:8px;
                    border-top:6px solid #FF8000; margin-bottom:28px;">
            <h2 style="color:#FF8000; margin:0; font-family:'Segoe UI',Arial,sans-serif;">
                📒 Conversor SPED ECD → Lançamentos em Lote &nbsp;|&nbsp; {VERSAO}
            </h2>
            <p style="color:#DDDDDD; margin:6px 0 0 0; font-family:'Segoe UI',Arial,sans-serif;">
                Selecione o arquivo SPED ECD e clique em
                <strong>▶ Converter</strong> para gerar o arquivo de importação
                do Domínio Contabilidade (registros 0000 / 6000 / 6100 / 6110).
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Sidebar ----
    with st.sidebar:
        st.markdown("### ℹ Sobre")
        st.markdown(f"**Versão:** {VERSAO}")
        st.markdown("**Thomson Reuters**")
        st.markdown("**Domínio Sistemas**")
        st.markdown("---")
        st.markdown("### 📋 Registros gerados")
        st.markdown(
            """
| Registro | Descrição |
|----------|-----------|
| `0000`   | CNPJ da empresa |
| `6000`   | Cabeçalho do lote (tipo X/D/C/V) |
| `6100`   | Lançamento principal |
| `6110`   | Partidas adicionais (rateio) |
            """
        )
        st.markdown("---")
        st.markdown("### 🔀 Classificação D/C/X/V")
        st.markdown(
            """
| Tipo | Regra |
|------|-------|
| **X** | 1 débito × 1 crédito |
| **D** | 1 débito × vários créditos |
| **C** | vários débitos × 1 crédito |
| **V** | vários débitos × vários créditos |

A classificação é feita por **contas distintas** após **soma dos valores** por conta.
            """
        )
        st.markdown("---")
        st.markdown("### ✅ Histórico de versões")
        st.markdown(
            """
**V1.6** — Soma de valores + opção 6110
- Soma valores de partidas da mesma conta **antes** de classificar
- Valor do 6100 reflete a soma real (não apenas a primeira partida)
- Opção de gerar ou não os registros 6110

**V1.5** — Classificação D/C/X/V correta
- Agrupa partidas I250 por conta antes de classificar
- Usa contas **distintas** para determinar o tipo

**V1.4** — Filtro de contas removido

**V1.3** — Campo 6 vazio; latin-1; histórico livre

**V1.2** — Caracteres especiais; encoding automático

**V1.1** — Barra de progresso
            """
        )

    # ---- Instruções ----
    with st.expander("📖 **Instruções de Uso** — clique para expandir", expanded=False):
        st.markdown(
            """
            <div class="instrucoes-box">

            <h4>🔹 Passo 1 — Obter o arquivo SPED ECD</h4>
            <p>Exporte o arquivo SPED ECD da sua contabilidade (extensão <code>.txt</code>).
            Certifique-se de que o arquivo contém os registros
            <code>0000</code>, <code>I050</code>, <code>I075</code>,
            <code>I200</code> e <code>I250</code>.</p>

            <h4>🔹 Passo 2 — Configurar e Converter</h4>
            <ol>
                <li>Clique em <b>Browse files</b> e selecione o arquivo SPED ECD.</li>
                <li>Escolha se deseja gerar os registros <b>6110</b> (partidas adicionais).</li>
                <li>Clique em <b>▶ Converter</b>.</li>
                <li>Aguarde o processamento e clique em
                    <b>⬇ Baixar arquivo convertido</b>.</li>
            </ol>

            <h4>🔹 Sobre o registro 6110</h4>
            <p>O registro <b>6110</b> no layout Domínio é destinado a
            <b>Centro de Custos</b> (campos 2 e 3 = código do CC a débito/crédito).
            Neste conversor, os campos são preenchidos com o <b>código reduzido
            da conta contábil</b> adicional (partidas extras dos tipos D, C e V).
            Se o seu Domínio não utiliza centro de custos, desabilite a geração
            do 6110 para evitar erros na importação.</p>

            <h4>🔹 Passo 3 — Importar no Domínio Contabilidade</h4>
            <ol>
                <li>Abra o <b>Domínio Contabilidade</b>.</li>
                <li>Acesse <b>Utilitários → Importação → Lançamentos em Lote</b>.</li>
                <li>Selecione o arquivo <code>.txt</code> gerado e confirme a importação.</li>
            </ol>

            <hr>

            <h4>⚠ Observações importantes</h4>
            <ul>
                <li>Os valores de partidas I250 com a <b>mesma conta contábil</b> são
                    <b>somados</b> antes da classificação e geração dos registros.
                    O valor do 6100 reflete essa soma.</li>
                <li>O tipo do lançamento (<b>X / D / C / V</b>) é detectado
                    automaticamente com base nas <b>contas distintas</b> de cada lado
                    (débito/crédito), após o agrupamento.</li>
                <li>O campo de código do histórico é deixado em branco para evitar
                    o erro <i>"histórico não cadastrado"</i>.</li>
                <li>Lançamentos sem partidas de débito <b>e</b> crédito simultâneas
                    são ignorados.</li>
                <li>Letras acentuadas do português são preservadas.
                    O arquivo é gravado em <b>latin-1</b>.</li>
                <li>Verifique sempre o <b>Log de processamento</b> ao final da página.</li>
            </ul>

            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ---- Estado da sessão ----
    if "log"          not in st.session_state:
        st.session_state.log          = [f"Aplicação pronta. Versão: {VERSAO}"]
    if "txt_gerado"   not in st.session_state:
        st.session_state.txt_gerado   = None
    if "nome_arquivo" not in st.session_state:
        st.session_state.nome_arquivo = "lancamentos_dominio.txt"
    if "metricas"     not in st.session_state:
        st.session_state.metricas     = {}

    # ---- Upload ----
    arquivo = st.file_uploader(
        "Arquivo SPED ECD",
        type=["txt"],
        help="Selecione o arquivo SPED ECD exportado da sua contabilidade.",
    )

    # ---- Opção de Centro de Custos (6110) ----
    st.markdown("#### ⚙ Opções de geração")

    col_opt1, col_opt2 = st.columns([2, 3])
    with col_opt1:
        gerar_6110 = st.toggle(
            "Gerar registros 6110 (partidas adicionais)",
            value=True,
            help=(
                "Ative para gerar os registros 6110 com as contas adicionais "
                "dos lançamentos dos tipos D, C e V.\n\n"
                "⚠ O campo de centro de custos do Domínio (6110) será preenchido "
                "com o código reduzido da conta contábil adicional. "
                "Desative se o seu Domínio não utiliza centro de custos ou "
                "se preferir importar apenas os lançamentos principais (6100)."
            ),
        )
    with col_opt2:
        if gerar_6110:
            st.info(
                "✅ **6110 habilitado** — partidas adicionais (D, C, V) serão geradas. "
                "Certifique-se de que o Domínio está configurado para aceitar centro de custos.",
                icon=None,
            )
        else:
            st.warning(
                "⚠ **6110 desabilitado** — apenas registros 6100 serão gerados. "
                "Lançamentos D, C e V terão apenas a partida principal.",
                icon=None,
            )

    st.markdown("")

    col1, col2 = st.columns([1, 1])
    with col1:
        converter = st.button(
            "▶ Converter",
            disabled=(arquivo is None),
            use_container_width=True,
            type="primary",
        )
    with col2:
        limpar = st.button("🗑 Limpar", use_container_width=True)

    if limpar:
        st.session_state.log          = ["Campos limpos."]
        st.session_state.txt_gerado   = None
        st.session_state.nome_arquivo = "lancamentos_dominio.txt"
        st.session_state.metricas     = {}
        st.rerun()

    # ---- Processamento ----
    if converter and arquivo is not None:
        st.session_state.log          = [
            f"Iniciando conversão (6110: {'SIM' if gerar_6110 else 'NÃO'})..."
        ]
        st.session_state.txt_gerado   = None
        st.session_state.nome_arquivo = "lancamentos_dominio.txt"
        st.session_state.metricas     = {}

        status_text  = st.empty()
        progress_bar = st.progress(0)

        conteudo_bytes = arquivo.read()
        linhas, ecd    = converter_sped_ecd(
            conteudo_bytes,
            st.session_state.log,
            progress_bar,
            status_text,
            gerar_6110=gerar_6110,
        )

        if linhas and ecd:
            progress_bar.progress(100)
            status_text.text("✅ Conversão concluída!")

            conteudo_txt = "\n".join(linhas) + "\n"
            st.session_state.txt_gerado = conteudo_txt.encode(
                "latin-1", errors="replace"
            )
            cnpj_num = re.sub(r"\D", "", ecd.cnpj)
            sufixo   = "_com6110" if gerar_6110 else "_sem6110"
            st.session_state.nome_arquivo = (
                f"ECD_{cnpj_num}_lancamentos_dominio{sufixo}.txt"
            )

            total_linhas = len(linhas)
            total_6000   = sum(1 for l in linhas if l.startswith("|6000|"))
            total_6100   = sum(1 for l in linhas if l.startswith("|6100|"))
            total_6110_c = sum(1 for l in linhas if l.startswith("|6110|"))
            st.session_state.metricas = {
                "CNPJ"              : ecd.cnpj,
                "Lançamentos (6000)": total_6000,
                "Linhas 6100"       : total_6100,
                "Linhas 6110"       : total_6110_c,
                "Total de linhas"   : total_linhas,
            }
        else:
            progress_bar.progress(100)
            status_text.text("❌ Falha na conversão. Verifique o log abaixo.")

        st.rerun()

    # ---- Métricas ----
    if st.session_state.metricas:
        st.markdown("#### 📊 Resumo da conversão")
        m      = st.session_state.metricas
        labels = list(m.keys())
        values = list(m.values())
        cols   = st.columns(5)
        for i, col in enumerate(cols):
            if i < len(labels):
                col.metric(labels[i], values[i])
        st.markdown("")

    # ---- Download ----
    if st.session_state.txt_gerado is not None:
        st.success("✅ Conversão concluída com sucesso!")
        st.download_button(
            label="⬇ Baixar arquivo convertido",
            data=st.session_state.txt_gerado,
            file_name=st.session_state.nome_arquivo,
            mime="text/plain",
            use_container_width=True,
            type="primary",
        )

    # ---- Log ----
    st.markdown("**Log de processamento**")
    log_texto = "\n".join(st.session_state.log)
    tem_erro  = any(str(l).startswith("ERRO") for l in st.session_state.log)
    cor_borda = "#D32F2F" if tem_erro else "#388E3C"

    st.markdown(
        f"""
        <div style="background:#FCFCFC; border:1px solid {cor_borda};
                    border-radius:6px; padding:14px;
                    font-family:Consolas,monospace; font-size:13px;
                    white-space:pre-wrap; max-height:340px;
                    overflow-y:auto; color:#1F1F1F;">
{log_texto}
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()import re
import traceback
import unicodedata
import streamlit as st

# ==============================
# VERSÃO
# ==============================
VERSAO = "V1.6"

# ==============================
# TEMA TR
# ==============================
def apply_tr_theme():
    st.markdown("""
        <style>
        html, body, [class*="css"] {
            font-family: 'Segoe UI', 'Arial', sans-serif;
            color: #444444;
        }
        h1, h2, h3 { color: #FF8000; font-weight: 700; }
        section[data-testid="stSidebar"] { background-color: #444444; color: #FFFFFF; }
        section[data-testid="stSidebar"] * { color: #FFFFFF !important; }
        .stButton > button {
            background-color: #FF8000; color: #FFFFFF;
            border: none; border-radius: 4px; font-weight: bold;
        }
        .stButton > button:hover { background-color: #D64001; color: #FFFFFF; }
        .stDownloadButton > button {
            background-color: #FF8000; color: #FFFFFF;
            border: none; border-radius: 4px; font-weight: bold;
        }
        .stDownloadButton > button:hover { background-color: #D64001; color: #FFFFFF; }
        hr { border-color: #FF8000; }
        [data-testid="metric-container"] {
            background-color: #E9E9E9;
            border-left: 4px solid #FF8000;
            border-radius: 4px; padding: 10px;
        }
        .instrucoes-box {
            background-color: #E9E9E9; border-left: 4px solid #FF8000;
            border-radius: 4px; padding: 16px 20px; margin: 12px 0;
            color: #444444; font-family: 'Segoe UI', Arial, sans-serif;
        }
        .instrucoes-box h4 { color: #FF8000; margin-top: 14px; margin-bottom: 6px; }
        .instrucoes-box h4:first-child { margin-top: 0; }
        .stProgress > div > div > div > div { background-color: #FF8000 !important; }
        </style>
    """, unsafe_allow_html=True)


# ==============================
# ESTRUTURA DE DADOS
# ==============================
class SpedECD:
    def __init__(self):
        self.cnpj        = ""
        self.contas      = {}
        self.historicos  = {}
        self.lancamentos = []


# ==============================
# NORMALIZAÇÃO DE HISTÓRICO
# ==============================
_MAPA_ESPECIAIS = {
    "\u2018": "'", "\u2019": "'",
    "\u201C": '"', "\u201D": '"',
    "\u2013": "-", "\u2014": "-",
    "\u2026": "...",
    "\u00A0": " ",
    "\u00D7": "x", "\u00F7": "/",
    "\u20AC": "EUR",
    "\u00A7": "S/",
    "\u00AE": "(R)",
    "\u00A9": "(C)",
    "\u2122": "(TM)",
}


def normalizar_historico(texto):
    if not texto:
        return ""
    for orig, dest in _MAPA_ESPECIAIS.items():
        texto = texto.replace(orig, dest)
    texto = unicodedata.normalize("NFC", texto)
    resultado = []
    for ch in texto:
        if ord(ch) < 0x20 and ord(ch) not in (0x09, 0x0A, 0x0D):
            continue
        try:
            ch.encode("latin-1")
            resultado.append(ch)
        except (UnicodeEncodeError, UnicodeDecodeError):
            decomposto = unicodedata.normalize("NFD", ch)
            base = decomposto[0]
            try:
                base.encode("latin-1")
                resultado.append(base)
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    texto = "".join(resultado)
    texto = re.sub(r" {2,}", " ", texto).strip()
    return texto[:250]


# ==============================
# PARSE DO SPED ECD
# ==============================
def _split_pipe(linha):
    campos = linha.strip().split("|")
    if campos and campos[0] == "":
        campos = campos[1:]
    if campos and campos[-1] == "":
        campos = campos[:-1]
    return campos


def parse_sped_ecd(conteudo_bytes, log, progress_bar, status_text):
    ecd        = SpedECD()
    lote_atual = None
    erros      = 0

    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            texto = conteudo_bytes.decode(encoding, errors="strict")
            log.append(f"Encoding detectado: {encoding}")
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        texto = conteudo_bytes.decode("utf-8", errors="replace")
        log.append("Aviso: encoding não identificado; usando UTF-8 com substituição.")

    linhas_lista = texto.splitlines()
    total        = len(linhas_lista) or 1
    status_text.text("📖 Lendo registros do SPED ECD...")

    for num_linha, linha in enumerate(linhas_lista, start=1):
        if num_linha % 500 == 0 or num_linha == total:
            pct = int((num_linha / total) * 50)
            progress_bar.progress(pct)
            status_text.text(f"📖 Lendo linha {num_linha:,} de {total:,}...")

        linha = linha.strip()
        if not linha:
            continue

        campos   = _split_pipe(linha)
        registro = campos[0] if campos else ""

        try:
            if registro == "0000":
                if len(campos) > 5:
                    ecd.cnpj = campos[5].strip()

            elif registro == "I050":
                if len(campos) > 7:
                    cod  = campos[5].strip()
                    nome = campos[7].strip()
                    if cod:
                        ecd.contas[cod] = nome

            elif registro == "I075":
                if len(campos) > 2:
                    cod   = campos[1].strip()
                    descr = normalizar_historico(campos[2])
                    ecd.historicos[cod] = descr

            elif registro == "I200":
                if len(campos) > 3:
                    lote_atual = {
                        "num"     : campos[1].strip(),
                        "data"    : campos[2].strip(),
                        "valor"   : campos[3].strip(),
                        "partidas": [],
                    }
                    ecd.lancamentos.append(lote_atual)

            elif registro == "I250":
                if lote_atual is not None and len(campos) > 4:
                    partida = {
                        "conta"     : campos[1].strip(),
                        "valor"     : campos[3].strip(),
                        "dc"        : campos[4].strip().upper(),
                        "descr_hist": normalizar_historico(
                            campos[7] if len(campos) > 7 else ""
                        ),
                    }
                    lote_atual["partidas"].append(partida)

        except Exception as e:
            log.append(f"Aviso: erro na linha {num_linha} ({registro}): {e}")
            erros += 1
            if erros > 50:
                log.append("ERRO: muitos erros de parse. Abortando leitura.")
                return None

    progress_bar.progress(50)

    if not ecd.cnpj:
        log.append("ERRO: CNPJ não encontrado no registro 0000.")
        return None

    log.append(f"Leitura concluída — CNPJ: {ecd.cnpj}")
    log.append(f"  Contas carregadas : {len(ecd.contas)}")
    log.append(f"  Históricos (I075) : {len(ecd.historicos)}")
    log.append(f"  Lançamentos (I200): {len(ecd.lancamentos)}")
    return ecd


# ==============================
# FUNÇÕES AUXILIARES
# ==============================

def formatar_data_dominio(data_sped):
    d = data_sped.strip()
    if "/" in d:
        return d
    if len(d) == 8 and d.isdigit():
        return f"{d[0:2]}/{d[2:4]}/{d[4:8]}"
    return d


def formatar_valor(valor_str):
    """Garante separador decimal com vírgula e pelo menos duas casas decimais."""
    if isinstance(valor_str, float):
        return f"{valor_str:.2f}".replace(".", ",")
    v = str(valor_str).strip()
    if "." in v and "," not in v:
        v = v.replace(".", ",")
    elif "." in v and "," in v:
        if v.index(".") < v.index(","):
            v = v.replace(".", "").replace(",", ".")
            v = v.replace(".", ",")
    if "," not in v:
        v += ",00"
    else:
        partes = v.split(",")
        if len(partes[1]) < 2:
            partes[1] = partes[1].ljust(2, "0")
        v = ",".join(partes)
    return v


def _str_to_float(valor_str):
    """Converte string de valor (com vírgula ou ponto) para float."""
    if isinstance(valor_str, (int, float)):
        return float(valor_str)
    v = str(valor_str).strip()
    # Remove pontos de milhar e troca vírgula decimal por ponto
    if "." in v and "," in v:
        if v.index(".") < v.index(","):
            v = v.replace(".", "").replace(",", ".")
        else:
            v = v.replace(",", "")
    elif "," in v:
        v = v.replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return 0.0


def montar_historico(partida):
    return partida.get("descr_hist", "").strip()


def primeiro_historico(partidas):
    for p in partidas:
        h = montar_historico(p)
        if h:
            return h
    return ""


def agrupar_partidas_por_conta(partidas):
    """
    Agrupa partidas pelo código de conta, somando os valores.
    Retorna lista de dicts {conta, valor (float), dc, descr_hist}.
    """
    agrupado = {}
    for p in partidas:
        conta = p["conta"]
        if conta not in agrupado:
            agrupado[conta] = {
                "conta"     : conta,
                "valor"     : 0.0,
                "dc"        : p["dc"],
                "descr_hist": p.get("descr_hist", ""),
            }
        agrupado[conta]["valor"] += _str_to_float(p["valor"])
        if not agrupado[conta]["descr_hist"] and p.get("descr_hist"):
            agrupado[conta]["descr_hist"] = p["descr_hist"]

    return list(agrupado.values())


def classificar_lancamento(debitos, creditos):
    """
    Classifica o lançamento com base em contas DISTINTAS já agrupadas:
        X = 1 débito  × 1 crédito
        D = 1 débito  × N créditos
        C = N débitos × 1 crédito
        V = N débitos × N créditos
    """
    nd = len(debitos)   # já agrupados por conta → 1 entrada por conta
    nc = len(creditos)

    if nd == 1 and nc == 1:
        return "X"
    if nd == 1 and nc > 1:
        return "D"
    if nc == 1 and nd > 1:
        return "C"
    return "V"


# ==============================
# GERADOR DO LAYOUT DOMÍNIO
# ==============================

def gerar_dominio(ecd, log, progress_bar, status_text, gerar_6110=True):
    """
    Gera as linhas do layout Domínio Sistemas.
    Registros: 0000 / 6000 / 6100 / 6110

    V1.6 — Soma de valores por conta + opção de gerar 6110:
    ────────────────────────────────────────────────────────
    • Agrupa partidas I250 por conta e SOMA os valores antes de classificar.
    • O valor do 6100 é a soma real do lado principal (débito ou crédito).
    • O valor de cada 6110 é a soma da conta adicional correspondente.
    • Parâmetro gerar_6110: se False, omite os registros 6110 (lançamentos
      sem rateio de centro de custos — apenas 6000 + 6100 são emitidos).
    • Classificação D/C/X/V baseada em contas distintas após agrupamento.
    • Campo 6 do 6100 sempre vazio (evita 'histórico não cadastrado').
    • Arquivo de saída em latin-1.
    """
    linhas     = []
    total_6100 = 0
    total_6110 = 0
    ignorados  = 0

    cnpj_numerico = re.sub(r"\D", "", ecd.cnpj)
    linhas.append(f"|0000|{cnpj_numerico}|")

    total_lanc = len(ecd.lancamentos)
    status_text.text(f"⚙ Gerando layout Domínio — {total_lanc:,} lançamentos...")

    for idx, lanc in enumerate(ecd.lancamentos):

        if idx % 100 == 0 or idx == total_lanc - 1:
            pct = 50 + int(((idx + 1) / total_lanc) * 50)
            progress_bar.progress(min(pct, 99))
            status_text.text(
                f"⚙ Gerando lançamento {idx + 1:,} de {total_lanc:,}..."
            )

        partidas_brutas = lanc.get("partidas", [])
        if not partidas_brutas:
            ignorados += 1
            continue

        # ── Agrupa por conta (soma valores) ──────────────────────────────
        partidas = agrupar_partidas_por_conta(partidas_brutas)

        debitos  = [p for p in partidas if p["dc"] == "D"]
        creditos = [p for p in partidas if p["dc"] == "C"]

        if not debitos or not creditos:
            ignorados += 1
            continue

        data      = formatar_data_dominio(lanc["data"])
        tipo_lanc = classificar_lancamento(debitos, creditos)
        historico = primeiro_historico(partidas_brutas)

        # ── Registro 6000 ────────────────────────────────────────────────
        linhas.append(f"|6000|{tipo_lanc}||||")

        # ── Registros 6100 / 6110 ────────────────────────────────────────
        #
        # Tipo X: 1 débito × 1 crédito
        # ─────────────────────────────
        if tipo_lanc == "X":
            db  = debitos[0]
            cr  = creditos[0]
            # Usa o valor do débito (= crédito em lançamento balanceado)
            val = formatar_valor(db["valor"])
            dsc = montar_historico(db) or historico
            linhas.append(
                f"|6100|{data}|{db['conta']}|{cr['conta']}"
                f"|{val}||{dsc}|||"
            )
            total_6100 += 1
            # Tipo X não tem partidas adicionais → 6110 não se aplica

        # Tipo D: 1 débito × vários créditos
        # ────────────────────────────────────
        # Valor do 6100 = soma total do débito
        # Valor de cada 6110 = valor da conta de crédito adicional
        elif tipo_lanc == "D":
            db           = debitos[0]
            cr_principal = creditos[0]
            val = formatar_valor(db["valor"])   # soma total do único débito
            dsc = montar_historico(db) or historico
            linhas.append(
                f"|6100|{data}|{db['conta']}|{cr_principal['conta']}"
                f"|{val}||{dsc}|||"
            )
            total_6100 += 1
            if gerar_6110:
                for cr in creditos[1:]:
                    vr = formatar_valor(cr["valor"])
                    linhas.append(f"|6110||{cr['conta']}|{vr}|")
                    total_6110 += 1

        # Tipo C: vários débitos × 1 crédito
        # ────────────────────────────────────
        # Valor do 6100 = soma total do crédito
        # Valor de cada 6110 = valor da conta de débito adicional
        elif tipo_lanc == "C":
            cr           = creditos[0]
            db_principal = debitos[0]
            val = formatar_valor(cr["valor"])   # soma total do único crédito
            dsc = montar_historico(db_principal) or historico
            linhas.append(
                f"|6100|{data}|{db_principal['conta']}|{cr['conta']}"
                f"|{val}||{dsc}|||"
            )
            total_6100 += 1
            if gerar_6110:
                for db in debitos[1:]:
                    vr = formatar_valor(db["valor"])
                    linhas.append(f"|6110|{db['conta']}||{vr}|")
                    total_6110 += 1

        # Tipo V: vários débitos × vários créditos
        # ──────────────────────────────────────────
        # Valor do 6100 = valor do primeiro débito
        # Valor de cada 6110 = valor de cada partida adicional
        else:
            db_principal = debitos[0]
            cr_principal = creditos[0]
            val = formatar_valor(db_principal["valor"])
            dsc = montar_historico(db_principal) or historico
            linhas.append(
                f"|6100|{data}|{db_principal['conta']}|{cr_principal['conta']}"
                f"|{val}||{dsc}|||"
            )
            total_6100 += 1
            if gerar_6110:
                for db in debitos[1:]:
                    vr = formatar_valor(db["valor"])
                    linhas.append(f"|6110|{db['conta']}||{vr}|")
                    total_6110 += 1
                for cr in creditos[1:]:
                    vr = formatar_valor(cr["valor"])
                    linhas.append(f"|6110||{cr['conta']}|{vr}|")
                    total_6110 += 1

    log.append(f"Registros 6100 gerados        : {total_6100}")
    log.append(f"Registros 6110 gerados        : {total_6110}")
    log.append(f"Registros 6110 {'habilitados' if gerar_6110 else 'DESABILITADOS (opção do usuário)'}")
    if ignorados:
        log.append(f"Lançamentos ignorados (sem D/C): {ignorados}")
    log.append(f"Total de linhas geradas       : {len(linhas)}")
    return linhas


# ==============================
# PIPELINE PRINCIPAL
# ==============================
def converter_sped_ecd(conteudo_bytes, log, progress_bar, status_text, gerar_6110=True):
    try:
        log.append("Iniciando leitura do SPED ECD...")
        ecd = parse_sped_ecd(conteudo_bytes, log, progress_bar, status_text)

        if ecd is None:
            log.append("ERRO: Leitura do SPED ECD falhou. Abortando.")
            return None, None

        log.append(f"Gerando layout Domínio Sistemas (6110: {'SIM' if gerar_6110 else 'NÃO'})...")
        linhas = gerar_dominio(ecd, log, progress_bar, status_text, gerar_6110=gerar_6110)

        if not linhas:
            log.append("ERRO: Nenhuma linha foi gerada.")
            return None, None

        return linhas, ecd

    except Exception:
        log.append("ERRO FATAL durante a conversão.")
        log.append(traceback.format_exc())
        return None, None


# ==============================
# INTERFACE STREAMLIT
# ==============================
def main():
    st.set_page_config(
        page_title="Domínio Sistemas | Thomson Reuters",
        page_icon="🟠",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_tr_theme()

    # ---- Cabeçalho ----
    st.markdown(
        f"""
        <div style="background:#444444; padding:24px 28px 18px 28px; border-radius:8px;
                    border-top:6px solid #FF8000; margin-bottom:28px;">
            <h2 style="color:#FF8000; margin:0; font-family:'Segoe UI',Arial,sans-serif;">
                📒 Conversor SPED ECD → Lançamentos em Lote &nbsp;|&nbsp; {VERSAO}
            </h2>
            <p style="color:#DDDDDD; margin:6px 0 0 0; font-family:'Segoe UI',Arial,sans-serif;">
                Selecione o arquivo SPED ECD e clique em
                <strong>▶ Converter</strong> para gerar o arquivo de importação
                do Domínio Contabilidade (registros 0000 / 6000 / 6100 / 6110).
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Sidebar ----
    with st.sidebar:
        st.markdown("### ℹ Sobre")
        st.markdown(f"**Versão:** {VERSAO}")
        st.markdown("**Thomson Reuters**")
        st.markdown("**Domínio Sistemas**")
        st.markdown("---")
        st.markdown("### 📋 Registros gerados")
        st.markdown(
            """
| Registro | Descrição |
|----------|-----------|
| `0000`   | CNPJ da empresa |
| `6000`   | Cabeçalho do lote (tipo X/D/C/V) |
| `6100`   | Lançamento principal |
| `6110`   | Partidas adicionais (rateio) |
            """
        )
        st.markdown("---")
        st.markdown("### 🔀 Classificação D/C/X/V")
        st.markdown(
            """
| Tipo | Regra |
|------|-------|
| **X** | 1 débito × 1 crédito |
| **D** | 1 débito × vários créditos |
| **C** | vários débitos × 1 crédito |
| **V** | vários débitos × vários créditos |

A classificação é feita por **contas distintas** após **soma dos valores** por conta.
            """
        )
        st.markdown("---")
        st.markdown("### ✅ Histórico de versões")
        st.markdown(
            """
**V1.6** — Soma de valores + opção 6110
- Soma valores de partidas da mesma conta **antes** de classificar
- Valor do 6100 reflete a soma real (não apenas a primeira partida)
- Opção de gerar ou não os registros 6110

**V1.5** — Classificação D/C/X/V correta
- Agrupa partidas I250 por conta antes de classificar
- Usa contas **distintas** para determinar o tipo

**V1.4** — Filtro de contas removido

**V1.3** — Campo 6 vazio; latin-1; histórico livre

**V1.2** — Caracteres especiais; encoding automático

**V1.1** — Barra de progresso
            """
        )

    # ---- Instruções ----
    with st.expander("📖 **Instruções de Uso** — clique para expandir", expanded=False):
        st.markdown(
            """
            <div class="instrucoes-box">

            <h4>🔹 Passo 1 — Obter o arquivo SPED ECD</h4>
            <p>Exporte o arquivo SPED ECD da sua contabilidade (extensão <code>.txt</code>).
            Certifique-se de que o arquivo contém os registros
            <code>0000</code>, <code>I050</code>, <code>I075</code>,
            <code>I200</code> e <code>I250</code>.</p>

            <h4>🔹 Passo 2 — Configurar e Converter</h4>
            <ol>
                <li>Clique em <b>Browse files</b> e selecione o arquivo SPED ECD.</li>
                <li>Escolha se deseja gerar os registros <b>6110</b> (partidas adicionais).</li>
                <li>Clique em <b>▶ Converter</b>.</li>
                <li>Aguarde o processamento e clique em
                    <b>⬇ Baixar arquivo convertido</b>.</li>
            </ol>

            <h4>🔹 Sobre o registro 6110</h4>
            <p>O registro <b>6110</b> no layout Domínio é destinado a
            <b>Centro de Custos</b> (campos 2 e 3 = código do CC a débito/crédito).
            Neste conversor, os campos são preenchidos com o <b>código reduzido
            da conta contábil</b> adicional (partidas extras dos tipos D, C e V).
            Se o seu Domínio não utiliza centro de custos, desabilite a geração
            do 6110 para evitar erros na importação.</p>

            <h4>🔹 Passo 3 — Importar no Domínio Contabilidade</h4>
            <ol>
                <li>Abra o <b>Domínio Contabilidade</b>.</li>
                <li>Acesse <b>Utilitários → Importação → Lançamentos em Lote</b>.</li>
                <li>Selecione o arquivo <code>.txt</code> gerado e confirme a importação.</li>
            </ol>

            <hr>

            <h4>⚠ Observações importantes</h4>
            <ul>
                <li>Os valores de partidas I250 com a <b>mesma conta contábil</b> são
                    <b>somados</b> antes da classificação e geração dos registros.
                    O valor do 6100 reflete essa soma.</li>
                <li>O tipo do lançamento (<b>X / D / C / V</b>) é detectado
                    automaticamente com base nas <b>contas distintas</b> de cada lado
                    (débito/crédito), após o agrupamento.</li>
                <li>O campo de código do histórico é deixado em branco para evitar
                    o erro <i>"histórico não cadastrado"</i>.</li>
                <li>Lançamentos sem partidas de débito <b>e</b> crédito simultâneas
                    são ignorados.</li>
                <li>Letras acentuadas do português são preservadas.
                    O arquivo é gravado em <b>latin-1</b>.</li>
                <li>Verifique sempre o <b>Log de processamento</b> ao final da página.</li>
            </ul>

            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ---- Estado da sessão ----
    if "log"          not in st.session_state:
        st.session_state.log          = [f"Aplicação pronta. Versão: {VERSAO}"]
    if "txt_gerado"   not in st.session_state:
        st.session_state.txt_gerado   = None
    if "nome_arquivo" not in st.session_state:
        st.session_state.nome_arquivo = "lancamentos_dominio.txt"
    if "metricas"     not in st.session_state:
        st.session_state.metricas     = {}

    # ---- Upload ----
    arquivo = st.file_uploader(
        "Arquivo SPED ECD",
        type=["txt"],
        help="Selecione o arquivo SPED ECD exportado da sua contabilidade.",
    )

    # ---- Opção de Centro de Custos (6110) ----
    st.markdown("#### ⚙ Opções de geração")

    col_opt1, col_opt2 = st.columns([2, 3])
    with col_opt1:
        gerar_6110 = st.toggle(
            "Gerar registros 6110 (partidas adicionais)",
            value=True,
            help=(
                "Ative para gerar os registros 6110 com as contas adicionais "
                "dos lançamentos dos tipos D, C e V.\n\n"
                "⚠ O campo de centro de custos do Domínio (6110) será preenchido "
                "com o código reduzido da conta contábil adicional. "
                "Desative se o seu Domínio não utiliza centro de custos ou "
                "se preferir importar apenas os lançamentos principais (6100)."
            ),
        )
    with col_opt2:
        if gerar_6110:
            st.info(
                "✅ **6110 habilitado** — partidas adicionais (D, C, V) serão geradas. "
                "Certifique-se de que o Domínio está configurado para aceitar centro de custos.",
                icon=None,
            )
        else:
            st.warning(
                "⚠ **6110 desabilitado** — apenas registros 6100 serão gerados. "
                "Lançamentos D, C e V terão apenas a partida principal.",
                icon=None,
            )

    st.markdown("")

    col1, col2 = st.columns([1, 1])
    with col1:
        converter = st.button(
            "▶ Converter",
            disabled=(arquivo is None),
            use_container_width=True,
            type="primary",
        )
    with col2:
        limpar = st.button("🗑 Limpar", use_container_width=True)

    if limpar:
        st.session_state.log          = ["Campos limpos."]
        st.session_state.txt_gerado   = None
        st.session_state.nome_arquivo = "lancamentos_dominio.txt"
        st.session_state.metricas     = {}
        st.rerun()

    # ---- Processamento ----
    if converter and arquivo is not None:
        st.session_state.log          = [
            f"Iniciando conversão (6110: {'SIM' if gerar_6110 else 'NÃO'})..."
        ]
        st.session_state.txt_gerado   = None
        st.session_state.nome_arquivo = "lancamentos_dominio.txt"
        st.session_state.metricas     = {}

        status_text  = st.empty()
        progress_bar = st.progress(0)

        conteudo_bytes = arquivo.read()
        linhas, ecd    = converter_sped_ecd(
            conteudo_bytes,
            st.session_state.log,
            progress_bar,
            status_text,
            gerar_6110=gerar_6110,
        )

        if linhas and ecd:
            progress_bar.progress(100)
            status_text.text("✅ Conversão concluída!")

            conteudo_txt = "\n".join(linhas) + "\n"
            st.session_state.txt_gerado = conteudo_txt.encode(
                "latin-1", errors="replace"
            )
            cnpj_num = re.sub(r"\D", "", ecd.cnpj)
            sufixo   = "_com6110" if gerar_6110 else "_sem6110"
            st.session_state.nome_arquivo = (
                f"ECD_{cnpj_num}_lancamentos_dominio{sufixo}.txt"
            )

            total_linhas = len(linhas)
            total_6000   = sum(1 for l in linhas if l.startswith("|6000|"))
            total_6100   = sum(1 for l in linhas if l.startswith("|6100|"))
            total_6110_c = sum(1 for l in linhas if l.startswith("|6110|"))
            st.session_state.metricas = {
                "CNPJ"              : ecd.cnpj,
                "Lançamentos (6000)": total_6000,
                "Linhas 6100"       : total_6100,
                "Linhas 6110"       : total_6110_c,
                "Total de linhas"   : total_linhas,
            }
        else:
            progress_bar.progress(100)
            status_text.text("❌ Falha na conversão. Verifique o log abaixo.")

        st.rerun()

    # ---- Métricas ----
    if st.session_state.metricas:
        st.markdown("#### 📊 Resumo da conversão")
        m      = st.session_state.metricas
        labels = list(m.keys())
        values = list(m.values())
        cols   = st.columns(5)
        for i, col in enumerate(cols):
            if i < len(labels):
                col.metric(labels[i], values[i])
        st.markdown("")

    # ---- Download ----
    if st.session_state.txt_gerado is not None:
        st.success("✅ Conversão concluída com sucesso!")
        st.download_button(
            label="⬇ Baixar arquivo convertido",
            data=st.session_state.txt_gerado,
            file_name=st.session_state.nome_arquivo,
            mime="text/plain",
            use_container_width=True,
            type="primary",
        )

    # ---- Log ----
    st.markdown("**Log de processamento**")
    log_texto = "\n".join(st.session_state.log)
    tem_erro  = any(str(l).startswith("ERRO") for l in st.session_state.log)
    cor_borda = "#D32F2F" if tem_erro else "#388E3C"

    st.markdown(
        f"""
        <div style="background:#FCFCFC; border:1px solid {cor_borda};
                    border-radius:6px; padding:14px;
                    font-family:Consolas,monospace; font-size:13px;
                    white-space:pre-wrap; max-height:340px;
                    overflow-y:auto; color:#1F1F1F;">
{log_texto}
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
