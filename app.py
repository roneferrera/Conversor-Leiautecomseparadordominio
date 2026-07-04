# ═══════════════════════════════════════════════════════════════════════════════
# -*- coding: utf-8 -*-
"""
Domínio Sistemas — Conversor Unificado (Streamlit) V1.8
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

VERSAO        = "V1.8"
CHUNK_SIZE    = 100_000
WRITE_CHUNK   = 5_000
TOL_VALOR     = 0.005
MAX_UPLOAD_MB = 200

COLS_PADRAO = [
    "Data", "Cód. Conta Debito", "Cód. Conta Credito", "Valor",
    "Cód. Histórico", "Complemento Histórico", "Inicia Lote",
    "Código Matriz/Filial", "Centro de Custo Débito", "Centro de Custo Crédito",
]

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
    .header-box{background:#102040;padding:20px 24px 14px;border-radius:8px;
                border-top:5px solid #FF6B00;margin-bottom:20px;}
    .cnpj-box{background:#0D1526;border:1px solid #1A3050;border-radius:8px;
              padding:16px 20px;margin:10px 0 16px 0;}
    .cnpj-auto{background:#0a2e1a;border:1px solid #00C896;border-radius:8px;
               padding:12px 18px;margin:10px 0 16px 0;color:#00C896;font-weight:700;}
    .cnpj-auto span{color:#FFD166;}
    .info-box{background:#102040;border-left:4px solid #FF6B00;border-radius:4px;
              padding:12px 16px;margin:8px 0;font-size:13px;}
    .card-ok{background:#0a2e1a;border:2px solid #00C896;border-radius:10px;padding:18px 24px;margin:12px 0;}
    .card-err{background:#2e0a0a;border:2px solid #FF4444;border-radius:10px;padding:18px 24px;margin:12px 0;}
    .card-warn{background:#1a1000;border-left:4px solid #FFD166;border-radius:4px;padding:10px 16px;margin:8px 0;}
    </style>
    """, unsafe_allow_html=True)

class Cronometro:
    def __init__(self):
        self._inicio_total=0.0; self._etapas=[]; self._inicio_etapa=0.0; self._etapa_atual=""
    def iniciar(self):
        self._inicio_total=time.perf_counter(); self._etapas.clear()
    def etapa(self,nome):
        agora=time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({"nome":self._etapa_atual,"segundos":round(agora-self._inicio_etapa,3)})
        self._etapa_atual=nome; self._inicio_etapa=agora
    def encerrar(self):
        agora=time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({"nome":self._etapa_atual,"segundos":round(agora-self._inicio_etapa,3)})
            self._etapa_atual=""
        return round(agora-self._inicio_total,3)
    @staticmethod
    def fmt(s):
        if s<0.001: return "<1ms"
        if s<1: return f"{s*1000:.0f}ms"
        if s<60: return f"{s:.2f}s"
        m=int(s//60); return f"{m}min {s%60:.1f}s"
    @property
    def etapas(self): return self._etapas

_MAPA_ESPECIAIS={
    "\u2018":"'","\u2019":"'","\u201C":'"',"\u201D":'"',
    "\u2013":"-","\u2014":"-","\u2026":"...","\u00A0":" ",
    "\u00D7":"x","\u00F7":"/","\u20AC":"EUR","\u00A7":"S/",
    "\u00AE":"(R)","\u00A9":"(C)","\u2122":"(TM)",
}

def _norm_hist(texto:str)->str:
    if not texto: return ""
    for o,d in _MAPA_ESPECIAIS.items(): texto=texto.replace(o,d)
    texto=unicodedata.normalize("NFC",texto)
    res=[]
    for ch in texto:
        if ord(ch)<0x20 and ord(ch) not in (9,10,13): continue
        if ch=="|": res.append(" "); continue
        try: ch.encode("latin-1"); res.append(ch)
        except UnicodeEncodeError:
            base=unicodedata.normalize("NFD",ch)[0]
            try: base.encode("latin-1"); res.append(base)
            except UnicodeEncodeError: pass
    return re.sub(r" {2,}"," ","".join(res)).strip()[:250]

def sanitizar_texto(t:str)->str: return _norm_hist(str(t) if t else "")
def formatar_data(v):
    try:
        if isinstance(v,(datetime,pd.Timestamp)): return v.strftime("%d/%m/%Y")
        return pd.to_datetime(v,dayfirst=True).strftime("%d/%m/%Y")
    except: return str(v)
def eh_vazio(v):
    if v is None: return True
    try:
        if pd.isna(v): return True
    except: pass
    return str(v).strip() in ("","nan","NaN","None")
def ts_log(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def so_nums(v): return re.sub(r"\D","",str(v))

_VAZIO_CONTA=frozenset(("","nan","none","0","0.0"))

def limpar_contas_vec(serie):
    arr=serie.fillna("").astype(str).str.strip().str.lower().to_numpy()
    out=np.where(np.isin(arr,list(_VAZIO_CONTA)),"",arr)
    mask=out!=""
    if mask.any():
        vals=out[mask]; conv=np.empty(len(vals),dtype=object)
        for i,v in enumerate(vals):
            try: conv[i]=str(int(float(v.replace(",","."))))
            except: conv[i]=v
        out[mask]=conv
    return out

def limpar_valor_vec(serie):
    return (pd.to_numeric(
        serie.fillna("0").astype(str).str.strip()
             .str.replace(",",".",regex=False)
             .str.replace(r"[^\d.\-]","",regex=True),
        errors="coerce").fillna(0.0).round(2).to_numpy(dtype=np.float64))

def validar_cnpj(cnpj):
    c=so_nums(cnpj)
    if len(c)!=14 or len(set(c))==1: return False
    def d(c,p):
        s=sum(int(c[i])*p[i] for i in range(len(p))); r=s%11; return 0 if r<2 else 11-r
    return (int(c[12])==d(c,[5,4,3,2,9,8,7,6,5,4,3,2]) and
            int(c[13])==d(c,[6,5,4,3,2,9,8,7,6,5,4,3,2]))

def validar_cpf(cpf):
    c=so_nums(cpf)
    if len(c)!=11 or len(set(c))==1: return False
    def d(c,n):
        s=sum(int(c[i])*(n-i) for i in range(n-1)); r=(s*10)%11; return 0 if r==10 else r
    return int(c[9])==d(c,10) and int(c[10])==d(c,11)

def validar_inscricao(v):
    n=so_nums(v)
    if len(n)==14 and validar_cnpj(n): return True,"CNPJ",n
    if len(n)==11 and validar_cpf(n):  return True,"CPF",n
    return False,"",n

def fmt_cnpj(n):
    c=so_nums(n)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c)==14 else n

def fmt_cpf(n):
    c=so_nums(n)
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c)==11 else n

def fmt_reg_0000(ni:str)->str: return f"|0000|{ni}|"
def fmt_reg_6000(tp:str)->str: return f"|6000|{tp}||||"

def _fmt_valor_layout(valor)->str:
    if isinstance(valor,(int,float)): return f"{float(valor):.2f}".replace(".",",")
    v=str(valor).strip()
    if "." in v and "," in v:
        if v.index(".")<v.index(","): v=v.replace(".","").replace(",",".")
        else: v=v.replace(",","")
    elif "," in v: v=v.replace(",",".")
    try: return f"{float(v):.2f}".replace(".",",")
    except ValueError: return "0,00"

def fmt_reg_6100(data,deb,cred,valor,cod_hist="",desc="",_u="",_f="",_s=""):
    return f"|6100|{data}|{deb}|{cred}|{_fmt_valor_layout(valor)}||{_norm_hist(desc)}|||||||"

_CHARS_PT=set("ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿºª")

def _detectar_encoding_bytes(conteudo:bytes)->str:
    for enc in ("utf-8-sig","utf-8","cp1252","latin-1"):
        try:
            texto=conteudo.decode(enc,errors="strict")
            if sum(1 for c in texto[:4096] if c in _CHARS_PT)>0 or enc in ("utf-8-sig","utf-8"):
                return enc
        except (UnicodeDecodeError,LookupError): continue
    return "latin-1"

def identificar_tipo(nome_arquivo:str,conteudo:bytes)->str:
    ext=os.path.splitext(nome_arquivo)[1].lower()
    if ext in (".xlsx",".xls",".xlsm"): return "excel"
    enc=_detectar_encoding_bytes(conteudo)
    try: amostra=conteudo[:8192].decode(enc,errors="replace")
    except: amostra=""
    linhas=[l.strip() for l in amostra.splitlines() if l.strip()]
    for ln in linhas[:40]:
        if ln.startswith("|0000|") or ln.startswith("|I0"): return "ecd"
        campos=ln.split("|")
        if len(campos)>=2 and campos[1] in ("0000","I010","I050","I075","I100","I150","I155","I200","I250","I350","I355","I990"):
            return "ecd"
    semis=sum(1 for ln in linhas[:20] if ";" in ln)
    if semis>=max(1,len(linhas[:20])//2): return "lote"
    return "lote"

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO SPED ECD — V1.8
# ═══════════════════════════════════════════════════════════════════════════════

def _split_pipe(linha:str)->list:
    c=linha.strip().split("|")
    if c and c[0]=="": c=c[1:]
    if c and c[-1]=="": c=c[:-1]
    return c

def _campo(campos:list,idx:int,default:str="")->str:
    return campos[idx].strip() if idx<len(campos) else default

def _conta_valida(conta:str)->bool:
    return bool(conta) and conta.isdigit()

class SpedECD:
    def __init__(self):
        self.cnpj=""; self.contas={}; self.historicos={}; self.lancamentos=[]

def _parse_ecd(conteudo:bytes,log:list)->tuple:
    ecd=SpedECD()
    lote_atual=None
    erros_parse=0; registros_erro=[]; contas_invalidas=0
    i200_count=0; i250_count=0

    enc=_detectar_encoding_bytes(conteudo)
    log.append(f"  Encoding detectado : {enc}")
    try: texto=conteudo.decode(enc,errors="replace")
    except: texto=conteudo.decode("utf-8",errors="replace")

    linhas=texto.splitlines()
    log.append(f"  Total de linhas    : {len(linhas):,}")

    for num,linha in enumerate(linhas,1):
        linha_orig=linha; linha=linha.strip()
        if not linha: continue
        campos=_split_pipe(linha)
        if not campos: continue
        reg=campos[0]
        try:
            if reg=="0000":
                if len(campos)>5: ecd.cnpj=_campo(campos,5)
            elif reg=="I050":
                cod=_campo(campos,5); nome=_campo(campos,7)
                if cod: ecd.contas[cod]=nome
            elif reg=="I075":
                cod=_campo(campos,1); desc=_campo(campos,2)
                if cod: ecd.historicos[cod]=_norm_hist(desc)
            elif reg=="I200":
                # ── CADA I200 = lançamento 100% independente ──────────────────
                lote_atual={
                    "num":   _campo(campos,1),
                    "data":  _campo(campos,2),
                    "valor": _campo(campos,3),
                    "partidas": [],   # lista EXCLUSIVA deste I200
                }
                ecd.lancamentos.append(lote_atual)
                i200_count+=1
                if i200_count<=5:
                    log.append(f"  [DBG I200 #{i200_count}] num={lote_atual['num']} data={lote_atual['data']} valor={lote_atual['valor']}")
            elif reg=="I250":
                if lote_atual is None:
                    registros_erro.append({"linha":num,"motivo":"I250 sem I200","conteudo":linha_orig.strip()})
                    continue
                conta=_campo(campos,1); valor_str=_campo(campos,3)
                dc=_campo(campos,4).upper()
                descr_hist=_norm_hist(_campo(campos,7))
                if dc not in ("D","C"):
                    registros_erro.append({"linha":num,"motivo":f"IND_DC='{dc}' inválido | {campos}","conteudo":linha_orig.strip()})
                    continue
                if not _conta_valida(conta):
                    registros_erro.append({"linha":num,"motivo":f"Conta '{conta}' inválida","conteudo":linha_orig.strip()})
                    contas_invalidas+=1; continue
                lote_atual["partidas"].append({"conta":conta,"valor":valor_str,"dc":dc,"descr_hist":descr_hist})
                i250_count+=1
                if i250_count<=20:
                    log.append(f"  [DBG I250 #{i250_count}] I200={lote_atual['num']} conta={conta} dc={dc} val={valor_str} hist={descr_hist[:30]!r}")
            elif reg in ("I299","I300"):
                lote_atual=None
        except Exception as ex:
            registros_erro.append({"linha":num,"motivo":f"Exceção: {ex}","conteudo":linha_orig.strip()})
            erros_parse+=1
            if erros_parse>50:
                log.append("ERRO: muitos erros — abortando.")
                return None,registros_erro

    if not ecd.cnpj:
        log.append("ERRO: CNPJ não encontrado no registro 0000.")
        return None,registros_erro

    # Estatísticas
    sem=sum(1 for l in ecd.lancamentos if not l["partidas"])
    cx=sum(1 for l in ecd.lancamentos if sum(1 for p in l["partidas"] if p["dc"]=="D")==1 and sum(1 for p in l["partidas"] if p["dc"]=="C")==1)
    cd=sum(1 for l in ecd.lancamentos if sum(1 for p in l["partidas"] if p["dc"]=="D")==1 and sum(1 for p in l["partidas"] if p["dc"]=="C")>1)
    cc=sum(1 for l in ecd.lancamentos if sum(1 for p in l["partidas"] if p["dc"]=="D")>1 and sum(1 for p in l["partidas"] if p["dc"]=="C")==1)
    cv=sum(1 for l in ecd.lancamentos if sum(1 for p in l["partidas"] if p["dc"]=="D")>1 and sum(1 for p in l["partidas"] if p["dc"]=="C")>1)

    log.append(f"  CNPJ               : {ecd.cnpj}")
    log.append(f"  Lançamentos (I200) : {i200_count:,}")
    log.append(f"  Partidas (I250)    : {i250_count:,}")
    log.append(f"  Sem partida        : {sem:,}")
    log.append(f"  Tipo X (1D→1C)     : {cx:,}")
    log.append(f"  Tipo D (1D→nC)     : {cd:,}")
    log.append(f"  Tipo C (nD→1C)     : {cc:,}")
    log.append(f"  Tipo V (nD→nC)     : {cv:,}")
    if contas_invalidas: log.append(f"  Contas inválidas   : {contas_invalidas:,}")
    if registros_erro:   log.append(f"  Erros/avisos       : {len(registros_erro):,}")
    return ecd,registros_erro

def _fmt_data_ecd(d:str)->str:
    d=d.strip()
    if "/" in d: return d
    if len(d)==8 and d.isdigit(): return f"{d[:2]}/{d[2:4]}/{d[4:]}"
    return d

def _str2float(v)->float:
    if isinstance(v,(int,float)): return float(v)
    v=str(v).strip()
    if "." in v and "," in v:
        if v.index(".")<v.index(","): v=v.replace(".","").replace(",",".")
        else: v=v.replace(",","")
    elif "," in v: v=v.replace(",",".")
    try: return float(v)
    except: return 0.0

def _montar_hist_ecd(p:dict)->str: return p.get("descr_hist","").strip()
def _primeiro_hist(partidas:list)->str:
    for p in partidas:
        h=_montar_hist_ecd(p)
        if h: return h
    return ""

def _classif(nd:int,nc:int)->str:
    if nd==1 and nc==1: return "X"
    if nd==1 and nc>1:  return "D"
    if nd>1  and nc==1: return "C"
    return "V"

def tipo_lancamento(nd,nc): return _classif(nd,nc)

# ═══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DAS LINHAS ECD — V1.8
# ───────────────────────────────────────────────────────────────────────────────
# CORREÇÃO PRINCIPAL V1.8:
# O sistema Domínio NÃO aceita tipo V com débito e crédito preenchidos
# simultaneamente na mesma linha 6100 (erro: "não é permitido ter débito e
# crédito no mesmo lançamento se o tipo for diferente de 'um para um'").
#
# REGRA:
#   • 1D × 1C → tipo X  → 1 linha com débito E crédito preenchidos ✓
#   • 1D × nC → tipo D  → 1ª linha só débito, demais só crédito ✓
#   • nD × 1C → tipo C  → 1ª linha só crédito, demais só débito ✓
#   • nD × nC → tipo V  → DECOMPOR em lançamentos X individuais
#                          (1 linha por par débito×crédito com valor proporcional)
# ═══════════════════════════════════════════════════════════════════════════════
def _linhas_ecd(lanc:dict)->list:
    """
    Gera 6000 + 6100 para um único I200.
    
    REGRA V1.8 — tipo V é DECOMPOSTO em múltiplos lançamentos X,
    pois o Domínio rejeita linhas 6100 com débito+crédito em lançamento V.
    """
    partidas=lanc["partidas"]
    debs =[p for p in partidas if p["dc"]=="D"]
    creds=[p for p in partidas if p["dc"]=="C"]
    if not debs or not creds: return []

    data=_fmt_data_ecd(lanc["data"])
    nd=len(debs); nc=len(creds)
    hist=_primeiro_hist(partidas)
    out=[]

    def ln(db,cr,val,h):
        return fmt_reg_6100(data,db,cr,val,"",h)

    if nd==1 and nc==1:
        # ── TIPO X: 1 débito → 1 crédito ─────────────────────────────────────
        h=_montar_hist_ecd(debs[0]) or hist
        out.append(fmt_reg_6000("X"))
        out.append(ln(debs[0]["conta"],creds[0]["conta"],_str2float(debs[0]["valor"]),h))

    elif nd==1 and nc>1:
        # ── TIPO D: 1 débito → N créditos ────────────────────────────────────
        h=_montar_hist_ecd(debs[0]) or hist
        out.append(fmt_reg_6000("D"))
        out.append(ln(debs[0]["conta"],"",_str2float(debs[0]["valor"]),h))
        for cr in creds:
            h=_montar_hist_ecd(cr) or _montar_hist_ecd(debs[0]) or hist
            out.append(ln("",cr["conta"],_str2float(cr["valor"]),h))

    elif nd>1 and nc==1:
        # ── TIPO C: N débitos → 1 crédito ────────────────────────────────────
        h=_montar_hist_ecd(creds[0]) or hist
        out.append(fmt_reg_6000("C"))
        out.append(ln("",creds[0]["conta"],_str2float(creds[0]["valor"]),h))
        for db in debs:
            h=_montar_hist_ecd(db) or _montar_hist_ecd(creds[0]) or hist
            out.append(ln(db["conta"],"",_str2float(db["valor"]),h))

    else:
        # ── TIPO V → DECOMPOR EM LANÇAMENTOS X INDIVIDUAIS ───────────────────
        # O Domínio rejeita tipo V com débito+crédito na mesma linha.
        # Solução: cada par (débito_i × crédito_j) vira um lançamento X
        # independente. O valor usado é o do crédito (partida analítica).
        #
        # Exemplo: 2 débitos × 3 créditos → 6 lançamentos X separados
        for db in debs:
            for cr in creds:
                h=_montar_hist_ecd(db) or _montar_hist_ecd(cr) or hist
                val=_str2float(cr["valor"])
                out.append(fmt_reg_6000("X"))
                out.append(ln(db["conta"],cr["conta"],val,h))

    return out

def _gerar_ecd(ecd:SpedECD,log:list,prog_bar,status)->list:
    linhas=[fmt_reg_0000(re.sub(r"\D","",ecd.cnpj))]
    t6000=t6100=ignorados=0
    debug={"X":0,"D":0,"C":0,"V":0}
    total=len(ecd.lancamentos)

    for idx,lanc in enumerate(ecd.lancamentos):
        if idx%500==0 or idx==total-1:
            prog_bar.progress(min(55+int(((idx+1)/total)*35),99))
            status.text(f"Gerando lançamento {idx+1:,}/{total:,}...")
        if not lanc.get("partidas"):
            ignorados+=1; continue
        novas=_linhas_ecd(lanc)
        if not novas:
            ignorados+=1; continue
        for l in novas:
            if l.startswith("|6000|"):
                t=l.split("|")[2] if len(l.split("|"))>2 else "?"
                debug[t]=debug.get(t,0)+1; t6000+=1
            elif l.startswith("|6100|"):
                t6100+=1
        linhas.extend(novas)

    log.append(f"  Reg. 6000 gerados  : {t6000:,}")
    log.append(f"  Reg. 6100 gerados  : {t6100:,}")
    log.append(f"  Ignorados          : {ignorados:,}")
    log.append(f"  Tipos — X:{debug['X']} D:{debug['D']} C:{debug['C']} V_decomp:{debug.get('V',0)}")
    log.append(f"  Total linhas saída : {len(linhas):,}")
    return linhas

def _txt_erros_ecd(registros_erro:list,cnpj:str)->str:
    linhas=["="*70,"RELATÓRIO DE ERROS — SPED ECD",f"CNPJ : {cnpj}",f"Total: {len(registros_erro)}","="*70,""]
    for i,r in enumerate(registros_erro,1):
        linhas+=[f"[{i:04d}] Linha   : {r['linha']}",f"       Motivo  : {r['motivo']}",f"       Conteúdo: {r['conteudo']}",""]
    linhas+=["="*70,"FIM DO RELATÓRIO"]
    return "\n".join(linhas)

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO TXT STREAMING
# ═══════════════════════════════════════════════════════════════════════════════
def _filtrar_chunk(chunk:pd.DataFrame)->pd.DataFrame:
    for c in COLS_PADRAO:
        if c not in chunk.columns: chunk[c]=""
    for c in COLS_PADRAO: chunk[c]=chunk[c].fillna("").astype(str).str.strip()
    il=chunk["Inicia Lote"].str.strip()
    chunk["Inicia Lote"]=il.where(il.str.fullmatch(r"[1-9]\d*"),"")
    m_data=chunk["Data"]!=""
    datas=pd.to_datetime(chunk.loc[m_data,"Data"],dayfirst=True,errors="coerce")
    m_dv=m_data.copy(); m_dv[m_data]=datas.notna()
    m_conta=((chunk["Cód. Conta Debito"]!="")|(chunk["Cód. Conta Credito"]!=""))
    m_valor=chunk["Valor"].str.strip()!=""
    return chunk[m_dv&m_conta&m_valor].copy()

def ler_txt_streaming(conteudo:bytes):
    enc=_detectar_encoding_bytes(conteudo)
    buf=io.BytesIO(conteudo)
    reader=pd.read_csv(buf,sep=";",header=None,names=COLS_PADRAO,dtype=str,
                       encoding=enc,on_bad_lines="skip",engine="c",
                       usecols=range(len(COLS_PADRAO)),chunksize=CHUNK_SIZE)
    linha_at=0
    for chunk in reader:
        n=len(chunk)
        chunk["_linha_origem"]=np.arange(linha_at+1,linha_at+n+1,dtype=np.int32)
        linha_at+=n
        filtrado=_filtrar_chunk(chunk); del chunk
        if len(filtrado)>0: yield filtrado,enc
        del filtrado

def diagnosticar_lote(W:pd.DataFrame,dif:float)->dict:
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

def _gerar_linhas_6100(debs:pd.DataFrame,creds:pd.DataFrame,tp:str)->list:
    out=[]
    if tp=="X":
        rd=debs.iloc[0]; rc=creds.iloc[0]
        out.append(fmt_reg_6100(formatar_data(rd["dt"]),str(rd["cd"]),str(rc["cc"]),
                                float(rd["vf"]),"",_norm_hist(str(rd["desc"]) or str(rc["desc"]))))
    elif tp=="D":
        rd=debs.iloc[0]
        out.append(fmt_reg_6100(formatar_data(rd["dt"]),str(rd["cd"]),"",
                                float(rd["vf"]),"",_norm_hist(str(rd["desc"]))))
        for _,rc in creds.iterrows():
            out.append(fmt_reg_6100(formatar_data(rd["dt"]),"",str(rc["cc"]),
                                    float(rc["vf"]),"",_norm_hist(str(rc["desc"]) or str(rd["desc"]))))
    elif tp=="C":
        rc=creds.iloc[0]
        out.append(fmt_reg_6100(formatar_data(debs.iloc[0]["dt"]),"",str(rc["cc"]),
                                float(rc["vf"]),"",_norm_hist(str(rc["desc"]))))
        for _,rd in debs.iterrows():
            out.append(fmt_reg_6100(formatar_data(rd["dt"]),str(rd["cd"]),"",
                                    float(rd["vf"]),"",_norm_hist(str(rd["desc"]) or str(rc["desc"]))))
    else:
        cross=debs[["cd","vf","desc","dt"]].merge(
            creds[["cc","desc"]].rename(columns={"desc":"desc_c"}),how="cross")
        for _,row in cross.iterrows():
            out.append(fmt_reg_6100(formatar_data(row["dt"]),str(row["cd"]),str(row["cc"]),
                                    float(row["vf"]),"",_norm_hist(str(row["desc"]) or str(row["desc_c"]))))
    return out

def _flush_lote(df_lote,num,saida_buf,resumo,erros):
    if df_lote is None or len(df_lote)==0: return
    v_float=limpar_valor_vec(df_lote["Valor"])
    cd_arr=limpar_contas_vec(df_lote["Cód. Conta Debito"])
    cc_arr=limpar_contas_vec(df_lote["Cód. Conta Credito"])
    td_arr=cd_arr!=""; tc_arr=cc_arr!=""; ambos_arr=td_arr&tc_arr
    vd_arr=np.where(td_arr,v_float,0.0); vc_arr=np.where(tc_arr,v_float,0.0)
    dt_arr=df_lote["Data"].fillna("").astype(str).to_numpy()
    col_desc=df_lote["Complemento Histórico"].fillna("").astype(str)
    desc_arr=col_desc.to_numpy(dtype=object)
    mask_esp=col_desc.str.contains(r'[^\x20-\x7E]|\|',regex=True,na=False).to_numpy()
    for i in np.where(mask_esp)[0]: desc_arr[i]=_norm_hist(desc_arr[i])
    lo_arr=df_lote["_linha_origem"].fillna(0).astype(int).to_numpy(dtype=np.int32)
    W=pd.DataFrame({"nl":num,"lo":lo_arr,"vd":vd_arr,"vc":vc_arr,"vf":v_float,
                    "cd":cd_arr,"cc":cc_arr,"td":td_arr,"tc":tc_arr,
                    "ambos":ambos_arr,"dt":dt_arr,"desc":desc_arr})
    lm=int(lo_arr.min()) if len(lo_arr) else 0
    lx=int(lo_arr.max()) if len(lo_arr) else 0
    fx=f"{lm}–{lx}" if lm!=lx else str(lm)
    dt_fmt=formatar_data(dt_arr[0]) if len(dt_arr) else ""
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

def _flush_lote_normal(W,num,saida_buf,resumo,erros,fx,dt_fmt):
    td_arr=W["td"].to_numpy(); tc_arr=W["tc"].to_numpy()
    vd_arr=W["vd"].to_numpy(); vc_arr=W["vc"].to_numpy()
    desc_arr=W["desc"].to_numpy()
    td_sum=round(float(vd_arr[td_arr].sum()),2)
    tc_sum=round(float(vc_arr[tc_arr].sum()),2)
    dif=round(abs(td_sum-tc_sum),2); ok=dif<TOL_VALOR
    entrada={"num_lote":num,"data":dt_fmt,
              "descricao":str(desc_arr[0]) if len(desc_arr) else "",
              "total_debito":td_sum,"total_credito":tc_sum,
              "diferenca":dif,"balanceado":ok,
              "qtd_linhas":len(W),"faixa_linhas":fx,"diagnostico":{}}
    if not ok:
        entrada["diagnostico"]=diagnosticar_lote(W,dif); erros.append(entrada)
    else:
        debs=W[W["td"]].reset_index(drop=True); creds=W[W["tc"]].reset_index(drop=True)
        if len(debs)>0 and len(creds)>0:
            tp=tipo_lancamento(len(debs),len(creds))
            linhas_out=[fmt_reg_6000(tp)]+_gerar_linhas_6100(debs,creds,tp)
            saida_buf.write("\n".join(linhas_out)+"\n")
    resumo.append(entrada)

def processar_streaming(conteudo:bytes,ni:str,log:list)->tuple:
    saida_buf=io.StringIO(); saida_buf.write(fmt_reg_0000(ni)+"\n")
    pendente=None; num_lote_g=0; usa_inicia=None
    resumo:list=[]; erros:list=[]; total_lins=0; ignoradas=0
    enc_final="utf-8"; chunk_count=0
    for chunk_df,enc in ler_txt_streaming(conteudo):
        enc_final=enc; total_lins+=len(chunk_df); chunk_count+=1
        if usa_inicia is None:
            usa_inicia=bool((chunk_df["Inicia Lote"].str.strip()!="").any())
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
            if ambos_tmp.all():
                chunk_df["_num_lote"]=np.arange(num_lote_g+1,num_lote_g+len(chunk_df)+1,dtype=np.int32)
            elif ambos_tmp.any():
                desc=chunk_df["Complemento Histórico"].fillna("").astype(str).str.strip().str.upper().str.replace(r"\s+"," ",regex=True)
                chave=(chunk_df["Data"].fillna("").astype(str).str.strip()+"|||"+desc).to_numpy()
                muda=np.empty(len(chave),dtype=bool); muda[0]=True; muda[1:]=chave[1:]!=chave[:-1]
                chunk_df["_num_lote"]=np.cumsum(muda|ambos_tmp,dtype=np.int32)+num_lote_g
            else:
                desc=chunk_df["Complemento Histórico"].fillna("").astype(str).str.strip().str.upper().str.replace(r"\s+"," ",regex=True)
                chave=(chunk_df["Data"].fillna("").astype(str).str.strip()+"|||"+desc).to_numpy()
                muda=np.empty(len(chave),dtype=bool); muda[0]=True; muda[1:]=chave[1:]!=chave[:-1]
                chunk_df["_num_lote"]=np.cumsum(muda,dtype=np.int32)+num_lote_g
        ultimo_lote=int(chunk_df["_num_lote"].max())
        mask_ultimo=chunk_df["_num_lote"]==ultimo_lote
        pendente=chunk_df[mask_ultimo].copy()
        chunk_proc=chunk_df[~mask_ultimo]; del chunk_df
        for nl,grupo in chunk_proc.groupby("_num_lote",sort=True):
            _flush_lote(grupo,int(nl),saida_buf,resumo,erros)
        num_lote_g=ultimo_lote-1; del chunk_proc
        if chunk_count%5==0: gc.collect()
    if pendente is not None and len(pendente)>0:
        num_lote_g+=1; _flush_lote(pendente,num_lote_g,saida_buf,resumo,erros); del pendente
    gc.collect()
    log.append(f"  Linhas lidas      : {total_lins:,}")
    log.append(f"  Lotes processados : {len(resumo):,}")
    log.append(f"  Lotes OK          : {len(resumo)-len(erros):,}")
    log.append(f"  Lotes com erro    : {len(erros):,}")
    saida_bytes=saida_buf.getvalue().encode("utf-8-sig"); del saida_buf
    return saida_bytes,resumo,erros,total_lins,ignoradas,enc_final

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO EXCEL
# ═══════════════════════════════════════════════════════════════════════════════
_COLS_ESP_LOW=[c.lower() for c in COLS_PADRAO[:8]]

def detectar_cabecalho_excel(conteudo:bytes,sheet:str)->tuple:
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

def ler_excel_lote(conteudo:bytes,sheet:str,linha_h:int)->tuple:
    buf=io.BytesIO(conteudo)
    raw=pd.read_excel(buf,sheet_name=sheet,header=None,dtype=str,engine="openpyxl")
    pasta="C:\\Temp"
    try:
        v=str(raw.iloc[1,6]).strip()
        if v and v.lower() not in ("nan","none",""): pasta=v
    except: pass
    while raw.shape[1]<len(COLS_PADRAO)+2: raw[raw.shape[1]]=""
    raw.columns=range(raw.shape[1])
    df=raw.iloc[linha_h+1:].reset_index(drop=True).copy(); del raw; gc.collect()
    df.columns=list(range(df.shape[1]))
    df=df.rename(columns={i:c for i,c in enumerate(COLS_PADRAO)})
    _V={"nan","NaN","None","none",""}
    for c in COLS_PADRAO:
        if c in df.columns: df[c]=df[c].fillna("").astype(str).str.strip().replace(list(_V),"")
    mask=~((df["Data"]=="")&(df["Cód. Conta Debito"]=="")&(df["Cód. Conta Credito"]=="")&(df["Valor"]==""))
    df=df[mask].reset_index(drop=True).copy()
    df["_linha_origem"]=(df.index+linha_h+2).astype(np.int32)
    return df,pasta

def montar_lotes_excel(df:pd.DataFrame)->tuple:
    R=df.copy()
    for col in COLS_PADRAO+["_linha_origem"]:
        if col not in R.columns: R[col]=""
    inicia=R["Inicia Lote"].fillna("").astype(str).str.strip()
    tem_ini=bool((inicia!="").any())
    if tem_ini:
        marcador=(inicia!="").to_numpy(dtype=bool)
        R["_num_lote"]=np.where(np.cumsum(marcador)>0,np.cumsum(marcador,dtype=np.int32),np.int32(1))
    else:
        cd_tmp=limpar_contas_vec(R["Cód. Conta Debito"])
        cc_tmp=limpar_contas_vec(R["Cód. Conta Credito"])
        ambos_tmp=(cd_tmp!="")&(cc_tmp!="")
        if ambos_tmp.all():
            R["_num_lote"]=np.arange(1,len(R)+1,dtype=np.int32)
        elif ambos_tmp.any():
            desc=R["Complemento Histórico"].fillna("").astype(str).str.strip().str.upper().str.replace(r"\s+"," ",regex=True)
            chave=(R["Data"].fillna("").astype(str).str.strip()+"|||"+desc).to_numpy()
            muda=np.empty(len(chave),dtype=bool); muda[0]=True; muda[1:]=chave[1:]!=chave[:-1]
            R["_num_lote"]=np.cumsum(muda|ambos_tmp,dtype=np.int32)
        else:
            desc=R["Complemento Histórico"].fillna("").astype(str).str.strip().str.upper().str.replace(r"\s+"," ",regex=True)
            chave=(R["Data"].fillna("").astype(str).str.strip()+"|||"+desc).to_numpy()
            muda=np.empty(len(chave),dtype=bool); muda[0]=True; muda[1:]=chave[1:]!=chave[:-1]
            R["_num_lote"]=np.cumsum(muda,dtype=np.int32)
    return R,"Inicia Lote" if tem_ini else "Data + Descrição"

def processar_excel(df:pd.DataFrame,ni:str,log:list)->tuple:
    saida_buf=io.StringIO(); saida_buf.write(fmt_reg_0000(ni)+"\n")
    resumo:list=[]; erros:list=[]
    for nl,grupo in df.groupby("_num_lote",sort=True):
        _flush_lote(grupo,int(nl),saida_buf,resumo,erros)
    gc.collect()
    log.append(f"  Lotes processados : {len(resumo):,}")
    log.append(f"  Lotes OK          : {len(resumo)-len(erros):,}")
    log.append(f"  Lotes com erro    : {len(erros):,}")
    saida_bytes=saida_buf.getvalue().encode("utf-8-sig"); del saida_buf
    return saida_bytes,resumo,erros

def _montar_log_lote(resumo,erros,ni,ti,inf,n_gravados,ignoradas,enc,crono):
    td=sum(v["total_debito"] for v in resumo); tc=sum(v["total_credito"] for v in resumo)
    ok=len(resumo)-len(erros)
    conc="SUCESSO" if not erros else f"ATENÇÃO — {len(erros)} lote(s) desbalanceado(s)"
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

def _init_state():
    defaults={"resultado_bytes":None,"resultado_nome":"saida.txt","erros_bytes":None,"erros_nome":"erros.txt",
              "log_bytes":None,"log_nome":"log.txt","log_linhas":[],"resumo":[],"erros_lote":[],
              "metricas":{},"tipo_detectado":None,"sheets":[],"sheet_sel":"","arquivo_bytes":None,
              "arquivo_nome":"","processado":False,"cnpj_ecd":"","cnpj_ecd_fmt":""}
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k]=v

def _reset():
    keys=["resultado_bytes","resultado_nome","erros_bytes","erros_nome","log_bytes","log_nome",
          "log_linhas","resumo","erros_lote","metricas","tipo_detectado","sheets","sheet_sel",
          "arquivo_bytes","arquivo_nome","processado","cnpj_ecd","cnpj_ecd_fmt"]
    for k in keys:
        st.session_state[k]=([] if k in ("log_linhas","resumo","erros_lote","sheets") else
                              {} if k=="metricas" else None if k.endswith("_bytes") else
                              False if k=="processado" else "")

def _pre_scan_cnpj_ecd(conteudo:bytes)->str:
    enc=_detectar_encoding_bytes(conteudo)
    try: amostra=conteudo[:4096].decode(enc,errors="replace")
    except: amostra=conteudo[:4096].decode("utf-8",errors="replace")
    for linha in amostra.splitlines():
        campos=_split_pipe(linha.strip())
        if campos and campos[0]=="0000" and len(campos)>5:
            cnpj=re.sub(r"\D","",campos[5].strip())
            if len(cnpj)==14: return cnpj
    return ""

def _render_resultados_lote(exibir_log:bool):
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

def _render_resultados_ecd(exibir_log:bool):
    metricas=st.session_state.metricas or {}
    st.markdown("---"); st.markdown("## 📊 Resultado da Conversão — SPED ECD")
    if metricas:
        cols=st.columns(len(metricas))
        for i,(k,v) in enumerate(metricas.items()): cols[i].metric(k,v)
    st.markdown("#### ⬇ Downloads")
    dl1,dl2=st.columns(2)
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

def main():
    st.set_page_config(page_title="Domínio Sistemas | Thomson Reuters",page_icon="🟠",layout="wide",initial_sidebar_state="expanded")
    apply_theme(); _init_state()
    st.markdown(f"<div class='header-box'><h2 style='color:#FF6B00;margin:0;'>Domínio Sistemas — Conversor Unificado</h2>"
                f"<p style='color:#6B7A8D;margin:6px 0 0;'>Lançamentos Contábeis (TXT/Excel) &nbsp;|&nbsp; SPED ECD &nbsp;→&nbsp; "
                f"0000 + 6000 + 6100 &nbsp;|&nbsp; <b style='color:#FF6B00;'>Thomson Reuters</b>&nbsp;|&nbsp; <small>{VERSAO}</small></p></div>",
                unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("### ⚙ Configurações"); st.markdown("---")
        exibir_log=st.checkbox("Exibir log de processamento",value=True)
        st.markdown("---"); st.markdown(f"**Versão:** {VERSAO}")
        st.markdown("**Thomson Reuters — Domínio Sistemas**"); st.markdown("---")
        st.markdown("**Formatos suportados:**")
        st.markdown("- 📊 Excel (.xlsx / .xls)\n- 📄 TXT separado por `;`\n- 📋 SPED ECD (.txt)")
        st.markdown("---")
        st.code("|0000|CNPJ|\n|6000|TIPO||||\n|6100|DATA|DEB|CRED|VALOR||HIST|||||||",language=None)
        st.markdown(f"**Limite:** {MAX_UPLOAD_MB} MB")
    st.markdown("#### 📂 Passo 1 — Selecionar Arquivo")
    uploaded=st.file_uploader(f"Arraste ou clique (Excel, TXT ou SPED ECD — máx. {MAX_UPLOAD_MB} MB)",
                               type=["xlsx","xls","xlsm","txt","csv"])
    if uploaded is not None:
        conteudo=uploaded.read(); mb=len(conteudo)/(1024*1024)
        if mb>MAX_UPLOAD_MB:
            st.error(f"⛔ Arquivo muito grande ({mb:.1f} MB). Limite: {MAX_UPLOAD_MB} MB."); return
        if conteudo!=st.session_state.arquivo_bytes or uploaded.name!=st.session_state.arquivo_nome:
            _reset()
            st.session_state.arquivo_bytes=conteudo; st.session_state.arquivo_nome=uploaded.name
            tipo=identificar_tipo(uploaded.name,conteudo); st.session_state.tipo_detectado=tipo
            if tipo=="excel":
                try:
                    xl=pd.ExcelFile(io.BytesIO(conteudo),engine="openpyxl")
                    st.session_state.sheets=xl.sheet_names
                    st.session_state.sheet_sel=("Plan1" if "Plan1" in xl.sheet_names else xl.sheet_names[0])
                except: st.session_state.sheets=[]
            elif tipo=="ecd":
                cnpj_num=_pre_scan_cnpj_ecd(conteudo)
                st.session_state.cnpj_ecd=cnpj_num
                st.session_state.cnpj_ecd_fmt=fmt_cnpj(cnpj_num) if cnpj_num else ""
    if st.session_state.arquivo_bytes is None:
        st.markdown("<div class='info-box'>⬆ Selecione um arquivo para começar.</div>",unsafe_allow_html=True); return
    tipo=st.session_state.tipo_detectado
    badges={"ecd":"<span class='badge-ecd'>📋 SPED ECD</span>",
            "excel":"<span class='badge-excel'>📊 Excel</span>",
            "lote":"<span class='badge-lote'>📄 TXT Lote</span>"}
    mb_info=len(st.session_state.arquivo_bytes)/(1024*1024)
    st.markdown(f"{badges.get(tipo,'')} <span style='color:#6B7A8D;font-size:13px;margin-left:12px;'>{st.session_state.arquivo_nome} — {mb_info:.1f} MB</span>",unsafe_allow_html=True)
    st.markdown("")
    sheet_sel=""; linha_h=3; auto_head=True
    if tipo=="excel" and st.session_state.sheets:
        st.markdown("#### 📋 Passo 2 — Configurar Excel")
        col1,col2,col3=st.columns([2,1,1])
        with col1:
            sheet_sel=st.selectbox("Aba (Sheet)",st.session_state.sheets,
                index=(st.session_state.sheets.index(st.session_state.sheet_sel) if st.session_state.sheet_sel in st.session_state.sheets else 0))
            st.session_state.sheet_sel=sheet_sel
        with col2: auto_head=st.checkbox("Detectar cabeçalho automaticamente",value=True)
        with col3:
            if not auto_head: linha_h=st.number_input("Linha do cabeçalho",min_value=1,max_value=50,value=4)-1
    ni=""; ok_insc=False; ti=""; inf=""
    if tipo=="ecd":
        st.markdown("#### 🏢 Passo 2 — CNPJ (preenchido automaticamente)")
        cnpj_ecd=st.session_state.cnpj_ecd
        if cnpj_ecd and validar_cnpj(cnpj_ecd):
            st.markdown(f"<div class='cnpj-auto'>✔ CNPJ extraído: <span>{st.session_state.cnpj_ecd_fmt}</span></div>",unsafe_allow_html=True)
            st.code(fmt_reg_0000(cnpj_ecd),language=None)
            ok_insc=True; ti="CNPJ"; ni=cnpj_ecd; inf=st.session_state.cnpj_ecd_fmt
        else:
            st.warning("⚠ CNPJ não encontrado. Informe manualmente.")
            cnpj_raw=st.text_input("CNPJ / CPF",placeholder="00.000.000/0001-00",key="cnpj_manual_ecd")
            ok_insc,ti,ni=validar_inscricao(cnpj_raw)
            if cnpj_raw:
                if ok_insc: inf=fmt_cnpj(ni) if ti=="CNPJ" else fmt_cpf(ni); st.success(f"✔ {ti} válido: {inf}")
                else: st.error("✖ CNPJ/CPF inválido")
    else:
        st.markdown("#### 🏢 Passo 2 — Informar CNPJ / CPF")
        cnpj_raw=st.text_input("CNPJ / CPF",placeholder="00.000.000/0001-00 ou 000.000.000-00",key="cnpj_lote")
        ok_insc,ti,ni=validar_inscricao(cnpj_raw)
        if cnpj_raw:
            if ok_insc:
                inf=fmt_cnpj(ni) if ti=="CNPJ" else fmt_cpf(ni)
                col_a,col_b=st.columns([1,2])
                with col_a: st.success(f"✔ {ti} válido")
                with col_b: st.code(fmt_reg_0000(ni),language=None)
            else: st.error("✖ CNPJ/CPF inválido")
    st.markdown("---"); st.markdown("#### ⚙ Passo 3 — Opções e Conversão")
    col_op1,_=st.columns(2)
    with col_op1:
        gerar_6110=st.checkbox("Gerar registro 6110 (apenas SPED ECD)",value=False,disabled=(tipo!="ecd"))
    col_b1,col_b2=st.columns([2,1])
    with col_b1:
        btn_converter=st.button("▶ CONVERTER",disabled=(not ok_insc),use_container_width=True,type="primary")
    with col_b2:
        btn_limpar=st.button("🗑 Limpar tudo",use_container_width=True)
    if btn_limpar: _reset(); st.rerun()
    if btn_converter and ok_insc:
        conteudo=st.session_state.arquivo_bytes; log=[]; crono=Cronometro(); crono.iniciar()
        status_txt=st.empty(); prog_bar=st.progress(0)
        try:
            if tipo=="ecd":
                status_txt.text("Lendo SPED ECD..."); log.append("── LEITURA SPED ECD ──")
                crono.etapa("Leitura SPED ECD"); prog_bar.progress(10)
                ecd,registros_erro=_parse_ecd(conteudo,log)
                if ecd is None:
                    st.error("Falha na leitura do SPED ECD."); st.session_state.log_linhas=log
                else:
                    prog_bar.progress(50); status_txt.text("Gerando registros...")
                    crono.etapa("Geração dos registros"); log.append("\n── GERAÇÃO ──")
                    linhas_ecd=_gerar_ecd(ecd,log,prog_bar,status_txt)
                    if gerar_6110:
                        linhas_com_6110=[]
                        for l in linhas_ecd:
                            linhas_com_6110.append(l)
                            if l.startswith("|6100|"):
                                campos=l.split("|")
                                if len(campos)>=6:
                                    data_l=campos[2]; deb_l=campos[3]; cred_l=campos[4]
                                    valor_l=campos[5]; hist_l=campos[7] if len(campos)>7 else ""
                                    if deb_l: linhas_com_6110.append(f"|6110|{data_l}|{deb_l}|{valor_l}|D||{hist_l}|||||||")
                                    if cred_l: linhas_com_6110.append(f"|6110|{data_l}|{cred_l}|{valor_l}|C||{hist_l}|||||||")
                        linhas_ecd=linhas_com_6110
                    crono.etapa("Montagem do arquivo"); prog_bar.progress(90); status_txt.text("Montando arquivo...")
                    buf_out=io.StringIO()
                    for i in range(0,len(linhas_ecd),WRITE_CHUNK):
                        buf_out.write("\n".join(linhas_ecd[i:i+WRITE_CHUNK])+"\n")
                    resultado_bytes=buf_out.getvalue().encode("utf-8-sig"); del buf_out,linhas_ecd; gc.collect()
                    nome_saida=f"ECD_{ni}_dominio.txt"
                    st.session_state.resultado_bytes=resultado_bytes; st.session_state.resultado_nome=nome_saida
                    n6000=resultado_bytes.count(b"|6000|"); n6100=resultado_bytes.count(b"|6100|")
                    st.session_state.metricas={"CNPJ":ecd.cnpj,"Lançamentos (I200)":f"{len(ecd.lancamentos):,}",
                                               "Registros 6000":f"{n6000:,}","Registros 6100":f"{n6100:,}",
                                               "Tamanho saída":f"{len(resultado_bytes)/1024:.1f} KB"}
                    if registros_erro:
                        erros_txt=_txt_erros_ecd(registros_erro,ecd.cnpj)
                        st.session_state.erros_bytes=erros_txt.encode("utf-8-sig")
                        st.session_state.erros_nome=f"ECD_{ni}_erros.txt"
                    total_seg=crono.encerrar()
                    log.append(f"\n── TEMPO TOTAL: {Cronometro.fmt(total_seg)} ──")
                    for e in crono.etapas: log.append(f"  {e['nome']}: {Cronometro.fmt(e['segundos'])}")
                    st.session_state.log_linhas=log; st.session_state.processado=True
                    prog_bar.progress(100); status_txt.text("Concluído!")
            elif tipo=="excel":
                crono.etapa("Leitura Excel"); status_txt.text("Lendo Excel..."); prog_bar.progress(8)
                sh=st.session_state.sheet_sel; lh_det,_=detectar_cabecalho_excel(conteudo,sh)
                lh=lh_det if auto_head else linha_h; df,_=ler_excel_lote(conteudo,sh,lh)
                log.append(f"Excel — Aba: {sh} | Cabeçalho: linha {lh+1}"); log.append(f"Linhas carregadas: {len(df):,}")
                prog_bar.progress(30); crono.etapa("Montagem de lotes"); status_txt.text("Montando lotes...")
                df,modo=montar_lotes_excel(df); n_lotes=int(df["_num_lote"].max()) if len(df)>0 else 0
                log.append(f"Lotes: {n_lotes:,} [modo: {modo}]"); prog_bar.progress(45)
                crono.etapa("Processamento / validação"); status_txt.text("Processando lotes...")
                resultado_bytes,resumo,erros=processar_excel(df,ni,log); del df; gc.collect(); prog_bar.progress(85)
                n_gravados=resultado_bytes.count(b"|6000|")
                st.session_state.resultado_bytes=resultado_bytes; st.session_state.resultado_nome="lancamentos.txt"
                st.session_state.resumo=resumo; st.session_state.erros_lote=erros
                crono.etapa("Geração do log")
                log_txt=_montar_log_lote(resumo,erros,ni,ti,inf,n_gravados,0,"N/A (Excel)",crono)
                st.session_state.log_bytes=log_txt.encode("utf-8-sig"); st.session_state.log_nome="log_conversao.txt"
                total_seg=crono.encerrar(); log.append(f"\nTempo total: {Cronometro.fmt(total_seg)}")
                st.session_state.metricas={"Lotes total":f"{len(resumo):,}","Lotes OK":f"{len(resumo)-len(erros):,}",
                                           "Lotes erro":f"{len(erros):,}","Reg. gerados":f"{n_gravados:,}",
                                           "Tamanho saída":f"{len(resultado_bytes)/1024:.1f} KB"}
                st.session_state.log_linhas=log; st.session_state.processado=True
                prog_bar.progress(100); status_txt.text("Concluído!")
            else:
                crono.etapa("Processamento streaming"); mb_txt=len(conteudo)/(1024*1024)
                status_txt.text(f"Processando {mb_txt:.1f} MB em streaming..."); prog_bar.progress(5)
                log.append(f"── TXT STREAMING — {mb_txt:.1f} MB ──")
                resultado_bytes,resumo,erros,total_lins,ignoradas,enc_usado=processar_streaming(conteudo,ni,log)
                prog_bar.progress(90); n_gravados=resultado_bytes.count(b"|6000|")
                st.session_state.resultado_bytes=resultado_bytes; st.session_state.resultado_nome="lancamentos.txt"
                st.session_state.resumo=resumo; st.session_state.erros_lote=erros
                crono.etapa("Geração do log")
                log_txt=_montar_log_lote(resumo,erros,ni,ti,inf,n_gravados,ignoradas,enc_usado,crono)
                st.session_state.log_bytes=log_txt.encode("utf-8-sig"); st.session_state.log_nome="log_conversao.txt"
                total_seg=crono.encerrar(); log.append(f"\nTempo total: {Cronometro.fmt(total_seg)}")
                st.session_state.metricas={"Linhas lidas":f"{total_lins:,}","Lotes total":f"{len(resumo):,}",
                                           "Lotes OK":f"{len(resumo)-len(erros):,}","Lotes erro":f"{len(erros):,}",
                                           "Reg. gerados":f"{n_gravados:,}","Tamanho saída":f"{len(resultado_bytes)/1024:.1f} KB"}
                st.session_state.log_linhas=log; st.session_state.processado=True
                prog_bar.progress(100); status_txt.text("Concluído!")
        except Exception as ex:
            tb=traceback.format_exc(); st.error(f"⛔ Erro inesperado: {ex}")
            log.append(f"ERRO FATAL: {ex}\n{tb}"); st.session_state.log_linhas=log
            prog_bar.progress(0); status_txt.text("Falha.")
        st.rerun()
    if st.session_state.processado:
        if st.session_state.tipo_detectado=="ecd": _render_resultados_ecd(exibir_log)
        else: _render_resultados_lote(exibir_log)

if __name__=="__main__":
    main()
