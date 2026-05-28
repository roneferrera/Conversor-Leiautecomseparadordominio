import re
import traceback
import unicodedata
import streamlit as st

VERSAO = "V3.1"

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
# NORMALIZACAO
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
        log.append("Aviso: encoding nao identificado; usando UTF-8 com substituicao.")

    linhas_lista = texto.splitlines()
    total        = len(linhas_lista) or 1
    status_text.text("Lendo registros do SPED ECD...")

    for num_linha, linha in enumerate(linhas_lista, start=1):
        if num_linha % 500 == 0 or num_linha == total:
            pct = int((num_linha / total) * 50)
            progress_bar.progress(pct)
            status_text.text(f"Lendo linha {num_linha:,} de {total:,}...")

        linha = linha.strip()
        if not linha:
            continue

        campos   = _split_pipe(linha)
        if not campos:
            continue
        registro = campos[0]

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
                if lote_atual is None:
                    continue
                if len(campos) <= 4:
                    continue
                dc_raw = campos[4].strip().upper()
                if dc_raw not in ("D", "C"):
                    log.append(
                        f"Aviso linha {num_linha}: I250 dc='{dc_raw}' invalido - ignorado."
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
        log.append("ERRO: CNPJ nao encontrado no registro 0000.")
        return None

    log.append(f"Leitura concluida - CNPJ: {ecd.cnpj}")
    log.append(f"  Contas carregadas : {len(ecd.contas)}")
    log.append(f"  Historicos (I075) : {len(ecd.historicos)}")
    log.append(f"  Lancamentos (I200): {len(ecd.lancamentos)}")

    log.append("-" * 60)
    log.append("DEBUG - primeiros 10 lancamentos:")
    for i, lanc in enumerate(ecd.lancamentos[:10]):
        debs  = [p for p in lanc["partidas"] if p["dc"] == "D"]
        creds = [p for p in lanc["partidas"] if p["dc"] == "C"]
        nd, nc = len(debs), len(creds)
        tipo = ("X" if nd == 1 and nc == 1 else
                "D" if nd == 1 and nc > 1  else
                "C" if nc == 1 and nd > 1  else
                "V" if nd > 1  and nc > 1  else "?")
        ds = ", ".join(f"{p['conta']}({p['valor']})" for p in debs)
        cs = ", ".join(f"{p['conta']}({p['valor']})" for p in creds)
        log.append(f"  [{i+1:03d}] {lanc['data']} tipo={tipo} D=[{ds}] C=[{cs}]")
    log.append("-" * 60)

    return ecd


# ==============================
# FUNCOES AUXILIARES
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
# MONTAGEM DAS LINHAS — V3.1
# ==============================

def _fmt6100_x(data, conta_deb, conta_cred, valor, hist):
    """
    Tipo X — debito E credito na mesma linha.
    |6100|DATA|DEB|CRED|VALOR||HIST|||||||
    """
    h = (hist or "").replace("|", " ").strip()
    return f"|6100|{data}|{conta_deb}|{conta_cred}|{valor}||{h}|||||||"


def _fmt6100_debito(data, conta, valor, hist):
    """
    Tipos D/C/V — linha somente de debito.
    |6100|DATA|DEB||VALOR||HIST|||||||
    """
    h = (hist or "").replace("|", " ").strip()
    return f"|6100|{data}|{conta}||{valor}||{h}|||||||"


def _fmt6100_credito(data, conta, valor, hist):
    """
    Tipos D/C/V — linha somente de credito.
    |6100|DATA||CRED|VALOR||HIST|||||||
    """
    h = (hist or "").replace("|", " ").strip()
    return f"|6100|{data}||{conta}|{valor}||{h}|||||||"


def gerar_linhas_lancamento(lanc):
    """
    Gera 6000 + 6100(s) para um lancamento.

    Regras V3.1:
      X -> 6000 + 1 linha 6100 com DEB+CRED+VALOR na mesma linha
      D -> 6000 + 1 linha 6100 somente debito + N linhas 6100 somente credito
      C -> 6000 + N linhas 6100 somente debito + 1 linha 6100 somente credito
      V -> 6000 + N linhas 6100 somente debito + N linhas 6100 somente credito
    """
    partidas = agrupar_partidas_por_conta(lanc["partidas"])
    debs  = [p for p in partidas if p["dc"] == "D"]
    creds = [p for p in partidas if p["dc"] == "C"]

    if not debs or not creds:
        return []

    data = formatar_data_dominio(lanc["data"])
    tipo = classificar(debs, creds)
    hist = primeiro_historico(lanc["partidas"])

    out = [f"|6000|{tipo}||||"]

    if tipo == "X":
        # Uma unica linha com debito E credito juntos
        db  = debs[0]
        cr  = creds[0]
        val = formatar_valor(db["valor"])
        h   = montar_historico(db) or hist
        out.append(_fmt6100_x(data, db["conta"], cr["conta"], val, h))

    else:
        # D, C ou V — uma linha por debito, uma linha por credito
        for db in debs:
            val = formatar_valor(db["valor"])
            h   = montar_historico(db) or hist
            out.append(_fmt6100_debito(data, db["conta"], val, h))

        for cr in creds:
            val = formatar_valor(cr["valor"])
            h   = montar_historico(cr) or hist
            out.append(_fmt6100_credito(data, cr["conta"], val, h))

    return out


# ==============================
# GERADOR PRINCIPAL
# ==============================
def gerar_dominio(ecd, log, progress_bar, status_text):
    linhas      = []
    t6000 = t6100 = ignorados = 0
    debug_tipos = {"X": 0, "D": 0, "C": 0, "V": 0}

    cnpj_num = re.sub(r"\D", "", ecd.cnpj)
    linhas.append(f"|0000|{cnpj_num}|")

    total = len(ecd.lancamentos)
    status_text.text(f"Gerando {total:,} lancamentos...")

    for idx, lanc in enumerate(ecd.lancamentos):
        if idx % 100 == 0 or idx == total - 1:
            pct = 50 + int(((idx + 1) / total) * 50)
            progress_bar.progress(min(pct, 99))
            status_text.text(f"Lancamento {idx+1:,} de {total:,}...")

        if not lanc.get("partidas"):
            ignorados += 1
            continue

        novas = gerar_linhas_lancamento(lanc)
        if not novas:
            ignorados += 1
            continue

        for l in novas:
            if l.startswith("|6000|"):
                t = l.split("|")[2] if len(l.split("|")) > 2 else "?"
                debug_tipos[t] = debug_tipos.get(t, 0) + 1
                t6000 += 1
            elif l.startswith("|6100|"):
                t6100 += 1

        linhas.extend(novas)

    log.append(f"Registros 6000 : {t6000}")
    log.append(f"Registros 6100 : {t6100}")
    log.append(f"Ignorados      : {ignorados}")
    log.append(f"Total linhas   : {len(linhas)}")
    log.append(
        f"Tipos - X:{debug_tipos.get('X',0)} D:{debug_tipos.get('D',0)} "
        f"C:{debug_tipos.get('C',0)} V:{debug_tipos.get('V',0)}"
    )
    return linhas


# ==============================
# PIPELINE
# ==============================
def converter_sped_ecd(conteudo_bytes, log, progress_bar, status_text):
    try:
        ecd = parse_sped_ecd(conteudo_bytes, log, progress_bar, status_text)
        if ecd is None:
            return None, None
        linhas = gerar_dominio(ecd, log, progress_bar, status_text)
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
        page_title="Dominio Sistemas | Thomson Reuters",
        page_icon="🟠",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_tr_theme()

    st.markdown(f"""
        <div style="background:#444444;padding:24px 28px 18px;border-radius:8px;
                    border-top:6px solid #FF8000;margin-bottom:28px;">
            <h2 style="color:#FF8000;margin:0;font-family:'Segoe UI',Arial,sans-serif;">
                Conversor SPED ECD para Lancamentos em Lote | {VERSAO}
            </h2>
            <p style="color:#DDDDDD;margin:6px 0 0;font-family:'Segoe UI',Arial,sans-serif;">
                Selecione o arquivo SPED ECD e clique em <strong>Converter</strong>.
            </p>
        </div>""", unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(
            f"### Sobre\n**Versao:** {VERSAO}\n\n**Thomson Reuters - Dominio Sistemas**"
        )
        st.markdown("---")
        st.markdown("""### Estrutura gerada
**Tipo X** (1 debito, 1 credito):

                    st.markdown("---")
        st.markdown("""### Tipos X/D/C/V
| Tipo | Regra |
|------|-------|
| X | 1 debito, 1 credito |
| D | 1 debito, N creditos |
| C | N debitos, 1 credito |
| V | N debitos, N creditos |""")
        st.markdown("---")
        st.markdown("""### Versoes
**V3.1** - Tipo X em uma linha
- X: DEB+CRED na mesma linha 6100
- D/C/V: uma linha 6100 por partida

**V3.0** - Arquitetura correta (1 linha por partida)

**V2.1** - Fix parse I200/I250""")

    with st.expander("Instrucoes de Uso", expanded=False):
        st.markdown("""
        <div class="instrucoes-box">
        <h4>Regras de geracao (V3.1)</h4>
        <ul>
            <li><b>Tipo X</b>: uma unica linha 6100 com debito E credito preenchidos.</li>
            <li><b>Tipos D, C, V</b>: uma linha 6100 por partida — debitos com campo
            credito vazio, creditos com campo debito vazio.</li>
        </ul>

        <h4>Exemplo tipo X</h4>
        <pre>|6000|X||||
|6100|07/01/2022|686|10001|4287,68||Historico|||||||</pre>

        <h4>Exemplo tipo D (1 debito, 2 creditos)</h4>
        <pre>|6000|D||||
|6100|07/01/2022|686||4287,68||Historico|||||||
|6100|07/01/2022||10001|4223,36||Historico|||||||
|6100|07/01/2022||178|64,32||Historico|||||||</pre>

        <h4>Passo a passo</h4>
        <ol>
            <li>Selecione o arquivo SPED ECD.</li>
            <li>Clique em Converter.</li>
            <li>Verifique o log e baixe o arquivo.</li>
            <li>Importe no Dominio: Utilitarios, Importacao, Lancamentos em Lote.</li>
        </ol>

        <h4>Observacoes</h4>
        <ul>
            <li>Partidas com mesma conta e mesmo lado (D ou C) sao somadas.</li>
            <li>Arquivo gravado em latin-1.</li>
            <li>Lancamentos sem debito e credito simultaneos sao ignorados.</li>
        </ul>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    for k, v in [
        ("log", [f"Pronto. Versao: {VERSAO}"]),
        ("txt_gerado", None),
        ("nome_arquivo", "lancamentos.txt"),
        ("metricas", {}),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

    arquivo = st.file_uploader("Arquivo SPED ECD", type=["txt"])

    st.markdown("")
    b1, b2 = st.columns(2)
    with b1:
        converter = st.button(
            "Converter",
            disabled=(arquivo is None),
            use_container_width=True,
            type="primary",
        )
    with b2:
        limpar = st.button("Limpar", use_container_width=True)

    if limpar:
        st.session_state.log          = ["Limpo."]
        st.session_state.txt_gerado   = None
        st.session_state.nome_arquivo = "lancamentos.txt"
        st.session_state.metricas     = {}
        st.rerun()

    if converter and arquivo:
        st.session_state.log        = ["Iniciando V3.1..."]
        st.session_state.txt_gerado = None
        st.session_state.metricas   = {}

        status_text  = st.empty()
        progress_bar = st.progress(0)

        linhas, ecd = converter_sped_ecd(
            arquivo.read(),
            st.session_state.log,
            progress_bar,
            status_text,
        )

        if linhas and ecd:
            progress_bar.progress(100)
            status_text.text("Concluido!")
            txt = "\n".join(linhas) + "\n"
            st.session_state.txt_gerado = txt.encode("latin-1", errors="replace")
            cnpj = re.sub(r"\D", "", ecd.cnpj)
            st.session_state.nome_arquivo = f"ECD_{cnpj}_dominio_V3.1.txt"
            st.session_state.metricas = {
                "CNPJ"        : ecd.cnpj,
                "Lanc. (6000)": sum(1 for l in linhas if l.startswith("|6000|")),
                "Linhas 6100" : sum(1 for l in linhas if l.startswith("|6100|")),
                "Total linhas": len(linhas),
            }
        else:
            progress_bar.progress(100)
            status_text.text("Falha - veja o log.")
        st.rerun()

    if st.session_state.metricas:
        st.markdown("#### Resumo")
        cols = st.columns(4)
        for i, (k, v) in enumerate(st.session_state.metricas.items()):
            cols[i].metric(k, v)

    if st.session_state.txt_gerado:
        st.success("Arquivo gerado com sucesso!")
        st.download_button(
            "Baixar arquivo convertido",
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
