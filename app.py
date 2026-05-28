# -*- coding: utf-8 -*-
"""
Domínio Sistemas — Conversor Unificado (Streamlit)
Suporta:
  • Lançamentos Contábeis (TXT/Excel) → 0000 + 6000 + 6100
  • SPED ECD (.txt)                   → 0000 + 6000 + 6100
Identificação automática do tipo de arquivo no upload.
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

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════════════
VERSAO      = "V1.0"
CHUNK_SIZE  = 50_000
BUFFER_IO   = 8 * 1024 * 1024
WRITE_CHUNK = 10_000
TOL_VALOR   = 0.005

COLS_PADRAO = [
    "Data",
    "Cód. Conta Debito",
    "Cód. Conta Credito",
    "Valor",
    "Cód. Histórico",
    "Complemento Histórico",
    "Inicia Lote",
    "Código Matriz/Filial",
    "Centro de Custo Débito",
    "Centro de Custo Crédito",
]

# ═══════════════════════════════════════════════════════════════════════════════
# TEMA — Thomson Reuters
# ═══════════════════════════════════════════════════════════════════════════════
def apply_theme():
    st.markdown("""
    <style>
    html, body, [class*='css'] {
        font-family: 'Segoe UI', Arial, sans-serif;
        color: #E8ECF0;
    }
    .stApp { background-color: #0A0E1A; }
    h1, h2, h3 { color: #FF6B00; font-weight: 700; }
    section[data-testid='stSidebar'] {
        background-color: #0D1526;
        border-right: 2px solid #1A3050;
    }
    section[data-testid='stSidebar'] * { color: #E8ECF0 !important; }
    .stButton > button {
        background-color: #FF6B00; color: #fff;
        border: none; border-radius: 4px; font-weight: bold;
    }
    .stButton > button:hover { background-color: #CC5500; color: #fff; }
    .stDownloadButton > button {
        background-color: #FF6B00; color: #fff;
        border: none; border-radius: 4px; font-weight: bold;
    }
    .stDownloadButton > button:hover { background-color: #CC5500; }
    hr { border-color: #FF6B00; }
    [data-testid='metric-container'] {
        background-color: #102040;
        border-left: 4px solid #FF6B00;
        border-radius: 4px; padding: 10px;
    }
    .stProgress > div > div > div > div { background-color: #FF6B00 !important; }
    .bloco-log {
        background:#060B14; border:1px solid #1A3050; border-radius:6px;
        padding:14px; font-family:Consolas,monospace; font-size:12px;
        white-space:pre-wrap; max-height:520px; overflow-y:auto; color:#E8ECF0;
    }
    .badge-ecd   { color:#F472B6; font-weight:700; }
    .badge-excel { color:#00C896; font-weight:700; }
    .badge-lote  { color:#FFD166; font-weight:700; }
    .badge-erro  { color:#FF4444; font-weight:700; }
    .badge-ok    { color:#00C896; font-weight:700; }
    .header-box {
        background:#102040; padding:20px 24px 14px;
        border-radius:8px; border-top:5px solid #FF6B00;
        margin-bottom:20px;
    }
    </style>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CRONÔMETRO
# ═══════════════════════════════════════════════════════════════════════════════
class Cronometro:
    def __init__(self):
        self._inicio_total = 0.0
        self._etapas = []
        self._inicio_etapa = 0.0
        self._etapa_atual = ""

    def iniciar(self):
        self._inicio_total = time.perf_counter()
        self._etapas.clear()

    def etapa(self, nome):
        agora = time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({
                "nome": self._etapa_atual,
                "segundos": round(agora - self._inicio_etapa, 3),
            })
        self._etapa_atual  = nome
        self._inicio_etapa = agora

    def encerrar(self):
        agora = time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({
                "nome": self._etapa_atual,
                "segundos": round(agora - self._inicio_etapa, 3),
            })
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
# UTILITÁRIOS GERAIS
# ═══════════════════════════════════════════════════════════════════════════════
def sanitizar_texto(t):
    if not t: return ""
    return re.sub(r" {2,}", " ", t.replace("|", " ")).strip()

def limpar_int(v):
    try:    return str(int(float(str(v).strip())))
    except: return ""

def formatar_data(v):
    try:
        if isinstance(v, (datetime, pd.Timestamp)):
            return v.strftime("%d/%m/%Y")
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

# ── CNPJ / CPF ────────────────────────────────────────────────────────────────
def validar_cnpj(cnpj):
    c = so_nums(cnpj)
    if len(c) != 14 or len(set(c)) == 1: return False
    def d(c, p):
        s = sum(int(c[i]) * p[i] for i in range(len(p)))
        r = s % 11; return 0 if r < 2 else 11 - r
    return (int(c[12]) == d(c,[5,4,3,2,9,8,7,6,5,4,3,2]) and
            int(c[13]) == d(c,[6,5,4,3,2,9,8,7,6,5,4,3,2]))

def validar_cpf(cpf):
    c = so_nums(cpf)
    if len(c) != 11 or len(set(c)) == 1: return False
    def d(c, n):
        s = sum(int(c[i])*(n-i) for i in range(n-1))
        r = (s*10)%11; return 0 if r==10 else r
    return int(c[9])==d(c,10) and int(c[10])==d(c,11)

def validar_inscricao(v):
    n = so_nums(v)
    if len(n)==14 and validar_cnpj(n): return True, "CNPJ", n
    if len(n)==11 and validar_cpf(n):  return True, "CPF",  n
    return False, "", n

def fmt_cnpj(n):
    c = so_nums(n)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c)==14 else n

def fmt_cpf(n):
    c = so_nums(n)
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c)==11 else n

# ═══════════════════════════════════════════════════════════════════════════════
# FORMATAÇÃO DE REGISTROS DE SAÍDA
# ═══════════════════════════════════════════════════════════════════════════════
def fmt_reg_0000(ni): return f"|0000|{ni}|"
def fmt_reg_6000(tp): return f"|6000|{tp}||||"

def fmt_reg_6100(data, deb, cred, valor, cod_hist, desc, usuario, filial, scp):
    valor_fmt = f"{valor:.2f}".replace(".", ",")
    return (f"|6100|{data}|{deb}|{cred}|{valor_fmt}"
            f"|{cod_hist}|{sanitizar_texto(desc)}|{usuario}|{filial}|{scp}|")

# ═══════════════════════════════════════════════════════════════════════════════
# DETECÇÃO DE ENCODING
# ═══════════════════════════════════════════════════════════════════════════════
_CHARS_PT = set(
    "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞß"
    "àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿºª"
)

def _detectar_encoding_bytes(conteudo: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            texto = conteudo.decode(enc, errors="strict")
            if sum(1 for c in texto[:4096] if c in _CHARS_PT) > 0 \
               or enc in ("utf-8-sig","utf-8"):
                return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"

# ═══════════════════════════════════════════════════════════════════════════════
# IDENTIFICAÇÃO AUTOMÁTICA DO TIPO DE ARQUIVO
# ═══════════════════════════════════════════════════════════════════════════════
def identificar_tipo(nome_arquivo: str, conteudo: bytes) -> str:
    """
    Retorna 'ecd', 'excel' ou 'lote'.
    """
    ext = os.path.splitext(nome_arquivo)[1].lower()
    if ext in (".xlsx", ".xls", ".xlsm"):
        return "excel"

    enc = _detectar_encoding_bytes(conteudo)
    try:
        amostra = conteudo[:8192].decode(enc, errors="replace")
    except Exception:
        amostra = ""

    linhas = [l.strip() for l in amostra.splitlines() if l.strip()]
    for ln in linhas[:40]:
        if ln.startswith("|0000|") or ln.startswith("|I0"):
            return "ecd"
        campos = ln.split("|")
        if len(campos) >= 2 and campos[1] in (
            "0000","I010","I050","I075","I100","I150",
            "I155","I200","I250","I350","I355","I990",
        ):
            return "ecd"

    semis = sum(1 for ln in linhas[:20] if ";" in ln)
    if semis >= max(1, len(linhas[:20]) // 2):
        return "lote"
    return "lote"

# ═══════════════════════════════════════════════════════════════════════════════
# ▌▌▌ MÓDULO SPED ECD ▌▌▌
# ═══════════════════════════════════════════════════════════════════════════════
_MAPA_ESPECIAIS = {
    "\u2018":"'","\u2019":"'","\u201C":'"',"\u201D":'"',
    "\u2013":"-","\u2014":"-","\u2026":"...","\u00A0":" ",
    "\u00D7":"x","\u00F7":"/","\u20AC":"EUR","\u00A7":"S/",
    "\u00AE":"(R)","\u00A9":"(C)","\u2122":"(TM)",
}

def _norm_hist(texto):
    if not texto: return ""
    for o, d in _MAPA_ESPECIAIS.items(): texto = texto.replace(o, d)
    texto = unicodedata.normalize("NFC", texto)
    res = []
    for ch in texto:
        if ord(ch) < 0x20 and ord(ch) not in (9,10,13): continue
        try:    ch.encode("latin-1"); res.append(ch)
        except:
            base = unicodedata.normalize("NFD", ch)[0]
            try:    base.encode("latin-1"); res.append(base)
            except: pass
    return re.sub(r" {2,}", " ", "".join(res)).strip()[:250]

def _split_pipe(linha):
    c = linha.strip().split("|")
    if c and c[0]  == "": c = c[1:]
    if c and c[-1] == "": c = c[:-1]
    return c

def _conta_valida(conta): return bool(conta) and conta.isdigit()

class SpedECD:
    def __init__(self):
        self.cnpj=""; self.contas={}; self.historicos={}; self.lancamentos=[]

def _parse_ecd(conteudo: bytes, log: list) -> tuple:
    ecd = SpedECD(); lote_atual=None; erros_parse=0
    registros_erro=[]; contas_invalidas=0

    enc = _detectar_encoding_bytes(conteudo)
    log.append(f"  Encoding detectado: {enc}")
    try:
        texto = conteudo.decode(enc, errors="replace")
    except Exception:
        texto = conteudo.decode("utf-8", errors="replace")

    linhas = texto.splitlines()
    for num, linha in enumerate(linhas, 1):
        linha_orig = linha; linha = linha.strip()
        if not linha: continue
        campos = _split_pipe(linha)
        if not campos: continue
        reg = campos[0]
        try:
            if reg == "0000":
                if len(campos) > 5: ecd.cnpj = campos[5].strip()
            elif reg == "I050":
                if len(campos) > 7:
                    cod = campos[5].strip(); nome = campos[7].strip()
                    if cod: ecd.contas[cod] = nome
            elif reg == "I075":
                if len(campos) > 2:
                    ecd.historicos[campos[1].strip()] = _norm_hist(campos[2])
            elif reg == "I200":
                lote_atual = {
                    "num":  campos[1].strip() if len(campos)>1 else "",
                    "data": campos[2].strip() if len(campos)>2 else "",
                    "valor":campos[3].strip() if len(campos)>3 else "",
                    "partidas":[],
                }
                ecd.lancamentos.append(lote_atual)
            elif reg == "I250":
                if lote_atual is None: continue
                if len(campos) <= 4:
                    registros_erro.append({"linha":num,
                        "motivo":"I250 campos insuficientes",
                        "conteudo":linha_orig.strip()}); continue
                dc = campos[4].strip().upper()
                if dc not in ("D","C"):
                    registros_erro.append({"linha":num,
                        "motivo":f"dc='{dc}' inválido",
                        "conteudo":linha_orig.strip()}); continue
                conta = campos[1].strip()
                if not _conta_valida(conta):
                    registros_erro.append({"linha":num,
                        "motivo":f"Conta '{conta}' não numérica",
                        "conteudo":linha_orig.strip()})
                    contas_invalidas += 1; continue
                lote_atual["partidas"].append({
                    "conta": conta,
                    "valor": campos[3].strip(),
                    "dc":    dc,
                    "descr_hist": _norm_hist(campos[7] if len(campos)>7 else ""),
                })
            elif reg in ("I299","I300"):
                lote_atual = None
        except Exception as ex:
            registros_erro.append({"linha":num,
                "motivo":f"Exceção: {ex}","conteudo":linha_orig.strip()})
            erros_parse += 1
            if erros_parse > 50:
                log.append("ERRO: muitos erros — abortando."); return None, registros_erro

    if not ecd.cnpj:
        log.append("ERRO: CNPJ não encontrado."); return None, registros_erro

    log.append(f"  CNPJ: {ecd.cnpj}")
    log.append(f"  Contas: {len(ecd.contas):,} | Históricos: {len(ecd.historicos):,}")
    log.append(f"  Lançamentos (I200): {len(ecd.lancamentos):,}")
    if contas_invalidas:  log.append(f"  Contas inválidas ignoradas: {contas_invalidas:,}")
    if registros_erro:    log.append(f"  Linhas com aviso/erro: {len(registros_erro):,}")
    return ecd, registros_erro

def _fmt_data_ecd(d):
    d = d.strip()
    if "/" in d: return d
    if len(d)==8 and d.isdigit(): return f"{d[:2]}/{d[2:4]}/{d[4:]}"
    return d

def _fmt_valor_ecd(v):
    if isinstance(v, float): return f"{v:.2f}".replace(".",",")
    v = str(v).strip()
    if "." in v and "," not in v: v = v.replace(".",",")
    elif "." in v and "," in v:
        if v.index(".")<v.index(","): v=v.replace(".","").replace(",",".").replace(".",",")
    if "," not in v: v += ",00"
    else:
        p=v.split(",")
        if len(p[1])<2: p[1]=p[1].ljust(2,"0")
        v=",".join(p)
    return v

def _str2float(v):
    if isinstance(v,(int,float)): return float(v)
    v=str(v).strip()
    if "." in v and "," in v:
        if v.index(".")<v.index(","): v=v.replace(".","").replace(",",".")
        else: v=v.replace(",","")
    elif "," in v: v=v.replace(",",".")
    try:    return float(v)
    except: return 0.0

def _montar_hist(p): return p.get("descr_hist","").strip()

def _primeiro_hist(partidas):
    for p in partidas:
        h=_montar_hist(p)
        if h: return h
    return ""

def _agrupar(partidas):
    ag={}
    for p in partidas:
        chave=(p["conta"],p["dc"])
        if chave not in ag:
            ag[chave]={"conta":p["conta"],"valor":0.0,
                       "dc":p["dc"],"descr_hist":p.get("descr_hist","")}
        ag[chave]["valor"]+=_str2float(p["valor"])
        if not ag[chave]["descr_hist"] and p.get("descr_hist"):
            ag[chave]["descr_hist"]=p["descr_hist"]
    return list(ag.values())

def _classif(nd,nc):
    if nd==1 and nc==1: return "X"
    if nd==1 and nc>1:  return "D"
    if nc==1 and nd>1:  return "C"
    return "V"

def _linhas_ecd(lanc):
    partidas=_agrupar(lanc["partidas"])
    debs=[p for p in partidas if p["dc"]=="D"]
    creds=[p for p in partidas if p["dc"]=="C"]
    if not debs or not creds: return []
    data=_fmt_data_ecd(lanc["data"])
    tipo=_classif(len(debs),len(creds))
    hist=_primeiro_hist(lanc["partidas"])
    out=[fmt_reg_6000(tipo)]
    def h6(db,cr):
        val=_fmt_valor_ecd(db["valor"]); h=_montar_hist(db) or hist
        return f"|6100|{data}|{db['conta']}|{cr['conta']}|{val}||{h}|||||||"
    def hd(db):
        val=_fmt_valor_ecd(db["valor"]); h=_montar_hist(db) or hist
        return f"|6100|{data}|{db['conta']}||{val}||{h}|||||||"
    def hc(cr):
        val=_fmt_valor_ecd(cr["valor"]); h=_montar_hist(cr) or hist
        return f"|6100|{data}||{cr['conta']}|{val}||{h}|||||||"
    if   tipo=="X": out.append(h6(debs[0],creds[0]))
    elif tipo=="D": [out.append(hd(db)) for db in debs]; [out.append(hc(cr)) for cr in creds]
    elif tipo=="C": [out.append(hc(cr)) for cr in creds]; [out.append(hd(db)) for db in debs]
    else:           [out.append(hd(db)) for db in debs]; [out.append(hc(cr)) for cr in creds]
    return out

def _gerar_ecd(ecd, log, prog_bar, status):
    linhas=[fmt_reg_0000(re.sub(r"\D","",ecd.cnpj))]
    t6000=t6100=ignorados=0; debug={"X":0,"D":0,"C":0,"V":0}
    total=len(ecd.lancamentos)
    for idx,lanc in enumerate(ecd.lancamentos):
        if idx%500==0 or idx==total-1:
            prog_bar.progress(min(55+int(((idx+1)/total)*35),99))
            status.text(f"Gerando lançamento {idx+1:,}/{total:,}...")
        if not lanc.get("partidas"): ignorados+=1; continue
        novas=_linhas_ecd(lanc)
        if not novas: ignorados+=1; continue
        for l in novas:
            if l.startswith("|6000|"):
                t=l.split("|")[2] if len(l.split("|"))>2 else "?"
                debug[t]=debug.get(t,0)+1; t6000+=1
            elif l.startswith("|6100|"): t6100+=1
        linhas.extend(novas)
    log.append(f"  Registros 6000: {t6000:,} | 6100: {t6100:,} | Ignorados: {ignorados:,}")
    log.append(f"  Tipos — X:{debug['X']} D:{debug['D']} C:{debug['C']} V:{debug['V']}")
    log.append(f"  Total linhas  : {len(linhas):,}")
    return linhas

def _txt_erros_ecd(registros_erro, cnpj):
    linhas=["="*70,"RELATÓRIO DE ERROS — SPED ECD",
            f"CNPJ: {cnpj}",f"Total: {len(registros_erro)}","="*70,""]
    for i,r in enumerate(registros_erro,1):
        linhas+=[f"[{i:04d}] Linha : {r['linha']}",
                 f"       Motivo: {r['motivo']}",
                 f"       Conteúdo: {r['conteudo']}",""]
    linhas+=["="*70,"FIM DO RELATÓRIO"]
    return "\n".join(linhas)

# ═══════════════════════════════════════════════════════════════════════════════
# ▌▌▌ MÓDULO LANÇAMENTOS EM LOTE (TXT / EXCEL) ▌▌▌
# ═══════════════════════════════════════════════════════════════════════════════
def _filtrar_chunk(chunk):
    for c in COLS_PADRAO:
        if c not in chunk.columns: chunk[c]=""
    for c in COLS_PADRAO:
        chunk[c]=chunk[c].fillna("").astype(str).str.strip()
    il=chunk["Inicia Lote"].str.strip()
    chunk["Inicia Lote"]=il.where(il.str.fullmatch(r"[1-9]\d*"),"")
    m_data=chunk["Data"]!=""
    datas=pd.to_datetime(chunk.loc[m_data,"Data"],dayfirst=True,errors="coerce")
    m_dv=m_data.copy(); m_dv[m_data]=datas.notna()
    m_conta=((chunk["Cód. Conta Debito"]!="")|(chunk["Cód. Conta Credito"]!=""))
    m_valor=chunk["Valor"].str.strip()!=""
    return chunk[m_dv & m_conta & m_valor].copy()

def ler_txt_lote(conteudo: bytes) -> tuple:
    enc = _detectar_encoding_bytes(conteudo)
    texto = conteudo.decode(enc, errors="replace")
    buf = io.StringIO(texto)
    partes=[]; total=0; validas=0; linha_at=0
    reader=pd.read_csv(buf,sep=";",header=None,names=COLS_PADRAO,
                       dtype=str,on_bad_lines="skip",engine="python",
                       usecols=range(len(COLS_PADRAO)),chunksize=CHUNK_SIZE)
    for i,chunk in enumerate(reader):
        n=len(chunk)
        chunk["_linha_origem"]=np.arange(linha_at+1,linha_at+n+1,dtype=np.int32)
        linha_at+=n; total+=n
        filtrado=_filtrar_chunk(chunk); validas+=len(filtrado)
        if len(filtrado)>0: partes.append(filtrado)
        del chunk,filtrado
        if i%5==0: gc.collect()
    if not partes:
        raise ValueError("Nenhuma linha válida. Verifique o separador  ;  e a ordem das colunas.")
    df=pd.concat(partes,ignore_index=True,copy=False)
    del partes; gc.collect()
    return df, total-validas, enc

_COLS_ESP_LOW=[c.lower() for c in COLS_PADRAO[:8]]

def detectar_cabecalho_excel(conteudo: bytes, sheet: str) -> tuple:
    buf=io.BytesIO(conteudo)
    raw=pd.read_excel(buf,sheet_name=sheet,header=None,nrows=25,engine="openpyxl")
    pasta=None
    try:
        v=str(raw.iloc[1,6]).strip()
        if v and v.lower() not in ("nan","none",""): pasta=v
    except: pass
    for i,row in raw.iterrows():
        vals=[str(v).strip().lower() for v in row if not eh_vazio(v)]
        if sum(1 for c in _COLS_ESP_LOW if c in vals)>=4: return i,pasta
    return 3,pasta

def ler_excel_lote(conteudo: bytes, sheet: str, linha_h: int) -> tuple:
    buf=io.BytesIO(conteudo)
    raw=pd.read_excel(buf,sheet_name=sheet,header=None,dtype=str,engine="openpyxl")
    pasta="C:\\Temp"
    try:
        v=str(raw.iloc[1,6]).strip()
        if v and v.lower() not in ("nan","none",""): pasta=v
    except: pass
    while raw.shape[1]<len(COLS_PADRAO)+2: raw[raw.shape[1]]=""
    raw.columns=range(raw.shape[1])
    df=raw.iloc[linha_h+1:].reset_index(drop=True).copy()
    del raw; gc.collect()
    df.columns=list(range(df.shape[1]))
    df=df.rename(columns={i:c for i,c in enumerate(COLS_PADRAO)})
    _V={"nan","NaN","None","none",""}
    for c in COLS_PADRAO:
        if c in df.columns:
            df[c]=df[c].fillna("").astype(str).str.strip().replace(list(_V),"")
    mask=~((df["Data"]=="")&(df["Cód. Conta Debito"]=="")&
           (df["Cód. Conta Credito"]=="")&(df["Valor"]==""))
    df=df[mask].reset_index(drop=True).copy()
    df["_linha_origem"]=(df.index+linha_h+2).astype(np.int32)
    return df, pasta

def montar_lotes(df):
    R=df.copy()
    for col in COLS_PADRAO+["_linha_origem"]:
        if col not in R.columns: R[col]=""
    inicia=R["Inicia Lote"].fillna("").astype(str).str.strip()
    tem_ini=bool((inicia!="").any())
    if tem_ini:
        marcador=(inicia!="").to_numpy(dtype=bool)
        R["_num_lote"]=np.where(np.cumsum(marcador)>0,
                                np.cumsum(marcador,dtype=np.int32),np.int32(1))
    else:
        desc=(R["Complemento Histórico"].fillna("").astype(str).str.strip()
              .str.upper().str.replace(r"\s+"," ",regex=True))
        chave=(R["Data"].fillna("").astype(str).str.strip()+"|||"+desc).to_numpy()
        muda=np.empty(len(chave),dtype=bool); muda[0]=True; muda[1:]=chave[1:]!=chave[:-1]
        R["_num_lote"]=np.cumsum(muda,dtype=np.int32)
    return R, "Inicia Lote" if tem_ini else "Data + Descrição"

def tipo_lancamento(nd,nc):
    if nd==1 and nc==1: return "X"
    if nd==1 and nc>1:  return "D"
    if nd>1  and nc==1: return "C"
    return "V"

def diagnosticar_lote(g2, dif):
    debs=g2[g2["td"]].copy(); creds=g2[g2["tc"]].copy()
    td=round(float(debs["vf"].sum()),2); tc=round(float(creds["vf"].sum()),2)
    linhas_det=[]
    for _,r in g2.iterrows():
        linhas_det.append({"linha_origem":int(r["lo"]),"data":formatar_data(r["dt"]),
            "conta_debito":str(r["cd"]) if r["td"] else "",
            "conta_credito":str(r["cc"]) if r["tc"] else "",
            "valor":float(r["vf"]),"descricao":sanitizar_texto(str(r["desc"]))[:70],
            "tipo":"D" if r["td"] else "C"})
    suspeitas=[]; dif_abs=abs(dif)
    for r in linhas_det:
        if abs(r["valor"]-dif_abs)<TOL_VALOR:
            suspeitas.append({**r,"motivo":f"Valor R$ {r['valor']:.2f} igual à diferença"})
    if not suspeitas:
        for r in linhas_det:
            v=r["valor"]
            if r["tipo"]=="D":
                if abs(round(td-v,2)-tc)<TOL_VALOR:
                    suspeitas.append({**r,"motivo":f"Remover DÉBITO R$ {v:.2f} zeraria o lote"})
            else:
                if abs(td-round(tc-v,2))<TOL_VALOR:
                    suspeitas.append({**r,"motivo":f"Remover CRÉDITO R$ {v:.2f} zeraria o lote"})
    sugestao=(f"Débito excede crédito em R$ {dif_abs:.2f}." if td>tc
              else f"Crédito excede débito em R$ {dif_abs:.2f}.")
    return {"total_debito":td,"total_credito":tc,"diferenca":dif_abs,
            "qtd_debitos":len(debs),"qtd_creditos":len(creds),
            "linhas":linhas_det,"suspeitas":suspeitas,"sugestao":sugestao}

def _gerar_registros_lote(W_ok, cnt):
    mask_x=(cnt["nd"]==1)&(cnt["nc"]==1)
    lotes_x=cnt[mask_x].index; lotes_c=cnt[~mask_x].index
    if len(lotes_x)>0:
        Wd=(W_ok[W_ok["td"]&W_ok["nl"].isin(lotes_x)]
            [["nl","cd","vf","hist","desc","dt","fil"]].copy())
        Wc=(W_ok[W_ok["tc"]&W_ok["nl"].isin(lotes_x)][["nl","cc"]].copy())
        M=Wd.merge(Wc,on="nl",how="inner")
        for _,row in M.iterrows():
            data=formatar_data(row["dt"]); deb=str(row["cd"]); cred=str(row["cc"])
            valor=float(row["vf"])
            hist=limpar_int(row["hist"]) if str(row["hist"]).strip() not in ("","nan") else ""
            desc=str(row["desc"]).strip()
            fil=str(row["fil"]).strip() if str(row["fil"]).strip() not in ("","nan") else ""
            yield fmt_reg_6000("X")
            yield fmt_reg_6100(data,deb,cred,valor,hist,desc,"",fil,"")
        del Wd,Wc,M; gc.collect()
    if len(lotes_c)>0:
        Wcomp=W_ok[W_ok["nl"].isin(lotes_c)]
        for nl_c,g2 in Wcomp.groupby("nl",sort=False):
            nd=int(cnt.loc[nl_c,"nd"]) if nl_c in cnt.index else 0
            nc2=int(cnt.loc[nl_c,"nc"]) if nl_c in cnt.index else 0
            tp=tipo_lancamento(nd,nc2)
            yield fmt_reg_6000(tp)
            debs=g2[g2["td"]].reset_index(drop=True)
            creds=g2[g2["tc"]].reset_index(drop=True)
            if tp=="D":
                rd=debs.iloc[0]; data=formatar_data(rd["dt"])
                hist=limpar_int(rd["hist"]) if str(rd["hist"]).strip() not in ("","nan") else ""
                fil=str(rd["fil"]).strip() if str(rd["fil"]).strip() not in ("","nan") else ""
                for _,rc in creds.iterrows():
                    desc=str(rd["desc"]).strip() or str(rc["desc"]).strip()
                    yield fmt_reg_6100(data,str(rd["cd"]),str(rc["cc"]),float(rc["vf"]),hist,desc,"",fil,"")
            elif tp=="C":
                rc=creds.iloc[0]
                for _,rd in debs.iterrows():
                    data=formatar_data(rd["dt"])
                    hist=limpar_int(rd["hist"]) if str(rd["hist"]).strip() not in ("","nan") else ""
                    fil=str(rd["fil"]).strip() if str(rd["fil"]).strip() not in ("","nan") else ""
                    desc=str(rd["desc"]).strip() or str(rc["desc"]).strip()
                    yield fmt_reg_6100(data,str(rd["cd"]),str(rc["cc"]),float(rd["vf"]),hist,desc,"",fil,"")
            else:
                for _,rd in debs.iterrows():
                    data=formatar_data(rd["dt"])
                    hist=limpar_int(rd["hist"]) if str(rd["hist"]).strip() not in ("","nan") else ""
                    fil=str(rd["fil"]).strip() if str(rd["fil"]).strip() not in ("","nan") else ""
                    for _,rc in creds.iterrows():
                        desc=str(rd["desc"]).strip() or str(rc["desc"]).strip()
                        yield fmt_reg_6100(data,str(rd["cd"]),str(rc["cc"]),float(rc["vf"]),hist,desc,"",fil,"")

def processar_lote(df):
    v_float=limpar_valor_vec(df["Valor"])
    cd_arr=limpar_contas_vec(df["Cód. Conta Debito"])
    cc_arr=limpar_contas_vec(df["Cód. Conta Credito"])
    td_arr=cd_arr!=""; tc_arr=cc_arr!=""
    vd_arr=np.where(td_arr,v_float,0.0); vc_arr=np.where(tc_arr,v_float,0.0)
    nl_arr=df["_num_lote"].to_numpy(dtype=np.int32)
    lo_arr=df["_linha_origem"].fillna(0).astype(int).to_numpy(dtype=np.int32)
    dt_arr=df["Data"].fillna("").astype(str).to_numpy()
    desc_arr=np.array([sanitizar_texto(v) for v in
                       df["Complemento Histórico"].fillna("").astype(str).tolist()],dtype=object)
    hist_arr=df["Cód. Histórico"].fillna("").astype(str).to_numpy()
    fil_arr=(df["Código Matriz/Filial"].fillna("").astype(str).to_numpy()
             if "Código Matriz/Filial" in df.columns else np.full(len(df),"",dtype=object))
    W=pd.DataFrame({"nl":nl_arr,"lo":lo_arr,"vd":vd_arr,"vc":vc_arr,"vf":v_float,
                    "cd":cd_arr,"cc":cc_arr,"td":td_arr,"tc":tc_arr,"dt":dt_arr,
                    "desc":desc_arr,"hist":hist_arr,"fil":fil_arr})
    g=W.groupby("nl",sort=False)
    agg=g.agg(td=("vd","sum"),tc=("vc","sum"),qt=("nl","size"),
              dt=("dt","first"),ds=("desc","first"),
              lm=("lo","min"),lx=("lo","max")).reset_index()
    agg["td"]=agg["td"].round(2); agg["tc"]=agg["tc"].round(2)
    agg["dif"]=(agg["td"]-agg["tc"]).abs().round(2)
    agg["ok"]=agg["dif"]<TOL_VALOR
    erros_set=set(agg.loc[~agg["ok"],"nl"].tolist())
    ok_set=set(agg.loc[agg["ok"],"nl"].tolist())
    resumo=[]; erros=[]
    for r in agg.itertuples(index=False):
        lm=int(r.lm); lx=int(r.lx); fx=f"{lm}–{lx}" if lm!=lx else str(lm)
        e={"num_lote":r.nl,"data":formatar_data(r.dt),"descricao":str(r.ds or "").strip(),
           "total_debito":float(r.td),"total_credito":float(r.tc),
           "diferenca":float(r.dif),"balanceado":bool(r.ok),
           "qtd_linhas":int(r.qt),"faixa_linhas":fx,"diagnostico":{}}
        resumo.append(e)
        if not bool(r.ok): erros.append(e)
    if erros_set:
        W_err=W[W["nl"].isin(erros_set)]
        for nl_err,g2 in W_err.groupby("nl",sort=False):
            ent=next(x for x in erros if x["num_lote"]==nl_err)
            ent["diagnostico"]=diagnosticar_lote(g2,ent["diferenca"])
    W_ok=W[W["nl"].isin(ok_set)]
    cnt_d=W_ok[W_ok["td"]].groupby("nl",sort=False).size().rename("nd")
    cnt_c=W_ok[W_ok["tc"]].groupby("nl",sort=False).size().rename("nc")
    cnt=pd.concat([cnt_d,cnt_c],axis=1).fillna(0).astype(np.int16)
    gerador=_gerar_registros_lote(W_ok,cnt)
    return gerador, erros, resumo

def _montar_bytes_saida(ni, gerador) -> bytes:
    buf=io.StringIO()
    buf.write(fmt_reg_0000(ni)+"\n")
    bloco=[]; total=0
    for linha in gerador:
        bloco.append(linha); total+=1
        if len(bloco)>=WRITE_CHUNK:
            buf.write("\n".join(bloco)+"\n"); bloco.clear()
    if bloco: buf.write("\n".join(bloco)+"\n")
    return buf.getvalue().encode("utf-8-sig")

def _montar_bytes_ecd(linhas: list) -> bytes:
    buf=io.StringIO()
    for i in range(0,len(linhas),WRITE_CHUNK):
        buf.write("\n".join(linhas[i:i+WRITE_CHUNK])+"\n")
    return buf.getvalue().encode("utf-8-sig")

# ═══════════════════════════════════════════════════════════════════════════════
# RELATÓRIO DE LOG (LOTE)
# ═══════════════════════════════════════════════════════════════════════════════
def _montar_log_lote(resumo, erros, ni, ti, inf, n_gravados,
                     ignoradas, enc, crono: Cronometro) -> str:
    td=sum(v["total_debito"] for v in resumo)
    tc=sum(v["total_credito"] for v in resumo)
    ok=len(resumo)-len(erros)
    conc="SUCESSO" if not erros else f"ATENÇÃO — {len(erros)} lote(s) desbalanceado(s)"
    SEP="═"*90; sep2="─"*90
    L=[SEP,"  DOMÍNIO SISTEMAS  |  Thomson Reuters",
       "  LOG DE VALIDAÇÃO — LANÇAMENTOS CONTÁBEIS",SEP,
       f"  Data/Hora     : {ts_log()}",
       f"  Encoding leit.: {enc or 'N/A'}",
       f"  {ti:<6}         : {inf}",SEP,"",
       "  RESUMO GERAL",sep2,
       f"  Lotes total   : {len(resumo):>10,}",
       f"  Lotes OK      : {ok:>10,}",
       f"  Lotes ERRO    : {len(erros):>10,}",
       f"  Reg. 6000+6100: {n_gravados:>10,}",
       f"  Ignoradas     : {ignoradas:>10,}",
       f"  Total Déb.    : R$ {td:>14.2f}",
       f"  Total Créd.   : R$ {tc:>14.2f}",
       f"  Conclusão     : {conc}",""]
    if crono and crono.etapas:
        total_seg=sum(e["segundos"] for e in crono.etapas)
        L+=[sep2,"  RELATÓRIO DE TEMPO",sep2]
        for e in crono.etapas:
            L.append(f"  {'  '+e['nome']:<38} {Cronometro.fmt(e['segundos']):>8}")
        L+=["  "+"─"*46,f"  {'  TOTAL':<38} {Cronometro.fmt(total_seg):>8}",""]
    L+=[sep2,
        f"  {'Lote':<8}{'Linhas':<16}{'Data':<13}{'Qtd':<6}"
        f"{'Débito':>15}{'Crédito':>15}{'Diferença':>13}  Status",
        "  "+"─"*88]
    for v in resumo:
        L.append(f"  {str(v['num_lote']):<8}{v['faixa_linhas']:<16}"
                 f"{v['data']:<13}{str(v['qtd_linhas']):<6}"
                 f"R$ {v['total_debito']:>12.2f}  R$ {v['total_credito']:>12.2f}"
                 f"  R$ {v['diferenca']:>10.2f}   "
                 f"{'✔ OK' if v['balanceado'] else '✖ ERRO'}")
    L+=["  "+"─"*88,f"  {'TOTAIS':<37}R$ {td:>12.2f}  R$ {tc:>12.2f}",""]
    L+=[SEP,f"  Fim  │  {ts_log()}",f"  Resultado │  {conc}",SEP]
    return "\n".join(L)

# ═══════════════════════════════════════════════════════════════════════════════
# INTERFACE STREAMLIT
# ═══════════════════════════════════════════════════════════════════════════════
def _init_state():
    defaults = {
        "resultado_bytes":  None,
        "resultado_nome":   "saida.txt",
        "erros_bytes":      None,
        "erros_nome":       "erros.txt",
        "log_bytes":        None,
        "log_nome":         "log.txt",
        "log_linhas":       [],
        "resumo":           [],
        "erros_lote":       [],
        "metricas":         {},
        "tipo_detectado":   None,
        "sheets":           [],
        "sheet_sel":        "",
        "arquivo_bytes":    None,
        "arquivo_nome":     "",
        "processado":       False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def _reset():
    keys = ["resultado_bytes","resultado_nome","erros_bytes","erros_nome",
            "log_bytes","log_nome","log_linhas","resumo","erros_lote",
            "metricas","tipo_detectado","sheets","sheet_sel",
            "arquivo_bytes","arquivo_nome","processado"]
    for k in keys:
        st.session_state[k] = ([] if k in ("log_linhas","resumo","erros_lote","sheets")
                                else {} if k=="metricas"
                                else None if k.endswith("_bytes")
                                else False if k=="processado"
                                else "")

def main():
    st.set_page_config(
        page_title="Domínio Sistemas | Thomson Reuters",
        page_icon="🟠", layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_theme()
    _init_state()

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        "<div class='header-box'>"
        "<h2 style='color:#FF6B00;margin:0;'>Domínio Sistemas — Conversor Unificado</h2>"
        "<p style='color:#6B7A8D;margin:6px 0 0;'>"
        "Lançamentos Contábeis (TXT/Excel) &nbsp;|&nbsp; SPED ECD &nbsp;→&nbsp; "
        "0000 + 6000 + 6100 &nbsp;|&nbsp; "
        "<b style='color:#FF6B00;'>Thomson Reuters</b></p>"
        "</div>", unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙ Configurações")
        st.markdown("---")
        cnpj_raw = st.text_input("CNPJ / CPF", placeholder="00.000.000/0001-00",
                                  help="Informe o CNPJ (14 dígitos) ou CPF (11 dígitos).")
        ok_insc, ti, ni = validar_inscricao(cnpj_raw)
        if cnpj_raw:
            if ok_insc:
                inf = fmt_cnpj(ni) if ti=="CNPJ" else fmt_cpf(ni)
                st.success(f"✔ {ti} válido: {inf}")
                st.code(fmt_reg_0000(ni), language=None)
            else:
                st.error("✖ CNPJ/CPF inválido")
                inf = ""
        else:
            inf = ""

        st.markdown("---")
        exibir_log = st.checkbox("Exibir log de processamento", value=False)
        st.markdown("---")
        st.markdown("### Versões")
        st.markdown("**V1.0** — Conversor Unificado")
        st.markdown("---")
        st.markdown("**Formatos suportados:**")
        st.markdown("- 📊 Excel (.xlsx/.xls)")
        st.markdown("- 📄 TXT separado por `;`")
        st.markdown("- 📋 SPED ECD (.txt)")

    # ── Upload ────────────────────────────────────────────────────────────────
    st.markdown("#### 📂 Selecionar Arquivo")
    uploaded = st.file_uploader(
        "Arraste ou clique para selecionar",
        type=["xlsx","xls","xlsm","txt","csv"],
        label_visibility="collapsed",
    )

    if uploaded is not None:
        conteudo = uploaded.read()
        if (conteudo != st.session_state.arquivo_bytes or
                uploaded.name != st.session_state.arquivo_nome):
            _reset()
            st.session_state.arquivo_bytes = conteudo
            st.session_state.arquivo_nome  = uploaded.name
            tipo = identificar_tipo(uploaded.name, conteudo)
            st.session_state.tipo_detectado = tipo
            # Detectar sheets se Excel
            if tipo == "excel":
                try:
                    xl = pd.ExcelFile(io.BytesIO(conteudo), engine="openpyxl")
                    st.session_state.sheets = xl.sheet_names
                    st.session_state.sheet_sel = (
                        "Plan1" if "Plan1" in xl.sheet_names else xl.sheet_names[0])
                except Exception:
                    st.session_state.sheets = []

    # ── Badge tipo detectado ──────────────────────────────────────────────────
    if st.session_state.tipo_detectado:
        tipo = st.session_state.tipo_detectado
        badges = {
            "ecd":   ("<span class='badge-ecd'>📋 SPED ECD detectado</span>", "ECD"),
            "excel": ("<span class='badge-excel'>📊 Excel — Lançamentos em Lote</span>", "Excel"),
            "lote":  ("<span class='badge-lote'>📄 TXT — Lançamentos em Lote</span>", "TXT"),
        }
        badge_html, _ = badges.get(tipo, ("", ""))
        st.markdown(badge_html, unsafe_allow_html=True)

    # ── Opções específicas por tipo ───────────────────────────────────────────
    sheet_sel  = ""
    linha_h    = 3
    auto_head  = True

    if st.session_state.tipo_detectado == "excel" and st.session_state.sheets:
        col1, col2, col3 = st.columns([2,1,1])
        with col1:
            sheet_sel = st.selectbox("Aba (Sheet)", st.session_state.sheets,
                index=st.session_state.sheets.index(st.session_state.sheet_sel)
                      if st.session_state.sheet_sel in st.session_state.sheets else 0)
            st.session_state.sheet_sel = sheet_sel
        with col2:
            auto_head = st.checkbox("Detectar cabeçalho automaticamente", value=True)
        with col3:
            if not auto_head:
                linha_h = st.number_input("Linha do cabeçalho", min_value=1,
                                          max_value=50, value=4) - 1
            else:
                linha_h = 3

    # ── Opções gerais ─────────────────────────────────────────────────────────
    col_op1, col_op2 = st.columns(2)
    with col_op1:
        gerar_6110 = st.checkbox(
            "Gerar registro 6110 (apenas SPED ECD)",
            value=False,
            help="Gera linha analítica 6110 após cada 6100 (somente para SPED ECD).")
    with col_op2:
        st.markdown("")   # espaçador

    st.markdown("---")

    # ── Botões ────────────────────────────────────────────────────────────────
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        btn_converter = st.button(
            "▶ CONVERTER",
            disabled=(st.session_state.arquivo_bytes is None or not ok_insc),
            use_container_width=True, type="primary")
    with col_b2:
        btn_limpar = st.button("🗑 Limpar", use_container_width=True)

    if btn_limpar:
        _reset(); st.rerun()

    # ── CONVERSÃO ─────────────────────────────────────────────────────────────
    if btn_converter and st.session_state.arquivo_bytes and ok_insc:
        conteudo = st.session_state.arquivo_bytes
        nome     = st.session_state.arquivo_nome
        tipo     = st.session_state.tipo_detectado
        log      = []
        crono    = Cronometro(); crono.iniciar()

        status_txt  = st.empty()
        prog_bar    = st.progress(0)

        try:
            # ══════════════════════════════════════════════════════════════════
            # FLUXO SPED ECD
            # ══════════════════════════════════════════════════════════════════
            if tipo == "ecd":
                status_txt.text("Lendo SPED ECD...")
                log.append("── LEITURA SPED ECD ──")
                crono.etapa("Leitura SPED ECD")
                prog_bar.progress(10)

                ecd, registros_erro = _parse_ecd(conteudo, log)
                if ecd is None:
                    st.error("Falha na leitura do SPED ECD. Verifique o log.")
                    st.session_state.log_linhas = log
                else:
                    cnpj_final = ni if ni else re.sub(r"\D","",ecd.cnpj)
                    prog_bar.progress(50)
                    status_txt.text("Gerando registros...")
                    crono.etapa("Geração dos registros")
                    log.append("\n── GERAÇÃO ──")

                    linhas_ecd = _gerar_ecd(ecd, log, prog_bar, status_txt)

                    # Opcional: 6110
                    if gerar_6110:
                        linhas_com_6110 = []
                        for l in linhas_ecd:
                            linhas_com_6110.append(l)
                            if l.startswith("|6100|"):
                                campos = l.split("|")
                                if len(campos) >= 6:
                                    data_l  = campos[2]
                                    deb_l   = campos[3]
                                    cred_l  = campos[4]
                                    valor_l = campos[5]
                                    hist_l  = campos[7] if len(campos)>7 else ""
                                    if deb_l:
                                        linhas_com_6110.append(
                                            f"|6110|{data_l}|{deb_l}|{valor_l}|D||{hist_l}|||||||")
                                    if cred_l:
                                        linhas_com_6110.append(
                                            f"|6110|{data_l}|{cred_l}|{valor_l}|C||{hist_l}|||||||")
                        linhas_ecd = linhas_com_6110

                    crono.etapa("Geração do arquivo")
                    prog_bar.progress(90)
                    status_txt.text("Montando arquivo...")

                    resultado_bytes = _montar_bytes_ecd(linhas_ecd)
                    nome_saida = f"ECD_{re.sub(chr(92)+'D','',ecd.cnpj)}_dominio.txt"

                    st.session_state.resultado_bytes = resultado_bytes
                    st.session_state.resultado_nome  = nome_saida
                    st.session_state.metricas = {
                        "CNPJ": ecd.cnpj,
                        "Lançamentos (I200)": f"{len(ecd.lancamentos):,}",
                        "Registros 6000": sum(1 for l in linhas_ecd if l.startswith("|6000|")),
                        "Registros 6100": sum(1 for l in linhas_ecd if l.startswith("|6100|")),
                        "Total linhas":   len(linhas_ecd),
                    }

                    if registros_erro:
                        erros_txt = _txt_erros_ecd(registros_erro, ecd.cnpj)
                        st.session_state.erros_bytes = erros_txt.encode("utf-8-sig")
                        st.session_state.erros_nome  = (
                            f"ECD_{re.sub(chr(92)+'D','',ecd.cnpj)}_erros.txt")

                    total_seg = crono.encerrar()
                    log.append(f"\n── TEMPO TOTAL: {Cronometro.fmt(total_seg)} ──")
                    for e in crono.etapas:
                        log.append(f"  {e['nome']}: {Cronometro.fmt(e['segundos'])}")
                    st.session_state.log_linhas  = log
                    st.session_state.processado  = True
                    prog_bar.progress(100)
                    status_txt.text("Concluído!")

            # ══════════════════════════════════════════════════════════════════
            # FLUXO LANÇAMENTOS EM LOTE (TXT / EXCEL)
            # ══════════════════════════════════════════════════════════════════
            else:
                crono.etapa("Leitura do arquivo")
                ignoradas = 0; enc_usado = ""

                if tipo == "excel":
                    status_txt.text("Lendo Excel...")
                    prog_bar.progress(8)
                    sh = st.session_state.sheet_sel
                    lh_det, _ = detectar_cabecalho_excel(conteudo, sh)
                    lh = lh_det if auto_head else linha_h
                    df, _ = ler_excel_lote(conteudo, sh, lh)
                    enc_usado = "N/A (Excel)"
                    log.append(f"Excel — Aba: {sh} | Cabeçalho: linha {lh+1}")
                else:
                    status_txt.text("Lendo TXT...")
                    prog_bar.progress(5)
                    df, ignoradas, enc_usado = ler_txt_lote(conteudo)
                    log.append(f"TXT | Encoding: {enc_usado} | Ignoradas: {ignoradas:,}")

                prog_bar.progress(30)
                log.append(f"Linhas carregadas: {len(df):,}")

                crono.etapa("Montagem de lotes")
                status_txt.text("Montando lotes...")
                df, modo = montar_lotes(df)
                n_lotes = int(df["_num_lote"].max()) if len(df)>0 else 0
                log.append(f"Lotes: {n_lotes:,} [modo: {modo}]")
                prog_bar.progress(42)

                crono.etapa("Processamento / validação")
                status_txt.text("Validando lotes...")
                gerador, erros, resumo = processar_lote(df)
                del df; gc.collect()
                prog_bar.progress(70)

                st.session_state.resumo     = resumo
                st.session_state.erros_lote = erros
                n_ok = len(resumo)-len(erros)
                log.append(f"Lotes OK: {n_ok:,} | Erros: {len(erros):,}")

                crono.etapa("Geração do arquivo")
                n_gravados = 0
                if any(v["balanceado"] for v in resumo):
                    status_txt.text("Gerando arquivo...")
                    resultado_bytes = _montar_bytes_saida(ni, gerador)
                    n_gravados = resultado_bytes.count(b"|6000|")
                    st.session_state.resultado_bytes = resultado_bytes
                    st.session_state.resultado_nome  = "lancamentos.txt"
                    log.append(f"Registros gravados: {n_gravados:,}")
                prog_bar.progress(90)

                crono.etapa("Geração do log")
                total_seg = crono.encerrar()
                log_txt = _montar_log_lote(resumo, erros, ni, ti, inf,
                                           n_gravados, ignoradas, enc_usado, crono)
                st.session_state.log_bytes  = log_txt.encode("utf-8-sig")
                st.session_state.log_nome   = "log_conversao.txt"
                log.append(f"\nTempo total: {Cronometro.fmt(total_seg)}")
                for e in crono.etapas:
                    log.append(f"  {e['nome']}: {Cronometro.fmt(e['segundos'])}")

                st.session_state.metricas = {
                    "Lotes total":  f"{len(resumo):,}",
                    "Lotes OK":     f"{n_ok:,}",
                    "Lotes erro":   f"{len(erros):,}",
                    "Reg. gerados": f"{n_gravados:,}",
                    "Ignoradas":    f"{ignoradas:,}",
                }
                st.session_state.log_linhas = log
                st.session_state.processado = True
                prog_bar.progress(100)
                status_txt.text("Concluído!")

        except Exception as ex:
            tb = traceback.format_exc()
            st.error(f"⛔ Erro: {ex}")
            log.append(f"ERRO FATAL: {ex}\n{tb}")
            st.session_state.log_linhas = log
            prog_bar.progress(0)
            status_txt.text("Falha.")

        st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # RESULTADOS
    # ══════════════════════════════════════════════════════════════════════════
    if st.session_state.processado:

        # ── Métricas ──────────────────────────────────────────────────────────
        if st.session_state.metricas:
            st.markdown("#### 📊 Resumo")
            cols = st.columns(len(st.session_state.metricas))
            for i,(k,v) in enumerate(st.session_state.metricas.items()):
                cols[i].metric(k, v)

        # ── Tabela de validação (lote) ─────────────────────────────────────────
        if st.session_state.resumo:
            st.markdown("#### ✅ Validação dos Lotes")
            resumo = st.session_state.resumo
            rows = []
            for v in resumo:
                rows.append({
                    "Lote":      v["num_lote"],
                    "Linhas":    v["faixa_linhas"],
                    "Data":      v["data"],
                    "Débito":    f"R$ {v['total_debito']:.2f}",
                    "Crédito":   f"R$ {v['total_credito']:.2f}",
                    "Diferença": f"R$ {v['diferenca']:.2f}",
                    "Status":    "✔ OK" if v["balanceado"] else "✖ ERRO",
                })
            df_res = pd.DataFrame(rows)
            st.dataframe(df_res, use_container_width=True, hide_index=True)

            # Diagnóstico de erros
            erros = st.session_state.erros_lote
            if erros:
                st.markdown("#### ⚠ Diagnóstico dos Lotes com Erro")
                for e in erros:
                    with st.expander(
                        f"Lote {e['num_lote']} — Linhas {e['faixa_linhas']} "
                        f"— Diferença R$ {e['diferenca']:.2f}", expanded=False):
                        diag = e.get("diagnostico",{})
                        st.markdown(f"**Sugestão:** {diag.get('sugestao','')}")
                        suspeitas = diag.get("suspeitas",[])
                        if suspeitas:
                            st.markdown("**⚡ Linhas suspeitas:**")
                            for s in suspeitas:
                                tp = "DÉBITO" if s["tipo"]=="D" else "CRÉDITO"
                                cta = s["conta_debito"] or s["conta_credito"]
                                st.markdown(
                                    f"- Ln `{s['linha_origem']}` {tp} "
                                    f"Conta `{cta}` R$ `{s['valor']:.2f}` — {s['motivo']}")
                        linhas_det = diag.get("linhas",[])
                        if linhas_det:
                            df_det = pd.DataFrame(linhas_det)[
                                ["linha_origem","tipo","conta_debito",
                                 "conta_credito","valor","descricao"]]
                            st.dataframe(df_det, use_container_width=True, hide_index=True)

        # ── Downloads ─────────────────────────────────────────────────────────
        st.markdown("#### ⬇ Downloads")
        dl1, dl2, dl3 = st.columns(3)

        with dl1:
            if st.session_state.resultado_bytes:
                st.success("Arquivo gerado!")
                st.download_button(
                    "⬇ Baixar arquivo convertido",
                    data=st.session_state.resultado_bytes,
                    file_name=st.session_state.resultado_nome,
                    mime="text/plain", use_container_width=True, type="primary")

        with dl2:
            if st.session_state.erros_bytes:
                st.warning("Há linhas com erro.")
                st.download_button(
                    "⬇ Baixar relatório de erros",
                    data=st.session_state.erros_bytes,
                    file_name=st.session_state.erros_nome,
                    mime="text/plain", use_container_width=True)

        with dl3:
            if st.session_state.log_bytes:
                st.download_button(
                    "⬇ Baixar log completo",
                    data=st.session_state.log_bytes,
                    file_name=st.session_state.log_nome,
                    mime="text/plain", use_container_width=True)

        # ── Log no console ────────────────────────────────────────────────────
        if exibir_log and st.session_state.log_linhas:
            st.markdown("#### 🖥 Log de Processamento")
            log_txt = "\n".join(str(l) for l in st.session_state.log_linhas)
            tem_erro = any("ERRO" in str(l).upper()
                           for l in st.session_state.log_linhas)
            cor = "#FF4444" if tem_erro else "#1A3050"
            st.markdown(
                f"<div class='bloco-log' style='border-color:{cor};'>"
                f"{log_txt}</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
