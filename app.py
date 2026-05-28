import re
import traceback
import unicodedata
import streamlit as st

VERSAO = "V2.0"

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
                lote_atual = {
                    "num"     : campos[1].strip() if len(campos) > 1 else "",
                    "data"    : campos[2].strip() if len(campos) > 2 else "",
                    "valor"   : campos[3].strip() if len(campos) > 3 else "",
                    "partidas": [],
                }
                ecd.lancamentos.append(lote_atual)

            elif registro == "I250":
                if lote_atual is not None and len(campos) > 4:
                    dc_raw = campos[4].strip().upper()
                    if dc_raw not in ("D", "C"):
                        log.append(
                            f"Aviso: I250 com dc='{dc_raw}' ignorado (esperado D ou C)."
                        )
                        continue
                    partida = {
                        "conta"     : campos[1].strip(),
                        "valor"     : campos[3].strip(),
                        "dc"        : dc_raw,
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

    # DEBUG — primeiros 20 lançamentos
    log.append("─" * 60)
    log.append("DEBUG — primeiros 20 lançamentos lidos do SPED:")
    for i, lanc in enumerate(ecd.lancamentos[:20]):
        debitos  = [p for p in lanc["partidas"] if p["dc"] == "D"]
        creditos = [p for p in lanc["partidas"] if p["dc"] == "C"]
        nd, nc   = len(debitos), len(creditos)
        tipo = "X" if nd==1 and nc==1 else "D" if nd==1 and nc>1 else "C" if nc==1 and nd>1 else "V"
        debs  = ", ".join(f"{p['conta']}({p['valor']})" for p in debitos)
        creds = ", ".join(f"{p['conta']}({p['valor']})" for p in creditos)
        log.append(
            f"  [{i+1:03d}] data={lanc['data']} tipo={tipo} "
            f"D=[{debs}] C=[{creds}]"
        )
    log.append("─" * 60)

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
    if isinstance(valor_str, (int, float)):
        return float(valor_str)
    v = str(valor_str).strip()
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
    """Agrupa por (conta, dc) somando valores — mantém os lados D e C separados."""
    agrupado = {}
    for p in partidas:
        chave = (p["conta"], p["dc"])
        if chave not in agrupado:
            agrupado[chave] = {
                "conta"     : p["conta"],
                "valor"     : 0.0,
                "dc"        : p["dc"],
                "descr_hist": p.get("descr_hist", ""),
            }
        agrupado[chave]["valor"] += _str_to_float(p["valor"])
        if not agrupado[chave]["descr_hist"] and p.get("descr_hist"):
            agrupado[chave]["descr_hist"] = p["descr_hist"]
    return list(agrupado.values())


def classificar_lancamento(debitos, creditos):
    nd, nc = len(debitos), len(creditos)
    if nd == 1 and nc == 1:
        return "X"
    if nd == 1 and nc > 1:
        return "D"
    if nc == 1 and nd > 1:
        return "C"
    return "V"


# ==============================
# MONTAGEM DAS LINHAS DO LAYOUT
# ==============================

def _6100_X(data, db, cr, historico):
    """
    Tipo X — 1 débito × 1 crédito.
    6100 com débito E crédito preenchidos (único caso permitido).
    Formato: |6100|DATA|DEB|CRED|VALOR||HIST||||||
    """
    val = formatar_valor(db["valor"])
    dsc = (montar_historico(db) or historico).replace("|", " ")
    return [f"|6100|{data}|{db['conta']}|{cr['conta']}|{val}||{dsc}||||||"]


def _6100_D(data, db, creditos, historico, gerar_6110):
    """
    Tipo D — 1 débito × N créditos.

    Regra Domínio:
      6100 → só débito preenchido (crédito VAZIO)
      6110 → um registro por crédito (todos, inclusive o primeiro)

    Formato 6100: |6100|DATA|DEB||VALOR||HIST||||||
    Formato 6110: |6110||CRED|VALOR|
    """
    linhas = []
    val = formatar_valor(db["valor"])
    dsc = (montar_historico(db) or historico).replace("|", " ")
    linhas.append(f"|6100|{data}|{db['conta']}||{val}||{dsc}||||||")
    if gerar_6110:
        for cr in creditos:                          # TODOS os créditos no 6110
            vr = formatar_valor(cr["valor"])
            linhas.append(f"|6110||{cr['conta']}|{vr}|")
    return linhas


def _6100_C(data, creditos, debitos, historico, gerar_6110):
    """
    Tipo C — N débitos × 1 crédito.

    Regra Domínio:
      6100 → só crédito preenchido (débito VAZIO)
      6110 → um registro por débito (todos, inclusive o primeiro)

    Formato 6100: |6100|DATA||CRED|VALOR||HIST||||||
    Formato 6110: |6110|DEB||VALOR|
    """
    linhas = []
    cr  = creditos[0]
    val = formatar_valor(cr["valor"])
    dsc = (primeiro_historico(debitos) or historico).replace("|", " ")
    linhas.append(f"|6100|{data}||{cr['conta']}|{val}||{dsc}||||||")
    if gerar_6110:
        for db in debitos:                           # TODOS os débitos no 6110
            vr = formatar_valor(db["valor"])
            linhas.append(f"|6110|{db['conta']}||{vr}|")
    return linhas


def _6100_V(data, debitos, creditos, historico, gerar_6110):
    """
    Tipo V — N débitos × N créditos.

    Regra Domínio:
      6100 → só débito principal (crédito VAZIO)
      6110 → demais débitos + todos os créditos

    Formato 6100: |6100|DATA|DEB||VALOR||HIST||||||
    Formato 6110 débito : |6110|DEB||VALOR|
    Formato 6110 crédito: |6110||CRED|VALOR|
    """
    linhas = []
    db0 = debitos[0]
    val = formatar_valor(db0["valor"])
    dsc = (montar_historico(db0) or historico).replace("|", " ")
    linhas.append(f"|6100|{data}|{db0['conta']}||{val}||{dsc}||||||")
    if gerar_6110:
        for db in debitos[1:]:
            vr = formatar_valor(db["valor"])
            linhas.append(f"|6110|{db['conta']}||{vr}|")
        for cr in creditos:
            vr = formatar_valor(cr["valor"])
            linhas.append(f"|6110||{cr['conta']}|{vr}|")
    return linhas


# ==============================
# GERADOR DO LAYOUT DOMÍNIO — V2.0
# ==============================
def gerar_dominio(ecd, log, progress_bar, status_text, gerar_6110=True):
    """
    V2.0 — Correção definitiva da regra de preenchimento do 6100:

    ┌──────┬─────────────────────────────────────────────────────────┐
    │ Tipo │ Regra de preenchimento                                  │
    ├──────┼─────────────────────────────────────────────────────────┤
    │  X   │ 6100: DEB + CRED + VALOR   (sem 6110)                  │
    │  D   │ 6100: DEB + VAZIO + VALOR  → 6110: todos os créditos   │
    │  C   │ 6100: VAZIO + CRED + VALOR → 6110: todos os débitos    │
    │  V   │ 6100: DEB + VAZIO + VALOR  → 6110: outros D + todos C  │
    └──────┴─────────────────────────────────────────────────────────┘

    O erro "não é permitido ter débito e crédito no mesmo lançamento
    se o tipo for diferente de 'um débito para um crédito'" ocorre
    exatamente quando o 6100 tem DEB e CRED preenchidos com tipo D/C/V.
    """
    linhas      = []
    total_6100  = 0
    total_6110  = 0
    ignorados   = 0
    debug_tipos = {"X": 0, "D": 0, "C": 0, "V": 0}

    cnpj_numerico = re.sub(r"\D", "", ecd.cnpj)
    linhas.append(f"|0000|{cnpj_numerico}|")

    total_lanc = len(ecd.lancamentos)
    status_text.text(f"⚙ Gerando layout Domínio — {total_lanc:,} lançamentos...")

    for idx, lanc in enumerate(ecd.lancamentos):

        if idx % 100 == 0 or idx == total_lanc - 1:
            pct = 50 + int(((idx + 1) / total_lanc) * 50)
            progress_bar.progress(min(pct, 99))
            status_text.text(f"⚙ Gerando lançamento {idx+1:,} de {total_lanc:,}...")

        partidas_brutas = lanc.get("partidas", [])
        if not partidas_brutas:
            ignorados += 1
            continue

        partidas = agrupar_partidas_por_conta(partidas_brutas)
        debitos  = [p for p in partidas if p["dc"] == "D"]
        creditos = [p for p in partidas if p["dc"] == "C"]

        if not debitos or not creditos:
            ignorados += 1
            continue

        data      = formatar_data_dominio(lanc["data"])
        tipo      = classificar_lancamento(debitos, creditos)
        historico = primeiro_historico(partidas_brutas)
        debug_tipos[tipo] = debug_tipos.get(tipo, 0) + 1

        # ── Registro 6000 ─────────────────────────────────────────────
        linhas.append(f"|6000|{tipo}||||")

        # ── Registros 6100 / 6110 ─────────────────────────────────────
        if tipo == "X":
            novas = _6100_X(data, debitos[0], creditos[0], historico)
        elif tipo == "D":
            novas = _6100_D(data, debitos[0], creditos, historico, gerar_6110)
        elif tipo == "C":
            novas = _6100_C(data, creditos, debitos, historico, gerar_6110)
        else:
            novas = _6100_V(data, debitos, creditos, historico, gerar_6110)

        linhas.extend(novas)
        total_6100 += 1
        total_6110 += sum(1 for l in novas if l.startswith("|6110|"))

    log.append(f"Registros 6100 gerados        : {total_6100}")
    log.append(f"Registros 6110 gerados        : {total_6110}")
    log.append(
        f"Registros 6110 "
        f"{'habilitados' if gerar_6110 else 'DESABILITADOS'}"
    )
    if ignorados:
        log.append(f"Lançamentos ignorados (sem D/C): {ignorados}")
    log.append(f"Total de linhas geradas       : {len(linhas)}")
    log.append(
        f"Tipos — X:{debug_tipos['X']}  D:{debug_tipos['D']}  "
        f"C:{debug_tipos['C']}  V:{debug_tipos['V']}"
    )
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

        log.append(
            f"Gerando layout Domínio V2.0 "
            f"(6110: {'SIM' if gerar_6110 else 'NÃO'})..."
        )
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
                do Domínio Contabilidade.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
| `6100`   | Lançamento principal (12 campos) |
| `6110`   | Partidas adicionais (opcional) |
            """
        )
        st.markdown("---")
        st.markdown("### 🔀 Regras D/C/X/V — V2.0")
        st.markdown(
            """
| Tipo | 6100 | 6110 |
|------|------|------|
| **X** | DEB + CRED | — |
| **D** | DEB + vazio | todos créditos |
| **C** | vazio + CRED | todos débitos |
| **V** | DEB + vazio | outros D + todos C |
            """
        )
        st.markdown("---")
        st.markdown("### ✅ Versões")
        st.markdown(
            """
**V2.0** — Fix definitivo regra 6100/6110
- Tipo D/C/V: 6100 nunca tem DEB+CRED juntos
- Tipo D: crédito sempre vai para 6110
- Tipo C: débito sempre vai para 6110
- Tipo V: créditos sempre vão para 6110

**V1.9** — Debug de classificação

**V1.8** — Agrupamento por (conta, dc)

**V1.7** — 6100 com campos extras

**V1.6** — Soma de valores + opção 6110
            """
        )

    with st.expander("📖 **Instruções de Uso**", expanded=False):
        st.markdown(
            """
            <div class="instrucoes-box">
            <h4>🔹 Regra fundamental do layout Domínio (V2.0)</h4>
            <p>O registro <b>6100</b> só pode ter débito E crédito preenchidos
            simultaneamente quando o tipo for <b>X</b> (um débito para um crédito).
            Para os tipos D, C e V, o campo oposto fica <b>vazio</b> no 6100,
            e as partidas adicionais (incluindo a primeira do lado oposto)
            vão todas para o <b>6110</b>.</p>

            <h4>🔹 Estrutura por tipo</h4>
            <ul>
                <li><b>X</b>: <code>|6100|DATA|DEB|CRED|VALOR||HIST||||||</code></li>
                <li><b>D</b>: <code>|6100|DATA|DEB||VALOR||HIST||||||</code> + 6110 p/ cada crédito</li>
                <li><b>C</b>: <code>|6100|DATA||CRED|VALOR||HIST||||||</code> + 6110 p/ cada débito</li>
                <li><b>V</b>: <code>|6100|DATA|DEB||VALOR||HIST||||||</code> + 6110 p/ outros D e todos C</li>
            </ul>

            <h4>🔹 Passo a passo</h4>
            <ol>
                <li>Selecione o arquivo SPED ECD (<code>.txt</code>).</li>
                <li>Escolha se deseja gerar os registros <b>6110</b>.</li>
                <li>Clique em <b>▶ Converter</b> e aguarde.</li>
                <li>Verifique o log e baixe o arquivo gerado.</li>
                <li>Importe no Domínio: <b>Utilitários → Importação → Lançamentos em Lote</b>.</li>
            </ol>

            <h4>⚠ Observações</h4>
            <ul>
                <li>Partidas com mesma conta e mesmo lado (D ou C) são <b>somadas</b>.</li>
                <li>Arquivo gravado em <b>latin-1</b>.</li>
                <li>Lançamentos sem débito e crédito simultâneos são ignorados.</li>
            </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    if "log"          not in st.session_state:
        st.session_state.log          = [f"Aplicação pronta. Versão: {VERSAO}"]
    if "txt_gerado"   not in st.session_state:
        st.session_state.txt_gerado   = None
    if "nome_arquivo" not in st.session_state:
        st.session_state.nome_arquivo = "lancamentos_dominio.txt"
    if "metricas"     not in st.session_state:
        st.session_state.metricas     = {}

    arquivo = st.file_uploader(
        "Arquivo SPED ECD",
        type=["txt"],
        help="Selecione o arquivo SPED ECD exportado da sua contabilidade.",
    )

    st.markdown("#### ⚙ Opções de geração")
    col_opt1, col_opt2 = st.columns([2, 3])
    with col_opt1:
        gerar_6110 = st.toggle(
            "Gerar registros 6110 (partidas adicionais)",
            value=True,
            help="Desative se o Domínio não usa centro de custos.",
        )
    with col_opt2:
        if gerar_6110:
            st.info("✅ **6110 habilitado** — partidas adicionais (D, C, V) serão geradas.")
        else:
            st.warning("⚠ **6110 desabilitado** — apenas registros 6100 serão gerados.")

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

    if converter and arquivo is not None:
        st.session_state.log = [
            f"Iniciando conversão V2.0 (6110: {'SIM' if gerar_6110 else 'NÃO'})..."
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
            st.session_state.txt_gerado = conteudo_txt.encode("latin-1", errors="replace")

            cnpj_num = re.sub(r"\D", "", ecd.cnpj)
            sufixo   = "_com6110" if gerar_6110 else "_sem6110"
            st.session_state.nome_arquivo = (
                f"ECD_{cnpj_num}_lancamentos_dominio{sufixo}.txt"
            )

            t6000 = sum(1 for l in linhas if l.startswith("|6000|"))
            t6100 = sum(1 for l in linhas if l.startswith("|6100|"))
            t6110 = sum(1 for l in linhas if l.startswith("|6110|"))
            st.session_state.metricas = {
                "CNPJ"              : ecd.cnpj,
                "Lançamentos (6000)": t6000,
                "Linhas 6100"       : t6100,
                "Linhas 6110"       : t6110,
                "Total de linhas"   : len(linhas),
            }
        else:
            progress_bar.progress(100)
            status_text.text("❌ Falha na conversão. Verifique o log abaixo.")

        st.rerun()

    if st.session_state.metricas:
        st.markdown("#### 📊 Resumo da conversão")
        m      = st.session_state.metricas
        cols   = st.columns(5)
        for i, (k, v) in enumerate(m.items()):
            cols[i].metric(k, v)
        st.markdown("")

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

    st.markdown("**Log de processamento**")
    log_texto = "\n".join(st.session_state.log)
    tem_erro  = any(str(l).startswith("ERRO") for l in st.session_state.log)
    cor_borda = "#D32F2F" if tem_erro else "#388E3C"
    st.markdown(
        f"""
        <div style="background:#FCFCFC; border:1px solid {cor_borda};
                    border-radius:6px; padding:14px;
                    font-family:Consolas,monospace; font-size:13px;
                    white-space:pre-wrap; max-height:500px;
                    overflow-y:auto; color:#1F1F1F;">
{log_texto}
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
