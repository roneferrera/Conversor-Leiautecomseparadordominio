
    entrada coding: utf-8 -*-
import os
import re
import gc
import io
import time
import traceback
importsar_streaming(conteudo: bytes, ni: str, log: list) -> tuple:
    saida_buf = io.StringIO(); saida_buf.write(fmt_reg_0000(ni)+"\n")
    pendente = None; num_lote_g = 0; usa_inicia = None
    resumo: list = []; erros: list = []; total_lins = 0; ignoradas = 0
    enc_final = "utf-8"; chunk_count = 0
    for chunk_df, enc in ler_txt_streaming(conteudo):
        enc_final = enc; total_lins += len(chunk_df); chunk_count += 1
        if usa_inicia is None:
            usa_inicia = bool((chunk_df["Inicia Lote"].str.strip() != "").any())
        if pendente is not None and len(pendente) > 0:
            chunk_df = pd.concat([pendente,chunk_df], unicodedata
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime

VERSAO        = "V3.4"
CHUNK_SIZE    = 100_000
WRITE_CHUNK   = 5_000
TOL_VALOR     = 0.005
MAX_UPLOAD_MB = 200

COLS_PADRAO = [
    "Data", "Cód.ignore_index=True); pendente = None
        if usa_inicia:
            inicia = chunk_df["Inicia Lote"].fill Conta Debito", "Cód. Conta Credito", "Valor",
    "Cód. Histórico", "Complemento Histórico", "Inicia Lote",
    "Código Matriz/Filial", "Centro de Custo Débito", "Centro de Custo Crédito",
]

# ═══════════════════════════════════════════════════════════════════════════════
# TEMA
# ═══════════════════════════════════════════════════════════════════════════════
def apply_theme():
    st.markdown("""
    <style>
    htmlna("").astype(str).str.strip()
            marcador = (inicia != "").to_numpy(,body,[class*='css']{font-family:'dtype=bool)
            chunk_df["_num_lote"] = np.cumsum(marcador,dtypeSegoe UI',Arial,sans-serif;color:#E8ECF0;}
    .stApp{background-color:#0=np.int32)+num_lote_g
        else:
            cd_tmp = limA0E1A;}
    h1,h2,h3{color:#FF6B00;font-weight:700;}
    section[data-testid='stSidebar']{background-color:#0D1526par_contas_vec(chunk_df["Cód. Conta Debito"])
            cc_tmp = limpar_contas_vec(chunk_df["Cód. Conta Credito"])
            amb;border-right:2px solid #1A3050;}
    section[data-os_tmp = (cd_tmp != "") & (cc_tmp != "")
            if ambos_tmp.all():
                chunk_df["_num_lote"] =testid='stSidebar'] *{color:#E8ECF0 !important;}
    .stButton> np.arange(num_lote_g+1,num_lote_g+len(chunk_df)+1,dtype=np.int32)button{background-color:#FF6B00;color:#fff;border:none;border-radius:4px;font-weight:bold;}
    .stButton>button
            elif ambos_tmp.any():
                desc = chunk_df["Complemento Histórico"].fillna("").:hover{background-color:#CC5500;color:#fff;}
    .stDownloadButton>button{background-color:#FFastype(str).str.strip().str.upper().str.replace(r"\s+"," ",regex=True)
                chave = (chunk_df["Data"].fillna("").astype(str).str.strip()+"|||6B00;color:#fff;border:none;border-radius:4px;font-weight:bold;}
    .stDownloadButton>button:hover{background-color:#CC5500;}
    hr"+desc).to_numpy()
                muda = np.empty(len(ch{border-color:#FF6B00;}
    [data-testid='metric-container']{background-color:#102040ave),dtype=bool); muda[0]=True; muda[1:]=chave[1;border-left:4px solid #FF6B00;border-radius:4px;padding:10px;}
    .st:]!=chave[:-1]
                chunk_df["_num_lote"] = np.cumsum(muda|ambos_tmp,dtype=npProgress>div>div>div>div{background-color:#FF6B00 !important;}.int32)+num_lote_g
            else:
                desc = chunk_df["Complemento Histórico"].fillna("").astype(str).str.strip().str.upper().str.replace(r"\
    .bloco-log{background:#060B14;border:1px solid #1A3050;border-radius:6px;padding:14px;
               font-family:s+"," ",regex=True)
                chave = (chunk_df["Data"].fillna("").astype(str).str.strip()+"|||"+desc).to_numpy()
                muda = np.empty(len(chave),Consolas,monospace;font-size:12px;white-space:pre-wrap;
               max-height:520px;overflow-y:auto;color:#E8ECF0;}dtype=bool); muda[0]=True; muda[1:]=chave[1:]!=chave[:-1]
                chunk_df["_num_lote"] = np.cumsum(muda,
    .badge-ecd{background:#1a0a2dtype=np.int32)+num_lote_g
        ultimo_lote = int(chunk_df["_num_lote"].max())
        maske;color:#F472B6;font-weight:700;padding:6px 14px;
               border-radius:6_ultimo = chunk_df["_num_lote"] == ultimo_lote
        pendente = chunk_df[mask_ultimo].copy()
        chunk_procpx;border:1px solid #F472B6;display:inline-block;}
    .badge-excel{background:#0a = chunk_df[~mask_ultimo]; del chunk_df
        for nl, grupo in chunk_proc.groupby("_num_lote",sort=True):
            _flush_lote(grupo,int(nl),saida_buf,resumo,erros)2e1a;color:#00C896;font-weight:700;padding:6px 14px;
                 border-radius:6px;border:1px solid #00C896;display:inline-block;}
    .badge-lote{background:#2
        num_lote_g = ultimo_lote-1; del chunk_proc
        if chunk_counte2a0a;color:#FFD166;font-weight:700;padding:6px 14px % 5 == 0: gc.collect()
    if pendente is not None and len(pendente) > 0:
        num;
                border-radius:6px;border:1px solid #FFD166;display:inline-block;}
    .badge-pos{background:#0a1a2_lote_g += 1; _flush_lote(pendente,num_lote_g,saida_buf,resumo,erros); del pendente
    gce;color:#6EC6FF;font-weight:700;padding:6px 14px;
               border-radius:6px;.collect()
    log.append(f"  Linhas lidas      : {total_lins:,}")
    log.appendborder:1px solid #6EC6FF;display:inline-block;}
    .header-box{background:#102040;padding:20px (f"  Lotes processados : {len(resumo):,}")
    log.append(f"  Lotes OK          : {len(resum24px 14px;border-radius:8px;
                border-topo)-len(erros):,}")
    log.append(f"  Lotes com erro    : {len(erros):,}")
    saida_bytes:5px solid #FF6B00;margin-bottom:20px;}
    .cnpj-box{background:#0D1526;border = saida_buf.getvalue().encode("utf-8-sig"); del saida_buf
    return saida_bytes, resumo, erros,:1px solid #1A3050;border-radius:8px;
              padding:16px 20px;margin:10px 0  total_lins, ignoradas, enc_final

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO16px 0;}
    .cnpj-auto{background:#0a2e1a;border:1px solid #00C896;border-radius:8px EXCEL — inalterado
# ═══════════════════════════════════════════════════════════════════════════════
_COLS_ESP_LOW = [c.lower() for c in COLS;
               padding:12px 18px;margin:10px 0 16px 0;color:#00C896;font-weight:700;}_PADRAO[:8]]

def detectar_cabecalho_excel(conteudo: bytes,
    .cnpj-auto span{color:#FFD166;}
    .info-box{background:#102040;border-left sheet: str) -> tuple:
    buf = io.BytesIO(conteudo)
    raw = pd.read_excel(:4px solid #FF6B00;border-radius:4px;
              padding:12px 16px;margin:8px 0;font-size:13px;}buf,sheet_name=sheet,header=None,nrows=25,engine="openpyxl")
    pasta = None
    .card-ok{background:#0a2e1a;border:2px solid #00C896;border-radius:10px;padding:18px 
    try:
        v = str(raw.iloc[1,6]).strip()
        if v and v.24px;margin:12px 0;}
    .card-err{background:#2e0a0a;border:2px solid #FF4lower() not in ("nan","none",""): pasta = v
    except:444;border-radius:10px;padding:18px 24px;margin:12px 0;}
    .card-warn{background:#1a1000;border- pass
    for i, row in raw.iterrows():
        vals = [str(v).strip().left:4px solid #FFD166;border-radius:4px;padding:10px 16px;margin:8px 0;}
    .filial-box{background:#0lower() for v in row if not eh_vazio(v)]
        if sum(1 for ca1a2e;border:1px solid #6EC6FF;border-radius:8px;
                padding:14px 18 in _COLS_ESP_LOW if c in vals) >= 4: return i, pasta
    return 3px;margin:10px 0;}
    </style>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════, pasta

def ler_excel_lote(conteudo: bytes, sheet: str, linha_h: int)════════════
# CRONÔMETRO
# ═══════════════════════════════════════════════════════════════════════════════
class Cronometro:
    def __init__(self): -> tuple:
    buf = io.BytesIO(conteudo)
    raw = pd.read_excel(buf,sheet_name=sheet,header=None,dtype=str,engine
        self._inicio_total=0.0; self._et="openpyxl")
    pasta = "C:\\Temp"
    try:
        vapas=[]; self._inicio_etapa=0.0; self._etapa_atual="" = str(raw.iloc[1,6]).strip()
        if v and v.lower() not in ("nan","none",""): pasta = v
    except: pass
    while
    def iniciar(self):
        self._inicio_total=time.perf_counter(); self._etapas. raw.shape[1] < len(COLS_PADRAO)+2: raw[rawclear()
    def etapa(self,nome):
        agora=time.perf_counter()
        if.shape[1]] = ""
    raw.columns = range(raw.shape[1])
    df = raw.iloc[ self._etapa_atual:
            self._etapas.append({"nome":self._etapa_atual,"segundos":round(linha_h+1:].reset_index(drop=True).copy(); del raw;agora-self._inicio_etapa,3)})
        self._etapa_atual=nome; self._inicio_etapa=agora
    def enc gc.collect()
    df.columns = list(range(df.shape[1]))
    df = df.rename(columns={i:cerrar(self):
        agora=time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({"nome":self._etapa_atual,"segund for i,c in enumerate(COLS_PADRAO)})
    _V = {"nanos":round(agora-self._inicio_etapa,3)})
            self._etapa_atual=""
        return round(agora-self._inicio","NaN","None","none",""}
    for c in COLS_PADRAO:
        if c in df.columns: df[c] = df_total,3)
    @staticmethod
    def fmt(s):
        if s<0.[c].fillna("").astype(str).str.strip().replace(list(_V),"")001: return "<1ms"
        if s<1: return f"{s*1000:.0f}ms"
        if s<60
    mask = ~((df["Data"]=="")&(df["C: return f"{s:.2f}s"
        m=int(s//60); return f"{m}min {s%60:.1f}s"ód. Conta Debito"]=="")&(df["Cód. Conta Credito"]=="")&(df["Valor"]==""))
    df = df[mask].reset
    @property
    def etapas(self): return self._etapas

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS_index(drop=True).copy()
    df["_linha_origem"] = (df.index+linha_h+2 — NORMALIZAÇÃO DE HISTÓRICO
# ═══════════════════════════════════════════════════════════════════════════════
_).astype(np.int32)
    return df, pasta

def montar_lotes_excel(df: pd.DataFrame) -> tupleMAPA_ESPECIAIS = {
    "\u2018":":
    R = df.copy()
    for col in COLS_PADRAO+["_linha_origem"]:
        if col not'",  "\u2019":"'",  "\u201C":'"',  "\u201D":'"',
    "\u2013":"-",  "\u2014":"-",  "\u2 in R.columns: R[col] = ""
    inicia = R["Inicia Lote"].fillna("").astype(str).str.strip()
    tem_ini026":"...","\u00A0":" ",
    "\u00D = bool((inicia != "").any())
    if tem_ini:
        marcador = (inicia != "").to_numpy(dtype=bool)
        R["_num_lote"] = np7":"x",  "\u00F7":"/",  "\u20AC":"EUR","\u00A7.where(np.cumsum(marcador)>0,np.cumsum(marcador,dtype=np.int32),np":"S/",
    "\u00AE":"(R)","\u00.int32(1))
    else:
        cd_tmp = limpar_contas_vec(R["Cód. Conta DebA9":"(C)","\u2122":"(TM)",
    "\u00C0":"A","\u00C1":"ito"])
        cc_tmp = limpar_contas_vec(R["Cód. Conta Credito"])
        ambos_tmp = (cd_tmp != "") & (cc_tmp != "")
        if ambos_tmpA","\u00C2":"A","\u00C3":"A","\u00C4":"A","\u00C5":"A",
    "\u00E0":"a.all():
            R["_num_lote"] = np.arange(1,len(R)+1,dtype=np.int32)
        elif ambos_tmp.any():
            desc = R["Complemento Histórico","\u00E1":"a","\u00E2":"a","\u00E3":"a","\u00E4":"a","\u00E5":"a",
    "\u00C8"].fillna("").astype(str).str.strip().str.upper().str.replace(r"\s+"," ",regex=True)
            chave = (R["Data"].fillna("").astype(str).str.strip()+"":"E","\u00C9":"E","\u00CA":"E","\u00CB":"E",
    "\u00E8":"e","\u00E|||"+desc).to_numpy()
            muda = np.empty(len(chave),dtype=bool); muda[0]=True; muda[1:]=chave[1:]!=chave[:-1]
            R["_9":"e","\u00EA":"e","\u00EB":"e",
    "\u00CC":"I","\u00CD":"I","\u00CE":"I","\u00CF":"Inum_lote"] = np.cumsum(muda|ambos_tmp,dtype=np.int32)
        else:
            desc = R["Complemento Histórico"].fillna("").astype(str).str.strip().",
    "\u00EC":"i","\u00ED":"i","\u00EE":"i","\u00EF":"i",
    "\u00D2str.upper().str.replace(r"\s+"," ",regex=True)
            chave = (R["Data"].fillna("").astype(str).str.strip()+"|||"+desc).to_numpy()
            muda = np":"O","\u00D3":"O","\u00D4":"O","\u00D5":"O","\u00D6":"O",
    "\u00F2":"o.empty(len(chave),dtype=bool); muda[0]=True; muda[1:]=chave[1:]!=chave[:-1]
            R["_num_lote"] = np.cumsum(muda,","\u00F3":"o","\u00F4":"o","\u00F5":"o","\u00F6":"o",
    "\u00D9":"Udtype=np.int32)
    return R, "Inicia Lote" if tem_ini else "Data + Descri","\u00DA":"U","\u00DB":"U","\u00DC":"U",
    "\u00F9":"u","\u00FA":"u","\u00FB":"u","\u00ção"

def processar_excel(df: pd.DataFrame, ni: str, log: list) -> tuple:
    saida_buf = io.StringIO(); saida_buf.FC":"u",
    "\u00DD":"Y","\u00FD":"y","\u00FF":"y",
    "\u00Cwrite(fmt_reg_0000(ni)+"\n")
    resumo: list = []; erros: list = []
    for nl, grupo in df.groupby7":"C","\u00E7":"c",
    "\u00D1":"N("_num_lote",sort=True):
        _flush_lote(grupo,int(nl),saida_buf,resumo,erros)
    gc.collect()
    log.append(f"  L","\u00F1":"n",
    "\u00BA":"o","\u00AA":"a",
    "\u00B0":"o",
    "\u00BD":"1/2","\u00BC":"1/4","\u00BEotes processados : {len(resumo):,}")
    log.append(f"  Lotes OK          : {len(resumo)-len(erros):,}")
    log.append(f"  Lotes com erro    :":"3/4",
    "\u0131":"i","\u00DF":"ss", {len(erros):,}")
    saida_bytes = saida_buf.getvalue().encode("utf-8-sig"); del saida_buf
    return saida_bytes, resumo, erros

def _montar_log_lote(resumo, erros, ni, ti, inf
}

def _norm_hist(texto: str) -> str:
    if not texto:
        return ""
    for orig, dest in _MAPA_ESPECIAIS.items():
        texto = texto.replace(orig, dest)
    texto = unic, n_gravados, ignoradas, enc, crono):
    tdodedata.normalize("NFC", texto)
    res = []
    for ch in texto:
        cp = ord(ch)
        if cp < 0x20 and cp != = sum(v["total_debito"] for v in resumo); tc = sum(v["total_credito"] for v in 9:
            continue
        if ch == "|":
            res.append(" ")
             resumo)
    ok = len(resumo)-len(erros)
    conc = "SUCcontinue
        try:
            ch.encode("latin-1")
            res.append(ch)
            continue
        except UnicodeESSO" if not erros else f"ATENÇÃO — {len(erros)} lote(s) desbalEncodeError:
            pass
        decomposto = unicodedata.normalize("NFD", ch)
        base = decomposto[anceado(s)"
    SEP = "═"*90; sep20]
        try:
            base.encode("latin-1")
            res.append(base)
            continue
        except UnicodeEncodeError:
            pass
        nome = "─"*90
    L = [SEP,"  DOMÍNIO SISTEMAS  |  Thomson Reuters","  LOG DE VALIDAÇÃO — = unicodedata.name(ch, "")
        if "LATIN" in nome:
            partes = nome.split()
            for i LANÇAMENTOS CONTÁBEIS",SEP,
         f"  Data, p in enumerate(partes):
                if p == "LETTER" and i + 1 < len(partes):
                    letra = partes[i + /Hora     : {ts_log()}",f1]
                    if len(letra) == 1:
                        res.append(letra.lower() if "SMALL"  Encoding leit.: {enc or 'N/A'}",
         f"  {ti" in nome else letra.upper())
                        break
    return re.sub(r" {2,}", " ", ":<6}         : {inf}",SEP,"".join(res)).strip()[:250]


def sanitizar_texto(t","  RESUMO GERAL",sep2,
         f"  Lotes total: str) -> str:
    return _norm_hist(str(t) if t else "")

def formatar_data(v   : {len(resumo):>10,}",f"  Lotes OK      : {ok:>10,}",
         f"  Lotes):
    try:
        if isinstance(v, (datetime, pd.Timestamp)): return v.strftime("%d/%m/%Y") ERRO    : {len(erros):>10,}",f"  Reg. 6000+6
        return pd.to_datetime(v, dayfirst=True).strftime("%d/%m/%Y")
    except: return str(v)

def100: {n_gravados:>10,}",
         f"  Ignoradas     : {ignoradas:>10,}",f"  Total Déb.     eh_vazio(v):
    if v is None: return True
    try:
        if pd.isna(v): return True
    : R$ {td:>14.2f}",
         f"  Total Créd.   : R$ {tc:>14.2f}",f"  Conclusexcept: pass
    return str(v).strip() in ("", "nan", "NaN", "None")

def tsão     : {conc}",""]
    if crono and crono.et_log(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def so_nums(v): return reapas:
        total_seg = sum(e["segundos"] for e in crono.etapas)
        L +=.sub(r"\D", "", str(v))

_VAZIO_CONTA = frozenset((" [sep2,"  RELATÓRIO DE TEMPO",sep2]
        for", "nan", "none", "0", "0.0"))

def limpar_contas_vec(serie e in crono.etapas: L.append(f"  {'  '+e['nome']:<38}):
    arr = serie.fillna("").astype(str).str.strip().str.lower().to_numpy()
    out = np {Cronometro.fmt(e['segundos']):>8}").where(np.isin(arr, list(_VAZIO_CONTA)), "", arr)
    mask = out != ""
    if mask.any():
        vals
        L += ["  "+"─"*46,f"  {' = out[mask]; conv = np.empty(len(vals), dtype=object)
        for i, v in enumerate(vals  TOTAL':<38} {Cronometro.fmt(total_seg):>8}",""]
    L += [sep2,f"  {'Lote):
            try: conv[i] = str(int(float(v.replace(",", "."':<8}{'Linhas':<16}{'Data':<13}{'Qt))))
            except: conv[i] = v
        out[mask] = conv
    return out

def limpar_valor_vec(serie):
    return (d':<6}{'Débito':>15}{'Crédito':>15}{'Diferença':>13}  pd.to_numeric(
        serie.fillna("0").astype(str).str.strip()
             .str.replace(",", "Status","  "+"─"*88]
    for v in resumo:
        L.append(f"  {str(v['.", regex=False)
             .str.replace(r"[^\d.\-]", "", regex=True),num_lote']):<8}{v['faixa_linhas']:<16}{v['data']:<13}{str(v['qt
        errors="coerce").fillna(0.0).round(2).to_numpy(d_linhas']):<6}"
                 f"R$ {v['total_debito']:>12.2f}  R$ {v['totaldtype=np.float64))

def validar_cnpj(cnpj):
    c = so_nums(cnpj)_credito']:>12.2f}  R$ {v['diferenca']:>10.2f}   "
                 f"{'✔ OK' if v['balanceado
    if len(c) != 14 or len(set(c)) == 1: return False
    def d'] else '✖ ERRO'}")
    L += ["  "+"─"*88,f"  {'TOTAIS':<37(c, p):
        s = sum(int(c[i]) * p}R$ {td:>12.2f}  R$ {tc:>12.2f}","",
          SE[i] for i in range(len(p))); r = s % 11; return 0P,f"  Fim  │  {ts_log()}",f if r < 2 else 11 - r
    return (int(c[12]) == d(c, ["  Resultado │  {conc}",SEP]
    return "\n".join(L)

# ═══════════════════5,4,3,2,9,8,7,6,5,4,3,2]) and
            int(c[13]) == d(c,════════════════════════════════════════════════════════════
# ███████████████████████████████████████████████████████████████████████████████
# [6,5,4,3,2,9,8,7,6,5,4,3,2]))

def validar_cpf(cpf):
    c MÓDULO DOMÍNIO TXT POSICIONAL — V3 = so_nums(cpf)
    if len(c) != 11 or len(set(c)) == 1: return False
    def d(c, n):
        s = sum(int(c[i]) *.3  ← CORREÇÃO FINAL
# ███████████████████████████████ (n - i) for i in range(n - 1)); r = (s *████████████████████████████████████████████████
# ═══════════════════════════════════════════════════════════════════════════════

def _extrair_filial 10) % 11; return 0 if r == 10 else r
    return int(c[9]) == d(c, 10(linha: str) -> str:
    """
    Extrai o código da filial do Reg ) and int(c[10]) == d(c, 11)

def validar_inscricao(v):
    n = so_nums(v)
    if len(n)03, posições 558-564 (1 == 14 and validar_cnpj(n): return True, "CNPJ", n
    if len(n) == 11 and valid-based) = [557:564].
    Removear_cpf(n):  return True, "CPF", n
    return False, "", n

def fmt_cnpj(n zeros à esquerda. "0000000"):
    c = so_nums(n)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12 ou "0" → "" (matriz).
    Ex: "0000257" → "257"
    """
    if len]}-{c[12:]}" if len(c) == 14 else n

def fmt_cpf(n):
    c = so(linha) < 564: return ""
    raw = linha[557:564].strip()
    if not raw or not raw.isdigit(): return_nums(n)
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else n

def fmt_ ""
    codigo = str(int(raw))
    return "" if codigo == "0" else codigo

def _extrair_ccreg_0000(ni: str) -> str:(raw: str) -> str:
    """Remove zeros à esquerda de um campo CC de 7 chars."""
    raw = raw.strip()
    if not raw or not raw.isdigit(): return ""
    codigo return f"|0000|{ni}|"
def fmt_reg_6000(tp: str) -> str: return f"|6000|{tp}||||"

def _fmt_valor_layout(valor = str(int(raw))
    return "" if codigo == "0" else codigo

def _posicional_para_decimal(val) -> str:
    if isinstance(valor, (int, float)): return f"{float(valor):.2f}".replace_raw: str) -> float:
    """Campo de 15 chars com(".", ",")
    v = str(valor).strip()
    if "." in v and "," in v:
        if v.index(".") < v.index(","): v = v.replace(".", " 2 casas decimais implícitas (sem separador)."""
    val_raw = val_raw.strip()
    if not val_raw or not val_raw.isdigit(): return 0.0
    val_raw = val_raw.zfill(3)
    try").replace(",", ".")
        else: v = v.replace(",", "")
    elif "," in v: v = v.: return float(f"{int(val_raw[:-2])}.{val_raw[-2:]}")
    except: return 0.0

def _replace(",", ".")
    try: return f"{float(v):.2f}".replace(".", ",")
    except ValueError: return "parse_posicional(conteudo: bytes, log: list) -> dict:
    """
    Parser do0,00"

def fmt_reg_6100(data, d TXT posicional Domínio — V3.3 FINAL.

    eb, cred, valor, codREGRA DE VÍNCULO Reg 05 →_hist="", desc="", _u="", _f="", _s=""):
    return f"|6100|{data}|{deb}| Reg 03:
        Cada Reg 05 pertence ao Reg 03 que o prec{cred}|{_fmt_valor_layout(valor)}||{_norm_hist(desc)}|||ede IMEDIATAMENTE no arquivo.
        O campo "idx||||"

_CHARS_PT = set("ÀÁÂ" é calculado ANTES do append do Reg 03 eÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ gravado na partida.
        O Reg 05 usa lØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýote_atual["partidas"][-1]["idx"] —þÿºª")

def _detectar_encoding_bytes(con o índice da última
        partida inserida no momento da leitura doteudo: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1 Reg 05.
        NÃO há filtragem por tipo"):
        try:
            texto = conteudo.decode(enc, errors="strict")
            if sum(1 for c in texto[: de CC — fidelidade total ao arquivo.
    """
    enc4096] if c in _CHARS_PT) > 0 or enc in = _detectar_encoding_bytes(conteudo)
    log.append(f"  Encoding detectado : {enc}")
    try: texto = conteudo.decode(enc, errors="replace") ("utf-8-sig", "utf-8"):
                return enc
        except (UnicodeDecodeError, LookupError): continue
    return "latin-1"

#
    except: texto = conteudo.decode("utf-8", errors="replace")

    linhas = texto.splitlines()
    log.append(f"  Total de ═══════════════════════════════════════════════════════════════════════════════
# IDENTIFICAÇÃO DE TIPO
# ═══════════════════════════════════════════ linhas    : {len(linhas):,}")

    cabecalho = {}
    lotes: list = []
    lote_atual =════════════════════════════════════
def identificar_tipo(nome_arquivo: str, conteudo: bytes) -> str:
    ext = os.path.splitext None
    erros: list = []
    filiais_set: set = set()
    cnt(nome_arquivo)[1].lower()
    if ext in (".xlsx", ".xls", ".xlsm"): return "excel"
    enc = _detectar_encoding_ = {"01":0,"02":0,"03":0,"05":0,"08bytes(conteudo)
    try: amostra = conteudo[:8192].decode(enc, errors="replace":0,"99":0,"outro":0}

    for num_linha, linha in enumerate(linhas, ")
    except: amostra = ""
    linhas = [l for l in amostra.splitlines() if l.strip()]
    for1):
        if len(linha) < 2: continue
        reg = linha[:2]
        try ln in linhas[:40]:
        if ln.startswith("|0000|"):
            if reg == "01":
                cnt["01"] += 1
                cabecalho = { or ln.startswith("|I0"): return "ecd"
        campos = ln.split("|")
                    "cod_empresa": linha[2:9].strip(),
                    "cnpj":        linha[9:23
        if len(campos) >= 2 and campos[1] in (
            "0000","].strip(),
                    "dt_ini":      linha[23:33].strip(),
                    "dt_fin":      linha[33:43I010","I050","I075","I100","I150","I155","I200","I250].strip(),
                    "tipo_nota":   linha[44:46].strip() if","I350","I355","I990"
        ): return "ecd"
    for ln in linhas[:15 len(linha) > 45 else "",
                }
                log.append(f"  Cabeçalho — Empresa]:
        s = ln.rstrip("\r\n")
        if len(s) >= 54 and s[:2: {cabecalho['cod_empresa']} "
                           f"| CNPJ: {cabecalho['cnpj']} "
                           f"|] == "01" and s[43:44] == "N":
            return "dominio_pos"
        if len(s) >= 20 and s[:2] == "02" and s[9:10] in Período: {cabecalho['dt_ini']} a {cabecalho['dt_fin']}")

            elif reg == "02":
                cnt["02"] += 1
                tipo ("X","D","C","V"):
            return "dominio__lanc = linha[9:10].strip().upper()
                data_lanc = linha[10:20pos"
    semis = sum(1 for ln in linhas[:20].strip()
                usuario   = linha[20:50].strip()
                if tipo_lanc not in ("X","D] if ";" in ln)
    if semis >= max(1, len(linhas[:20]) // 2): return "","C","V"): tipo_lanc = "X"
                lote_atual = {
                    "seq":      linha[2:9].strip(),
                    "tipo":     tipo_lanc,
                    "data":     lote"
    return "lote"

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO SPED ECD
# ═══════════════════════════════════════════════════════════════════data_lanc,
                    "usuario":  usuario,
                    "partidas": [],
                    "centros":  [],
                }
                lotes════════════
def _split_pipe(linha: str) -> list:
    c = linha.strip.append(lote_atual)

            elif reg == "03":
                cnt["03"] += 1
                if lote_atual is None:
                    er().split("|")
    if c and c[0] == "": c = c[1:]
    if c and c[-1] ==ros.append({"linha":num_linha,"motivo":"Reg 03 sem Reg 02 anterior"," "": c = c[:-1]
    return c

def _campo(campos: list, idx: int, default: str = "") -> str:conteudo":linha[:80]})
                    continue

                cta_d
    return campos[idx].strip() if idx < len(campos) else default

def _conta_valida(conta: str) -> bool:
    returneb   = linha[9:16].strip()
                cta_cred  = linha[16:23 bool(conta) and conta.isdigit()

class Sp].strip()
                val_raw   = linha[23:38].strip()
                cod_hist  = linha[38:45].strip()
                historico = linha[45:557edECD:
    def __init__(self):
        self.cnpj = ""; self.contas = {}].strip() if len(linha) > 45 else ""

                # Filial: pos 558-564 (índ; self.historicos = {}; self.lancamentos = []

def _parseices 557:564)
                filial_p = _extrair_filial(linha)
                if filial_p: filiais_set.add(_ecd(conteudo: bytes, log: list) -> tuple:
    ecd = SpedECD()
    lfilial_p)

                if cta_deb  in ("0000000","0",""): cote_atual = None
    erros_parse = 0;ta_deb  = ""
                if cta_cred in ("0000000","0",""): cta_cred = ""

                valor_dec = _posicional_para registros_erro = []; contas_invalidas = 0
    i_decimal(val_raw)
                hist_norm = _norm_hist(historico)

                # Índice pos200_count = 0; i250_count = 0
    enc = _detectar_encoding_bytes(conteudo)icional único — calculado ANTES do append
                idx_partida = len(lote_atual["partidas"])
    log.append(f"  Encoding detectado : {enc}")
    try: texto = conteudo.decode(

                lote_atual["partidas"].append({
                    "idx":      idx_partida,
                    "seq":      linha[2:9].strip(),
                    "cenc, errors="replace")
    except: texto = conteudo.decode("utf-8", errors="replace")
    linhas = texto.splitlines()
    log.appendta_deb":  cta_deb,
                    "cta_cred": cta_cred,
                    "valor":    valor_dec,
                    "cod_hist": cod_hist,(f"  Total de linhas    : {len(linhas):,}")
    for num, linha in enumerate(linhas, 1):
        linha
                    "hist":     hist_norm,
                    "filial":   filial_p,
                })

            elif reg == "05":
                cnt["05"] += _orig = linha; linha = linha.strip()
        if not linha: continue
        campos = _split_pipe(linha)
        if1
                if lote_atual is None:
                    erros.append({"linha":num_linha,"motivo":"Reg 05 sem Reg 02 anterior","conteudo":linha[:80]})
                 not campos: continue
        reg = campos[0]
        try:
            if reg == "0000":
                if    continue
                if not lote_atual["partidas"]:
                    erros.append({"linha":num_linha,"motivo":"Reg 05 sem Reg len(campos) > 5: ecd.cnpj = _campo(campos, 5)
            elif reg == "I 03 anterior no lote","conteudo":linha[:80]})
                    continue

                cc_deb_raw  050":
                cod = _campo(campos, 5); nome = _campo(campos, 7= linha[9:16]  if len(linha) > 15 else "0000000"
                cc_cred_raw = linha[16:23])
                if cod: ecd.contas[cod] = nome
            elif reg == "I075":
                cod = _campo(campos, 1); desc = _campo(campos,  if len(linha) > 22 else "0000000"
                val_raw5    = linha[23:38].strip()2)
                if cod: ecd.historicos[cod] = _norm_hist(desc)
            elif reg == "I200":
                lote_ if len(linha) > 37 else "0"

                cc_deb  = _extrair_cc(cc_deb_raw)
                cc_cred =atual = {
                    "num": _campo(campos, 1), "data": _campo(campos, 2),
                    "valor": _campo(campos,  _extrair_cc(cc_cred_raw)
                valor_c = _posicional_para_decimal(val_raw5)

                # Vínculo:3), "partidas": [],
                }
                ecd.lancamentos.append(lote_atual); i última partida inserida antes deste Reg 05
                idx_pai = lote_atual["partidas"][-1]["idx"]

                200_count += 1
            elif reg == "I250":
                if lote_atual is None:
                    registros_erro.append({"lote_atual["centros"].append({
                    "seq":         linha[2:9].strip(),
                    "cc_deb":      cc_deb,
                linha": num, "motivo": "I250 sem I200", "conteudo": linha_orig.    "cc_cred":     cc_cred,
                    "valor":       valor_c,
                    "idx_partida": idx_pai,
                })

            elif reg == "08strip()}); continue
                conta = _campo(campos, 1); valor_str = _campo(campos, 3)
                dc = _campo(campos, 4).upper()
                descr_hist = _norm_hist(_campo(campos, 7))
                if dc not in ("D", "C"):": cnt["08"] = cnt.get("08",0)+1
            elif reg == "99": cnt["99"] += 1
            else: cnt["outro"] += 1

        except Exception as ex:
            erros.append({"linha":num_linha,"motivo":str(ex),"conteudo":linha[:80]})

    log.append(f"  Reg 01 (cabeçalho) :
                    registros_erro.append({"linha": num, "motivo": f"IND_DC='{dc}' inválido", "conteudo": linha_orig.strip()}); continue
                if not _conta_valida(conta):
                    registros_erro.append({"linha": num, "motivo": f" {cnt['01']}")
    log.append(f"  Reg 02 (lotes)     : {cnt['02']:Conta '{conta}' inválida", "conteudo": linha_orig.strip()})
                    contas_invalidas += 1; continue
                lote_atual["partidas"].append({"conta":,}")
    log.append(f"  Reg 03 (partidas)  : {cnt['03']:,}")
    log.append(f"  Reg 05 (c.custos)  : {cnt['05']:,}")
    log.append(f"  Reg 08 (informativo): conta, "valor": valor_str, "dc": dc, "descr_hist": descr_hist})
                i250_count += 1
            elif reg in ("I299 {cnt.get('08',0):,}")
    if erros: log.append(f"  Erros/avi", "I300"):
                lote_atual = None
        except Exception as ex:
            registsos       : {len(erros):,}")

    filiais_encontradas = sorted(filiais_set,ros_erro.append({"linha": num, "motivo": f"Exceção: {ex}", "conteudo": linha_orig.strip()})
             key=lambda x: int(x) if x.isdigit() else x)
    if filiais_encontradas: log.append(f"  Filiais detecterros_parse += 1
            if erros_parse > 50: log.append("ERRO: muadas : {filiais_encontradas}")

    return {"cabecalho":cabecalho,"lotes":lotes,"erros":erros,"filiais_itos erros — abortando."); return None, registencontradas":filiais_encontradas}


def _aplicar_de_para(filialros_erro
    if not ecd.cnpj:
        log.append("ERRO: CNPJ não encontrado no registro 0000.: str, mapa: dict) -> str:
    if not filial: return ""
    return mapa.get(filial"); return None, registros_erro
    log.append(f"  CNPJ               : {ecd.cnpj}")
    log.append(f"  Lanç, filial)


def _gerar_saida_posicional(parsed: dict, ni: str, gamentos (I200) : {i200_count:,}")
    log.append(f"  Partidas (I250)    : {i250_count:,}")
    iferar_6110: bool,
                             usar_de_para: bool, mapa_ contas_invalidas: log.append(f"  Contas inválidas   : {contas_invalidas:,}")
    if registros_erro:   log.append(f"  filiais: dict,
                             log: list) -> bytes:
    """
    Geração daErros/avisos       : {len(registros_erro):,}")
    return ecd, registros_erro

def _fmt_data saída — V3.3 FINAL.

    REGRAS DE FIDELIDADE AO ARQUIVO:
        _ecd(d: str) -> str:
    d = d.strip()
    if "/" in d:• Vinculação Direta: o 6110 só return d
    if len(d) == 8 and d.isdigit(): return f"{d[:2 existe se o Reg 05 correspondente
          existir no arquivo para aqu]}/{d[2:4]}/{d[4:]}"
    return d

def _str2float(vela partida (idx).
        • Independência: emite cc_deb e cc_cred exatamente como estão
          no arquivo, mesmo que apenas um lado est) -> float:
    if isinstance(v, (int, float)): return float(v)
    v = str(v).strip()
    if "." in v and "," in v:eja preenchido.
        • Fidelidade: replica o arquivo de origem sem
        if v.index(".") < v.index(","): v = v.replace(".", "").replace(",", ".")
        else: v = v.replace(",", "")
    elif filtros por tipo de CC.
        • Sem contrapartida automática: se "," in v: v = v.replace(",", ".")
    try: return float(v)
    except: return 0.0

def _montar_hist_ecd(p o arquivo não informou um lado,
          o registro não é gerado.: dict) -> str: return p.get("descr_hist", "").strip()
def _primeiro_hist
        • O 6110 é emitido IMEDIATAMENTE após o 6(partidas: list) -> str:
    for p in partidas:
        h = _montar_hist_ecd(p)
        100 pai.
    """
    buf = io.StringIO()
    buf.write(f"|0if h: return h
    return ""

def _classif(nd: int, nc: int)000|{ni}|\n")

    lotes = parsed["lotes"]
    ok -> str:
    if nd == 1 and nc == 1: return "X"
    if nd == 1 and nc > = ignorados = 0
    cnt = {"t6000":0,"t6100":0,"t6110":0 1:  return "D"
    if nd > 1  and nc == 1: return "C"
    return "V"

def tipo_lanc}
    debug = {"X":0,"D":0,"C":0,"V":0}
    _amento(nd, nc): return _classif(nd, nc)

def _linhas_ecd(lanc: dictnulos = {"","0","0000000"}) -> list:
    partidas = lanc["partidas"]
    debs  = [p for p in partidas if p["dc"] == "D"]
    creds = [p for p in partidas if p["dc"] == "C"]
    if not debs or not creds: return []
    data

    for lote in lotes:
        data     = lote.get("data","")
        partidas = lote.get("partidas",[])
        centros  = lote.get("centros",[])

        if not partidas: ignorados += 1; continue

        debs = _fmt_data_ecd(lanc["data"])
    nd = len(debs); nc = len(creds)
    hist  = [p for p in partidas if p["cta_deb"]  not in _nulos]
        creds = [p for p = _primeiro_hist(partidas)
    out = []
    def so_deb(conta, val in partidas if p["cta_cred"] not in _nulos]

        if not debs or not creds: ignorados += 1; continue

        nd,, h): return fmt_reg_6100(data, conta nc = len(debs), len(creds)
        if   nd == 1 and nc == 1: tipo, "", val, "", h)
    def so_cred(conta, val, h): return fmt_reg_6100(data, "", conta, val, "", h)
    def d_real = "X"
        elif nd == 1 and nc > 1:  tipo_real = "D"
        elif nd > eb_e_cred(conta_d, conta_c, val, h): return fmt_reg_6100(data, conta_1  and nc == 1: tipo_real = "C"
        else:                     tipo_real = "V"

        debug[tipo_real] = debug.get(tipo_real,d, conta_c, val, "", h)
    if nd == 1 and nc == 1:
        db = debs[0]; cr = creds[0]
        h0)+1

        # Índice de centros por partida (chave = = _montar_hist_ecd(db) or _montar_hist_ecd(cr) or hist idx da partida)
        centros_por_partida: dict[int,list] = {}
        for cc in centros:
            idx = cc.
        out.append(fmt_reg_6000("X"))
        out.append(deb_e_cred(db["get("idx_partida",-1)
            if idx >= 0:
                centros_por_partida.setdefault(idx,[]).append(cc)

        def _filconta"], cr["conta"], _str2float(db["valor"]), h))
    elif nd == 1 and nc > 1:
        db = debs[0];ial_p(p: dict) -> str:
            f = p.get("filial","")
            if usar_de_para and mapa_filiais:
                f = _aplicar h = _montar_hist_ecd(db) or hist
        out.append(fmt_reg_6000("D"))
        out.append(so_deb(db["conta_de_para(f, mapa_filiais)
            return f

        def _emite_6110(idx: int):"], _str2float(db["valor"]), h))
        for cr in creds:
            h = _montar_hist_ecd(cr) or _
            """
            Emite os 6110 do idx — SEM NENHmontar_hist_ecd(db) or hist
            out.append(so_cred(cr["conta"], _str2float(cr["valor"]), h))
    elif nd > 1 UM FILTRO por tipo de CC.
            Regras de fidelidade:
              - Sóand nc == 1:
        cr = creds[0]; h = _montar_hist_ecd(cr) or hist
        out.append(fmt_reg_6000("C"))
        out.append(so_cred(cr["conta"], _str2float(cr["valor"]), h))
        for db in debs:
            h = _montar_hist_ecd(db) or _ emite se existir Reg 05 para este idx
              - Emite cc_deb e cc_cred exatamente como estão no arquivo
              - Não filtra, não completa, não espelha
              - Sem contrapartida autommontar_hist_ecd(cr) or hist
            out.append(so_deb(db["conta"], _str2float(db["valor"]), h))
    else:
        out.append(fmt_reg_6000("ática
            """
            if not gerar_6110: return
            for cc in centros_por_partida.get(idx,[]):
                ccV"))
        for cr in creds:
            h = _montar_hist_ecd(cr) or hist
            out.append(so_cred(cr["conta"], _str2float(cr["valor"]), h))_d = cc.get("cc_deb","")
                cc_c = cc.get("cc_cred","")
                v_cc
        for db in debs:
            h = _montar_hist_ecd(db) or hist
            out.append(so_deb(db["conta"], _str2float(db["valor"]), h))
    return out = cc.get("valor",0.0)
                if cc_d or cc_c:
                    v_fmt = f"{v_cc:.

def _gerar_ecd(ecd: SpedECD, log: list, prog_2f}".replace(".",",")
                    buf.write(f"|6110|{ccbar, status) -> list:
    linhas = [fmt_d}|{cc_c}|{v_fmt}|\n")
                    cnt["t6110"] += 1

        def _escreve(d_reg_0000(re.sub(r"\D", "", ecd.cnpj))]
    t6000eb_cta: str, cred_cta: str, valor: float,
                     hist = t6100 = ignorados = 0
    debug = {"X": 0, "D":: str, filial: str, idx: int):
            """Escreve |6100| e im 0, "C": 0, "V": 0}
    total = len(ecd.lancamentos)
    for idx, lanc in enumerate(ecd.ediatamente seus |6110| filhos."""
            valor_fmt = f"{valor:.2flancamentos):
        if idx % 500 == 0 or idx == total - 1:
            prog_bar.progress(min(55}".replace(".",",")
            hist_safe = _norm_hist(hist)
            buf.write(f"|6 + int(((idx + 1) / total) * 35), 99))
            status.100|{data}|{deb_cta}|{cred_cta}|{valor_fmt}||{hist_safe}||{filial}||\n")
            cnt["ttext(f"Gerando lançamento {idx+1:,}/{total:,}...")
        if not6100"] += 1
            _emite_6110(idx)

        # Escreve 6000
        buf lanc.get("partidas"): ignorados += 1; continue
        novas = _.write(f"|6000|{tipo_real}||||\n")
        cnt["t6000"] += 1

        # ──linhas_ecd(lanc)
        if not novas: ignorados += 1; continue
        for l in novas:
            if l.startswith("|6 TIPO X ───────────────────────────────────────────────────────────
        if tipo_real == "000|"):
                t = l.split("|")[2] if len(l.split("|"))X":
            d = debs[0]; c = creds[0]
            h   = d > 2 else "?"
                debug[t] = debug.get(t, 0) + 1; t6000 +=["hist"] or c["hist"]
            fil = _filial_p(d) or _filial_p( 1
            elif l.startswith("|6100|"): t6100 += 1
        linhas.extend(novas)
    logc)
            # Escreve o 6100 com deb+cred e em.append(f"  Reg. 6000 gerados  : {t6000:,ite 6110 do débito
            _escreve(d["cta_deb"], c["cta_cred"], d["valor"], h, fil,}")
    log.append(f"  Reg. 6100 gerados  : {t6100:,}")
    log.append(f"  Ignorados          : {ignorados:,}")
    log.append(f" d["idx"])
            # Se crédito tem idx diferente e  Tipos — X:{debug.get('X',0)} D:{debug.get('D tem centros próprios, emite também
            if gerar_6110 and c["idx"] != d["idx"] and c["idx',0)} C:{debug.get('C',0)} V:{debug.get('V',0)}")
    return linhas

def _txt_erros_ecd(regist"] in centros_por_partida:
                _emite_6110(c["idx"])

        # ── TIPO D ───────────────────────────────────────────────────────────
        elif tipo_ros_erro: list, cnpj: str) -> str:
    linhas = ["="*70,real == "D":
            d = debs[0]
            _escreve(d["cta_deb"],"",d["valor"],d["hist "RELATÓRIO DE ERROS — SPED ECD", f"CNPJ : {cnpj}", f"Total:"],_filial_p(d),d["idx"])
            for c in creds:
                h   = c["hist"] or d["hist"]
                fil = {len(registros_erro)}", "="*70, ""]
    for i, r in enumerate(registros_erro, 1):
        linhas += [f"[ _filial_p(c) or _filial_p(d)
                _escreve("",c["cta_cred"],c["valor"],h,fil,c["idx"]){i:04d}] Linha   : {r['linha']}", f"       Motivo  

        # ── TIPO C ───────────────────────────────────────────────────────────
        elif tipo_real == "C":
            c = creds[0]
            _escreve(": {r['motivo']}", f"       Conteúdo: {r['conteudo']}", ""]
    linhas += ["="*70, "FIM DO RELATÓRIO"]
    return "\n".join(linhas)

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO TXT",c["cta_cred"],c["valor"],c["hist"],_filial_p(c),c["idx"])
            for d in debs:
                h   = d["hist"] or c["hist"]
                fil = _filial_p(d) or _filial_p(c)
                _escreve(d["cta_deb"],"",d["valor"],h,fil,d["idx"])

        # ── TIPO STREAMING
# ═══════════════════════════════════════════════════════════════════════════════
def _filtrar_chunk(chunk: pd.DataFrame) V ───────────────────────────────────────────────────────────
        else:
            for c in creds:
                _escreve("",c["cta_cred"],c -> pd.DataFrame:
    for c in COLS_PADRAO:
        if c not in chunk.columns: chunk["valor"],c["hist"],_filial_p(c),c["idx"])
            for d in debs:
                _escreve(d["cta_deb"],"",d["valor"],d["hist[c] = ""
    for c in COLS_PADRAO: chunk[c] = chunk[c].fillna("").astype(str"],_filial_p(d),d["idx"])

        ok += 1

    log.append(f"  Reg.).str.strip()
    il = chunk["Inicia Lote"].str.strip()
    chunk 6000 gerados  : {cnt['t6000']:,}")
    log.append(f"  Reg. 6100 gerados  ["Inicia Lote"] = il.where(il.str.fullmatch(r"[1-9]\d*"), ": {cnt['t6100']:,}")
    if gerar_6110: log.append(f"  Reg. 6110 gerados  : {cnt['t6110")
    m_data = chunk["Data"] != ""
    datas = pd.to_datetime(chunk.loc[m_data, "Data"], dayfirst=True, errors="coerce")
    m']:,}")
    log.append(f"  Lotes OK           : {ok:,}")
    log.append(f"  Lotes ignorados    : {ignorados:,}")
    log.append(f"  Tipos — X:{debug.get('X',0)}_dv = m_data.copy(); m_dv[m_data] = datas.notna()
    m_conta = ((chunk["C D:{debug.get('D',0)} "
               f"C:{debug.get('C',0)} V:{debug.get('V',0)}")

    resultado = buf.getvalue().encode("utf-8-sig")
    del buf; gc.collect()
    return resultadoód. Conta Debito"] != "") | (chunk["Cód. Conta Credito"] != ""))
    m_valor


# ─────────────────────────────────────────────────────────────────────────────
# VARREDURA R = chunk["Valor"].str.strip() != ""
    return chunk[m_dv & m_conta & m_valor].copy()

def ÁPIDA DE FILIAIS (pré-scan antes da conversler_txt_streaming(conteudo: bytes):
    enc = _detectar_encoding_bytes(conteudo)
    buf = io.BytesIO(conteudo)
    readerão)
# ─────────────────────────────────────────────────────────────────────────────
def _pre_scan_posicional(conteudo: bytes) = pd.read_csv(buf, sep=";", header=None, names=COLS_PADRAO, dtype=str,
                         encoding=enc, -> list:
    """Varre apenas Reg 03 para extrair cód on_bad_lines="skip", engine="c",
                         usecols=range(lenigos de filial únicos."""
    enc = _detectar_encoding_bytes(conteudo)
    try: texto = conteudo.decode(enc, errors="replace")(COLS_PADRAO)), chunksize=CHUNK_SIZE)
    linha_at = 0
    for chunk in reader:
        n = len(chunk)
        chunk["_linha_origem"] = np
    except: texto = conteudo.decode("utf-8", errors="replace")
    filiais = set()
    for linha in texto.splitlines():
        if.arange(linha_at + 1, linha_at + n + 1, dtype=np.int32)
        linha_at += len(linha) >= 564 and linha[:2] == "03":
            raw = linha[557 n
        filtrado = _filtrar_chunk(chunk); del chunk
        if len(filtrado) > 0::564].strip()
            if raw and raw.isdigit():
                codigo = str(int(raw))
                if codigo != "0": filiais.add(codigo yield filtrado, enc
        del filtrado

def diagnosticar_l)
    return sorted(filiais, key=lambda x: int(x) if x.isdigit() else x)


# ─────────────────────────────────────────────────────────────────────────────ote(W: pd.DataFrame, dif: float) -> dict:
    debs = W[W["td
# WIDGET DE/PARA FILIAIS — coluna"]].copy(); creds = W[W["tc"]].copy()
    td = round(float(de "De" pré-populada, somente "Parabs["vf"].sum()), 2); tc = round(float(creds["vf"].sum()), 2)
    linhas_det = []
    for _, r in W.iterrows():
        linhas_det.append({"linha_origem": int(r["lo"]), "data": formatar_data(r["dt"]),
                           "conta_debito": str(r["cd"]) if r["td"] else "",
                           "conta_credito": str(r["cc"]) if r["tc"] else "",
                           "valor": float(r["vf"]), "descricao": _norm_hist(str(r["desc"]))[:70],
                           "tipo": "D" if r["td"] else "C"})
    suspeitas = []; dif_abs = abs(dif)
    for r in linhas_det:
        if abs(r["valor"] - dif_abs) < TOL_" editável
# ─────────────────────────────────────────────────────────────────────────────
def _pre_popular_mapa_filiais(filiais_encontradas: list):
    """Pré-popula o DataFrame de mapeamento, preservando o que o usuário digitou."""
    dfVALOR:
            suspeitas.append({**r, "motivo": f"Valor R_atual = st.session_state.get("mapa_filiais_df")
    if df_atual is not None and len(df_atual) > 0:
        origens_atuais = set(
            str(r).strip()
            for r in df_atual["Código Original (De)"].tolist()
            if str(r).strip() not in ("","nan","None")
        )
        if origens_atuais == set(filiais_encontradas): return

    if filiais_encontradas:
        rows = [{"Código Original (De)": f, "Código Destino (Para)$ {r['valor']:.2f} igual à diferença"})
    if not suspeitas:
        for r in linhas_det:": ""}
                for f in filiais_encontradas]
    else:
        rows = [{"Código Original (De)": "", "Código Destino (Para)": ""}]

    st
            v = r["valor"]
            if r["tipo"] == "D":
                if abs(round.session_state["mapa_filiais_df"] = pd.DataFrame(rows, dtype=str)


def _widget_de(td - v, 2) - tc) < TOL_VALOR:
                    suspeitas.append({**r, "motivo": f"Remover_para_filiais(habilitado: bool, filiais_encontradas: list) -> dict:
    """
     DÉBITO R$ {v:.2f} zeraria o lote"})
            else:Tabela De/Para de filiais.
    - Coluna "De": pré-preenchida com os códigos do
                if abs(td - round(tc - v, 2)) < TOL_VALOR:
                    suspeitas.append({**r, "motivo": f"Remover arquivo, NÃO editável.
    - Coluna "Para": editável — o usuário informa CRÉDITO R$ {v:.2f} zeraria o lote"})
    sugestao = (f"Déb o código destino.
    """
    if not habilitado: return {}

    _pre_popular_mapa_filiais(filiais_encontradas)

    st.markdown("""
    ito excede crédito em R$ {dif_abs:.2f}." if td<div style='background:#0a1a2e;border: > tc
                else f"Crédito excede débito em R$ {dif_abs:.2f}.")
    return {"total1px solid #6EC6FF;border-radius:8px;
                padding:14px _debito": td, "total_credito": tc, "diferenca": dif_abs,
            "qt18px;margin:10px 0;'>
    <b style='color:#6EC6FF;'>🏢d_debitos": len(debs), "qtd_creditos": len(creds),
            "linhas": Mapeamento De/Para — Código da Filial</b><br> linhas_det, "suspeitas": suspeitas, "sugestao": sugestao}

def _gerar_linhas_6100(de
    <small style='color:#9BB0C8;'>
    Os códigos originbs: pd.DataFrame, creds: pd.DataFrame, tp: str) -> list:
    out = []
    if tp == "X":
        rdais foram detectados automaticamente no arquivo (pos 558-564 do Reg 03) = debs.iloc[0]; rc = creds.iloc[0]
        out.append(fmt_reg_6100(formatar_data(rd["dt.<br>
    Preencha apenas a coluna <b style='color:#FFD166"]), str(rd["cd"]), str(rc["cc"]),
                                float(rd["vf"]), "",;'>Código Destino (Para)</b>
    com o código que deve aparecer no campo 9 do reg. 6100 de _norm_hist(str(rd["desc"]) or str(rc["desc"]))))
    elif tp == "D saída.<br>
    Linhas com destino em branco mantêm o código original sem":
        rd = debs.iloc[0]
        out.append(fmt_reg_6100(formatar_data(rd["dt"]), str(rd["cd"]), "",
                                float(rd[" alteração.
    </small>
    </div>
    """, unsafe_allow_html=True)

    df_base = st.session_state["vf"]), "", _norm_hist(str(rd["desc"]))))
        for _, rc in creds.iterrows():
            out.append(fmt_reg_6100(formmapa_filiais_df"].copy()

    df_edit = st.data_editor(
        df_base,
        numatar_data(rd["dt"]), "", str(rc["cc"]),
                                    float(rc["vf"]), "", _norm_hist(str(rc["desc"]) or str(rd_rows="fixed",
        use_container_width=True,
        column_config={
            "Código Original (De)": st.column_config.TextColumn(["desc"]))))
    elif tp == "C":
        rc = creds.iloc[0]
        out.append(fmt_reg_6100(formatar_data(debs.
                "Código Original (De)",
                help="Código da filial conforme aparece no arquivo (detectado automaticamente, pos 558-564 iloc[0]["dt"]), "", str(rc["cc"]),
                                float(rc["vf"]), "", _norm_hist(str(rc["desc"]))))
        for _, rd in debs.iterrows():do Reg 03)",
                disabled=True,
            ),
            "Código Destino (Para)": st.column_config.TextColumn(
                "Código Destino
            out.append(fmt_reg_6100(formatar_data(rd["dt"]), str(rd["cd"]), "",
                                    float(rd["vf"]), "", _norm_hist(str(rd (Para)",
                help="Código que deve aparecer no campo 9 do reg. 6100. Deixe em branco para manter o original["desc"]) or str(rc["desc"]))))
    else:
        for _, rc in creds.iterrows():
            out.append(fmt_reg_6100(form.",
                max_chars=20,
            ),
        },
        key="editor_filatar_data(rc["dt"]), "", str(rc["cc"]),
                                    float(rc["vf"]), "", _norm_hist(str(rc["desc"]))))
        for _, rd iniais",
    )

    st.session_state["mapa_filiais_df"] = df_edit

    mapa = {}
    for _, row in df_edit. debs.iterrows():
            out.append(fmt_reg_6100(formatar_data(rd["dt"]), str(rd["cd"]), "",
                                    float(rd["vf"]), "", _norm_hist(striterrows():
        orig = str(row.get("Código Original (De)","")).strip()
        dest = str(row.get("Código Destino (Para)(rd["desc"]))))
    return out

def _flush_lote(df_lote, num","")).strip()
        if orig and orig.lower() not in ("nan","none","") \, saida_buf, resumo, erros):
                and dest and dest.lower() not in ("nan","none",""):
            mapa[orig] = dest

    if mapa:
        mapa_str
    if df_lote is None or len(df_lote) == 0: return
    v_float = lim = " | ".join(f"{k} → {v}" for k, v in sorted(mapa.items()))
        st.caption(f"✅par_valor_vec(df_lote["Valor"])
    cd_arr = limpar_contas_vec(df_l {len(mapa)} regra(s) ativa(s): {mapa_str}")
    elifote["Cód. Conta Debito"])
    cc_arr = limpar_contas_vec(df_lote["Cód. Conta Credito"])
    td_arr = cd filiais_encontradas:
        st.caption("ℹ️ Nenhum código destino informado — fil_arr != ""; tc_arr = cc_arr != ""; ambos_arr = td_arr & tc_arr
    vdiais mantidas como estão.")
    else:
        st.caption("ℹ️ Nenhuma filial detect_arr = np.where(td_arr, v_float, 0.0); vc_arr = np.where(tc_arr, v_float, 0.0)ada no arquivo.")

    return mapa


def processar_dominio_posicional(conteudo: bytes, ni
    dt_arr = df_lote["Data"].fillna("").astype(str).to_numpy()
    col_desc = df: str,
                                  gerar_6110: bool,
                                  usar_de_para: bool,
                                  mapa_filiais: dict,
                                  log: list,_lote["Complemento Histórico"].fillna("").astype(str)
    desc_arr = col_desc. prog_bar, status) -> tuple:
    status.text("to_numpy(dtype=object)
    for i in range(len(desc_arr)): desc_arr[i] = _norm_hist(str(desc_arr[i]))Lendo arquivo posicional Domínio...")
    prog_bar.progress(10)
    log
    lo_arr = df_lote["_linha_origem"].fillna(0).astype(int).to_numpy(dtype=np.append("── PARSE POSICIONAL ──")

    parsed = _parse_posicional(conteudo, log)
    er.int32)
    W = pd.DataFrame({"nl": num, "lo": lo_arr, "vd": vd_arr, "ros  = parsed["erros"]

    if usar_de_para and mapa_filiais:
        log.append(vc": vc_arr, "vf": v_float,
                      "cd": cd_arr, "cc": cc_arr, "td": td_arr, "tc": tc_arr,f"  De/Para filiais    : {len(mapa_filiais)} regra(s) →
                      "ambos": ambos_arr, "dt": dt_arr, "desc": desc_arr})
    lm = int {mapa_filiais}")
    else:
        log.append("  De/Para filiais    : desabilitado")

    prog_bar.progress(50(lo_arr.min()) if len(lo_arr) else 0
    lx = int(lo_arr.)
    status.text("Gerando saída com separador...")
    log.append("\n── GEmax()) if len(lo_arr) else 0
    fx = f"{lm}–{lx}" if lm != lx else strRAÇÃO ──")

    resultado_bytes = _gerar_saida_posicional(
        parsed, ni, gerar_6110, usar_de_para, mapa_fil(lm)
    dt_fmt = formatar_data(dt_arr[0]) if len(dt_arr) elseiais, log
    )

    prog_bar.progress(90)

    n6000 = resultado ""
    if ambos_arr.all():
        for _, row in W.iterrows():
            desc_bytes.count(b"|6000|")
    n6100 = resultado_bytes.count(b"|6100|")
    n6110 = resultado_bytes.count(b"|6110|")

    me = _norm_hist(str(row["desc"])); dt_l = formtricas = {
        "CNPJ / CPF"    : ni,
        "Lotes"         : fatar_data(str(row["dt"]))
            saida_buf.write(fmt_reg_6000("X") + "\n")
            saida_"{len(parsed['lotes']):,}",
        "Reg. 6000"     : f"{n6000:,}",
        "Reg. 6100"     buf.write(fmt_reg_6100(dt_l, str(row["cd"]), str(row["cc"]), float(row["vf"]), "", desc): f"{n6100:,}",
        "Tamanho saída" : f"{len(resultado_bytes)/1024:.1f} KB",
    } + "\n")
            resumo.append({"num_lote": num, "data": dt_l, "descricao": desc,
    if gerar_6110: metricas["Reg. 6110"] = f"{n6110:,}"

    prog_bar.progress(100)
    status.text("
                           "total_debito": float(row["vf"]), "total_credito": float(row["vf"]),
                           "diferenca": 0.0, "balConcluído!")
    return resultado_bytes, metricas, erros, parsed["filiais_encontradas"]


#anceado": True, "qtd_linhas": 1,
                           "faixa_linhas": str(int(row["lo"])), "diagnostico": {} ═══════════════════════════════════════════════════════════════════════════════
# ESTADO DA SESSÃO
# ═══════════════════════════════════════════════════════════════════════════════
def _init_state():
    defaults = {
        "resultado_bytes":})
        del W; return
    if ambos_arr.any():
        for _, row in W[W["ambos"]].iterrows():
            desc = _norm_hist(str(row["desc"])); dt_l = formatar_data(str(row["dt"]))
            saida_bufNone,"resultado_nome":"saida.txt",
        "erros_bytes":None,"erros_nome":"erros.txt",
        "log_bytes":None,"log_nome":"log.txt",
        "log_lin.write(fmt_reg_6000("X") + "\n")
            saida_buf.write(fmt_reg_6100(dt_l, str(row["cd"]), str(row["cc"]), float(rowhas":[],"resumo":[],"erros_lote["vf"]), "", desc) + "\n")
            resumo.append({"num_lote": num, "data": dt_l, "descricao": desc,
                           "total_debito": float(row["vf":[],
        "metricas":{},"tipo_detectado":None,"sheets""]), "total_credito": float(row["vf"]),
                           "diferenca": 0.0, "balanceado": True, "qtd_linhas": 1,
                           "faixa_linhas"::[],
        "sheet_sel":"","arquivo_bytes":None,"arquivo_nome":"",
        "process str(int(row["lo"])), "diagnostico": {}})
        W_resto = W[~W["ambos"]].resetado":False,"cnpj_ecd":"","cnpj_ecd_fmt":"",
        "m_index(drop=True)
        if len(W_resto) > 0: _flush_lote_normal(W_resto, num, saida_buf, resumoapa_filiais_df":None,
        "filiais_detectadas":[],
    }
    for k, v in defaults.items():
        if k not in st.session, erros, fx, dt_fmt)
        del W; return
    _flush_lote_normal(W, num, saida_buf, resumo, erros_state: st.session_state[k] = v

def _reset():
    keys =, fx, dt_fmt); del W

def _flush_lote_normal(W, num, saida_buf, resumo, erros, fx, dt_fmt):
    td ["resultado_bytes","resultado_nome","erros_bytes","erros_nome","log_bytes","log_nome",
            "log_linhas","resumo","erros__arr = W["td"].to_numpy(); tc_arr = W["tc"].to_numpy()
    vd_arr = W["vd"].to_numpy(); lote","metricas","tipo_detectado","sheets","sheet_sel",
            "arquivo_bytes","arquivo_nome","processado","cnpj_ecd","cnpj_ecd_fmt","filiais_detectadas"]
    vc_arr = W["vc"].to_numpy()
    desc_arr = W["desc"].to_numpy()
    td_sum = roundfor k in keys:
        st.session_state[k] = (
            [] if k in ("log(float(vd_arr[td_arr].sum()), 2)
    tc_sum = round(float(vc_arr[tc_arr].sum(_linhas","resumo","erros_lote","sheets","filiais_detectadas") else
            {})), 2)
    dif = round(abs(td_sum - tc_sum), 2); ok = dif  if k == "metricas" else
            None if k.endswith("_bytes") else
            False if k == "processado"< TOL_VALOR
    entrada = {"num_lote": num, "data": dt_fmt,
               "descricao": _norm_hist(str(desc_arr[ else ""
        )
    # mapa_filiais_df NÃO é resetado — será rec0])) if len(desc_arr) else "",
               "total_debito": td_sum, "total_credito": tc_sum,
               "diferenca": difriado por _pre_popular_mapa_filiais

def _pre_scan_cn, "balanceado": ok,
               "qtd_linhas": len(W), "faixa_linhas": fx, "diagnostico": {}}
    if notpj_ecd(conteudo: bytes) -> str:
    enc = _detectar_encoding_bytes(conteudo)
    try: amo ok:
        entrada["diagnostico"] = diagnosticar_lote(W, dif); erros.append(entrada)stra = conteudo[:4096].decode(enc, errors="replace")
    except: amostra = conteudo[:4096].decode("utf-8", errors="replace")
    else:
        debs = W[W["td"]].reset_index(drop=True); creds = W[W["tc"]].reset_index(drop=True)
        if
    for linha in amostra.splitlines():
        campos = _split_pipe(linha. len(debs) > 0 and len(creds) > 0:
            tp = tipo_lancamento(len(debs), len(creds))strip())
        if campos and campos[0] == "0000" and len(campos) > 5:
            cn
            linhas_out = [fmt_reg_6000(tp)] + _gerar_linhaspj = re.sub(r"\D","",campos[5].strip())
            if len(cnpj) == 14: return cnpj
    return ""

# ═══════════════════════════════════════════════════════════════════════════════
# RENDERIZAÇÃO DE RESULT_6100(debs, creds, tp)
            saida_buf.write("\n".join(linhas_out) + "\n")
    resumo.append(entrada)

def processar_streaming(conteudo: bytes, ni: str, log:ADOS
# ═══════════════════════════════════════════════════════════════════════════════
def _render_resultados_lote list) -> tuple:
    saida_buf = io.StringIO(); saida_buf.write(fmt(exibir_log: bool):
    resumo = st.session_state.resumo or [_reg_0000(ni) + "\n")
    pendente = None; num_lote_g = 0;]; erros = st.session_state.erros_lote or []
    metricas = st.session_state.metricas or {}
    st.markdown usa_inicia = None
    resumo: list = []; erros: list = []; total("---"); st.markdown("## 📊 Resultado da Conversão")
    if metricas:
        cols_lins = 0; ignoradas = 0
    enc_final = "utf-8"; chunk_count = 0
    for chunk_df, enc = st.columns(len(metricas))
        for i,(k,v) in enumerate(metricas.items()): cols[i].metric(k,v)
    if resumo:
        total = len(resumo); n_ok = sum(1 for v in ler_txt_streaming(conteudo):
        enc_final = enc; total_lins += len(chunk_df); chunk_count += 1 in resumo if v["balanceado"]); n_err = total-n_ok
        pct_ok = n_ok
        if usa_inicia is None:
            usa_inicia = bool((chunk_df["Inicia Lote"].str.strip() != "").any())
        if/total if total > 0 else 0.0
        td_total = sum(v["total pendente is not None and len(pendente) > 0:
            chunk_df = pd.concat([pendente, chunk_df], ignore_index=_debito"] for v in resumo); tc_total = sum(v["total_credito"] for v in resumo)
        dTrue); pendente = None
        if usa_inicia:
            inicia = chunk_df["Inicia Lote"].fillif_geral = round(abs(td_total-tc_total),2);na("").astype(str).str.strip()
            marcador = (inicia != "").to_numpy(dtype=bool)
            chunk tudo_ok = dif_geral < TOL_VALOR and_df["_num_lote"] = np.cumsum(marcador, dtype=np.int32) + n_err == 0
        if tudo_ok:
            st.markdown("<div class='card-ok num_lote_g
        else:
            cd_tmp = limpar_contas_vec(chunk_df["Cód'><span style='font-size:22px;'>✅</span> . Conta Debito"])
            cc_tmp = limpar_contas_vec(chunk_df["Cód. Conta Credito"])
            ambos_tmp = (cd_tmp != "") & (<b style='color:#00C896;font-size:18cc_tmp != "")
            if ambos_tmp.all():
                chunk_df["_num_lote"] = np.arange(numpx;'>Todos os lotes balanceados.</b></div>",unsafe_allow_html=True)
        else:
            st.markdown(_lote_g + 1, num_lote_g + len(chunk_df) + 1, dtype=np.int32)
            elif ambos_tmp.any():f"<div class='card-err'><span style='font-size:22px;'>⚠️</span> <b style='color:#FF4444;font-size:18px;'
                desc = chunk_df["Complemento Histórico"].fillna("").astype(str).str.strip().str>{n_err} lote(s) desbalanceado(s).</b></div>",unsafe_allow_html=True)
        col_.upper().str.replace(r"\s+", " ", regex=True)
                chave = (chunkbarra,col_nums = st.columns([3,1])
        with col_barra:_df["Data"].fillna("").astype(str).str.strip() + "|||" + desc).to_numpy() st.progress(pct_ok); st.caption(f"{n_ok:,} de
                muda = np.empty(len(chave), dtype=bool); muda[0] = True; {total:,} lotes balanceados ({pct_ok*100:.1f}%)")
        with col_nums: st.metric("✅ Bal muda[1:] = chave[1:] != chave[:-1]
                chunk_df["_num_lote"] = np.cumsum(muda |anceados",f"{n_ok:,}"); st.metric("❌ Com erro",f"{n_err:,}")
        col_d ambos_tmp, dtype=np.int32) + num_lote_g
            else:
                desc = chunk_df["Complemento Histórico"].fillna("").astype(str).,col_c,col_dif = st.columns(3)
        col_d.metric("Total Débito",f"R$ {td_total:,.2f}"); col_str.strip().str.upper().str.replace(r"\s+", " ", regex=True)
                chave = (chunk_df["Data"].fillna("").astype(str).str.strip() + "|||" + desc).toc.metric("Total Crédito",f"R$ {tc_total:,.2f}")
        col_dif.metric("Diferença Geral",f"R$ {dif_geral:,.2f}",_numpy()
                muda = np.empty(len(chave), dtype=bool); muda[0] = True; muda[1:] = chave[1:] != chave[:-1]
                chunk_df["_
                       delta="OK" if tudo_ok else f"R$ {dif_geral:,.2f}",
                       delta_color="num_lote"] = np.cumsum(muda, dtype=np.int32) + num_lote_g
        ultimo_lote = int(chunk_df["_numnormal" if tudo_ok else "inverse")
    if resumo:
        st.markdown("#### 📋 De_lote"].max())
        mask_ultimo = chunk_df["_num_lote"] == ultimo_lote
        pendente = chunk_df[masktalhe por Lote")
        filtro = st.radio("Exibir lotes_ultimo].copy()
        chunk_proc = chunk_df[~mask_ultimo]; del chunk_df
        for nl:",["Todos","✅ Somente OK","❌ Somente com erro"],horizontal=True,key="filtro_lotes_radio")
        rows = []
        for v in resumo:
            if filtro == "✅ Somente OK" and not v["balanceado"]: continue
            if filtro == "❌ Somente com erro" and v["balanceado"]: continue
            rows.append({"Lote":v["num_lote"],"Linhas":v["faixa_linhas"],"Data":v["data"],
                         "Qtd":v["qtd_linhas"],"Débito":v["total_debito"],"Crédito":v["total_credito"],
                         "Diferença":v["diferenca"],"Status":"✔ OK" if v["balanceado"] else "✖ ERRO"})
        if rows:
            df_res = pd.DataFrame(rows)
            styled = (df_res.style
                      .map(lambda v:"color:#00C896;font-weight:700" if v=="✔ OK" else "color:#FF4444;font-weight:700",subset=["Status"])
                      .map, grupo in chunk_proc.groupby("_num_lote", sort=True):
            _flush_lote(grupo, int(lambda v:"color:#FF4444" if v>TOL_VALOR else "color:#00C896",subset=["Diferença"])
                      .format(nl), saida_buf, resumo, erros)
        num_lote_g = ultimo_lote - 1; del chunk_proc
        if chunk_count % 5 == 0: gc.collect()
    if pendente is not None and({"Débito":"R$ {:,.2f}","Crédito":"R$ {:,.2f}","Diferença":"R$ {:,.2f}"} len(pendente) > 0:
        num_lote_g += 1; _flush_lote(pendente, num_lote_g, saida_buf, resumo, erros); del pendente
    gc.collect()
    log.append(f"  Linhas lidas      : {total_lins:,}")
    log.append(f"  Lotes processados : {len(resumo):,}")
    log.append(f"  Lotes OK          : {len(resumo)-len(erros):,}")
    log.append(f"  Lotes com erro    : {len(erros):,}")
    saida_bytes = saida_buf.getvalue().encode("utf-8-sig"); del saida_buf
    return saida_bytes, resumo, erros, total_lins, ignoradas, enc_final

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO EXCEL
# ═══════════════════════════════════════════════════════════════════════════════
_COLS_ESP_LOW = [c.lower() for c in COLS))
            st.dataframe(styled,use_container_width=True,hide_index=True)
    if erros:
        st.markdown("#### 🔍 Diagn_PADRAO[:8]]

def detectar_cabecalho_excel(conteudo: bytes,óstico dos Lotes Desbalanceados")
        for e in erros:
            diag = e. sheet: str) -> tuple:
    buf = io.BytesIO(conteudo)
    raw = pd.read_excel(get("diagnostico",{})
            label = f"Lote {e['num_lote']}buf, sheet_name=sheet, header=None, nrows=25, engine="openpyxl")
    pasta = None
    try  │  Linhas {e['faixa_linhas']}  │  Data {e['data']}  │  D:
        v = str(raw.iloc[1, 6]).strip()
        if v and v.lower() not in ("nan", "none", ""): pasta = v
    except: pass
    for i,if. R$ {e['diferenca']:,.2f}"
            with st.expander(label,expanded=(len(erros)==1)):
                if diag.get("sugestao"):
                    st.markdown(f"<div class='card-warn row in raw.iterrows():
        vals = [str(v).strip().lower() for v in row if not eh_vazio(v)]
        if sum(1 for c in _COLS_ESP_LOW if c in vals) >= 4'>💡 <b style='color:#FFD166;'>Sugestão:</b> {diag['sugestao']}</div>",unsafe_allow_html=True)
                c: return i, pasta
    return 3, pasta

def ler_excel_lote(con1,c2,c3,c4 = st.columns(4)
                c1.metric("Débito",f"R$ {diag.teudo: bytes, sheet: str, linha_h: int) -> tuple:
    buf = io.BytesIO(conteudoget('total_debito',0):,.2f}")
                c2.metric("Crédito",f"R$ {diag.get('total_credito',0):,.2f}")
                c3.metric("Difer)
    raw = pd.read_excel(buf, sheet_name=sheet, header=None, dtype=str, engine="openpyxl")
    pasta = "ença",f"R$ {diag.get('diferenca',0):,.2f}")
                c4.metric("Partidas",f"D:{C:\\Temp"
    try:
        v = str(raw.iloc[1, diag.get('qtd_debitos',0)} / C:{diag.get('qtd_creditos',0)}")
                for6]).strip()
        if v and v.lower() not in ("nan", "none", ""): pasta = v
    except: pass
    while raw.shape[1] < len s in diag.get("suspeitas",[]):
                    tp = "DÉBITO" if s["tipo"]=="D(COLS_PADRAO) + 2: raw[raw.shape[1]] = ""
    raw." else "CRÉDITO"; cta = s["conta_debito"] or s["conta_columns = range(raw.shape[1])
    df = raw.iloc[linha_h + 1:].resetcredito"]
                    st.markdown(f"- Linha `{s['linha_origem']}` — **_index(drop=True).copy(); del raw; gc.collect()
    df.columns = list(range(df.shape[1]))
    df = df.rename(columns={i: c for i, c in enumerate(COLS_PADRAO)})
    _{tp}** Cta `{cta}` — R$ `{s['valor']:,.2f}` — {s['motivo']}")
                if diag.get("linhas"):V = {"nan", "NaN", "None", "none
                    df_det = pd.DataFrame(diag["linhas"])
                    cols_show = [c for c in ["linha_origem","tipo","conta_debito","conta_credito","valor","descricao"] if c in df_det.columns]
                    st.dataframe(df", ""}
    for c in COLS_PADRAO:
        if c in df.columns: df[c] = df[c].fillna("").astype(str).str.strip().replace(list(_V), "")
    mask_det[cols_show].style
                                 .map(lambda v:"color:#6EC6FF;font-weight:700" if v=="D" else "color:#FF9 = ~((df["Data"] == "") & (df["Cód. Conta DebitoEBC;font-weight:700",subset=["tipo"])
                                 .format({"valor":"R$ {:,.2f}"}"] == "") & (df["Cód. Conta Credito"] == "") & (df["Valor"] == ""))
    df = df[mask].reset_index(drop=True).copy()),use_container_width=True,hide_index=True)
    st.markdown("---"); st.markdown("#### 
    df["_linha_origem"] = (df.index + linha_h + 2).astype(np.int32)
    return⬇ Downloads")
    dl1,dl2,dl3 = st.columns(3); n df, pasta

def montar_lotes_excel(df: pd.DataFrame) -> tuple:
    R = df.copy()_err = len(erros); n_ok = len(resumo)-n_err
    with dl1:
        if
    for col in COLS_PADRAO + ["_linha_origem"]:
        if col not in R.columns: R[col] = ""
    in st.session_state.resultado_bytes:
            if n_err == 0: st.success(f"✅ {n_ok:,} lotes — arquivo pronto!")icia = R["Inicia Lote"].fillna("").astype(str).str.strip()
    tem_ini = bool((inicia != "").any())
    if tem_ini:
        marcador = (inicia != "").to_numpy(dtype=bool)
        R["_num_lote"] = np.where
            else: st.warning(f"⚠ {n_ok:,} OK / {n_err:,} com erro")
            st.download(np.cumsum(marcador) > 0, np.cumsum(marcador, dtype=np.int32), np.int_button("⬇ Baixar arquivo convertido",data=st.session_state.resultado_bytes,
                               file_name=st.session_state.resultado_32(1))
    else:
        cd_tmp = limpar_contas_vec(R["Cód. Conta Debito"])
        cc_tmp = limpar_contas_nome,mime="text/plain",use_container_width=True,type="primary")
    with dlvec(R["Cód. Conta Credito"])
        ambos_tmp = (cd_tmp != "") & (cc_tmp != "")
        if ambos_tmp.all():
            R["_num_lote"] =2:
        if erros:
            linhas_err = ["RELATÓRIO DE LOTES DESBALANCEADOS","=" np.arange(1, len(R) + 1, dtype=np.int32)
        elif ambos_tmp.any():
            desc = R["Complemento Histórico"].fillna("").astype(str).str.*60,"",f"Data/Hora : {tsstrip().str.upper().str.replace(r"\s+", " ", regex=True)
            chave = (R["Data"].fillna("").astype(str).str.strip() + "|||" + desc).to_numpy()_log()}",f"Total erros: {len
            muda = np.empty(len(chave), dtype=bool); muda[0] = True; muda[1:] = chave[1:] != chave[:-1]
            R["_num_lote"] =(erros)}","","="*60,""]
            for e in erros: linhas_err += np.cumsum(muda | ambos_tmp, dtype=np.int32)
        else:
            desc = R["Complemento Histórico"].fillna("").astype(str).str.strip().str.upper().str. [f"Lote: {e['num_lote']} | Data: {e['data']}replace(r"\s+", " ", regex=True)
            chave = (R["Data"].fillna("").astype(str).str.strip() + "|||" + desc).to_numpy()
            muda = np.empty( | Dif: R$ {e['diferenca']:,.2f}",""]
            st.error(f"❌ {len(erros):len(chave), dtype=bool); muda[0] = True; muda[1:] = chave[1:] != chave[:-1]
            R["_num_lote"] = np.cumsum(muda,,} lote(s) com erro.")
            st.download_button("⬇ Baixar relatório de erros",data="\n".join(linhas_ dtype=np.int32)
    return R, "Inicia Lote" if tem_ini else "Data +err).encode("utf-8-sig"),
                               file_name="erros_lotes.txt",mime="text/plain",use_container_width=True) Descrição"

def processar_excel(df: pd.DataFrame, ni: str, log: list) -> tuple:
    saida_buf = io.StringIO
        elif st.session_state.erros_bytes:
            st.download_button("⬇ Baixar relatório de erros",data=st.session_state.erros_bytes,
                               file_name=st.session_state.erros_nome,mime="text/plain",use_container_width=True)
    with dl3:
        if st(); saida_buf.write(fmt_reg_0000(ni) + "\n")
    resumo: list = []; erros: list = []
    for nl.session_state.log_bytes:
            st.download_button("⬇ Baixar log completo",data=st.session_state.log_bytes,
                               file_name=, grupo in df.groupby("_num_lote", sort=True):
        _flush_lote(grupo, int(nl), saida_buf, resumo, erros)
    gc.collect()
    log.append(f"  Lotes processados : {len(resumo):,}")
    log.append(f"  Lotes OK          : {len(resumo)-len(erros):,}")
    log.append(f"  st.session_state.log_nome,mime="text/plain",use_container_width=True)
    if exibir_log and st.session_state.logLotes com erro    : {len(erros):,}")
    saida_bytes = saida_buf.getvalue().encode("utf-8-sig"); del saida_buf
    return saida_bytes, resumo, erros_linhas:
        st.markdown("#### 🖥 Log de Processamento")
        log

def _montar_log_lote(resumo, erros, ni, ti_txt = "\n".join(str(l) for l in st.session_state.log_linhas)
        tem_erro = any(", inf, n_gravados, ignoradas, enc, cronoERRO" in str(l).upper() for l in st.session_state.log_linhas)
        st.markdown(f"<div class='bl):
    td = sum(v["total_debito"] for v in resumo);oco-log' style='border-color:{'#FF4444' if tem_erro else '#1 tc = sum(v["total_credito"] for v in resumo)
    ok = len(resumo) - len(erros)
    conc = "A3050'};'>{log_txt}</div>",unsafe_allow_html=True)

def _render_resultados_ecd(exibir_log: bool):
    metricas = st.session_SUCESSO" if not erros else f"ATENÇÃO — {len(erros)} lote(s) desbalanceado(s)"
    SEP = "═"*90state.metricas or {}
    st.markdown("---"); st.markdown("## 📊 Resultado da Conversão — SPED E; sep2 = "─"*90
    L = [SEP, "CD")
    if metricas:
        cols = st.columns(len(metricas))
        for i,(k,v) in enumerate(metricas.items()): cols[i].metric(k,v)
    st  DOMÍNIO SISTEMAS  |  Thomson Reuters",.markdown("#### ⬇ Downloads")
    dl1,dl2 = st.columns(2)
    with dl1:
        if st.session_state.resultado_bytes:
             "  LOG DE VALIDAÇÃO — LANÇAMENTOS CONTst.success("Arquivo gerado com sucesso!")
            st.download_button("⬇ Baixar arquivo convertÁBEIS", SEP,
         f"  Data/Hora     : {tsido",data=st.session_state.resultado_bytes,
                               file_name=st.session_state.resultado_nome,mime="text/plain",use_container_width=True,type="primary")
    with_log()}", f"  Encoding leit.: {enc or 'N dl2:
        if st.session_state.erros_bytes:
            st.warning("Arquivo de erros disponível.")
            st.download/A'}",
         f"  {ti:<6}         _button("⬇ Baixar relatório de erros",data=st.session_state.erros_bytes,
                               file_name=st.session_state.erros_nome,mime="text: {inf}", SEP, "", "  RESUMO GERAL", sep2,
         f"  /plain",use_container_width=True)
    if exibir_log and st.session_state.log_linhas:
        st.markdown("#### 🖥 Log de Processamento")Lotes total   : {len(resumo):>10,}", f"  Lotes OK      : {ok:
        log_txt = "\n".join(str(l) for l in st.session_state.log_linhas)
        tem_erro = any("ERRO" in str(l).upper() for l in st.session_state.log>10,}",
         f"  Lotes ERRO    : {len(erros):>10,}", f"  Reg. 6000+6100: {n_gravados:>10,}",
         f"  _linhas)
        st.markdown(f"<div class='bloco-log' style='border-color:{'#FF4444' if tem_erro else '#1A3050'};'>{log_txt}</div>",unsafe_Ignoradas     : {ignoradas:>10,}", f"  Total Déb.    : R$ {td:>14allow_html=True)

def _render_resultados_posicional(exibir_log: bool):
    metricas = st.session_state.metricas or {}
    st.markdown("---"); st.markdown("## 📊 Resultado — Leiaute Posicional Domínio")
    if metricas:
        cols = st.2f}",
         f"  Total Créd.   : R$ {tc:>14.2f}", f"  Conclusão     : {conc}",.columns(len(metricas))
        for i,(k,v) in enumerate(metricas.items()): cols[i].metric(k,v)
    st.markdown("#### ⬇ Downloads")
    dl1 ""]
    if crono and crono.etap,dl2 = st.columns(2)
    with dl1:
        if st.session_state.resultado_bytes:
            st.success("✅ Arquivo convertido com sucesso!")
            as:
        total_seg = sum(e["segundos"] for e in crono.etapas)
        L +=st.download_button("⬇ Baixar arquivo convertido",data=st.session_state.resultado_bytes,
                               file_name=st.session_state.resultado_nome,mime="text/ [sep2, "  RELATÓRIO DE TEMPO", sep2]
        for e in crono.etapas: L.append(f"  {'  '+e['nome']:<38} {Cronplain",use_container_width=True,type="primary")
    with dl2:
        if st.session_state.erros_bytes:
            st.warning("⚠ Háometro.fmt(e['segundos']):>8}")
        L += [" registros com erros de parse.")
            st.download_button("⬇ Baixar relatório de erros",data=st.session_  "+"─"*46, f"  {'  state.erros_bytes,
                               file_name=st.session_state.erros_nome,mime="text/plain",use_container_width=True)
    if exibir_log and st.session_state.log_TOTAL':<38} {Cronometro.fmt(total_seg):>8}", ""]
    L += [sep2, f"  {'Lotelinhas:
        st.markdown("#### 🖥 Log de Processamento")
        log_txt = "\n".join(str(l) for l in st.session_state.log_linhas)
        tem_erro =':<8}{'Linhas':<16}{'Data':<13}{'Qt any("ERRO" in str(l).upper() for l in st.session_state.log_linhas)
        st.markdown(f"<div class='bloco-log' style='border-color:{'#FF4444' ifd':<6}{'Débito':>15}{'Crédito':>15}{'Diferença':>13 tem_erro else '#1A3050'};'>{log_txt}</div>",unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════}  Status",
          "  "+"─"*88]
    for v in resumo════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(page_title="Dom:
        L.append(f"  {str(v['num_lote']):<8}{v['faixa_linhas']:<16}{v['data']:<13}{strínio Sistemas | Thomson Reuters",
                       page_icon="🟠",layout="wide",initial_sidebar_(v['qtd_linhas']):<6}"
                 f"R$ {v['total_debito']:>12.2f}state="expanded")
    apply_theme(); _init_state()

    st.markdown(
        f"  R$ {v['total_credito']:>12.2f}  R$ {v['diferenca']:>10.2f}   "
                 f"{'✔<div class='header-box'>"
        f"<h2 style='color:#FF6B00 OK' if v['balanceado'] else '✖ ERRO'}")
    L += ["  "+"─"*88, f"  {';margin:0;'>Domínio Sistemas — Conversor Unificado</h2>"TOTAIS':<37}R$ {td:>12.2f}  R$ {tc:>12.2f}",
        f"<p style='color:#6B7A8D;margin:6px 0 0;' "",
          SEP, f"  Fim  │  {ts_log()}", f>"
        f"Lançamentos Contábeis (T"  Resultado │  {conc}", SEP]
    return "\n".join(L)

# ═══════════════════XT/Excel/Posicional) &nbsp;|&nbsp; SPED ECD &nbsp;════════════════════════════════════════════════════════════
# ███████████████████████████████████████████████████████████████████████████████
# MÓDULO DOM→&nbsp; "
        f"0000 + 6000ÍNIO TXT POSICIONAL — V3.4  + 6100 &nbsp;|&nbsp; <b style='color:#FF6B00;'>Thomson Reuters</b>"
        f"&FINAL
#
# REGRAS IMPLEMENTADAS (conforme definnbsp;|&nbsp; <small>{VERSAO}</small></p></div>",
        unsafe_allow_html=Trueição do usuário):
#   1. Vinculação Di
    )

    with st.sidebar:
        st.markdown("### ⚙ Configurações"); st.markdown("---")reta: o CC (débito ou crédito) só existe se
        exibir_log = st.checkbox("Exibir log de processamento",value=True)
        st.markdown("---"); st.markdown(f"** houver o
#      respectivo lançamento na conta.
#   2. Independência de Registros: pode haver CC a crédito sem CCVersão:** {VERSAO}")
        st.markdown("**Thomson Reuters — Domínio Sistemas**"); st.markdown("---")
        st.markdown("**Formatos suportados:**")
        st.markdown("- 📊 Excel a débito
#      e vice-versa.
#   3. Fidelidade ao Arquivo: replica (.xlsx / .xls)\n- 📄 TXT separado por `;`\n- 📋 exatamente o que consta no arquivo
#      de origem.
#   4. Sem SPED ECD (.txt)\n- 📋 TXT Posicional Contrapartida Automática: se o arquivo não informar o CC de um
#      dos lados, o registro correspondente não é gerado. Não Domínio")
        st.markdown("---")
        st.code("|0000|CNPJ|\n|6000|TIPO||||\n|6100|DATA|DEB há
#      preenchimento automático ou espelhamento.
#
# VÍNCULO Reg 05 → Reg 03:
#   |CRED|VALOR||HIST||FILIAL|Cada Reg 05 pertence ao Reg 03 que o precede|\n|6110|CC_DEB|CC_CRED|VALOR| imediatamente no arquivo.
#   Vínculo = idx da última",language=None)
        st.markdown(f"**Limite:** {MAX_UPLOAD_MB} MB")

    # ── P partida inserida no momento da leitura.
#   NÃO há filtragem por tipo de CC na geração do 6110.
# ███asso 1: Arquivo ─────────────────────────────────────────────────────
    st.markdown("#### 📂 Passo 1 — Selecionar Arquivo")
    uploaded = st.file_uploader(████████████████████████████████████████████████████████████████████████████
# ═══════════════════════════════════════════════════════════════════════════════

def _extra
        f"Arraste ou clique (Excel, TXT separado por ';',ir_filial(linha: str) -> str:
    """
    Lê os 7 chars das posições 558-564 (1-based SPED ECD ou TXT Posicional — máx. {MAX_UPLOAD_MB} MB)",
        type=["xlsx","xls","xlsm","txt","csv"]
    )

    if uploaded is not None:
        conteudo = uploaded.read(); mb = len(conteudo)) = índices [557:564].
    Remove zeros à esquerda. "0000000" ou/(1024*1024)
        if mb > MAX_UPLOAD_MB:
            st.error(f"⛔ Arquivo muito grande ({mb:.1f} MB). "0" → vazio (matriz).
    """
    if len(linha) < 564 Limite: {MAX_UPLOAD_MB} MB."); return
        if conteudo != st:
        return ""
    raw = linha[557:564].strip()
    if not raw or not raw.isdigit():
        return ""
    codigo.session_state.arquivo_bytes or uploaded.name != st.session_state.arquivo_nome:
            _reset()
            st.session_state = str(int(raw))
    return "" if codigo == "0" else codigo


def _extrair_cc(raw.arquivo_bytes = conteudo
            st.session_state.arquivo_nome  = uploaded.name
            tipo = identificar_tipo(uploaded.name, conteudo)
            st: str) -> str:
    """Remove zeros à esquerda de um campo CC de 7 chars.session_state.tipo_detectado = tipo
            if tipo == "excel":
                try:
                    xl = pd.ExcelFile(io."""
    raw = raw.strip()
    if not raw or not raw.isdigit():
        return ""
    codigo = str(int(raw))
    return "" if codigo == "0" else codigo.BytesIO(conteudo),engine="openpyxl")
                    st.session_state.sheets = xl.sheet_names
                    


def _posicional_para_decimal(val_raw: str) -> float:
    """st.session_state.sheet_sel = ("Plan1" if "Plan1" in xl.sheet_names else xl
    Campo de 15 chars com 2 casas decimais implícitas (.sheet_names[0])
                except: st.session_state.sheets = []
            elif tipo == "ecd":
                cnpj_sem separador).
    Ex: "000000000193num = _pre_scan_cnpj_ecd(conteudo)
                st.session_state.cnpj_ecd     = cnpj_num224085" → 1932240.85
    """
    val_raw = val_raw.strip
                st.session_state.cnpj_ecd_fmt = fmt_cnpj(cnpj_num) if cnpj_num else ""
            elif tipo == "dom()
    if not val_raw or not val_raw.isdigit():
        return 0.0
    val_raw = val_raw.zfill(3inio_pos":
                filiais = _pre_scan_posicional(conteudo)
                st.session_state.filiais_detectadas =)
    inteiros = val_raw[:-2]
    decimais  = val_raw[-2:]
    try filiais

    if st.session_state.arquivo_bytes is None:
        st.markdown("<div class='info-box'>:
        return float(f"{int(inteiros)}.{decimais}")
    except Exception:
        return 0.0


def _parse_posicional(⬆ Selecione um arquivo para começar.</div>",unsafe_allow_html=True)
        conteudo: bytes, log: list) -> dict:
    """
    Parser do TXT posicional Domreturn

    tipo = st.session_state.tipo_detectado
    badges = {
        "ecd":         "ínio — V3.4 FINAL.

    REGRA DE VÍNCULO Reg 05 → Reg 03:
        Cada Reg 05 pertence ao Reg 03 que o precede IMEDIATAMENTE no arquivo.
        Vínculo = idx da última partida inserida no<span class='badge-ecd'>📋 SPED ECD</span>",
        "excel":       "<span class='badge-excel'>📊 Excel</span>",
        "lote":        "<span class='badge-lote'>📄 TXT Lote (; momento da leitura do Reg 05.
        NÃO há filtragem por tipo de CC (débito/crédito).)</span>",
        "dominio_pos": "<span class='badge-pos'>📋 TXT Posicional Domínio</span>",
    }
    mb
        O sistema replica exatamente o que consta no arquivo de origem.
    """
    enc = __info = len(st.session_state.arquivo_bytes)/(1024*1024)
    st.markdown(
        f"{detectar_encoding_bytes(conteudo)
    log.append(f"  Encoding detectbadges.get(tipo,'')} "
        f"<span style='color:#6B7A8D;font-size:13px;margin-left:12px;'>"
        f"{st.session_state.arquivo_nome} —ado : {enc}")
    try:
        texto = conteudo.decode(enc, errors="replace")
    except Exception:
        texto = conteudo.decode("utf-8", errors="replace")

    linhas = texto.splitlines()
    log.append(f"  Total de {mb_info:.1f} MB</span>",
        unsafe_allow_html=True
    )
    st.markdown("")

    # ── Passo 2: Config Excel linhas    : {len(linhas):,}")

    cabecalho = {}
    lotes: list = []
    l ─────────────────────────────────────────────────
    sheet_sel = ""; linha_h = 3ote_atual = None
    erros: list = []
    filiais_set: set = set()
    ; auto_head = True
    if tipo == "excel" and st.session_state.sheets:
        st.markdown("#### 📋cnt = {"01": 0, "02": 0, "03": 0, "05": 0, "08 Passo 2 — Configurar Excel")
        col1,col2,col3 = st.columns([2": 0, "99": 0, "outro": 0}

    for num_linha, linha in enumerate(linhas,1,1])
        with col1:
            sheet_sel = st.selectbox("Aba (Sheet)",st, 1):
        if len(linha) < 2:
            continue
        reg = linha[:2].session_state.sheets,
                index=(st.session_state.sheets.index(st.session_state.sheet_sel)
                       

        try:
            # ── Reg 01 — Caif st.session_state.sheet_sel in st.session_state.sheets else 0))
            st.session_state.sheet_sel = sheet_sel
        with col2:beçalho ──────────────────────────────────────────
            if reg == "01":
                cnt["01"] += 1
                cabecalho = {
                    "cod auto_head = st.checkbox("Detectar cabeçalho automaticamente",value=True)
        with col3:
            if_empresa": linha[2:9].strip(),
                    "cnpj": not auto_head: linha_h = st.number_input("Linha do cabeçalho",min_value=1,max_value=50        linha[9:23].strip(),
                    "dt_ini":      linha[23:33].strip(),
                    "dt_fin":      linha[33:43,value=4)-1

    # ── Passo 2: CNPJ ────────────────────────────────].strip(),
                    "tipo_nota":   linha[44:46].strip() if len(linha) > 45────────────────────────
    ni = ""; ok_insc else "",
                }
                log.append(f"  Cabeçalho — Empresa: {cabecalho['cod_empresa']} " = False; ti = ""; inf = ""
    if tipo == "ecd":
        st
                           f"| CNPJ: {cabecalho['cnpj']} "
                           f"| Período: {cabecalho['dt_ini']} a {cabecalho['dt.markdown("#### 🏢 Passo 2 — CNPJ (preenchido automaticamente)")
        cnpj_e_fin']}")

            # ── Reg 02 — Dados do Lote ──────────────────────────────────────
            elif reg == "02":
                cnt["02"]cd = st.session_state.cnpj_ecd
        if cnpj_ecd and validar_cnpj(cnpj_ecd):
            st += 1
                tipo_lanc = linha[9:10].strip().upper()
                data_lanc = linha[10:20.markdown(f"<div class='cnpj-auto'>✔ CNPJ extraído: ].strip()
                usuario   = linha[20:50].strip()
                if tipo_lanc not in ("X", "D", "C<span>{st.session_state.cnpj_ecd_fmt}</span></div>",unsafe_allow_html=True)
            st", "V"):
                    tipo_lanc = "X"
                lote_atual = {
                    "seq":.code(fmt_reg_0000(cnpj_ecd),language=None)
            ok      linha[2:9].strip(),
                    "tipo":     tipo_lanc,
                    "data":     data_insc = True; ti = "CNPJ"; ni = cnpj_ecd; inf = st.session_state.cnp_lanc,
                    "usuario":  usuario,
                    "partidas": [],
                    "centros":  [],
                }
                lj_ecd_fmt
        else:
            st.warning("⚠ CNPJ não encontrado. Informe manualmente.")
            cnotes.append(lote_atual)

            # ── Reg 03 — Partidas ────────────────────────────────────────────
            elif regpj_raw = st.text_input("CNPJ / CPF",placeholder="00.000.000/0001-00",key == "03":
                cnt["03"] += 1
                if lote_atual is None:
                    erros.append({
                        "linha": num_linha,
                        "="cnpj_manual_ecd")
            ok_insc,ti,ni = validmotivo": "Reg 03 sem Reg 02 anterior",
                        "conar_inscricao(cnpj_raw)
            if cnpj_raw:
                if ok_insc: infteudo": linha[:80]
                    })
                    continue

                cta_ = fmt_cnpj(ni) if ti=="CNPJ" else fmt_cpf(ni); st.success(f"✔ {ti} válido: {infdeb   = linha[9:16].strip()
                cta_cred  = linha[16:23].strip()
                val_raw   = linha[23:38].strip()
                cod_hist  = linha[38:45].strip()
                historico = linha[45:557].strip()}")
                else: st.error("✖ CNPJ/CPF inválido")
    else if len(linha) > 45 else ""
                filial_p  = _extrair_fil:
        st.markdown("#### 🏢 Passo 2 — Informar CNPJ / CPF")
        cnpj_raw = st.textial(linha)

                if filial_p:
                    filiais_set.add(filial_p)

                if cta_deb  _input("CNPJ / CPF",placeholder="00.000.000/0001-00 ou 000.000.000-00",key="cnpjin ("0000000", "0", ""): cta_deb  = ""
                if cta_lote")
        ok_insc,ti,ni = validar_inscricao(cnpj_raw)
        if cnpj_raw:
            if ok_insc:_cred in ("0000000", "0", ""): cta_cred = ""

                valor_dec = _posicional_para_decimal(val_raw)
                hist
                inf = fmt_cnpj(ni) if ti=="CNPJ" else fmt_cpf(ni)
                col_a,col_b = st.columns([_norm = _norm_hist(historico)

                # Índice pos1,2])
                with col_a: st.success(f"✔ {ti} válido")
                with col_b: st.code(fmticional único — calculado ANTES do append
                idx_part_reg_0000(ni),language=None)
            else: st.error("✖ CNPJ/CPF inválido")

    # ── Passo 3: Opções ida = len(lote_atual["partidas"])

                lote_atual["partidas"].append({
                    "idx":      idx_partida,
                    "seq":      linha───────────────────────────────────────────────────────
    st.markdown("---"); st.markdown("#### ⚙ Passo 3 — Opções[2:9].strip(),
                    "cta_deb":  cta_deb,
                    "cta_cred": cta_cred,
                    "valor":    valor e Conversão")

    col_op1,col_op2 = st.columns(2)_dec,
                    "cod_hist": cod_hist,
                    "hist":     hist_norm,
                    "filial":   filial_p,
                })
    with col_op1:
        gerar_6110 = st.checkbox(
            "Gerar registro 6110 (Centro de Cus

            # ── Reg 05 — Rateios por Centro detos)",
            value=False,
            disabled=(tipo not in ("ecd","dominio_pos")),
            help="G Custos ────────────────────────
            elif reg == "05":
                cnt["05"] += 1
                if lote_atual is None:
                    erros.append({
                era o registro 6110 imediatamente após cada 6100 pai        "linha": num_linha,
                        "motivo": "Reg 05 sem Reg 02 anterior",
                        "conteudo": linha[:80]
                    })
                    continue

                if (filho direto)."
        )
    with col_op2:
        usar_de not lote_atual["partidas"]:
                    erros.append({
                        "linha": num_linha,
                        "motivo": "Reg 05 sem Reg 03 anterior no_para = st.checkbox(
            "🏢 Habilitar De/Para de fil lote",
                        "conteudo": linha[:80]
                    })
                    continue

                cc_deb_raw  = linha[9:16]iais",
            value=False,
            disabled=(tipo != "dominio_pos"),
            help="Disponível apenas para TXT Posicional. Os códigos originais são detectados automaticamente."
        )

    # Tabela De/Para — só aparece quando habilitado
    mapa_filiais = {}
    if tipo == "dominio_pos" and usar_de_para:
        filiais_detectadas = st.session_state.get("filiais_detectadas",[])
        mapa_filiais = _widget_de_para_filiais(habilitado=True, filiais_encontradas=filiais_detectadas)

    col_b1,col_b2 = st.columns([2,1])
    with col_b1:
        btn_converter = st.button("▶ CONVERTER",disabled=(not  if len(linha) > 15 else "0000000"
                cc_cred_raw = linha[16:23] if len(linha) > 22 else "0000000"
                val_raw5    = linha[23:38].strip() if len(linha) > 37 else "0"

                cc_deb  = _extrair_cc(cc_deb_raw)
                cc_cred = _extrair_cc(cc_cred_raw)
                valor_c = _posicional_para_decimal(val_raw5)

                # VÍNCULO POSICIONAL: último Reg 03 lido antes deste Reg 05.
                # Fidelidade total ao arquivo — sem inferência por tipo de CC.
                idx_pai = lote_atual["partidas"][-1]["idx"]

                lote_atual["centros"].append({
                    "seq":          ok_insc),use_container_width=True,type="primary")
    with col_b2:
        btn_limpar = st.button("🗑 Limpar tudo",use_container_width=True)

    if btn_limpar: _reset();linha[2:9].strip(),
                    "cc_deb":      cc_deb,
                    "cc_cred":     cc_cred,
                    "valor":       valor_c,
                 st.rerun()

    # ── Processamento ─────────────────────────────────────────────────────────
    if btn_converter and    "idx_partida": idx_pai,
                })

            elif reg == "08":
                cnt["08"] = cnt.get("08", 0) + 1 ok_insc:
        conteudo = st.session_state.arquivo_bytes
        log = [];
            elif reg == "99":
                cnt["99"] += 1
            else:
                cnt["outro"] += 1

        except Exception as ex:
            erros.append({
                "linha": num crono = Cronometro(); crono.iniciar()
        status_linha,
                "motivo": str(ex),
                "conteudo": linha[:80]
            })

    log.append(f"  Reg 01 _txt = st.empty(); prog_bar = st.progress(0)

        try(cabeçalho)  : {cnt['01']}")
    log.append(f"  Reg 02 (l:
            # ── SPED ECD ─────────────────────────────────────────────────────
            if tipo == "ecdotes)      : {cnt['02']:,}")
    log.append(f"  Reg 03 (partidas)   : {cnt['03']:,}")
    log.append(":
                status_txt.text("Lendo SPED ECD..."); log.append("── LEITURA SPED ECDf"  Reg 05 (c.custos)   : {cnt['05']:,}")
    log.append(f"  Reg 08 (informativo ──")
                crono.etapa("Leitura SPED ECD"); prog_bar.progress(10)): {cnt.get('08',0):,}")
    if erros:
        log.append(f"  Erros/
                ecd, registros_erro = _parse_ecd(conteudo,avisos        : {len(erros):,}")

    filiais_encontradas = sorted log)
                if ecd is None:
                    st.error("Falha na leitura do SPED ECD."); st.session(filiais_set, key=lambda x: int(x) if x.isdigit() else x)
    if filiais_encontradas:_state.log_linhas = log
                else:
                    prog_bar.progress(50); status
        log.append(f"  Filiais detectadas  : {filiais_encontradas}")

    return {
        "cabecalho":           cabecalho,
        _txt.text("Gerando registros...")
                    crono.etapa("Geração dos registros"); log.append("\"lotes":               lotes,
        "erros":               erros,
        "filiais_encontradas": filiais_encontradas,
    }


def _aplicar_den── GERAÇÃO ──")
                    linhas_ecd = _gerar_ecd(ecd, log_para(filial: str, mapa: dict) -> str:
    if not filial:
        return ""
    return mapa.get(filial, filial)


def _gerar_saida_pos, prog_bar, status_txt)
                    if gerar_6110:
                        linicional(parsed: dict, ni: str, gerar_6110: bool,
                             usarhas_com_6110 = []
                        for l in linhas_ecd:
                            linhas_com_6110.append(l)
                            if l.startswith("|6100|"):
                                campos = l.split("|")
                                if len(campos) >= 6_de_para: bool, mapa_filiais: dict,
                             log: list) -> bytes:
    """
    Geração da saída — V3.4 FINAL.

    REGRAS:
                                    deb_l=campos[3]; cred_l=campos[4]; valor_l=campos[5] DO 6110 (conforme definição do usuário):
        1. Vin
                                    hist_l=campos[7] if len(campos)>7 else ""; data_l=campos[2]
                                    if deb_l: linhas_com_6110.append(f"|6110|{data_l}|{debculação Direta: o 6110 só existe se o Reg 05 correspondente
           existir no arquivo para aquela partida (idx).
        2. Independência:_l}|{valor_l}|D||{hist_l}|||||||")
                                    if cred_l: linhas_com_6110.append pode haver 6110 só com cc_cred, só com cc_deb,
           ou com ambos — exatamente como está no arquivo.
        3. Fidelidade: replica o arquivo de origem SEM NENHUM FILTRO por
           tipo de CC.
        4. Sem contrapartida automática: se o arquivo não informou um lado,
           o registro não é gerado.
        5. O 6110 é emitido IMEDIATAMENTE após o 6100 pai.
    """
    buf = io.StringIO()
    buf.write(f"|0000|{ni}|\n")

    lotes = parsed["lotes"]
    ok = ignorados = 0
    cnt = {"t6000": 0, "t6100": 0, "t6110": 0}
    debug = {"X": 0, "D": 0, "C": (f"|6110|{data_l}|{cred_l}|{valor_l}|C||{hist_l}|||||||")
                        linhas_ecd = linhas_com_6110
                    crono.etapa("Montagem do arquivo"); prog_bar.progress(90); status_txt.text("Montando arquivo...")
                    buf_out = io.StringIO()
                    for i in range(0,len(linhas_ecd),WRITE_CHUNK):
                        buf_out.write("\n".join(linhas_ecd[i:i+WRITE_CHUNK])+"\n")
                    resultado_bytes = buf_out.getvalue().encode("utf-8-sig"); del buf_out,linhas_ecd; gc.collect()
                    nome_saida = f"ECD_{ni}_dominio.txt"
                    st.session_state.resultado_bytes = resultado_bytes; st.session_state.resultado_nome = nome_saida
                    n6000 = resultado_bytes.count(b"|6000|"); n6100 = resultado_bytes.count(b"|6100|")
                    st.session_state.metricas = {
                        "CNPJ":e0, "V": 0}

    _nulos = {"", "0", "0000000cd.cnpj,"Lançamentos (I200)":f"{len"}

    for lote in lotes:
        data     = lote.get("data", "")
        part(ecd.lancamentos):,}",
                        "Registros 6000":f"{nidas = lote.get("partidas", [])
        centros  = lote.get("centros",  [])

        if not partidas:
            ignorados += 1
            continue

        de6000:,}","Registros 6100":f"{n6100:,}",
                        "Tamanho saída":f"{len(resultado_bytes)/bs  = [p for p in partidas if p["cta_deb"]  not in _nulos]
        creds = [p for p1024:.1f} KB"
                    }
                    if registros_erro:
                        erros_txt = _txt_erros_ecd(registros_erro,ecd.cnpj)
                        st.session_state.erros_bytes = in partidas if p["cta_cred"] not in _nulos]

        if not debs or not creds:
            ignorados += 1
            continue

        nd, nc = len(debs), len(creds)
        if   nd == 1 and nc == 1: tipo_ erros_txt.encode("utf-8-sig")
                        st.session_state.erros_nome  = f"ECD_{ni}_erros.txt"
                    total_seg = crono.encerrar()
                    log.append(f"\n── TEMPOreal = "X"
        elif nd == 1 and nc > 1:  tipo_real = "D"
        elif nd > 1   TOTAL: {Cronometro.fmt(total_seg)} ──")
                    for eand nc == 1: tipo_real = "C"
        else:                     tipo_real = "V"

        debug[tipo_real] = debug.get(tipo_real, 0) + 1

        # ── Índice de centros por in crono.etapas: log.append(f"  {e['nome']}: {Cronometro.fmt(e['segundos'])}")
                    st partida ────────────────────────────────────
        # Chave: idx da part.session_state.log_linhas = log; st.session_state.processado = True
                    prog_bar.progress(100); status_txt.text("ida (índice posicional único do parse).
        # Valor: lista de Reg 05Concluído!")

            # ── EXCEL ─────────────────────────────────────────────────────────
            elif tipo == "excel":
                crono.etapa("Lei cujo idx_partida == idx da partida.
        # Partidas semtura Excel"); status_txt.text("Lendo Excel..."); prog_bar.progress(8)
                sh = st Reg 05 → chave ausente → get() retorna [] → n.session_state.sheet_sel; lh_det,_enhum 6110.
        centros_por_partida: dict[int, list] = {}
        for cc in centros:
            idx = detectar_cabecalho_excel(conteudo,sh)
                lh = lh_det if auto = cc.get("idx_partida", -1)
            if idx >= 0:
                centros_por_partida.setdefault(idx, [])._head else linha_h; df,_ = ler_excel_lote(conteudo,shappend(cc)

        def _filial_p(p: dict) -> str:
            f = p.get("filial", "")
            if usar,lh)
                log.append(f"Excel — Aba: {sh} | Ca_de_para and mapa_filiais:
                f = _aplicar_de_para(f, mapa_filiais)
            return f

        def _emitebeçalho: linha {lh+1}"); log.append(f"Linhas carregadas: {len(df):,}")
                prog_bar.progress(30); crono.etapa("Montagem de lotes_6110(idx: int):
            """
            Emite os registros 6110 do idx inform"); status_txt.text("Montando lotes...")
                df,modo = montar_lotes_excel(df);ado, SEM NENHUM FILTRO.

            Regras aplicadas:
             n_lotes = int(df["_num_lote"].max())- Vinculação direta: só emite se existir Reg 05 para este idx.
            - Independ if len(df)>0 else 0
                log.append(f"Lotes: {n_lotes:ência: emite cc_deb e cc_cred exatamente como estão
              no arquivo, mesmo que,} [modo: {modo}]"); prog_bar.progress(45)
                crono.etapa("Process apenas um lado esteja preenchido.
            - Fidelidade: não filtra, não completa, não espelha.
            - Sem contrapartida automática.
            """amento / validação"); status_txt.text("Processando lotes...")
                resultado_bytes,resumo,erros = processar_excel(df,ni,log); del df;
            if not gerar_6110:
                return
            for cc in centros_por_partida.get(idx, []):
                cc gc.collect(); prog_bar.progress(85)
                n_gravados = resultado_bytes.count(b"|6000|")_d = cc.get("cc_deb",  "")
                cc_c = cc.get("cc_cred", "")
                v_
                st.session_state.resultado_bytes = resultado_bytes; st.session_state.resultado_nome = "lancamentos.txt"
                st.session_cc = cc.get("valor",   0.0)
                # Emite se tstate.resumo = resumo; st.session_state.erros_lote = erros
                crono.etapa("Geração do logiver pelo menos um CC preenchido
                if cc_d or cc_c:
                    v_fmt = f"{v_cc:.")
                log_txt = _montar_log_lote(resumo,erros,ni,2f}".replace(".", ",")
                    buf.write(f"|6110|{cc_d}|{cc_cti,inf,n_gravados,0,"N/A (Excel)",}|{v_fmt}|\n")
                    cnt["t6110"] += 1

        def _escreve(deb_crono)
                st.session_state.log_bytes = log_txt.encode("utf-8-sig"); st.session_state.log_nome = "logcta: str, cred_cta: str, valor: float,
                     hist: str, filial: str, idx: int):
            """Escreve |6100| e imediat_conversao.txt"
                total_seg = crono.encerrar(); log.append(f"\nTempo total: {Cronometro.fmt(total_seg)}")
                st.session_state.metricas = {
                    "Lotes total":f"{len(resumo):,}","Lotes OKamente seus |6110| filhos."""
            valor_fmt = f"{valor:.2f}".replace(".", ",")
            hist_safe = _norm_hist(hist)
            buf.write(f"|6100|{data}|{deb_cta}|{cred_":f"{len(resumo)-len(erros):,}",
                    "Lotes erro":f"{len(erros):,}","Regcta}|{valor_fmt}||{hist_safe}||{filial}||\n")
            cnt["t6100"] += 1
            _emite_6110(idx. gerados":f"{n_gravados:,}",
                    "Tamanho saída":f"{len(resultado_bytes)/1024:.1f} KB"
                }
                st.session_state.log_linhas = log; st.session_state.processado = True
                prog_bar.progress(100); status_txt.text("Concluído!")

            # ── T)

        # Escreve 6000
        buf.write(f"|6000|{tipo_real}||||\n")
        cnt["t6000"] += 1

        # ── TIPO X —XT POSICIONAL DOMÍNIO ─────────────────────────────────────────
            elif tipo == "dominio_pos":
                crono.etapa("Parse posicional") 1 débito × 1 crédito ────────────────────────────────────
        if tipo_real
                log.append("── TXT POSICIONAL DOMÍNIO ──")
                resultado_bytes, metricas, == "X":
            d = debs[0]; c = creds[0]
            h   = d["hist"] erros_parse, filiais_enc = processar_dominio_posicional( or c["hist"]
            fil = _filial_p(d) or _filial_p(c)
            # Escreve o
                    conteudo, ni, gerar_6110, usar_de_para, mapa_filiais,
                    log, prog_bar, status_txt
                )
                # Atualiza filiais (parse completo pode ter 6100 com deb+cred e emite os 6110  mais que pre-scan)
                st.session_state.filiais_detectadas = filiais_encdo idx do débito
            _escreve(d["cta_deb"], c["cta_cred"], d["valor"], h, fil, d["idx"])
            # Se crédito tem idx diferente e tem

                nome_saida = f"DOM_POS_{ni}_dominio.txt"
                st.session_state.resultado_bytes = resultado_bytes centros próprios, emite também
            if gerar_6110 and c["idx"] != d["idx"] and c["idx"] in centros_por_
                st.session_state.resultado_nome  = nome_saida
                st.session_state.metricas        = metricas
                st.session_state.processado      = True
                ifpartida:
                _emite_6110(c["idx"])

        # ── TIPO D — 1 débito → vários créditos ── erros_parse:
                    erros_txt = _txt_erros_ecd(erros_parse, ni)
                    st.session_state.erros_bytes = erros_txt.encode("utf-8-sig")
                    st.session_state.erros_nome  = f"DOM_POS_{ni}_erros.txt"
                total_seg = crono.encerrar()
                log.append(────────────────────────────
        elif tipo_real == "D":
            d = debs[0]
            _escreve(d["cta_deb"], "", d["valor"], d["hist"], _filial_p(d), d["idx"])
            for c in creds:
                h   = c["hist"] or d["histf"\n── TEMPO TOTAL: {Cronometro.fmt(total_seg)} ──")
                for e in crono.etapas: log.append(f"  {e['nome']}: {Cronometro.fmt"]
                fil = _filial_p(c) or _filial_p(d)
                _escreve("", c["cta_cred"], c["valor"], h, fil, c["idx"])(e['segundos'])}")
                st.session_state.log_linhas = log

            # ── TXT STREAMING (separador

        # ── TIPO C — vários débitos → 1 crédito ──────────────────────────────
        elif tipo_real == ";") ──────────────────────────────────
            else:
                crono.etapa("Processamento streaming "C":
            c = creds[0]
            _escreve("", c["cta_cred"], c["valor"], c["hist"], _filial_p(c), c["idx"])"); mb_txt = len(conteudo)/(1024*1024)
                status_txt.text(f"Processando {mb_txt:.1f} MB em streaming..."); prog_bar.progress(5)
                log.append(
            for d in debs:
                h   = d["hist"] or c["hist"]
                fil = _filial_p(d) or _filial_p(c)
                _escreve(d["cta_deb"], "", d["valor"], h, fil, d["idx"])

        # ── TIPO V — vários débitos × vários créditos ─────────────────────────
        else:
            forf"── TXT STREAMING — {mb_txt:.1f} MB ──")
                resultado_bytes,resumo,erros,total_lins,ignoradas,enc_usado c in creds:
                _escreve("", c["cta_cred"], c["valor"], c["hist"], _filial_p(c), c["idx"])
            for d in debs: = processar_streaming(conteudo,ni,log)
                prog_bar.progress(90); n_gravados = resultado_bytes.count(b"|6000|")
                st.session
                _escreve(d["cta_deb"], "", d["valor"], d["hist"], _filial_p(d), d["idx"])

        ok += 1

    log.append(f"  Reg. 6000 gerados  : {cnt['t6000_state.resultado_bytes = resultado_bytes; st.session_state.resultado_nome = "lancamentos.txt"
                st.session_state.resumo = resumo; st.session_state.erros_lote = erros
                crono.etapa("Geração do log")
                log_txt = _montar_log_lote(resumo,erros,ni,ti,inf,n_gravados,ignor']:,}")
    log.append(f"  Reg. 6100 gerados  : {cnt['t6100']:,}")
    if gerar_6110:
        adas,enc_usado,crono)
                st.session_state.log_bytes = log_txt.encode("utf-8-sig"); st.session_state.log_nome = "log_conversao.txt"
                total_seglog.append(f"  Reg. 6110 gerados  : {cnt['t6110']:,}")
    log.append(f"  Lotes OK            = crono.encerrar(); log.append(f"\nTempo total: {Cronometro.fmt(total_seg)}")
                st.session_state.metricas = {
                    "Lin: {ok:,}")
    log.append(f"  Lotes ignorados    : {ignorados:,}")
    log.append(f"  Tipos —has lidas":f"{total_lins:,}","Lotes total":f"{len(resumo):,}",
                    "Lotes OK X:{debug.get('X',0)} "
               f"D:{debug.get('D',0)} "
               f"C:{debug.get('C',0)} "
               f"V:{debug.get('V',0)}")

    resultado":f"{len(resumo)-len(erros):,}","Lotes erro":f"{len(erros):,}",
                    "Reg. gerados":f"{n_gravados:,}"," = buf.getvalue().encode("utf-8-sig")
    del buf; gc.collect()
    return resultadoTamanho saída":f"{len(resultado_bytes)/1024:.1f} KB"
                }
                st.session_state.log_linhas = log; st.session_state.processado = True
                prog_bar


# ─────────────────────────────────────────────────────────────────────────────
# WIDGET DE/.progress(100); status_txt.text("Concluído!")

        except Exception as ex:
            tb = traceback.format_exc(); st.error(f"PARA FILIAIS
# ─────────────────────────────────────────────────────────────────────────────
def⛔ Erro inesperado: {ex}")
            log.append(f"ERRO FATAL: {ex}\n{tb}"); st _widget_de_para_filiais(habilitado: bool) -> dict:
    if.session_state.log_linhas = log
            prog_bar.progress(0); status_txt.text("Falha.")

        st not habilitado:
        return {}

    st.markdown("""
    <div style='background:#.rerun()

    # ── Exibição de resultados ────────────────────────────────0a1a2e;border:1px solid #6EC6────────────────
    if st.session_state.processado:
        tipo_proc = st.session_state.tipo_detectado
        if tipo_proc == "ecd":
            _FF;border-radius:8px;
                padding:14px 18px;margin:10px 0;'>
    render_resultados_ecd(exibir_log)
        elif tipo_proc == "dominio_pos":
            _render_resultados_pos<b style='color:#6EC6FF;'>🏢 Mapeamento De/Para — Códigoicional(exibir_log)
        else:
            _render_resultados_lote(exibir_log)


if __name__ == "__main__ da Filial</b><br>
    <small style='color:#9BB0":
    main()
