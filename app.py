import re
import traceback
import unicodedata
import streamlit as st

VERSAO = "V2.1"

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
# NORMALIZAÇÃO
# ==============================
_MAPA_ESPECIAIS = {
    "\u2018": "'", "\u2019": "'",
    "\u201C": '"', "\u201D": '"',
    "\u2013": "-", "\u2014": "-",
    "\u2026": "...", "\u00A0": " ",
    "\u00D7": "x", "\u00F7": "/",
    "\u20AC": "EUR", "\u00A7": "S/",
    "\u00AE": "(R)", "\u00A9": "(C)",
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
# PARSE DO SPED ECD — V2.1
# ==============================
def _split_pipe(linha):
    """
    Divide a linha pelo pipe e remove os delimitadores externos vazios.
    Ex: |I200|001|07012022|4287,68| → ['I200','001','07012022','4287,68']
    """
    campos = linha.strip().split("|")
    if campos and campos[0] == "":
        campos = campos[1:]
    if campos and campos[-1] == "":
        campos = campos[:-1]
    return campos


def parse_sped_ecd(conteudo_bytes, log, progress_bar, status_text):
    """
    V2.1 — Parse robusto do SPED ECD.

    Hierarquia do SPED ECD relevante para lançamentos:
        I150 → Cabeçalho do lote de lançamentos
        I200 → Lançamento (1 por lote)
        I250 → Partidas do lançamento (N por I200)
        I299 → Encerramento do lote (fecha o I150)

    IMPORTANTE: cada I200 é um lançamento independente.
    As partidas I250 pertencem EXCLUSIVAMENTE ao I200 imediatamente anterior.
    O código garante isso zerando lote_atual a cada novo I200 e nunca
    acumulando partidas de I200 diferentes.
    """
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
        if not campos:
            continue
        registro = campos[0]

        try:
            # ── Identificação da empresa ──────────────────────────────────
            if registro == "0000":
                if len(campos) > 5:
                    ecd.cnpj = campos[5].strip()

            # ── Plano de contas ───────────────────────────────────────────
            elif registro == "I050":
                if len(campos) > 7:
                    cod  = campos[5].strip()
                    nome = campos[7].strip()
                    if cod:
                        ecd.contas[cod] = nome

            # ── Históricos padronizados ───────────────────────────────────
            elif registro == "I075":
                if len(campos) > 2:
                    cod   = campos[1].strip()
                    descr = normalizar_historico(campos[2])
                    ecd.historicos[cod] = descr

            # ── Novo lançamento: SEMPRE cria lote novo e limpa partidas ───
            elif registro == "I200":
                # Fecha o lote anterior — não carrega nada para o próximo
                lote_atual = {
                    "num"     : campos[1].strip() if len(campos) > 1 else "",
                    "data"    : campos[2].strip() if len(campos) > 2 else "",
                    "valor"   : campos[3].strip() if len(campos) > 3 else "",
                    "partidas": [],   # lista LIMPA — exclusiva deste I200
                }
                ecd.lancamentos.append(lote_atual)

            # ── Partida: só adiciona ao lote ATUAL (I200 imediatamente anterior) ──
            elif registro == "I250":
                if lote_atual is None:
                    # I250 sem I200 pai — ignorar
                    continue
                if len(campos) <= 4:
                    continue
                dc_raw = campos[4].strip().upper()
                if dc_raw not in ("D", "C"):
                    log.append(
                        f"Aviso linha {num_linha}: I250 dc='{dc_raw}' inválido — ignorado."
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

            # ── Encerramento do lote: fecha o I200 atual ──────────────────
            elif registro in ("I299", "I300"):
                lote_atual = None

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

    # ── DEBUG: primeiros 20 lançamentos ──────────────────────────────────
    log.append("─" * 60)
    log.append("DEBUG — primeiros 20 lançamentos após parse:")
    for i, lanc in enumerate(ecd.lancamentos[:20]):
        debs  = [p for p in lanc["partidas"] if p["dc"] == "D"]
        creds = [p for p in lanc["partidas"] if p["dc"] == "C"]
        nd, nc = len(debs), len(creds)
        tipo = ("X" if nd==1 and nc==1 else
                "D" if nd==1 and nc>1  else
                "C" if nc==1 and nd>1  else
                "V" if nd>1  and nc>1  else "?")
        ds = ", ".join(f"{p['conta']}({p['valor']})" for p in debs)
        cs = ", ".join(f"{p['conta']}({p['valor']})" for p in creds)
        log.append(
            f"  [{i+1:03d}] {lanc['data']} tipo={tipo} "
            f"D=[{ds}] C=[{cs}]"
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


def formatar_valor(v):
    if isinstance(v, float):
        return f"{v:.2f}".replace(".", ",")
    v = str(v).strip()
    if "." in v and "," not in v:
        v = v.replace(".", ",")
    elif "." in v and "," in v:
        if v.index(".") < v.index(","):
            v = v.replace(".", "").replace(",", ".")
            v = v.replace(".", ",")
    if "," not in v:
        v += ",00"
    else:
        p = v.split(",")
        if len(p[1]) < 2:
            p[1] = p[1].ljust(2, "0")
        v = ",".join(p)
    return v


def _str_to_float(v):
    if isinstance(v, (int, float)):
        return float(v)
    v = str(v).strip()
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


def montar_historico(p):
    return p.get("descr_hist", "").strip()


def primeiro_historico(partidas):
    for p in partidas:
        h = montar_historico(p)
        if h:
            return h
    return ""


def agrupar_partidas_por_conta(partidas):
    """
    Agrupa por (conta, dc) somando valores.
    Mantém os lados D e C sempre separados.
    """
    ag = {}
    for p in partidas:
        chave = (p["conta"], p["dc"])
        if chave not in ag:
            ag[chave] = {
                "conta"     : p["conta"],
                "valor"     : 0.0,
                "dc"        : p["dc"],
                "descr_hist": p.get("descr_hist", ""),
            }
        ag[chave]["valor"] += _str_to_float(p["valor"])
        if not ag[chave]["descr_hist"] and p.get("descr_hist"):
            ag[chave]["descr_hist"] = p["descr_hist"]
    return list(ag.values())


def classificar(debs, creds):
    nd, nc = len(debs), len(creds)
    if nd == 1 and nc == 1: return "X"
    if nd == 1 and nc > 1:  return "D"
    if nc == 1 and nd > 1:  return "C"
    return "V"


# ==============================
# MONTAGEM DAS LINHAS — V2.1
# ==============================
# Layout Domínio 6100 — 13 campos internos (14 pipes no total):
# REG|DATA|COD_DEB|COD_CRED|VALOR|COD_HIST|COMPLEMENTO|NUM_DOC|
# COD_MOEDA|TAXA|NUM_LANC|IND_CTA_PART|TIPO_MOEDA|
#
# Resultado tipo X : |6100|DATA|DEB|CRED|VALOR||HIST|||||||
# Resultado tipo D : |6100|DATA|DEB||VALOR||HIST|||||||
# Resultado tipo C : |6100|DATA||CRED|VALOR||HIST|||||||
# Resultado tipo V : |6100|DATA|DEB||VALOR||HIST|||||||
#
# Total de pipes: 14 (13 separadores + 2 externos = 14 pipes visíveis)

def _fmt6100(data, deb, cred, valor, hist):
    """
    Gera linha 6100 com 13 campos internos (14 pipes).
    deb  = código da conta débito  ou "" se vazio
    cred = código da conta crédito ou "" se vazio
    """
    h = (hist or "").replace("|", " ").strip()
    return f"|6100|{data}|{deb}|{cred}|{valor}||{h}|||||||"


def gerar_linhas_lancamento(lanc, gerar_6110):
    """
    Retorna lista de strings (6000 + 6100 + 6110) para um lançamento.

    Regras Domínio:
    ┌──────┬──────────────────────────────┬─────────────────────────────┐
    │ Tipo │ 6100                         │ 6110                        │
    ├──────┼──────────────────────────────┼─────────────────────────────┤
    │  X   │ DEB + CRED + VALOR           │ nenhum                      │
    │  D   │ DEB + "" + VALOR             │ todos os créditos           │
    │  C   │ "" + CRED + VALOR            │ todos os débitos            │
    │  V   │ DEB_principal + "" + VALOR   │ demais D + todos os C       │
    └──────┴──────────────────────────────┴─────────────────────────────┘
    """
    partidas = agrupar_partidas_por_conta(lanc["partidas"])
    debs  = [p for p in partidas if p["dc"] == "D"]
    creds = [p for p in partidas if p["dc"] == "C"]

    if not debs or not creds:
        return []

    data = formatar_data_dominio(lanc["data"])
    tipo = classificar(debs, creds)
    hist = primeiro_historico(lanc["partidas"])
    out  = [f"|6000|{tipo}||||"]

    if tipo == "X":
        db = debs[0];  cr = creds[0]
        val = formatar_valor(db["valor"])
        h   = montar_historico(db) or hist
        out.append(_fmt6100(data, db["conta"], cr["conta"], val, h))

    elif tipo == "D":
        db  = debs[0]
        val = formatar_valor(db["valor"])
        h   = montar_historico(db) or hist
        out.append(_fmt6100(data, db["conta"], "", val, h))
        if gerar_6110:
            for cr in creds:
                out.append(f"|6110||{cr['conta']}|{formatar_valor(cr['valor'])}|")

    elif tipo == "C":
        cr  = creds[0]
        val = formatar_valor(cr["valor"])
        h   = primeiro_historico(lanc["partidas"])
        out.append(_fmt6100(data, "", cr["conta"], val, h))
        if gerar_6110:
            for db in debs:
                out.append(f"|6110|{db['conta']}||{formatar_valor(db['valor'])}|")

    else:  # V
        db0 = debs[0]
        val = formatar_valor(db0["valor"])
        h   = montar_historico(db0) or hist
        out.append(_fmt6100(data, db0["conta"], "", val, h))
        if gerar_6110:
            for db in debs[1:]:
                out.append(f"|6110|{db['conta']}||{formatar_valor(db['valor'])}|")
            for cr in creds:
                out.append(f"|6110||{cr['conta']}|{formatar_valor(cr['valor'])}|")

    return out


# ==============================
# GERADOR PRINCIPAL — V2.1
# ==============================
def gerar_dominio(ecd, log, progress_bar, status_text, gerar_6110=True):
    linhas     = []
    t6100 = t6110 = ignorados = 0
    debug_tipos = {"X": 0, "D": 0, "C": 0, "V": 0}

    cnpj_num = re.sub(r"\D", "", ecd.cnpj)
    linhas.append(f"|0000|{cnpj_num}|")

    total = len(ecd.lancamentos)
    status_text.text(f"⚙ Gerando {total:,} lançamentos...")

    for idx, lanc in enumerate(ecd.lancamentos):
        if idx % 100 == 0 or idx == total - 1:
            pct = 50 + int(((idx + 1) / total) * 50)
            progress_bar.progress(min(pct, 99))
            status_text.text(f"⚙ Lançamento {idx+1:,} de {total:,}...")

        if not lanc.get("partidas"):
            ignorados += 1
            continue

        novas = gerar_linhas_lancamento(lanc, gerar_6110)
        if not novas:
            ignorados += 1
            continue

        # Detecta tipo para estatística
        for l in novas:
            if l.startswith("|6000|"):
                t = l.split("|")[2]
                debug_tipos[t] = debug_tipos.get(t, 0) + 1
            elif l.startswith("|6100|"):
                t6100 += 1
            elif l.startswith("|6110|"):
                t6110 += 1

        linhas.extend(novas)

    log.append(f"Registros 6100 : {t6100}")
    log.append(f"Registros 6110 : {t6110} ({'habilitados' if gerar_6110 else 'DESABILITADOS'})")
    log.append(f"Ignorados      : {ignorados}")
    log.append(f"Total linhas   : {len(linhas)}")
    log.append(
        f"Tipos — X:{debug_tipos.get('X',0)} D:{debug_tipos.get('D',0)} "
        f"C:{debug_tipos.get('C',0)} V:{debug_tipos.get('V',0)}"
    )
    return linhas


# ==============================
# PIPELINE
# ==============================
def converter_sped_ecd(conteudo_bytes, log, progress_bar, status_text, gerar_6110=True):
    try:
        ecd = parse_sped_ecd(conteudo_bytes, log, progress_bar, status_text)
        if ecd is None:
            return None, None
        linhas = gerar_dominio(ecd, log, progress_bar, status_text, gerar_6110)
        if not linhas:
            log.append("ERRO: Nenhuma linha gerada.")
            return None, None
        return linhas, ecd
    except Exception:
        log.append("ERRO FATAL:")
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

    st.markdown(f"""
        <div style="background:#444444;padding:24px 28px 18px;border-radius:8px;
                    border-top:6px solid #FF8000;margin-bottom:28px;">
            <h2 style="color:#FF8000;margin:0;font-family:'Segoe UI',Arial,sans-serif;">
                📒 Conversor SPED ECD → Lançamentos em Lote &nbsp;|&nbsp; {VERSAO}
            </h2>
            <p style="color:#DDDDDD;margin:6px 0 0;font-family:'Segoe UI',Arial,sans-serif;">
                Selecione o arquivo SPED ECD e clique em <strong>▶ Converter</strong>.
            </p>
        </div>""", unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(f"### ℹ Sobre\n**Versão:** {VERSAO}\n\n**Thomson Reuters — Domínio Sistemas**")
        st.markdown("---")
        st.markdown("""### 📋 Registros gerados
| Registro | Descrição |
|----------|-----------|
| `0000` | CNPJ |
| `6000` | Tipo X/D/C/V |
| `6100` | Lançamento (13 campos) |
| `6110` | Partidas adicionais |""")
        st.markdown("---")
        st.markdown("""### 🔀 Regras D/C/X/V — V2.1
| Tipo | 6100 | 6110 |
|------|------|------|
| **X** | DEB+CRED | — |
| **D** | DEB+vazio | todos créditos |
| **C** | vazio+CRED | todos débitos |
| **V** | DEB+vazio | outros D+todos C |""")
        st.markdown("---")
        st.markdown("""### ✅ Versões
**V2.1** — Fix parse I200/I250
- I299/I300 fecha o lote atual
- Partidas nunca vazam entre lançamentos
- 6100 com 13 campos (14 pipes)

**V2.0** — Fix regra DEB/CRED no 6100

**V1.9** — Debug de classificação

**V1.8** — Agrupamento por (conta,dc)""")

    with st.expander("📖 Instruções de Uso", expanded=False):
        st.markdown("""
        <div class="instrucoes-box">
        <h4>🔹 Como funciona o parse (V2.1)</h4>
        <p>Cada registro <code>I200</code> do SPED ECD representa um lançamento independente.
        Os registros <code>I250</code> seguintes pertencem <b>exclusivamente</b> a esse I200.
        Quando um novo I200 ou I299/I300 é encontrado, o lote anterior é fechado.
        Isso evita que partidas de lançamentos diferentes se misturem.</p>

        <h4>🔹 Estrutura do 6100 (V2.1)</h4>
        <p><code>|6100|DATA|DEB|CRED|VALOR||HIST|||||||</code><br>
        13 campos internos = 14 pipes totais.</p>

        <h4>🔹 Passo a passo</h4>
        <ol>
            <li>Selecione o arquivo SPED ECD.</li>
            <li>Escolha se gera 6110.</li>
            <li>Clique em <b>▶ Converter</b>.</li>
            <li>Verifique o DEBUG no log — mostra os primeiros 20 lançamentos com D/C detectados.</li>
            <li>Importe no Domínio: <b>Utilitários → Importação → Lançamentos em Lote</b>.</li>
        </ol>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    for k, v in [("log", [f"Pronto. Versão: {VERSAO}"]),
                 ("txt_gerado", None), ("nome_arquivo", "lancamentos.txt"),
                 ("metricas", {})]:
        if k not in st.session_state:
            st.session_state[k] = v

    arquivo = st.file_uploader("Arquivo SPED ECD", type=["txt"])

    st.markdown("#### ⚙ Opções")
    c1, c2 = st.columns([2, 3])
    with c1:
        gerar_6110 = st.toggle("Gerar registros 6110", value=True,
            help="Desative se o Domínio não usa centro de custos.")
    with c2:
        if gerar_6110:
            st.info("✅ 6110 habilitado.")
        else:
            st.warning("⚠ 6110 desabilitado — só 6100 será gerado.")

    st.markdown("")
    b1, b2 = st.columns(2)
    with b1:
        converter = st.button("▶ Converter", disabled=(arquivo is None),
                              use_container_width=True, type="primary")
    with b2:
        limpar = st.button("🗑 Limpar", use_container_width=True)

    if limpar:
        st.session_state.log          = ["Limpo."]
        st.session_state.txt_gerado   = None
        st.session_state.nome_arquivo = "lancamentos.txt"
        st.session_state.metricas     = {}
        st.rerun()

    if converter and arquivo:
        st.session_state.log        = [f"Iniciando V2.1 (6110={'SIM' if gerar_6110 else 'NÃO'})..."]
        st.session_state.txt_gerado = None
        st.session_state.metricas   = {}

        status_text  = st.empty()
        progress_bar = st.progress(0)

        linhas, ecd = converter_sped_ecd(
            arquivo.read(), st.session_state.log,
            progress_bar, status_text, gerar_6110
        )

        if linhas and ecd:
            progress_bar.progress(100)
            status_text.text("✅ Concluído!")
            txt = "\n".join(linhas) + "\n"
            st.session_state.txt_gerado = txt.encode("latin-1", errors="replace")
            cnpj = re.sub(r"\D", "", ecd.cnpj)
            sfx  = "_com6110" if gerar_6110 else "_sem6110"
            st.session_state.nome_arquivo = f"ECD_{cnpj}_dominio{sfx}.txt"
            st.session_state.metricas = {
                "CNPJ"        : ecd.cnpj,
                "Lanç. (6000)": sum(1 for l in linhas if l.startswith("|6000|")),
                "Linhas 6100" : sum(1 for l in linhas if l.startswith("|6100|")),
                "Linhas 6110" : sum(1 for l in linhas if l.startswith("|6110|")),
                "Total linhas": len(linhas),
            }
        else:
            progress_bar.progress(100)
            status_text.text("❌ Falha — veja o log.")
        st.rerun()

    if st.session_state.metricas:
        st.markdown("#### 📊 Resumo")
        cols = st.columns(5)
        for i, (k, v) in enumerate(st.session_state.metricas.items()):
            cols[i].metric(k, v)

    if st.session_state.txt_gerado:
        st.success("✅ Arquivo gerado com sucesso!")
        st.download_button(
            "⬇ Baixar arquivo convertido",
            data=st.session_state.txt_gerado,
            file_name=st.session_state.nome_arquivo,
            mime="text/plain",
            use_container_width=True,
            type="primary",
        )

    st.markdown("**Log de processamento**")
    log_txt  = "\n".join(st.session_state.log)
    tem_erro = any(str(l).startswith("ERRO") for l in st.session_state.log)
    cor      = "#D32F2F" if tem_erro else "#388E3C"
    st.markdown(f"""
        <div style="background:#FCFCFC;border:1px solid {cor};border-radius:6px;
                    padding:14px;font-family:Consolas,monospace;font-size:13px;
                    white-space:pre-wrap;max-height:500px;overflow-y:auto;color:#1F1F1F;">
{log_txt}
        </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
