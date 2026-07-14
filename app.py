# -*- coding: utf-8 -*-
"""
Conversor Unificado SPED ECD — V4.0
Fusão de:
  - DE/PARA de Contas (fuzzy + manual + backup JSON)
  - Conversor de Lançamentos (I200/I250 → 6000/6100)
  - Saldo Inicial (I155/I355 → lançamento único)
  - Saldo Final (I155 → 6100)
  - I157 (troca de plano)
  - SPED Ajustado (I250 com novos códigos)
  - Centro de Custo (6110)
  - Comparação I052 entre ECDs
"""

import os
import re
import gc
import io
import time
import json
import traceback
import unicodedata
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta
from thefuzz import process, fuzz

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════════════
VERSAO        = "V4.0"
CHUNK_SIZE    = 100_000
WRITE_CHUNK   = 5_000
TOL_VALOR     = 0.005
MAX_UPLOAD_MB = 200

COLS_PADRAO = [
    "Data", "Cód. Conta Debito", "Cód. Conta Credito", "Valor",
    "Cód. Histórico", "Complemento Histórico", "Inicia Lote",
    "Código Matriz/Filial", "Centro de Custo Débito", "Centro de Custo Crédito",
]

# ═══════════════════════════════════════════════════════════════════════════════
# TEMA
# ═══════════════════════════════════════════════════════════════════════════════
def apply_theme():
    st.markdown("""
    <style>
    html,body,[class*='css']{font-family:'Segoe UI',Arial,sans-serif;color:#E8ECF0;}
    .stApp{background-color:#0A0E1A;}
    h1,h2,h3{color:#FF6B00;font-weight:700;}
    section[data-testid='stSidebar']{background-color:#0D1526;border-right:2px solid #1A3050;}
    section[data-testid='stSidebar'] *{color:#E8ECF0 !important;}
    .stButton>button{background-color:#FF6B00;color:#fff;border:none;border-radius:4px;font-weight:bold;}
    .stButton>button:hover{background-color:#CC5500;color:#fff;}
    .stDownloadButton>button{background-color:#FF6B00;color:#fff;border:none;border-radius:4px;font-weight:bold;}
    .stDownloadButton>button:hover{background-color:#CC5500;}
    hr{border-color:#FF6B00;}
    [data-testid='metric-container']{background-color:#102040;border-left:4px solid #FF6B00;
                                     border-radius:4px;padding:10px;}
    .stProgress>div>div>div>div{background-color:#FF6B00 !important;}
    .bloco-log{background:#060B14;border:1px solid #1A3050;border-radius:6px;padding:14px;
               font-family:Consolas,monospace;font-size:12px;white-space:pre-wrap;
               max-height:520px;overflow-y:auto;color:#E8ECF0;}
    .cont-row{border-bottom:1px solid #1A3050;padding:15px 0px;}
    .badge-ecd{background:#1a0a2e;color:#F472B6;font-weight:700;padding:6px 14px;
               border-radius:6px;border:1px solid #F472B6;display:inline-block;}
    .badge-excel{background:#0a2e1a;color:#00C896;font-weight:700;padding:6px 14px;
                 border-radius:6px;border:1px solid #00C896;display:inline-block;}
    .badge-lote{background:#2e2a0a;color:#FFD166;font-weight:700;padding:6px 14px;
                border-radius:6px;border:1px solid #FFD166;display:inline-block;}
    .badge-pos{background:#0a1a2e;color:#6EC6FF;font-weight:700;padding:6px 14px;
               border-radius:6px;border:1px solid #6EC6FF;display:inline-block;}
    .badge-si{background:#1a0a2e;color:#FF9EBC;font-weight:700;padding:6px 14px;
              border-radius:6px;border:1px solid #FF9EBC;display:inline-block;}
    .header-box{background:#102040;padding:20px 24px 14px;border-radius:8px;
                border-top:5px solid #FF6B00;margin-bottom:20px;}
    .cnpj-auto{background:#0a2e1a;border:1px solid #00C896;border-radius:8px;
               padding:12px 18px;margin:10px 0 16px 0;color:#00C896;font-weight:700;}
    .cnpj-auto span{color:#FFD166;}
    .info-box{background:#102040;border-left:4px solid #FF6B00;border-radius:4px;
              padding:12px 16px;margin:8px 0;font-size:13px;}
    .card-ok{background:#0a2e1a;border:2px solid #00C896;border-radius:10px;
             padding:18px 24px;margin:12px 0;}
    .card-err{background:#2e0a0a;border:2px solid #FF4444;border-radius:10px;
              padding:18px 24px;margin:12px 0;}
    .card-warn{background:#1a1000;border-left:4px solid #FFD166;border-radius:4px;
               padding:10px 16px;margin:8px 0;}
    .filial-box{background:#0a1a2e;border:1px solid #6EC6FF;border-radius:8px;
                padding:14px 18px;margin:10px 0;}
    .si-box{background:#1a0a2e;border:1px solid #FF9EBC;border-radius:8px;
            padding:14px 18px;margin:10px 0;}
    .depara-box{background:#0a1a0a;border:1px solid #00C896;border-radius:8px;
                padding:14px 18px;margin:10px 0;}
    </style>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CRONÔMETRO
# ═══════════════════════════════════════════════════════════════════════════════
class Cronometro:
    def __init__(self):
        self._inicio_total = 0.0
        self._etapas       = []
        self._inicio_etapa = 0.0
        self._etapa_atual  = ""

    def iniciar(self):
        self._inicio_total = time.perf_counter()
        self._etapas.clear()

    def etapa(self, nome):
        agora = time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({
                "nome": self._etapa_atual,
                "segundos": round(agora - self._inicio_etapa, 3)
            })
        self._etapa_atual  = nome
        self._inicio_etapa = agora

    def encerrar(self):
        agora = time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({
                "nome": self._etapa_atual,
                "segundos": round(agora - self._inicio_etapa, 3)
            })
            self._etapa_atual = ""
        return round(agora - self._inicio_total, 3)

    @staticmethod
    def fmt(s):
        if s < 0.001: return "<1ms"
        if s < 1:     return f"{s*1000:.0f}ms"
        if s < 60:    return f"{s:.2f}s"
        m = int(s // 60)
        return f"{m}min {s%60:.1f}s"

    @property
    def etapas(self): return self._etapas

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS GERAIS
# ═══════════════════════════════════════════════════════════════════════════════
_MAPA_ESPECIAIS = {
    "\u2018":"'","\u2019":"'","\u201C":'"',"\u201D":'"',"\u2013":"-","\u2014":"-",
    "\u2026":"...","\u00A0":" ","\u00D7":"x","\u00F7":"/","\u20AC":"EUR","\u00A7":"S/",
    "\u00AE":"(R)","\u00A9":"(C)","\u2122":"(TM)",
    "\u00C0":"A","\u00C1":"A","\u00C2":"A","\u00C3":"A","\u00C4":"A","\u00C5":"A",
    "\u00E0":"a","\u00E1":"a","\u00E2":"a","\u00E3":"a","\u00E4":"a","\u00E5":"a",
    "\u00C8":"E","\u00C9":"E","\u00CA":"E","\u00CB":"E",
    "\u00E8":"e","\u00E9":"e","\u00EA":"e","\u00EB":"e",
    "\u00CC":"I","\u00CD":"I","\u00CE":"I","\u00CF":"I",
    "\u00EC":"i","\u00ED":"i","\u00EE":"i","\u00EF":"i",
    "\u00D2":"O","\u00D3":"O","\u00D4":"O","\u00D5":"O","\u00D6":"O",
    "\u00F2":"o","\u00F3":"o","\u00F4":"o","\u00F5":"o","\u00F6":"o",
    "\u00D9":"U","\u00DA":"U","\u00DB":"U","\u00DC":"U",
    "\u00F9":"u","\u00FA":"u","\u00FB":"u","\u00FC":"u",
    "\u00DD":"Y","\u00FD":"y","\u00FF":"y","\u00C7":"C","\u00E7":"c",
    "\u00D1":"N","\u00F1":"n","\u00BA":"o","\u00AA":"a","\u00B0":"o",
    "\u00BD":"1/2","\u00BC":"1/4","\u00BE":"3/4","\u0131":"i","\u00DF":"ss",
}

def _norm_hist(texto: str) -> str:
    if not texto: return ""
    for orig, dest in _MAPA_ESPECIAIS.items():
        texto = texto.replace(orig, dest)
    texto = unicodedata.normalize("NFC", texto)
    res = []
    for ch in texto:
        cp = ord(ch)
        if cp < 0x20 and cp != 9: continue
        if ch == "|": res.append(" "); continue
        try: ch.encode("latin-1"); res.append(ch); continue
        except UnicodeEncodeError: pass
        decomposto = unicodedata.normalize("NFD", ch)
        base = decomposto[0]
        try: base.encode("latin-1"); res.append(base); continue
        except UnicodeEncodeError: pass
        nome = unicodedata.name(ch, "")
        if "LATIN" in nome:
            partes = nome.split()
            for i, p in enumerate(partes):
                if p == "LETTER" and i+1 < len(partes):
                    letra = partes[i+1]
                    if len(letra) == 1:
                        res.append(letra.lower() if "SMALL" in nome else letra.upper())
                        break
    return re.sub(r" {2,}", " ", "".join(res)).strip()[:250]

def sanitizar_texto(t: str) -> str:
    return _norm_hist(str(t) if t else "")

def formatar_data(v):
    try:
        if isinstance(v, (datetime, pd.Timestamp)):
            return v.strftime("%d/%m/%Y")
        return pd.to_datetime(v, dayfirst=True).strftime("%d/%m/%Y")
    except:
        return str(v)

def eh_vazio(v):
    if v is None: return True
    try:
        if pd.isna(v): return True
    except: pass
    return str(v).strip() in ("", "nan", "NaN", "None")

def ts_log():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def so_nums(v):
    return re.sub(r"\D", "", str(v))

def limpar_nome_arquivo(nome: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", nome).strip()

_VAZIO_CONTA = frozenset(("", "nan", "none", "0", "0.0"))

def limpar_contas_vec(serie):
    arr = serie.fillna("").astype(str).str.strip().str.lower().to_numpy()
    out = np.where(np.isin(arr, list(_VAZIO_CONTA)), "", arr)
    mask = out != ""
    if mask.any():
        vals = out[mask]
        conv = np.empty(len(vals), dtype=object)
        for i, v in enumerate(vals):
            try:    conv[i] = str(int(float(v.replace(",", "."))))
            except: conv[i] = v
        out[mask] = conv
    return out

def limpar_valor_vec(serie):
    return (
        pd.to_numeric(
            serie.fillna("0").astype(str).str.strip()
                 .str.replace(",", ".", regex=False)
                 .str.replace(r"[^\d.\-]", "", regex=True),
            errors="coerce"
        ).fillna(0.0).round(2).to_numpy(dtype=np.float64)
    )

def validar_cnpj(cnpj):
    c = so_nums(cnpj)
    if len(c) != 14 or len(set(c)) == 1: return False
    def d(c, p):
        s = sum(int(c[i]) * p[i] for i in range(len(p)))
        r = s % 11
        return 0 if r < 2 else 11 - r
    return (int(c[12]) == d(c, [5,4,3,2,9,8,7,6,5,4,3,2]) and
            int(c[13]) == d(c, [6,5,4,3,2,9,8,7,6,5,4,3,2]))

def validar_cpf(cpf):
    c = so_nums(cpf)
    if len(c) != 11 or len(set(c)) == 1: return False
    def d(c, n):
        s = sum(int(c[i]) * (n - i) for i in range(n - 1))
        r = (s * 10) % 11
        return 0 if r == 10 else r
    return int(c[9]) == d(c, 10) and int(c[10]) == d(c, 11)

def validar_inscricao(v):
    n = so_nums(v)
    if len(n) == 14 and validar_cnpj(n): return True, "CNPJ", n
    if len(n) == 11 and validar_cpf(n):  return True, "CPF",  n
    return False, "", n

def fmt_cnpj(n):
    c = so_nums(n)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else n

def fmt_cpf(n):
    c = so_nums(n)
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else n

def fmt_reg_0000(ni: str) -> str:
    return f"|0000|{ni}|"

def fmt_reg_6000(tp: str) -> str:
    return f"|6000|{tp}||||"

def _fmt_valor_layout(valor) -> str:
    if isinstance(valor, (int, float)):
        return f"{float(valor):.2f}".replace(".", ",")
    v = str(valor).strip()
    if "." in v and "," in v:
        if v.index(".") < v.index(","): v = v.replace(".", "").replace(",", ".")
        else: v = v.replace(",", "")
    elif "," in v:
        v = v.replace(",", ".")
    try:    return f"{float(v):.2f}".replace(".", ",")
    except: return "0,00"

def fmt_reg_6100(data, deb, cred, valor, cod_hist="", desc="",
                 _u="", _f="", _s=""):
    return (f"|6100|{data}|{deb}|{cred}|{_fmt_valor_layout(valor)}"
            f"||{_norm_hist(desc)}|||||||")

def format_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

_CHARS_PT = set(
    "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞß"
    "àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿºª"
)

def _detectar_encoding_bytes(conteudo: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            texto = conteudo.decode(enc, errors="strict")
            if sum(1 for c in texto[:4096] if c in _CHARS_PT) > 0 or enc in ("utf-8-sig", "utf-8"):
                return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"

def _gerar_6110_linha(deb_cta, cred_cta, valor_fmt, modo):
    linhas = []
    if modo in ("ambos", "deb")  and deb_cta:
        linhas.append(f"|6110|{deb_cta}||{valor_fmt}|")
    if modo in ("ambos", "cred") and cred_cta:
        linhas.append(f"|6110||{cred_cta}|{valor_fmt}|")
    return linhas

def ler_arquivo_texto_seguro(file) -> list:
    raw_data = file.getvalue()
    try:    content = raw_data.decode("latin-1")
    except: content = raw_data.decode("cp1252", errors="ignore")
    return [linha.strip('\r\n') for linha in content.splitlines() if linha.strip()]

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 2 — MÓDULO DE/PARA DE CONTAS (fusão V3.6.2 + app DE/PARA)
# ═══════════════════════════════════════════════════════════════════════════════

import json
from thefuzz import process, fuzz

# ── Plano padrão UNSÃO embutido (fallback se plano_padrao.xlsx não existir) ──
PLANO_UNSAO_PADRAO = [
    # (Código, Classificação, Nome)
    ("1",    "1",          "ATIVO"),
    ("101",  "1.01",       "ATIVO CIRCULANTE"),
    ("10101","1.01.01",    "CAIXA E EQUIVALENTES DE CAIXA"),
    ("10102","1.01.02",    "APLICACOES FINANCEIRAS"),
    ("10103","1.01.03",    "CONTAS A RECEBER"),
    ("10104","1.01.04",    "ESTOQUES"),
    ("10105","1.01.05",    "OUTROS ATIVOS CIRCULANTES"),
    ("102",  "1.02",       "ATIVO NAO CIRCULANTE"),
    ("10201","1.02.01",    "REALIZAVEL A LONGO PRAZO"),
    ("10202","1.02.02",    "INVESTIMENTOS"),
    ("10203","1.02.03",    "IMOBILIZADO"),
    ("10204","1.02.04",    "INTANGIVEL"),
    ("2",    "2",          "PASSIVO"),
    ("201",  "2.01",       "PASSIVO CIRCULANTE"),
    ("20101","2.01.01",    "FORNECEDORES"),
    ("20102","2.01.02",    "OBRIGACOES TRABALHISTAS"),
    ("20103","2.01.03",    "OBRIGACOES FISCAIS"),
    ("20104","2.01.04",    "OUTROS PASSIVOS CIRCULANTES"),
    ("202",  "2.02",       "PASSIVO NAO CIRCULANTE"),
    ("20201","2.02.01",    "EMPRESTIMOS E FINANCIAMENTOS LP"),
    ("20202","2.02.02",    "OUTROS PASSIVOS NAO CIRCULANTES"),
    ("203",  "2.03",       "PATRIMONIO LIQUIDO"),
    ("20301","2.03.01",    "CAPITAL SOCIAL"),
    ("20302","2.03.02",    "RESERVAS DE CAPITAL"),
    ("20303","2.03.03",    "RESERVAS DE LUCRO"),
    ("20304","2.03.04",    "RESULTADO DO EXERCICIO"),
    ("3",    "3",          "RECEITAS"),
    ("301",  "3.01",       "RECEITA BRUTA"),
    ("30101","3.01.01",    "RECEITA DE SERVICOS"),
    ("30102","3.01.02",    "RECEITA DE VENDAS"),
    ("302",  "3.02",       "DEDUCOES DA RECEITA"),
    ("4",    "4",          "DESPESAS"),
    ("401",  "4.01",       "CUSTO DOS SERVICOS"),
    ("402",  "4.02",       "DESPESAS OPERACIONAIS"),
    ("40201","4.02.01",    "DESPESAS ADMINISTRATIVAS"),
    ("40202","4.02.02",    "DESPESAS FINANCEIRAS"),
    ("40203","4.02.03",    "OUTRAS DESPESAS"),
    ("5",    "5",          "RESULTADO"),
    ("501",  "5.01",       "RESULTADO ANTES DO IR"),
    ("502",  "5.02",       "PROVISAO IRPJ CSLL"),
    ("503",  "5.03",       "RESULTADO LIQUIDO"),
]

def _carregar_plano_padrao_unsao() -> pd.DataFrame:
    """Retorna o DataFrame do plano padrão UNSÃO (embutido ou do arquivo)."""
    caminho = "plano_padrao.xlsx"
    if os.path.exists(caminho):
        try:
            df = pd.read_excel(caminho, header=None).iloc[:, [0, 1, 2]]
            df.columns = ["Código", "Classificação", "Nome"]
            df = df.astype(str)
            df["Display"] = df["Código"] + " | " + df["Classificação"] + " - " + df["Nome"]
            df["Grupo"]   = df["Classificação"].str[0]
            return df
        except Exception:
            pass
    # Fallback embutido
    rows = [{"Código": c, "Classificação": cl, "Nome": n} for c, cl, n in PLANO_UNSAO_PADRAO]
    df = pd.DataFrame(rows).astype(str)
    df["Display"] = df["Código"] + " | " + df["Classificação"] + " - " + df["Nome"]
    df["Grupo"]   = df["Classificação"].str[0]
    return df


def _carregar_plano_excel_upload(conteudo_excel: bytes) -> pd.DataFrame:
    """Lê um plano de contas enviado pelo usuário (Excel, sem cabeçalho, 3 colunas)."""
    buf = io.BytesIO(conteudo_excel)
    df  = pd.read_excel(buf, header=None, engine="openpyxl").iloc[:, [0, 1, 2]]
    df.columns = ["Código", "Classificação", "Nome"]
    df = df.astype(str)
    df["Display"] = df["Código"] + " | " + df["Classificação"] + " - " + df["Nome"]
    df["Grupo"]   = df["Classificação"].str[0]
    return df


# ── Estado inicial do módulo DE/PARA ─────────────────────────────────────────
def _init_depara_state():
    defaults_depara = {
        "depara_map":              {},       # cod_antigo → cod_novo
        "depara_plano_df":         None,     # DataFrame do plano novo
        "depara_plano_nome":       "",       # nome do arquivo do plano
        "depara_backup_id":        "",       # controle de re-upload de backup
        "depara_balanco_proc":     False,
        "depara_balanco_dados":    None,
        "depara_balanco_totais":   {},
        "depara_balanco_has_data": False,
        "depara_i157_proc":        False,
        "depara_i157_dados":       None,
        "depara_i157_has_data":    False,
        "depara_ocultar_mapeadas": False,
    }
    for k, v in defaults_depara.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_depara():
    """Limpa apenas o estado do módulo DE/PARA (mantém o arquivo ECD)."""
    st.session_state.depara_map            = {}
    st.session_state.depara_balanco_proc   = False
    st.session_state.depara_balanco_dados  = None
    st.session_state.depara_balanco_totais = {}
    st.session_state.depara_i157_proc      = False
    st.session_state.depara_i157_dados     = None
    st.session_state.depara_i157_has_data  = False


# ── Helpers internos ─────────────────────────────────────────────────────────
def _atualizar_manual_depara(cod_conta: str):
    chave = f"depara_in_{cod_conta}"
    if chave in st.session_state:
        valor = str(st.session_state[chave]).strip()
        if valor:
            st.session_state.depara_map[cod_conta] = valor


def _extrair_contas_ecd_para_depara(conteudo: bytes) -> tuple:
    """
    Varre o SPED ECD e retorna:
      - contas_origem : list[dict] com cod, classif, nome, grupo
      - initial_balances : dict cod → (val_str, dc)
      - final_balances   : dict cod → (val_str, dc)
      - nome_empresa, dt_inicial_sped, dt_final_sped
    """
    enc = _detectar_encoding_bytes(conteudo)
    try:    texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")
    linhas = texto.splitlines()

    nome_empresa   = "EMPRESA"
    dt_ini_sped    = None
    dt_fin_sped    = None
    initial_balances: dict = {}
    final_balances:   dict = {}
    contas_com_mov: set    = set()
    rtl_count_i150         = 0

    for linha in linhas:
        linha = linha.strip()
        if not linha: continue
        campos = _split_pipe(linha)
        if not campos: continue
        reg = campos[0]

        if reg == "0000":
            if len(campos) > 5:
                nome_empresa = limpar_nome_arquivo(_campo(campos, 5))
            if len(campos) > 3:
                try:
                    dt_ini_sped = datetime.strptime(
                        _campo(campos, 3).strip(), "%d%m%Y"
                    ).date()
                except Exception:
                    pass
            if len(campos) > 4:
                try:
                    dt_fin_sped = datetime.strptime(
                        _campo(campos, 4).strip(), "%d%m%Y"
                    ).date()
                except Exception:
                    pass

        elif reg == "I150":
            rtl_count_i150 += 1

        elif reg == "I155":
            if len(campos) < 10: continue
            cod        = _campo(campos, 1).strip()
            val_ini    = _campo(campos, 4).strip()
            dc_ini     = _campo(campos, 5).strip()
            val_fin    = _campo(campos, 7).strip()
            dc_fin     = _campo(campos, 8).strip()
            if not cod: continue
            contas_com_mov.add(cod)
            if cod not in initial_balances:
                initial_balances[cod] = (
                    val_ini if rtl_count_i150 <= 1 else "0,00",
                    dc_ini
                )
            final_balances[cod] = (val_fin, dc_fin)

        elif reg == "I250":
            cod = _campo(campos, 1).strip()
            if cod: contas_com_mov.add(cod)

    # Extrai contas do I050 que têm movimento
    contas_origem_data = []
    for linha in linhas:
        linha = linha.strip()
        if not linha: continue
        campos = _split_pipe(linha)
        if not campos or campos[0] != "I050": continue
        if len(campos) < 6: continue

        cod_encontrado = None
        pos_classif    = -1
        for i in [5, 6, 7]:
            if i < len(campos) and campos[i].strip() in contas_com_mov:
                cod_encontrado = campos[i].strip()
                pos_classif    = i
                break

        if not cod_encontrado: continue

        nome_conta = "Sem Nome"
        for j in range(pos_classif + 1, len(campos)):
            v = campos[j].strip()
            if len(v) > 2 and not v.replace(".", "").isnumeric():
                nome_conta = v
                break

        grupo = campos[pos_classif][0] if campos[pos_classif] else ""
        contas_origem_data.append({
            "cod":     cod_encontrado,
            "classif": campos[pos_classif].strip(),
            "nome":    nome_conta,
            "grupo":   grupo,
        })

    df_origem = (
        pd.DataFrame(contas_origem_data)
        .drop_duplicates(subset=["cod"])
        .reset_index(drop=True)
    )
    return df_origem, initial_balances, final_balances, nome_empresa, dt_ini_sped, dt_fin_sped


def _rodar_fuzzy_depara(df_origem: pd.DataFrame,
                         df_plano:  pd.DataFrame) -> list:
    """
    Para cada conta de origem, calcula o melhor match no plano novo.
    Retorna lista de dicts com metadados para renderização.
    """
    results = []
    for _, row in df_origem.iterrows():
        cod_atual  = str(row["cod"])
        grupo_atual = row["grupo"]

        df_filtrado = df_plano[df_plano["Grupo"] == grupo_atual]
        df_busca    = df_filtrado if not df_filtrado.empty else df_plano

        if grupo_atual in ("1", "2"):
            df_opcoes = df_filtrado if not df_filtrado.empty else df_plano
        else:
            df_opcoes = df_plano[~df_plano["Grupo"].isin(["1", "2"])]
            if df_opcoes.empty:
                df_opcoes = df_plano

        lista_nomes = df_busca["Nome"].tolist()
        candidatos  = process.extract(
            row["nome"], lista_nomes,
            scorer=fuzz.token_set_ratio, limit=5
        )

        melhor_match     = None
        melhor_score_fin = -1
        for nome_cand, score_flex in candidatos:
            score_rig  = fuzz.token_sort_ratio(row["nome"], nome_cand)
            media      = (score_flex + score_rig) / 2
            if media > melhor_score_fin:
                melhor_score_fin = media
                melhor_match     = nome_cand

        score = int(melhor_score_fin)

        cod_sugerido_ia    = None
        display_sugerido_ia = None
        if score >= 65 and melhor_match:
            match_row = df_busca[df_busca["Nome"] == melhor_match]
            if not match_row.empty:
                cod_sugerido_ia     = match_row.iloc[0]["Código"]
                display_sugerido_ia = match_row.iloc[0]["Display"]

        esta_no_mapa = cod_atual in st.session_state.depara_map
        valor_no_mapa = str(st.session_state.depara_map.get(cod_atual, ""))

        resolvida = False
        is_manual = False
        if esta_no_mapa:
            resolvida = True
            if valor_no_mapa != cod_sugerido_ia:
                is_manual = True
        elif score >= 65:
            resolvida = True

        results.append({
            "row":               row,
            "df_busca":          df_busca,
            "df_opcoes":         df_opcoes,
            "score":             score,
            "cod_sugerido_ia":   cod_sugerido_ia,
            "display_sugerido_ia": display_sugerido_ia,
            "resolvida":         resolvida,
            "is_manual":         is_manual,
            "esta_no_mapa":      esta_no_mapa,
            "valor_no_mapa":     valor_no_mapa,
        })
    return results


def _montar_map_final_depara(process_data: list) -> dict:
    """
    Constrói o mapa final cod_antigo → cod_novo
    priorizando o mapeamento manual sobre a sugestão IA.
    """
    mapa = {}
    for item in process_data:
        cod = str(item["row"]["cod"])
        if item["esta_no_mapa"]:
            mapa[cod] = st.session_state.depara_map[cod]
        elif item["score"] >= 65 and item["cod_sugerido_ia"]:
            mapa[cod] = item["cod_sugerido_ia"]
    return mapa


# ── Geração dos arquivos de saída ─────────────────────────────────────────────
def _gerar_sped_ajustado_depara(conteudo: bytes,
                                  map_final: dict,
                                  nome_empresa: str) -> bytes:
    """Substitui cod_cta nos registros I250 pelo novo código."""
    enc = _detectar_encoding_bytes(conteudo)
    try:    texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")

    saida = []
    for linha in texto.splitlines():
        linha_s = linha.strip()
        if not linha_s:
            continue
        if linha_s.startswith("|9999|"):
            saida.append(linha_s)
            break
        if linha_s.startswith("|I250|"):
            campos = linha_s.split("|")
            if len(campos) > 2 and campos[2] in map_final:
                novo_cod = str(map_final[campos[2]]).strip().replace("|", "")
                campos[2] = novo_cod
            saida.append("|".join(campos))
        else:
            saida.append(linha_s)

    return "\r\n".join(saida).encode("latin-1", errors="replace")


def _gerar_i157_depara(map_final: dict,
                        initial_balances: dict,
                        nome_empresa: str) -> tuple:
    """
    Gera o arquivo I157 (troca de plano) com os saldos iniciais.
    Retorna (bytes, has_data).
    """
    linhas = ["ID;;;;;;"]
    items_i157 = []

    for cod_antigo, cod_novo in map_final.items():
        cod_novo_clean = str(cod_novo).replace("|", "")
        val_str, dc    = initial_balances.get(cod_antigo, ("0,00", "D"))
        try:    val_float = float(val_str.replace(",", "."))
        except: val_float = 0.0
        if val_float > 0:
            items_i157.append((cod_novo_clean, cod_antigo, val_str, dc))

    if not items_i157:
        return "\r\n".join(linhas).encode("latin-1", errors="replace"), False

    items_i157.sort(key=lambda x: str(x[0]))
    for cod_novo, cod_antigo, val_str, dc in items_i157:
        if "." in cod_antigo or not cod_antigo.isnumeric():
            linha = f"C;{cod_novo};;{cod_antigo};{val_str};{dc};"
        else:
            linha = f"C;{cod_novo};{cod_antigo};;{val_str};{dc};"
        linhas.append(linha)

    return "\r\n".join(linhas).encode("latin-1", errors="replace"), True


def _gerar_balanco_depara(map_final: dict,
                           saldos: dict,
                           dt_fmt: str,
                           tipo_saldo: str) -> tuple:
    """
    Gera o arquivo de balanço (saldo inicial ou final).
    Retorna (bytes, totais_dict, has_data).
    """
    linhas = ["|6000|V||||"]
    total_d = total_c = 0.0
    has_data = False

    for cod_antigo, cod_novo in map_final.items():
        cod_novo_clean = str(cod_novo).replace("|", "")
        val_str, dc    = saldos.get(cod_antigo, ("0,00", "D"))
        try:    val_float = float(val_str.replace(",", "."))
        except: val_float = 0.0

        if val_float > 0:
            hist = _norm_hist(f"SALDO DE ABERTURA EM {dt_fmt}")
            if dc == "D":
                total_d += val_float
                linhas.append(
                    f"|6100|{dt_fmt}|{cod_novo_clean}||{val_str}||{hist}|||||"
                )
            else:
                total_c += val_float
                linhas.append(
                    f"|6100|{dt_fmt}||{cod_novo_clean}|{val_str}||{hist}|||||"
                )
            has_data = True

    dados = "\r\n".join(linhas).encode("latin-1", errors="replace")
    return dados, {"D": round(total_d, 2), "C": round(total_c, 2)}, has_data


# ── Widget principal do módulo DE/PARA ───────────────────────────────────────
def render_modulo_depara(conteudo_ecd: bytes, ativo: bool):
    """
    Renderiza o módulo completo DE/PARA de contas.
    Deve ser chamado dentro da aba/seção correta do main().

    Parâmetros
    ----------
    conteudo_ecd : bytes  — conteúdo bruto do SPED ECD
    ativo        : bool   — se False, exibe apenas aviso e retorna {}
    """
    _init_depara_state()

    if not ativo:
        st.markdown(
            "<div class='info-box'>ℹ DE/PARA desabilitado. "
            "Marque a opção no Passo 3 para ativar.</div>",
            unsafe_allow_html=True
        )
        return {}

    st.markdown(
        "<div class='depara-box'>"
        "<b style='color:#00C896;font-size:15px;'>🔀 Módulo DE/PARA de Contas</b><br>"
        "<small style='color:#9BB0C8;'>Mapeie as contas do SPED ECD para o novo plano. "
        "O fuzzy matching sugere automaticamente. Ajuste manualmente quando necessário.</small>"
        "</div>", unsafe_allow_html=True
    )

    # ── Escolha do plano ──────────────────────────────────────────────────────
    col_p1, col_p2 = st.columns([1, 2])
    with col_p1:
        usar_padrao = st.checkbox(
            "Usar Plano Padrão UNSÃO", value=True, key="depara_usar_padrao"
        )
    with col_p2:
        file_plano_up = None
        if not usar_padrao:
            file_plano_up = st.file_uploader(
                "Subir Novo Plano (Excel — 3 colunas: Código, Classificação, Nome)",
                type=["xlsx"], key="depara_upload_plano"
            )
            with st.expander("ℹ Ver modelo de planilha"):
                st.write("Sem cabeçalho. Colunas: A=Código, B=Classificação, C=Nome")
                df_ex = pd.DataFrame({
                    "A (Código)":       ["50", "51"],
                    "B (Classificação)":["1.01.01", "1.01.02"],
                    "C (Nome)":         ["CAIXA GERAL", "BANCO CONTA MOV."],
                })
                st.table(df_ex)
                buf_ex = io.BytesIO()
                with pd.ExcelWriter(buf_ex, engine="xlsxwriter") as w:
                    pd.DataFrame(columns=["A", "B", "C"]).to_excel(
                        w, sheet_name="Plan1", header=False, index=False
                    )
                st.download_button(
                    "⬇ Baixar modelo",
                    data=buf_ex.getvalue(),
                    file_name="Modelo_Plano_Contas.xlsx",
                    mime="application/vnd.ms-excel",
                )

    # Carrega plano
    if usar_padrao or file_plano_up is None:
        df_plano = _carregar_plano_padrao_unsao()
        st.session_state.depara_plano_nome = "UNSÃO (padrão)"
    else:
        df_plano = _carregar_plano_excel_upload(file_plano_up.read())
        st.session_state.depara_plano_nome = file_plano_up.name
    st.session_state.depara_plano_df = df_plano

    # ── Backup JSON ───────────────────────────────────────────────────────────
    st.markdown("---")
    col_bk1, col_bk2 = st.columns(2)
    with col_bk1:
        st.markdown("**💾 Carregar progresso salvo (.json)**")
        arq_backup = st.file_uploader(
            "Backup JSON", type=["json"], key="depara_backup_upload"
        )
        if arq_backup is not None:
            file_id = f"{arq_backup.name}_{arq_backup.size}"
            if st.session_state.depara_backup_id != file_id:
                try:
                    dados = json.load(arq_backup)
                    dados_limpos = {str(k): str(v) for k, v in dados.items()}
                    st.session_state.depara_map.update(dados_limpos)
                    for cod, val in dados_limpos.items():
                        st.session_state[f"depara_in_{cod}"] = val
                    st.session_state.depara_backup_id = file_id
                    st.success(f"✅ Backup carregado! {len(dados_limpos)} contas.")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Erro ao carregar backup: {ex}")

    with col_bk2:
        if st.session_state.depara_map:
            st.markdown("**⬇ Salvar progresso atual**")
            st.download_button(
                "💾 Salvar progresso (.json)",
                data=json.dumps(st.session_state.depara_map, indent=4).encode("utf-8"),
                file_name="backup_depara_ecd.json",
                mime="application/json",
                use_container_width=True,
            )

    # ── Extração das contas do ECD ────────────────────────────────────────────
    st.markdown("---")
    with st.spinner("Extraindo contas do SPED ECD..."):
        (df_origem, initial_balances, final_balances,
         nome_empresa, dt_ini_sped, dt_fin_sped) = _extrair_contas_ecd_para_depara(conteudo_ecd)

    if df_origem.empty:
        st.error("Nenhuma conta com movimento detectada no SPED ECD.")
        return {}

    # ── Fuzzy matching ────────────────────────────────────────────────────────
    with st.spinner("Calculando sugestões automáticas (fuzzy)..."):
        process_data = _rodar_fuzzy_depara(df_origem, df_plano)

    map_final = _montar_map_final_depara(process_data)

    total_contas    = len(df_origem)
    total_mapeadas  = sum(1 for item in process_data if item["resolvida"])
    total_pendentes = total_contas - total_mapeadas
    pct             = (total_mapeadas / total_contas * 100) if total_contas > 0 else 0.0

    # ── Métricas ──────────────────────────────────────────────────────────────
    cm1, cm2, cm3 = st.columns(3)
    cm1.metric("Total de Contas",  f"{total_contas:,}")
    cm2.metric("Mapeadas",         f"{total_mapeadas:,}", f"{pct:.1f}%")
    cm3.metric("Pendentes",        f"{total_pendentes:,}",
               f"-{total_pendentes}" if total_pendentes else "0",
               delta_color="inverse")
    st.progress(pct / 100)

    # ── Filtro ────────────────────────────────────────────────────────────────
    ocultar = st.checkbox(
        "Ocultar contas já mapeadas", value=False, key="depara_ocultar"
    )

    # ── Renderização linha a linha ────────────────────────────────────────────
    st.markdown("#### 🔗 Mapeamento de Contas")
    for item in process_data:
        row       = item["row"]
        cod_atual = str(row["cod"])

        if ocultar and item["resolvida"]:
            continue

        with st.container():
            col_orig, col_dest = st.columns([1, 1])
            with col_orig:
                st.markdown(f"**{row['nome']}**")
                st.caption(f"Cód. SPED: `{cod_atual}` | Grupo: `{row['grupo']}`")

            with col_dest:
                df_opcoes = item["df_opcoes"]
                opcoes    = (
                    ["-- SELECIONE --", "📝 -- DIGITAR MANUALMENTE --"]
                    + df_opcoes["Display"].tolist()
                )
                chave_sel = f"depara_sel_{cod_atual}"

                # Valor inicial do selectbox
                valor_inicial = opcoes[0]
                if item["esta_no_mapa"]:
                    match_row = df_plano[df_plano["Código"] == item["valor_no_mapa"]]
                    if not match_row.empty:
                        disp = match_row.iloc[0]["Display"]
                        if disp not in opcoes:
                            opcoes.insert(2, disp)
                        valor_inicial = disp
                    else:
                        valor_inicial = "📝 -- DIGITAR MANUALMENTE --"
                        if f"depara_in_{cod_atual}" not in st.session_state:
                            st.session_state[f"depara_in_{cod_atual}"] = item["valor_no_mapa"]
                elif item["display_sugerido_ia"]:
                    if item["display_sugerido_ia"] not in opcoes:
                        opcoes.insert(2, item["display_sugerido_ia"])
                    if chave_sel not in st.session_state:
                        valor_inicial = item["display_sugerido_ia"]
                    else:
                        valor_inicial = st.session_state[chave_sel]

                if chave_sel not in st.session_state:
                    st.session_state[chave_sel] = valor_inicial

                # Badge de status
                if item["is_manual"]:
                    st.info("📌 Mapeado Manualmente")
                elif item["score"] >= 65:
                    st.success(f"✅ Sugestão automática: {item['score']}%")
                else:
                    st.warning(f"⚠ Similaridade baixa ({item['score']}%)")

                escolha = st.selectbox(
                    label=f"sel_{cod_atual}", options=opcoes,
                    key=chave_sel, label_visibility="collapsed"
                )

                # Processa escolha
                novo_valor = None
                if escolha == "📝 -- DIGITAR MANUALMENTE --":
                    pass  # campo de texto abaixo
                elif escolha != "-- SELECIONE --":
                    try:
                        cod_red = escolha.split(" | ")[0]
                        if cod_red != item["valor_no_mapa"]:
                            novo_valor = cod_red
                    except Exception:
                        pass
                elif escolha == "-- SELECIONE --" and item["esta_no_mapa"]:
                    del st.session_state.depara_map[cod_atual]
                    st.rerun()

                if novo_valor:
                    st.session_state.depara_map[cod_atual] = novo_valor
                    st.rerun()

                if escolha == "📝 -- DIGITAR MANUALMENTE --":
                    val_ant = st.session_state.depara_map.get(cod_atual, "")
                    st.text_input(
                        f"Cód. manual para {cod_atual}:",
                        value=val_ant,
                        key=f"depara_in_{cod_atual}",
                        on_change=_atualizar_manual_depara,
                        args=(cod_atual,),
                    )

            st.markdown('<div class="cont-row"></div>', unsafe_allow_html=True)

    # ── Seção de downloads ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📂 Finalização e Downloads")

    col_d1, col_d2, col_d3, col_d4 = st.columns(4)

    # 1 — SPED Ajustado
    with col_d1:
        st.markdown("**1. SPED Ajustado (I250)**")
        if total_pendentes > 0:
            st.warning(f"⚠ Faltam {total_pendentes} conta(s).")
            st.button("🚀 Gerar SPED Ajustado", disabled=True, key="btn_sped_adj_dis")
        else:
            sped_bytes = _gerar_sped_ajustado_depara(conteudo_ecd, map_final, nome_empresa)
            st.download_button(
                "💾 Baixar SPED Ajustado",
                data=sped_bytes,
                file_name=f"SPED_AJUSTADO_{nome_empresa}.txt",
                mime="text/plain",
                use_container_width=True,
                key="dl_sped_ajustado",
            )

    # 2 — Balanço I155
    with col_d2:
        st.markdown("**2. Balanço (I155)**")
        from datetime import timedelta
        tipo_saldo = st.radio(
            "Referência:", ["Inicial (Abertura)", "Final (Fechamento)"],
            key="depara_tipo_saldo"
        )
        data_pad = datetime.today()
        if tipo_saldo == "Inicial (Abertura)" and dt_ini_sped:
            data_pad = dt_ini_sped - timedelta(days=1)
        elif tipo_saldo == "Final (Fechamento)" and dt_fin_sped:
            data_pad = dt_fin_sped

        data_bal = st.date_input("Data p/ Balanço:", data_pad,
                                  format="DD/MM/YYYY", key="depara_data_bal")
        dt_fmt   = data_bal.strftime("%d/%m/%Y")

        if st.button("🔍 Processar Balanço", key="btn_proc_balanco"):
            saldos_uso = (
                initial_balances
                if tipo_saldo == "Inicial (Abertura)"
                else final_balances
            )
            dados_bal, totais_bal, has_bal = _gerar_balanco_depara(
                map_final, saldos_uso, dt_fmt, tipo_saldo
            )
            st.session_state.depara_balanco_dados    = dados_bal
            st.session_state.depara_balanco_totais   = totais_bal
            st.session_state.depara_balanco_proc     = True
            st.session_state.depara_balanco_has_data = has_bal
            st.rerun()

        if st.session_state.depara_balanco_proc:
            tot  = st.session_state.depara_balanco_totais
            diff = round(tot["D"] - tot["C"], 2)
            st.caption(f"Débitos : {format_moeda(tot['D'])}")
            st.caption(f"Créditos: {format_moeda(tot['C'])}")
            if abs(diff) > 0.01:
                st.error(f"Diferença: {format_moeda(diff)}")
            else:
                st.success("✅ Diferença: R$ 0,00")
            if st.session_state.depara_balanco_has_data and total_pendentes == 0:
                st.download_button(
                    "💾 Baixar Balanço",
                    data=st.session_state.depara_balanco_dados,
                    file_name=f"BALANCO_{nome_empresa}_{dt_fmt.replace('/','')}.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key="dl_balanco",
                )

    # 3 — I157
    with col_d3:
        st.markdown("**3. Troca de Plano (I157)**")
        if st.button("🔄 Processar I157", key="btn_proc_i157"):
            dados_i157, has_i157 = _gerar_i157_depara(
                map_final, initial_balances, nome_empresa
            )
            st.session_state.depara_i157_dados     = dados_i157
            st.session_state.depara_i157_proc      = True
            st.session_state.depara_i157_has_data  = has_i157
            st.rerun()

        if st.session_state.depara_i157_proc:
            if st.session_state.depara_i157_has_data and total_pendentes == 0:
                st.success("✅ I157 gerado!")
                st.download_button(
                    "💾 Baixar I157",
                    data=st.session_state.depara_i157_dados,
                    file_name=f"I157_Saldos_{nome_empresa}.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key="dl_i157",
                )
            elif total_pendentes > 0:
                st.warning("Resolva as pendências primeiro.")
            else:
                st.warning("Sem saldos para gerar I157.")

    # 4 — Conferência / Pendentes
    with col_d4:
        st.markdown("**4. Conferência**")
        mapeadas_set = set(map_final.keys())
        df_pend = df_origem[~df_origem["cod"].isin(mapeadas_set)]
        if not df_pend.empty:
            st.warning(f"{len(df_pend)} conta(s) pendente(s).")
            csv_pend = df_pend.to_csv(index=False, sep=";", encoding="utf-8-sig")
            st.download_button(
                "📑 Baixar pendentes (.csv)",
                data=csv_pend.encode("utf-8-sig"),
                file_name="contas_pendentes.csv",
                mime="text/csv",
                use_container_width=True,
                key="dl_pendentes",
            )
        else:
            st.success("✅ Todas as contas mapeadas!")

    return map_final
	
	# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 3 — PARSER ECD UNIFICADO + MODOS DE SAÍDA
# (Lançamentos, Saldo Inicial, Saldo Final, I157, SPED Ajustado, 6110)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Helpers de pipe ──────────────────────────────────────────────────────────
def _split_pipe(linha: str) -> list:
    c = linha.strip().split("|")
    if c and c[0] == "":  c = c[1:]
    if c and c[-1] == "": c = c[:-1]
    return c

def _campo(campos: list, idx: int, default: str = "") -> str:
    return campos[idx].strip() if idx < len(campos) else default

def _conta_valida(conta: str) -> bool:
    return bool(conta) and conta.isdigit()

# ── Estrutura de dados do ECD ─────────────────────────────────────────────────
class SpedECD:
    def __init__(self):
        self.cnpj        = ""
        self.nome        = ""
        self.dt_ini      = ""
        self.dt_fin      = ""
        self.contas      = {}    # cod → nome
        self.historicos  = {}    # cod → desc
        self.lancamentos = []    # lista de lotes I200/I250

# ── Detecção de encoding ──────────────────────────────────────────────────────
def identificar_tipo(nome_arquivo: str, conteudo: bytes) -> str:
    ext = os.path.splitext(nome_arquivo)[1].lower()
    if ext in (".xlsx", ".xls", ".xlsm"): return "excel"
    enc = _detectar_encoding_bytes(conteudo)
    try:    amostra = conteudo[:8192].decode(enc, errors="replace")
    except: amostra = ""
    linhas = [l for l in amostra.splitlines() if l.strip()]
    for ln in linhas[:40]:
        if ln.startswith("|0000|") or ln.startswith("|I0"): return "ecd"
        campos = ln.split("|")
        if len(campos) >= 2 and campos[1] in (
            "0000","I010","I050","I075","I100","I150","I155",
            "I200","I250","I350","I355","I990"): return "ecd"
    for ln in linhas[:15]:
        s = ln.rstrip("\r\n")
        if len(s) >= 54 and s[:2] == "01" and s[43:44] == "N": return "dominio_pos"
        if len(s) >= 20 and s[:2] == "02" and s[9:10] in ("X","D","C","V"): return "dominio_pos"
    semis = sum(1 for ln in linhas[:20] if ";" in ln)
    if semis >= max(1, len(linhas[:20])//2): return "lote"
    return "lote"

# ── Pre-scan CNPJ ─────────────────────────────────────────────────────────────
def _pre_scan_cnpj_ecd(conteudo: bytes) -> str:
    enc = _detectar_encoding_bytes(conteudo)
    try:    amostra = conteudo[:4096].decode(enc, errors="replace")
    except: amostra = conteudo[:4096].decode("utf-8", errors="replace")
    for linha in amostra.splitlines():
        campos = _split_pipe(linha.strip())
        if campos and campos[0] == "0000" and len(campos) > 5:
            cnpj = re.sub(r"\D", "", campos[5].strip())
            if len(cnpj) == 14: return cnpj
    return ""

# ── Normalização de data ──────────────────────────────────────────────────────
def _normalizar_data_ecd(d: str) -> str:
    d = d.strip()
    if not d: return ""
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", d): return d
    if re.fullmatch(r"\d{8}", d): return f"{d[:2]}/{d[2:4]}/{d[4:]}"
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", d)
    if m: return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return d

def _fmt_data_ecd(d: str) -> str:
    d = d.strip()
    if "/" in d: return d
    if len(d) == 8 and d.isdigit(): return f"{d[:2]}/{d[2:4]}/{d[4:]}"
    return d

def _str2float(v) -> float:
    if isinstance(v, (int, float)): return float(v)
    v = str(v).strip()
    if "." in v and "," in v:
        if v.index(".") < v.index(","): v = v.replace(".", "").replace(",", ".")
        else: v = v.replace(",", "")
    elif "," in v: v = v.replace(",", ".")
    try:    return float(v)
    except: return 0.0

# ═══════════════════════════════════════════════════════════════════════════════
# PARSE PRINCIPAL DO ECD
# ═══════════════════════════════════════════════════════════════════════════════
def _parse_ecd_completo(conteudo: bytes, log: list) -> tuple:
    """
    Lê todos os registros relevantes do SPED ECD em uma única passagem:
      I050  → plano de contas
      I075  → históricos
      I150  → períodos
      I155  → saldos (inicial + final por período)
      I200  → cabeçalho do lançamento
      I250  → partidas do lançamento
      I355  → saldos de resultado (contas de receita/despesa)
    Retorna (SpedECD, saldos_dict, erros_list)
    """
    ecd = SpedECD()

    # ── Saldos ────────────────────────────────────────────────────────────────
    initial_balances: dict = {}   # cod → (val_str, dc)  — primeiro período
    final_balances:   dict = {}   # cod → (val_str, dc)  — último período
    saldos_i355:      dict = {}   # cod → (valor_float, dc)
    i155_por_periodo: dict = {}
    periodo_atual_idx        = -1
    rtl_count_i150           = 0

    # ── Plano / candidatas PL ─────────────────────────────────────────────────
    mapa_nome_cta:  dict = {}
    mapa_nat_cta:   dict = {}
    contas_pl_candidatas: list = []
    contas_i355_set: set  = set()

    # ── Lançamentos ───────────────────────────────────────────────────────────
    lote_atual = None
    i200_count = i250_count = 0

    # ── Erros ─────────────────────────────────────────────────────────────────
    erros_parse:    list = []
    contas_invalidas     = 0
    erros_fatais         = 0

    enc = _detectar_encoding_bytes(conteudo)
    log.append(f"  Encoding detectado : {enc}")
    try:    texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")
    linhas = texto.splitlines()
    log.append(f"  Total de linhas    : {len(linhas):,}")

    for num_linha, linha in enumerate(linhas, 1):
        linha_orig = linha
        linha      = linha.strip()
        if not linha: continue
        campos = _split_pipe(linha)
        if not campos: continue
        reg = campos[0]

        try:
            # ── Cabeçalho ────────────────────────────────────────────────────
            if reg == "0000":
                if len(campos) > 3: ecd.dt_ini = _campo(campos, 3).strip()
                if len(campos) > 4: ecd.dt_fin = _campo(campos, 4).strip()
                if len(campos) > 5: ecd.cnpj   = re.sub(r"\D", "", _campo(campos, 5).strip())
                if len(campos) > 6: ecd.nome    = _campo(campos, 6).strip()

            # ── Plano de contas ───────────────────────────────────────────────
            elif reg == "I050":
                if len(campos) < 6: continue
                cod_nat  = _campo(campos, 2).strip()
                ind_cta  = _campo(campos, 3).strip().upper()
                cod_cta  = _campo(campos, 5).strip()
                nome_cta = _campo(campos, 7).strip() if len(campos) > 7 else ""
                if not cod_cta: continue
                ecd.contas[cod_cta]   = nome_cta
                mapa_nome_cta[cod_cta] = nome_cta
                mapa_nat_cta[cod_cta]  = cod_nat

                # Candidatas a conta PL/Resultado
                eh_nat  = cod_nat in ("05", "09", "5", "9")
                nome_up = nome_cta.upper()
                eh_nome = any(p in nome_up for p in (
                    "SUPERAVIT","DÉFICIT","DEFICIT","RESULTADO",
                    "LUCRO","PREJUIZO","PREJUÍZO","SOBRA","PERDA",
                    "SURPLUS","RESULTADO DO EXERC","LUCROS OU PREJUIZ",
                ))
                if ind_cta == "A" and (eh_nat or eh_nome):
                    contas_pl_candidatas.append({
                        "cod_cta":  cod_cta,
                        "nome":     nome_cta,
                        "cod_nat":  cod_nat,
                        "cod_sup":  _campo(campos, 6).strip() if len(campos) > 6 else "",
                        "criterio": "COD_NAT" if eh_nat else "NOME",
                    })

            # ── Históricos ────────────────────────────────────────────────────
            elif reg == "I075":
                cod  = _campo(campos, 1)
                desc = _campo(campos, 2)
                if cod: ecd.historicos[cod] = _norm_hist(desc)

            # ── Períodos de saldo ─────────────────────────────────────────────
            elif reg == "I150":
                rtl_count_i150 += 1
                periodo_atual_idx += 1
                i155_por_periodo[periodo_atual_idx] = {}

            # ── Saldos I155 ───────────────────────────────────────────────────
            elif reg == "I155":
                if periodo_atual_idx < 0: continue
                cod_cta  = _campo(campos, 1).strip()
                val_ini  = _campo(campos, 4).strip()
                dc_ini   = _campo(campos, 5).strip().upper()
                val_fin  = _campo(campos, 7).strip()
                dc_fin   = _campo(campos, 8).strip().upper()
                if not cod_cta: continue
                if dc_ini not in ("D", "C"): dc_ini = "D"
                if dc_fin not in ("D", "C"): dc_fin = "D"

                # Saldo inicial — apenas do 1º período
                if cod_cta not in initial_balances:
                    if rtl_count_i150 <= 1:
                        initial_balances[cod_cta] = (val_ini, dc_ini)
                    else:
                        initial_balances[cod_cta] = ("0,00", dc_ini)

                # Saldo final — sempre sobrescreve (último período vence)
                final_balances[cod_cta] = (val_fin, dc_fin)

                # Para o parse de saldo inicial V3.6.2
                try:    vf = _str2float(val_fin)
                except: vf = 0.0
                i155_por_periodo[periodo_atual_idx][cod_cta] = (vf, dc_fin)

            # ── Saldos I355 ───────────────────────────────────────────────────
            elif reg == "I355":
                cod_cta = _campo(campos, 1).strip()
                vl_cta  = _campo(campos, 3).strip()
                ind_dc  = _campo(campos, 4).strip().upper()
                if not cod_cta: continue
                if ind_dc not in ("D", "C"): ind_dc = "D"
                try:    vf = _str2float(vl_cta)
                except: vf = 0.0
                saldos_i355[cod_cta] = (vf, ind_dc)
                contas_i355_set.add(cod_cta)

            # ── Lançamentos I200 ──────────────────────────────────────────────
            elif reg == "I200":
                lote_atual = {
                    "num":     _campo(campos, 1),
                    "data":    _campo(campos, 2),
                    "valor":   _campo(campos, 3),
                    "partidas": [],
                }
                ecd.lancamentos.append(lote_atual)
                i200_count += 1

            # ── Partidas I250 ─────────────────────────────────────────────────
            elif reg == "I250":
                if lote_atual is None:
                    erros_parse.append({
                        "linha":    num_linha,
                        "motivo":   "I250 sem I200 precedente",
                        "conteudo": linha_orig.strip(),
                    })
                    continue
                conta     = _campo(campos, 1)
                valor_str = _campo(campos, 3)
                dc        = _campo(campos, 4).upper()
                desc_hist = _norm_hist(_campo(campos, 7))
                if dc not in ("D", "C"):
                    erros_parse.append({
                        "linha":    num_linha,
                        "motivo":   f"IND_DC='{dc}' inválido",
                        "conteudo": linha_orig.strip(),
                    })
                    continue
                if not _conta_valida(conta):
                    erros_parse.append({
                        "linha":    num_linha,
                        "motivo":   f"Conta '{conta}' inválida",
                        "conteudo": linha_orig.strip(),
                    })
                    contas_invalidas += 1
                    continue
                lote_atual["partidas"].append({
                    "conta":      conta,
                    "valor":      valor_str,
                    "dc":         dc,
                    "descr_hist": desc_hist,
                })
                i250_count += 1

            elif reg in ("I299", "I300"):
                lote_atual = None

        except Exception as ex:
            erros_parse.append({
                "linha":    num_linha,
                "motivo":   f"Exceção: {ex}",
                "conteudo": linha_orig.strip(),
            })
            erros_fatais += 1
            if erros_fatais > 50:
                log.append("ERRO: muitos erros fatais — parse abortado.")
                return None, {}, erros_parse

    # ── Saldos finais consolidados ────────────────────────────────────────────
    saldos_i155_raw: dict = {}
    if i155_por_periodo:
        ultimo_idx      = max(i155_por_periodo.keys())
        saldos_i155_raw = i155_por_periodo[ultimo_idx]

    saldos_i155_pat = {
        cta: (v, dc)
        for cta, (v, dc) in saldos_i155_raw.items()
        if cta not in contas_i355_set
    }

    # ── Sugestão automática da conta PL ──────────────────────────────────────
    total_rec = sum(v for v, dc in saldos_i355.values() if dc == "C")
    total_des = sum(v for v, dc in saldos_i355.values() if dc == "D")
    resultado_liq_ref = round(abs(total_rec - total_des), 2)
    conta_pl_sugerida = _sugerir_conta_pl_v4(
        contas_pl_candidatas, saldos_i155_raw, resultado_liq_ref, log
    )
    if conta_pl_sugerida:
        st.session_state["conta_pl_sugerida"]      = conta_pl_sugerida
        st.session_state["conta_pl_sugerida_nome"] = mapa_nome_cta.get(conta_pl_sugerida, "")

    # ── Logs ─────────────────────────────────────────────────────────────────
    if not ecd.cnpj:
        log.append("ERRO: CNPJ não encontrado no registro 0000.")
        return None, {}, erros_parse

    log.append(f"  CNPJ               : {ecd.cnpj}")
    log.append(f"  Nome               : {ecd.nome}")
    log.append(f"  Período            : {_normalizar_data_ecd(ecd.dt_ini)} a {_normalizar_data_ecd(ecd.dt_fin)}")
    log.append(f"  Lançamentos (I200) : {i200_count:,}")
    log.append(f"  Partidas    (I250) : {i250_count:,}")
    log.append(f"  Saldos I155 pat.   : {len(saldos_i155_pat):,}")
    log.append(f"  Saldos I355        : {len(saldos_i355):,}")
    log.append(f"  Candidatas PL      : {len(contas_pl_candidatas):,}")
    if contas_invalidas: log.append(f"  Contas inválidas   : {contas_invalidas:,}")
    if erros_parse:      log.append(f"  Erros/avisos       : {len(erros_parse):,}")

    saldos_dict = {
        "initial_balances": initial_balances,
        "final_balances":   final_balances,
        "saldos_i355":      saldos_i355,
        "saldos_i155_pat":  saldos_i155_pat,
        "saldos_i155_raw":  saldos_i155_raw,
        "mapa_nome_cta":    mapa_nome_cta,
        "mapa_nat_cta":     mapa_nat_cta,
        "conta_pl_sugerida": conta_pl_sugerida,
    }
    return ecd, saldos_dict, erros_parse


# ── Sugestão de conta PL (V4 — sem dependência de st.session_state interno) ──
def _sugerir_conta_pl_v4(contas_pl_candidatas: list,
                          saldos_i155_raw: dict,
                          resultado_liquido: float,
                          log: list) -> str:
    if not contas_pl_candidatas:
        return ""
    candidatas_com_saldo = []
    for c in contas_pl_candidatas:
        cod = c["cod_cta"]
        if cod in saldos_i155_raw:
            v, dc = saldos_i155_raw[cod]
            diff  = abs(abs(v) - resultado_liquido)
            candidatas_com_saldo.append({**c, "saldo": v, "dc": dc, "diff": diff})

    if not candidatas_com_saldo:
        return contas_pl_candidatas[0]["cod_cta"]

    def _score(c):
        prioridade_nat = 0 if c["cod_nat"] in ("09", "9") else 1
        return (prioridade_nat, c["diff"])

    candidatas_com_saldo.sort(key=_score)
    melhor = candidatas_com_saldo[0]
    log.append(f"  Sugestão PL        : {melhor['cod_cta']} — {melhor['nome']}")
    return melhor["cod_cta"]


# ═══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DE LANÇAMENTOS (I200/I250 → 6000/6100)
# ═══════════════════════════════════════════════════════════════════════════════
def _montar_hist_ecd(p: dict) -> str:
    return p.get("descr_hist", "").strip()

def _primeiro_hist(partidas: list) -> str:
    for p in partidas:
        h = _montar_hist_ecd(p)
        if h: return h
    return ""

def _classif(nd: int, nc: int) -> str:
    if nd == 1 and nc == 1: return "X"
    if nd == 1 and nc > 1:  return "D"
    if nd > 1  and nc == 1: return "C"
    return "V"

def _linhas_ecd_lancamento(lanc: dict) -> list:
    partidas = lanc["partidas"]
    debs  = [p for p in partidas if p["dc"] == "D"]
    creds = [p for p in partidas if p["dc"] == "C"]
    if not debs or not creds: return []
    data = _fmt_data_ecd(lanc["data"])
    hist = _primeiro_hist(partidas)
    nd, nc = len(debs), len(creds)
    out = []

    def _h(p1, p2=None):
        h = _montar_hist_ecd(p1)
        if not h and p2: h = _montar_hist_ecd(p2)
        return h or hist

    if nd == 1 and nc == 1:
        db, cr = debs[0], creds[0]
        out.append(fmt_reg_6000("X"))
        out.append(fmt_reg_6100(data, db["conta"], cr["conta"], _str2float(db["valor"]), "", _h(db, cr)))

    elif nd == 1 and nc > 1:
        db = debs[0]
        out.append(fmt_reg_6000("D"))
        out.append(fmt_reg_6100(data, db["conta"], "", _str2float(db["valor"]), "", _h(db)))
        for cr in creds:
            out.append(fmt_reg_6100(data, "", cr["conta"], _str2float(cr["valor"]), "", _h(cr, db)))

    elif nd > 1 and nc == 1:
        cr = creds[0]
        out.append(fmt_reg_6000("C"))
        out.append(fmt_reg_6100(data, "", cr["conta"], _str2float(cr["valor"]), "", _h(cr)))
        for db in debs:
            out.append(fmt_reg_6100(data, db["conta"], "", _str2float(db["valor"]), "", _h(db, cr)))

    else:
        out.append(fmt_reg_6000("V"))
        for cr in creds:
            out.append(fmt_reg_6100(data, "", cr["conta"], _str2float(cr["valor"]), "", _h(cr)))
        for db in debs:
            out.append(fmt_reg_6100(data, db["conta"], "", _str2float(db["valor"]), "", _h(db)))

    return out


def _gerar_lancamentos_ecd(ecd: SpedECD, log: list,
                            prog_bar, status,
                            gerar_6110: bool = False,
                            map_depara: dict = None) -> list:
    """
    Converte os lançamentos I200/I250 para 6000/6100.
    Se map_depara não for None, substitui os códigos de conta.
    """
    linhas = [fmt_reg_0000(re.sub(r"\D", "", ecd.cnpj))]
    t6000 = t6100 = ignorados = 0
    debug = {"X": 0, "D": 0, "C": 0, "V": 0}
    total = len(ecd.lancamentos)

    for idx, lanc in enumerate(ecd.lancamentos):
        if idx % 500 == 0 or idx == total - 1:
            prog_bar.progress(min(55 + int(((idx + 1) / total) * 35), 99))
            status.text(f"Gerando lançamento {idx+1:,}/{total:,}...")

        if not lanc.get("partidas"):
            ignorados += 1
            continue

        # Aplica DE/PARA se ativo
        if map_depara:
            for p in lanc["partidas"]:
                p["conta"] = map_depara.get(p["conta"], p["conta"])

        novas = _linhas_ecd_lancamento(lanc)
        if not novas:
            ignorados += 1
            continue

        for l in novas:
            if l.startswith("|6000|"):
                tp = l.split("|")[2] if len(l.split("|")) > 2 else "?"
                debug[tp] = debug.get(tp, 0) + 1
                t6000 += 1
            elif l.startswith("|6100|"):
                t6100 += 1

        # Injeta 6110 após cada 6100 se solicitado
        if gerar_6110:
            novas_com_6110 = []
            for l in novas:
                novas_com_6110.append(l)
                if l.startswith("|6100|"):
                    campos_l = l.split("|")
                    if len(campos_l) >= 6:
                        deb_l  = campos_l[3].strip()
                        cred_l = campos_l[4].strip()
                        val_l  = campos_l[5].strip()
                        if deb_l and cred_l: modo = "ambos"
                        elif deb_l:          modo = "deb"
                        else:                modo = "cred"
                        for l6110 in _gerar_6110_linha(deb_l, cred_l, val_l, modo):
                            novas_com_6110.append(l6110)
            novas = novas_com_6110

        linhas.extend(novas)

    log.append(f"  Reg. 6000 gerados  : {t6000:,}")
    log.append(f"  Reg. 6100 gerados  : {t6100:,}")
    log.append(f"  Ignorados          : {ignorados:,}")
    log.append(f"  Tipos — X:{debug.get('X',0)} D:{debug.get('D',0)} "
               f"C:{debug.get('C',0)} V:{debug.get('V',0)}")
    return linhas


# ═══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DE SALDO INICIAL (I155/I355 → lançamento único)
# ═══════════════════════════════════════════════════════════════════════════════
def _calcular_resultado_liquido_i355(saldos_i355: dict) -> tuple:
    total_rec = sum(v for _, (v, dc) in saldos_i355.items() if dc == "C")
    total_des = sum(v for _, (v, dc) in saldos_i355.items() if dc == "D")
    resultado  = round(total_rec - total_des, 2)
    if resultado >= 0: return resultado, "C"
    else:              return abs(resultado), "D"


def _gerar_saldo_inicial_v4(saldos_dict: dict,
                              ni: str,
                              historico_prefixo: str,
                              modo: str,
                              conta_pl_resultado: str,
                              log: list) -> tuple:
    """
    Gera o lançamento único de saldo inicial.
    Retorna (bytes, resumo_dict, erros_list).
    """
    data_ref    = _normalizar_data_ecd(saldos_dict.get("data_ref", ""))
    saldos_pat  = saldos_dict["saldos_i155_pat"]
    saldos_i355 = saldos_dict["saldos_i355"]

    log.append(f"  Modo               : {modo}")

    if modo == "apenas_patrimonial":
        todos_saldos = dict(saldos_pat)
        log.append(f"  Contas incluídas   : {len(todos_saldos):,} (somente patrimoniais)")

    elif modo == "aberto_com_resultado":
        if not saldos_i355:
            log.append("  AVISO: Sem I355 — usando apenas patrimonial.")
            todos_saldos = dict(saldos_pat)
        elif not conta_pl_resultado:
            log.append("  ERRO: Conta PL não informada — usando apenas patrimonial.")
            todos_saldos = dict(saldos_pat)
        else:
            res_liq, dc_res = _calcular_resultado_liquido_i355(saldos_i355)
            total_rec = round(sum(v for _, (v, dc) in saldos_i355.items() if dc == "C"), 2)
            total_des = round(sum(v for _, (v, dc) in saldos_i355.items() if dc == "D"), 2)
            log.append(f"  I355 — Receitas    : R$ {total_rec:,.2f}")
            log.append(f"  I355 — Despesas    : R$ {total_des:,.2f}")
            log.append(f"  Resultado líquido  : R$ {res_liq:,.2f} "
                       f"({'Superávit' if dc_res=='C' else 'Déficit'})")

            todos_saldos = dict(saldos_pat)

            if conta_pl_resultado in todos_saldos:
                saldo_pl, dc_pl = todos_saldos[conta_pl_resultado]
                if dc_pl == "C" and dc_res == "C": novo_saldo = round(saldo_pl - res_liq, 2)
                elif dc_pl == "D" and dc_res == "D": novo_saldo = round(saldo_pl - res_liq, 2)
                elif dc_pl == "C" and dc_res == "D": novo_saldo = round(saldo_pl + res_liq, 2)
                else: novo_saldo = round(saldo_pl + res_liq, 2)

                if novo_saldo >= 0:
                    todos_saldos[conta_pl_resultado] = (novo_saldo, dc_pl)
                else:
                    dc_inv = "D" if dc_pl == "C" else "C"
                    todos_saldos[conta_pl_resultado] = (abs(novo_saldo), dc_inv)

                novo_v, novo_dc = todos_saldos[conta_pl_resultado]
                log.append(f"  Conta PL ajustada  : R$ {novo_v:,.2f} {novo_dc}")
            else:
                log.append(f"  AVISO: Conta {conta_pl_resultado} não encontrada no I155.")

            for cta, (v, dc) in saldos_i355.items():
                todos_saldos[cta] = (v, dc)

            log.append(f"  Contas incluídas   : {len(todos_saldos):,} "
                       f"(patrimonial + {len(saldos_i355):,} resultado)")
    else:
        todos_saldos = dict(saldos_pat)

    todos_saldos = {cta: (v, dc) for cta, (v, dc) in todos_saldos.items() if abs(v) > 1e-6}

    if not todos_saldos:
        log.append("  AVISO: Nenhum saldo diferente de zero.")
        return b"", {}, []

    debs  = sorted([(cta, v, dc) for cta, (v, dc) in todos_saldos.items() if dc == "D"], key=lambda x: x[0])
    creds = sorted([(cta, v, dc) for cta, (v, dc) in todos_saldos.items() if dc == "C"], key=lambda x: x[0])

    total_deb  = round(sum(v for _, v, _ in debs),  2)
    total_cred = round(sum(v for _, v, _ in creds), 2)
    diferenca  = round(abs(total_deb - total_cred), 2)
    balanceado = diferenca < TOL_VALOR

    log.append(f"  Partidas débito    : {len(debs):,}  → R$ {total_deb:,.2f}")
    log.append(f"  Partidas crédito   : {len(creds):,} → R$ {total_cred:,.2f}")
    log.append(f"  Diferença          : R$ {diferenca:,.2f}")
    log.append(f"  Balanceado         : {'SIM ✅' if balanceado else 'NAO ⚠'}")

    buf = io.StringIO()
    buf.write(fmt_reg_0000(ni) + "\n")

    nd, nc = len(debs), len(creds)
    if   nd == 1 and nc == 1: tp = "X"
    elif nd == 1 and nc > 1:  tp = "D"
    elif nd > 1  and nc == 1: tp = "C"
    else:                     tp = "V"
    buf.write(fmt_reg_6000(tp) + "\n")

    def _hist(cta):
        return _norm_hist(f"{(historico_prefixo or 'SALDO INICIAL').strip()} {cta}")[:250]

    if tp == "X":
        cta_d, v_d, _ = debs[0]; cta_c, v_c, _ = creds[0]
        buf.write(fmt_reg_6100(data_ref, cta_d, cta_c, round((v_d + v_c) / 2, 2), "", _hist(cta_d)) + "\n")
    elif tp == "D":
        cta_d, v_d, _ = debs[0]
        buf.write(fmt_reg_6100(data_ref, cta_d, "", v_d, "", _hist(cta_d)) + "\n")
        for cta_c, v_c, _ in creds:
            buf.write(fmt_reg_6100(data_ref, "", cta_c, v_c, "", _hist(cta_c)) + "\n")
    elif tp == "C":
        cta_c, v_c, _ = creds[0]
        buf.write(fmt_reg_6100(data_ref, "", cta_c, v_c, "", _hist(cta_c)) + "\n")
        for cta_d, v_d, _ in debs:
            buf.write(fmt_reg_6100(data_ref, cta_d, "", v_d, "", _hist(cta_d)) + "\n")
    else:
        for cta_c, v_c, _ in creds:
            buf.write(fmt_reg_6100(data_ref, "", cta_c, v_c, "", _hist(cta_c)) + "\n")
        for cta_d, v_d, _ in debs:
            buf.write(fmt_reg_6100(data_ref, cta_d, "", v_d, "", _hist(cta_d)) + "\n")

    n6100 = buf.getvalue().count("|6100|")
    log.append(f"  Tipo lançamento    : {tp}")
    log.append(f"  Reg. 6100 gerados  : {n6100:,}")

    resultado_bytes = buf.getvalue().encode("utf-8-sig")
    del buf

    resumo = {
        "data": data_ref, "total_debito": total_deb, "total_credito": total_cred,
        "diferenca": diferenca, "balanceado": balanceado,
        "qtd_debs": nd, "qtd_creds": nc, "tipo": tp, "n6100": n6100,
        "contas_i155": len(saldos_pat), "contas_i355": len(saldos_i355), "modo": modo,
    }
    erros_out = []
    if not balanceado:
        erros_out.append({
            "linha":    0,
            "motivo":   (f"Desbalanceado: dif. R$ {diferenca:,.2f} "
                         f"(D={total_deb:,.2f} / C={total_cred:,.2f}). "
                         f"Verifique a conta PL/Resultado informada."),
            "conteudo": "",
        })
    return resultado_bytes, resumo, erros_out


# ═══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DE SALDO FINAL (I155 → modo fechamento)
# ═══════════════════════════════════════════════════════════════════════════════
def _gerar_saldo_final_v4(saldos_dict: dict,
                           ni: str,
                           data_ref: str,
                           historico_prefixo: str,
                           map_depara: dict,
                           log: list) -> tuple:
    """
    Gera lançamento de saldo final a partir do I155.
    Se map_depara ativo, substitui os códigos.
    Retorna (bytes, resumo_dict, erros_list).
    """
    final_balances = saldos_dict["final_balances"]
    log.append(f"  Data referência    : {data_ref}")
    log.append(f"  Saldos I155 final  : {len(final_balances):,}")

    linhas = [fmt_reg_0000(ni), fmt_reg_6000("V")]
    total_d = total_c = 0.0
    has_data = False

    for cod_antigo, (val_str, dc) in sorted(final_balances.items()):
        cod_novo = map_depara.get(cod_antigo, cod_antigo) if map_depara else cod_antigo
        cod_novo = str(cod_novo).replace("|", "")
        try:    val_float = _str2float(val_str)
        except: val_float = 0.0
        if val_float <= 0: continue

        hist = _norm_hist(f"{(historico_prefixo or 'SALDO FINAL').strip()} {cod_novo}")
        if dc == "D":
            total_d += val_float
            linhas.append(fmt_reg_6100(data_ref, cod_novo, "", val_float, "", hist))
        else:
            total_c += val_float
            linhas.append(fmt_reg_6100(data_ref, "", cod_novo, val_float, "", hist))
        has_data = True

    diferenca  = round(abs(total_d - total_c), 2)
    balanceado = diferenca < TOL_VALOR
    log.append(f"  Total Débito       : R$ {total_d:,.2f}")
    log.append(f"  Total Crédito      : R$ {total_c:,.2f}")
    log.append(f"  Diferença          : R$ {diferenca:,.2f}")
    log.append(f"  Balanceado         : {'SIM ✅' if balanceado else 'NAO ⚠'}")

    dados = "\r\n".join(linhas).encode("utf-8-sig")
    resumo = {
        "data": data_ref, "total_debito": round(total_d, 2),
        "total_credito": round(total_c, 2), "diferenca": diferenca,
        "balanceado": balanceado, "n6100": len(linhas) - 2,
    }
    erros_out = []
    if not balanceado:
        erros_out.append({
            "linha":    0,
            "motivo":   f"Saldo final desbalanceado: dif. R$ {diferenca:,.2f}",
            "conteudo": "",
        })
    return dados if has_data else b"", resumo, erros_out


# ═══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DO SPED AJUSTADO (I250 com novos códigos)
# ═══════════════════════════════════════════════════════════════════════════════
def _gerar_sped_ajustado_v4(conteudo: bytes,
                              map_depara: dict,
                              log: list) -> bytes:
    """
    Copia o SPED ECD substituindo os códigos de conta nos registros I250.
    """
    enc = _detectar_encoding_bytes(conteudo)
    try:    texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")

    saida = []
    substituicoes = 0

    for linha in texto.splitlines():
        linha_s = linha.strip()
        if not linha_s: continue
        if linha_s.startswith("|9999|"):
            saida.append(linha_s)
            break
        if linha_s.startswith("|I250|"):
            campos = linha_s.split("|")
            if len(campos) > 2 and campos[2] in map_depara:
                novo_cod  = str(map_depara[campos[2]]).strip().replace("|", "")
                campos[2] = novo_cod
                substituicoes += 1
            saida.append("|".join(campos))
        else:
            saida.append(linha_s)

    log.append(f"  Substituições I250 : {substituicoes:,}")
    return "\r\n".join(saida).encode("latin-1", errors="replace")


# ═══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DO I157 (troca de plano)
# ═══════════════════════════════════════════════════════════════════════════════
def _gerar_i157_v4(map_depara: dict,
                    initial_balances: dict,
                    log: list) -> tuple:
    """
    Gera arquivo I157 com saldos iniciais remapeados.
    Retorna (bytes, has_data).
    """
    linhas   = ["ID;;;;;;"]
    items    = []

    for cod_antigo, cod_novo in map_depara.items():
        cod_novo_clean = str(cod_novo).replace("|", "")
        val_str, dc    = initial_balances.get(cod_antigo, ("0,00", "D"))
        try:    val_float = _str2float(val_str)
        except: val_float = 0.0
        if val_float > 0:
            items.append((cod_novo_clean, cod_antigo, val_str, dc))

    if not items:
        log.append("  I157               : sem saldos para gerar")
        return "\r\n".join(linhas).encode("latin-1", errors="replace"), False

    items.sort(key=lambda x: str(x[0]))
    for cod_novo, cod_antigo, val_str, dc in items:
        if "." in cod_antigo or not cod_antigo.isnumeric():
            linha = f"C;{cod_novo};;{cod_antigo};{val_str};{dc};"
        else:
            linha = f"C;{cod_novo};{cod_antigo};;{val_str};{dc};"
        linhas.append(linha)

    log.append(f"  I157               : {len(items):,} registros gerados")
    return "\r\n".join(linhas).encode("latin-1", errors="replace"), True


# ═══════════════════════════════════════════════════════════════════════════════
# RELATÓRIO DE ERROS
# ═══════════════════════════════════════════════════════════════════════════════
def _txt_erros_ecd(registros_erro: list, cnpj: str) -> str:
    linhas = [
        "=" * 70,
        "RELATÓRIO DE ERROS — SPED ECD",
        f"CNPJ : {cnpj}",
        f"Total: {len(registros_erro)}",
        "=" * 70, "",
    ]
    for i, r in enumerate(registros_erro, 1):
        linhas += [
            f"[{i:04d}] Linha   : {r.get('linha', '-')}",
            f"       Motivo  : {r.get('motivo', '')}",
            f"       Conteúdo: {r.get('conteudo', '')}",
            "",
        ]
    linhas += ["=" * 70, "FIM DO RELATÓRIO"]
    return "\n".join(linhas)
	
	# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 4 — ESTADO, WIDGETS (PASSOS 1–4) E MOTOR DE PROCESSAMENTO V4.0
# ═══════════════════════════════════════════════════════════════════════════════

# ── Estado global da sessão ───────────────────────────────────────────────────
def _init_state():
    defaults = {
        # Arquivo
        "arquivo_bytes":        None,
        "arquivo_nome":         "",
        "tipo_detectado":       None,
        "processado":           False,

        # CNPJ
        "cnpj_ecd":             "",
        "cnpj_ecd_fmt":         "",

        # Outputs
        "resultado_bytes":      None,
        "resultado_nome":       "saida.txt",
        "erros_bytes":          None,
        "erros_nome":           "erros.txt",
        "log_bytes":            None,
        "log_nome":             "log.txt",
        "log_linhas":           [],
        "metricas":             {},

        # Lote/Excel
        "resumo":               [],
        "erros_lote":           [],
        "sheets":               [],
        "sheet_sel":            "",

        # Filiais (posicional)
        "filiais_detectadas":   [],
        "mapa_filiais_df":      None,

        # Saldo Inicial
        "hist_prefixo_si":      "SALDO INICIAL",
        "modo_resultado_si":    "apenas_patrimonial",
        "conta_pl_resultado_si": "",
        "conta_pl_sugerida":    "",
        "conta_pl_sugerida_nome": "",

        # Modos de saída V4.0
        "modo_lancamentos":     True,
        "modo_saldo_inicial":   False,
        "modo_i157":            False,
        "modo_sped_ajustado":   False,
        "modo_6110":            False,
        "modo_depara_ativo":    False,

        # DE/PARA
        "depara_map":           {},
        "depara_plano_df":      None,
        "depara_plano_nome":    "",
        "depara_backup_id":     "",
        "depara_balanco_proc":  False,
        "depara_balanco_dados": None,
        "depara_balanco_totais": {},
        "depara_balanco_has_data": False,
        "depara_i157_proc":     False,
        "depara_i157_dados":    None,
        "depara_i157_has_data": False,
        "depara_ocultar_mapeadas": False,

        # Comparação I052
        "i052_resultado":       None,
        "i052_parsed_ant":      None,
        "i052_parsed_atu":      None,
        "i052_label_ant":       "",
        "i052_label_atu":       "",
        "i052_log":             [],

        # Resultados múltiplos V4.0
        "v4_resultados":        {},   # chave → bytes
        "v4_metricas":          {},   # chave → dict
        "v4_erros":             {},   # chave → list
        "v4_ecd":               None, # objeto SpedECD parseado
        "v4_saldos_dict":       None, # dict de saldos do parse
        "v4_erros_parse":       [],   # erros do _parse_ecd_completo
        "v4_map_depara":        {},   # mapa final cod_antigo→cod_novo
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset():
    """Limpa tudo exceto DE/PARA (preserva progresso de mapeamento)."""
    preserve = {
        "depara_map", "depara_plano_df", "depara_plano_nome",
        "depara_backup_id", "depara_ocultar_mapeadas",
        "conta_pl_sugerida", "conta_pl_sugerida_nome",
    }
    for k, v in {
        "arquivo_bytes": None, "arquivo_nome": "", "tipo_detectado": None,
        "processado": False, "cnpj_ecd": "", "cnpj_ecd_fmt": "",
        "resultado_bytes": None, "resultado_nome": "saida.txt",
        "erros_bytes": None, "erros_nome": "erros.txt",
        "log_bytes": None, "log_nome": "log.txt",
        "log_linhas": [], "metricas": {}, "resumo": [], "erros_lote": [],
        "sheets": [], "sheet_sel": "", "filiais_detectadas": [],
        "mapa_filiais_df": None,
        "v4_resultados": {}, "v4_metricas": {}, "v4_erros": {},
        "v4_ecd": None, "v4_saldos_dict": None,
        "v4_erros_parse": [], "v4_map_depara": {},
        "depara_balanco_proc": False, "depara_balanco_dados": None,
        "depara_balanco_totais": {}, "depara_balanco_has_data": False,
        "depara_i157_proc": False, "depara_i157_dados": None,
        "depara_i157_has_data": False,
        "i052_resultado": None, "i052_parsed_ant": None,
        "i052_parsed_atu": None, "i052_label_ant": "",
        "i052_label_atu": "", "i052_log": [],
    }.items():
        if k not in preserve:
            st.session_state[k] = v


# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR DE PROCESSAMENTO V4.0 (UNIFICADO)
# ═══════════════════════════════════════════════════════════════════════════════
def _processar_v4(conteudo: bytes, ni: str,
                  modos: dict, opcoes: dict,
                  log: list, prog_bar, status) -> dict:
    """
    Ponto de entrada único para todos os modos de saída do ECD V4.0.

    modos = {
        "lancamentos":   bool,
        "saldo_inicial": bool,
        "saldo_final":   bool,
        "i157":          bool,
        "sped_ajustado": bool,
        "gerar_6110":    bool,
    }
    opcoes = {
        "modo_resultado_si": str,   # "apenas_patrimonial" | "aberto_com_resultado"
        "conta_pl":          str,
        "hist_prefixo_si":   str,
        "data_ref_sf":       str,   # data do saldo final (DD/MM/YYYY)
        "hist_prefixo_sf":   str,
        "map_depara":        dict,  # {} se DE/PARA inativo
        "depara_ativo":      bool,
    }
    Retorna dict com chaves = nomes dos arquivos gerados → bytes.
    """
    resultados:  dict = {}
    metricas_v4: dict = {}
    erros_v4:    dict = {}
    crono = Cronometro()
    crono.iniciar()

    # ── 1. PARSE ÚNICO ────────────────────────────────────────────────────────
    crono.etapa("Parse ECD")
    status.text("Lendo SPED ECD (parse único)...")
    prog_bar.progress(5)
    log.append("── PARSE SPED ECD V4.0 (passagem única) ──")

    ecd, saldos_dict, erros_parse = _parse_ecd_completo(conteudo, log)
    st.session_state.v4_ecd         = ecd
    st.session_state.v4_saldos_dict = saldos_dict
    st.session_state.v4_erros_parse = erros_parse

    if ecd is None:
        log.append("ERRO FATAL: parse retornou None — abortando.")
        return {}, {}, erros_parse

    # ── 2. DE/PARA — resolve mapa final ──────────────────────────────────────
    map_depara = {}
    if opcoes.get("depara_ativo") and opcoes.get("map_depara"):
        map_depara = opcoes["map_depara"]
        log.append(f"  DE/PARA ativo      : {len(map_depara):,} regras")
    st.session_state.v4_map_depara = map_depara

    prog_bar.progress(20)

    # ── 3. LANÇAMENTOS (I200/I250 → 6000/6100) ────────────────────────────────
    if modos.get("lancamentos"):
        crono.etapa("Lançamentos")
        status.text("Gerando lançamentos (I200/I250 → 6000/6100)...")
        log.append("\n── LANÇAMENTOS ──")
        try:
            linhas_lanc = _gerar_lancamentos_ecd(
                ecd, log, prog_bar, status,
                gerar_6110=modos.get("gerar_6110", False),
                map_depara=map_depara if map_depara else None,
            )
            buf = io.StringIO()
            for i in range(0, len(linhas_lanc), WRITE_CHUNK):
                buf.write("\n".join(linhas_lanc[i:i + WRITE_CHUNK]) + "\n")
            bytes_lanc = buf.getvalue().encode("utf-8-sig")
            del buf, linhas_lanc
            gc.collect()

            n6000 = bytes_lanc.count(b"|6000|")
            n6100 = bytes_lanc.count(b"|6100|")
            n6110 = bytes_lanc.count(b"|6110|")
            nome_lanc = f"ECD_LANCAMENTOS_{ni}.txt"
            resultados[nome_lanc]  = bytes_lanc
            metricas_v4["lancamentos"] = {
                "Reg. 6000": f"{n6000:,}",
                "Reg. 6100": f"{n6100:,}",
                "Reg. 6110": f"{n6110:,}" if modos.get("gerar_6110") else "—",
                "Tamanho":   f"{len(bytes_lanc)/1024:.1f} KB",
            }
            log.append(f"  Arquivo gerado     : {nome_lanc}")
        except Exception as ex:
            log.append(f"  ERRO lançamentos   : {ex}")
            erros_v4["lancamentos"] = [{"linha": 0, "motivo": str(ex), "conteudo": ""}]

    prog_bar.progress(40)

    # ── 4. SALDO INICIAL ──────────────────────────────────────────────────────
    if modos.get("saldo_inicial"):
        crono.etapa("Saldo Inicial")
        status.text("Gerando saldo inicial (I155/I355)...")
        log.append("\n── SALDO INICIAL ──")
        try:
            # Injeta data_ref no saldos_dict para compatibilidade
            sd_si = dict(saldos_dict)
            dt_ini_raw = ecd.dt_ini if hasattr(ecd, "dt_ini") else ""
            sd_si["data_ref"] = _normalizar_data_ecd(dt_ini_raw)

            bytes_si, resumo_si, erros_si = _gerar_saldo_inicial_v4(
                sd_si, ni,
                opcoes.get("hist_prefixo_si", "SALDO INICIAL"),
                opcoes.get("modo_resultado_si", "apenas_patrimonial"),
                opcoes.get("conta_pl", ""),
                log,
            )
            nome_si = f"ECD_SALDO_INICIAL_{ni}.txt"
            resultados[nome_si]  = bytes_si
            metricas_v4["saldo_inicial"] = resumo_si
            if erros_si:
                erros_v4["saldo_inicial"] = erros_si
            log.append(f"  Arquivo gerado     : {nome_si}")
        except Exception as ex:
            log.append(f"  ERRO saldo inicial : {ex}")
            erros_v4["saldo_inicial"] = [{"linha": 0, "motivo": str(ex), "conteudo": ""}]

    prog_bar.progress(55)

    # ── 5. SALDO FINAL ────────────────────────────────────────────────────────
    if modos.get("saldo_final"):
        crono.etapa("Saldo Final")
        status.text("Gerando saldo final (I155 → fechamento)...")
        log.append("\n── SALDO FINAL ──")
        try:
            data_sf = opcoes.get("data_ref_sf", "")
            if not data_sf:
                data_sf = _normalizar_data_ecd(
                    ecd.dt_fin if hasattr(ecd, "dt_fin") else ""
                )
            bytes_sf, resumo_sf, erros_sf = _gerar_saldo_final_v4(
                saldos_dict, ni, data_sf,
                opcoes.get("hist_prefixo_sf", "SALDO FINAL"),
                map_depara if map_depara else None,
                log,
            )
            nome_sf = f"ECD_SALDO_FINAL_{ni}.txt"
            resultados[nome_sf]  = bytes_sf
            metricas_v4["saldo_final"] = resumo_sf
            if erros_sf:
                erros_v4["saldo_final"] = erros_sf
            log.append(f"  Arquivo gerado     : {nome_sf}")
        except Exception as ex:
            log.append(f"  ERRO saldo final   : {ex}")
            erros_v4["saldo_final"] = [{"linha": 0, "motivo": str(ex), "conteudo": ""}]

    prog_bar.progress(70)

    # ── 6. I157 (troca de plano) ──────────────────────────────────────────────
    if modos.get("i157") and map_depara:
        crono.etapa("I157")
        status.text("Gerando I157 (troca de plano)...")
        log.append("\n── I157 ──")
        try:
            bytes_i157, has_i157 = _gerar_i157_v4(
                map_depara,
                saldos_dict.get("initial_balances", {}),
                log,
            )
            nome_i157 = f"I157_SALDOS_{ni}.txt"
            if has_i157:
                resultados[nome_i157] = bytes_i157
                metricas_v4["i157"] = {"Registros": str(bytes_i157.count(b"\n"))}
                log.append(f"  Arquivo gerado     : {nome_i157}")
            else:
                log.append("  I157               : sem saldos — arquivo não gerado")
        except Exception as ex:
            log.append(f"  ERRO I157          : {ex}")
            erros_v4["i157"] = [{"linha": 0, "motivo": str(ex), "conteudo": ""}]

    elif modos.get("i157") and not map_depara:
        log.append("  I157               : DE/PARA inativo — I157 requer mapeamento ativo")

    prog_bar.progress(82)

    # ── 7. SPED AJUSTADO (I250 com novos códigos) ─────────────────────────────
    if modos.get("sped_ajustado") and map_depara:
        crono.etapa("SPED Ajustado")
        status.text("Gerando SPED Ajustado (I250 com novos códigos)...")
        log.append("\n── SPED AJUSTADO ──")
        try:
            bytes_adj = _gerar_sped_ajustado_v4(conteudo, map_depara, log)
            nome_adj  = f"SPED_AJUSTADO_{ni}.txt"
            resultados[nome_adj]  = bytes_adj
            metricas_v4["sped_ajustado"] = {
                "Tamanho": f"{len(bytes_adj)/1024:.1f} KB"
            }
            log.append(f"  Arquivo gerado     : {nome_adj}")
        except Exception as ex:
            log.append(f"  ERRO SPED ajustado : {ex}")
            erros_v4["sped_ajustado"] = [{"linha": 0, "motivo": str(ex), "conteudo": ""}]

    elif modos.get("sped_ajustado") and not map_depara:
        log.append("  SPED Ajustado      : DE/PARA inativo — ignorado")

    prog_bar.progress(92)

    # ── 8. Relatório de erros de parse ────────────────────────────────────────
    if erros_parse:
        txt_err = _txt_erros_ecd(erros_parse, ni)
        st.session_state.erros_bytes = txt_err.encode("utf-8-sig")
        st.session_state.erros_nome  = f"ECD_{ni}_erros_parse.txt"
        log.append(f"\n  Erros de parse     : {len(erros_parse):,} — relatório gerado")

    # ── 9. Tempo total ────────────────────────────────────────────────────────
    total_seg = crono.encerrar()
    log.append(f"\n── TEMPO TOTAL: {Cronometro.fmt(total_seg)} ──")
    for e in crono.etapas:
        log.append(f"  {e['nome']:<30} {Cronometro.fmt(e['segundos'])}")

    prog_bar.progress(100)
    status.text("✅ Concluído!")

    return resultados, metricas_v4, erros_v4


# ═══════════════════════════════════════════════════════════════════════════════
# RENDERIZAÇÃO DOS RESULTADOS V4.0
# ═══════════════════════════════════════════════════════════════════════════════
def _render_resultados_v4(exibir_log: bool):
    resultados  = st.session_state.get("v4_resultados", {})
    metricas_v4 = st.session_state.get("v4_metricas", {})
    erros_v4    = st.session_state.get("v4_erros", {})
    log_linhas  = st.session_state.get("log_linhas", [])

    st.markdown("---")
    st.markdown("## 📦 Passo 5 — Downloads")

    if not resultados:
        st.warning("Nenhum arquivo gerado. Verifique as opções selecionadas.")
        return

    # ── Métricas gerais ───────────────────────────────────────────────────────
    total_arqs  = len(resultados)
    total_erros = sum(len(v) for v in erros_v4.values())
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Arquivos gerados",  f"{total_arqs}")
    col_m2.metric("Módulos com erro",  f"{len(erros_v4)}", delta_color="inverse")
    col_m3.metric("Erros de parse",
                  f"{len(st.session_state.get('v4_erros_parse', []))}",
                  delta_color="inverse")

    # ── Downloads por módulo ──────────────────────────────────────────────────
    st.markdown("### 📂 Arquivos Gerados")

    _ICONES = {
        "LANCAMENTOS":    "📒",
        "SALDO_INICIAL":  "📥",
        "SALDO_FINAL":    "📤",
        "I157":           "🔄",
        "SPED_AJUSTADO":  "📋",
    }

    for nome_arq, bytes_arq in resultados.items():
        if not bytes_arq:
            continue
        icone = "📄"
        for chave, ico in _ICONES.items():
            if chave in nome_arq.upper():
                icone = ico
                break

        with st.container():
            col_info, col_dl = st.columns([3, 1])
            with col_info:
                st.markdown(f"**{icone} {nome_arq}**")
                st.caption(f"{len(bytes_arq)/1024:.1f} KB")

                # Métricas específicas do módulo
                chave_mod = None
                if "LANCAMENTOS"   in nome_arq.upper(): chave_mod = "lancamentos"
                elif "SALDO_INICIAL" in nome_arq.upper(): chave_mod = "saldo_inicial"
                elif "SALDO_FINAL"   in nome_arq.upper(): chave_mod = "saldo_final"
                elif "I157"          in nome_arq.upper(): chave_mod = "i157"
                elif "AJUSTADO"      in nome_arq.upper(): chave_mod = "sped_ajustado"

                if chave_mod and chave_mod in metricas_v4:
                    met = metricas_v4[chave_mod]
                    if isinstance(met, dict):
                        partes = []
                        for k, v in met.items():
                            if v and v != "—":
                                partes.append(f"**{k}:** {v}")
                        if partes:
                            st.markdown(" &nbsp;|&nbsp; ".join(partes))

                        # Alerta de balanceamento para saldos
                        if chave_mod in ("saldo_inicial", "saldo_final"):
                            bal = met.get("balanceado", True)
                            if isinstance(bal, bool) and not bal:
                                dif = met.get("diferenca", 0)
                                st.error(f"⚠ Desbalanceado: R$ {dif:,.2f} de diferença")
                            elif isinstance(bal, bool) and bal:
                                st.success("✅ Balanceado (D = C)")

                # Erros do módulo
                if chave_mod and chave_mod in erros_v4:
                    errs = erros_v4[chave_mod]
                    st.warning(f"⚠ {len(errs)} erro(s) neste módulo")

            with col_dl:
                st.download_button(
                    f"⬇ Baixar",
                    data=bytes_arq,
                    file_name=nome_arq,
                    mime="text/plain",
                    use_container_width=True,
                    key=f"dl_{nome_arq}",
                )
            st.markdown('<div class="cont-row"></div>', unsafe_allow_html=True)

    # ── Relatório de erros de parse ───────────────────────────────────────────
    if st.session_state.get("erros_bytes"):
        st.markdown("### ⚠ Relatório de Erros")
        st.download_button(
            "⬇ Baixar relatório de erros de parse",
            data=st.session_state.erros_bytes,
            file_name=st.session_state.erros_nome,
            mime="text/plain",
            use_container_width=True,
            key="dl_erros_parse",
        )

    # ── Log ───────────────────────────────────────────────────────────────────
    if exibir_log and log_linhas:
        st.markdown("### 🖥 Log de Processamento")
        log_txt  = "\n".join(str(l) for l in log_linhas)
        tem_erro = any("ERRO" in str(l).upper() for l in log_linhas)
        st.markdown(
            f"<div class='bloco-log' style='border-color:"
            f"{'#FF4444' if tem_erro else '#1A3050'};'>{log_txt}</div>",
            unsafe_allow_html=True
        )
        col_dl_log1, col_dl_log2 = st.columns(2)
        with col_dl_log1:
            st.download_button(
                "⬇ Baixar log completo",
                data=log_txt.encode("utf-8-sig"),
                file_name="log_v4.txt",
                mime="text/plain",
                use_container_width=True,
                key="dl_log_v4",
            )


# ═══════════════════════════════════════════════════════════════════════════════
# WIDGETS DOS PASSOS 1–4 (interface principal V4.0)
# ═══════════════════════════════════════════════════════════════════════════════
def _render_passos_ecd(conteudo: bytes, exibir_log: bool):
    """
    Renderiza os Passos 2, 3 e 4 para arquivos SPED ECD.
    Retorna True se o botão Processar foi clicado.
    """
    ni = ""; ok_insc = False

    # ── PASSO 2 — CNPJ ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🏢 Passo 2 — CNPJ (auto-detectado)")

    cnpj_ecd = st.session_state.cnpj_ecd
    if cnpj_ecd and validar_cnpj(cnpj_ecd):
        st.markdown(
            f"<div class='cnpj-auto'>✔ CNPJ extraído automaticamente: "
            f"<span>{st.session_state.cnpj_ecd_fmt}</span></div>",
            unsafe_allow_html=True
        )
        st.code(fmt_reg_0000(cnpj_ecd), language=None)
        ok_insc = True
        ni      = cnpj_ecd
    else:
        st.warning("⚠ CNPJ não encontrado no registro 0000. Informe manualmente.")
        cnpj_raw = st.text_input(
            "CNPJ / CPF", placeholder="00.000.000/0001-00",
            key="cnpj_manual_v4"
        )
        ok_insc, ti, ni = validar_inscricao(cnpj_raw)
        if cnpj_raw:
            if ok_insc:
                inf = fmt_cnpj(ni) if ti == "CNPJ" else fmt_cpf(ni)
                st.success(f"✔ {ti} válido: {inf}")
            else:
                st.error("✖ CNPJ/CPF inválido")

    # ── PASSO 3 — DE/PARA (opcional) ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔀 Passo 3 — [OPCIONAL] DE/PARA de Contas")

    depara_ativo = st.checkbox(
        "Ativar módulo DE/PARA de contas",
        value=st.session_state.get("modo_depara_ativo", False),
        key="chk_depara_ativo"
    )
    st.session_state.modo_depara_ativo = depara_ativo

    map_depara = {}
    if depara_ativo:
        map_depara = render_modulo_depara(conteudo, ativo=True)
        st.session_state.v4_map_depara = map_depara
    else:
        st.markdown(
            "<div class='info-box'>ℹ DE/PARA desabilitado. "
            "As contas serão mantidas com os códigos originais do SPED ECD.</div>",
            unsafe_allow_html=True
        )

    # ── PASSO 4 — MODO DE SAÍDA ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ⚙ Passo 4 — Modo de Saída")

    st.markdown(
        "<div class='info-box'>Selecione os arquivos que deseja gerar. "
        "Múltiplas saídas podem ser geradas em um único processamento.</div>",
        unsafe_allow_html=True
    )

    col_cb1, col_cb2 = st.columns(2)

    with col_cb1:
        modo_lanc = st.checkbox(
            "📒 Lançamentos (I200/I250 → 6000/6100)",
            value=st.session_state.get("modo_lancamentos", True),
            key="chk_modo_lanc"
        )
        st.session_state.modo_lancamentos = modo_lanc

        modo_si = st.checkbox(
            "📥 Saldo Inicial (I155/I355 → lançamento único)",
            value=st.session_state.get("modo_saldo_inicial", False),
            key="chk_modo_si"
        )
        st.session_state.modo_saldo_inicial = modo_si

        modo_sf = st.checkbox(
            "📤 Saldo Final (I155 → modo fechamento)",
            value=st.session_state.get("modo_saldo_final", False),
            key="chk_modo_sf"
        )
        st.session_state.modo_saldo_final = modo_sf

    with col_cb2:
        modo_i157 = st.checkbox(
            "🔄 I157 — Troca de Plano (requer DE/PARA ativo)",
            value=st.session_state.get("modo_i157", False),
            disabled=not depara_ativo,
            key="chk_modo_i157"
        )
        st.session_state.modo_i157 = modo_i157

        modo_adj = st.checkbox(
            "📋 SPED Ajustado (I250 com novos códigos — requer DE/PARA ativo)",
            value=st.session_state.get("modo_sped_ajustado", False),
            disabled=not depara_ativo,
            key="chk_modo_adj"
        )
        st.session_state.modo_sped_ajustado = modo_adj

        modo_6110 = st.checkbox(
            "🏷 Centro de Custo (6110)",
            value=st.session_state.get("modo_6110", False),
            key="chk_modo_6110"
        )
        st.session_state.modo_6110 = modo_6110

    # ── Sub-opções Saldo Inicial ──────────────────────────────────────────────
    conta_pl = ""
    if modo_si:
        st.markdown("##### 📥 Opções — Saldo Inicial")
        col_si1, col_si2 = st.columns([1, 2])
        with col_si1:
            hist_prefixo_si = st.text_input(
                "Prefixo do histórico",
                value=st.session_state.get("hist_prefixo_si", "SALDO INICIAL"),
                max_chars=60, key="hist_si_v4"
            )
            st.session_state.hist_prefixo_si = hist_prefixo_si
        with col_si2:
            modo_resultado_si = st.radio(
                "Tratamento das contas de Resultado (I355):",
                options=["apenas_patrimonial", "aberto_com_resultado"],
                format_func=lambda x: {
                    "apenas_patrimonial":   "✅ Apenas Patrimonial (balanço fechado)",
                    "aberto_com_resultado": "📂 Aberto com Resultado (inclui I355)",
                }[x],
                index=0 if st.session_state.get(
                    "modo_resultado_si", "apenas_patrimonial"
                ) == "apenas_patrimonial" else 1,
                key="modo_res_si_v4"
            )
            st.session_state.modo_resultado_si = modo_resultado_si

        if modo_resultado_si == "aberto_com_resultado":
            sugerida      = st.session_state.get("conta_pl_sugerida", "")
            sugerida_nome = st.session_state.get("conta_pl_sugerida_nome", "")
            if sugerida:
                st.markdown(
                    f"<div class='si-box'>"
                    f"<b style='color:#FF9EBC;'>💡 Conta sugerida:</b> "
                    f"<span style='color:#FFD166;font-weight:700;'>{sugerida}</span>"
                    f" — {sugerida_nome}</div>",
                    unsafe_allow_html=True
                )
            conta_pl = st.text_input(
                "Código da conta de Superávit/Déficit (PL/Resultado)",
                value=sugerida or st.session_state.get("conta_pl_resultado_si", ""),
                placeholder="Ex: 311010101",
                key="conta_pl_v4"
            )
            st.session_state.conta_pl_resultado_si = conta_pl
            if not conta_pl:
                st.warning("⚠ Informe a conta PL para que o balanço feche (D = C).")


    # ── Validação antes de processar ──────────────────────────────────────────
    algum_modo = any([
        modo_lanc, modo_si, modo_sf,
        modo_i157 and depara_ativo,
        modo_adj  and depara_ativo,
    ])

    if not algum_modo:
        st.warning("⚠ Selecione ao menos um modo de saída.")

    # ── PASSO 5 — Botão Processar ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ▶ Passo 5 — Processar e Downloads")

    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        btn_processar = st.button(
            "▶ PROCESSAR SPED ECD",
            disabled=(not ok_insc or not algum_modo),
            use_container_width=True,
            type="primary",
            key="btn_processar_v4"
        )
    with col_btn2:
        btn_limpar = st.button(
            "🗑 Limpar", use_container_width=True, key="btn_limpar_v4"
        )

    if btn_limpar:
        _reset()
        st.rerun()

    if btn_processar and ok_insc and algum_modo:
        log      = []
        status   = st.empty()
        prog_bar = st.progress(0)

        modos = {
            "lancamentos":   modo_lanc,
            "saldo_inicial": modo_si,
            "saldo_final":   modo_sf,
            "i157":          modo_i157 and depara_ativo,
            "sped_ajustado": modo_adj  and depara_ativo,
            "gerar_6110":    modo_6110,
        }
        opcoes = {
            "modo_resultado_si": st.session_state.get(
                "modo_resultado_si", "apenas_patrimonial"
            ),
            "conta_pl":          conta_pl,
            "hist_prefixo_si":   st.session_state.get("hist_prefixo_si", "SALDO INICIAL"),
            "data_ref_sf":       data_ref_sf,
            "hist_prefixo_sf":   hist_prefixo_sf,
            "map_depara":        map_depara,
            "depara_ativo":      depara_ativo,
        }

        try:
            resultados, metricas_v4, erros_v4 = _processar_v4(
                conteudo, ni, modos, opcoes, log, prog_bar, status
            )
            st.session_state.v4_resultados = resultados
            st.session_state.v4_metricas   = metricas_v4
            st.session_state.v4_erros      = erros_v4
            st.session_state.log_linhas    = log
            st.session_state.processado    = True

        except Exception as ex:
            tb = traceback.format_exc()
            st.error(f"⛔ Erro inesperado: {ex}")
            log.append(f"ERRO FATAL: {ex}\n{tb}")
            st.session_state.log_linhas = log
            prog_bar.progress(0)
            status.text("Falha.")

        st.rerun()

    # ── Resultados (após processamento) ───────────────────────────────────────
    if st.session_state.processado and st.session_state.get("v4_resultados"):
        _render_resultados_v4(exibir_log)

    return btn_processar if "btn_processar" in dir() else False

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO COMPLEMENTAR — Funções faltantes no V4.0
# Cole este bloco ANTES da função main()
# ═══════════════════════════════════════════════════════════════════════════════

# ── 1. _pre_scan_conta_pl_sugerida ───────────────────────────────────────────
def _pre_scan_conta_pl_sugerida(conteudo: bytes):
    """
    Lê I050 / I150 / I155 / I355 para sugerir a conta PL
    sem processar o arquivo completo.
    Grava resultado no st.session_state.
    """
    enc = _detectar_encoding_bytes(conteudo)
    try:    texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")

    contas_pl_candidatas = []
    saldos_i355          = {}
    mapa_nome_cta        = {}
    i155_por_periodo     = {}
    periodo_atual_idx    = -1

    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha: continue
        campos = _split_pipe(linha)
        if not campos: continue
        reg = campos[0]

        if reg == "I050":
            if len(campos) < 6: continue
            cod_nat  = _campo(campos, 2).strip()
            ind_cta  = _campo(campos, 3).strip().upper()
            cod_cta  = _campo(campos, 5).strip()
            nome_cta = _campo(campos, 7).strip() if len(campos) > 7 else ""
            if not cod_cta: continue
            mapa_nome_cta[cod_cta] = nome_cta
            eh_nat  = cod_nat in ("05", "09", "5", "9")
            nome_up = nome_cta.upper()
            eh_nome = any(p in nome_up for p in (
                "SUPERAVIT","DÉFICIT","DEFICIT","RESULTADO",
                "LUCRO","PREJUIZO","PREJUÍZO","SOBRA","PERDA",
                "SURPLUS","RESULTADO DO EXERC","LUCROS OU PREJUIZ",
            ))
            if ind_cta == "A" and (eh_nat or eh_nome):
                contas_pl_candidatas.append({
                    "cod_cta":  cod_cta,
                    "nome":     nome_cta,
                    "cod_nat":  cod_nat,
                    "cod_sup":  _campo(campos, 6).strip() if len(campos) > 6 else "",
                    "criterio": "COD_NAT" if eh_nat else "NOME",
                })

        elif reg == "I150":
            periodo_atual_idx += 1
            i155_por_periodo[periodo_atual_idx] = {}

        elif reg == "I155":
            if periodo_atual_idx < 0: continue
            cod_cta = _campo(campos, 1).strip()
            vl_fin  = _campo(campos, 7).strip()
            ind_dc  = _campo(campos, 8).strip().upper()
            if not cod_cta: continue
            if ind_dc not in ("D", "C"): ind_dc = "D"
            try:    valor_f = _str2float(vl_fin)
            except: valor_f = 0.0
            i155_por_periodo[periodo_atual_idx][cod_cta] = (valor_f, ind_dc)

        elif reg == "I355":
            cod_cta = _campo(campos, 1).strip()
            vl_cta  = _campo(campos, 3).strip()
            ind_dc  = _campo(campos, 4).strip().upper()
            if not cod_cta: continue
            if ind_dc not in ("D", "C"): ind_dc = "D"
            try:    valor_f = _str2float(vl_cta)
            except: valor_f = 0.0
            saldos_i355[cod_cta] = (valor_f, ind_dc)

    saldos_i155_raw = {}
    if i155_por_periodo:
        ultimo_idx      = max(i155_por_periodo.keys())
        saldos_i155_raw = i155_por_periodo[ultimo_idx]

    total_rec     = sum(v for v, dc in saldos_i355.values() if dc == "C")
    total_des     = sum(v for v, dc in saldos_i355.values() if dc == "D")
    resultado_liq = round(abs(total_rec - total_des), 2)

    log_tmp  = []
    sugerida = _sugerir_conta_pl_v4(
        contas_pl_candidatas, saldos_i155_raw, resultado_liq, log_tmp
    )
    if sugerida:
        st.session_state["conta_pl_sugerida"]      = sugerida
        st.session_state["conta_pl_sugerida_nome"] = mapa_nome_cta.get(sugerida, "")


# ── 2. _pre_scan_posicional ───────────────────────────────────────────────────
def _pre_scan_posicional(conteudo: bytes) -> list:
    """
    Varre rapidamente o TXT posicional e retorna lista de filiais detectadas.
    """
    enc = _detectar_encoding_bytes(conteudo)
    try:    texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")

    filiais = set()
    for linha in texto.splitlines():
        s = linha.rstrip("\r\n")
        if len(s) >= 20 and s[:2] in ("01", "02", "03"):
            try:
                filial = s[2:6].strip()
                if filial and filial.isdigit():
                    filiais.add(filial)
            except Exception:
                pass
    return sorted(filiais)


# ── 3. _widget_de_para_filiais ────────────────────────────────────────────────
def _widget_de_para_filiais(ativo: bool, filiais: list) -> dict:
    """
    Renderiza o widget de DE/PARA de filiais.
    Retorna dict {cod_origem: cod_destino}.
    """
    if not ativo or not filiais:
        return {}

    st.markdown(
        "<div class='filial-box'>"
        "<b style='color:#6EC6FF;'>🏢 DE/PARA de Filiais</b><br>"
        "<small style='color:#8AAAC8;'>Mapeie os códigos de filial do arquivo "
        "para os códigos do sistema destino.</small>"
        "</div>",
        unsafe_allow_html=True,
    )

    mapa = {}
    cols = st.columns(min(len(filiais), 4))
    for i, filial in enumerate(filiais):
        with cols[i % len(cols)]:
            destino = st.text_input(
                f"Filial {filial} →",
                value=filial,
                key=f"depara_filial_{filial}",
                max_chars=10,
            )
            if destino and destino != filial:
                mapa[filial] = destino
    return mapa


# ── 4. detectar_cabecalho_excel ───────────────────────────────────────────────
def detectar_cabecalho_excel(conteudo: bytes, sheet: str) -> tuple:
    """
    Detecta automaticamente a linha do cabeçalho em um Excel.
    Retorna (linha_idx, confianca).
    """
    try:
        buf = io.BytesIO(conteudo)
        df_raw = pd.read_excel(
            buf, sheet_name=sheet, header=None,
            engine="openpyxl", nrows=20
        )
        palavras_chave = {
            "data", "date", "conta", "account", "valor", "value",
            "débito", "debito", "crédito", "credito", "histórico",
            "historico", "lote", "filial", "centro", "custo",
            "cód", "cod", "complemento", "desc",
        }
        melhor_linha = 0
        melhor_score = 0
        for i, row in df_raw.iterrows():
            score = sum(
                1 for cell in row
                if isinstance(cell, str) and
                any(p in cell.lower() for p in palavras_chave)
            )
            if score > melhor_score:
                melhor_score = score
                melhor_linha = i
        return melhor_linha, melhor_score
    except Exception:
        return 3, 0


# ── 5. ler_excel_lote ─────────────────────────────────────────────────────────
def ler_excel_lote(conteudo: bytes, sheet: str, linha_header: int) -> tuple:
    """
    Lê o Excel e normaliza as colunas para o padrão interno.
    Retorna (DataFrame, lista_colunas_encontradas).
    """
    buf = io.BytesIO(conteudo)
    df  = pd.read_excel(
        buf, sheet_name=sheet, header=linha_header,
        engine="openpyxl", dtype=str
    )
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)

    # Normalização de nomes de coluna
    mapa_cols = {}
    for col in df.columns:
        col_low = col.lower().strip()
        if any(p in col_low for p in ("data",)):
            mapa_cols[col] = "Data"
        elif any(p in col_low for p in ("déb", "deb", "conta deb")):
            mapa_cols[col] = "Cód. Conta Debito"
        elif any(p in col_low for p in ("créd", "cred", "conta cred")):
            mapa_cols[col] = "Cód. Conta Credito"
        elif any(p in col_low for p in ("valor",)):
            mapa_cols[col] = "Valor"
        elif any(p in col_low for p in ("histórico", "historico", "hist", "complemento")):
            mapa_cols[col] = "Complemento Histórico"
        elif any(p in col_low for p in ("lote", "inicia")):
            mapa_cols[col] = "Inicia Lote"
        elif any(p in col_low for p in ("filial", "matriz")):
            mapa_cols[col] = "Código Matriz/Filial"
        elif any(p in col_low for p in ("cc deb", "custo deb", "centro deb")):
            mapa_cols[col] = "Centro de Custo Débito"
        elif any(p in col_low for p in ("cc cred", "custo cred", "centro cred")):
            mapa_cols[col] = "Centro de Custo Crédito"
        elif any(p in col_low for p in ("cód. hist", "cod hist", "código hist")):
            mapa_cols[col] = "Cód. Histórico"

    df = df.rename(columns=mapa_cols)
    colunas_encontradas = [c for c in COLS_PADRAO if c in df.columns]
    for col in COLS_PADRAO:
        if col not in df.columns:
            df[col] = ""
    return df, colunas_encontradas


# ── 6. montar_lotes_excel ─────────────────────────────────────────────────────
def montar_lotes_excel(df: pd.DataFrame) -> tuple:
    """
    Agrupa as linhas do Excel em lotes contábeis.
    Retorna (DataFrame com coluna _num_lote, modo_detectado).
    """
    df = df.copy()
    df["_num_lote"] = 0
    modo = "inicia_lote"

    # Modo 1: coluna "Inicia Lote" explícita
    if "Inicia Lote" in df.columns:
        col_il = df["Inicia Lote"].fillna("").astype(str).str.strip().str.upper()
        marcadores = col_il.isin(["S", "SIM", "X", "1", "TRUE", "LOTE"])
        if marcadores.sum() > 0:
            num_lote = 0
            lotes    = []
            for _, row in df.iterrows():
                il = str(row.get("Inicia Lote", "")).strip().upper()
                if il in ("S", "SIM", "X", "1", "TRUE", "LOTE"):
                    num_lote += 1
                lotes.append(num_lote)
            df["_num_lote"] = lotes
            return df, "inicia_lote"

    # Modo 2: agrupamento por data + filial (cada linha = um lote simples)
    modo = "linha_a_linha"
    df["_num_lote"] = range(1, len(df) + 1)
    return df, modo


# ── 7. _ordenar_lotes_por_data_filial ────────────────────────────────────────
def _ordenar_lotes_por_data_filial(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ordena o DataFrame por Data e depois por Filial.
    """
    df = df.copy()
    if "Data" in df.columns:
        df["_data_ord"] = pd.to_datetime(
            df["Data"].fillna("").astype(str).str.strip(),
            dayfirst=True, errors="coerce"
        )
        filial_col = "Código Matriz/Filial" if "Código Matriz/Filial" in df.columns else None
        sort_cols  = ["_data_ord"]
        if filial_col:
            sort_cols.append(filial_col)
        sort_cols.append("_num_lote")
        df = df.sort_values(sort_cols, na_position="last").reset_index(drop=True)
        df = df.drop(columns=["_data_ord"])
    return df


# ── 8. _pre_scan_filiais_excel ────────────────────────────────────────────────
def _pre_scan_filiais_excel(df: pd.DataFrame) -> list:
    """
    Extrai a lista de filiais únicas de um DataFrame Excel.
    """
    col = "Código Matriz/Filial"
    if col not in df.columns:
        return []
    filiais = (
        df[col].dropna().astype(str).str.strip()
        .replace("", pd.NA).dropna().unique().tolist()
    )
    return sorted(set(f for f in filiais if f and f.lower() not in ("nan", "")))


# ── 9. processar_excel ────────────────────────────────────────────────────────
def processar_excel(df: pd.DataFrame, ni: str,
                    mapa_filiais: dict, gerar_6110: bool,
                    log: list) -> tuple:
    """
    Converte um DataFrame Excel no leiaute 6000/6100.
    Retorna (bytes, resumo_list, erros_list).
    """
    buf    = io.StringIO()
    resumo = []
    erros  = []

    buf.write(fmt_reg_0000(ni) + "\n")

    lotes_ids = sorted(df["_num_lote"].unique())
    for num_lote in lotes_ids:
        grupo = df[df["_num_lote"] == num_lote].copy()
        if grupo.empty: continue

        linhas_lote = []
        erros_lote  = []

        # Filtra linhas válidas
        for _, row in grupo.iterrows():
            data  = str(row.get("Data", "")).strip()
            deb   = str(row.get("Cód. Conta Debito", "")).strip()
            cred  = str(row.get("Cód. Conta Credito", "")).strip()
            valor = str(row.get("Valor", "")).strip()
            hist  = _norm_hist(str(row.get("Complemento Histórico", "")))
            filial = str(row.get("Código Matriz/Filial", "")).strip()
            cc_deb  = str(row.get("Centro de Custo Débito", "")).strip()
            cc_cred = str(row.get("Centro de Custo Crédito", "")).strip()

            # Aplica DE/PARA de filiais
            if mapa_filiais and filial in mapa_filiais:
                filial = mapa_filiais[filial]

            # Valida
            if not data or not valor:
                erros_lote.append(f"Lote {num_lote}: data/valor vazio")
                continue

            try:
                val_f = _str2float(valor)
            except Exception:
                erros_lote.append(f"Lote {num_lote}: valor inválido '{valor}'")
                continue

            if abs(val_f) < 1e-6: continue

            data_fmt = ""
            try:
                data_fmt = pd.to_datetime(data, dayfirst=True).strftime("%d/%m/%Y")
            except Exception:
                data_fmt = data

            # Limpa contas
            deb_arr  = limpar_contas_vec(pd.Series([deb]))
            cred_arr = limpar_contas_vec(pd.Series([cred]))
            deb_c    = deb_arr[0]
            cred_c   = cred_arr[0]

            linhas_lote.append({
                "data": data_fmt, "deb": deb_c, "cred": cred_c,
                "valor": val_f, "hist": hist, "filial": filial,
                "cc_deb": cc_deb, "cc_cred": cc_cred,
            })

        if not linhas_lote:
            if erros_lote:
                erros.extend(erros_lote)
            continue

        # Determina tipo do lote
        n_deb  = sum(1 for l in linhas_lote if l["deb"])
        n_cred = sum(1 for l in linhas_lote if l["cred"])
        if   n_deb == 1 and n_cred == 1: tp = "X"
        elif n_deb == 1 and n_cred > 1:  tp = "D"
        elif n_deb > 1  and n_cred == 1: tp = "C"
        else:                             tp = "V"

        buf.write(fmt_reg_6000(tp) + "\n")

        for l in linhas_lote:
            linha_6100 = fmt_reg_6100(
                l["data"], l["deb"], l["cred"], l["valor"], "", l["hist"]
            )
            buf.write(linha_6100 + "\n")

            if gerar_6110:
                if l["deb"] and l["cred"]: modo_6110 = "ambos"
                elif l["deb"]:             modo_6110 = "deb"
                else:                      modo_6110 = "cred"
                val_fmt = _fmt_valor_layout(l["valor"])
                for l6110 in _gerar_6110_linha(l["deb"], l["cred"], val_fmt, modo_6110):
                    buf.write(l6110 + "\n")

        resumo.append({
            "lote":    num_lote,
            "linhas":  len(linhas_lote),
            "tipo":    tp,
            "data":    linhas_lote[0]["data"] if linhas_lote else "",
            "filial":  linhas_lote[0]["filial"] if linhas_lote else "",
        })
        if erros_lote:
            erros.extend(erros_lote)

    resultado = buf.getvalue().encode("utf-8-sig")
    del buf
    return resultado, resumo, erros


# ── 10. processar_streaming ───────────────────────────────────────────────────
def processar_streaming(conteudo: bytes, ni: str,
                         log: list) -> tuple:
    """
    Processa TXT separado por ';' em modo streaming (linha a linha).
    Retorna (bytes, resumo, erros, total_linhas, ignoradas, encoding).
    """
    enc = _detectar_encoding_bytes(conteudo)
    try:    texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")

    buf      = io.StringIO()
    resumo   = []
    erros    = []
    ignoradas = 0
    total_linhas = 0

    buf.write(fmt_reg_0000(ni) + "\n")

    lote_atual   = []
    num_lote     = 0
    dentro_lote  = False

    def _flush_lote(lote, num):
        if not lote: return
        n_deb  = sum(1 for l in lote if l.get("deb"))
        n_cred = sum(1 for l in lote if l.get("cred"))
        if   n_deb == 1 and n_cred == 1: tp = "X"
        elif n_deb == 1 and n_cred > 1:  tp = "D"
        elif n_deb > 1  and n_cred == 1: tp = "C"
        else:                             tp = "V"
        buf.write(fmt_reg_6000(tp) + "\n")
        for l in lote:
            buf.write(fmt_reg_6100(
                l["data"], l.get("deb",""), l.get("cred",""),
                l["valor"], "", l.get("hist","")
            ) + "\n")
        resumo.append({"lote": num, "linhas": len(lote), "tipo": tp})

    for linha in texto.splitlines():
        total_linhas += 1
        linha = linha.strip()
        if not linha or linha.startswith("#"): continue

        partes = [p.strip() for p in linha.split(";")]
        if len(partes) < 4:
            ignoradas += 1
            continue

        data  = partes[0]
        deb   = partes[1]
        cred  = partes[2]
        valor = partes[3]
        hist  = partes[4] if len(partes) > 4 else ""
        inicia = partes[6].upper() if len(partes) > 6 else ""

        try:    val_f = _str2float(valor)
        except: val_f = 0.0

        if abs(val_f) < 1e-6:
            ignoradas += 1
            continue

        try:
            data_fmt = pd.to_datetime(data, dayfirst=True).strftime("%d/%m/%Y")
        except Exception:
            data_fmt = data

        deb_arr  = limpar_contas_vec(pd.Series([deb]))
        cred_arr = limpar_contas_vec(pd.Series([cred]))

        registro = {
            "data":  data_fmt,
            "deb":   deb_arr[0],
            "cred":  cred_arr[0],
            "valor": val_f,
            "hist":  _norm_hist(hist),
        }

        if inicia in ("S", "SIM", "X", "1", "LOTE") or not dentro_lote:
            if lote_atual:
                _flush_lote(lote_atual, num_lote)
            num_lote    += 1
            lote_atual   = [registro]
            dentro_lote  = True
        else:
            lote_atual.append(registro)

    if lote_atual:
        _flush_lote(lote_atual, num_lote)

    resultado = buf.getvalue().encode("utf-8-sig")
    del buf
    log.append(f"  Encoding           : {enc}")
    log.append(f"  Total linhas       : {total_linhas:,}")
    log.append(f"  Ignoradas          : {ignoradas:,}")
    log.append(f"  Lotes gerados      : {len(resumo):,}")
    return resultado, resumo, erros, total_linhas, ignoradas, enc


# ── 11. processar_dominio_posicional ─────────────────────────────────────────
def processar_dominio_posicional(conteudo: bytes, ni: str,
                                  gerar_6110: bool,
                                  usar_de_para: bool,
                                  mapa_filiais: dict,
                                  log: list,
                                  prog_bar, status) -> tuple:
    """
    Converte TXT posicional Domínio para leiaute 6000/6100.
    Retorna (bytes, metricas, erros, filiais_encontradas).
    """
    enc = _detectar_encoding_bytes(conteudo)
    try:    texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")

    linhas_txt   = texto.splitlines()
    buf          = io.StringIO()
    erros        = []
    resumo       = []
    filiais_enc  = set()
    num_lote     = 0
    lote_atual   = []
    total_linhas = len(linhas_txt)

    buf.write(fmt_reg_0000(ni) + "\n")

    def _flush(lote, num):
        if not lote: return
        n_deb  = sum(1 for l in lote if l.get("deb"))
        n_cred = sum(1 for l in lote if l.get("cred"))
        if   n_deb == 1 and n_cred == 1: tp = "X"
        elif n_deb == 1 and n_cred > 1:  tp = "D"
        elif n_deb > 1  and n_cred == 1: tp = "C"
        else:                             tp = "V"
        buf.write(fmt_reg_6000(tp) + "\n")
        for l in lote:
            buf.write(fmt_reg_6100(
                l["data"], l.get("deb",""), l.get("cred",""),
                l["valor"], "", l.get("hist","")
            ) + "\n")
            if gerar_6110:
                vf = _fmt_valor_layout(l["valor"])
                if l.get("deb") and l.get("cred"): modo = "ambos"
                elif l.get("deb"):                  modo = "deb"
                else:                               modo = "cred"
                for l6110 in _gerar_6110_linha(l.get("deb",""), l.get("cred",""), vf, modo):
                    buf.write(l6110 + "\n")
        resumo.append({"lote": num, "linhas": len(lote), "tipo": tp})

    for idx, linha in enumerate(linhas_txt):
        if idx % 5000 == 0:
            pct = min(10 + int((idx / max(total_linhas, 1)) * 80), 90)
            prog_bar.progress(pct)
            status.text(f"Processando linha {idx:,}/{total_linhas:,}...")

        s = linha.rstrip("\r\n")
        if not s: continue
        tp_reg = s[:2] if len(s) >= 2 else ""

        if tp_reg == "01":
            # Cabeçalho de lote
            if lote_atual:
                _flush(lote_atual, num_lote)
                lote_atual = []
            num_lote += 1

        elif tp_reg == "02":
            # Partida
            if len(s) < 54: continue
            try:
                filial = s[2:6].strip()
                filiais_enc.add(filial)
                if usar_de_para and mapa_filiais and filial in mapa_filiais:
                    filial = mapa_filiais[filial]

                data_raw = s[6:14].strip()
                try:
                    data_fmt = datetime.strptime(data_raw, "%d%m%Y").strftime("%d/%m/%Y")
                except Exception:
                    data_fmt = data_raw

                deb_raw  = s[14:28].strip()
                cred_raw = s[28:42].strip()
                val_raw  = s[42:54].strip()

                deb_arr  = limpar_contas_vec(pd.Series([deb_raw]))
                cred_arr = limpar_contas_vec(pd.Series([cred_raw]))

                try:    val_f = _str2float(val_raw) / 100
                except: val_f = 0.0

                hist = _norm_hist(s[54:].strip() if len(s) > 54 else "")

                lote_atual.append({
                    "data":   data_fmt,
                    "deb":    deb_arr[0],
                    "cred":   cred_arr[0],
                    "valor":  val_f,
                    "hist":   hist,
                    "filial": filial,
                })
            except Exception as ex:
                erros.append({
                    "linha": idx + 1, "motivo": str(ex), "conteudo": s
                })

    if lote_atual:
        _flush(lote_atual, num_lote)

    resultado = buf.getvalue().encode("utf-8-sig")
    del buf

    n6000 = resultado.count(b"|6000|")
    n6100 = resultado.count(b"|6100|")
    n6110 = resultado.count(b"|6110|")
    metricas = {
        "Lotes gerados":  f"{len(resumo):,}",
        "Reg. 6000":      f"{n6000:,}",
        "Reg. 6100":      f"{n6100:,}",
        "Reg. 6110":      f"{n6110:,}" if gerar_6110 else "—",
        "Filiais":        f"{len(filiais_enc):,}",
        "Tamanho saída":  f"{len(resultado)/1024:.1f} KB",
    }
    log.append(f"  Encoding           : {enc}")
    log.append(f"  Lotes gerados      : {len(resumo):,}")
    log.append(f"  Filiais detectadas : {sorted(filiais_enc)}")
    if erros: log.append(f"  Erros              : {len(erros):,}")

    prog_bar.progress(95)
    return resultado, metricas, erros, sorted(filiais_enc)


# ── 12. processar_saldo_inicial_ecd (legado V3.6.2) ──────────────────────────
def processar_saldo_inicial_ecd(conteudo: bytes, ni: str,
                                 hist_prefixo: str,
                                 modo_resultado: str,
                                 conta_pl: str,
                                 log: list,
                                 prog_bar, status) -> tuple:
    """
    Wrapper legado — chama o parse unificado e depois _gerar_saldo_inicial_v4.
    Retorna (bytes, metricas_dict, erros_list).
    """
    status.text("Lendo SPED ECD...")
    prog_bar.progress(10)
    log.append("── PARSE ECD (saldo inicial legado) ──")

    ecd, saldos_dict, erros_parse = _parse_ecd_completo(conteudo, log)
    if ecd is None:
        return b"", {}, erros_parse

    prog_bar.progress(40)
    status.text("Gerando saldo inicial...")
    log.append("── GERAÇÃO SALDO INICIAL ──")

    sd_si = dict(saldos_dict)
    sd_si["data_ref"] = _normalizar_data_ecd(ecd.dt_ini)

    bytes_si, resumo, erros_si = _gerar_saldo_inicial_v4(
        sd_si, ni, hist_prefixo, modo_resultado, conta_pl, log
    )
    prog_bar.progress(90)
    status.text("Concluído!")

    metricas = {
        "Data referência":   resumo.get("data", ""),
        "Contas I155":       f"{resumo.get('contas_i155', 0):,}",
        "Contas I355":       f"{resumo.get('contas_i355', 0):,}",
        "Reg. 6100 gerados": f"{resumo.get('n6100', 0):,}",
        "Total Débito":      format_moeda(resumo.get("total_debito", 0)),
        "Total Crédito":     format_moeda(resumo.get("total_credito", 0)),
        "Diferença":         format_moeda(resumo.get("diferenca", 0)),
        "Balanceado":        "✅ SIM" if resumo.get("balanceado") else "⚠ NÃO",
        "Modo":              resumo.get("modo", ""),
        "Tamanho saída":     f"{len(bytes_si)/1024:.1f} KB",
    }
    todos_erros = erros_parse + erros_si
    prog_bar.progress(100)
    return bytes_si, metricas, todos_erros


# ── 13. _montar_log_lote ──────────────────────────────────────────────────────
def _montar_log_lote(resumo: list, erros: list, ni: str,
                      ti: str, inf: str, n_gravados: int,
                      ignoradas: int, enc_usado: str,
                      crono: Cronometro) -> str:
    linhas = [
        "=" * 60,
        f"LOG DE CONVERSÃO — {ts_log()}",
        f"CNPJ/CPF : {inf} ({ti})",
        f"NI       : {ni}",
        f"Encoding : {enc_usado}",
        "=" * 60,
        f"Lotes processados : {len(resumo):,}",
        f"Lotes com erro    : {len(erros):,}",
        f"Reg. 6000 gerados : {n_gravados:,}",
        f"Linhas ignoradas  : {ignoradas:,}",
        "",
    ]
    if erros:
        linhas.append("── ERROS ──")
        for e in erros[:50]:
            linhas.append(f"  {e}")
        if len(erros) > 50:
            linhas.append(f"  ... e mais {len(erros)-50} erros")
        linhas.append("")

    linhas.append("── TEMPOS ──")
    for e in crono.etapas:
        linhas.append(f"  {e['nome']:<28} {Cronometro.fmt(e['segundos'])}")
    linhas += ["=" * 60, "FIM DO LOG"]
    return "\n".join(linhas)


# ── 14. _render_resultados_lote ───────────────────────────────────────────────
def _render_resultados_lote(exibir_log: bool):
    st.markdown("---")
    st.markdown("## 📦 Resultado — Lançamentos")

    resultado_bytes = st.session_state.get("resultado_bytes")
    metricas        = st.session_state.get("metricas", {})
    resumo          = st.session_state.get("resumo", [])
    erros_lote      = st.session_state.get("erros_lote", [])
    log_linhas      = st.session_state.get("log_linhas", [])

    if not resultado_bytes:
        st.warning("Nenhum resultado disponível.")
        return

    # Métricas
    if metricas:
        cols = st.columns(min(len(metricas), 4))
        for i, (k, v) in enumerate(metricas.items()):
            cols[i % len(cols)].metric(k, v)

    # Alertas
    if erros_lote:
        st.warning(f"⚠ {len(erros_lote)} lote(s) com problemas.")

    # Download principal
    st.download_button(
        "⬇ Baixar arquivo de lançamentos",
        data=resultado_bytes,
        file_name=st.session_state.get("resultado_nome", "lancamentos.txt"),
        mime="text/plain",
        use_container_width=True,
        key="dl_resultado_lote",
    )

    # Download log
    if st.session_state.get("log_bytes"):
        st.download_button(
            "⬇ Baixar log de conversão",
            data=st.session_state.log_bytes,
            file_name=st.session_state.get("log_nome", "log.txt"),
            mime="text/plain",
            use_container_width=True,
            key="dl_log_lote",
        )

    # Log na tela
    if exibir_log and log_linhas:
        st.markdown("### 🖥 Log")
        log_txt = "\n".join(str(l) for l in log_linhas)
        st.markdown(
            f"<div class='bloco-log'>{log_txt}</div>",
            unsafe_allow_html=True,
        )


# ── 15. _render_resultados_saldo_inicial ─────────────────────────────────────
def _render_resultados_saldo_inicial(exibir_log: bool):
    st.markdown("---")
    st.markdown("## 📦 Resultado — Saldo Inicial")

    resultado_bytes = st.session_state.get("resultado_bytes")
    metricas        = st.session_state.get("metricas", {})
    log_linhas      = st.session_state.get("log_linhas", [])

    if not resultado_bytes:
        st.warning("Nenhum resultado disponível.")
        return

    if metricas:
        bal = metricas.get("Balanceado", "")
        if "NÃO" in str(bal):
            st.error(f"⚠ Lançamento desbalanceado! Diferença: {metricas.get('Diferença','')}")
        else:
            st.success("✅ Lançamento balanceado (D = C)")

        cols = st.columns(min(len(metricas), 4))
        for i, (k, v) in enumerate(metricas.items()):
            cols[i % len(cols)].metric(k, str(v))

    st.download_button(
        "⬇ Baixar Saldo Inicial",
        data=resultado_bytes,
        file_name=st.session_state.get("resultado_nome", "saldo_inicial.txt"),
        mime="text/plain",
        use_container_width=True,
        key="dl_resultado_si",
    )

    if st.session_state.get("erros_bytes"):
        st.download_button(
            "⬇ Baixar relatório de erros",
            data=st.session_state.erros_bytes,
            file_name=st.session_state.get("erros_nome", "erros.txt"),
            mime="text/plain",
            use_container_width=True,
            key="dl_erros_si",
        )

    if exibir_log and log_linhas:
        st.markdown("### 🖥 Log")
        log_txt = "\n".join(str(l) for l in log_linhas)
        st.markdown(
            f"<div class='bloco-log'>{log_txt}</div>",
            unsafe_allow_html=True,
        )


# ── 16. _render_resultados_posicional ────────────────────────────────────────
def _render_resultados_posicional(exibir_log: bool):
    st.markdown("---")
    st.markdown("## 📦 Resultado — TXT Posicional Domínio")

    resultado_bytes = st.session_state.get("resultado_bytes")
    metricas        = st.session_state.get("metricas", {})
    log_linhas      = st.session_state.get("log_linhas", [])

    if not resultado_bytes:
        st.warning("Nenhum resultado disponível.")
        return

    if metricas:
        cols = st.columns(min(len(metricas), 4))
        for i, (k, v) in enumerate(metricas.items()):
            cols[i % len(cols)].metric(k, str(v))

    st.download_button(
        "⬇ Baixar arquivo convertido",
        data=resultado_bytes,
        file_name=st.session_state.get("resultado_nome", "posicional_convertido.txt"),
        mime="text/plain",
        use_container_width=True,
        key="dl_resultado_pos",
    )

    if st.session_state.get("erros_bytes"):
        st.download_button(
            "⬇ Baixar relatório de erros",
            data=st.session_state.erros_bytes,
            file_name=st.session_state.get("erros_nome", "erros.txt"),
            mime="text/plain",
            use_container_width=True,
            key="dl_erros_pos",
        )

    if exibir_log and log_linhas:
        st.markdown("### 🖥 Log")
        log_txt = "\n".join(str(l) for l in log_linhas)
        st.markdown(
            f"<div class='bloco-log'>{log_txt}</div>",
            unsafe_allow_html=True,
        )


# ── 17. _parse_i052_completo ──────────────────────────────────────────────────
def _parse_i052_completo(conteudo: bytes, log: list) -> dict:
    """
    Extrai registros I052 + saldos I155 de um SPED ECD.
    Retorna dict com cnpj, nome, periodo, mapa_i052, saldos_ini, saldos_fin.
    """
    enc = _detectar_encoding_bytes(conteudo)
    try:    texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")

    cnpj = nome = dt_ini = dt_fin = ""
    mapa_i052   = {}   # cod_cta → cod_agl
    saldos_ini  = {}   # cod_cta → (val_float, dc)
    saldos_fin  = {}   # cod_cta → (val_float, dc)
    i155_periodos = {}
    periodo_idx   = -1
    rtl_i150      = 0

    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha: continue
        campos = _split_pipe(linha)
        if not campos: continue
        reg = campos[0]

        if reg == "0000":
            if len(campos) > 5: cnpj   = re.sub(r"\D", "", campos[5].strip())
            if len(campos) > 6: nome   = campos[6].strip()
            if len(campos) > 3: dt_ini = campos[3].strip()
            if len(campos) > 4: dt_fin = campos[4].strip()

        elif reg == "I052":
            cod_cta = _campo(campos, 1).strip()
            cod_agl = _campo(campos, 2).strip()
            if cod_cta and cod_agl:
                mapa_i052[cod_cta] = cod_agl

        elif reg == "I150":
            rtl_i150 += 1
            periodo_idx += 1
            i155_periodos[periodo_idx] = {}

        elif reg == "I155":
            if periodo_idx < 0: continue
            cod_cta = _campo(campos, 1).strip()
            val_ini = _campo(campos, 4).strip()
            dc_ini  = _campo(campos, 5).strip().upper()
            val_fin = _campo(campos, 7).strip()
            dc_fin  = _campo(campos, 8).strip().upper()
            if not cod_cta: continue
            if dc_ini not in ("D","C"): dc_ini = "D"
            if dc_fin not in ("D","C"): dc_fin = "D"
            try:    vi = _str2float(val_ini)
            except: vi = 0.0
            try:    vf = _str2float(val_fin)
            except: vf = 0.0
            if cod_cta not in saldos_ini and rtl_i150 <= 1:
                saldos_ini[cod_cta] = (vi, dc_ini)
            saldos_fin[cod_cta] = (vf, dc_fin)

    log.append(f"  CNPJ               : {cnpj}")
    log.append(f"  Nome               : {nome}")
    log.append(f"  Período            : {_normalizar_data_ecd(dt_ini)} a {_normalizar_data_ecd(dt_fin)}")
    log.append(f"  Registros I052     : {len(mapa_i052):,}")
    log.append(f"  Saldos I155        : {len(saldos_fin):,}")

    return {
        "cnpj": cnpj, "nome": nome,
        "dt_ini": dt_ini, "dt_fin": dt_fin,
        "mapa_i052": mapa_i052,
        "saldos_ini": saldos_ini,
        "saldos_fin": saldos_fin,
    }


# ── 18. _comparar_i052 ────────────────────────────────────────────────────────
def _comparar_i052(ant: dict, atu: dict) -> dict:
    """
    Compara os I052 de dois ECDs.
    Retorna dict com listas: iguais, divergentes, novos, removidos, mudou_grupo.
    """
    mapa_ant = ant.get("mapa_i052", {})
    mapa_atu = atu.get("mapa_i052", {})
    sal_fin_ant = ant.get("saldos_fin", {})
    sal_ini_atu = atu.get("saldos_ini", {})

    todas_contas = set(mapa_ant) | set(mapa_atu)
    iguais = []; divergentes = []; novos = []; removidos = []; mudou_grupo = []

    for cta in sorted(todas_contas):
        em_ant = cta in mapa_ant
        em_atu = cta in mapa_atu
        agl_ant = mapa_ant.get(cta, "")
        agl_atu = mapa_atu.get(cta, "")
        sf_ant  = sal_fin_ant.get(cta, (0.0, "D"))
        si_atu  = sal_ini_atu.get(cta, (0.0, "D"))

        if em_ant and em_atu:
            if agl_ant == agl_atu:
                diff = round(abs(sf_ant[0] - si_atu[0]), 2)
                iguais.append({
                    "conta": cta, "agl": agl_atu,
                    "sf_ant": sf_ant, "si_atu": si_atu, "diff": diff,
                })
            else:
                mudou_grupo.append({
                    "conta": cta,
                    "agl_ant": agl_ant, "agl_atu": agl_atu,
                    "sf_ant": sf_ant, "si_atu": si_atu,
                })
        elif em_ant and not em_atu:
            removidos.append({"conta": cta, "agl": agl_ant, "sf_ant": sf_ant})
        elif not em_ant and em_atu:
            novos.append({"conta": cta, "agl": agl_atu, "si_atu": si_atu})

    divergentes = [i for i in iguais if i["diff"] > 0.01]
    iguais      = [i for i in iguais if i["diff"] <= 0.01]

    return {
        "iguais":      iguais,
        "divergentes": divergentes,
        "novos":       novos,
        "removidos":   removidos,
        "mudou_grupo": mudou_grupo,
    }


# ── 19. _render_comparacao_i052 ───────────────────────────────────────────────
def _render_comparacao_i052(resultado: dict,
                              label_ant: str, label_atu: str,
                              parsed_ant: dict, parsed_atu: dict):
    """Renderiza o resultado da comparação I052."""
    st.markdown("---")
    st.markdown("### 📊 Resultado da Comparação")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("✅ Iguais",       len(resultado["iguais"]))
    col2.metric("⚠ Divergentes",  len(resultado["divergentes"]), delta_color="inverse")
    col3.metric("🆕 Novos",        len(resultado["novos"]))
    col4.metric("🗑 Removidos",    len(resultado["removidos"]), delta_color="inverse")
    col5.metric("🔀 Mudou Grupo",  len(resultado["mudou_grupo"]), delta_color="inverse")

    if resultado["divergentes"]:
        st.markdown("#### ⚠ Contas com Saldo Divergente (Fin. Anterior ≠ Ini. Atual)")
        rows = []
        for r in resultado["divergentes"]:
            sf_v, sf_dc = r["sf_ant"]
            si_v, si_dc = r["si_atu"]
            rows.append({
                "Conta":       r["conta"],
                "COD_AGL":     r["agl"],
                "SF Anterior": f"{format_moeda(sf_v)} {sf_dc}",
                "SI Atual":    f"{format_moeda(si_v)} {si_dc}",
                "Diferença":   format_moeda(r["diff"]),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    if resultado["mudou_grupo"]:
        st.markdown("#### 🔀 Contas que Mudaram de Grupo (COD_AGL)")
        rows = []
        for r in resultado["mudou_grupo"]:
            rows.append({
                "Conta":     r["conta"],
                "AGL Ant.":  r["agl_ant"],
                "AGL Atu.":  r["agl_atu"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    if resultado["novos"]:
        st.markdown("#### 🆕 Contas Novas (só no atual)")
        rows = [{"Conta": r["conta"], "COD_AGL": r["agl"]} for r in resultado["novos"]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    if resultado["removidos"]:
        st.markdown("#### 🗑 Contas Removidas (só no anterior)")
        rows = [{"Conta": r["conta"], "COD_AGL": r["agl"]} for r in resultado["removidos"]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # Download CSV completo
    todas = []
    for r in resultado["iguais"]:
        todas.append({"Situação":"OK","Conta":r["conta"],"AGL":r["agl"],"Diff":0})
    for r in resultado["divergentes"]:
        todas.append({"Situação":"DIVERGENTE","Conta":r["conta"],"AGL":r["agl"],"Diff":r["diff"]})
    for r in resultado["mudou_grupo"]:
        todas.append({"Situação":"MUDOU_GRUPO","Conta":r["conta"],"AGL_ANT":r["agl_ant"],"AGL_ATU":r["agl_atu"],"Diff":0})
    for r in resultado["novos"]:
        todas.append({"Situação":"NOVO","Conta":r["conta"],"AGL":r["agl"],"Diff":0})
    for r in resultado["removidos"]:
        todas.append({"Situação":"REMOVIDO","Conta":r["conta"],"AGL":r["agl"],"Diff":0})

    if todas:
        csv = pd.DataFrame(todas).to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button(
            "⬇ Baixar comparação completa (.csv)",
            data=csv.encode("utf-8-sig"),
            file_name="comparacao_i052.csv",
            mime="text/csv",
            use_container_width=True,
            key="dl_i052_csv",
        )

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 5 — MAIN() UNIFICADO V4.0
# Integra: ECD V4.0 (multi-saída) + Lote TXT + Excel + Posicional +
#          Saldo Inicial legado + Comparação I052
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="Domínio Sistemas | Thomson Reuters",
        page_icon="🟠",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_theme()
    _init_state()

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    st.markdown(
        f"<div class='header-box'>"
        f"<h2 style='color:#FF6B00;margin:0;'>Domínio Sistemas — Conversor Unificado</h2>"
        f"<p style='color:#6B7A8D;margin:6px 0 0;'>"
        f"Lançamentos Contábeis (TXT/Excel/Posicional) &nbsp;|&nbsp; "
        f"SPED ECD → 0000 + 6000 + 6100 &nbsp;|&nbsp; "
        f"Saldo Inicial &nbsp;|&nbsp; DE/PARA de Contas &nbsp;|&nbsp; "
        f"Comparação I052 &nbsp;|&nbsp; "
        f"<b style='color:#FF6B00;'>Thomson Reuters</b> &nbsp;|&nbsp; "
        f"<small>{VERSAO}</small></p></div>",
        unsafe_allow_html=True,
    )

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙ Configurações")
        st.markdown("---")
        exibir_log = st.checkbox("Exibir log de processamento", value=True)
        st.markdown("---")
        st.markdown(f"**Versão:** {VERSAO}")
        st.markdown("**Thomson Reuters — Domínio Sistemas**")
        st.markdown("---")
        st.markdown("**Formatos suportados:**")
        st.markdown(
            "- 📊 Excel (.xlsx / .xls)\n"
            "- 📄 TXT separado por `;`\n"
            "- 📋 SPED ECD — lançamentos + saldo\n"
            "- 📋 TXT Posicional Domínio\n"
            "- 🔀 DE/PARA de Contas (fuzzy)\n"
            "- 🔍 Comparação I052"
        )
        st.markdown("---")
        st.code(
            "|0000|CNPJ|\n"
            "|6000|TIPO||||\n"
            "|6100|DATA|DEB|CRED|VALOR||HIST||FILIAL||\n"
            "|6110|CC_DEB|CC_CRED|VALOR|",
            language=None,
        )
        st.markdown(f"**Limite:** {MAX_UPLOAD_MB} MB")

    # ── Abas principais ───────────────────────────────────────────────────────
    aba_conv, aba_i052 = st.tabs([
        "🔄 Conversor / SPED ECD",
        "🔍 Comparar I052 entre ECDs",
    ])

    # ═════════════════════════════════════════════════════════════════════════
    # ABA 2 — COMPARAÇÃO I052
    # ═════════════════════════════════════════════════════════════════════════
    with aba_i052:
        st.markdown("### 🔍 Comparação de I052 — ECD Anterior vs. ECD Atual")
        st.markdown(
            "<div class='info-box'>"
            "Suba os dois arquivos SPED ECD. O sistema irá:<br>"
            "① Extrair os <b>I052</b> (vínculos conta → COD_AGL) de cada arquivo<br>"
            "② Comparar o <b>saldo final</b> de cada COD_AGL no anterior com o "
            "<b>saldo inicial</b> no atual<br>"
            "③ Apontar contas que <b>mudaram de grupo</b> entre os dois arquivos"
            "</div>",
            unsafe_allow_html=True,
        )
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            st.markdown("**📁 Arquivo ECD — ANTERIOR (ano N-1)**")
            upload_ant = st.file_uploader(
                "ECD anterior", type=["txt"], key="upload_i052_ant",
                help="Arquivo SPED ECD do período anterior (ex: 2023)",
            )
        with col_u2:
            st.markdown("**📁 Arquivo ECD — ATUAL (ano N)**")
            upload_atu = st.file_uploader(
                "ECD atual", type=["txt"], key="upload_i052_atu",
                help="Arquivo SPED ECD do período atual (ex: 2024)",
            )

        btn_comparar = st.button(
            "🔍 COMPARAR I052",
            disabled=(upload_ant is None or upload_atu is None),
            type="primary", use_container_width=True, key="btn_comparar_i052",
        )

        if btn_comparar and upload_ant and upload_atu:
            log_cmp = []
            with st.spinner("Lendo arquivo anterior..."):
                log_cmp.append("── PARSE ARQUIVO ANTERIOR ──")
                parsed_ant = _parse_i052_completo(upload_ant.read(), log_cmp)
            with st.spinner("Lendo arquivo atual..."):
                log_cmp.append("\n── PARSE ARQUIVO ATUAL ──")
                parsed_atu = _parse_i052_completo(upload_atu.read(), log_cmp)
            with st.spinner("Comparando..."):
                resultado_cmp = _comparar_i052(parsed_ant, parsed_atu)

            st.session_state["i052_resultado"]  = resultado_cmp
            st.session_state["i052_parsed_ant"] = parsed_ant
            st.session_state["i052_parsed_atu"] = parsed_atu
            st.session_state["i052_label_ant"]  = upload_ant.name
            st.session_state["i052_label_atu"]  = upload_atu.name
            st.session_state["i052_log"]        = log_cmp
            st.rerun()

        if st.session_state.get("i052_resultado"):
            _render_comparacao_i052(
                st.session_state["i052_resultado"],
                st.session_state["i052_label_ant"],
                st.session_state["i052_label_atu"],
                st.session_state["i052_parsed_ant"],
                st.session_state["i052_parsed_atu"],
            )
            if exibir_log and st.session_state.get("i052_log"):
                st.markdown("#### 🖥 Log")
                log_txt = "\n".join(st.session_state["i052_log"])
                st.markdown(
                    f"<div class='bloco-log'>{log_txt}</div>",
                    unsafe_allow_html=True,
                )

    # ═════════════════════════════════════════════════════════════════════════
    # ABA 1 — CONVERSOR PRINCIPAL
    # ═════════════════════════════════════════════════════════════════════════
    with aba_conv:

        # ── PASSO 1 — Upload ──────────────────────────────────────────────────
        st.markdown("### 📂 Passo 1 — Selecionar Arquivo")
        uploaded = st.file_uploader(
            f"Arraste ou clique (Excel, TXT separado por ';', "
            f"SPED ECD ou TXT Posicional — máx. {MAX_UPLOAD_MB} MB)",
            type=["xlsx", "xls", "xlsm", "txt", "csv"],
            key="upload_principal",
        )

        if uploaded is None:
            st.markdown(
                "<div class='info-box'>⬆ Selecione um arquivo para começar.</div>",
                unsafe_allow_html=True,
            )
            return

        # ── Leitura e detecção ────────────────────────────────────────────────
        conteudo = uploaded.read()
        mb = len(conteudo) / (1024 * 1024)
        if mb > MAX_UPLOAD_MB:
            st.error(f"⛔ Arquivo muito grande ({mb:.1f} MB). Limite: {MAX_UPLOAD_MB} MB.")
            return

        arquivo_mudou = (
            conteudo != st.session_state.arquivo_bytes
            or uploaded.name != st.session_state.arquivo_nome
        )
        if arquivo_mudou:
            _reset()
            st.session_state.arquivo_bytes = conteudo
            st.session_state.arquivo_nome  = uploaded.name
            tipo = identificar_tipo(uploaded.name, conteudo)
            st.session_state.tipo_detectado = tipo

            if tipo == "excel":
                try:
                    xl = pd.ExcelFile(io.BytesIO(conteudo), engine="openpyxl")
                    st.session_state.sheets    = xl.sheet_names
                    st.session_state.sheet_sel = (
                        "Plan1" if "Plan1" in xl.sheet_names else xl.sheet_names[0]
                    )
                except Exception:
                    st.session_state.sheets = []

            elif tipo == "ecd":
                cnpj_num = _pre_scan_cnpj_ecd(conteudo)
                st.session_state.cnpj_ecd     = cnpj_num
                st.session_state.cnpj_ecd_fmt = fmt_cnpj(cnpj_num) if cnpj_num else ""
                # Pré-scan da conta PL (legado — mantido para compatibilidade)
                _pre_scan_conta_pl_sugerida(conteudo)

            elif tipo == "dominio_pos":
                filiais = _pre_scan_posicional(conteudo)
                st.session_state.filiais_detectadas = filiais

        tipo = st.session_state.tipo_detectado

        # ── Badge do arquivo ──────────────────────────────────────────────────
        _BADGES = {
            "ecd":         "<span class='badge-ecd'>📋 SPED ECD</span>",
            "ecd_saldo":   "<span class='badge-si'>📥 SPED ECD — Saldo Inicial</span>",
            "excel":       "<span class='badge-excel'>📊 Excel</span>",
            "lote":        "<span class='badge-lote'>📄 TXT Lote (;)</span>",
            "dominio_pos": "<span class='badge-pos'>📋 TXT Posicional Domínio</span>",
        }
        st.markdown(
            f"{_BADGES.get(tipo, '')} "
            f"<span style='color:#6B7A8D;font-size:13px;margin-left:12px;'>"
            f"{st.session_state.arquivo_nome} — {mb:.1f} MB</span>",
            unsafe_allow_html=True,
        )
        st.markdown("")

        # ══════════════════════════════════════════════════════════════════════
        # FLUXO SPED ECD — V4.0 (multi-saída + DE/PARA)
        # ══════════════════════════════════════════════════════════════════════
        if tipo == "ecd":
            _render_passos_ecd(conteudo, exibir_log)
            return  # encerra aqui — _render_passos_ecd gerencia tudo

        # ══════════════════════════════════════════════════════════════════════
        # FLUXO LEGADO — Excel / TXT / Posicional / Saldo Inicial (V3.6.2)
        # ══════════════════════════════════════════════════════════════════════

        # ── Config Excel ──────────────────────────────────────────────────────
        sheet_sel = ""; linha_h = 3; auto_head = True
        if tipo == "excel" and st.session_state.sheets:
            st.markdown("---")
            st.markdown("#### 📋 Configurar Excel")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                sheet_sel = st.selectbox(
                    "Aba (Sheet)", st.session_state.sheets,
                    index=(
                        st.session_state.sheets.index(st.session_state.sheet_sel)
                        if st.session_state.sheet_sel in st.session_state.sheets else 0
                    ),
                )
                st.session_state.sheet_sel = sheet_sel
            with col2:
                auto_head = st.checkbox("Detectar cabeçalho automaticamente", value=True)
            with col3:
                if not auto_head:
                    linha_h = st.number_input(
                        "Linha do cabeçalho", min_value=1, max_value=50, value=4
                    ) - 1

        # ── CNPJ ─────────────────────────────────────────────────────────────
        ni = ""; ok_insc = False; ti = ""; inf = ""
        st.markdown("---")

        if tipo == "ecd_saldo":
            # ── Saldo Inicial (legado V3.6.2) ─────────────────────────────────
            st.markdown("#### 🏢 Passo 2 — CNPJ (auto-detectado)")
            cnpj_ecd = st.session_state.cnpj_ecd
            if cnpj_ecd and validar_cnpj(cnpj_ecd):
                st.markdown(
                    f"<div class='cnpj-auto'>✔ CNPJ extraído: "
                    f"<span>{st.session_state.cnpj_ecd_fmt}</span></div>",
                    unsafe_allow_html=True,
                )
                st.code(fmt_reg_0000(cnpj_ecd), language=None)
                ok_insc = True; ti = "CNPJ"; ni = cnpj_ecd
                inf = st.session_state.cnpj_ecd_fmt
            else:
                st.warning("⚠ CNPJ não encontrado. Informe manualmente.")
                cnpj_raw = st.text_input(
                    "CNPJ / CPF", placeholder="00.000.000/0001-00",
                    key="cnpj_manual_si",
                )
                ok_insc, ti, ni = validar_inscricao(cnpj_raw)
                if cnpj_raw:
                    if ok_insc:
                        inf = fmt_cnpj(ni) if ti == "CNPJ" else fmt_cpf(ni)
                        st.success(f"✔ {ti} válido: {inf}")
                    else:
                        st.error("✖ CNPJ/CPF inválido")

            # Bloco Saldo Inicial
            st.markdown("---")
            st.markdown(
                "<div class='si-box'>"
                "<b style='color:#FF9EBC;font-size:15px;'>📥 Módulo Saldo Inicial V3.6.2</b><br>"
                "<small style='color:#C8A0B8;'>Extrai o saldo do SPED ECD e gera um único "
                "lançamento de saldo inicial no leiaute Domínio.</small></div>",
                unsafe_allow_html=True,
            )

            col_si1, col_si2 = st.columns([1, 2])
            with col_si1:
                hist_prefixo = st.text_input(
                    "Prefixo do histórico",
                    value=st.session_state.get("hist_prefixo_si", "SALDO INICIAL"),
                    max_chars=60, key="hist_prefixo_si_widget",
                )
                st.session_state.hist_prefixo_si = hist_prefixo
            with col_si2:
                modo_resultado = st.radio(
                    "Tratamento das contas de Resultado (I355):",
                    options=["apenas_patrimonial", "aberto_com_resultado"],
                    format_func=lambda x: {
                        "apenas_patrimonial":   "✅ Apenas Patrimonial (balanço fechado)",
                        "aberto_com_resultado": "📂 Aberto com Resultado (inclui I355)",
                    }[x],
                    index=0 if st.session_state.get(
                        "modo_resultado_si", "apenas_patrimonial"
                    ) == "apenas_patrimonial" else 1,
                    key="modo_resultado_si_widget",
                )
                st.session_state.modo_resultado_si = modo_resultado

            conta_pl = ""
            if modo_resultado == "aberto_com_resultado":
                sugerida      = st.session_state.get("conta_pl_sugerida", "")
                sugerida_nome = st.session_state.get("conta_pl_sugerida_nome", "")
                if sugerida:
                    st.markdown(
                        f"<div class='si-box'>"
                        f"<b style='color:#FF9EBC;'>💡 Conta sugerida:</b> "
                        f"<span style='color:#FFD166;font-size:18px;font-weight:700;'>"
                        f"{sugerida}</span> — {sugerida_nome}</div>",
                        unsafe_allow_html=True,
                    )
                conta_pl = st.text_input(
                    "Código da conta de Superávit/Déficit (PL)",
                    value=sugerida or st.session_state.get("conta_pl_resultado_si", ""),
                    placeholder="Ex: 311010101",
                    key="conta_pl_resultado_si_widget",
                )
                st.session_state.conta_pl_resultado_si = conta_pl
                if not conta_pl:
                    st.warning("⚠ Informe a conta PL para que o balanço feche (D = C).")

        else:
            # ── CNPJ genérico (lote / Excel / posicional) ─────────────────────
            st.markdown("#### 🏢 Passo 2 — Informar CNPJ / CPF")
            cnpj_raw = st.text_input(
                "CNPJ / CPF",
                placeholder="00.000.000/0001-00 ou 000.000.000-00",
                key="cnpj_lote",
            )
            ok_insc, ti, ni = validar_inscricao(cnpj_raw)
            if cnpj_raw:
                if ok_insc:
                    inf = fmt_cnpj(ni) if ti == "CNPJ" else fmt_cpf(ni)
                    col_a, col_b = st.columns([1, 2])
                    with col_a: st.success(f"✔ {ti} válido")
                    with col_b: st.code(fmt_reg_0000(ni), language=None)
                else:
                    st.error("✖ CNPJ/CPF inválido")

        # ── Passo 3 — Opções ──────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### ⚙ Passo 3 — Opções e Conversão")
        col_op1, col_op2 = st.columns(2)
        with col_op1:
            gerar_6110 = st.checkbox(
                "Gerar registro 6110 (Centro de Custos)",
                value=False,
                disabled=(tipo not in ("dominio_pos", "excel", "lote")),
            )
        with col_op2:
            usar_de_para = st.checkbox(
                "🏢 Habilitar De/Para de filiais",
                value=False,
                disabled=(tipo not in ("dominio_pos", "excel")),
            )

        mapa_filiais = {}
        if tipo == "dominio_pos" and usar_de_para:
            mapa_filiais = _widget_de_para_filiais(
                True, st.session_state.get("filiais_detectadas", [])
            )
        elif tipo == "excel" and usar_de_para:
            filiais_excel = []
            if st.session_state.get("arquivo_bytes") and st.session_state.get("sheet_sel"):
                try:
                    sh_scan  = st.session_state.sheet_sel
                    lh_scan, _ = detectar_cabecalho_excel(
                        st.session_state.arquivo_bytes, sh_scan
                    )
                    df_scan, _ = ler_excel_lote(
                        st.session_state.arquivo_bytes, sh_scan, lh_scan
                    )
                    filiais_excel = _pre_scan_filiais_excel(df_scan)
                    del df_scan
                except Exception:
                    filiais_excel = []
            mapa_filiais = _widget_de_para_filiais(True, filiais_excel)

        # ── Botões ────────────────────────────────────────────────────────────
        st.markdown("---")
        col_b1, col_b2 = st.columns([3, 1])
        with col_b1:
            btn_converter = st.button(
                "▶ CONVERTER",
                disabled=not ok_insc,
                use_container_width=True,
                type="primary",
                key="btn_converter_legado",
            )
        with col_b2:
            btn_limpar = st.button(
                "🗑 Limpar tudo",
                use_container_width=True,
                key="btn_limpar_legado",
            )

        if btn_limpar:
            _reset()
            st.rerun()

        # ── Processamento ─────────────────────────────────────────────────────
        if btn_converter and ok_insc:
            log      = []
            crono    = Cronometro()
            crono.iniciar()
            status   = st.empty()
            prog_bar = st.progress(0)

            try:
                # ── SALDO INICIAL (legado V3.6.2) ─────────────────────────────
                if tipo == "ecd_saldo":
                    crono.etapa("Saldo Inicial ECD")
                    log.append("── SALDO INICIAL — SPED ECD V3.6.2 ──")
                    resultado_bytes, metricas, todos_erros = processar_saldo_inicial_ecd(
                        conteudo, ni,
                        st.session_state.get("hist_prefixo_si", "SALDO INICIAL"),
                        st.session_state.get("modo_resultado_si", "apenas_patrimonial"),
                        st.session_state.get("conta_pl_resultado_si", ""),
                        log, prog_bar, status,
                    )
                    st.session_state.resultado_bytes = resultado_bytes
                    st.session_state.resultado_nome  = f"SALDO_INI_{ni}.txt"
                    st.session_state.metricas        = metricas
                    st.session_state.processado      = True
                    if todos_erros:
                        st.session_state.erros_bytes = (
                            _txt_erros_ecd(todos_erros, ni).encode("utf-8-sig")
                        )
                        st.session_state.erros_nome = f"SALDO_INI_{ni}_erros.txt"
                    total_seg = crono.encerrar()
                    log.append(f"\n── TEMPO TOTAL: {Cronometro.fmt(total_seg)} ──")
                    for e in crono.etapas:
                        log.append(f"  {e['nome']}: {Cronometro.fmt(e['segundos'])}")
                    st.session_state.log_linhas = log

                # ── EXCEL ─────────────────────────────────────────────────────
                elif tipo == "excel":
                    crono.etapa("Leitura Excel")
                    status.text("Lendo Excel..."); prog_bar.progress(8)
                    sh = st.session_state.sheet_sel
                    lh_det, _ = detectar_cabecalho_excel(conteudo, sh)
                    lh = lh_det if auto_head else linha_h
                    df, _ = ler_excel_lote(conteudo, sh, lh)
                    log.append(f"Excel — Aba: {sh} | Cabeçalho: linha {lh+1}")
                    log.append(f"Linhas carregadas: {len(df):,}")
                    prog_bar.progress(20)

                    crono.etapa("Montagem de lotes")
                    status.text("Agrupando lotes...")
                    df, modo = montar_lotes_excel(df)
                    n_lotes = int(df["_num_lote"].max()) if len(df) > 0 else 0
                    log.append(f"Lotes detectados  : {n_lotes:,} [modo: {modo}]")
                    prog_bar.progress(35)

                    crono.etapa("Ordenação")
                    status.text("Reordenando lotes...")
                    df = _ordenar_lotes_por_data_filial(df)
                    prog_bar.progress(50)
                    log.append(
                        f"De/Para filiais   : {len(mapa_filiais)} regra(s)"
                        if mapa_filiais else "De/Para filiais   : desabilitado"
                    )
                    log.append(
                        "Reg. 6110         : habilitado"
                        if gerar_6110 else "Reg. 6110         : desabilitado"
                    )

                    crono.etapa("Processamento")
                    status.text("Processando lotes...")
                    resultado_bytes, resumo, erros = processar_excel(
                        df, ni, mapa_filiais, gerar_6110, log
                    )
                    del df; gc.collect()
                    prog_bar.progress(85)

                    n_gravados = resultado_bytes.count(b"|6000|")
                    n6110_f    = resultado_bytes.count(b"|6110|")
                    st.session_state.resultado_bytes = resultado_bytes
                    st.session_state.resultado_nome  = "lancamentos.txt"
                    st.session_state.resumo          = resumo
                    st.session_state.erros_lote      = erros

                    crono.etapa("Log")
                    log_txt = _montar_log_lote(
                        resumo, erros, ni, ti, inf, n_gravados, 0, "N/A (Excel)", crono
                    )
                    st.session_state.log_bytes = log_txt.encode("utf-8-sig")
                    st.session_state.log_nome  = "log_conversao.txt"
                    total_seg = crono.encerrar()
                    log.append(f"\nTempo total: {Cronometro.fmt(total_seg)}")
                    metricas = {
                        "Lotes total":  f"{len(resumo):,}",
                        "Lotes OK":     f"{len(resumo)-len(erros):,}",
                        "Lotes erro":   f"{len(erros):,}",
                        "Reg. gerados": f"{n_gravados:,}",
                        "Tamanho saída":f"{len(resultado_bytes)/1024:.1f} KB",
                    }
                    if gerar_6110:
                        metricas["Reg. 6110"] = f"{n6110_f:,}"
                    st.session_state.metricas   = metricas
                    st.session_state.log_linhas = log
                    st.session_state.processado = True
                    prog_bar.progress(100); status.text("Concluído!")

                # ── TXT POSICIONAL ────────────────────────────────────────────
                elif tipo == "dominio_pos":
                    crono.etapa("Parse posicional")
                    log.append("── TXT POSICIONAL DOMÍNIO ──")
                    resultado_bytes, metricas, erros_parse, filiais_enc = (
                        processar_dominio_posicional(
                            conteudo, ni, gerar_6110,
                            usar_de_para, mapa_filiais,
                            log, prog_bar, status,
                        )
                    )
                    st.session_state.filiais_detectadas = filiais_enc
                    st.session_state.resultado_bytes    = resultado_bytes
                    st.session_state.resultado_nome     = f"DOM_POS_{ni}_dominio.txt"
                    st.session_state.metricas           = metricas
                    st.session_state.processado         = True
                    if erros_parse:
                        st.session_state.erros_bytes = (
                            _txt_erros_ecd(erros_parse, ni).encode("utf-8-sig")
                        )
                        st.session_state.erros_nome = f"DOM_POS_{ni}_erros.txt"
                    total_seg = crono.encerrar()
                    log.append(f"\n── TEMPO TOTAL: {Cronometro.fmt(total_seg)} ──")
                    for e in crono.etapas:
                        log.append(f"  {e['nome']}: {Cronometro.fmt(e['segundos'])}")
                    st.session_state.log_linhas = log

                # ── TXT STREAMING (lote) ──────────────────────────────────────
                else:
                    crono.etapa("Streaming")
                    mb_txt = len(conteudo) / (1024 * 1024)
                    status.text(f"Processando {mb_txt:.1f} MB...")
                    prog_bar.progress(5)
                    log.append(f"── TXT STREAMING — {mb_txt:.1f} MB ──")
                    resultado_bytes, resumo, erros, total_lins, ignoradas, enc_usado = (
                        processar_streaming(conteudo, ni, log)
                    )
                    prog_bar.progress(90)
                    n_gravados = resultado_bytes.count(b"|6000|")
                    st.session_state.resultado_bytes = resultado_bytes
                    st.session_state.resultado_nome  = "lancamentos.txt"
                    st.session_state.resumo          = resumo
                    st.session_state.erros_lote      = erros

                    crono.etapa("Log")
                    log_txt = _montar_log_lote(
                        resumo, erros, ni, ti, inf, n_gravados,
                        ignoradas, enc_usado, crono,
                    )
                    st.session_state.log_bytes = log_txt.encode("utf-8-sig")
                    st.session_state.log_nome  = "log_conversao.txt"
                    total_seg = crono.encerrar()
                    log.append(f"\nTempo total: {Cronometro.fmt(total_seg)}")
                    st.session_state.metricas = {
                        "Linhas lidas":  f"{total_lins:,}",
                        "Lotes total":   f"{len(resumo):,}",
                        "Lotes OK":      f"{len(resumo)-len(erros):,}",
                        "Lotes erro":    f"{len(erros):,}",
                        "Reg. gerados":  f"{n_gravados:,}",
                        "Tamanho saída": f"{len(resultado_bytes)/1024:.1f} KB",
                    }
                    st.session_state.log_linhas = log
                    st.session_state.processado = True
                    prog_bar.progress(100); status.text("Concluído!")

            except Exception as ex:
                tb = traceback.format_exc()
                st.error(f"⛔ Erro inesperado: {ex}")
                log.append(f"ERRO FATAL: {ex}\n{tb}")
                st.session_state.log_linhas = log
                prog_bar.progress(0); status.text("Falha.")

            st.rerun()

        # ── Renderização dos resultados ───────────────────────────────────────
        if st.session_state.processado:
            tipo_proc = st.session_state.tipo_detectado
            if   tipo_proc == "ecd_saldo":   _render_resultados_saldo_inicial(exibir_log)
            elif tipo_proc == "dominio_pos":  _render_resultados_posicional(exibir_log)
            elif tipo_proc == "excel":        _render_resultados_lote(exibir_log)
            elif tipo_proc == "lote":         _render_resultados_lote(exibir_log)
            else:                             _render_resultados_lote(exibir_log)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()

	
