import re
import traceback
import unicodedata
import streamlit as st

# ==============================
# VERSÃO
# ==============================
VERSAO = "V1.3"

# ==============================
# CONTAS TEMPORÁRIAS DO SPED
# (não existem no plano de contas do Domínio)
# ==============================
CONTAS_IGNORAR = {
    "5000", "5001", "5002", "5003", "5004",
    "10000", "10001", "10002", "10003",
}

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
        self.contas      = {}   # cod_reduzido -> nome
        self.historicos  = {}   # cod -> descricao (I075)
        self.lancamentos = []   # lista de dicts com I200 + I250


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
    """
    Normaliza o histórico para compatibilidade com o Domínio Sistemas (latin-1).
    Preserva letras acentuadas do português: á é í ó ú â ê ô ã õ ç ü etc.
    """
    if not texto:
        return ""

    # Substituições explícitas
    for orig, dest in _MAPA_ESPECIAIS.items():
        texto = texto.replace(orig, dest)

    # Normalização NFC
    texto = unicodedata.normalize("NFC", texto)

    # Filtra caractere a caractere para latin-1
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

    # Detecta encoding
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
            # ---- 0000 – Identificação da empresa ----
            if registro == "0000":
                # |0000|LECD|DT_INI|DT_FIN|NOME|CNPJ|...
                if len(campos) > 5:
                    ecd.cnpj = campos[5].strip()

            # ---- I050 – Plano de contas ----
            elif registro == "I050":
                if len(campos) > 7:
                    cod  = campos[5].strip()
                    nome = campos[7].strip()
                    if cod:
                        ecd.contas[cod] = nome

            # ---- I075 – Históricos padrão ----
            elif registro == "I075":
                if len(campos) > 2:
                    cod   = campos[1].strip()
                    descr = normalizar_historico(campos[2])
                    ecd.historicos[cod] = descr

            # ---- I200 – Cabeçalho do lançamento ----
            elif registro == "I200":
                if len(campos) > 3:
                    lote_atual = {
                        "num"     : campos[1].strip(),
                        "data"    : campos[2].strip(),
                        "valor"   : campos[3].strip(),
                        "partidas": [],
                    }
                    ecd.lancamentos.append(lote_atual)

            # ---- I250 – Partidas do lançamento ----
            elif registro == "I250":
                if lote_atual is not None and len(campos) > 4:
                    partida = {
                        "conta"     : campos[1].strip(),
                        "valor"     : campos[3].strip(),
                        "dc"        : campos[4].strip().upper(),
                        # ▼ Não passa o código; usa só a descrição livre
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
    """DDMMAAAA → DD/MM/AAAA. Mantém se já tiver barra."""
    d = data_sped.strip()
    if "/" in d:
        return d
    if len(d) == 8 and d.isdigit():
        return f"{d[0:2]}/{d[2:4]}/{d[4:8]}"
    return d


def formatar_valor(valor_str):
    """Garante separador decimal com vírgula e pelo menos duas casas decimais."""
    v = valor_str.strip()
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


def tem_conta_ignorada(partidas):
    """Retorna True se qualquer partida usa conta temporária do SPED."""
    for p in partidas:
        if p["conta"] in CONTAS_IGNORAR:
            return True
    return False


def primeiro_historico_livre(partidas):
    """
    Retorna a primeira descrição livre não-vazia das partidas.
    NÃO usa código de histórico — vai apenas o texto descritivo.
    """
    for p in partidas:
        d = p.get("descr_hist", "").strip()
        if d:
            return d
    return ""


def identificar_tipo_lancamento(debitos, creditos):
    """
    X = 1 débito × 1 crédito
    D = 1 débito × vários créditos
    C = vários débitos × 1 crédito
    V = vários débitos × vários créditos
    """
    nd, nc = len(debitos), len(creditos)
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
def gerar_dominio(ecd, log, progress_bar, status_text):
    """
    Gera as linhas do layout Domínio Sistemas.
    Registros: 0000 / 6000 / 6100 / 6110

    Correções V1.3:
    - Campo 6 do 6100 sempre vazio (evita erro 'histórico não cadastrado')
    - Campo 7 do 6100 recebe apenas a descrição livre (normalizada em latin-1)
    - Lançamentos com contas temporárias (5000,5001,10000,10001…) são ignorados
    - Encoding de saída: latin-1 (sem mojibake)
    """
    linhas     = []
    total_6100 = 0
    total_6110 = 0
    ignorados  = 0
    ignorados_conta = 0

    # Registro 0000
    cnpj_numerico = re.sub(r"\D", "", ecd.cnpj)
    linhas.append(f"|0000|{cnpj_numerico}|")

    total_lanc = len(ecd.lancamentos)
    status_text.text(f"⚙ Gerando layout Domínio — {total_lanc:,} lançamentos...")

    for idx, lanc in enumerate(ecd.lancamentos):

        # Progresso fase 2: 50% → 99%
        if idx % 100 == 0 or idx == total_lanc - 1:
            pct = 50 + int(((idx + 1) / total_lanc) * 50)
            progress_bar.progress(min(pct, 99))
            status_text.text(
                f"⚙ Gerando lançamento {idx + 1:,} de {total_lanc:,}..."
            )

        partidas = lanc.get("partidas", [])
        if not partidas:
            ignorados += 1
            continue

        # Ignora lançamentos com contas temporárias do SPED
        if tem_conta_ignorada(partidas):
            ignorados_conta += 1
            continue

        debitos  = [p for p in partidas if p["dc"] == "D"]
        creditos = [p for p in partidas if p["dc"] == "C"]

        if not debitos or not creditos:
            ignorados += 1
            continue

        data      = formatar_data_dominio(lanc["data"])
        tipo_lanc = identificar_tipo_lancamento(debitos, creditos)

        # Histórico: apenas descrição livre, sem código
        historico = primeiro_historico_livre(partidas)

        # ---- Registro 6000 ----
        # |6000|TIPO|COD_LANC_PADRAO|LOCALIZADOR|RTT_FCONT|
        linhas.append(f"|6000|{tipo_lanc}||||")

        if tipo_lanc == "X":
            db  = debitos[0]
            cr  = creditos[0]
            val = formatar_valor(db["valor"])
            dsc = db.get("descr_hist", "").strip() or historico
            # Campo 6 (cod_hist) = vazio; campo 7 = descrição livre
            linhas.append(
                f"|6100|{data}|{db['conta']}|{cr['conta']}"
                f"|{val}||{dsc}|||"
            )
            total_6100 += 1

        elif tipo_lanc == "D":
            # 1 débito × vários créditos
            db           = debitos[0]
            cr_principal = creditos[0]
            val = formatar_valor(db["valor"])
            dsc = db.get("descr_hist", "").strip() or historico
            linhas.append(
                f"|6100|{data}|{db['conta']}|{cr_principal['conta']}"
                f"|{val}||{dsc}|||"
            )
            total_6100 += 1
            for cr in creditos[1:]:
                vr = formatar_valor(cr["valor"])
                linhas.append(f"|6110||{cr['conta']}|{vr}|")
                total_6110 += 1

        elif tipo_lanc == "C":
            # vários débitos × 1 crédito
            cr           = creditos[0]
            db_principal = debitos[0]
            val = formatar_valor(cr["valor"])
            dsc = db_principal.get("descr_hist", "").strip() or historico
            linhas.append(
                f"|6100|{data}|{db_principal['conta']}|{cr['conta']}"
                f"|{val}||{dsc}|||"
            )
            total_6100 += 1
            for db in debitos[1:]:
                vr = formatar_valor(db["valor"])
                linhas.append(f"|6110|{db['conta']}||{vr}|")
                total_6110 += 1

        else:
            # V — vários débitos × vários créditos
            db_principal = debitos[0]
            cr_principal = creditos[0]
            val = formatar_valor(db_principal["valor"])
            dsc = db_principal.get("descr_hist", "").strip() or historico
            linhas.append(
                f"|6100|{data}|{db_principal['conta']}|{cr_principal['conta']}"
                f"|{val}||{dsc}|||"
            )
            total_6100 += 1
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
    if ignorados:
        log.append(
            f"Lançamentos ignorados (sem D/C): {ignorados}"
        )
    if ignorados_conta:
        log.append(
            f"Lançamentos ignorados (conta temp. SPED): {ignorados_conta}"
        )
    log.append(f"Total de linhas geradas       : {len(linhas)}")
    return linhas


# ==============================
# PIPELINE PRINCIPAL
# ==============================
def converter_sped_ecd(conteudo_bytes, log, progress_bar, status_text):
    try:
        log.append("Iniciando leitura do SPED ECD...")
        ecd = parse_sped_ecd(conteudo_bytes, log, progress_bar, status_text)

        if ecd is None:
            log.append("ERRO: Leitura do SPED ECD falhou. Abortando.")
            return None, None

        log.append("Gerando layout Domínio Sistemas...")
        linhas = gerar_dominio(ecd, log, progress_bar, status_text)

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
        st.markdown("### ✅ Correções V1.3")
        st.markdown(
            """
- Campo 6 (cód. histórico) sempre **vazio** — evita erro *histórico não cadastrado*
- Histórico gravado apenas como **descrição livre** no campo 7
- Lançamentos com contas temporárias do SPED (`5000`, `5001`, `10000`, `10001`…) são **ignorados** automaticamente
- Arquivo gerado em **latin-1** — elimina caracteres corrompidos (`ï¿½`)
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

            <h4>🔹 Passo 2 — Converter</h4>
            <ol>
                <li>Clique em <b>Browse files</b> e selecione o arquivo SPED ECD.</li>
                <li>Clique em <b>▶ Converter</b>.</li>
                <li>Aguarde o processamento e clique em
                    <b>⬇ Baixar arquivo convertido</b>.</li>
            </ol>

            <h4>🔹 Passo 3 — Importar no Domínio Contabilidade</h4>
            <ol>
                <li>Abra o <b>Domínio Contabilidade</b>.</li>
                <li>Acesse <b>Utilitários → Importação → Lançamentos em Lote</b>.</li>
                <li>Selecione o arquivo <code>.txt</code> gerado e confirme a importação.</li>
            </ol>

            <hr>

            <h4>⚠ Observações importantes</h4>
            <ul>
                <li>O arquivo de saída segue o layout separado por pipe <code>|</code>
                    exigido pelo Domínio Sistemas.</li>
                <li>Lançamentos com contas temporárias do SPED
                    (<code>5000</code>, <code>5001</code>, <code>10000</code>, <code>10001</code>…)
                    são ignorados automaticamente — essas contas não existem no Domínio.</li>
                <li>O campo de código do histórico é deixado em branco para evitar
                    o erro <i>"histórico não cadastrado"</i>. O texto descritivo é
                    colocado diretamente no campo de descrição livre.</li>
                <li>O tipo do lançamento (<b>X / D / C / V</b>) é detectado
                    automaticamente pelo número de partidas.</li>
                <li>Letras acentuadas do português são preservadas.
                    O arquivo é gravado em <b>latin-1</b> para compatibilidade
                    com o Domínio.</li>
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

    # ---- Processamento com barra de progresso ----
    if converter and arquivo is not None:
        st.session_state.log          = ["Iniciando conversão..."]
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
        )

        if linhas and ecd:
            progress_bar.progress(100)
            status_text.text("✅ Conversão concluída!")

            # Grava em latin-1 — encoding nativo do Domínio
            conteudo_txt = "\n".join(linhas) + "\n"
            st.session_state.txt_gerado = conteudo_txt.encode(
                "latin-1", errors="replace"
            )
            cnpj_num = re.sub(r"\D", "", ecd.cnpj)
            st.session_state.nome_arquivo = (
                f"ECD_{cnpj_num}_lancamentos_dominio.txt"
            )

            total_linhas = len(linhas)
            total_6000   = sum(1 for l in linhas if l.startswith("|6000|"))
            total_6100   = sum(1 for l in linhas if l.startswith("|6100|"))
            total_6110   = sum(1 for l in linhas if l.startswith("|6110|"))
            st.session_state.metricas = {
                "CNPJ"              : ecd.cnpj,
                "Lançamentos (6000)": total_6000,
                "Linhas 6100"       : total_6100,
                "Linhas 6110"       : total_6110,
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
