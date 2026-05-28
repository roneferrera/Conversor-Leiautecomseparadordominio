import re
import io
import os
import traceback
import streamlit as st

# ==============================
# VERSÃO
# ==============================
VERSAO = "V1.0"

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
        h1, h2, h3 {
            color: #FF8000;
            font-weight: 700;
        }
        section[data-testid="stSidebar"] {
            background-color: #444444;
            color: #FFFFFF;
        }
        section[data-testid="stSidebar"] * {
            color: #FFFFFF !important;
        }
        .stButton > button {
            background-color: #FF8000;
            color: #FFFFFF;
            border: none;
            border-radius: 4px;
            font-weight: bold;
        }
        .stButton > button:hover {
            background-color: #D64001;
            color: #FFFFFF;
        }
        .stDownloadButton > button {
            background-color: #FF8000;
            color: #FFFFFF;
            border: none;
            border-radius: 4px;
            font-weight: bold;
        }
        .stDownloadButton > button:hover {
            background-color: #D64001;
            color: #FFFFFF;
        }
        hr {
            border-color: #FF8000;
        }
        [data-testid="metric-container"] {
            background-color: #E9E9E9;
            border-left: 4px solid #FF8000;
            border-radius: 4px;
            padding: 10px;
        }
        .instrucoes-box {
            background-color: #E9E9E9;
            border-left: 4px solid #FF8000;
            border-radius: 4px;
            padding: 16px 20px;
            margin: 12px 0;
            color: #444444;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        .instrucoes-box h4 {
            color: #FF8000;
            margin-top: 14px;
            margin-bottom: 6px;
        }
        .instrucoes-box h4:first-child {
            margin-top: 0;
        }
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
# PARSE DO SPED ECD
# ==============================

def _split_pipe(linha):
    campos = linha.strip().split("|")
    if campos and campos[0] == "":
        campos = campos[1:]
    if campos and campos[-1] == "":
        campos = campos[:-1]
    return campos


def parse_sped_ecd(conteudo_bytes, log):
    ecd        = SpedECD()
    lote_atual = None
    erros      = 0

    try:
        texto = conteudo_bytes.decode("utf-8", errors="replace")
    except Exception as e:
        log.append(f"ERRO ao decodificar arquivo: {e}")
        return None

    for num_linha, linha in enumerate(texto.splitlines(), start=1):
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
                # |I050|DT_INI|COD_EMP|IND_DC|NIVEL|COD_CTA|COD_CTA_SUP|NOME_CTA|
                if len(campos) > 7:
                    cod  = campos[5].strip()
                    nome = campos[7].strip()
                    if cod:
                        ecd.contas[cod] = nome

            # ---- I075 – Históricos padrão ----
            elif registro == "I075":
                # |I075|COD_HIST|DESCR_HIST|
                if len(campos) > 2:
                    ecd.historicos[campos[1].strip()] = campos[2].strip()

            # ---- I200 – Cabeçalho do lançamento ----
            elif registro == "I200":
                # |I200|NUM_LANC|DT_LANC|VL_LANC|IND_DC|IND_LANC|...
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
                # |I250|COD_CTA|COD_CCUS|VL_DC|IND_DC|NUM_ARQ|COD_HIST|DESCR_HIST|
                if lote_atual is not None and len(campos) > 4:
                    partida = {
                        "conta"     : campos[1].strip(),
                        "valor"     : campos[3].strip(),
                        "dc"        : campos[4].strip().upper(),
                        "cod_hist"  : campos[6].strip() if len(campos) > 6 else "",
                        "descr_hist": campos[7].strip() if len(campos) > 7 else "",
                    }
                    lote_atual["partidas"].append(partida)

        except Exception as e:
            log.append(f"Aviso: erro na linha {num_linha} ({registro}): {e}")
            erros += 1
            if erros > 50:
                log.append("ERRO: muitos erros de parse. Abortando leitura.")
                return None

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
    """
    Garante separador decimal com vírgula e pelo menos duas casas decimais.
    Ex.: '5571.24' → '5571,24' | '5571' → '5571,00'
    """
    v = valor_str.strip()

    # Troca ponto por vírgula (padrão SPED usa vírgula, mas por segurança)
    if "." in v and "," not in v:
        v = v.replace(".", ",")
    elif "." in v and "," in v:
        # Formato 1.234,56 → já ok; formato 1,234.56 → converte
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


def montar_historico(partida, historicos):
    """
    Prioridade: descrição completa da partida (I250 campo 7) > padrão I075.
    Limitado a 250 caracteres.
    """
    descr = partida.get("descr_hist", "").strip()
    cod   = partida.get("cod_hist",   "").strip()

    if descr:
        return descr[:250]
    if cod and cod in historicos:
        return historicos[cod][:250]
    return ""


def identificar_tipo_lancamento(partidas):
    """
    X = 1 débito × 1 crédito
    D = 1 débito × vários créditos
    C = vários débitos × 1 crédito
    V = vários débitos × vários créditos
    """
    debitos  = [p for p in partidas if p["dc"] == "D"]
    creditos = [p for p in partidas if p["dc"] == "C"]
    nd, nc   = len(debitos), len(creditos)

    if nd == 1 and nc == 1:
        return "X"
    if nd == 1 and nc > 1:
        return "D"
    if nc == 1 and nd > 1:
        return "C"
    return "V"


def primeiro_historico(partidas, historicos):
    """Retorna o primeiro histórico não-vazio encontrado nas partidas."""
    for p in partidas:
        h = montar_historico(p, historicos)
        if h:
            return h
    return ""


# ==============================
# GERADOR DO LAYOUT DOMÍNIO
# ==============================

def gerar_dominio(ecd, log):
    """
    Gera as linhas do layout Domínio Sistemas.
    Registros: 0000 / 6000 / 6100 / 6110

    Exemplo de saída esperada (arquivo exemplo_arquivo__lancamento_lote.txt):
        |0000|33333333000191|
        |6000|X||||
        |6100|10/09/2015|55|5|5571,24|1|DESCRICAO DO HISTORICO CONTABIL|GERENTE|||
    """
    linhas     = []
    total_6100 = 0
    total_6110 = 0
    ignorados  = 0

    # ---- Registro 0000 ----
    cnpj_numerico = re.sub(r"\D", "", ecd.cnpj)
    linhas.append(f"|0000|{cnpj_numerico}|")

    for lanc in ecd.lancamentos:
        partidas = lanc.get("partidas", [])
        if not partidas:
            ignorados += 1
            continue

        debitos  = [p for p in partidas if p["dc"] == "D"]
        creditos = [p for p in partidas if p["dc"] == "C"]

        if not debitos or not creditos:
            ignorados += 1
            continue

        data      = formatar_data_dominio(lanc["data"])
        tipo_lanc = identificar_tipo_lancamento(partidas)

        # ---- Registro 6000 ----
        # Campos: |6000|TIPO|COD_LANC_PADRAO|LOCALIZADOR|RTT_FCONT|
        linhas.append(f"|6000|{tipo_lanc}||||")

        # ---- Monta 6100 / 6110 conforme o tipo ----

        if tipo_lanc == "X":
            # 1 débito × 1 crédito
            db  = debitos[0]
            cr  = creditos[0]
            val = formatar_valor(db["valor"])
            cod = db.get("cod_hist", "")
            dsc = montar_historico(db, ecd.historicos)

            # |6100|DATA|DEBITO|CREDITO|VALOR|COD_HIST|DESCR_HIST|USUARIO|COD_FILIAL|COD_SCP|
            linhas.append(f"|6100|{data}|{db['conta']}|{cr['conta']}|{val}|{cod}|{dsc}|||")
            total_6100 += 1

        elif tipo_lanc == "D":
            # 1 débito × vários créditos
            db  = debitos[0]
            val = formatar_valor(db["valor"])
            cod = db.get("cod_hist", "")
            dsc = montar_historico(db, ecd.historicos)

            cr_principal = creditos[0]
            linhas.append(
                f"|6100|{data}|{db['conta']}|{cr_principal['conta']}"
                f"|{val}|{cod}|{dsc}|||"
            )
            total_6100 += 1

            # Créditos adicionais → 6110
            # |6110|CC_DEBITO|CC_CREDITO|VALOR_RATEIO|
            for cr in creditos[1:]:
                vr = formatar_valor(cr["valor"])
                linhas.append(f"|6110||{cr['conta']}|{vr}|")
                total_6110 += 1

        elif tipo_lanc == "C":
            # vários débitos × 1 crédito
            cr  = creditos[0]
            val = formatar_valor(cr["valor"])

            db_principal = debitos[0]
            cod = db_principal.get("cod_hist", "")
            dsc = montar_historico(db_principal, ecd.historicos)

            linhas.append(
                f"|6100|{data}|{db_principal['conta']}|{cr['conta']}"
                f"|{val}|{cod}|{dsc}|||"
            )
            total_6100 += 1

            # Débitos adicionais → 6110
            for db in debitos[1:]:
                vr = formatar_valor(db["valor"])
                linhas.append(f"|6110|{db['conta']}||{vr}|")
                total_6110 += 1

        else:
            # V — vários débitos × vários créditos
            db_principal = debitos[0]
            cr_principal = creditos[0]
            val = formatar_valor(db_principal["valor"])
            cod = db_principal.get("cod_hist", "")
            dsc = montar_historico(db_principal, ecd.historicos)

            linhas.append(
                f"|6100|{data}|{db_principal['conta']}|{cr_principal['conta']}"
                f"|{val}|{cod}|{dsc}|||"
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

    log.append(f"Registros 6100 gerados : {total_6100}")
    log.append(f"Registros 6110 gerados : {total_6110}")
    if ignorados:
        log.append(f"Lançamentos ignorados  : {ignorados} (sem partidas D/C completas)")
    log.append(f"Total de linhas geradas: {len(linhas)}")
    return linhas


# ==============================
# PIPELINE PRINCIPAL
# ==============================

def converter_sped_ecd(conteudo_bytes, log):
    """Lê o SPED ECD e gera as linhas do layout Domínio."""
    try:
        log.append("Iniciando leitura do SPED ECD...")
        ecd = parse_sped_ecd(conteudo_bytes, log)

        if ecd is None:
            log.append("ERRO: Leitura do SPED ECD falhou. Abortando.")
            return None, None

        log.append("Gerando layout Domínio Sistemas...")
        linhas = gerar_dominio(ecd, log)

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
                <li>Lançamentos sem partidas de débito <b>e</b> crédito simultâneas
                    são ignorados.</li>
                <li>O tipo do lançamento (<b>X / D / C / V</b>) é detectado
                    automaticamente pelo número de partidas.</li>
                <li>O histórico é extraído do campo descritivo do <code>I250</code>;
                    se vazio, usa o padrão do <code>I075</code>.</li>
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

    if converter and arquivo is not None:
        st.session_state.log          = ["Iniciando conversão..."]
        st.session_state.txt_gerado   = None
        st.session_state.nome_arquivo = "lancamentos_dominio.txt"
        st.session_state.metricas     = {}

        conteudo_bytes = arquivo.read()
        linhas, ecd    = converter_sped_ecd(conteudo_bytes, st.session_state.log)

        if linhas and ecd:
            conteudo_txt = "\n".join(linhas) + "\n"
            st.session_state.txt_gerado   = conteudo_txt.encode("utf-8", errors="replace")
            cnpj_num = re.sub(r"\D", "", ecd.cnpj)
            st.session_state.nome_arquivo = f"ECD_{cnpj_num}_lancamentos_dominio.txt"

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
