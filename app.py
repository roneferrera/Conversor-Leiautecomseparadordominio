# -*- coding: utf-8 -*-
"""
Domínio Sistemas — Conversor Unificado (Streamlit) V3.6.2
Novidades V3.6.2 (sobre V3.6):
  ┌─ MÓDULO SALDO INICIAL ────────────────────────────────────────────────────┐
  │ • Modo 1 — Apenas Patrimonial:                                            │
  │     Usa somente I155 (Ativo/Passivo/PL).                                  │
  │     Contas de resultado NÃO entram. Correto para balanço de abertura.     │
  │ • Modo 2 — Aberto com Resultado:                                          │
  │     Usa I155 patrimonial + I355 (Receitas/Despesas abertas).              │
  │     Deduz automaticamente o resultado líquido do I355 da conta de PL      │
  │     (Superávit/Déficit) para que D = C.                                   │
  │     Permite encerrar as despesas/receitas no sistema destino.             │
  └───────────────────────────────────────────────────────────────────────────┘
"""
import os
import re
import gc
import io
import time
import traceback
import unicodedata
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime

VERSAO        = "V3.6.2"
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
    [data-testid='metric-container']{background-color:#102040;border-left:4px solid #FF6B00;border-radius:4px;padding:10px;}
    .stProgress>div>div>div>div{background-color:#FF6B00 !important;}
    .bloco-log{background:#060B14;border:1px solid #1A3050;border-radius:6px;padding:14px;
               font-family:Consolas,monospace;font-size:12px;white-space:pre-wrap;
               max-height:520px;overflow-y:auto;color:#E8ECF0;}
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
    .card-ok{background:#0a2e1a;border:2px solid #00C896;border-radius:10px;padding:18px 24px;margin:12px 0;}
    .card-err{background:#2e0a0a;border:2px solid #FF4444;border-radius:10px;padding:18px 24px;margin:12px 0;}
    .card-warn{background:#1a1000;border-left:4px solid #FFD166;border-radius:4px;padding:10px 16px;margin:8px 0;}
    .filial-box{background:#0a1a2e;border:1px solid #6EC6FF;border-radius:8px;padding:14px 18px;margin:10px 0;}
    .si-box{background:#1a0a2e;border:1px solid #FF9EBC;border-radius:8px;padding:14px 18px;margin:10px 0;}
    </style>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CRONÔMETRO
# ═══════════════════════════════════════════════════════════════════════════════
class Cronometro:
    def __init__(self):
        self._inicio_total = 0.0; self._etapas = []
        self._inicio_etapa = 0.0; self._etapa_atual = ""
    def iniciar(self):
        self._inicio_total = time.perf_counter(); self._etapas.clear()
    def etapa(self, nome):
        agora = time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({"nome": self._etapa_atual,
                                  "segundos": round(agora - self._inicio_etapa, 3)})
        self._etapa_atual = nome; self._inicio_etapa = agora
    def encerrar(self):
        agora = time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({"nome": self._etapa_atual,
                                  "segundos": round(agora - self._inicio_etapa, 3)})
            self._etapa_atual = ""
        return round(agora - self._inicio_total, 3)
    @staticmethod
    def fmt(s):
        if s < 0.001: return "<1ms"
        if s < 1:     return f"{s*1000:.0f}ms"
        if s < 60:    return f"{s:.2f}s"
        m = int(s // 60); return f"{m}min {s%60:.1f}s"
    @property
    def etapas(self): return self._etapas

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
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
    for orig, dest in _MAPA_ESPECIAIS.items(): texto = texto.replace(orig, dest)
    texto = unicodedata.normalize("NFC", texto)
    res = []
    for ch in texto:
        cp = ord(ch)
        if cp < 0x20 and cp != 9: continue
        if ch == "|": res.append(" "); continue
        try: ch.encode("latin-1"); res.append(ch); continue
        except UnicodeEncodeError: pass
        decomposto = unicodedata.normalize("NFD", ch); base = decomposto[0]
        try: base.encode("latin-1"); res.append(base); continue
        except UnicodeEncodeError: pass
        nome = unicodedata.name(ch, "")
        if "LATIN" in nome:
            partes = nome.split()
            for i, p in enumerate(partes):
                if p == "LETTER" and i+1 < len(partes):
                    letra = partes[i+1]
                    if len(letra) == 1:
                        res.append(letra.lower() if "SMALL" in nome else letra.upper()); break
    return re.sub(r" {2,}", " ", "".join(res)).strip()[:250]

def sanitizar_texto(t: str) -> str: return _norm_hist(str(t) if t else "")
def formatar_data(v):
    try:
        if isinstance(v, (datetime, pd.Timestamp)): return v.strftime("%d/%m/%Y")
        return pd.to_datetime(v, dayfirst=True).strftime("%d/%m/%Y")
    except: return str(v)
def eh_vazio(v):
    if v is None: return True
    try:
        if pd.isna(v): return True
    except: pass
    return str(v).strip() in ("", "nan", "NaN", "None")
def ts_log(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def so_nums(v): return re.sub(r"\D", "", str(v))

_VAZIO_CONTA = frozenset(("", "nan", "none", "0", "0.0"))

def limpar_contas_vec(serie):
    arr = serie.fillna("").astype(str).str.strip().str.lower().to_numpy()
    out = np.where(np.isin(arr, list(_VAZIO_CONTA)), "", arr)
    mask = out != ""
    if mask.any():
        vals = out[mask]; conv = np.empty(len(vals), dtype=object)
        for i, v in enumerate(vals):
            try: conv[i] = str(int(float(v.replace(",", "."))))
            except: conv[i] = v
        out[mask] = conv
    return out

def limpar_valor_vec(serie):
    return (pd.to_numeric(
        serie.fillna("0").astype(str).str.strip()
             .str.replace(",", ".", regex=False)
             .str.replace(r"[^\d.\-]", "", regex=True),
        errors="coerce").fillna(0.0).round(2).to_numpy(dtype=np.float64))

def validar_cnpj(cnpj):
    c = so_nums(cnpj)
    if len(c) != 14 or len(set(c)) == 1: return False
    def d(c, p):
        s = sum(int(c[i])*p[i] for i in range(len(p))); r = s % 11
        return 0 if r < 2 else 11-r
    return (int(c[12]) == d(c,[5,4,3,2,9,8,7,6,5,4,3,2]) and
            int(c[13]) == d(c,[6,5,4,3,2,9,8,7,6,5,4,3,2]))

def validar_cpf(cpf):
    c = so_nums(cpf)
    if len(c) != 11 or len(set(c)) == 1: return False
    def d(c, n):
        s = sum(int(c[i])*(n-i) for i in range(n-1)); r = (s*10)%11
        return 0 if r == 10 else r
    return int(c[9]) == d(c,10) and int(c[10]) == d(c,11)

def validar_inscricao(v):
    n = so_nums(v)
    if len(n) == 14 and validar_cnpj(n): return True, "CNPJ", n
    if len(n) == 11 and validar_cpf(n):  return True, "CPF",  n
    return False, "", n

def fmt_cnpj(n):
    c = so_nums(n)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c)==14 else n
def fmt_cpf(n):
    c = so_nums(n)
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c)==11 else n
def fmt_reg_0000(ni: str) -> str: return f"|0000|{ni}|"
def fmt_reg_6000(tp: str) -> str: return f"|6000|{tp}||||"

def _fmt_valor_layout(valor) -> str:
    if isinstance(valor, (int, float)): return f"{float(valor):.2f}".replace(".", ",")
    v = str(valor).strip()
    if "." in v and "," in v:
        if v.index(".") < v.index(","): v = v.replace(".", "").replace(",", ".")
        else: v = v.replace(",", "")
    elif "," in v: v = v.replace(",", ".")
    try: return f"{float(v):.2f}".replace(".", ",")
    except ValueError: return "0,00"

def fmt_reg_6100(data, deb, cred, valor, cod_hist="", desc="", _u="", _f="", _s=""):
    return f"|6100|{data}|{deb}|{cred}|{_fmt_valor_layout(valor)}||{_norm_hist(desc)}|||||||"

_CHARS_PT = set("ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿºª")

def _detectar_encoding_bytes(conteudo: bytes) -> str:
    for enc in ("utf-8-sig","utf-8","cp1252","latin-1"):
        try:
            texto = conteudo.decode(enc, errors="strict")
            if sum(1 for c in texto[:4096] if c in _CHARS_PT) > 0 or enc in ("utf-8-sig","utf-8"):
                return enc
        except (UnicodeDecodeError, LookupError): continue
    return "latin-1"

def _gerar_6110_linha(deb_cta, cred_cta, valor_fmt, modo):
    linhas = []
    if modo in ("ambos","deb")  and deb_cta:  linhas.append(f"|6110|{deb_cta}||{valor_fmt}|")
    if modo in ("ambos","cred") and cred_cta: linhas.append(f"|6110||{cred_cta}|{valor_fmt}|")
    return linhas

# ═══════════════════════════════════════════════════════════════════════════════
# IDENTIFICAÇÃO DE TIPO
# ═══════════════════════════════════════════════════════════════════════════════
def identificar_tipo(nome_arquivo: str, conteudo: bytes) -> str:
    ext = os.path.splitext(nome_arquivo)[1].lower()
    if ext in (".xlsx",".xls",".xlsm"): return "excel"
    enc = _detectar_encoding_bytes(conteudo)
    try: amostra = conteudo[:8192].decode(enc, errors="replace")
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

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO SPED ECD — LANÇAMENTOS (I200/I250)
# ═══════════════════════════════════════════════════════════════════════════════
def _split_pipe(linha: str) -> list:
    c = linha.strip().split("|")
    if c and c[0] == "":  c = c[1:]
    if c and c[-1] == "": c = c[:-1]
    return c

def _campo(campos: list, idx: int, default: str = "") -> str:
    return campos[idx].strip() if idx < len(campos) else default

def _conta_valida(conta: str) -> bool:
    return bool(conta) and conta.isdigit()

class SpedECD:
    def __init__(self):
        self.cnpj = ""; self.contas = {}; self.historicos = {}; self.lancamentos = []

def _parse_ecd(conteudo: bytes, log: list) -> tuple:
    ecd = SpedECD(); lote_atual = None; erros_parse = 0
    registros_erro = []; contas_invalidas = 0; i200_count = 0; i250_count = 0
    enc = _detectar_encoding_bytes(conteudo)
    log.append(f"  Encoding detectado : {enc}")
    try: texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")
    linhas = texto.splitlines()
    log.append(f"  Total de linhas    : {len(linhas):,}")
    for num, linha in enumerate(linhas, 1):
        linha_orig = linha; linha = linha.strip()
        if not linha: continue
        campos = _split_pipe(linha)
        if not campos: continue
        reg = campos[0]
        try:
            if reg == "0000":
                if len(campos) > 5: ecd.cnpj = _campo(campos, 5)
            elif reg == "I050":
                cod = _campo(campos,5); nome = _campo(campos,7)
                if cod: ecd.contas[cod] = nome
            elif reg == "I075":
                cod = _campo(campos,1); desc = _campo(campos,2)
                if cod: ecd.historicos[cod] = _norm_hist(desc)
            elif reg == "I200":
                lote_atual = {"num":_campo(campos,1),"data":_campo(campos,2),
                              "valor":_campo(campos,3),"partidas":[]}
                ecd.lancamentos.append(lote_atual); i200_count += 1
            elif reg == "I250":
                if lote_atual is None:
                    registros_erro.append({"linha":num,"motivo":"I250 sem I200","conteudo":linha_orig.strip()}); continue
                conta = _campo(campos,1); valor_str = _campo(campos,3)
                dc = _campo(campos,4).upper(); descr_hist = _norm_hist(_campo(campos,7))
                if dc not in ("D","C"):
                    registros_erro.append({"linha":num,"motivo":f"IND_DC='{dc}' inválido","conteudo":linha_orig.strip()}); continue
                if not _conta_valida(conta):
                    registros_erro.append({"linha":num,"motivo":f"Conta '{conta}' inválida","conteudo":linha_orig.strip()})
                    contas_invalidas += 1; continue
                lote_atual["partidas"].append({"conta":conta,"valor":valor_str,"dc":dc,"descr_hist":descr_hist})
                i250_count += 1
            elif reg in ("I299","I300"): lote_atual = None
        except Exception as ex:
            registros_erro.append({"linha":num,"motivo":f"Exceção: {ex}","conteudo":linha_orig.strip()})
            erros_parse += 1
            if erros_parse > 50: log.append("ERRO: muitos erros — abortando."); return None, registros_erro
    if not ecd.cnpj: log.append("ERRO: CNPJ não encontrado no registro 0000."); return None, registros_erro
    log.append(f"  CNPJ               : {ecd.cnpj}")
    log.append(f"  Lançamentos (I200) : {i200_count:,}")
    log.append(f"  Partidas (I250)    : {i250_count:,}")
    if contas_invalidas: log.append(f"  Contas inválidas   : {contas_invalidas:,}")
    if registros_erro:   log.append(f"  Erros/avisos       : {len(registros_erro):,}")
    return ecd, registros_erro

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
    try: return float(v)
    except: return 0.0

def _montar_hist_ecd(p): return p.get("descr_hist","").strip()
def _primeiro_hist(partidas):
    for p in partidas:
        h = _montar_hist_ecd(p)
        if h: return h
    return ""

def _classif(nd, nc):
    if nd==1 and nc==1: return "X"
    if nd==1 and nc>1:  return "D"
    if nd>1  and nc==1: return "C"
    return "V"

def tipo_lancamento(nd, nc): return _classif(nd, nc)

def _linhas_ecd(lanc):
    partidas = lanc["partidas"]
    debs  = [p for p in partidas if p["dc"]=="D"]
    creds = [p for p in partidas if p["dc"]=="C"]
    if not debs or not creds: return []
    data = _fmt_data_ecd(lanc["data"]); nd=len(debs); nc=len(creds)
    hist = _primeiro_hist(partidas); out = []
    def so_deb(c,v,h):  return fmt_reg_6100(data,c,"",v,"",h)
    def so_cred(c,v,h): return fmt_reg_6100(data,"",c,v,"",h)
    def deb_cred(cd,cc,v,h): return fmt_reg_6100(data,cd,cc,v,"",h)
    if nd==1 and nc==1:
        db=debs[0]; cr=creds[0]; h=_montar_hist_ecd(db) or _montar_hist_ecd(cr) or hist
        out.append(fmt_reg_6000("X")); out.append(deb_cred(db["conta"],cr["conta"],_str2float(db["valor"]),h))
    elif nd==1 and nc>1:
        db=debs[0]; h=_montar_hist_ecd(db) or hist
        out.append(fmt_reg_6000("D")); out.append(so_deb(db["conta"],_str2float(db["valor"]),h))
        for cr in creds:
            h=_montar_hist_ecd(cr) or _montar_hist_ecd(db) or hist
            out.append(so_cred(cr["conta"],_str2float(cr["valor"]),h))
    elif nd>1 and nc==1:
        cr=creds[0]; h=_montar_hist_ecd(cr) or hist
        out.append(fmt_reg_6000("C")); out.append(so_cred(cr["conta"],_str2float(cr["valor"]),h))
        for db in debs:
            h=_montar_hist_ecd(db) or _montar_hist_ecd(cr) or hist
            out.append(so_deb(db["conta"],_str2float(db["valor"]),h))
    else:
        out.append(fmt_reg_6000("V"))
        for cr in creds:
            h=_montar_hist_ecd(cr) or hist; out.append(so_cred(cr["conta"],_str2float(cr["valor"]),h))
        for db in debs:
            h=_montar_hist_ecd(db) or hist; out.append(so_deb(db["conta"],_str2float(db["valor"]),h))
    return out

def _gerar_ecd(ecd, log, prog_bar, status):
    linhas = [fmt_reg_0000(re.sub(r"\D","",ecd.cnpj))]
    t6000=t6100=ignorados=0; debug={"X":0,"D":0,"C":0,"V":0}; total=len(ecd.lancamentos)
    for idx, lanc in enumerate(ecd.lancamentos):
        if idx%500==0 or idx==total-1:
            prog_bar.progress(min(55+int(((idx+1)/total)*35),99))
            status.text(f"Gerando lançamento {idx+1:,}/{total:,}...")
        if not lanc.get("partidas"): ignorados+=1; continue
        novas = _linhas_ecd(lanc)
        if not novas: ignorados+=1; continue
        for l in novas:
            if l.startswith("|6000|"):
                t=l.split("|")[2] if len(l.split("|"))>2 else "?"; debug[t]=debug.get(t,0)+1; t6000+=1
            elif l.startswith("|6100|"): t6100+=1
        linhas.extend(novas)
    log.append(f"  Reg. 6000 gerados  : {t6000:,}"); log.append(f"  Reg. 6100 gerados  : {t6100:,}")
    log.append(f"  Ignorados          : {ignorados:,}")
    log.append(f"  Tipos — X:{debug.get('X',0)} D:{debug.get('D',0)} C:{debug.get('C',0)} V:{debug.get('V',0)}")
    return linhas

def _injetar_6110_ecd(linhas_ecd):
    resultado = []
    for l in linhas_ecd:
        resultado.append(l)
        if l.startswith("|6100|"):
            campos = l.split("|")
            if len(campos) >= 6:
                deb_l=campos[3].strip(); cred_l=campos[4].strip(); valor_l=campos[5].strip()
                if deb_l and cred_l: modo="ambos"
                elif deb_l: modo="deb"
                else: modo="cred"
                for linha_6110 in _gerar_6110_linha(deb_l, cred_l, valor_l, modo):
                    resultado.append(linha_6110)
    return resultado

def _txt_erros_ecd(registros_erro: list, cnpj: str) -> str:
    linhas = ["="*70,"RELATÓRIO DE ERROS — SPED ECD",
              f"CNPJ : {cnpj}",f"Total: {len(registros_erro)}","="*70,""]
    for i, r in enumerate(registros_erro, 1):
        linhas += [f"[{i:04d}] Linha   : {r.get('linha','-')}",
                   f"       Motivo  : {r.get('motivo','')}",
                   f"       Conteúdo: {r.get('conteudo','')}", ""]
    linhas += ["="*70,"FIM DO RELATÓRIO"]
    return "\n".join(linhas)

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO SALDO INICIAL V3.6.2
# ═══════════════════════════════════════════════════════════════════════════════
def _normalizar_data_ecd(d: str) -> str:
    d = d.strip()
    if not d: return ""
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", d): return d
    if re.fullmatch(r"\d{8}", d): return f"{d[:2]}/{d[2:4]}/{d[4:]}"
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", d)
    if m: return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return d
def _sugerir_conta_pl(contas_pl_candidatas: list,
                      saldos_i155_raw: dict,
                      resultado_liquido: float,
                      log: list) -> str:
    if not contas_pl_candidatas:
        log.append("  Sugestão PL        : nenhuma candidata encontrada no I050")
        return ""

    candidatas_com_saldo = []
    for c in contas_pl_candidatas:
        cod = c["cod_cta"]
        if cod in saldos_i155_raw:
            v, dc = saldos_i155_raw[cod]
            diff  = abs(abs(v) - resultado_liquido)
            candidatas_com_saldo.append({**c, "saldo": v, "dc": dc, "diff": diff})

    if not candidatas_com_saldo:
        c = contas_pl_candidatas[0]
        log.append(f"  Sugestão PL        : {c['cod_cta']} — {c['nome']} (sem saldo no I155)")
        return c["cod_cta"]

    def _score(c):
        prioridade_nat = 0 if c["cod_nat"] in ("09", "9") else 1
        return (prioridade_nat, c["diff"])

    candidatas_com_saldo.sort(key=_score)
    melhor = candidatas_com_saldo[0]

    log.append(f"\n  ── SUGESTÃO AUTOMÁTICA — CONTA PL/RESULTADO ──")
    log.append(f"  Conta sugerida     : {melhor['cod_cta']}")
    log.append(f"  Nome               : {melhor['nome']}")
    log.append(f"  COD_NAT            : {melhor['cod_nat']}")
    log.append(f"  Saldo no I155      : R$ {melhor['saldo']:,.2f} {melhor['dc']}")
    log.append(f"  Resultado líquido  : R$ {resultado_liquido:,.2f}")
    log.append(f"  Critério detecção  : {melhor['criterio']}")

    return melhor["cod_cta"]
  
def _parse_saldo_inicial_ecd(conteudo: bytes, log: list) -> dict:
    """
    Lê I150, I155, I355 do SPED ECD.
    Separa automaticamente contas patrimoniais (I155) de resultado (I355).
    Contas que aparecem no I355 são marcadas para exclusão do I155
    (evita duplicidade de saldo zerado + saldo real).
    """
    enc = _detectar_encoding_bytes(conteudo)
    log.append(f"  Encoding detectado : {enc}")
    try: texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")
    linhas = texto.splitlines()
    log.append(f"  Total de linhas    : {len(linhas):,}")

    cnpj=""; dt_fin_0000=""; periodos=[]; i155_por_periodo={}
    periodo_atual_idx=-1; saldos_i355={}; erros=[]
    contas_i355: set = set()
    cnt={"0000":0,"I150":0,"I155":0,"I355":0}

    mapa_nome_cta: dict = {}
    mapa_nat_cta: dict = {}
    contas_pl_candidatas: list = []
    mapa_reduz_para_cta: dict = {}

    for num_linha, linha in enumerate(linhas, 1):
        linha = linha.strip()
        if not linha: continue
        campos = _split_pipe(linha)
        if not campos: continue
        reg = campos[0]
        try:
            if reg == "0000":
                cnt["0000"] += 1
                if len(campos) > 5: cnpj = re.sub(r"\D","",_campo(campos,5).strip())
                if len(campos) > 4: dt_fin_0000 = _campo(campos,4).strip()

            elif reg == "I050":
                if len(campos) < 6:
                    continue
                cod_nat  = _campo(campos, 2).strip()
                ind_cta  = _campo(campos, 3).strip().upper()
                cod_cta  = _campo(campos, 5).strip()
                cod_sup  = _campo(campos, 6).strip() if len(campos) > 6 else ""
                nome_cta = _campo(campos, 7).strip() if len(campos) > 7 else ""
                cta_reduz = cod_cta

                if cod_cta:
                    mapa_reduz_para_cta[cod_cta] = cod_cta
                    if cta_reduz:
                        mapa_reduz_para_cta[cta_reduz] = cod_cta
                    mapa_nome_cta[cod_cta] = nome_cta
                    mapa_nat_cta[cod_cta]  = cod_nat

                    eh_resultado_nat = cod_nat in ("05", "09", "5", "9")
                    nome_up = nome_cta.upper()
                    palavras_resultado = (
                        "SUPERAVIT", "DÉFICIT", "DEFICIT",
                        "RESULTADO", "LUCRO", "PREJUIZO", "PREJUÍZO",
                        "SOBRA", "PERDA", "SURPLUS",
                        "RESULTADO DO EXERC", "LUCROS OU PREJUIZ",
                    )
                    eh_resultado_nome = any(p in nome_up for p in palavras_resultado)

                    if ind_cta == "A" and (eh_resultado_nat or eh_resultado_nome):
                        contas_pl_candidatas.append({
                            "cod_cta":  cod_cta,
                            "nome":     nome_cta,
                            "cod_nat":  cod_nat,
                            "cod_sup":  cod_sup,
                            "criterio": "COD_NAT" if eh_resultado_nat else "NOME",
                        })

            elif reg == "I150":
                cnt["I150"] += 1
                dt_ini=_campo(campos,1).strip(); dt_fin=_campo(campos,2).strip()
                periodos.append((dt_ini,dt_fin))
                periodo_atual_idx = len(periodos)-1
                if periodo_atual_idx not in i155_por_periodo:
                    i155_por_periodo[periodo_atual_idx] = {}

            elif reg == "I155":
                cnt["I155"] += 1
                if periodo_atual_idx < 0:
                    erros.append({"linha":num_linha,"motivo":"I155 sem I150","conteudo":linha[:80]}); continue
                cod_cta=_campo(campos,1).strip()
                vl_fin=_campo(campos,7).strip(); ind_dc_fin=_campo(campos,8).strip().upper()
                if not cod_cta: continue
                if ind_dc_fin not in ("D","C"): ind_dc_fin="D"
                try: valor_f=_str2float(vl_fin)
                except: valor_f=0.0
                i155_por_periodo[periodo_atual_idx][cod_cta]=(valor_f,ind_dc_fin)

            elif reg == "I355":
                cnt["I355"] += 1
                cod_cta=_campo(campos,1).strip(); vl_cta=_campo(campos,3).strip()
                ind_dc=_campo(campos,4).strip().upper()
                if not cod_cta: continue
                if ind_dc not in ("D","C"): ind_dc="D"
                try: valor_f=_str2float(vl_cta)
                except: valor_f=0.0
                saldos_i355[cod_cta]=(valor_f,ind_dc)
                contas_i355.add(cod_cta)

        except Exception as ex:
            erros.append({"linha":num_linha,"motivo":f"Exceção: {ex}","conteudo":linha[:80]})

    # Saldos I155 do ÚLTIMO período
    saldos_i155_raw = {}
    if i155_por_periodo:
        ultimo_idx = max(i155_por_periodo.keys())
        saldos_i155_raw = i155_por_periodo[ultimo_idx]
        log.append(f"  Períodos I150      : {len(periodos):,}")
        log.append(f"  Último período     : {periodos[ultimo_idx][0]} a {periodos[ultimo_idx][1]}")
    else:
        log.append("  AVISO: Nenhum registro I150/I155 encontrado.")

    # Separa patrimoniais de resultado
    saldos_i155_pat = {cta:(v,dc) for cta,(v,dc) in saldos_i155_raw.items() if cta not in contas_i355}
    saldos_i155_res = {cta:(v,dc) for cta,(v,dc) in saldos_i155_raw.items() if cta in contas_i355}

    data_ref = periodos[-1][1] if periodos else dt_fin_0000
    data_ref = _normalizar_data_ecd(data_ref)

    log.append(f"  CNPJ               : {cnpj}")
    log.append(f"  Data referência    : {data_ref}")
    log.append(f"  I155 patrimoniais  : {len(saldos_i155_pat):,} contas")
    log.append(f"  I155 resultado     : {len(saldos_i155_res):,} contas (zeradas no encerramento)")
    log.append(f"  I355 resultado     : {len(saldos_i355):,} contas (antes do encerramento)")
    log.append(f"  Candidatas PL      : {len(contas_pl_candidatas):,} conta(s) detectada(s) no I050")
    if erros: log.append(f"  Erros/avisos       : {len(erros):,}")

    # ── Sugestão automática da conta PL ──────────────────────────────────────
    # ↑ indentação correta: 4 espaços, alinhado com o restante do corpo da função
    total_rec = sum(v for v, dc in saldos_i355.values() if dc == "C")
    total_des = sum(v for v, dc in saldos_i355.values() if dc == "D")
    resultado_liq_ref = round(abs(total_rec - total_des), 2)
    conta_pl_sugerida = _sugerir_conta_pl(
        contas_pl_candidatas, saldos_i155_raw, resultado_liq_ref, log
    )
    if conta_pl_sugerida:
        nome_sug = mapa_nome_cta.get(conta_pl_sugerida, "")
        st.session_state["conta_pl_sugerida"]      = conta_pl_sugerida
        st.session_state["conta_pl_sugerida_nome"] = nome_sug
        log.append(f"\n  ── ORIENTAÇÃO ──")
        log.append(f"  Conta sugerida     : {conta_pl_sugerida}")
        log.append(f"  Nome               : {nome_sug}")
        log.append(f"  Use este código no campo 'Conta PL/Resultado' abaixo.")

    return {
        "cnpj":              cnpj,
        "data_ref":          data_ref,
        "saldos_i155_pat":   saldos_i155_pat,
        "saldos_i155_res":   saldos_i155_res,
        "saldos_i355":       saldos_i355,
        "conta_pl_sugerida": conta_pl_sugerida,
        "erros":             erros,
        "cnt":               cnt,
    }


def _calcular_resultado_liquido_i355(saldos_i355: dict) -> tuple:
    """
    Calcula o resultado líquido do exercício a partir do I355.

    Receitas = contas com IND_DC = "C" (saldo credor)
    Despesas = contas com IND_DC = "D" (saldo devedor)

    Resultado líquido = Σ Receitas − Σ Despesas
      > 0 → Superávit  (resultado credor — aumenta o PL)
      < 0 → Déficit    (resultado devedor — reduz o PL)

    Retorna (resultado_liquido, ind_dc_resultado)
      ind_dc_resultado = "C" se superávit, "D" se déficit
    """
    total_rec = sum(v for _, (v, dc) in saldos_i355.items() if dc == "C")
    total_des = sum(v for _, (v, dc) in saldos_i355.items() if dc == "D")
    resultado = round(total_rec - total_des, 2)
    if resultado >= 0:
        return resultado, "C"   # Superávit → PL credor → deduz crédito do PL
    else:
        return abs(resultado), "D"  # Déficit → PL devedor → deduz débito do PL


def _encontrar_conta_pl_resultado(saldos_i155_pat: dict,
                                   conta_pl_manual: str,
                                   log: list) -> str:
    """
    Tenta identificar a conta de Superávit/Déficit no PL.
    Prioridade:
      1. Conta informada manualmente pelo usuário
      2. Conta cujo saldo no I155 é EXATAMENTE igual ao resultado líquido do I355
         (após o encerramento, o resultado foi transferido para essa conta)
    Retorna o código da conta ou "" se não encontrar.
    """
    if conta_pl_manual and conta_pl_manual.strip():
        cta = conta_pl_manual.strip()
        if cta in saldos_i155_pat:
            log.append(f"  Conta PL resultado : {cta} (informada manualmente)")
            return cta
        else:
            log.append(f"  AVISO: Conta {cta} não encontrada no I155 patrimonial.")
    log.append("  Conta PL resultado : não identificada automaticamente — "
               "informe manualmente para o modo Aberto com Resultado.")
    return ""


def _gerar_saldo_inicial_dominio(parsed: dict, ni: str,
                                  historico_prefixo: str,
                                  modo: str,
                                  conta_pl_resultado: str,
                                  log: list) -> tuple:
    data_ref    = parsed["data_ref"]
    saldos_pat  = parsed["saldos_i155_pat"]
    saldos_i355 = parsed["saldos_i355"]

    log.append(f"  Modo               : {modo}")

    if modo == "apenas_patrimonial":
        todos_saldos = dict(saldos_pat)
        log.append(f"  Contas incluídas   : {len(todos_saldos):,} (somente patrimoniais)")

    elif modo == "aberto_com_resultado":
        if not saldos_i355:
            log.append("  AVISO: Nenhum registro I355 encontrado — usando apenas patrimonial.")
            todos_saldos = dict(saldos_pat)

        elif not conta_pl_resultado:
            log.append("  ERRO: Conta de PL/Resultado não informada — usando apenas patrimonial.")
            todos_saldos = dict(saldos_pat)

        else:
            res_liq, dc_res = _calcular_resultado_liquido_i355(saldos_i355)
            total_rec = round(sum(v for _, (v, dc) in saldos_i355.items() if dc == "C"), 2)
            total_des = round(sum(v for _, (v, dc) in saldos_i355.items() if dc == "D"), 2)
            log.append(f"  I355 — Receitas    : R$ {total_rec:,.2f}")
            log.append(f"  I355 — Despesas    : R$ {total_des:,.2f}")
            log.append(f"  Resultado líquido  : R$ {res_liq:,.2f} "
                       f"({'Superávit' if dc_res == 'C' else 'Déficit'})")

            # Começa com o patrimonial
            todos_saldos = dict(saldos_pat)

            if conta_pl_resultado in todos_saldos:
                saldo_pl, dc_pl = todos_saldos[conta_pl_resultado]
                log.append(f"  Conta PL           : {conta_pl_resultado} | "
                           f"Saldo original: R$ {saldo_pl:,.2f} {dc_pl}")

                # Retira o resultado líquido da conta PL para "reabrir" via I355
                if dc_pl == "C" and dc_res == "C":
                    novo_saldo = round(saldo_pl - res_liq, 2)
                elif dc_pl == "D" and dc_res == "D":
                    novo_saldo = round(saldo_pl - res_liq, 2)
                elif dc_pl == "C" and dc_res == "D":
                    novo_saldo = round(saldo_pl + res_liq, 2)
                else:
                    novo_saldo = round(saldo_pl + res_liq, 2)

                if novo_saldo >= 0:
                    todos_saldos[conta_pl_resultado] = (novo_saldo, dc_pl)
                else:
                    dc_inv = "D" if dc_pl == "C" else "C"
                    todos_saldos[conta_pl_resultado] = (abs(novo_saldo), dc_inv)

                novo_v, novo_dc = todos_saldos[conta_pl_resultado]
                log.append(f"  Conta PL ajustada  : R$ {novo_v:,.2f} {novo_dc} "
                           f"(resultado de R$ {res_liq:,.2f} retirado para reabrir via I355)")
            else:
                log.append(f"  AVISO: Conta {conta_pl_resultado} não encontrada no I155 — "
                           f"balanço não fechará.")

            # Inclui as contas de resultado abertas (I355) como linhas separadas
            for cta, (v, dc) in saldos_i355.items():
                todos_saldos[cta] = (v, dc)

            log.append(f"  Contas incluídas   : {len(todos_saldos):,} "
                       f"(patrimonial + {len(saldos_i355):,} contas de resultado abertas)")

    else:
        todos_saldos = dict(saldos_pat)
        log.append("  Modo inválido — usando apenas_patrimonial.")

    todos_saldos = {cta: (v, dc) for cta, (v, dc) in todos_saldos.items() if abs(v) > 1e-6}

    if not todos_saldos:
        log.append("  AVISO: Nenhum saldo diferente de zero encontrado.")
        return b"", {}, []

    debs  = sorted([(cta, v, dc) for cta, (v, dc) in todos_saldos.items() if dc == "D"], key=lambda x: x[0])
    creds = sorted([(cta, v, dc) for cta, (v, dc) in todos_saldos.items() if dc == "C"], key=lambda x: x[0])

    total_deb  = round(sum(v for _, v, _ in debs),  2)
    total_cred = round(sum(v for _, v, _ in creds), 2)
    diferenca  = round(abs(total_deb - total_cred), 2)
    balanceado = diferenca < TOL_VALOR

    log.append(f"  Partidas débito    : {len(debs):,}  → R$ {total_deb:,.2f}")
    log.append(f"  Partidas crédito   : {len(creds):,}  → R$ {total_cred:,.2f}")
    log.append(f"  Diferença          : R$ {diferenca:,.2f}")
    log.append(f"  Balanceado         : {'SIM ✅' if balanceado else 'NAO ⚠ — verifique a conta PL informada'}")

    buf = io.StringIO()
    buf.write(fmt_reg_0000(ni) + "\n")

    nd = len(debs); nc = len(creds)
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

    resultado_bytes = buf.getvalue().encode("utf-8-sig"); del buf

    resumo = {
        "data": data_ref, "total_debito": total_deb, "total_credito": total_cred,
        "diferenca": diferenca, "balanceado": balanceado,
        "qtd_debs": nd, "qtd_creds": nc, "tipo": tp, "n6100": n6100,
        "contas_i155": len(saldos_pat), "contas_i355": len(saldos_i355), "modo": modo,
    }

    erros_out = []
    if not balanceado:
        erros_out.append({
            "linha": 0,
            "motivo": (f"Lançamento desbalanceado: dif. R$ {diferenca:,.2f} "
                       f"(D={total_deb:,.2f} / C={total_cred:,.2f}). "
                       f"Verifique se a conta de PL/Resultado informada está correta."),
            "conteudo": "",
        })
    return resultado_bytes, resumo, erros_out


def _pre_scan_conta_pl_sugerida(conteudo: bytes):
    """
    Lê apenas I050, I150, I155 e I355 para sugerir a conta PL
    sem precisar processar o arquivo completo.
    Grava o resultado no st.session_state.
    """
    log_tmp = []
    enc = _detectar_encoding_bytes(conteudo)
    try: texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")

    contas_pl_candidatas = []
    saldos_i355 = {}
    mapa_nome_cta = {}
    i155_por_periodo = {}
    periodo_atual_idx = -1

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
            eh_resultado_nat  = cod_nat in ("05", "09", "5", "9")
            nome_up = nome_cta.upper()
            palavras_resultado = (
                "SUPERAVIT","DÉFICIT","DEFICIT","RESULTADO",
                "LUCRO","PREJUIZO","PREJUÍZO","SOBRA","PERDA",
                "SURPLUS","RESULTADO DO EXERC","LUCROS OU PREJUIZ",
            )
            eh_resultado_nome = any(p in nome_up for p in palavras_resultado)
            if ind_cta == "A" and (eh_resultado_nat or eh_resultado_nome):
                contas_pl_candidatas.append({
                    "cod_cta":  cod_cta,
                    "nome":     nome_cta,
                    "cod_nat":  cod_nat,
                    "cod_sup":  _campo(campos, 6).strip() if len(campos) > 6 else "",
                    "criterio": "COD_NAT" if eh_resultado_nat else "NOME",
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
            try: valor_f = _str2float(vl_fin)
            except: valor_f = 0.0
            i155_por_periodo[periodo_atual_idx][cod_cta] = (valor_f, ind_dc)

        elif reg == "I355":
            cod_cta = _campo(campos, 1).strip()
            vl_cta  = _campo(campos, 3).strip()
            ind_dc  = _campo(campos, 4).strip().upper()
            if not cod_cta: continue
            if ind_dc not in ("D", "C"): ind_dc = "D"
            try: valor_f = _str2float(vl_cta)
            except: valor_f = 0.0
            saldos_i355[cod_cta] = (valor_f, ind_dc)

    # Pega saldos do último período I155
    saldos_i155_raw = {}
    if i155_por_periodo:
        ultimo_idx = max(i155_por_periodo.keys())
        saldos_i155_raw = i155_por_periodo[ultimo_idx]

    # Calcula resultado líquido do I355
    total_rec = sum(v for v, dc in saldos_i355.values() if dc == "C")
    total_des = sum(v for v, dc in saldos_i355.values() if dc == "D")
    resultado_liq_ref = round(abs(total_rec - total_des), 2)

    # Sugere a conta PL e grava no session_state
    sugerida = _sugerir_conta_pl(
        contas_pl_candidatas, saldos_i155_raw, resultado_liq_ref, log_tmp
    )
    if sugerida:
        st.session_state["conta_pl_sugerida"]      = sugerida
        st.session_state["conta_pl_sugerida_nome"] = mapa_nome_cta.get(sugerida, "")

def processar_saldo_inicial_ecd(conteudo: bytes, ni: str,
                                 historico_prefixo: str,
                                 modo: str,
                                 conta_pl_resultado: str,
                                 log: list, prog_bar, status) -> tuple:
    """Ponto de entrada do módulo Saldo Inicial V3.6.2."""
    status.text("Lendo SPED ECD — extraindo saldos (I155 + I355)...")
    prog_bar.progress(10)
    log.append("── PARSE SALDO INICIAL (ECD) V3.6.2 ──")

    parsed = _parse_saldo_inicial_ecd(conteudo, log)
    conta_pl_sugerida = parsed.get("conta_pl_sugerida", "")
    if conta_pl_sugerida:
        nome_pl = parsed.get("mapa_nome_cta", {}).get(conta_pl_sugerida, "")
        st.session_state["conta_pl_sugerida"]      = conta_pl_sugerida
        st.session_state["conta_pl_sugerida_nome"] = nome_pl
      
    cnpj_uso = ni if ni else parsed["cnpj"]
    if not cnpj_uso:
        log.append("ERRO: CNPJ não encontrado.")
        return b"", {}, [{"linha":0,"motivo":"CNPJ não encontrado","conteudo":""}]

    prog_bar.progress(50)
    status.text("Gerando lançamento único de saldo inicial...")
    log.append("\n── GERAÇÃO ──")

    resultado_bytes, resumo, erros_ger = _gerar_saldo_inicial_dominio(
        parsed, cnpj_uso, historico_prefixo, modo, conta_pl_resultado, log)

    todos_erros = parsed["erros"] + erros_ger
    prog_bar.progress(90)
    n6100 = resultado_bytes.count(b"|6100|") if resultado_bytes else 0

    metricas = {
        "CNPJ / CPF":      cnpj_uso,
        "Data referência": resumo.get("data",""),
        "Modo":            "Patrimonial" if modo=="apenas_patrimonial" else "Aberto+Resultado",
        "Contas I155":     f"{resumo.get('contas_i155',0):,}",
        "Contas I355":     f"{resumo.get('contas_i355',0):,}",
        "Partidas D":      f"{resumo.get('qtd_debs',0):,}",
        "Partidas C":      f"{resumo.get('qtd_creds',0):,}",
        "Tipo":            resumo.get("tipo","-"),
        "Reg. 6100":       f"{n6100:,}",
        "Balanceado":      "SIM" if resumo.get("balanceado") else "NAO",
        "Tamanho":         f"{len(resultado_bytes)/1024:.1f} KB",
    }
    prog_bar.progress(100); status.text("Concluído!")
    return resultado_bytes, metricas, todos_erros

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO TXT STREAMING
# ═══════════════════════════════════════════════════════════════════════════════
def _filtrar_chunk(chunk):
    for c in COLS_PADRAO:
        if c not in chunk.columns: chunk[c] = ""
    for c in COLS_PADRAO: chunk[c] = chunk[c].fillna("").astype(str).str.strip()
    il = chunk["Inicia Lote"].str.strip()
    chunk["Inicia Lote"] = il.where(il.str.fullmatch(r"[1-9]\d*"), "")
    m_data = chunk["Data"] != ""
    datas  = pd.to_datetime(chunk.loc[m_data,"Data"], dayfirst=True, errors="coerce")
    m_dv   = m_data.copy(); m_dv[m_data] = datas.notna()
    m_conta = ((chunk["Cód. Conta Debito"]!="")|(chunk["Cód. Conta Credito"]!=""))
    m_valor = chunk["Valor"].str.strip() != ""
    return chunk[m_dv & m_conta & m_valor].copy()

def ler_txt_streaming(conteudo: bytes):
    enc = _detectar_encoding_bytes(conteudo); buf = io.BytesIO(conteudo)
    reader = pd.read_csv(buf, sep=";", header=None, names=COLS_PADRAO, dtype=str,
                         encoding=enc, on_bad_lines="skip", engine="c",
                         usecols=range(len(COLS_PADRAO)), chunksize=CHUNK_SIZE)
    linha_at = 0
    for chunk in reader:
        n = len(chunk)
        chunk["_linha_origem"] = np.arange(linha_at+1, linha_at+n+1, dtype=np.int32)
        linha_at += n
        filtrado = _filtrar_chunk(chunk); del chunk
        if len(filtrado) > 0: yield filtrado, enc
        del filtrado

def diagnosticar_lote(W, dif):
    debs=W[W["td"]].copy(); creds=W[W["tc"]].copy()
    td=round(float(debs["vf"].sum()),2); tc=round(float(creds["vf"].sum()),2)
    linhas_det=[]
    for _,r in W.iterrows():
        linhas_det.append({"linha_origem":int(r["lo"]),"data":formatar_data(r["dt"]),
                           "conta_debito":str(r["cd"]) if r["td"] else "",
                           "conta_credito":str(r["cc"]) if r["tc"] else "",
                           "valor":float(r["vf"]),"descricao":_norm_hist(str(r["desc"]))[:70],
                           "tipo":"D" if r["td"] else "C"})
    suspeitas=[]; dif_abs=abs(dif)
    for r in linhas_det:
        if abs(r["valor"]-dif_abs) < TOL_VALOR:
            suspeitas.append({**r,"motivo":f"Valor R$ {r['valor']:.2f} igual à diferença"})
    if not suspeitas:
        for r in linhas_det:
            v=r["valor"]
            if r["tipo"]=="D":
                if abs(round(td-v,2)-tc) < TOL_VALOR:
                    suspeitas.append({**r,"motivo":f"Remover DÉBITO R$ {v:.2f} zeraria o lote"})
            else:
                if abs(td-round(tc-v,2)) < TOL_VALOR:
                    suspeitas.append({**r,"motivo":f"Remover CRÉDITO R$ {v:.2f} zeraria o lote"})
    sugestao=(f"Débito excede crédito em R$ {dif_abs:.2f}." if td>tc
              else f"Crédito excede débito em R$ {dif_abs:.2f}.")
    return {"total_debito":td,"total_credito":tc,"diferenca":dif_abs,
            "qtd_debitos":len(debs),"qtd_creditos":len(creds),
            "linhas":linhas_det,"suspeitas":suspeitas,"sugestao":sugestao}

def _gerar_linhas_6100(debs, creds, tp):
    out=[]
    if tp=="X":
        rd=debs.iloc[0]; rc=creds.iloc[0]
        out.append(fmt_reg_6100(formatar_data(rd["dt"]),str(rd["cd"]),str(rc["cc"]),
                                float(rd["vf"]),"",_norm_hist(str(rd["desc"]) or str(rc["desc"]))))
    elif tp=="D":
        rd=debs.iloc[0]
        out.append(fmt_reg_6100(formatar_data(rd["dt"]),str(rd["cd"]),"",float(rd["vf"]),"",_norm_hist(str(rd["desc"]))))
        for _,rc in creds.iterrows():
            out.append(fmt_reg_6100(formatar_data(rd["dt"]),"",str(rc["cc"]),float(rc["vf"]),"",
                                    _norm_hist(str(rc["desc"]) or str(rd["desc"]))))
    elif tp=="C":
        rc=creds.iloc[0]
        out.append(fmt_reg_6100(formatar_data(debs.iloc[0]["dt"]),"",str(rc["cc"]),float(rc["vf"]),"",_norm_hist(str(rc["desc"]))))
        for _,rd in debs.iterrows():
            out.append(fmt_reg_6100(formatar_data(rd["dt"]),str(rd["cd"]),"",float(rd["vf"]),"",
                                    _norm_hist(str(rd["desc"]) or str(rc["desc"]))))
    else:
        for _,rc in creds.iterrows():
            out.append(fmt_reg_6100(formatar_data(rc["dt"]),"",str(rc["cc"]),float(rc["vf"]),"",_norm_hist(str(rc["desc"]))))
        for _,rd in debs.iterrows():
            out.append(fmt_reg_6100(formatar_data(rd["dt"]),str(rd["cd"]),"",float(rd["vf"]),"",_norm_hist(str(rd["desc"]))))
    return out

def _flush_lote(df_lote, num, saida_buf, resumo, erros):
    if df_lote is None or len(df_lote)==0: return
    v_float=limpar_valor_vec(df_lote["Valor"])
    cd_arr=limpar_contas_vec(df_lote["Cód. Conta Debito"])
    cc_arr=limpar_contas_vec(df_lote["Cód. Conta Credito"])
    td_arr=cd_arr!=""; tc_arr=cc_arr!=""; ambos_arr=td_arr&tc_arr
    vd_arr=np.where(td_arr,v_float,0.0); vc_arr=np.where(tc_arr,v_float,0.0)
    dt_arr=df_lote["Data"].fillna("").astype(str).to_numpy()
    desc_arr=df_lote["Complemento Histórico"].fillna("").astype(str).to_numpy(dtype=object)
    for i in range(len(desc_arr)): desc_arr[i]=_norm_hist(str(desc_arr[i]))
    lo_arr=df_lote["_linha_origem"].fillna(0).astype(int).to_numpy(dtype=np.int32)
    W=pd.DataFrame({"nl":num,"lo":lo_arr,"vd":vd_arr,"vc":vc_arr,"vf":v_float,
                    "cd":cd_arr,"cc":cc_arr,"td":td_arr,"tc":tc_arr,
                    "ambos":ambos_arr,"dt":dt_arr,"desc":desc_arr})
    lm=int(lo_arr.min()) if len(lo_arr) else 0; lx=int(lo_arr.max()) if len(lo_arr) else 0
    fx=f"{lm}–{lx}" if lm!=lx else str(lm); dt_fmt=formatar_data(dt_arr[0]) if len(dt_arr) else ""
    if ambos_arr.all():
        for _,row in W.iterrows():
            desc=_norm_hist(str(row["desc"])); dt_l=formatar_data(str(row["dt"]))
            saida_buf.write(fmt_reg_6000("X")+"\n")
            saida_buf.write(fmt_reg_6100(dt_l,str(row["cd"]),str(row["cc"]),float(row["vf"]),"",desc)+"\n")
            resumo.append({"num_lote":num,"data":dt_l,"descricao":desc,
                           "total_debito":float(row["vf"]),"total_credito":float(row["vf"]),
                           "diferenca":0.0,"balanceado":True,"qtd_linhas":1,
                           "faixa_linhas":str(int(row["lo"])),"diagnostico":{}})
        del W; return
    if ambos_arr.any():
        for _,row in W[W["ambos"]].iterrows():
            desc=_norm_hist(str(row["desc"])); dt_l=formatar_data(str(row["dt"]))
            saida_buf.write(fmt_reg_6000("X")+"\n")
            saida_buf.write(fmt_reg_6100(dt_l,str(row["cd"]),str(row["cc"]),float(row["vf"]),"",desc)+"\n")
            resumo.append({"num_lote":num,"data":dt_l,"descricao":desc,
                           "total_debito":float(row["vf"]),"total_credito":float(row["vf"]),
                           "diferenca":0.0,"balanceado":True,"qtd_linhas":1,
                           "faixa_linhas":str(int(row["lo"])),"diagnostico":{}})
        W_resto=W[~W["ambos"]].reset_index(drop=True)
        if len(W_resto)>0: _flush_lote_normal(W_resto,num,saida_buf,resumo,erros,fx,dt_fmt)
        del W; return
    _flush_lote_normal(W,num,saida_buf,resumo,erros,fx,dt_fmt); del W

def _flush_lote_normal(W, num, saida_buf, resumo, erros, fx, dt_fmt):
    td_arr=W["td"].to_numpy(); tc_arr=W["tc"].to_numpy()
    vd_arr=W["vd"].to_numpy(); vc_arr=W["vc"].to_numpy(); desc_arr=W["desc"].to_numpy()
    td_sum=round(float(vd_arr[td_arr].sum()),2); tc_sum=round(float(vc_arr[tc_arr].sum()),2)
    dif=round(abs(td_sum-tc_sum),2); ok=dif<TOL_VALOR
    entrada={"num_lote":num,"data":dt_fmt,
              "descricao":_norm_hist(str(desc_arr[0])) if len(desc_arr) else "",
              "total_debito":td_sum,"total_credito":tc_sum,"diferenca":dif,
              "balanceado":ok,"qtd_linhas":len(W),"faixa_linhas":fx,"diagnostico":{}}
    if not ok:
        entrada["diagnostico"]=diagnosticar_lote(W,dif); erros.append(entrada)
    else:
        debs=W[W["td"]].reset_index(drop=True); creds=W[W["tc"]].reset_index(drop=True)
        if len(debs)>0 and len(creds)>0:
            tp=tipo_lancamento(len(debs),len(creds))
            linhas_out=[fmt_reg_6000(tp)]+_gerar_linhas_6100(debs,creds,tp)
            saida_buf.write("\n".join(linhas_out)+"\n")
    resumo.append(entrada)

def processar_streaming(conteudo, ni, log):
    saida_buf=io.StringIO(); saida_buf.write(fmt_reg_0000(ni)+"\n")
    pendente=None; num_lote_g=0; usa_inicia=None
    resumo=[]; erros=[]; total_lins=0; ignoradas=0; enc_final="utf-8"; chunk_count=0
    for chunk_df,enc in ler_txt_streaming(conteudo):
        enc_final=enc; total_lins+=len(chunk_df); chunk_count+=1
        if usa_inicia is None: usa_inicia=bool((chunk_df["Inicia Lote"].str.strip()!="").any())
        if pendente is not None and len(pendente)>0:
            chunk_df=pd.concat([pendente,chunk_df],ignore_index=True); pendente=None
        if usa_inicia:
            inicia=chunk_df["Inicia Lote"].fillna("").astype(str).str.strip()
            marcador=(inicia!="").to_numpy(dtype=bool)
            chunk_df["_num_lote"]=np.cumsum(marcador,dtype=np.int32)+num_lote_g
        else:
            cd_tmp=limpar_contas_vec(chunk_df["Cód. Conta Debito"])
            cc_tmp=limpar_contas_vec(chunk_df["Cód. Conta Credito"])
            ambos_tmp=(cd_tmp!="")&(cc_tmp!="")
            desc=(chunk_df["Complemento Histórico"].fillna("").astype(str)
                  .str.strip().str.upper().str.replace(r"\s+"," ",regex=True))
            chave=(chunk_df["Data"].fillna("").astype(str).str.strip()+"|||"+desc).to_numpy()
            muda=np.empty(len(chave),dtype=bool); muda[0]=True; muda[1:]=chave[1:]!=chave[:-1]
            if ambos_tmp.all():
                chunk_df["_num_lote"]=np.arange(num_lote_g+1,num_lote_g+len(chunk_df)+1,dtype=np.int32)
            elif ambos_tmp.any():
                chunk_df["_num_lote"]=np.cumsum(muda|ambos_tmp,dtype=np.int32)+num_lote_g
            else:
                chunk_df["_num_lote"]=np.cumsum(muda,dtype=np.int32)+num_lote_g
        ultimo_lote=int(chunk_df["_num_lote"].max())
        mask_ultimo=chunk_df["_num_lote"]==ultimo_lote
        pendente=chunk_df[mask_ultimo].copy(); chunk_proc=chunk_df[~mask_ultimo]; del chunk_df
        for nl,grupo in chunk_proc.groupby("_num_lote",sort=True):
            _flush_lote(grupo,int(nl),saida_buf,resumo,erros)
        num_lote_g=ultimo_lote-1; del chunk_proc
        if chunk_count%5==0: gc.collect()
    if pendente is not None and len(pendente)>0:
        num_lote_g+=1; _flush_lote(pendente,num_lote_g,saida_buf,resumo,erros); del pendente
    gc.collect()
    log.append(f"  Linhas lidas      : {total_lins:,}"); log.append(f"  Lotes processados : {len(resumo):,}")
    log.append(f"  Lotes OK          : {len(resumo)-len(erros):,}"); log.append(f"  Lotes com erro    : {len(erros):,}")
    saida_bytes=saida_buf.getvalue().encode("utf-8-sig"); del saida_buf
    return saida_bytes,resumo,erros,total_lins,ignoradas,enc_final

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO EXCEL V3.6
# ═══════════════════════════════════════════════════════════════════════════════
_COLS_ESP_LOW = [c.lower() for c in COLS_PADRAO[:8]]

def detectar_cabecalho_excel(conteudo, sheet):
    buf=io.BytesIO(conteudo); raw=pd.read_excel(buf,sheet_name=sheet,header=None,nrows=25,engine="openpyxl")
    pasta=None
    try:
        v=str(raw.iloc[1,6]).strip()
        if v and v.lower() not in ("nan","none",""): pasta=v
    except: pass
    for i,row in raw.iterrows():
        vals=[str(v).strip().lower() for v in row if not eh_vazio(v)]
        if sum(1 for c in _COLS_ESP_LOW if c in vals)>=4: return i,pasta
    return 3,pasta

def ler_excel_lote(conteudo, sheet, linha_h):
    buf=io.BytesIO(conteudo); raw=pd.read_excel(buf,sheet_name=sheet,header=None,dtype=str,engine="openpyxl")
    pasta="C:\\Temp"
    try:
        v=str(raw.iloc[1,6]).strip()
        if v and v.lower() not in ("nan","none",""): pasta=v
    except: pass
    while raw.shape[1]<len(COLS_PADRAO)+2: raw[raw.shape[1]]=""
    raw.columns=range(raw.shape[1])
    df=raw.iloc[linha_h+1:].reset_index(drop=True).copy(); del raw; gc.collect()
    df.columns=list(range(df.shape[1])); df=df.rename(columns={i:c for i,c in enumerate(COLS_PADRAO)})
    _V={"nan","NaN","None","none",""}
    for c in COLS_PADRAO:
        if c in df.columns: df[c]=df[c].fillna("").astype(str).str.strip().replace(list(_V),"")
    mask=~((df["Data"]=="")&(df["Cód. Conta Debito"]=="")&(df["Cód. Conta Credito"]=="")&(df["Valor"]==""))
    df=df[mask].reset_index(drop=True).copy()
    df["_linha_origem"]=(df.index+linha_h+2).astype(np.int32)
    return df,pasta

def _limpar_filial(v):
    s=str(v).strip() if v is not None else ""
    if s.lower() in ("","nan","none","0","0.0"): return ""
    try:
        n=int(float(s)); return "" if n==0 else str(n)
    except: return s

def _limpar_cc(v):
    s=str(v).strip() if v is not None else ""
    if s.lower() in ("","nan","none","0","0.0"): return ""
    try:
        n=int(float(s)); return "" if n==0 else str(n)
    except: return s

def montar_lotes_excel(df):
    R=df.copy()
    for col in COLS_PADRAO+["_linha_origem"]:
        if col not in R.columns: R[col]=""
    inicia_raw=R["Inicia Lote"].fillna("").astype(str).str.strip()
    inicia_num=pd.to_numeric(inicia_raw,errors="coerce"); tem_ini=bool((inicia_num>0).any())
    if tem_ini:
        lote_atual=0; lote_map={}; lote_ids=[]
        for v in inicia_num:
            if pd.notna(v) and v>0:
                v_int=int(v)
                if v_int not in lote_map: lote_atual+=1; lote_map[v_int]=lote_atual
                lote_ids.append(lote_map[v_int])
            else: lote_ids.append(lote_atual if lote_atual>0 else 1)
        R["_num_lote"]=np.array(lote_ids,dtype=np.int32); modo="Inicia Lote (agrupamento por valor)"
    else:
        cd_tmp=limpar_contas_vec(R["Cód. Conta Debito"]); cc_tmp=limpar_contas_vec(R["Cód. Conta Credito"])
        ambos_tmp=(cd_tmp!="")&(cc_tmp!="")
        desc=(R["Complemento Histórico"].fillna("").astype(str).str.strip().str.upper().str.replace(r"\s+"," ",regex=True))
        chave=(R["Data"].fillna("").astype(str).str.strip()+"|||"+desc).to_numpy()
        muda=np.empty(len(chave),dtype=bool); muda[0]=True; muda[1:]=chave[1:]!=chave[:-1]
        if ambos_tmp.all(): R["_num_lote"]=np.arange(1,len(R)+1,dtype=np.int32)
        elif ambos_tmp.any(): R["_num_lote"]=np.cumsum(muda|ambos_tmp,dtype=np.int32)
        else: R["_num_lote"]=np.cumsum(muda,dtype=np.int32)
        modo="Data + Descrição (fallback)"
    return R,modo

def _ordenar_lotes_por_data_filial(df):
    lote_info=[]
    for num_lote,grupo in df.groupby("_num_lote",sort=False):
        datas=pd.to_datetime(grupo["Data"].fillna("").astype(str),dayfirst=True,errors="coerce")
        data_min=datas.min()
        if pd.isna(data_min): data_min=pd.Timestamp("9999-12-31")
        filiais=grupo["Código Matriz/Filial"].fillna("").astype(str).str.strip()
        filiais_validas=filiais[~filiais.str.lower().isin(["","nan","none","0"])]
        filial_rep=filiais_validas.iloc[0] if len(filiais_validas)>0 else "0"
        try: filial_sort=int(float(filial_rep))
        except: filial_sort=0
        lote_info.append({"_num_lote":num_lote,"_sort_data":data_min,"_sort_filial":filial_sort})
    if not lote_info: return df
    df_info=pd.DataFrame(lote_info).sort_values(["_sort_data","_sort_filial"],ascending=[True,True])
    ordem_lotes=df_info["_num_lote"].tolist()
    partes=[df[df["_num_lote"]==nl] for nl in ordem_lotes]
    df_ord=pd.concat(partes,ignore_index=True)
    mapa_novo={v:i+1 for i,v in enumerate(ordem_lotes)}
    df_ord["_num_lote"]=df_ord["_num_lote"].map(mapa_novo).astype(np.int32)
    return df_ord

def _pre_scan_filiais_excel(df):
    col="Código Matriz/Filial"
    if col not in df.columns: return []
    filiais=set()
    for v in df[col].fillna("").astype(str).str.strip():
        f=_limpar_filial(v)
        if f: filiais.add(f)
    return sorted(filiais,key=lambda x:int(x) if x.isdigit() else x)

def _fmt_reg_6100_excel(data,deb,cred,valor,desc,filial):
    return f"|6100|{data}|{deb}|{cred}|{_fmt_valor_layout(valor)}||{_norm_hist(desc)}||{filial}||"

def _flush_lote_excel(df_lote,num,saida_buf,resumo,erros,mapa_filiais,gerar_6110):
    if df_lote is None or len(df_lote)==0: return
    v_float=limpar_valor_vec(df_lote["Valor"])
    cd_arr=limpar_contas_vec(df_lote["Cód. Conta Debito"])
    cc_arr=limpar_contas_vec(df_lote["Cód. Conta Credito"])
    td_arr=cd_arr!=""; tc_arr=cc_arr!=""; ambos_arr=td_arr&tc_arr
    dt_arr=df_lote["Data"].fillna("").astype(str).to_numpy()
    desc_arr=df_lote["Complemento Histórico"].fillna("").astype(str).to_numpy(dtype=object)
    for i in range(len(desc_arr)): desc_arr[i]=_norm_hist(str(desc_arr[i]))
    lo_arr=df_lote["_linha_origem"].fillna(0).astype(int).to_numpy(dtype=np.int32)
    fil_raw=df_lote["Código Matriz/Filial"].fillna("").astype(str).to_numpy()
    fil_arr=np.array([_limpar_filial(f) for f in fil_raw],dtype=object)
    if mapa_filiais: fil_arr=np.array([mapa_filiais.get(f,f) for f in fil_arr],dtype=object)
    col_ccd="Centro de Custo Débito"; col_ccc="Centro de Custo Crédito"
    ccd_raw=(df_lote[col_ccd].fillna("").astype(str).to_numpy() if col_ccd in df_lote.columns else np.full(len(df_lote),"",dtype=object))
    ccc_raw=(df_lote[col_ccc].fillna("").astype(str).to_numpy() if col_ccc in df_lote.columns else np.full(len(df_lote),"",dtype=object))
    ccd_arr=np.array([_limpar_cc(v) for v in ccd_raw],dtype=object)
    ccc_arr=np.array([_limpar_cc(v) for v in ccc_raw],dtype=object)
    lm=int(lo_arr.min()) if len(lo_arr) else 0; lx=int(lo_arr.max()) if len(lo_arr) else 0
    fx=f"{lm}–{lx}" if lm!=lx else str(lm); dt_fmt=formatar_data(dt_arr[0]) if len(dt_arr) else ""
    W=pd.DataFrame({"nl":num,"lo":lo_arr,"vf":v_float,"cd":cd_arr,"cc":cc_arr,
                    "td":td_arr,"tc":tc_arr,"ambos":ambos_arr,"dt":dt_arr,"desc":desc_arr,
                    "fil":fil_arr,"ccd":ccd_arr,"ccc":ccc_arr})
    if ambos_arr.all():
        for _,row in W.iterrows():
            desc=str(row["desc"]); dt_l=formatar_data(str(row["dt"])); fil=str(row["fil"]); vf=float(row["vf"])
            saida_buf.write(fmt_reg_6000("X")+"\n")
            saida_buf.write(_fmt_reg_6100_excel(dt_l,str(row["cd"]),str(row["cc"]),vf,desc,fil)+"\n")
            if gerar_6110:
                v_fmt=f"{vf:.2f}".replace(".",",")
                for l6110 in _gerar_6110_linha(str(row["ccd"]),str(row["ccc"]),v_fmt,"ambos"): saida_buf.write(l6110+"\n")
            resumo.append({"num_lote":num,"data":dt_l,"descricao":desc,"total_debito":vf,"total_credito":vf,
                           "diferenca":0.0,"balanceado":True,"qtd_linhas":1,"faixa_linhas":str(int(row["lo"])),"diagnostico":{}})
        del W; return
    if ambos_arr.any():
        for _,row in W[W["ambos"]].iterrows():
            desc=str(row["desc"]); dt_l=formatar_data(str(row["dt"])); fil=str(row["fil"]); vf=float(row["vf"])
            saida_buf.write(fmt_reg_6000("X")+"\n")
            saida_buf.write(_fmt_reg_6100_excel(dt_l,str(row["cd"]),str(row["cc"]),vf,desc,fil)+"\n")
            if gerar_6110:
                v_fmt=f"{vf:.2f}".replace(".",",")
                for l6110 in _gerar_6110_linha(str(row["ccd"]),str(row["ccc"]),v_fmt,"ambos"): saida_buf.write(l6110+"\n")
            resumo.append({"num_lote":num,"data":dt_l,"descricao":desc,"total_debito":vf,"total_credito":vf,
                           "diferenca":0.0,"balanceado":True,"qtd_linhas":1,"faixa_linhas":str(int(row["lo"])),"diagnostico":{}})
        W_resto=W[~W["ambos"]].reset_index(drop=True)
        if len(W_resto)>0: _flush_lote_excel_normal(W_resto,num,saida_buf,resumo,erros,fx,dt_fmt,gerar_6110)
        del W; return
    _flush_lote_excel_normal(W,num,saida_buf,resumo,erros,fx,dt_fmt,gerar_6110); del W

def _flush_lote_excel_normal(W,num,saida_buf,resumo,erros,fx,dt_fmt,gerar_6110):
    td_arr=W["td"].to_numpy(); tc_arr=W["tc"].to_numpy(); vf_arr=W["vf"].to_numpy()
    vd_arr=np.where(td_arr,vf_arr,0.0); vc_arr=np.where(tc_arr,vf_arr,0.0); desc_arr=W["desc"].to_numpy()
    td_sum=round(float(vd_arr[td_arr].sum()),2); tc_sum=round(float(vc_arr[tc_arr].sum()),2)
    dif=round(abs(td_sum-tc_sum),2); ok=dif<TOL_VALOR
    entrada={"num_lote":num,"data":dt_fmt,
              "descricao":_norm_hist(str(desc_arr[0])) if len(desc_arr) else "",
              "total_debito":td_sum,"total_credito":tc_sum,"diferenca":dif,
              "balanceado":ok,"qtd_linhas":len(W),"faixa_linhas":fx,"diagnostico":{}}
    if not ok:
        entrada["diagnostico"]=diagnosticar_lote(W,dif); erros.append(entrada)
    else:
        debs=W[W["td"]].reset_index(drop=True); creds=W[W["tc"]].reset_index(drop=True)
        if len(debs)>0 and len(creds)>0:
            tp=tipo_lancamento(len(debs),len(creds)); saida_buf.write(fmt_reg_6000(tp)+"\n")
            def _e(dc,cc,v,h,fil,ccd,ccc,dt):
                saida_buf.write(_fmt_reg_6100_excel(dt,dc,cc,v,_norm_hist(h),fil)+"\n")
                if gerar_6110:
                    if dc and cc: modo="ambos"
                    elif dc: modo="deb"
                    else: modo="cred"
                    vf=f"{v:.2f}".replace(".",",")
                    for l6110 in _gerar_6110_linha(ccd,ccc,vf,modo): saida_buf.write(l6110+"\n")
            if tp=="X":
                rd=debs.iloc[0]; rc=creds.iloc[0]
                _e(str(rd["cd"]),str(rc["cc"]),float(rd["vf"]),str(rd["desc"]) or str(rc["desc"]),
                   str(rd["fil"]) or str(rc["fil"]),str(rd["ccd"]),str(rc["ccc"]),formatar_data(str(rd["dt"])))
            elif tp=="D":
                rd=debs.iloc[0]
                _e(str(rd["cd"]),"",float(rd["vf"]),str(rd["desc"]),str(rd["fil"]),str(rd["ccd"]),"",formatar_data(str(rd["dt"])))
                for _,rc in creds.iterrows():
                    _e("",str(rc["cc"]),float(rc["vf"]),str(rc["desc"]) or str(rd["desc"]),
                       str(rc["fil"]) or str(rd["fil"]),"",str(rc["ccc"]),formatar_data(str(rc["dt"])))
            elif tp=="C":
                rc=creds.iloc[0]
                _e("",str(rc["cc"]),float(rc["vf"]),str(rc["desc"]),str(rc["fil"]),"",str(rc["ccc"]),formatar_data(str(rc["dt"])))
                for _,rd in debs.iterrows():
                    _e(str(rd["cd"]),"",float(rd["vf"]),str(rd["desc"]) or str(rc["desc"]),
                       str(rd["fil"]) or str(rc["fil"]),str(rd["ccd"]),"",formatar_data(str(rd["dt"])))
            else:
                for _,rc in creds.iterrows():
                    _e("",str(rc["cc"]),float(rc["vf"]),str(rc["desc"]),str(rc["fil"]),"",str(rc["ccc"]),formatar_data(str(rc["dt"])))
                for _,rd in debs.iterrows():
                    _e(str(rd["cd"]),"",float(rd["vf"]),str(rd["desc"]),str(rd["fil"]),str(rd["ccd"]),"",formatar_data(str(rd["dt"])))
    resumo.append(entrada)

def processar_excel(df,ni,mapa_filiais,gerar_6110,log):
    saida_buf=io.StringIO(); saida_buf.write(fmt_reg_0000(ni)+"\n")
    resumo=[]; erros=[]
    for nl,grupo in df.groupby("_num_lote",sort=True):
        _flush_lote_excel(grupo,int(nl),saida_buf,resumo,erros,mapa_filiais,gerar_6110)
    gc.collect(); n6110=saida_buf.getvalue().count("|6110|")
    log.append(f"  Lotes processados : {len(resumo):,}"); log.append(f"  Lotes OK          : {len(resumo)-len(erros):,}")
    log.append(f"  Lotes com erro    : {len(erros):,}")
    if gerar_6110: log.append(f"  Reg. 6110 gerados : {n6110:,}")
    saida_bytes=saida_buf.getvalue().encode("utf-8-sig"); del saida_buf
    return saida_bytes,resumo,erros

def _montar_log_lote(resumo,erros,ni,ti,inf,n_gravados,ignoradas,enc,crono):
    td=sum(v["total_debito"] for v in resumo); tc=sum(v["total_credito"] for v in resumo)
    ok=len(resumo)-len(erros); conc="SUCESSO" if not erros else f"ATENÇÃO — {len(erros)} lote(s) desbalanceado(s)"
    SEP="═"*90; sep2="─"*90
    L=[SEP,"  DOMÍNIO SISTEMAS  |  Thomson Reuters","  LOG DE VALIDAÇÃO — LANÇAMENTOS CONTÁBEIS",SEP,
       f"  Data/Hora     : {ts_log()}",f"  Encoding leit.: {enc or 'N/A'}",
       f"  {ti:<6}         : {inf}",SEP,"","  RESUMO GERAL",sep2,
       f"  Lotes total   : {len(resumo):>10,}",f"  Lotes OK      : {ok:>10,}",
       f"  Lotes ERRO    : {len(erros):>10,}",f"  Reg. 6000+6100: {n_gravados:>10,}",
       f"  Ignoradas     : {ignoradas:>10,}",f"  Total Déb.    : R$ {td:>14.2f}",
       f"  Total Créd.   : R$ {tc:>14.2f}",f"  Conclusão     : {conc}",""]
    if crono and crono.etapas:
        total_seg=sum(e["segundos"] for e in crono.etapas)
        L+=[sep2,"  RELATÓRIO DE TEMPO",sep2]
        for e in crono.etapas: L.append(f"  {'  '+e['nome']:<38} {Cronometro.fmt(e['segundos']):>8}")
        L+=["  "+"─"*46,f"  {'  TOTAL':<38} {Cronometro.fmt(total_seg):>8}",""]
    L+=[sep2,f"  {'Lote':<8}{'Linhas':<16}{'Data':<13}{'Qtd':<6}{'Débito':>15}{'Crédito':>15}{'Diferença':>13}  Status","  "+"─"*88]
    for v in resumo:
        L.append(f"  {str(v['num_lote']):<8}{v['faixa_linhas']:<16}{v['data']:<13}{str(v['qtd_linhas']):<6}"
                 f"R$ {v['total_debito']:>12.2f}  R$ {v['total_credito']:>12.2f}  R$ {v['diferenca']:>10.2f}   "
                 f"{'✔ OK' if v['balanceado'] else '✖ ERRO'}")
    L+=["  "+"─"*88,f"  {'TOTAIS':<37}R$ {td:>12.2f}  R$ {tc:>12.2f}","",
        SEP,f"  Fim  │  {ts_log()}",f"  Resultado │  {conc}",SEP]
    return "\n".join(L)

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO DOMÍNIO TXT POSICIONAL
# ═══════════════════════════════════════════════════════════════════════════════
def _extrair_filial(linha):
    if len(linha)<564: return ""
    raw=linha[557:564].strip()
    if not raw or not raw.isdigit(): return ""
    codigo=str(int(raw)); return "" if codigo=="0" else codigo

def _extrair_cc(raw):
    raw=raw.strip()
    if not raw or not raw.isdigit(): return ""
    codigo=str(int(raw)); return "" if codigo=="0" else codigo

def _posicional_para_decimal(val_raw):
    val_raw=val_raw.strip()
    if not val_raw or not val_raw.isdigit(): return 0.0
    val_raw=val_raw.zfill(3)
    try: return float(f"{int(val_raw[:-2])}.{val_raw[-2:]}")
    except: return 0.0

def _parse_posicional(conteudo,log):
    enc=_detectar_encoding_bytes(conteudo); log.append(f"  Encoding detectado : {enc}")
    try: texto=conteudo.decode(enc,errors="replace")
    except: texto=conteudo.decode("utf-8",errors="replace")
    linhas=texto.splitlines(); log.append(f"  Total de linhas    : {len(linhas):,}")
    cabecalho={}; lotes=[]; lote_atual=None; erros=[]; filiais_set=set()
    cnt={"01":0,"02":0,"03":0,"05":0,"08":0,"99":0,"outro":0}
    for num_linha,linha in enumerate(linhas,1):
        if len(linha)<2: continue
        reg=linha[:2]
        try:
            if reg=="01":
                cnt["01"]+=1
                cabecalho={"cod_empresa":linha[2:9].strip(),"cnpj":linha[9:23].strip(),
                           "dt_ini":linha[23:33].strip(),"dt_fin":linha[33:43].strip(),
                           "tipo_nota":linha[44:46].strip() if len(linha)>45 else ""}
                log.append(f"  Cabeçalho — Empresa: {cabecalho['cod_empresa']} | CNPJ: {cabecalho['cnpj']} | Período: {cabecalho['dt_ini']} a {cabecalho['dt_fin']}")
            elif reg=="02":
                cnt["02"]+=1; tipo_lanc=linha[9:10].strip().upper(); data_lanc=linha[10:20].strip(); usuario=linha[20:50].strip()
                if tipo_lanc not in ("X","D","C","V"): tipo_lanc="X"
                lote_atual={"seq":linha[2:9].strip(),"tipo":tipo_lanc,"data":data_lanc,"usuario":usuario,"partidas":[],"centros":[]}
                lotes.append(lote_atual)
            elif reg=="03":
                cnt["03"]+=1
                if lote_atual is None: erros.append({"linha":num_linha,"motivo":"Reg 03 sem Reg 02","conteudo":linha[:80]}); continue
                cta_deb=linha[9:16].strip(); cta_cred=linha[16:23].strip(); val_raw=linha[23:38].strip()
                cod_hist=linha[38:45].strip(); historico=linha[45:557].strip() if len(linha)>45 else ""
                filial_p=_extrair_filial(linha)
                if filial_p: filiais_set.add(filial_p)
                if cta_deb in ("0000000","0",""): cta_deb=""
                if cta_cred in ("0000000","0",""): cta_cred=""
                valor_dec=_posicional_para_decimal(val_raw); hist_norm=_norm_hist(historico)
                idx_partida=len(lote_atual["partidas"])
                lote_atual["partidas"].append({"idx":idx_partida,"seq":linha[2:9].strip(),
                                               "cta_deb":cta_deb,"cta_cred":cta_cred,"valor":valor_dec,
                                               "cod_hist":cod_hist,"hist":hist_norm,"filial":filial_p})
            elif reg=="05":
                cnt["05"]+=1
                if lote_atual is None: erros.append({"linha":num_linha,"motivo":"Reg 05 sem Reg 02","conteudo":linha[:80]}); continue
                if not lote_atual["partidas"]: erros.append({"linha":num_linha,"motivo":"Reg 05 sem Reg 03","conteudo":linha[:80]}); continue
                cc_deb_raw=linha[9:16] if len(linha)>15 else "0000000"
                cc_cred_raw=linha[16:23] if len(linha)>22 else "0000000"
                val_raw5=linha[23:38].strip() if len(linha)>37 else "0"
                cc_deb=_extrair_cc(cc_deb_raw); cc_cred=_extrair_cc(cc_cred_raw); valor_c=_posicional_para_decimal(val_raw5)
                idx_pai=lote_atual["partidas"][-1]["idx"]
                lote_atual["centros"].append({"seq":linha[2:9].strip(),"cc_deb":cc_deb,"cc_cred":cc_cred,"valor":valor_c,"idx_partida":idx_pai})
            elif reg=="08": cnt["08"]=cnt.get("08",0)+1
            elif reg=="99": cnt["99"]+=1
            else: cnt["outro"]+=1
        except Exception as ex: erros.append({"linha":num_linha,"motivo":str(ex),"conteudo":linha[:80]})
    log.append(f"  Reg 01 (cabeçalho) : {cnt['01']}"); log.append(f"  Reg 02 (lotes)     : {cnt['02']:,}")
    log.append(f"  Reg 03 (partidas)  : {cnt['03']:,}"); log.append(f"  Reg 05 (c.custos)  : {cnt['05']:,}")
    log.append(f"  Reg 08 (informativo): {cnt.get('08',0):,}")
    if erros: log.append(f"  Erros/avisos       : {len(erros):,}")
    filiais_encontradas=sorted(filiais_set,key=lambda x:int(x) if x.isdigit() else x)
    if filiais_encontradas: log.append(f"  Filiais detectadas : {filiais_encontradas}")
    return {"cabecalho":cabecalho,"lotes":lotes,"erros":erros,"filiais_encontradas":filiais_encontradas}

def _aplicar_de_para(filial,mapa):
    if not filial: return ""
    return mapa.get(filial,filial)

def _gerar_saida_posicional(parsed,ni,gerar_6110,usar_de_para,mapa_filiais,log):
    buf=io.StringIO(); buf.write(f"|0000|{ni}|\n")
    lotes=parsed["lotes"]; ok=ignorados=0; cnt={"t6000":0,"t6100":0,"t6110":0}; debug={"X":0,"D":0,"C":0,"V":0}
    _nulos={"","0","0000000"}
    for lote in lotes:
        data=lote.get("data",""); partidas=lote.get("partidas",[]); centros=lote.get("centros",[])
        if not partidas: ignorados+=1; continue
        debs=[p for p in partidas if p["cta_deb"] not in _nulos]
        creds=[p for p in partidas if p["cta_cred"] not in _nulos]
        if not debs or not creds: ignorados+=1; continue
        nd,nc=len(debs),len(creds)
        if nd==1 and nc==1: tipo_real="X"
        elif nd==1 and nc>1: tipo_real="D"
        elif nd>1 and nc==1: tipo_real="C"
        else: tipo_real="V"
        debug[tipo_real]=debug.get(tipo_real,0)+1
        centros_por_partida={}
        for cc in centros:
            idx=cc.get("idx_partida",-1)
            if idx>=0: centros_por_partida.setdefault(idx,[]).append(cc)
        def _filial_p(p):
            f=p.get("filial","")
            if usar_de_para and mapa_filiais: f=_aplicar_de_para(f,mapa_filiais)
            return f
        def _escreve_6110(idx,modo="ambos"):
            if not gerar_6110: return
            for cc in centros_por_partida.get(idx,[]):
                cc_d=cc.get("cc_deb",""); cc_c=cc.get("cc_cred",""); v_cc=cc.get("valor",0.0)
                v_fmt=f"{v_cc:.2f}".replace(".",",")
                for linha_6110 in _gerar_6110_linha(cc_d,cc_c,v_fmt,modo):
                    buf.write(linha_6110+"\n"); cnt["t6110"]+=1
        def _escreve(dc,cc,v,h,fil,idx):
            vf=f"{v:.2f}".replace(".",","); hs=_norm_hist(h)
            buf.write(f"|6100|{data}|{dc}|{cc}|{vf}||{hs}||{fil}||\n"); cnt["t6100"]+=1
            if dc and cc: modo="ambos"
            elif dc: modo="deb"
            else: modo="cred"
            _escreve_6110(idx,modo)
        buf.write(f"|6000|{tipo_real}||||\n"); cnt["t6000"]+=1
        if tipo_real=="X":
            d=debs[0]; c=creds[0]; h=d["hist"] or c["hist"]; fil=_filial_p(d) or _filial_p(c)
            _escreve(d["cta_deb"],c["cta_cred"],d["valor"],h,fil,d["idx"])
        elif tipo_real=="D":
            d=debs[0]; _escreve(d["cta_deb"],"",d["valor"],d["hist"],_filial_p(d),d["idx"])
            for c in creds:
                h=c["hist"] or d["hist"]; fil=_filial_p(c) or _filial_p(d)
                _escreve("",c["cta_cred"],c["valor"],h,fil,c["idx"])
        elif tipo_real=="C":
            c=creds[0]; _escreve("",c["cta_cred"],c["valor"],c["hist"],_filial_p(c),c["idx"])
            for d in debs:
                h=d["hist"] or c["hist"]; fil=_filial_p(d) or _filial_p(c)
                _escreve(d["cta_deb"],"",d["valor"],h,fil,d["idx"])
        else:
            for c in creds: _escreve("",c["cta_cred"],c["valor"],c["hist"],_filial_p(c),c["idx"])
            for d in debs: _escreve(d["cta_deb"],"",d["valor"],d["hist"],_filial_p(d),d["idx"])
        ok+=1
    log.append(f"  Reg. 6000 gerados  : {cnt['t6000']:,}"); log.append(f"  Reg. 6100 gerados  : {cnt['t6100']:,}")
    if gerar_6110: log.append(f"  Reg. 6110 gerados  : {cnt['t6110']:,}")
    log.append(f"  Lotes OK           : {ok:,}"); log.append(f"  Lotes ignorados    : {ignorados:,}")
    log.append(f"  Tipos — X:{debug.get('X',0)} D:{debug.get('D',0)} C:{debug.get('C',0)} V:{debug.get('V',0)}")
    resultado=buf.getvalue().encode("utf-8-sig"); del buf; gc.collect()
    return resultado

def _pre_scan_posicional(conteudo):
    enc=_detectar_encoding_bytes(conteudo)
    try: texto=conteudo.decode(enc,errors="replace")
    except: texto=conteudo.decode("utf-8",errors="replace")
    filiais=set()
    for linha in texto.splitlines():
        if len(linha)>=564 and linha[:2]=="03":
            raw=linha[557:564].strip()
            if raw and raw.isdigit():
                codigo=str(int(raw))
                if codigo!="0": filiais.add(codigo)
    return sorted(filiais,key=lambda x:int(x) if x.isdigit() else x)

def _pre_popular_mapa_filiais(filiais_encontradas):
    df_atual=st.session_state.get("mapa_filiais_df")
    if df_atual is not None and len(df_atual)>0:
        origens_atuais=set(str(r).strip() for r in df_atual["Código Original (De)"].tolist()
                           if str(r).strip() not in ("","nan","None"))
        if origens_atuais==set(filiais_encontradas): return
    rows=([{"Código Original (De)":f,"Código Destino (Para)":""} for f in filiais_encontradas]
          if filiais_encontradas else [{"Código Original (De)":"","Código Destino (Para)":""}])
    st.session_state["mapa_filiais_df"]=pd.DataFrame(rows,dtype=str)

def _widget_de_para_filiais(habilitado,filiais_encontradas):
    if not habilitado: return {}
    _pre_popular_mapa_filiais(filiais_encontradas)
    st.markdown("""<div style='background:#0a1a2e;border:1px solid #6EC6FF;border-radius:8px;
                padding:14px 18px;margin:10px 0;'>
    <b style='color:#6EC6FF;'>🏢 Mapeamento De/Para — Código da Filial</b><br>
    <small style='color:#9BB0C8;'>Preencha <b style='color:#FFD166;'>Código Destino (Para)</b>
    para remapear. Linhas em branco mantêm o código original.</small></div>""", unsafe_allow_html=True)
    df_base=st.session_state["mapa_filiais_df"].copy()
    df_edit=st.data_editor(df_base,num_rows="fixed",use_container_width=True,
                            column_config={"Código Original (De)":st.column_config.TextColumn("Código Original (De)",disabled=True),
                                           "Código Destino (Para)":st.column_config.TextColumn("Código Destino (Para)",max_chars=20)},
                            key="editor_filiais")
    st.session_state["mapa_filiais_df"]=df_edit
    mapa={}
    for _,row in df_edit.iterrows():
        orig=str(row.get("Código Original (De)","")).strip(); dest=str(row.get("Código Destino (Para)","")).strip()
        if orig and orig.lower() not in ("nan","none","") and dest and dest.lower() not in ("nan","none",""): mapa[orig]=dest
    if mapa: st.caption(f"✅ {len(mapa)} regra(s) ativa(s): {' | '.join(f'{k} → {v}' for k,v in sorted(mapa.items()))}")
    elif filiais_encontradas: st.caption("ℹ️ Nenhum código destino informado — filiais mantidas como estão.")
    else: st.caption("ℹ️ Nenhuma filial detectada no arquivo.")
    return mapa

def processar_dominio_posicional(conteudo,ni,gerar_6110,usar_de_para,mapa_filiais,log,prog_bar,status):
    status.text("Lendo arquivo posicional Domínio..."); prog_bar.progress(10)
    log.append("── PARSE POSICIONAL ──"); parsed=_parse_posicional(conteudo,log); erros=parsed["erros"]
    log.append(f"  De/Para filiais    : {len(mapa_filiais)} regra(s) → {mapa_filiais}" if usar_de_para and mapa_filiais else "  De/Para filiais    : desabilitado")
    prog_bar.progress(50); status.text("Gerando saída com separador..."); log.append("\n── GERAÇÃO ──")
    resultado_bytes=_gerar_saida_posicional(parsed,ni,gerar_6110,usar_de_para,mapa_filiais,log)
    prog_bar.progress(90)
    n6000=resultado_bytes.count(b"|6000|"); n6100=resultado_bytes.count(b"|6100|"); n6110=resultado_bytes.count(b"|6110|")
    metricas={"CNPJ / CPF":ni,"Lotes":f"{len(parsed['lotes']):,}","Reg. 6000":f"{n6000:,}","Reg. 6100":f"{n6100:,}","Tamanho saída":f"{len(resultado_bytes)/1024:.1f} KB"}
    if gerar_6110: metricas["Reg. 6110"]=f"{n6110:,}"
    prog_bar.progress(100); status.text("Concluído!")
    return resultado_bytes,metricas,erros,parsed["filiais_encontradas"]

# ═══════════════════════════════════════════════════════════════════════════════
# ESTADO DA SESSÃO
# ═══════════════════════════════════════════════════════════════════════════════
def _init_state():
    defaults={
        "resultado_bytes":None,"resultado_nome":"saida.txt",
        "erros_bytes":None,"erros_nome":"erros.txt",
        "log_bytes":None,"log_nome":"log.txt",
        "log_linhas":[],"resumo":[],"erros_lote":[],"metricas":{},
        "tipo_detectado":None,"sheets":[],"sheet_sel":"",
        "arquivo_bytes":None,"arquivo_nome":"","processado":False,
        "cnpj_ecd":"","cnpj_ecd_fmt":"","mapa_filiais_df":None,"filiais_detectadas":[],
        # Saldo Inicial
        "modo_saldo_inicial":False,
        "hist_prefixo_si":"SALDO INICIAL",
        "modo_resultado_si":"apenas_patrimonial",
        "conta_pl_resultado_si":"",
    }
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k]=v

def _reset():
    keys=["resultado_bytes","resultado_nome","erros_bytes","erros_nome",
          "log_bytes","log_nome","log_linhas","resumo","erros_lote","metricas",
          "tipo_detectado","sheets","sheet_sel","arquivo_bytes","arquivo_nome",
          "processado","cnpj_ecd","cnpj_ecd_fmt","filiais_detectadas","modo_saldo_inicial"]
    for k in keys:
        st.session_state[k]=(
            [] if k in ("log_linhas","resumo","erros_lote","sheets","filiais_detectadas") else
            {} if k=="metricas" else
            None if k.endswith("_bytes") else
            False if k in ("processado","modo_saldo_inicial") else "")

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO COMPARAÇÃO I052 — ECD ANTERIOR vs. ECD ATUAL
# ═══════════════════════════════════════════════════════════════════════════════
def _parse_i052_completo(conteudo: bytes, log: list) -> dict:
    """
    Lê um SPED ECD e extrai:
      - I050 → mapa conta → nome/natureza
      - I052 → vínculos conta → COD_AGL (plano referencial)
      - I150/I155 → saldo final de cada conta (último período)
      - I350/I355 → saldo inicial de cada conta
      - 0000 → CNPJ e período
    """
    enc = _detectar_encoding_bytes(conteudo)
    log.append(f"  Encoding           : {enc}")
    try:    texto = conteudo.decode(enc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")
    linhas = texto.splitlines()
    log.append(f"  Total de linhas    : {len(linhas):,}")

    cnpj = ""; dt_ini_0000 = ""; dt_fin_0000 = ""
    mapa_nome: dict  = {}   # cod_cta → nome
    mapa_nat:  dict  = {}   # cod_cta → cod_nat
    i052: dict       = {}   # cod_cta → list[cod_agl]

    # Saldos finais (I155) — último período
    i155_por_periodo: dict = {}
    periodo_atual_idx = -1

    # Saldos iniciais (I355) — abertura
    saldos_i355: dict = {}  # cod_cta → (valor, dc)

    cnt = {"0000": 0, "I050": 0, "I052": 0, "I150": 0, "I155": 0, "I355": 0}
    erros = []

    for num_linha, linha in enumerate(linhas, 1):
        linha = linha.strip()
        if not linha:
            continue
        campos = _split_pipe(linha)
        if not campos:
            continue
        reg = campos[0]

        try:
            if reg == "0000":
                cnt["0000"] += 1
                if len(campos) > 3: dt_ini_0000 = _campo(campos, 3).strip()
                if len(campos) > 4: dt_fin_0000 = _campo(campos, 4).strip()
                if len(campos) > 5: cnpj = re.sub(r"\D", "", _campo(campos, 5).strip())

            elif reg == "I050":
                cnt["I050"] += 1
                if len(campos) < 6: continue
                cod_nat  = _campo(campos, 2).strip()
                cod_cta  = _campo(campos, 5).strip()
                nome_cta = _campo(campos, 7).strip() if len(campos) > 7 else ""
                if cod_cta:
                    mapa_nome[cod_cta] = nome_cta
                    mapa_nat[cod_cta]  = cod_nat

            elif reg == "I052":
                cnt["I052"] += 1
                # Layout: |I052|COD_CTA|COD_AGL|
                cod_cta = _campo(campos, 1).strip()
                cod_agl = _campo(campos, 2).strip()
                if cod_cta and cod_agl:
                    i052.setdefault(cod_cta, []).append(cod_agl)

            elif reg == "I150":
                cnt["I150"] += 1
                periodo_atual_idx += 1
                i155_por_periodo[periodo_atual_idx] = {}

            elif reg == "I155":
                cnt["I155"] += 1
                if periodo_atual_idx < 0: continue
                cod_cta   = _campo(campos, 1).strip()
                vl_fin    = _campo(campos, 7).strip()
                ind_dc    = _campo(campos, 8).strip().upper()
                if not cod_cta: continue
                if ind_dc not in ("D", "C"): ind_dc = "D"
                try:    valor_f = _str2float(vl_fin)
                except: valor_f = 0.0
                i155_por_periodo[periodo_atual_idx][cod_cta] = (valor_f, ind_dc)

            elif reg == "I355":
                cnt["I355"] += 1
                cod_cta = _campo(campos, 1).strip()
                vl_cta  = _campo(campos, 3).strip()
                ind_dc  = _campo(campos, 4).strip().upper()
                if not cod_cta: continue
                if ind_dc not in ("D", "C"): ind_dc = "D"
                try:    valor_f = _str2float(vl_cta)
                except: valor_f = 0.0
                saldos_i355[cod_cta] = (valor_f, ind_dc)

        except Exception as ex:
            erros.append({"linha": num_linha, "motivo": str(ex), "conteudo": linha[:80]})

    # Saldos finais do último período I155
    saldos_i155_final: dict = {}
    periodos_count = len(i155_por_periodo)
    if i155_por_periodo:
        ultimo_idx = max(i155_por_periodo.keys())
        saldos_i155_final = i155_por_periodo[ultimo_idx]

    log.append(f"  CNPJ               : {cnpj}")
    log.append(f"  Período            : {_normalizar_data_ecd(dt_ini_0000)} a {_normalizar_data_ecd(dt_fin_0000)}")
    log.append(f"  Registros I050     : {cnt['I050']:,}")
    log.append(f"  Registros I052     : {cnt['I052']:,}  ({len(i052):,} contas com vínculo)")
    log.append(f"  Períodos I150      : {periodos_count:,}")
    log.append(f"  Saldos I155 finais : {len(saldos_i155_final):,}")
    log.append(f"  Saldos I355        : {len(saldos_i355):,}")
    if erros:
        log.append(f"  Erros/avisos       : {len(erros):,}")

    return {
        "cnpj":              cnpj,
        "dt_ini":            _normalizar_data_ecd(dt_ini_0000),
        "dt_fin":            _normalizar_data_ecd(dt_fin_0000),
        "mapa_nome":         mapa_nome,
        "mapa_nat":          mapa_nat,
        "i052":              i052,           # cod_cta → [cod_agl]
        "saldos_finais":     saldos_i155_final,  # cod_cta → (valor, dc)
        "saldos_iniciais":   saldos_i355,        # cod_cta → (valor, dc)
        "erros":             erros,
    }


def _comparar_i052(ant: dict, atu: dict) -> dict:
    """
    Compara os I052 de dois ECDs e retorna:
      - contas_mudaram_grupo : conta mudou de COD_AGL entre os dois arquivos
      - contas_so_anterior   : conta existia no I052 anterior mas sumiu no atual
      - contas_so_atual      : conta nova no I052 atual
      - divergencias_saldo   : saldo final (ant) ≠ saldo inicial (atu) para o mesmo COD_AGL
      - resumo_agl           : por COD_AGL → saldo_fin_ant, saldo_ini_atu, diferença
    """
    i052_ant = ant["i052"]  # cod_cta → [cod_agl]
    i052_atu = atu["i052"]

    contas_ant = set(i052_ant.keys())
    contas_atu = set(i052_atu.keys())

    contas_so_anterior = sorted(contas_ant - contas_atu)
    contas_so_atual    = sorted(contas_atu - contas_ant)
    contas_comuns      = contas_ant & contas_atu

    contas_mudaram_grupo = []
    for cta in sorted(contas_comuns):
        agls_ant = set(i052_ant[cta])
        agls_atu = set(i052_atu[cta])
        if agls_ant != agls_atu:
            contas_mudaram_grupo.append({
                "conta":    cta,
                "nome":     ant["mapa_nome"].get(cta, atu["mapa_nome"].get(cta, "")),
                "agl_ant":  sorted(agls_ant),
                "agl_atu":  sorted(agls_atu),
                "adicionados": sorted(agls_atu - agls_ant),
                "removidos":   sorted(agls_ant - agls_atu),
            })

    # ── Comparação de saldos por COD_AGL ─────────────────────────────────────
    # Agrupa saldo final (ant I155) por COD_AGL
    agl_saldo_fin: dict = {}   # cod_agl → float (signed: C positivo, D negativo)
    for cta, agls in i052_ant.items():
        if cta not in ant["saldos_finais"]: continue
        v, dc = ant["saldos_finais"][cta]
        signed = v if dc == "C" else -v
        for agl in agls:
            agl_saldo_fin[agl] = round(agl_saldo_fin.get(agl, 0.0) + signed, 2)

    # Agrupa saldo inicial (atu I355) por COD_AGL
    agl_saldo_ini: dict = {}   # cod_agl → float (signed)
    for cta, agls in i052_atu.items():
        if cta not in atu["saldos_iniciais"]: continue
        v, dc = atu["saldos_iniciais"][cta]
        signed = v if dc == "C" else -v
        for agl in agls:
            agl_saldo_ini[agl] = round(agl_saldo_ini.get(agl, 0.0) + signed, 2)

    todos_agls = set(agl_saldo_fin.keys()) | set(agl_saldo_ini.keys())
    resumo_agl = []
    divergencias_saldo = []

    for agl in sorted(todos_agls):
        sf = agl_saldo_fin.get(agl, 0.0)
        si = agl_saldo_ini.get(agl, 0.0)
        dif = round(sf - si, 2)
        row = {
            "cod_agl":       agl,
            "saldo_fin_ant": sf,
            "saldo_ini_atu": si,
            "diferenca":     dif,
            "ok":            abs(dif) < TOL_VALOR,
        }
        resumo_agl.append(row)
        if abs(dif) >= TOL_VALOR:
            divergencias_saldo.append(row)

    return {
        "contas_mudaram_grupo":  contas_mudaram_grupo,
        "contas_so_anterior":    contas_so_anterior,
        "contas_so_atual":       contas_so_atual,
        "divergencias_saldo":    divergencias_saldo,
        "resumo_agl":            resumo_agl,
        "total_contas_ant":      len(contas_ant),
        "total_contas_atu":      len(contas_atu),
        "total_agls":            len(todos_agls),
    }


def _render_comparacao_i052(resultado: dict, label_ant: str, label_atu: str,
                             parsed_ant: dict, parsed_atu: dict):
    """Renderiza o resultado da comparação I052 na interface Streamlit."""
    st.markdown("---")
    st.markdown("## 📊 Resultado da Comparação I052")

    # ── Cabeçalho dos arquivos ────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            f"<div class='filial-box'><b style='color:#6EC6FF;'>📁 ANTERIOR</b><br>"
            f"<span style='color:#FFD166;'>{label_ant}</span><br>"
            f"CNPJ: {fmt_cnpj(parsed_ant['cnpj']) if parsed_ant['cnpj'] else '—'}<br>"
            f"Período: {parsed_ant['dt_ini']} a {parsed_ant['dt_fin']}<br>"
            f"Contas I052: {resultado['total_contas_ant']:,}</div>",
            unsafe_allow_html=True
        )
    with col_b:
        st.markdown(
            f"<div class='filial-box'><b style='color:#6EC6FF;'>📁 ATUAL</b><br>"
            f"<span style='color:#FFD166;'>{label_atu}</span><br>"
            f"CNPJ: {fmt_cnpj(parsed_atu['cnpj']) if parsed_atu['cnpj'] else '—'}<br>"
            f"Período: {parsed_atu['dt_ini']} a {parsed_atu['dt_fin']}<br>"
            f"Contas I052: {resultado['total_contas_atu']:,}</div>",
            unsafe_allow_html=True
        )

    # ── Métricas resumo ───────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Contas — Anterior",    f"{resultado['total_contas_ant']:,}")
    m2.metric("Contas — Atual",       f"{resultado['total_contas_atu']:,}")
    m3.metric("Mudaram de grupo",     f"{len(resultado['contas_mudaram_grupo']):,}")
    m4.metric("Só no anterior",       f"{len(resultado['contas_so_anterior']):,}")
    m5.metric("Só no atual",          f"{len(resultado['contas_so_atual']):,}")

    n_div = len(resultado["divergencias_saldo"])
    if n_div == 0:
        st.markdown(
            "<div class='card-ok'>✅ <b style='color:#00C896;'>Todos os saldos por COD_AGL "
            "batem entre o saldo final do anterior e o saldo inicial do atual.</b></div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div class='card-err'>⚠️ <b style='color:#FF4444;'>{n_div} COD_AGL(s) com "
            f"divergência de saldo entre os dois arquivos.</b></div>",
            unsafe_allow_html=True
        )

    # ── Seção 1: Contas que mudaram de grupo ─────────────────────────────────
    st.markdown("#### 🔀 Contas que mudaram de COD_AGL")
    if resultado["contas_mudaram_grupo"]:
        rows_mud = []
        for r in resultado["contas_mudaram_grupo"]:
            rows_mud.append({
                "Conta":       r["conta"],
                "Nome":        r["nome"],
                "AGL Anterior": ", ".join(r["agl_ant"]),
                "AGL Atual":    ", ".join(r["agl_atu"]),
                "Adicionados":  ", ".join(r["adicionados"]),
                "Removidos":    ", ".join(r["removidos"]),
            })
        st.dataframe(pd.DataFrame(rows_mud), use_container_width=True, hide_index=True)
    else:
        st.success("Nenhuma conta mudou de grupo.")

    # ── Seção 2: Contas apenas no anterior ───────────────────────────────────
    with st.expander(f"📤 Contas presentes APENAS no anterior ({len(resultado['contas_so_anterior']):,})",
                     expanded=False):
        if resultado["contas_so_anterior"]:
            rows_ant = [{"Conta": c,
                         "Nome":  parsed_ant["mapa_nome"].get(c, ""),
                         "Nat.":  parsed_ant["mapa_nat"].get(c, "")}
                        for c in resultado["contas_so_anterior"]]
            st.dataframe(pd.DataFrame(rows_ant), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma.")

    # ── Seção 3: Contas apenas no atual ──────────────────────────────────────
    with st.expander(f"📥 Contas presentes APENAS no atual ({len(resultado['contas_so_atual']):,})",
                     expanded=False):
        if resultado["contas_so_atual"]:
            rows_atu = [{"Conta": c,
                         "Nome":  parsed_atu["mapa_nome"].get(c, ""),
                         "Nat.":  parsed_atu["mapa_nat"].get(c, "")}
                        for c in resultado["contas_so_atual"]]
            st.dataframe(pd.DataFrame(rows_atu), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma.")

    # ── Seção 4: Divergências de saldo por COD_AGL ───────────────────────────
    st.markdown("#### 💰 Saldo Final (anterior) vs. Saldo Inicial (atual) por COD_AGL")
    st.caption(
        "Saldo final = soma dos I155 do último período do arquivo anterior, agrupado por COD_AGL.  "
        "Saldo inicial = soma dos I355 do arquivo atual, agrupado por COD_AGL."
    )

    filtro_agl = st.radio(
        "Exibir:", ["Todos os COD_AGL", "✅ Somente OK", "❌ Somente com divergência"],
        horizontal=True, key="filtro_agl_radio"
    )

    rows_agl = []
    for r in resultado["resumo_agl"]:
        if filtro_agl == "✅ Somente OK" and not r["ok"]: continue
        if filtro_agl == "❌ Somente com divergência" and r["ok"]: continue
        rows_agl.append({
            "COD_AGL":         r["cod_agl"],
            "Saldo Fin. Ant.": r["saldo_fin_ant"],
            "Saldo Ini. Atu.": r["saldo_ini_atu"],
            "Diferença":       r["diferenca"],
            "Status":          "✔ OK" if r["ok"] else "✖ DIVERGE",
        })

    if rows_agl:
        df_agl = pd.DataFrame(rows_agl)
        styled = (
            df_agl.style
            .map(lambda v: "color:#00C896;font-weight:700" if v == "✔ OK"
                           else "color:#FF4444;font-weight:700", subset=["Status"])
            .map(lambda v: "color:#FF4444" if abs(v) >= TOL_VALOR else "color:#00C896",
                 subset=["Diferença"])
            .format({
                "Saldo Fin. Ant.": "R$ {:,.2f}",
                "Saldo Ini. Atu.": "R$ {:,.2f}",
                "Diferença":       "R$ {:,.2f}",
            })
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Download da tabela como CSV
        csv_bytes = df_agl.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
        st.download_button(
            "⬇ Baixar comparação COD_AGL (.csv)",
            data=csv_bytes,
            file_name="comparacao_i052_agl.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("Nenhum COD_AGL encontrado para os filtros selecionados.")

def _pre_scan_cnpj_ecd(conteudo):
    enc=_detectar_encoding_bytes(conteudo)
    try: amostra=conteudo[:4096].decode(enc,errors="replace")
    except: amostra=conteudo[:4096].decode("utf-8",errors="replace")
    for linha in amostra.splitlines():
        campos=_split_pipe(linha.strip())
        if campos and campos[0]=="0000" and len(campos)>5:
            cnpj=re.sub(r"\D","",campos[5].strip())
            if len(cnpj)==14: return cnpj
    return ""

# ═══════════════════════════════════════════════════════════════════════════════
# RENDERIZAÇÃO DE RESULTADOS
# ═══════════════════════════════════════════════════════════════════════════════
def _render_resultados_lote(exibir_log):
    resumo=st.session_state.resumo or []; erros=st.session_state.erros_lote or []
    metricas=st.session_state.metricas or {}
    st.markdown("---"); st.markdown("## 📊 Resultado da Conversão")
    if metricas:
        cols=st.columns(len(metricas))
        for i,(k,v) in enumerate(metricas.items()): cols[i].metric(k,v)
    if resumo:
        total=len(resumo); n_ok=sum(1 for v in resumo if v["balanceado"]); n_err=total-n_ok
        pct_ok=n_ok/total if total>0 else 0.0
        td_total=sum(v["total_debito"] for v in resumo); tc_total=sum(v["total_credito"] for v in resumo)
        dif_geral=round(abs(td_total-tc_total),2); tudo_ok=dif_geral<TOL_VALOR and n_err==0
        if tudo_ok:
            st.markdown("<div class='card-ok'><span style='font-size:22px;'>✅</span> <b style='color:#00C896;font-size:18px;'>Todos os lotes balanceados.</b></div>",unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='card-err'><span style='font-size:22px;'>⚠️</span> <b style='color:#FF4444;font-size:18px;'>{n_err} lote(s) desbalanceado(s).</b></div>",unsafe_allow_html=True)
        col_barra,col_nums=st.columns([3,1])
        with col_barra: st.progress(pct_ok); st.caption(f"{n_ok:,} de {total:,} lotes balanceados ({pct_ok*100:.1f}%)")
        with col_nums: st.metric("✅ Balanceados",f"{n_ok:,}"); st.metric("❌ Com erro",f"{n_err:,}")
        col_d,col_c,col_dif=st.columns(3)
        col_d.metric("Total Débito",f"R$ {td_total:,.2f}"); col_c.metric("Total Crédito",f"R$ {tc_total:,.2f}")
        col_dif.metric("Diferença Geral",f"R$ {dif_geral:,.2f}",delta="OK" if tudo_ok else f"R$ {dif_geral:,.2f}",delta_color="normal" if tudo_ok else "inverse")
    if resumo:
        st.markdown("#### 📋 Detalhe por Lote")
        filtro=st.radio("Exibir lotes:",["Todos","✅ Somente OK","❌ Somente com erro"],horizontal=True,key="filtro_lotes_radio")
        rows=[]
        for v in resumo:
            if filtro=="✅ Somente OK" and not v["balanceado"]: continue
            if filtro=="❌ Somente com erro" and v["balanceado"]: continue
            rows.append({"Lote":v["num_lote"],"Linhas":v["faixa_linhas"],"Data":v["data"],"Qtd":v["qtd_linhas"],
                         "Débito":v["total_debito"],"Crédito":v["total_credito"],"Diferença":v["diferenca"],
                         "Status":"✔ OK" if v["balanceado"] else "✖ ERRO"})
        if rows:
            df_res=pd.DataFrame(rows)
            styled=(df_res.style
                    .map(lambda v:"color:#00C896;font-weight:700" if v=="✔ OK" else "color:#FF4444;font-weight:700",subset=["Status"])
                    .map(lambda v:"color:#FF4444" if v>TOL_VALOR else "color:#00C896",subset=["Diferença"])
                    .format({"Débito":"R$ {:,.2f}","Crédito":"R$ {:,.2f}","Diferença":"R$ {:,.2f}"}))
            st.dataframe(styled,use_container_width=True,hide_index=True)
    if erros:
        st.markdown("#### 🔍 Diagnóstico dos Lotes Desbalanceados")
        for e in erros:
            diag=e.get("diagnostico",{})
            label=f"Lote {e['num_lote']}  │  Linhas {e['faixa_linhas']}  │  Data {e['data']}  │  Dif. R$ {e['diferenca']:,.2f}"
            with st.expander(label,expanded=(len(erros)==1)):
                if diag.get("sugestao"):
                    st.markdown(f"<div class='card-warn'>💡 <b style='color:#FFD166;'>Sugestão:</b> {diag['sugestao']}</div>",unsafe_allow_html=True)
                c1,c2,c3,c4=st.columns(4)
                c1.metric("Débito",f"R$ {diag.get('total_debito',0):,.2f}"); c2.metric("Crédito",f"R$ {diag.get('total_credito',0):,.2f}")
                c3.metric("Diferença",f"R$ {diag.get('diferenca',0):,.2f}"); c4.metric("Partidas",f"D:{diag.get('qtd_debitos',0)} / C:{diag.get('qtd_creditos',0)}")
                for s in diag.get("suspeitas",[]):
                    tp="DÉBITO" if s["tipo"]=="D" else "CRÉDITO"; cta=s["conta_debito"] or s["conta_credito"]
                    st.markdown(f"- Linha `{s['linha_origem']}` — **{tp}** Cta `{cta}` — R$ `{s['valor']:,.2f}` — {s['motivo']}")
                if diag.get("linhas"):
                    df_det=pd.DataFrame(diag["linhas"])
                    cols_show=[c for c in ["linha_origem","tipo","conta_debito","conta_credito","valor","descricao"] if c in df_det.columns]
                    st.dataframe(df_det[cols_show].style
                                 .map(lambda v:"color:#6EC6FF;font-weight:700" if v=="D" else "color:#FF9EBC;font-weight:700",subset=["tipo"])
                                 .format({"valor":"R$ {:,.2f}"}),use_container_width=True,hide_index=True)
    st.markdown("---"); st.markdown("#### ⬇ Downloads")
    dl1,dl2,dl3=st.columns(3); n_err=len(erros); n_ok=len(resumo)-n_err
    with dl1:
        if st.session_state.resultado_bytes:
            if n_err==0: st.success(f"✅ {n_ok:,} lotes — arquivo pronto!")
            else: st.warning(f"⚠ {n_ok:,} OK / {n_err:,} com erro")
            st.download_button("⬇ Baixar arquivo convertido",data=st.session_state.resultado_bytes,
                               file_name=st.session_state.resultado_nome,mime="text/plain",use_container_width=True,type="primary")
    with dl2:
        if erros:
            linhas_err=["RELATÓRIO DE LOTES DESBALANCEADOS","="*60,"",f"Data/Hora : {ts_log()}",f"Total erros: {len(erros)}","","="*60,""]
            for e in erros: linhas_err+=[f"Lote: {e['num_lote']} | Data: {e['data']} | Dif: R$ {e['diferenca']:,.2f}",""]
            st.error(f"❌ {len(erros):,} lote(s) com erro.")
            st.download_button("⬇ Baixar relatório de erros",data="\n".join(linhas_err).encode("utf-8-sig"),
                               file_name="erros_lotes.txt",mime="text/plain",use_container_width=True)
        elif st.session_state.erros_bytes:
            st.download_button("⬇ Baixar relatório de erros",data=st.session_state.erros_bytes,
                               file_name=st.session_state.erros_nome,mime="text/plain",use_container_width=True)
    with dl3:
        if st.session_state.log_bytes:
            st.download_button("⬇ Baixar log completo",data=st.session_state.log_bytes,
                               file_name=st.session_state.log_nome,mime="text/plain",use_container_width=True)
    if exibir_log and st.session_state.log_linhas:
        st.markdown("#### 🖥 Log de Processamento")
        log_txt="\n".join(str(l) for l in st.session_state.log_linhas)
        tem_erro=any("ERRO" in str(l).upper() for l in st.session_state.log_linhas)
        st.markdown(f"<div class='bloco-log' style='border-color:{'#FF4444' if tem_erro else '#1A3050'};'>{log_txt}</div>",unsafe_allow_html=True)

def _render_resultados_ecd(exibir_log):
    metricas=st.session_state.metricas or {}
    st.markdown("---"); st.markdown("## 📊 Resultado da Conversão — SPED ECD")
    if metricas:
        cols=st.columns(len(metricas))
        for i,(k,v) in enumerate(metricas.items()): cols[i].metric(k,v)
    st.markdown("#### ⬇ Downloads"); dl1,dl2=st.columns(2)
    with dl1:
        if st.session_state.resultado_bytes:
            st.success("Arquivo gerado com sucesso!")
            st.download_button("⬇ Baixar arquivo convertido",data=st.session_state.resultado_bytes,
                               file_name=st.session_state.resultado_nome,mime="text/plain",use_container_width=True,type="primary")
    with dl2:
        if st.session_state.erros_bytes:
            st.warning("Arquivo de erros disponível.")
            st.download_button("⬇ Baixar relatório de erros",data=st.session_state.erros_bytes,
                               file_name=st.session_state.erros_nome,mime="text/plain",use_container_width=True)
    if exibir_log and st.session_state.log_linhas:
        st.markdown("#### 🖥 Log de Processamento")
        log_txt="\n".join(str(l) for l in st.session_state.log_linhas)
        tem_erro=any("ERRO" in str(l).upper() for l in st.session_state.log_linhas)
        st.markdown(f"<div class='bloco-log' style='border-color:{'#FF4444' if tem_erro else '#1A3050'};'>{log_txt}</div>",unsafe_allow_html=True)

def _render_resultados_posicional(exibir_log):
    metricas=st.session_state.metricas or {}
    st.markdown("---"); st.markdown("## 📊 Resultado — Leiaute Posicional Domínio")
    if metricas:
        cols=st.columns(len(metricas))
        for i,(k,v) in enumerate(metricas.items()): cols[i].metric(k,v)
    st.markdown("#### ⬇ Downloads"); dl1,dl2=st.columns(2)
    with dl1:
        if st.session_state.resultado_bytes:
            st.success("✅ Arquivo convertido com sucesso!")
            st.download_button("⬇ Baixar arquivo convertido",data=st.session_state.resultado_bytes,
                               file_name=st.session_state.resultado_nome,mime="text/plain",use_container_width=True,type="primary")
    with dl2:
        if st.session_state.erros_bytes:
            st.warning("⚠ Há registros com erros de parse.")
            st.download_button("⬇ Baixar relatório de erros",data=st.session_state.erros_bytes,
                               file_name=st.session_state.erros_nome,mime="text/plain",use_container_width=True)
    if exibir_log and st.session_state.log_linhas:
        st.markdown("#### 🖥 Log de Processamento")
        log_txt="\n".join(str(l) for l in st.session_state.log_linhas)
        tem_erro=any("ERRO" in str(l).upper() for l in st.session_state.log_linhas)
        st.markdown(f"<div class='bloco-log' style='border-color:{'#FF4444' if tem_erro else '#1A3050'};'>{log_txt}</div>",unsafe_allow_html=True)

def _render_resultados_saldo_inicial(exibir_log):
    metricas=st.session_state.metricas or {}
    st.markdown("---"); st.markdown("## 📊 Resultado — Saldo Inicial (SPED ECD → Domínio)")
    if metricas:
        items=list(metricas.items())
        for inicio in range(0,len(items),5):
            bloco=items[inicio:inicio+5]; cols=st.columns(len(bloco))
            for i,(k,v) in enumerate(bloco): cols[i].metric(k,v)
    bal=metricas.get("Balanceado","")
    if bal=="SIM":
        st.markdown("<div class='card-ok'><span style='font-size:22px;'>✅</span> <b style='color:#00C896;font-size:18px;'>Lançamento de saldo inicial balanceado (D = C).</b></div>",unsafe_allow_html=True)
    else:
        st.markdown("<div class='card-err'><span style='font-size:22px;'>⚠️</span> <b style='color:#FF4444;font-size:18px;'>Lançamento DESBALANCEADO — verifique a conta de PL/Resultado informada.</b></div>",unsafe_allow_html=True)
    st.markdown("#### ⬇ Downloads"); dl1,dl2,dl3=st.columns(3)
    with dl1:
        if st.session_state.resultado_bytes:
            if bal=="SIM": st.success("✅ Arquivo de saldo inicial gerado!")
            else: st.warning("⚠ Arquivo gerado com diferença.")
            st.download_button("⬇ Baixar saldo inicial (.txt)",data=st.session_state.resultado_bytes,
                               file_name=st.session_state.resultado_nome,mime="text/plain",use_container_width=True,type="primary")
    with dl2:
        if st.session_state.erros_bytes:
            st.error("❌ Há erros — baixe o relatório.")
            st.download_button("⬇ Baixar relatório de erros",data=st.session_state.erros_bytes,
                               file_name=st.session_state.erros_nome,mime="text/plain",use_container_width=True)
    with dl3:
        if st.session_state.log_linhas:
            log_txt="\n".join(str(l) for l in st.session_state.log_linhas)
            st.download_button("⬇ Baixar log",data=log_txt.encode("utf-8-sig"),
                               file_name="log_saldo_inicial.txt",mime="text/plain",use_container_width=True)
    if exibir_log and st.session_state.log_linhas:
        st.markdown("#### 🖥 Log de Processamento")
        log_txt="\n".join(str(l) for l in st.session_state.log_linhas)
        tem_erro=any("ERRO" in str(l).upper() or "NAO" in str(l).upper() for l in st.session_state.log_linhas)
        st.markdown(f"<div class='bloco-log' style='border-color:{'#FF4444' if tem_erro else '#1A3050'};'>{log_txt}</div>",unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(
        page_title="Domínio Sistemas | Thomson Reuters",
        page_icon="🟠", layout="wide", initial_sidebar_state="expanded"
    )
    apply_theme()
    _init_state()

    st.markdown(
        f"<div class='header-box'>"
        f"<h2 style='color:#FF6B00;margin:0;'>Domínio Sistemas — Conversor Unificado</h2>"
        f"<p style='color:#6B7A8D;margin:6px 0 0;'>Lançamentos Contábeis (TXT/Excel/Posicional) &nbsp;|&nbsp; "
        f"SPED ECD &nbsp;→&nbsp; 0000 + 6000 + 6100 &nbsp;|&nbsp; Saldo Inicial ECD &nbsp;|&nbsp; "
        f"<b style='color:#FF6B00;'>Thomson Reuters</b>&nbsp;|&nbsp; <small>{VERSAO}</small></p></div>",
        unsafe_allow_html=True
    )

    with st.sidebar:
        st.markdown("### ⚙ Configurações"); st.markdown("---")
        exibir_log = st.checkbox("Exibir log de processamento", value=True)
        st.markdown("---"); st.markdown(f"**Versão:** {VERSAO}")
        st.markdown("**Thomson Reuters — Domínio Sistemas**"); st.markdown("---")
        st.markdown("**Formatos suportados:**")
        st.markdown("- 📊 Excel (.xlsx / .xls)\n- 📄 TXT separado por `;`\n"
                    "- 📋 SPED ECD (.txt) — lançamentos\n- 📋 SPED ECD (.txt) — saldo inicial\n"
                    "- 📋 TXT Posicional Domínio")
        st.markdown("---")
        st.code("|0000|CNPJ|\n|6000|TIPO||||\n|6100|DATA|DEB|CRED|VALOR||HIST||FILIAL||\n|6110|CC_DEB|CC_CRED|VALOR|", language=None)
        st.markdown(f"**Limite:** {MAX_UPLOAD_MB} MB")

    # ── ABAS — existem sempre, independente de upload ─────────────────────────
    aba_conv, aba_i052 = st.tabs([
        "🔄 Conversor / Saldo Inicial",
        "🔍 Comparar I052 entre ECDs",
    ])

    # ═════════════════════════════════════════════════════════════════════════
    # ABA 2 — COMPARAÇÃO I052 (independente de upload principal)
    # ═════════════════════════════════════════════════════════════════════════
    with aba_i052:
        st.markdown("### 🔍 Comparação de I052 — ECD Anterior vs. ECD Atual")
        st.markdown(
            "<div class='info-box'>"
            "Suba os dois arquivos SPED ECD. O sistema irá:<br>"
            "① Extrair os <b>I052</b> (vínculos conta → COD_AGL) de cada arquivo<br>"
            "② Comparar o <b>saldo final</b> de cada COD_AGL no anterior com o "
            "<b>saldo inicial</b> no atual (regra <code>REGRA_VALIDA_BALANCO_SALDO_INI</code>)<br>"
            "③ Apontar contas que <b>mudaram de grupo</b> entre os dois arquivos"
            "</div>", unsafe_allow_html=True
        )

        col_u1, col_u2 = st.columns(2)
        with col_u1:
            st.markdown("**📁 Arquivo ECD — ANTERIOR (ano N-1)**")
            upload_ant = st.file_uploader(
                "ECD anterior", type=["txt"], key="upload_i052_ant",
                help="Arquivo SPED ECD do período anterior (ex: 2023)"
            )
        with col_u2:
            st.markdown("**📁 Arquivo ECD — ATUAL (ano N)**")
            upload_atu = st.file_uploader(
                "ECD atual", type=["txt"], key="upload_i052_atu",
                help="Arquivo SPED ECD do período atual (ex: 2024)"
            )

        btn_comparar = st.button(
            "🔍 COMPARAR I052",
            disabled=(upload_ant is None or upload_atu is None),
            type="primary", use_container_width=True, key="btn_comparar_i052"
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

            # Persiste no session_state para sobreviver ao rerun
            st.session_state["i052_resultado"]  = resultado_cmp
            st.session_state["i052_parsed_ant"] = parsed_ant
            st.session_state["i052_parsed_atu"] = parsed_atu
            st.session_state["i052_label_ant"]  = upload_ant.name
            st.session_state["i052_label_atu"]  = upload_atu.name
            st.session_state["i052_log"]        = log_cmp

        # Renderiza se já existe resultado salvo
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
                st.markdown(f"<div class='bloco-log'>{log_txt}</div>", unsafe_allow_html=True)

    # ═════════════════════════════════════════════════════════════════════════
    # ABA 1 — CONVERSOR / SALDO INICIAL
    # ═════════════════════════════════════════════════════════════════════════
    with aba_conv:

        st.markdown("#### 📂 Passo 1 — Selecionar Arquivo")
        uploaded = st.file_uploader(
            f"Arraste ou clique (Excel, TXT separado por ';', SPED ECD ou TXT Posicional — máx. {MAX_UPLOAD_MB} MB)",
            type=["xlsx", "xls", "xlsm", "txt", "csv"],
            key="upload_principal"
        )

        if uploaded is None:
            st.markdown(
                "<div class='info-box'>⬆ Selecione um arquivo para começar.</div>",
                unsafe_allow_html=True
            )
            # Aba sem arquivo: encerra aqui, sem st.stop() para não afetar aba_i052
            return

        # ── Leitura e detecção do arquivo ────────────────────────────────────
        conteudo = uploaded.read()
        mb = len(conteudo) / (1024 * 1024)
        if mb > MAX_UPLOAD_MB:
            st.error(f"⛔ Arquivo muito grande ({mb:.1f} MB). Limite: {MAX_UPLOAD_MB} MB.")
            return

        if conteudo != st.session_state.arquivo_bytes or uploaded.name != st.session_state.arquivo_nome:
            _reset()
            st.session_state.arquivo_bytes = conteudo
            st.session_state.arquivo_nome  = uploaded.name
            tipo = identificar_tipo(uploaded.name, conteudo)
            st.session_state.tipo_detectado = tipo
            if tipo == "excel":
                try:
                    xl = pd.ExcelFile(io.BytesIO(conteudo), engine="openpyxl")
                    st.session_state.sheets   = xl.sheet_names
                    st.session_state.sheet_sel = (
                        "Plan1" if "Plan1" in xl.sheet_names else xl.sheet_names[0]
                    )
                except:
                    st.session_state.sheets = []
            elif tipo == "ecd":
                cnpj_num = _pre_scan_cnpj_ecd(conteudo)
                st.session_state.cnpj_ecd     = cnpj_num
                st.session_state.cnpj_ecd_fmt = fmt_cnpj(cnpj_num) if cnpj_num else ""
                _pre_scan_conta_pl_sugerida(conteudo)
            elif tipo == "dominio_pos":
                filiais = _pre_scan_posicional(conteudo)
                st.session_state.filiais_detectadas = filiais

        tipo = st.session_state.tipo_detectado

        # ── Badge e info do arquivo ───────────────────────────────────────────
        badges = {
            "ecd":        "<span class='badge-ecd'>📋 SPED ECD</span>",
            "ecd_saldo":  "<span class='badge-si'>📥 SPED ECD — Saldo Inicial</span>",
            "excel":      "<span class='badge-excel'>📊 Excel</span>",
            "lote":       "<span class='badge-lote'>📄 TXT Lote (;)</span>",
            "dominio_pos":"<span class='badge-pos'>📋 TXT Posicional Domínio</span>",
        }
        mb_info = len(st.session_state.arquivo_bytes) / (1024 * 1024)
        st.markdown(
            f"{badges.get(tipo, '')} "
            f"<span style='color:#6B7A8D;font-size:13px;margin-left:12px;'>"
            f"{st.session_state.arquivo_nome} — {mb_info:.1f} MB</span>",
            unsafe_allow_html=True
        )
        st.markdown("")

        # ── Configuração Excel ────────────────────────────────────────────────
        sheet_sel = ""; linha_h = 3; auto_head = True
        if tipo == "excel" and st.session_state.sheets:
            st.markdown("#### 📋 Passo 2 — Configurar Excel")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                sheet_sel = st.selectbox(
                    "Aba (Sheet)", st.session_state.sheets,
                    index=(st.session_state.sheets.index(st.session_state.sheet_sel)
                           if st.session_state.sheet_sel in st.session_state.sheets else 0)
                )
                st.session_state.sheet_sel = sheet_sel
            with col2:
                auto_head = st.checkbox("Detectar cabeçalho automaticamente", value=True)
            with col3:
                if not auto_head:
                    linha_h = st.number_input("Linha do cabeçalho", min_value=1, max_value=50, value=4) - 1

        # ── CNPJ ─────────────────────────────────────────────────────────────
        ni = ""; ok_insc = False; ti = ""; inf = ""

        if tipo in ("ecd", "ecd_saldo"):
            st.markdown("#### 🏢 Passo 2 — CNPJ (preenchido automaticamente)")
            cnpj_ecd = st.session_state.cnpj_ecd
            if cnpj_ecd and validar_cnpj(cnpj_ecd):
                st.markdown(
                    f"<div class='cnpj-auto'>✔ CNPJ extraído: "
                    f"<span>{st.session_state.cnpj_ecd_fmt}</span></div>",
                    unsafe_allow_html=True
                )
                st.code(fmt_reg_0000(cnpj_ecd), language=None)
                ok_insc = True; ti = "CNPJ"; ni = cnpj_ecd; inf = st.session_state.cnpj_ecd_fmt
            else:
                st.warning("⚠ CNPJ não encontrado. Informe manualmente.")
                cnpj_raw = st.text_input("CNPJ / CPF", placeholder="00.000.000/0001-00",
                                         key="cnpj_manual_ecd")
                ok_insc, ti, ni = validar_inscricao(cnpj_raw)
                if cnpj_raw:
                    if ok_insc:
                        inf = fmt_cnpj(ni) if ti == "CNPJ" else fmt_cpf(ni)
                        st.success(f"✔ {ti} válido: {inf}")
                    else:
                        st.error("✖ CNPJ/CPF inválido")

            # ── Bloco Saldo Inicial ───────────────────────────────────────────
            st.markdown("---")
            st.markdown(
                "<div class='si-box'><b style='color:#FF9EBC;font-size:15px;'>📥 Módulo Saldo Inicial</b><br>"
                "<small style='color:#C8A0B8;'>Extrai o saldo final do SPED ECD e gera um único lançamento "
                "de saldo inicial no leiaute Domínio.</small></div>",
                unsafe_allow_html=True
            )

            col_si1, col_si2 = st.columns([1, 2])
            with col_si1:
                modo_saldo = st.checkbox(
                    "🔄 Gerar Saldo Inicial",
                    value=st.session_state.get("modo_saldo_inicial", False),
                    key="chk_saldo_inicial"
                )
                st.session_state.modo_saldo_inicial = modo_saldo
            with col_si2:
                hist_prefixo = st.text_input(
                    "Prefixo do histórico",
                    value=st.session_state.get("hist_prefixo_si", "SALDO INICIAL"),
                    max_chars=60, key="hist_prefixo_si_widget"
                )
                st.session_state.hist_prefixo_si = hist_prefixo

            if modo_saldo:
                st.markdown("##### Tratamento das contas de Resultado")
                modo_resultado = st.radio(
                    "Como tratar as contas de Resultado (I355)?",
                    options=["apenas_patrimonial", "aberto_com_resultado"],
                    format_func=lambda x: {
                        "apenas_patrimonial":   "✅ Apenas Patrimonial — Ativo/Passivo/PL (balanço fechado, sem resultado)",
                        "aberto_com_resultado": "📂 Aberto com Resultado — inclui Receitas/Despesas para encerrar no sistema destino",
                    }[x],
                    index=0 if st.session_state.get("modo_resultado_si", "apenas_patrimonial") == "apenas_patrimonial" else 1,
                    key="modo_resultado_si_widget"
                )
                st.session_state.modo_resultado_si = modo_resultado

                conta_pl = ""
                if modo_resultado == "aberto_com_resultado":
                    sugerida      = st.session_state.get("conta_pl_sugerida", "")
                    sugerida_nome = st.session_state.get("conta_pl_sugerida_nome", "")
                    if sugerida:
                        st.markdown(
                            f"<div class='si-box'>"
                            f"<b style='color:#FF9EBC;'>💡 Conta sugerida automaticamente:</b><br>"
                            f"<span style='color:#FFD166;font-size:18px;font-weight:700;'>{sugerida}</span>"
                            f"<span style='color:#9BB0C8;margin-left:12px;'>{sugerida_nome}</span><br>"
                            f"<small style='color:#9BB0C8;'>Detectada pelo COD_NAT/nome no I050 do SPED ECD.<br>"
                            f"Confirme se este é o código correto antes de processar.</small>"
                            f"</div>", unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            "<div class='card-warn'>⚠ <b style='color:#FFD166;'>Informe a conta de Superávit/Déficit do PL.</b><br>"
                            "<small>O sistema irá deduzir o resultado líquido do I355 desta conta para fechar o balanço (D=C).</small></div>",
                            unsafe_allow_html=True
                        )
                    conta_pl = st.text_input(
                        "Código da conta de Superávit/Déficit (PL)",
                        value=sugerida if sugerida else st.session_state.get("conta_pl_resultado_si", ""),
                        placeholder="Ex: 311010101",
                        key="conta_pl_resultado_si_widget"
                    )
                    st.session_state.conta_pl_resultado_si = conta_pl
                    if not conta_pl:
                        st.warning("⚠ Informe a conta de PL/Resultado para que o balanço feche corretamente.")
                    elif sugerida and conta_pl != sugerida:
                        st.info(f"ℹ Usando conta informada manualmente: {conta_pl} (sugestão era: {sugerida})")
                else:
                    conta_pl = ""
                    st.session_state.conta_pl_resultado_si = ""

                st.session_state.tipo_detectado = "ecd_saldo"
                tipo = "ecd_saldo"
            else:
                if st.session_state.tipo_detectado == "ecd_saldo" and not st.session_state.processado:
                    st.session_state.tipo_detectado = "ecd"
                    tipo = "ecd"

        else:
            st.markdown("#### 🏢 Passo 2 — Informar CNPJ / CPF")
            cnpj_raw = st.text_input(
                "CNPJ / CPF", placeholder="00.000.000/0001-00 ou 000.000.000-00",
                key="cnpj_lote"
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

        # ── Opções e conversão ────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### ⚙ Passo 3 — Opções e Conversão")
        col_op1, col_op2 = st.columns(2)
        with col_op1:
            gerar_6110 = st.checkbox(
                "Gerar registro 6110 (Centro de Custos)", value=False,
                disabled=(tipo not in ("ecd", "dominio_pos", "excel"))
            )
        with col_op2:
            usar_de_para = st.checkbox(
                "🏢 Habilitar De/Para de filiais", value=False,
                disabled=(tipo not in ("dominio_pos", "excel"))
            )

        mapa_filiais = {}
        if tipo == "dominio_pos" and usar_de_para:
            mapa_filiais = _widget_de_para_filiais(True, st.session_state.get("filiais_detectadas", []))
        elif tipo == "excel" and usar_de_para:
            filiais_excel = []
            if st.session_state.get("arquivo_bytes") and st.session_state.get("sheet_sel"):
                try:
                    sh_scan  = st.session_state.sheet_sel
                    lh_scan, _ = detectar_cabecalho_excel(st.session_state.arquivo_bytes, sh_scan)
                    df_scan, _ = ler_excel_lote(st.session_state.arquivo_bytes, sh_scan, lh_scan)
                    filiais_excel = _pre_scan_filiais_excel(df_scan)
                    del df_scan
                except:
                    filiais_excel = []
            mapa_filiais = _widget_de_para_filiais(True, filiais_excel)

        col_b1, col_b2 = st.columns([2, 1])
        with col_b1:
            btn_converter = st.button(
                "▶ CONVERTER", disabled=(not ok_insc),
                use_container_width=True, type="primary"
            )
        with col_b2:
            btn_limpar = st.button("🗑 Limpar tudo", use_container_width=True)

        if btn_limpar:
            _reset()
            st.rerun()

        if btn_converter and ok_insc:
            conteudo = st.session_state.arquivo_bytes
            log = []; crono = Cronometro(); crono.iniciar()
            status_txt = st.empty(); prog_bar = st.progress(0)
            try:
                # ── SALDO INICIAL ─────────────────────────────────────────────
                if tipo == "ecd_saldo":
                    crono.etapa("Saldo Inicial ECD")
                    log.append("── SALDO INICIAL — SPED ECD V3.6.2 ──")
                    resultado_bytes, metricas, todos_erros = processar_saldo_inicial_ecd(
                        conteudo, ni,
                        st.session_state.get("hist_prefixo_si", "SALDO INICIAL"),
                        st.session_state.get("modo_resultado_si", "apenas_patrimonial"),
                        st.session_state.get("conta_pl_resultado_si", ""),
                        log, prog_bar, status_txt
                    )
                    st.session_state.resultado_bytes = resultado_bytes
                    st.session_state.resultado_nome  = f"SALDO_INI_{ni}.txt"
                    st.session_state.metricas        = metricas
                    st.session_state.processado      = True
                    if todos_erros:
                        st.session_state.erros_bytes = _txt_erros_ecd(todos_erros, ni).encode("utf-8-sig")
                        st.session_state.erros_nome  = f"SALDO_INI_{ni}_erros.txt"
                    total_seg = crono.encerrar()
                    log.append(f"\n── TEMPO TOTAL: {Cronometro.fmt(total_seg)} ──")
                    for e in crono.etapas:
                        log.append(f"  {e['nome']}: {Cronometro.fmt(e['segundos'])}")
                    st.session_state.log_linhas = log

                # ── SPED ECD lançamentos ──────────────────────────────────────
                elif tipo == "ecd":
                    status_txt.text("Lendo SPED ECD...")
                    log.append("── LEITURA SPED ECD ──")
                    crono.etapa("Leitura SPED ECD"); prog_bar.progress(10)
                    ecd, registros_erro = _parse_ecd(conteudo, log)
                    if ecd is None:
                        st.error("Falha na leitura do SPED ECD.")
                        st.session_state.log_linhas = log
                    else:
                        prog_bar.progress(50)
                        status_txt.text("Gerando registros...")
                        crono.etapa("Geração dos registros")
                        log.append("\n── GERAÇÃO ──")
                        linhas_ecd = _gerar_ecd(ecd, log, prog_bar, status_txt)
                        if gerar_6110:
                            linhas_ecd = _injetar_6110_ecd(linhas_ecd)
                            n6110 = sum(1 for l in linhas_ecd if l.startswith("|6110|"))
                            log.append(f"  Reg. 6110 gerados  : {n6110:,}")
                        crono.etapa("Montagem do arquivo")
                        prog_bar.progress(90); status_txt.text("Montando arquivo...")
                        buf_out = io.StringIO()
                        for i in range(0, len(linhas_ecd), WRITE_CHUNK):
                            buf_out.write("\n".join(linhas_ecd[i:i+WRITE_CHUNK]) + "\n")
                        resultado_bytes = buf_out.getvalue().encode("utf-8-sig")
                        del buf_out, linhas_ecd; gc.collect()
                        st.session_state.resultado_bytes = resultado_bytes
                        st.session_state.resultado_nome  = f"ECD_{ni}_dominio.txt"
                        n6000   = resultado_bytes.count(b"|6000|")
                        n6100   = resultado_bytes.count(b"|6100|")
                        n6110_f = resultado_bytes.count(b"|6110|")
                        metricas = {
                            "CNPJ": ecd.cnpj,
                            "Lançamentos (I200)": f"{len(ecd.lancamentos):,}",
                            "Registros 6000": f"{n6000:,}",
                            "Registros 6100": f"{n6100:,}",
                            "Tamanho saída":  f"{len(resultado_bytes)/1024:.1f} KB",
                        }
                        if gerar_6110:
                            metricas["Registros 6110"] = f"{n6110_f:,}"
                        st.session_state.metricas = metricas
                        if registros_erro:
                            st.session_state.erros_bytes = _txt_erros_ecd(registros_erro, ecd.cnpj).encode("utf-8-sig")
                            st.session_state.erros_nome  = f"ECD_{ni}_erros.txt"
                        total_seg = crono.encerrar()
                        log.append(f"\n── TEMPO TOTAL: {Cronometro.fmt(total_seg)} ──")
                        for e in crono.etapas:
                            log.append(f"  {e['nome']}: {Cronometro.fmt(e['segundos'])}")
                        st.session_state.log_linhas = log
                        st.session_state.processado = True
                        prog_bar.progress(100); status_txt.text("Concluído!")

                # ── EXCEL ─────────────────────────────────────────────────────
                elif tipo == "excel":
                    crono.etapa("Leitura Excel")
                    status_txt.text("Lendo Excel..."); prog_bar.progress(8)
                    sh = st.session_state.sheet_sel
                    lh_det, _ = detectar_cabecalho_excel(conteudo, sh)
                    lh = lh_det if auto_head else linha_h
                    df, _ = ler_excel_lote(conteudo, sh, lh)
                    log.append(f"Excel — Aba: {sh} | Cabeçalho: linha {lh+1}")
                    log.append(f"Linhas carregadas: {len(df):,}"); prog_bar.progress(20)
                    crono.etapa("Montagem de lotes")
                    status_txt.text("Agrupando lotes...")
                    df, modo = montar_lotes_excel(df)
                    n_lotes = int(df["_num_lote"].max()) if len(df) > 0 else 0
                    log.append(f"Lotes detectados  : {n_lotes:,} [modo: {modo}]"); prog_bar.progress(35)
                    crono.etapa("Ordenação")
                    status_txt.text("Reordenando lotes...")
                    df = _ordenar_lotes_por_data_filial(df)
                    log.append(f"Lotes reordenados : {n_lotes:,}"); prog_bar.progress(50)
                    log.append(f"De/Para filiais   : {len(mapa_filiais)} regra(s)" if mapa_filiais else "De/Para filiais   : desabilitado")
                    log.append("Reg. 6110         : habilitado" if gerar_6110 else "Reg. 6110         : desabilitado")
                    crono.etapa("Processamento")
                    status_txt.text("Processando lotes...")
                    resultado_bytes, resumo, erros = processar_excel(df, ni, mapa_filiais, gerar_6110, log)
                    del df; gc.collect(); prog_bar.progress(85)
                    n_gravados = resultado_bytes.count(b"|6000|")
                    n6110_f    = resultado_bytes.count(b"|6110|")
                    st.session_state.resultado_bytes = resultado_bytes
                    st.session_state.resultado_nome  = "lancamentos.txt"
                    st.session_state.resumo          = resumo
                    st.session_state.erros_lote      = erros
                    crono.etapa("Log")
                    log_txt = _montar_log_lote(resumo, erros, ni, ti, inf, n_gravados, 0, "N/A (Excel)", crono)
                    st.session_state.log_bytes = log_txt.encode("utf-8-sig")
                    st.session_state.log_nome  = "log_conversao.txt"
                    total_seg = crono.encerrar()
                    log.append(f"\nTempo total: {Cronometro.fmt(total_seg)}")
                    metricas = {
                        "Lotes total": f"{len(resumo):,}",
                        "Lotes OK":    f"{len(resumo)-len(erros):,}",
                        "Lotes erro":  f"{len(erros):,}",
                        "Reg. gerados":f"{n_gravados:,}",
                        "Tamanho saída":f"{len(resultado_bytes)/1024:.1f} KB",
                    }
                    if gerar_6110:
                        metricas["Reg. 6110"] = f"{n6110_f:,}"
                    st.session_state.metricas    = metricas
                    st.session_state.log_linhas  = log
                    st.session_state.processado  = True
                    prog_bar.progress(100); status_txt.text("Concluído!")

                # ── TXT POSICIONAL ────────────────────────────────────────────
                elif tipo == "dominio_pos":
                    crono.etapa("Parse posicional")
                    log.append("── TXT POSICIONAL DOMÍNIO ──")
                    resultado_bytes, metricas, erros_parse, filiais_enc = processar_dominio_posicional(
                        conteudo, ni, gerar_6110, usar_de_para, mapa_filiais, log, prog_bar, status_txt
                    )
                    st.session_state.filiais_detectadas = filiais_enc
                    st.session_state.resultado_bytes    = resultado_bytes
                    st.session_state.resultado_nome     = f"DOM_POS_{ni}_dominio.txt"
                    st.session_state.metricas           = metricas
                    st.session_state.processado         = True
                    if erros_parse:
                        st.session_state.erros_bytes = _txt_erros_ecd(erros_parse, ni).encode("utf-8-sig")
                        st.session_state.erros_nome  = f"DOM_POS_{ni}_erros.txt"
                    total_seg = crono.encerrar()
                    log.append(f"\n── TEMPO TOTAL: {Cronometro.fmt(total_seg)} ──")
                    for e in crono.etapas:
                        log.append(f"  {e['nome']}: {Cronometro.fmt(e['segundos'])}")
                    st.session_state.log_linhas = log

                # ── TXT STREAMING ─────────────────────────────────────────────
                else:
                    crono.etapa("Streaming")
                    mb_txt = len(conteudo) / (1024 * 1024)
                    status_txt.text(f"Processando {mb_txt:.1f} MB..."); prog_bar.progress(5)
                    log.append(f"── TXT STREAMING — {mb_txt:.1f} MB ──")
                    resultado_bytes, resumo, erros, total_lins, ignoradas, enc_usado = processar_streaming(conteudo, ni, log)
                    prog_bar.progress(90)
                    n_gravados = resultado_bytes.count(b"|6000|")
                    st.session_state.resultado_bytes = resultado_bytes
                    st.session_state.resultado_nome  = "lancamentos.txt"
                    st.session_state.resumo          = resumo
                    st.session_state.erros_lote      = erros
                    crono.etapa("Log")
                    log_txt = _montar_log_lote(resumo, erros, ni, ti, inf, n_gravados, ignoradas, enc_usado, crono)
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
                    prog_bar.progress(100); status_txt.text("Concluído!")

            except Exception as ex:
                tb = traceback.format_exc()
                st.error(f"⛔ Erro inesperado: {ex}")
                log.append(f"ERRO FATAL: {ex}\n{tb}")
                st.session_state.log_linhas = log
                prog_bar.progress(0); status_txt.text("Falha.")

            st.rerun()

        # ── Renderização dos resultados ───────────────────────────────────────
        if st.session_state.processado:
            tipo_proc = st.session_state.tipo_detectado
            if   tipo_proc == "ecd_saldo":   _render_resultados_saldo_inicial(exibir_log)
            elif tipo_proc == "ecd":         _render_resultados_ecd(exibir_log)
            elif tipo_proc == "dominio_pos": _render_resultados_posicional(exibir_log)
            else:                            _render_resultados_lote(exibir_log)


if __name__ == "__main__":
    main()
