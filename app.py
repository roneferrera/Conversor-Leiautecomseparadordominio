# -*- coding: utf-8 -*-
"""
Domínio Sistemas — Conversor Unificado
Suporta:
  • Lançamentos Contábeis (TXT/Excel) → 0000 + 6000 + 6100
  • SPED ECD (.txt)                   → 0000 + 6000 + 6100
Identificação automática do tipo de arquivo no upload.
"""
import os
import re
import gc
import time
import traceback
import unicodedata
import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
from threading import Thread

# ═══════════════════════════════════════════════════════════════════════════════
# TEMA — Thomson Reuters
# ═══════════════════════════════════════════════════════════════════════════════
TEMA = {
    "bg_escuro":  "#0A0E1A",
    "bg_medio":   "#0D1526",
    "bg_card":    "#102040",
    "bg_input":   "#0F1E35",
    "acento":     "#FF6B00",
    "acento2":    "#1E90FF",
    "acento3":    "#00C896",
    "amarelo":    "#FFD166",
    "texto":      "#E8ECF0",
    "texto_dim":  "#6B7A8D",
    "borda":      "#1A3050",
    "btn_hover":  "#CC5500",
    "fonte":      "Segoe UI",
    "fonte_mono": "Consolas",
    "cor_0000":   "#FFD166",
    "cor_6000":   "#C084FC",
    "cor_6100":   "#4ADE80",
    "cor_erro":   "#FF4444",
    "cor_ok":     "#00C896",
    "cor_susp":   "#FF9500",
    "cor_enc":    "#A78BFA",
    "cor_tempo":  "#38BDF8",
    "cor_ecd":    "#F472B6",   # rosa — identificador SPED ECD
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════════════
CHUNK_SIZE  = 50_000
BUFFER_IO   = 8 * 1024 * 1024
WRITE_CHUNK = 10_000
MAX_PREV    = 24
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
# CRONÔMETRO
# ═══════════════════════════════════════════════════════════════════════════════
class Cronometro:
    def __init__(self):
        self._inicio_total: float = 0.0
        self._etapas: list        = []
        self._inicio_etapa: float = 0.0
        self._etapa_atual: str    = ""

    def iniciar(self):
        self._inicio_total = time.perf_counter()
        self._etapas.clear()

    def etapa(self, nome: str):
        agora = time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({
                "nome": self._etapa_atual,
                "segundos": round(agora - self._inicio_etapa, 3),
            })
        self._etapa_atual  = nome
        self._inicio_etapa = agora

    def encerrar(self) -> float:
        agora = time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({
                "nome": self._etapa_atual,
                "segundos": round(agora - self._inicio_etapa, 3),
            })
            self._etapa_atual = ""
        return round(agora - self._inicio_total, 3)

    @staticmethod
    def fmt(segundos: float) -> str:
        if segundos < 0.001: return "<1ms"
        if segundos < 1:     return f"{segundos*1000:.0f}ms"
        if segundos < 60:    return f"{segundos:.2f}s"
        m = int(segundos // 60); s = segundos % 60
        return f"{m}min {s:.1f}s"

    def relatorio(self) -> list:
        return [
            f"  {'  ' + e['nome']:<38} {self.fmt(e['segundos']):>8}"
            for e in self._etapas
        ]

    @property
    def etapas(self): return self._etapas


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS GERAIS
# ═══════════════════════════════════════════════════════════════════════════════
def sanitizar_texto(texto: str) -> str:
    if not texto: return ""
    texto = texto.replace("|", " ")
    return re.sub(r" {2,}", " ", texto).strip()

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

def ts_log():   return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def ts_arq():   return datetime.now().strftime("%Y%m%d_%H%M%S")
def so_nums(v): return re.sub(r"\D", "", str(v))

_VAZIO_CONTA = frozenset(("", "nan", "none", "0", "0.0"))

def limpar_contas_vec(serie: pd.Series) -> np.ndarray:
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

def limpar_valor_vec(serie: pd.Series) -> np.ndarray:
    return (
        pd.to_numeric(
            serie.fillna("0").astype(str).str.strip()
                 .str.replace(",", ".", regex=False)
                 .str.replace(r"[^\d.\-]", "", regex=True),
            errors="coerce"
        ).fillna(0.0).round(2).to_numpy(dtype=np.float64)
    )

# ═══════════════════════════════════════════════════════════════════════════════
# CNPJ / CPF
# ═══════════════════════════════════════════════════════════════════════════════
def validar_cnpj(cnpj):
    c = so_nums(cnpj)
    if len(c) != 14 or len(set(c)) == 1: return False
    def d(c, p):
        s = sum(int(c[i]) * p[i] for i in range(len(p)))
        r = s % 11; return 0 if r < 2 else 11 - r
    return (int(c[12]) == d(c, [5,4,3,2,9,8,7,6,5,4,3,2]) and
            int(c[13]) == d(c, [6,5,4,3,2,9,8,7,6,5,4,3,2]))

def validar_cpf(cpf):
    c = so_nums(cpf)
    if len(c) != 11 or len(set(c)) == 1: return False
    def d(c, n):
        s = sum(int(c[i]) * (n - i) for i in range(n - 1))
        r = (s * 10) % 11; return 0 if r == 10 else r
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

# ═══════════════════════════════════════════════════════════════════════════════
# DETECÇÃO DE ENCODING
# ═══════════════════════════════════════════════════════════════════════════════
_CHARS_PT = set(
    "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞß"
    "àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿºª"
)

def _detectar_encoding(caminho: str) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1", "iso-8859-1"):
        try:
            with open(caminho, "r", encoding=enc, errors="strict") as f:
                amostra = f.read(16384)
            if sum(1 for c in amostra if c in _CHARS_PT) > 0 \
               or enc in ("utf-8-sig", "utf-8"):
                return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "latin-1"

# ═══════════════════════════════════════════════════════════════════════════════
# IDENTIFICAÇÃO AUTOMÁTICA DO TIPO DE ARQUIVO
# ═══════════════════════════════════════════════════════════════════════════════
def identificar_tipo_arquivo(caminho: str) -> str:
    """
    Retorna:
      'ecd'   — arquivo SPED ECD (contém |0000| e |I200| ou |I050|)
      'excel' — arquivo Excel (.xlsx/.xls)
      'lote'  — TXT de lançamentos em lote (separado por ;)
    """
    ext = os.path.splitext(caminho)[1].lower()
    if ext in (".xlsx", ".xls", ".xlsm"):
        return "excel"

    enc = _detectar_encoding(caminho)
    try:
        with open(caminho, "r", encoding=enc, errors="replace") as f:
            amostra = f.read(8192)
    except Exception:
        return "lote"

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

    # Heurística: se tiver ponto-e-vírgula como separador → lote
    semis = sum(1 for ln in linhas[:20] if ";" in ln)
    if semis >= max(1, len(linhas[:20]) // 2):
        return "lote"

    return "lote"

# ═══════════════════════════════════════════════════════════════════════════════
# FORMATAÇÃO DE REGISTROS DE SAÍDA
# ═══════════════════════════════════════════════════════════════════════════════
def fmt_reg_0000(ni: str) -> str:
    return f"|0000|{ni}|"

def fmt_reg_6000(tipo: str) -> str:
    return f"|6000|{tipo}||||"

def fmt_reg_6100(data: str, deb: str, cred: str, valor: float,
                 cod_hist: str, desc: str, usuario: str,
                 filial: str, scp: str) -> str:
    valor_fmt = f"{valor:.2f}".replace(".", ",")
    desc_safe = sanitizar_texto(desc)
    return (f"|6100|{data}|{deb}|{cred}|{valor_fmt}"
            f"|{cod_hist}|{desc_safe}|{usuario}|{filial}|{scp}|")

# ═══════════════════════════════════════════════════════════════════════════════
# ▌▌▌ MÓDULO SPED ECD ▌▌▌
# ═══════════════════════════════════════════════════════════════════════════════
_MAPA_ESPECIAIS = {
    "\u2018":"'","\u2019":"'","\u201C":'"',"\u201D":'"',
    "\u2013":"-","\u2014":"-","\u2026":"...","\u00A0":" ",
    "\u00D7":"x","\u00F7":"/","\u20AC":"EUR","\u00A7":"S/",
    "\u00AE":"(R)","\u00A9":"(C)","\u2122":"(TM)",
}

def _normalizar_hist_ecd(texto: str) -> str:
    if not texto: return ""
    for orig, dest in _MAPA_ESPECIAIS.items():
        texto = texto.replace(orig, dest)
    texto = unicodedata.normalize("NFC", texto)
    resultado = []
    for ch in texto:
        if ord(ch) < 0x20 and ord(ch) not in (0x09, 0x0A, 0x0D): continue
        try:
            ch.encode("latin-1"); resultado.append(ch)
        except (UnicodeEncodeError, UnicodeDecodeError):
            base = unicodedata.normalize("NFD", ch)[0]
            try:    base.encode("latin-1"); resultado.append(base)
            except: pass
    return re.sub(r" {2,}", " ", "".join(resultado)).strip()[:250]

def _split_pipe(linha: str) -> list:
    campos = linha.strip().split("|")
    if campos and campos[0] == "":  campos = campos[1:]
    if campos and campos[-1] == "": campos = campos[:-1]
    return campos

def _conta_valida(conta: str) -> bool:
    return bool(conta) and conta.isdigit()

class SpedECD:
    def __init__(self):
        self.cnpj        = ""
        self.contas      = {}
        self.historicos  = {}
        self.lancamentos = []

def _parse_ecd(conteudo_bytes: bytes, log_cb, prog_cb) -> tuple:
    """
    Retorna (SpedECD, registros_erro) ou (None, registros_erro).
    log_cb(msg)  — callback de log
    prog_cb(msg, pct) — callback de progresso
    """
    ecd              = SpedECD()
    lote_atual       = None
    erros_parse      = 0
    registros_erro   = []
    contas_invalidas = 0

    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            texto = conteudo_bytes.decode(enc, errors="strict")
            log_cb(f"  Encoding detectado: {enc}")
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        texto = conteudo_bytes.decode("utf-8", errors="replace")
        log_cb("  Aviso: encoding não identificado — UTF-8 com substituição.")

    linhas_lista = texto.splitlines()
    total        = len(linhas_lista) or 1
    prog_cb("Lendo registros SPED ECD...", 10)

    for num_linha, linha in enumerate(linhas_lista, start=1):
        if num_linha % 2000 == 0 or num_linha == total:
            pct = 10 + int((num_linha / total) * 40)
            prog_cb(f"Lendo linha {num_linha:,}/{total:,}...", pct)

        linha_orig = linha
        linha      = linha.strip()
        if not linha: continue
        campos   = _split_pipe(linha)
        if not campos: continue
        registro = campos[0]

        try:
            if registro == "0000":
                if len(campos) > 5: ecd.cnpj = campos[5].strip()

            elif registro == "I050":
                if len(campos) > 7:
                    cod = campos[5].strip(); nome = campos[7].strip()
                    if cod: ecd.contas[cod] = nome

            elif registro == "I075":
                if len(campos) > 2:
                    ecd.historicos[campos[1].strip()] = \
                        _normalizar_hist_ecd(campos[2])

            elif registro == "I200":
                lote_atual = {
                    "num"     : campos[1].strip() if len(campos) > 1 else "",
                    "data"    : campos[2].strip() if len(campos) > 2 else "",
                    "valor"   : campos[3].strip() if len(campos) > 3 else "",
                    "partidas": [],
                }
                ecd.lancamentos.append(lote_atual)

            elif registro == "I250":
                if lote_atual is None: continue
                if len(campos) <= 4:
                    motivo = "I250 com campos insuficientes"
                    registros_erro.append({
                        "linha": num_linha, "motivo": motivo,
                        "conteudo": linha_orig.strip()})
                    continue

                dc_raw = campos[4].strip().upper()
                if dc_raw not in ("D", "C"):
                    motivo = f"I250 dc='{dc_raw}' inválido"
                    registros_erro.append({
                        "linha": num_linha, "motivo": motivo,
                        "conteudo": linha_orig.strip()})
                    continue

                conta = campos[1].strip()
                if not _conta_valida(conta):
                    motivo = f"Conta '{conta}' contém caracteres não numéricos"
                    registros_erro.append({
                        "linha": num_linha, "motivo": motivo,
                        "conteudo": linha_orig.strip()})
                    contas_invalidas += 1
                    continue

                lote_atual["partidas"].append({
                    "conta"     : conta,
                    "valor"     : campos[3].strip(),
                    "dc"        : dc_raw,
                    "descr_hist": _normalizar_hist_ecd(
                        campos[7] if len(campos) > 7 else ""),
                })

            elif registro in ("I299", "I300"):
                lote_atual = None

        except Exception as ex:
            motivo = f"Exceção em {registro}: {ex}"
            registros_erro.append({
                "linha": num_linha, "motivo": motivo,
                "conteudo": linha_orig.strip()})
            erros_parse += 1
            if erros_parse > 50:
                log_cb("ERRO: muitos erros de parse — abortando leitura.")
                return None, registros_erro

    if not ecd.cnpj:
        log_cb("ERRO: CNPJ não encontrado no registro 0000.")
        return None, registros_erro

    log_cb(f"  Leitura concluída — CNPJ: {ecd.cnpj}")
    log_cb(f"  Contas      : {len(ecd.contas):,}")
    log_cb(f"  Históricos  : {len(ecd.historicos):,}")
    log_cb(f"  Lançamentos : {len(ecd.lancamentos):,}")
    if contas_invalidas:
        log_cb(f"  Contas inválidas ignoradas: {contas_invalidas:,}")
    if registros_erro:
        log_cb(f"  Linhas com aviso/erro     : {len(registros_erro):,}")
    return ecd, registros_erro

# ── helpers ECD ───────────────────────────────────────────────────────────────
def _fmt_data_ecd(d: str) -> str:
    d = d.strip()
    if "/" in d: return d
    if len(d) == 8 and d.isdigit():
        return f"{d[:2]}/{d[2:4]}/{d[4:]}"
    return d

def _fmt_valor_ecd(v) -> str:
    if isinstance(v, float):
        return f"{v:.2f}".replace(".", ",")
    v = str(v).strip()
    if "." in v and "," not in v: v = v.replace(".", ",")
    elif "." in v and "," in v:
        if v.index(".") < v.index(","):
            v = v.replace(".", "").replace(",", ".").replace(".", ",")
    if "," not in v: v += ",00"
    else:
        p = v.split(",")
        if len(p[1]) < 2: p[1] = p[1].ljust(2, "0")
        v = ",".join(p)
    return v

def _str_to_float_ecd(v) -> float:
    if isinstance(v, (int, float)): return float(v)
    v = str(v).strip()
    if "." in v and "," in v:
        if v.index(".") < v.index(","): v = v.replace(".", "").replace(",", ".")
        else: v = v.replace(",", "")
    elif "," in v: v = v.replace(",", ".")
    try:    return float(v)
    except: return 0.0

def _montar_hist(p: dict) -> str:
    return p.get("descr_hist", "").strip()

def _primeiro_hist(partidas: list) -> str:
    for p in partidas:
        h = _montar_hist(p)
        if h: return h
    return ""

def _agrupar_partidas(partidas: list) -> list:
    ag = {}
    for p in partidas:
        chave = (p["conta"], p["dc"])
        if chave not in ag:
            ag[chave] = {"conta": p["conta"], "valor": 0.0,
                         "dc": p["dc"], "descr_hist": p.get("descr_hist","")}
        ag[chave]["valor"] += _str_to_float_ecd(p["valor"])
        if not ag[chave]["descr_hist"] and p.get("descr_hist"):
            ag[chave]["descr_hist"] = p["descr_hist"]
    return list(ag.values())

def _classificar_ecd(nd: int, nc: int) -> str:
    if nd == 1 and nc == 1: return "X"
    if nd == 1 and nc > 1:  return "D"
    if nc == 1 and nd > 1:  return "C"
    return "V"

def _linhas_lancamento_ecd(lanc: dict) -> list:
    partidas = _agrupar_partidas(lanc["partidas"])
    debs  = [p for p in partidas if p["dc"] == "D"]
    creds = [p for p in partidas if p["dc"] == "C"]
    if not debs or not creds: return []

    data = _fmt_data_ecd(lanc["data"])
    tipo = _classificar_ecd(len(debs), len(creds))
    hist = _primeiro_hist(lanc["partidas"])
    out  = [fmt_reg_6000(tipo)]

    def _6100_x(db, cr):
        val = _fmt_valor_ecd(db["valor"])
        h   = _montar_hist(db) or hist
        return f"|6100|{data}|{db['conta']}|{cr['conta']}|{val}||{h}|||||||"

    def _6100_deb(db):
        val = _fmt_valor_ecd(db["valor"])
        h   = _montar_hist(db) or hist
        return f"|6100|{data}|{db['conta']}||{val}||{h}|||||||"

    def _6100_cred(cr):
        val = _fmt_valor_ecd(cr["valor"])
        h   = _montar_hist(cr) or hist
        return f"|6100|{data}||{cr['conta']}|{val}||{h}|||||||"

    if tipo == "X":
        out.append(_6100_x(debs[0], creds[0]))
    elif tipo == "D":
        for db in debs:  out.append(_6100_deb(db))
        for cr in creds: out.append(_6100_cred(cr))
    elif tipo == "C":
        for cr in creds: out.append(_6100_cred(cr))
        for db in debs:  out.append(_6100_deb(db))
    else:
        for db in debs:  out.append(_6100_deb(db))
        for cr in creds: out.append(_6100_cred(cr))
    return out

def _gerar_ecd(ecd: SpedECD, log_cb, prog_cb) -> tuple:
    """Retorna (linhas_geradas, resumo_dict)."""
    linhas  = [fmt_reg_0000(re.sub(r"\D", "", ecd.cnpj))]
    t6000 = t6100 = ignorados = 0
    debug_tipos = {"X":0,"D":0,"C":0,"V":0}
    total = len(ecd.lancamentos)

    for idx, lanc in enumerate(ecd.lancamentos):
        if idx % 500 == 0 or idx == total - 1:
            pct = 55 + int(((idx+1)/total)*35)
            prog_cb(f"Gerando lançamento {idx+1:,}/{total:,}...", pct)

        if not lanc.get("partidas"):
            ignorados += 1; continue

        novas = _linhas_lancamento_ecd(lanc)
        if not novas:
            ignorados += 1; continue

        for l in novas:
            if l.startswith("|6000|"):
                t = l.split("|")[2] if len(l.split("|")) > 2 else "?"
                debug_tipos[t] = debug_tipos.get(t, 0) + 1
                t6000 += 1
            elif l.startswith("|6100|"):
                t6100 += 1
        linhas.extend(novas)

    resumo = {
        "t6000": t6000, "t6100": t6100,
        "ignorados": ignorados, "total": len(linhas),
        "tipos": debug_tipos,
    }
    log_cb(f"  Registros 6000 : {t6000:,}")
    log_cb(f"  Registros 6100 : {t6100:,}")
    log_cb(f"  Ignorados      : {ignorados:,}")
    log_cb(f"  Total linhas   : {len(linhas):,}")
    log_cb(f"  Tipos — X:{debug_tipos['X']} D:{debug_tipos['D']} "
           f"C:{debug_tipos['C']} V:{debug_tipos['V']}")
    return linhas, resumo

# ═══════════════════════════════════════════════════════════════════════════════
# ▌▌▌ MÓDULO LANÇAMENTOS EM LOTE (TXT / EXCEL) ▌▌▌
# ═══════════════════════════════════════════════════════════════════════════════
def _filtrar_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    for c in COLS_PADRAO:
        if c not in chunk.columns: chunk[c] = ""
    for c in COLS_PADRAO:
        chunk[c] = chunk[c].fillna("").astype(str).str.strip()
    il = chunk["Inicia Lote"].str.strip()
    chunk["Inicia Lote"] = il.where(il.str.fullmatch(r"[1-9]\d*"), "")
    m_data  = chunk["Data"] != ""
    datas   = pd.to_datetime(chunk.loc[m_data,"Data"], dayfirst=True, errors="coerce")
    m_dv    = m_data.copy(); m_dv[m_data] = datas.notna()
    m_conta = ((chunk["Cód. Conta Debito"] != "") |
               (chunk["Cód. Conta Credito"] != ""))
    m_valor = chunk["Valor"].str.strip() != ""
    return chunk[m_dv & m_conta & m_valor].copy()

def ler_txt_lote(caminho: str, cb=None) -> tuple:
    enc = _detectar_encoding(caminho)
    if cb: cb(f"Encoding: {enc}. Contando linhas...", 5)
    with open(caminho, "r", encoding=enc, errors="replace") as f:
        total_linhas = sum(1 for _ in f)
    partes=[]; total=0; validas=0; linha_at=0
    reader = pd.read_csv(
        caminho, sep=";", header=None, names=COLS_PADRAO, dtype=str,
        encoding=enc, encoding_errors="replace", on_bad_lines="skip",
        engine="c", usecols=range(len(COLS_PADRAO)), low_memory=False,
        chunksize=CHUNK_SIZE)
    for i, chunk in enumerate(reader):
        n = len(chunk)
        chunk["_linha_origem"] = np.arange(
            linha_at+1, linha_at+n+1, dtype=np.int32)
        linha_at += n; total += n
        filtrado = _filtrar_chunk(chunk); validas += len(filtrado)
        if len(filtrado) > 0: partes.append(filtrado)
        pct = min(28, 5 + int(linha_at / max(1, total_linhas) * 23))
        if cb: cb(f"Lendo... {linha_at:,}/{total_linhas:,} ({validas:,} válidas)", pct)
        del chunk, filtrado
        if i % 5 == 0: gc.collect()
    if not partes:
        raise ValueError(
            "Nenhuma linha válida encontrada.\n"
            "Verifique: separador  ;  e ordem das colunas.")
    if cb: cb("Concatenando...", 29)
    df = pd.concat(partes, ignore_index=True, copy=False)
    del partes; gc.collect()
    if cb: cb(f"TXT OK — {validas:,} válidas, {total-validas:,} ignoradas.", 30)
    return df, total - validas, enc

_COLS_ESP_LOW = [c.lower() for c in COLS_PADRAO[:8]]

def detectar_cabecalho(caminho: str, sheet: str) -> tuple:
    raw   = pd.read_excel(caminho, sheet_name=sheet, header=None, nrows=25)
    pasta = None
    try:
        v = str(raw.iloc[1,6]).strip()
        if v and v.lower() not in ("nan","none",""): pasta = v
    except: pass
    for i, row in raw.iterrows():
        vals = [str(v).strip().lower() for v in row if not eh_vazio(v)]
        if sum(1 for c in _COLS_ESP_LOW if c in vals) >= 4:
            return i, pasta
    return 3, pasta

def ler_excel_lote(caminho: str, sheet: str, linha_h: int, cb=None) -> tuple:
    if cb: cb("Lendo Excel...", 8)
    raw = pd.read_excel(caminho, sheet_name=sheet, header=None,
                        dtype=str, engine="openpyxl")
    pasta = "C:\\Temp"
    try:
        v = str(raw.iloc[1,6]).strip()
        if v and v.lower() not in ("nan","none",""): pasta = v
    except: pass
    while raw.shape[1] < len(COLS_PADRAO)+2: raw[raw.shape[1]] = ""
    raw.columns = range(raw.shape[1])
    df = raw.iloc[linha_h+1:].reset_index(drop=True).copy()
    del raw; gc.collect()
    df.columns = list(range(df.shape[1]))
    df = df.rename(columns={i:c for i,c in enumerate(COLS_PADRAO)})
    _V = {"nan","NaN","None","none",""}
    for c in COLS_PADRAO:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str).str.strip().replace(list(_V),"")
    mask = ~((df["Data"]=="") & (df["Cód. Conta Debito"]=="") &
             (df["Cód. Conta Credito"]=="") & (df["Valor"]==""))
    df = df[mask].reset_index(drop=True).copy()
    df["_linha_origem"] = (df.index + linha_h + 2).astype(np.int32)
    if cb: cb(f"Excel OK — {len(df):,} linhas.", 30)
    return df, pasta

def montar_lotes(df: pd.DataFrame, cb=None) -> pd.DataFrame:
    if cb: cb("Montando lotes...", 33)
    R = df.copy()
    for col in COLS_PADRAO + ["_linha_origem"]:
        if col not in R.columns: R[col] = ""
    inicia    = R["Inicia Lote"].fillna("").astype(str).str.strip()
    tem_ini   = bool((inicia != "").any())
    if tem_ini:
        marcador       = (inicia != "").to_numpy(dtype=bool)
        R["_num_lote"] = np.where(np.cumsum(marcador) > 0,
                                  np.cumsum(marcador, dtype=np.int32),
                                  np.int32(1))
    else:
        desc  = (R["Complemento Histórico"].fillna("").astype(str).str.strip()
                 .str.upper().str.replace(r"\s+", " ", regex=True))
        chave = (R["Data"].fillna("").astype(str).str.strip()
                 + "|||" + desc).to_numpy()
        muda       = np.empty(len(chave), dtype=bool)
        muda[0]    = True; muda[1:] = chave[1:] != chave[:-1]
        R["_num_lote"] = np.cumsum(muda, dtype=np.int32)
    nl  = int(R["_num_lote"].max()) if len(R) > 0 else 0
    mod = "Inicia Lote" if tem_ini else "Data + Descrição"
    if cb: cb(f"Lotes: {nl:,}  [modo: {mod}].", 36)
    return R

def tipo_lancamento(nd: int, nc: int) -> str:
    if nd==1 and nc==1: return "X"
    if nd==1 and nc >1: return "D"
    if nd >1 and nc==1: return "C"
    return "V"

def diagnosticar_lote(g2: pd.DataFrame, dif: float) -> dict:
    debs  = g2[g2["td"]].copy(); creds = g2[g2["tc"]].copy()
    td    = round(float(debs["vf"].sum()),2)
    tc    = round(float(creds["vf"].sum()),2)
    linhas_det = []
    for _, r in g2.iterrows():
        linhas_det.append({
            "linha_origem":  int(r["lo"]),
            "data":          formatar_data(r["dt"]),
            "conta_debito":  str(r["cd"]) if r["td"] else "",
            "conta_credito": str(r["cc"]) if r["tc"] else "",
            "valor":         float(r["vf"]),
            "descricao":     sanitizar_texto(str(r["desc"]))[:70],
            "tipo":          "D" if r["td"] else "C",
        })
    suspeitas = []; dif_abs = abs(dif)
    for r in linhas_det:
        if abs(r["valor"] - dif_abs) < TOL_VALOR:
            suspeitas.append({**r,"motivo":
                f"Valor R$ {r['valor']:.2f} igual à diferença — possível duplicata"})
    if not suspeitas:
        for r in linhas_det:
            v = r["valor"]
            if r["tipo"] == "D":
                if abs(round(td-v,2)-tc) < TOL_VALOR:
                    suspeitas.append({**r,"motivo":
                        f"Remover DÉBITO R$ {v:.2f} zeraria o lote"})
            else:
                if abs(td-round(tc-v,2)) < TOL_VALOR:
                    suspeitas.append({**r,"motivo":
                        f"Remover CRÉDITO R$ {v:.2f} zeraria o lote"})
    sugestao = (
        f"Débito excede crédito em R$ {dif_abs:.2f}." if td > tc else
        f"Crédito excede débito em R$ {dif_abs:.2f}.")
    return {"total_debito":td,"total_credito":tc,"diferenca":dif_abs,
            "qtd_debitos":len(debs),"qtd_creditos":len(creds),
            "linhas":linhas_det,"suspeitas":suspeitas,"sugestao":sugestao}

def _gerar_registros_lote(W_ok: pd.DataFrame, cnt: pd.DataFrame, cb=None):
    mask_x  = (cnt["nd"]==1) & (cnt["nc"]==1)
    lotes_x = cnt[mask_x].index; lotes_c = cnt[~mask_x].index
    if len(lotes_x) > 0:
        Wd = (W_ok[W_ok["td"] & W_ok["nl"].isin(lotes_x)]
              [["nl","cd","vf","hist","desc","dt","fil"]].copy())
        Wc = (W_ok[W_ok["tc"] & W_ok["nl"].isin(lotes_x)][["nl","cc"]].copy())
        M  = Wd.merge(Wc, on="nl", how="inner")
        for _, row in M.iterrows():
            data = formatar_data(row["dt"]); deb = str(row["cd"])
            cred = str(row["cc"]); valor = float(row["vf"])
            hist = limpar_int(row["hist"]) if str(row["hist"]).strip() not in ("","nan") else ""
            desc = str(row["desc"]).strip()
            fil  = str(row["fil"]).strip() if str(row["fil"]).strip() not in ("","nan") else ""
            yield fmt_reg_6000("X")
            yield fmt_reg_6100(data, deb, cred, valor, hist, desc, "", fil, "")
        del Wd, Wc, M; gc.collect()
    if len(lotes_c) > 0:
        Wcomp  = W_ok[W_ok["nl"].isin(lotes_c)]
        nc_tot = len(lotes_c)
        for i, (nl_c, g2) in enumerate(Wcomp.groupby("nl", sort=False)):
            if cb and i % max(1, nc_tot//20) == 0:
                cb(f"Compostos: {i:,}/{nc_tot:,}...", 70+int(i/nc_tot*16))
            nd  = int(cnt.loc[nl_c,"nd"]) if nl_c in cnt.index else 0
            nc2 = int(cnt.loc[nl_c,"nc"]) if nl_c in cnt.index else 0
            tp  = tipo_lancamento(nd, nc2)
            yield fmt_reg_6000(tp)
            debs  = g2[g2["td"]].reset_index(drop=True)
            creds = g2[g2["tc"]].reset_index(drop=True)
            if tp == "D":
                rd = debs.iloc[0]
                data = formatar_data(rd["dt"])
                hist = limpar_int(rd["hist"]) if str(rd["hist"]).strip() not in ("","nan") else ""
                fil  = str(rd["fil"]).strip() if str(rd["fil"]).strip() not in ("","nan") else ""
                for _, rc in creds.iterrows():
                    desc = str(rd["desc"]).strip() or str(rc["desc"]).strip()
                    yield fmt_reg_6100(data,str(rd["cd"]),str(rc["cc"]),
                                       float(rc["vf"]),hist,desc,"",fil,"")
            elif tp == "C":
                rc = creds.iloc[0]
                for _, rd in debs.iterrows():
                    data = formatar_data(rd["dt"])
                    hist = limpar_int(rd["hist"]) if str(rd["hist"]).strip() not in ("","nan") else ""
                    fil  = str(rd["fil"]).strip() if str(rd["fil"]).strip() not in ("","nan") else ""
                    desc = str(rd["desc"]).strip() or str(rc["desc"]).strip()
                    yield fmt_reg_6100(data,str(rd["cd"]),str(rc["cc"]),
                                       float(rd["vf"]),hist,desc,"",fil,"")
            else:
                for _, rd in debs.iterrows():
                    data = formatar_data(rd["dt"])
                    hist = limpar_int(rd["hist"]) if str(rd["hist"]).strip() not in ("","nan") else ""
                    fil  = str(rd["fil"]).strip() if str(rd["fil"]).strip() not in ("","nan") else ""
                    for _, rc in creds.iterrows():
                        desc = str(rd["desc"]).strip() or str(rc["desc"]).strip()
                        yield fmt_reg_6100(data,str(rd["cd"]),str(rc["cc"]),
                                           float(rc["vf"]),hist,desc,"",fil,"")

def processar_lote(df: pd.DataFrame, cb=None) -> tuple:
    if cb: cb("Preparando arrays...", 38)
    v_float  = limpar_valor_vec(df["Valor"])
    cd_arr   = limpar_contas_vec(df["Cód. Conta Debito"])
    cc_arr   = limpar_contas_vec(df["Cód. Conta Credito"])
    td_arr   = cd_arr != ""; tc_arr = cc_arr != ""
    vd_arr   = np.where(td_arr, v_float, 0.0)
    vc_arr   = np.where(tc_arr, v_float, 0.0)
    nl_arr   = df["_num_lote"].to_numpy(dtype=np.int32)
    lo_arr   = df["_linha_origem"].fillna(0).astype(int).to_numpy(dtype=np.int32)
    dt_arr   = df["Data"].fillna("").astype(str).to_numpy()
    desc_arr = np.array([sanitizar_texto(v)
                         for v in df["Complemento Histórico"].fillna("").astype(str).tolist()],
                        dtype=object)
    hist_arr = df["Cód. Histórico"].fillna("").astype(str).to_numpy()
    fil_arr  = (df["Código Matriz/Filial"].fillna("").astype(str).to_numpy()
                if "Código Matriz/Filial" in df.columns
                else np.full(len(df),"",dtype=object))
    W = pd.DataFrame({
        "nl":nl_arr,"lo":lo_arr,"vd":vd_arr,"vc":vc_arr,"vf":v_float,
        "cd":cd_arr,"cc":cc_arr,"td":td_arr,"tc":tc_arr,"dt":dt_arr,
        "desc":desc_arr,"hist":hist_arr,"fil":fil_arr,
    })
    if cb: cb("Calculando totais...", 42)
    g   = W.groupby("nl", sort=False)
    agg = g.agg(td=("vd","sum"),tc=("vc","sum"),qt=("nl","size"),
                dt=("dt","first"),ds=("desc","first"),
                lm=("lo","min"),lx=("lo","max")).reset_index()
    agg["td"]  = agg["td"].round(2); agg["tc"] = agg["tc"].round(2)
    agg["dif"] = (agg["td"]-agg["tc"]).abs().round(2)
    agg["ok"]  = agg["dif"] < TOL_VALOR
    n_lotes=len(agg); n_ok=int(agg["ok"].sum()); n_erro=n_lotes-n_ok
    if cb: cb(f"Lotes: {n_lotes:,} | {n_ok:,} OK | {n_erro:,} erro.", 50)
    erros_set = set(agg.loc[~agg["ok"],"nl"].tolist())
    ok_set    = set(agg.loc[ agg["ok"],"nl"].tolist())
    resumo=[]; erros=[]
    for r in agg.itertuples(index=False):
        lm=int(r.lm); lx=int(r.lx)
        fx = f"{lm}–{lx}" if lm!=lx else str(lm)
        e = {"num_lote":r.nl,"data":formatar_data(r.dt),
             "descricao":str(r.ds or "").strip(),
             "total_debito":float(r.td),"total_credito":float(r.tc),
             "diferenca":float(r.dif),"balanceado":bool(r.ok),
             "qtd_linhas":int(r.qt),"faixa_linhas":fx,"diagnostico":{}}
        resumo.append(e)
        if not bool(r.ok): erros.append(e)
    if erros_set:
        if cb: cb(f"Diagnosticando {len(erros_set):,} lote(s)...", 55)
        W_err = W[W["nl"].isin(erros_set)]
        for nl_err, g2 in W_err.groupby("nl", sort=False):
            ent = next(x for x in erros if x["num_lote"]==nl_err)
            ent["diagnostico"] = diagnosticar_lote(g2, ent["diferenca"])
    W_ok  = W[W["nl"].isin(ok_set)]
    cnt_d = W_ok[W_ok["td"]].groupby("nl",sort=False).size().rename("nd")
    cnt_c = W_ok[W_ok["tc"]].groupby("nl",sort=False).size().rename("nc")
    cnt   = pd.concat([cnt_d,cnt_c],axis=1).fillna(0).astype(np.int16)
    gerador = _gerar_registros_lote(W_ok, cnt, cb)
    return gerador, erros, resumo

# ═══════════════════════════════════════════════════════════════════════════════
# GRAVAÇÃO STREAMING
# ═══════════════════════════════════════════════════════════════════════════════
def gravar_arquivo(caminho: str, ni: str, gerador, cb=None) -> int:
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    total=0; buf=[]
    with open(caminho, "w", encoding="utf-8-sig", buffering=BUFFER_IO) as f:
        f.write(fmt_reg_0000(ni) + "\n")
        for linha in gerador:
            buf.append(linha); total += 1
            if len(buf) >= WRITE_CHUNK:
                f.write("\n".join(buf)); f.write("\n"); buf.clear()
        if buf: f.write("\n".join(buf)); f.write("\n")
    return total

def gravar_linhas_ecd(caminho: str, linhas: list, cb=None) -> int:
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    with open(caminho, "w", encoding="utf-8-sig", buffering=BUFFER_IO) as f:
        for i in range(0, len(linhas), WRITE_CHUNK):
            bloco = linhas[i:i+WRITE_CHUNK]
            f.write("\n".join(bloco)); f.write("\n")
            if cb: cb(f"Gravando... {min(i+WRITE_CHUNK,len(linhas)):,}/{len(linhas):,}", 90)
    return len(linhas)

# ═══════════════════════════════════════════════════════════════════════════════
# RELATÓRIO DE ERROS ECD
# ═══════════════════════════════════════════════════════════════════════════════
def gerar_txt_erros_ecd(registros_erro: list, cnpj: str, pasta: str) -> str:
    os.makedirs(pasta, exist_ok=True)
    nome = os.path.join(pasta, f"ECD_{re.sub(r'\\D','',cnpj)}_erros_{ts_arq()}.txt")
    linhas = [
        "=" * 70,
        "RELATÓRIO DE LINHAS COM ERRO / AVISO — SPED ECD",
        f"CNPJ: {cnpj}",
        f"Total de ocorrências: {len(registros_erro)}",
        "=" * 70, "",
    ]
    for i, reg in enumerate(registros_erro, 1):
        linhas += [
            f"[{i:04d}] Linha no arquivo : {reg['linha']}",
            f"       Motivo          : {reg['motivo']}",
            f"       Conteúdo        : {reg['conteudo']}", "",
        ]
    linhas += ["=" * 70, "FIM DO RELATÓRIO"]
    with open(nome, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(linhas))
    return nome

# ═══════════════════════════════════════════════════════════════════════════════
# LOG GERAL (LOTE)
# ═══════════════════════════════════════════════════════════════════════════════
def gerar_log_lote(orig, tipo_orig, pasta, resumo, erros, arq_txt,
                   insc_fmt, tipo_insc, n_gravados=0, ignoradas=0,
                   enc_detectado="", crono: Cronometro = None, cb=None):
    if cb: cb("Gravando log...", 93)
    os.makedirs(pasta, exist_ok=True)
    nome = os.path.join(pasta, f"log_{ts_arq()}.txt")
    td = sum(v["total_debito"]  for v in resumo)
    tc = sum(v["total_credito"] for v in resumo)
    ok = len(resumo) - len(erros)
    conc = ("SUCESSO" if not erros
            else f"ATENÇÃO — {len(erros)} lote(s) desbalanceado(s)")
    SEP = "═"*90; sep2 = "─"*90
    L = [
        SEP, "  DOMÍNIO SISTEMAS  |  Thomson Reuters",
        "  LOG DE VALIDAÇÃO — LANÇAMENTOS CONTÁBEIS", SEP,
        f"  Data/Hora     : {ts_log()}",
        f"  Entrada       : {tipo_orig}",
        f"  Encoding leit.: {enc_detectado or 'N/A'}",
        f"  Arquivo       : {os.path.abspath(orig)}",
        f"  {tipo_insc:<6}         : {insc_fmt}",
        f"  Saída         : {arq_txt or 'Não gerado'}",
        SEP, "",
        "  RESUMO GERAL", sep2,
        f"  Lotes total   : {len(resumo):>10,}",
        f"  Lotes OK      : {ok:>10,}",
        f"  Lotes ERRO    : {len(erros):>10,}",
        f"  Reg. 6000+6100: {n_gravados:>10,}",
        f"  Ignoradas     : {ignoradas:>10,}",
        f"  Total Déb.    : R$ {td:>14.2f}",
        f"  Total Créd.   : R$ {tc:>14.2f}",
        f"  Conclusão     : {conc}", "",
    ]
    if crono and crono.etapas:
        total_seg = sum(e["segundos"] for e in crono.etapas)
        L += [sep2, "  RELATÓRIO DE TEMPO", sep2]
        L += crono.relatorio()
        L += ["  "+"─"*46,
              f"  {'  TOTAL':<38} {Cronometro.fmt(total_seg):>8}", ""]
    L += [sep2,
          f"  {'Lote':<8}{'Linhas':<16}{'Data':<13}{'Qtd':<6}"
          f"{'Débito':>15}{'Crédito':>15}{'Diferença':>13}  Status",
          "  "+"─"*88]
    for v in resumo:
        L.append(
            f"  {str(v['num_lote']):<8}{v['faixa_linhas']:<16}"
            f"{v['data']:<13}{str(v['qtd_linhas']):<6}"
            f"R$ {v['total_debito']:>12.2f}  R$ {v['total_credito']:>12.2f}"
            f"  R$ {v['diferenca']:>10.2f}   "
            f"{'✔ OK' if v['balanceado'] else '✖ ERRO'}")
    L += ["  "+"─"*88, f"  {'TOTAIS':<37}R$ {td:>12.2f}  R$ {tc:>12.2f}", ""]
    with open(nome, "w", encoding="utf-8-sig", buffering=BUFFER_IO) as f:
        f.write("\n".join(L))
    return nome

# ═══════════════════════════════════════════════════════════════════════════════
# INTERFACE — Thomson Reuters
# ═══════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Domínio Sistemas — Conversor Unificado  |  Thomson Reuters")
        self.geometry("1220x1020")
        self.minsize(1000, 800)
        self.configure(bg=TEMA["bg_escuro"])
        self.resizable(True, True)

        self.v_caminho  = tk.StringVar()
        self.v_pasta    = tk.StringVar(value="C:\\Temp")
        self.v_header   = tk.IntVar(value=4)
        self.v_auto     = tk.BooleanVar(value=True)
        self.v_sheet    = tk.StringVar()
        self.v_insc     = tk.StringVar()
        self.v_tipo_det = tk.StringVar(value="—")   # tipo detectado
        self._fmt           = False
        self._tempo_inicio  = None
        self._enc_det       = ""
        self._crono         = Cronometro()
        self._tipo_arquivo  = None   # 'ecd' | 'lote' | 'excel'

        self.v_insc.trace_add("write", self._digitar_insc)
        self._construir_ui()
        self._boas_vindas()

    # ── UI ───────────────────────────────────────────────────────────────────
    def _construir_ui(self):
        self._ui_header()
        self._ui_painel()
        self._ui_progresso()
        self._ui_console()
        self._ui_footer()

    def _ui_header(self):
        h = tk.Frame(self, bg=TEMA["bg_card"], height=72)
        h.pack(fill="x"); h.pack_propagate(False)
        tk.Frame(h, bg=TEMA["acento"], width=6).pack(side="left", fill="y")
        tk.Label(h, text="  DOMÍNIO SISTEMAS",
                 font=(TEMA["fonte"], 17, "bold"),
                 bg=TEMA["bg_card"], fg=TEMA["acento"]).pack(
                     side="left", padx=(12,0), pady=16)
        tk.Label(h, text="  Conversor Unificado — Lançamentos Contábeis & SPED ECD",
                 font=(TEMA["fonte"], 10),
                 bg=TEMA["bg_card"], fg=TEMA["texto_dim"]).pack(
                     side="left", pady=16)
        badge = tk.Frame(h, bg=TEMA["acento"], padx=10, pady=4)
        badge.pack(side="right", padx=16, pady=18)
        tk.Label(badge, text="Thomson Reuters",
                 font=(TEMA["fonte"], 9, "bold"),
                 bg=TEMA["acento"], fg="white").pack()

    def _ui_painel(self):
        P = tk.Frame(self, bg=TEMA["bg_medio"], pady=10)
        P.pack(fill="x")

        def lbl(pai, texto, w=22):
            return tk.Label(pai, text=texto, width=w, anchor="w",
                            font=(TEMA["fonte"], 9, "bold"),
                            bg=TEMA["bg_medio"], fg=TEMA["texto"])

        def inp(pai, var, w=None, fg=None):
            kw = dict(textvariable=var, font=(TEMA["fonte_mono"], 9),
                      bg=TEMA["bg_input"], fg=fg or TEMA["texto"],
                      insertbackground=TEMA["acento"], relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=TEMA["borda"],
                      highlightcolor=TEMA["acento"])
            if w: kw["width"] = w
            return tk.Entry(pai, **kw)

        # ── Linha 1: Arquivo ──────────────────────────────────────────────────
        r1 = tk.Frame(P, bg=TEMA["bg_medio"])
        r1.pack(fill="x", padx=18, pady=(6,3))
        lbl(r1, "Arquivo:").pack(side="left")
        inp(r1, self.v_caminho).pack(
            side="left", fill="x", expand=True, ipady=6, padx=(0,8))
        self.btn_sel = self._btn(r1, "📂  Selecionar", self._sel_arquivo)
        self.btn_sel.pack(side="left")

        # ── Badge de tipo detectado ────────────────────────────────────────────
        r1b = tk.Frame(P, bg=TEMA["bg_medio"])
        r1b.pack(fill="x", padx=18, pady=(0,3))
        lbl(r1b, "Tipo detectado:").pack(side="left")
        self.lbl_tipo_det = tk.Label(
            r1b, textvariable=self.v_tipo_det,
            font=(TEMA["fonte"], 10, "bold"),
            bg=TEMA["bg_medio"], fg=TEMA["cor_ecd"])
        self.lbl_tipo_det.pack(side="left")

        # ── Linha aba (Excel) ─────────────────────────────────────────────────
        self.r_sheet = tk.Frame(P, bg=TEMA["bg_medio"])
        self.r_sheet.pack(fill="x", padx=18, pady=3)
        lbl(self.r_sheet, "Aba (Sheet):").pack(side="left")
        self.combo = ttk.Combobox(
            self.r_sheet, textvariable=self.v_sheet,
            font=(TEMA["fonte"], 10), state="readonly", width=32)
        self._estilo_combo()
        self.combo.pack(side="left", ipady=4)
        self.combo.bind("<<ComboboxSelected>>", self._trocar_sheet)
        self.r_sheet.pack_forget()   # oculto até Excel ser detectado

        # ── Linha cabeçalho (Excel) ───────────────────────────────────────────
        self.r_head = tk.Frame(P, bg=TEMA["bg_medio"])
        self.r_head.pack(fill="x", padx=18, pady=3)
        lbl(self.r_head, "Linha de cabeçalho:").pack(side="left")
        tk.Checkbutton(
            self.r_head, text="Detectar automaticamente",
            variable=self.v_auto, command=self._toggle_head,
            font=(TEMA["fonte"], 10), bg=TEMA["bg_medio"], fg=TEMA["texto"],
            selectcolor=TEMA["bg_card"], activebackground=TEMA["bg_medio"],
            activeforeground=TEMA["acento"], cursor="hand2",
        ).pack(side="left")
        tk.Label(self.r_head, text="   ou manual:",
                 font=(TEMA["fonte"], 9),
                 bg=TEMA["bg_medio"], fg=TEMA["texto_dim"]).pack(side="left")
        self.spin = tk.Spinbox(
            self.r_head, from_=1, to=50, textvariable=self.v_header,
            width=5, font=(TEMA["fonte"], 10), bg=TEMA["bg_input"],
            fg=TEMA["texto"], buttonbackground=TEMA["bg_card"],
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=TEMA["borda"], state="disabled")
        self.spin.pack(side="left", padx=8, ipady=4)
        self.r_head.pack_forget()

        # ── CNPJ / CPF ────────────────────────────────────────────────────────
        r4 = tk.Frame(P, bg=TEMA["bg_medio"])
        r4.pack(fill="x", padx=18, pady=3)
        lbl(r4, "CNPJ / CPF:").pack(side="left")
        fi = tk.Frame(r4, bg=TEMA["bg_medio"]); fi.pack(side="left")
        self.e_insc = tk.Entry(
            fi, textvariable=self.v_insc,
            font=(TEMA["fonte_mono"], 11, "bold"),
            bg=TEMA["bg_input"], fg=TEMA["acento"],
            insertbackground=TEMA["acento"], relief="flat", bd=0,
            highlightthickness=2, highlightbackground=TEMA["borda"],
            highlightcolor=TEMA["acento"], width=22)
        self.e_insc.pack(side="left", ipady=7, padx=(0,10))
        self.lbl_insc = tk.Label(
            fi, text="", font=(TEMA["fonte"], 9, "bold"),
            bg=TEMA["bg_medio"], fg=TEMA["texto_dim"])
        self.lbl_insc.pack(side="left")
        tk.Label(r4, text="  ← ex: 00.000.000/0001-00",
                 font=(TEMA["fonte"], 9, "italic"),
                 bg=TEMA["bg_medio"], fg=TEMA["texto_dim"]).pack(side="left")

        # ── Pasta de saída ────────────────────────────────────────────────────
        r5 = tk.Frame(P, bg=TEMA["bg_medio"])
        r5.pack(fill="x", padx=18, pady=3)
        lbl(r5, "Pasta de saída:").pack(side="left")
        self.lbl_pasta = tk.Label(
            r5, text="C:\\Temp",
            font=(TEMA["fonte"], 9, "italic"),
            bg=TEMA["bg_medio"], fg=TEMA["acento3"])
        self.lbl_pasta.pack(side="left")
        inp(r5, self.v_pasta, w=36, fg=TEMA["acento3"]).pack(
            side="left", ipady=6, padx=(8,8))
        self._btn(r5, "📁  Alterar", self._sel_pasta,
                  cor=TEMA["bg_card"]).pack(side="left")

        # ── Botões ────────────────────────────────────────────────────────────
        r6 = tk.Frame(P, bg=TEMA["bg_medio"])
        r6.pack(fill="x", padx=18, pady=(8,4))
        self.btn_conv = self._btn(
            r6, "  ▶  CONVERTER", self._iniciar,
            fonte_size=12, pady=10, padx=32)
        self.btn_conv.pack(side="left")
        self._btn(r6, "🗑  Limpar", self._limpar_console,
                  cor=TEMA["bg_card"], pady=10, padx=14).pack(
                      side="left", padx=(10,0))
        self.lbl_prev = tk.Label(
            r6, text="", font=(TEMA["fonte_mono"], 9),
            bg=TEMA["bg_medio"], fg=TEMA["cor_0000"])
        self.lbl_prev.pack(side="left", padx=(18,0))
        self.lbl_crono = tk.Label(
            r6, text="", font=(TEMA["fonte_mono"], 10, "bold"),
            bg=TEMA["bg_medio"], fg=TEMA["cor_tempo"])
        self.lbl_crono.pack(side="right", padx=(0,6))

    def _ui_progresso(self):
        outer = tk.Frame(self, bg=TEMA["bg_escuro"])
        outer.pack(fill="x", padx=14, pady=(3,0))
        card = tk.Frame(outer, bg=TEMA["bg_medio"],
                        highlightthickness=1,
                        highlightbackground=TEMA["borda"])
        card.pack(fill="x")
        rl = tk.Frame(card, bg=TEMA["bg_medio"])
        rl.pack(fill="x", padx=10, pady=(5,2))
        tk.Label(rl, text="⚙  Processamento",
                 font=(TEMA["fonte"], 9, "bold"),
                 bg=TEMA["bg_medio"], fg=TEMA["acento"]).pack(side="left")
        self.lbl_pct = tk.Label(
            rl, text="0%", font=(TEMA["fonte"], 9, "bold"),
            bg=TEMA["bg_medio"], fg=TEMA["acento"], width=5, anchor="e")
        self.lbl_pct.pack(side="right")
        self.lbl_eta = tk.Label(
            rl, text="Aguardando...", font=(TEMA["fonte"], 9),
            bg=TEMA["bg_medio"], fg=TEMA["texto_dim"], anchor="e")
        self.lbl_eta.pack(side="right", padx=(0,10))
        self.cv = tk.Canvas(card, height=18, bg=TEMA["bg_input"],
                            highlightthickness=0)
        self.cv.pack(fill="x", padx=10, pady=(0,7))
        self._pr = self.cv.create_rectangle(0,0,0,18,
                                             fill=TEMA["acento"],outline="")
        self._pt = self.cv.create_text(0,9,text="",fill=TEMA["bg_escuro"],
                                        font=(TEMA["fonte"],8,"bold"),
                                        anchor="center")
        self.cv.bind("<Configure>", lambda e: self._barra(self._pv))
        self._pv = 0

    def _barra(self, pct, eta=None):
        self._pv = max(0, min(100, int(pct)))
        w  = self.cv.winfo_width() or 400; fw = int(w * self._pv / 100)
        cor = (TEMA["acento3"]  if self._pv==100 else
               TEMA["cor_erro"] if self._pv==0   else
               TEMA["amarelo"]  if self._pv>=80  else TEMA["acento"])
        self.cv.coords(self._pr, 0,0,fw,18)
        self.cv.itemconfig(self._pr, fill=cor)
        cx = w//2
        self.cv.coords(self._pt, cx, 9)
        self.cv.itemconfig(self._pt, text=f"{self._pv}%",
                           fill=TEMA["bg_escuro"] if fw>cx else TEMA["acento"])
        if eta: self.lbl_eta.configure(text=eta, fg=TEMA["texto"])
        self.lbl_pct.configure(text=f"{self._pv}%",
                                fg=cor if self._pv>0 else TEMA["texto_dim"])

    def _barra_com_tempo(self, pct, eta=None):
        if pct>0 and self._tempo_inicio is None:
            self._tempo_inicio = time.perf_counter()
        ts=""
        if self._tempo_inicio and 0<pct<100:
            dec = time.perf_counter()-self._tempo_inicio
            if pct>=5:
                rest = max(0, dec*100/pct-dec)
                ts = (f"  ⏱ ~{int(rest)}s" if rest<60
                      else f"  ⏱ ~{int(rest/60)}min")
        elif pct==100 and self._tempo_inicio:
            tot=time.perf_counter()-self._tempo_inicio
            ts=(f"  ✔ {tot:.1f}s" if tot<60
                else f"  ✔ {int(tot//60)}m{int(tot%60):.0f}s")
            self._tempo_inicio=None
        self._barra(pct, (eta or "")+ts)

    def prog(self, eta, pct):
        self.after(0, lambda e=eta, p=pct: self._barra_com_tempo(p, e))

    def _ui_console(self):
        f = tk.Frame(self, bg=TEMA["bg_escuro"])
        f.pack(fill="both", expand=True, padx=14, pady=(5,0))
        ch = tk.Frame(f, bg=TEMA["bg_card"], height=26)
        ch.pack(fill="x"); ch.pack_propagate(False)
        tk.Frame(ch, bg=TEMA["acento"], width=4).pack(side="left", fill="y")
        tk.Label(ch, text="  ▸  Console de Execução",
                 font=(TEMA["fonte"], 9, "bold"),
                 bg=TEMA["bg_card"], fg=TEMA["acento"]).pack(
                     side="left", padx=6)
        for cor, txt in [
            (TEMA["cor_0000"],"0000"),(TEMA["cor_6000"],"6000"),
            (TEMA["cor_6100"],"6100"),(TEMA["cor_ok"],"OK"),
            (TEMA["cor_erro"],"ERRO"),(TEMA["cor_susp"],"SUSPEITA"),
            (TEMA["cor_tempo"],"TEMPO"),(TEMA["cor_ecd"],"ECD"),
        ]:
            tk.Label(ch, text=f"  ■ {txt}",
                     font=(TEMA["fonte"],8),
                     bg=TEMA["bg_card"], fg=cor).pack(side="right", padx=2)
        self.con = scrolledtext.ScrolledText(
            f, font=(TEMA["fonte_mono"],9), bg="#060B14", fg=TEMA["texto"],
            insertbackground=TEMA["acento"], relief="flat", bd=0,
            highlightthickness=1, highlightbackground=TEMA["borda"],
            state="disabled", wrap="none")
        self.con.pack(fill="both", expand=True, pady=(2,0))
        for tag, fg, bold in [
            ("titulo", TEMA["acento2"],   True),
            ("ok",     TEMA["cor_ok"],    False),
            ("erro",   TEMA["cor_erro"],  False),
            ("aviso",  TEMA["amarelo"],   False),
            ("info",   TEMA["texto_dim"], False),
            ("dest",   TEMA["texto"],     True),
            ("r0",     TEMA["cor_0000"],  True),
            ("r6000",  TEMA["cor_6000"],  True),
            ("r6100",  TEMA["cor_6100"],  False),
            ("susp",   TEMA["cor_susp"],  True),
            ("diag",   "#FF6B6B",         False),
            ("ti",     TEMA["acento2"],   False),
            ("enc",    TEMA["cor_enc"],   False),
            ("tempo",  TEMA["cor_tempo"], True),
            ("tempo2", TEMA["cor_tempo"], False),
            ("ecd",    TEMA["cor_ecd"],   True),
            ("ecd2",   TEMA["cor_ecd"],   False),
        ]:
            kw = {"foreground": fg}
            if bold: kw["font"] = (TEMA["fonte_mono"], 9, "bold")
            self.con.tag_config(tag, **kw)

    def _ui_footer(self):
        ft = tk.Frame(self, bg=TEMA["bg_card"], height=26)
        ft.pack(fill="x", side="bottom"); ft.pack_propagate(False)
        tk.Frame(ft, bg=TEMA["acento"], width=4).pack(side="left", fill="y")
        self.lbl_st = tk.Label(
            ft, text="  Aguardando...", font=(TEMA["fonte"],9),
            bg=TEMA["bg_card"], fg=TEMA["texto_dim"], anchor="w")
        self.lbl_st.pack(side="left", fill="x", expand=True)
        tk.Label(ft,
                 text="Lançamentos Contábeis & SPED ECD  |  Thomson Reuters  ",
                 font=(TEMA["fonte"],9,"italic"),
                 bg=TEMA["bg_card"], fg=TEMA["texto_dim"]).pack(side="right")

    def _btn(self, pai, texto, cmd, cor=None,
             fonte_size=10, pady=6, padx=16):
        b = tk.Button(pai, text=texto, command=cmd,
                      font=(TEMA["fonte"],fonte_size,"bold"),
                      bg=cor or TEMA["acento"], fg="white",
                      activebackground=TEMA["btn_hover"],
                      activeforeground="white",
                      relief="flat", bd=0, cursor="hand2",
                      padx=padx, pady=pady)
        if not cor:
            b.bind("<Enter>", lambda e: b.configure(bg=TEMA["btn_hover"]))
            b.bind("<Leave>", lambda e: b.configure(bg=TEMA["acento"]))
        return b

    def _estilo_combo(self):
        s = ttk.Style(); s.theme_use("clam")
        s.configure("TCombobox",
                    fieldbackground=TEMA["bg_input"],
                    background=TEMA["bg_card"],
                    foreground=TEMA["texto"],
                    selectbackground=TEMA["bg_card"],
                    selectforeground=TEMA["acento"],
                    bordercolor=TEMA["borda"],
                    arrowcolor=TEMA["acento"])

    def log(self, msg, tag=""):
        self.con.configure(state="normal")
        self.con.insert("end", msg+"\n", tag if tag else ())
        self.con.see("end")
        self.con.configure(state="disabled")

    def _limpar_console(self):
        self.con.configure(state="normal")
        self.con.delete("1.0","end")
        self.con.configure(state="disabled")

    def _st(self, msg, cor=None):
        self.lbl_st.configure(text=f"  {msg}", fg=cor or TEMA["texto_dim"])

    # ── Boas-vindas ───────────────────────────────────────────────────────────
    def _boas_vindas(self):
        self.log("╔══════════════════════════════════════════════════════════════╗","titulo")
        self.log("║   DOMÍNIO SISTEMAS  |  Thomson Reuters                       ║","titulo")
        self.log("║   Conversor Unificado — Lançamentos Contábeis & SPED ECD     ║","titulo")
        self.log("╚══════════════════════════════════════════════════════════════╝\n","titulo")
        self.log("Formatos suportados:","dest")
        self.log("  📊  Excel (.xlsx/.xls)  — Lançamentos em Lote","ti")
        self.log("  📄  TXT separado por ;  — Lançamentos em Lote","ti")
        self.log("  📋  SPED ECD (.txt)     — Escrituração Contábil Digital","ecd")
        self.log("","")
        self.log("Identificação automática do tipo de arquivo no upload.","aviso")
        self.log("","")
        self.log("Saída gerada (lógica ECD para todos os formatos):","dest")
        self.log("  |0000|CNPJ|","r0")
        self.log("  |6000|TIPO||||","r6000")
        self.log("  |6100|DATA|DEB|CRED|VALOR|HIST|DESC||FILIAL||","r6100")
        self.log("","")
        self.log("Selecione o arquivo e informe o CNPJ/CPF.","dest")

    # ── Eventos ───────────────────────────────────────────────────────────────
    def _digitar_insc(self, *_):
        if self._fmt: return
        self._fmt = True
        raw = self.v_insc.get(); n = so_nums(raw)
        if len(n) <= 11:
            if len(n)>=10: fmt=f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"
            elif len(n)>=7: fmt=f"{n[:3]}.{n[3:6]}.{n[6:]}"
            elif len(n)>=4: fmt=f"{n[:3]}.{n[3:]}"
            else: fmt=n
        else:
            if len(n)>=13: fmt=f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:14]}"
            elif len(n)>=9: fmt=f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:]}"
            elif len(n)>=6: fmt=f"{n[:2]}.{n[2:5]}.{n[5:]}"
            elif len(n)>=3: fmt=f"{n[:2]}.{n[2:]}"
            else: fmt=n
        self.v_insc.set(fmt); self.e_insc.icursor("end")
        ok, tp, nl = validar_inscricao(fmt)
        if ok:
            self.lbl_insc.configure(text=f"✔ {tp} válido", fg=TEMA["acento3"])
            self.e_insc.configure(highlightbackground=TEMA["acento3"],
                                   highlightcolor=TEMA["acento3"])
            self.lbl_prev.configure(text=f"  Preview → |0000|{nl}|")
        elif len(nl) in (11,14):
            self.lbl_insc.configure(text="✖ Inválido", fg=TEMA["cor_erro"])
            self.e_insc.configure(highlightbackground=TEMA["cor_erro"],
                                   highlightcolor=TEMA["cor_erro"])
            self.lbl_prev.configure(text="")
        else:
            self.lbl_insc.configure(text="", fg=TEMA["texto_dim"])
            self.e_insc.configure(highlightbackground=TEMA["borda"],
                                   highlightcolor=TEMA["acento"])
            self.lbl_prev.configure(text="")
        self._fmt = False

    def _sel_arquivo(self):
        c = filedialog.askopenfilename(
            title="Selecionar arquivo",
            filetypes=[
                ("Todos suportados","*.xlsx *.xls *.xlsm *.txt *.csv"),
                ("Excel","*.xlsx *.xls *.xlsm"),
                ("TXT / SPED ECD","*.txt *.csv"),
                ("Todos","*.*"),
            ])
        if c: self._carregar_arquivo(c)

    def _carregar_arquivo(self, caminho: str):
        self.v_caminho.set(caminho)
        self._limpar_console()
        self.after(0, lambda: self._barra(0,"Identificando..."))

        tipo = identificar_tipo_arquivo(caminho)
        self._tipo_arquivo = tipo

        # Atualiza badge
        labels = {
            "ecd":   ("📋  SPED ECD",                    TEMA["cor_ecd"]),
            "excel": ("📊  Excel — Lançamentos em Lote",  TEMA["acento3"]),
            "lote":  ("📄  TXT — Lançamentos em Lote",    TEMA["amarelo"]),
        }
        txt, cor = labels.get(tipo, ("?","white"))
        self.v_tipo_det.set(txt)
        self.lbl_tipo_det.configure(fg=cor)

        # Mostra/oculta controles de Excel
        if tipo == "excel":
            self.r_sheet.pack(fill="x", padx=18, pady=3)
            self.r_head.pack(fill="x",  padx=18, pady=3)
            try:
                xl = pd.ExcelFile(caminho)
                sheets = xl.sheet_names
                self.combo["values"] = sheets
                self.v_sheet.set("Plan1" if "Plan1" in sheets else sheets[0])
                self._trocar_sheet()
            except Exception as ex:
                messagebox.showerror("Erro ao abrir Excel", str(ex))
        else:
            self.r_sheet.pack_forget()
            self.r_head.pack_forget()
            self._preview_txt(caminho, tipo)

    def _preview_txt(self, caminho: str, tipo: str):
        self.log("╔══════════════════════════════════════════════════════════════╗","titulo")
        self.log("║   DOMÍNIO SISTEMAS  |  Conversor Unificado                   ║","titulo")
        self.log("╚══════════════════════════════════════════════════════════════╝\n","titulo")
        self.log(f"📄 {os.path.basename(caminho)}","info")
        try:
            enc = _detectar_encoding(caminho); self._enc_det = enc
            self.log(f"  Encoding detectado: {enc}","enc")
            with open(caminho,"r",encoding=enc,errors="replace") as f:
                linhas_prev = [f.readline() for _ in range(6)]
            if tipo == "ecd":
                self.log("\n🔍 Tipo identificado: SPED ECD","ecd")
                self.log("Prévia dos primeiros registros:","dest")
                for ln in linhas_prev:
                    ln=ln.strip()
                    if not ln: continue
                    reg = ln.split("|")[1] if "|" in ln else ""
                    tag = ("r0" if reg=="0000" else "ecd2" if reg.startswith("I")
                           else "info")
                    self.log(f"  {ln[:100]}",tag)
            else:
                self.log("\n🔍 Tipo identificado: TXT Lançamentos em Lote","aviso")
                cab=["Data","Déb","Créd","Valor","CódH",
                     "Desc","IniciaLote","Filial","CCDéb","CCCréd"]
                self.log("Prévia:","dest")
                for i,ln in enumerate(linhas_prev):
                    ln=ln.strip()
                    if not ln: continue
                    pts=ln.split(";")
                    self.log(f"\n  Linha {i+1}:","info")
                    for j,p in enumerate(pts[:10]):
                        col=cab[j] if j<len(cab) else f"col{j}"
                        v=p.strip() if p.strip() else "(vazio)"
                        self.log(f"    [{j}] {col:<14} → {v}","r6100" if v!="(vazio)" else "info")
            self.log("\nInforme o CNPJ/CPF e clique em ▶ CONVERTER.","dest")
        except Exception as ex:
            self.log(f"⚠ {ex}","aviso")

    def _trocar_sheet(self, *_):
        c=self.v_caminho.get(); s=self.v_sheet.get()
        if not c or not s: return
        try:
            lh, pasta = detectar_cabecalho(c, s)
            self.v_header.set(lh+1)
            if pasta:
                self.v_pasta.set(pasta)
                self.lbl_pasta.configure(text="(lida do Excel — G2)",
                                          fg=TEMA["acento3"])
            self._limpar_console()
            self.log("╔══════════════════════════════════════════════════════════════╗","titulo")
            self.log("║   DOMÍNIO SISTEMAS  |  Conversor Unificado                   ║","titulo")
            self.log("╚══════════════════════════════════════════════════════════════╝\n","titulo")
            self.log(f"📊 {os.path.basename(c)}","info")
            self.log(f"📋 Aba: {s}","info")
            self.log(f"📌 Cabeçalho detectado: linha {lh+1}","ok")
            if pasta: self.log(f"📁 Pasta de saída: {pasta}","ok")
            self.log("\nInforme o CNPJ/CPF e clique em ▶ CONVERTER.","dest")
        except Exception as ex:
            self.log(f"⚠ {ex}","aviso")

    def _sel_pasta(self):
        p=filedialog.askdirectory(title="Pasta de saída")
        if p:
            self.v_pasta.set(p)
            self.lbl_pasta.configure(text="(definida manualmente)",
                                      fg=TEMA["amarelo"])

    def _toggle_head(self):
        self.spin.configure(
            state="disabled" if self.v_auto.get() else "normal")

    def _iniciar(self):
        if not self.v_caminho.get():
            messagebox.showwarning("Atenção","Selecione um arquivo."); return
        if self._tipo_arquivo == "excel" and not self.v_sheet.get():
            messagebox.showwarning("Atenção","Selecione a aba (sheet)."); return
        ok,_,_ = validar_inscricao(self.v_insc.get())
        if not ok:
            messagebox.showwarning("CNPJ/CPF inválido",
                "Informe um CNPJ (14 dígitos) ou CPF (11 dígitos) válido.")
            self.e_insc.focus_set(); return
        self.btn_conv.configure(state="disabled")
        self.btn_sel.configure(state="disabled")
        self.lbl_crono.configure(text="⏱ Processando...")
        self.after(0, lambda: self._barra(0,"Iniciando..."))
        self._st("Convertendo...", TEMA["amarelo"])
        self._tempo_inicio = None
        Thread(target=self._converter, daemon=True).start()

    # ── Thread principal de conversão ─────────────────────────────────────────
    def _converter(self):
        crono = self._crono; crono.iniciar()
        try:
            cam   = self.v_caminho.get()
            pasta = self.v_pasta.get() or "C:\\Temp"
            _, ti, ni = validar_inscricao(self.v_insc.get())
            inf   = fmt_cnpj(ni) if ti=="CNPJ" else fmt_cpf(ni)
            tipo  = self._tipo_arquivo

            self.after(0, self._limpar_console)
            self.after(0, lambda: self.log(
                "╔══════════════════════════════════════════════════════════════╗","titulo"))
            self.after(0, lambda: self.log(
                "║   DOMÍNIO SISTEMAS  |  Thomson Reuters                       ║","titulo"))
            self.after(0, lambda: self.log(
                "╚══════════════════════════════════════════════════════════════╝\n","titulo"))

            if tipo == "ecd":
                self._converter_ecd(cam, pasta, ni, ti, inf, crono)
            else:
                self._converter_lote(cam, pasta, ni, ti, inf, crono, tipo)

        except Exception as ex:
            tb = traceback.format_exc()
            self._crono.encerrar()
            self.after(0, lambda e=str(ex): self.log(f"\n⛔ ERRO: {e}","erro"))
            self.after(0, lambda t=tb: self.log(t,"info"))
            self.after(0, lambda e=str(ex): self._st(f"⛔ {e}",TEMA["cor_erro"]))
            self.after(0, lambda: self._barra(0,"⛔ Erro"))
            self.after(0, lambda e=str(ex): messagebox.showerror("Erro",e))
            self.after(0, lambda: self.lbl_crono.configure(
                text="⛔ Erro", fg=TEMA["cor_erro"]))
        finally:
            self.after(0, lambda: self.btn_conv.configure(state="normal"))
            self.after(0, lambda: self.btn_sel.configure(state="normal"))

    # ── Fluxo SPED ECD ────────────────────────────────────────────────────────
    def _converter_ecd(self, cam, pasta, ni, ti, inf, crono):
        self.after(0, lambda: self.log(
            f"📋 SPED ECD: {os.path.basename(cam)}","ecd"))
        self.after(0, lambda: self.log(f"🏢 {ti}: {inf}","info"))
        self.after(0, lambda p=pasta: self.log(f"📁 Pasta: {p}\n","info"))

        crono.etapa("Leitura SPED ECD")
        with open(cam,"rb") as f: conteudo = f.read()

        logs_ecd = []
        def _log(m): logs_ecd.append(m); self.after(0, lambda mm=m: self.log(f"  {mm}","ecd2"))

        ecd, registros_erro = _parse_ecd(conteudo, _log, self.prog)
        if ecd is None:
            self.prog("Falha na leitura.",0)
            self.after(0, lambda: self._st("⛔ Falha na leitura do ECD.",TEMA["cor_erro"]))
            return

        # Usa o CNPJ do próprio arquivo ECD se o usuário não informou
        cnpj_final = ni if ni else re.sub(r"\D","",ecd.cnpj)

        crono.etapa("Geração dos registros ECD")
        linhas, resumo_ecd = _gerar_ecd(ecd, _log, self.prog)

        crono.etapa("Gravação do arquivo")
        self.prog("Gravando arquivo...", 88)
        os.makedirs(pasta, exist_ok=True)
        arq_txt = os.path.join(pasta,
                               f"ECD_{cnpj_final}_dominio_{ts_arq()}.txt")
        n_grav  = gravar_linhas_ecd(arq_txt, linhas, self.prog)

        self.after(0, lambda ct=arq_txt: self.log(f"\n✅ Arquivo: {ct}","ok"))
        self.after(0, lambda n=n_grav: self.log(
            f"   {n:,} linhas gravadas (0000 + 6000 + 6100)","ok"))

        # Relatório de erros ECD
        arq_erros = None
        if registros_erro:
            crono.etapa("Relatório de erros ECD")
            arq_erros = gerar_txt_erros_ecd(registros_erro, ecd.cnpj, pasta)
            _ae = arq_erros
            self.after(0, lambda ae=_ae: self.log(
                f"⚠ Relatório de erros: {ae}","aviso"))

        crono.etapa("Finalização")
        total_seg = crono.encerrar()
        total_fmt = Cronometro.fmt(total_seg)
        self.prog("Concluído!", 100)
        self.after(0, lambda tf=total_fmt: self.lbl_crono.configure(
            text=f"⏱ Total: {tf}", fg=TEMA["cor_tempo"]))
        self.after(0, lambda tf=total_fmt: self._exibir_relatorio_tempo(crono,tf))

        msg = (f"SPED ECD convertido!\n\n"
               f"  • CNPJ: {ecd.cnpj}\n"
               f"  • {n_grav:,} linhas gravadas\n"
               f"  • ⏱ {total_fmt}\n\n"
               f"Arquivo: {arq_txt}")
        if registros_erro:
            msg += f"\n\n⚠ {len(registros_erro)} linha(s) com aviso — veja: {arq_erros}"
        self.after(0, lambda m=msg, n=n_grav, tf=total_fmt:
            (self._st(f"✅ ECD: {n:,} registros em {tf}", TEMA["acento3"]),
             messagebox.showinfo("SPED ECD — Sucesso!", m)))

    # ── Fluxo Lançamentos em Lote (TXT / Excel) ────────────────────────────────
    def _converter_lote(self, cam, pasta, ni, ti, inf, crono, tipo):
        ignoradas=0; enc_usado=""; n_gravados=0

        crono.etapa("Leitura do arquivo")
        if tipo == "excel":
            sh     = self.v_sheet.get()
            lh, px = detectar_cabecalho(cam, sh)
            if not self.v_auto.get(): lh = self.v_header.get()-1
            elif px: pasta = px
            df, _  = ler_excel_lote(cam, sh, lh, cb=self.prog)
            to     = f"Excel — Aba: {sh}"; enc_usado="N/A (Excel)"
            self.after(0, lambda: self.log(f"📊 {os.path.basename(cam)}","info"))
            self.after(0, lambda s=sh: self.log(f"📋 Aba: {s}","info"))
        else:
            df, ignoradas, enc_usado = ler_txt_lote(cam, cb=self.prog)
            to = "TXT (separado por ;)"
            self.after(0, lambda: self.log(f"📄 {os.path.basename(cam)}","info"))
            self.after(0, lambda e=enc_usado: self.log(f"  Encoding: {e}","enc"))
            if ignoradas>0:
                self.after(0, lambda ig=ignoradas: self.log(
                    f"⚠ {ig:,} linha(s) ignorada(s)","aviso"))

        self.after(0, lambda t=ti,i=inf: self.log(f"🏢 {t}: {i}","info"))
        self.after(0, lambda p=pasta: self.log(f"📁 Pasta: {p}\n","info"))
        _q=len(df)
        self.after(0, lambda q=_q: self.log(f"✔ {q:,} linhas carregadas.","ok"))

        crono.etapa("Montagem de lotes")
        df  = montar_lotes(df, cb=self.prog)
        _nl = int(df["_num_lote"].max()) if len(df)>0 else 0
        _mod=("Inicia Lote"
              if (df["Inicia Lote"].fillna("").astype(str).str.strip()!="").any()
              else "Data + Descrição")
        self.after(0, lambda nl=_nl,mo=_mod: self.log(
            f"✔ {nl:,} lote(s)  [agrupamento: {mo}].\n","ok"))

        crono.etapa("Processamento / validação")
        gerador, erros, resumo = processar_lote(df, cb=self.prog)
        del df; gc.collect()
        self.after(0, lambda: self._tabela_validacao(resumo, erros, ni, ti, inf))

        crono.etapa("Gravação do arquivo")
        arq_txt=None
        if any(v["balanceado"] for v in resumo):
            self.prog("Gravando em streaming...", 89)
            os.makedirs(pasta, exist_ok=True)
            arq_txt    = os.path.join(pasta, f"lanctos_{ts_arq()}.txt")
            n_gravados = gravar_arquivo(arq_txt, ni, gerador)
            _ct=arq_txt
            self.after(0, lambda ct=_ct: self.log(f"\n✅ Arquivo: {ct}","ok"))
            self.after(0, lambda n=n_gravados: self.log(
                f"   1×|0000|  +  {n:,} registros |6000|/|6100|","ok"))

        crono.etapa("Geração do log")
        log_path = gerar_log_lote(
            cam, to, pasta, resumo, erros, arq_txt,
            inf, ti, n_gravados, ignoradas, enc_usado, crono,
            cb=self.prog)
        _cl=log_path
        self.after(0, lambda cl=_cl: self.log(f"📋 Log: {cl}","ok"))

        total_seg=crono.encerrar(); total_fmt=Cronometro.fmt(total_seg)
        self.prog("Concluído!",100)
        self.after(0, lambda tf=total_fmt: self.lbl_crono.configure(
            text=f"⏱ Total: {tf}", fg=TEMA["cor_tempo"]))
        self.after(0, lambda tf=total_fmt: self._exibir_relatorio_tempo(crono,tf))

        if erros:
            _ne=len(erros)
            self.after(0, lambda ne=_ne: self._st(
                f"⛔ {ne} lote(s) com erro.",TEMA["cor_erro"]))
            self.after(0, lambda ne=_ne,cl=_cl: messagebox.showwarning(
                "Conversão com erros",
                f"{ne} lote(s) desbalanceado(s) omitidos.\nLog: {cl}"))
        else:
            self.after(0, lambda n=n_gravados,tf=total_fmt: self._st(
                f"✅ {n:,} registros gerados em {tf}",TEMA["acento3"]))
            self.after(0, lambda n=n_gravados,tf=total_fmt,
                              ct=arq_txt,cl=_cl,t2=ti,i2=inf:
                messagebox.showinfo("Sucesso!",
                    f"Conversão concluída!\n\n"
                    f"  • 1 × |0000|  ({t2}: {i2})\n"
                    f"  • {n:,} × |6000| + |6100|\n"
                    f"  • ⏱ {tf}\n\n"
                    f"Arquivo: {ct}\nLog: {cl}"))

    # ── Relatório de tempo ────────────────────────────────────────────────────
    def _exibir_relatorio_tempo(self, crono: Cronometro, total_fmt: str):
        S="─"*52
        self.log(f"\n{'═'*52}","tempo")
        self.log("  ⏱  RELATÓRIO DE TEMPO","tempo")
        self.log(f"{'═'*52}","tempo")
        for e in crono.etapas:
            self.log(f"  {'  '+e['nome']:<34} {Cronometro.fmt(e['segundos']):>8}","tempo2")
        self.log(S,"tempo")
        self.log(f"  {'  TOTAL':<34} {total_fmt:>8}","tempo")
        self.log(f"{'═'*52}\n","tempo")

    # ── Tabela de validação (lote) ────────────────────────────────────────────
    def _tabela_validacao(self, resumo, erros, ni, ti, inf):
        S="─"*92; S2="═"*92
        self.log(S2,"titulo")
        self.log("  REGISTRO 0000","titulo"); self.log(S2,"titulo")
        self.log(f"  {ti}: {inf}  →  {fmt_reg_0000(ni)}","r0"); self.log("")
        self.log(S2,"titulo")
        self.log("  VALIDAÇÃO DOS LOTES","titulo"); self.log(S2,"titulo")
        self.log(
            f"  {'Lote':<8}{'Linhas':<16}{'Data':<13}{'Qtd':<6}"
            f"{'Débito':>15}{'Crédito':>15}{'Diferença':>13}  Status","dest")
        self.log(S,"info")
        for v in resumo:
            ln=(f"  {str(v['num_lote']):<8}{v['faixa_linhas']:<16}"
                f"{v['data']:<13}{str(v['qtd_linhas']):<6}"
                f"R$ {v['total_debito']:>12.2f}  "
                f"R$ {v['total_credito']:>12.2f}  "
                f"R$ {v['diferenca']:>10.2f}   ")
            self.log(ln+("✔ OK" if v["balanceado"] else "✖ ERRO"),
                     "ok" if v["balanceado"] else "erro")
        self.log(S,"info")
        td=sum(v["total_debito"]  for v in resumo)
        tc=sum(v["total_credito"] for v in resumo)
        self.log(f"  {'TOTAIS':<39}R$ {td:>12.2f}  R$ {tc:>12.2f}","dest")
        self.log(S2,"titulo")
        lok=len(resumo)-len(erros)
        self.log(f"\n  ✔ Lotes OK  : {lok:,}/{len(resumo):,}","ok")
        self.log(f"  ✖ Com erro  : {len(erros):,}/{len(resumo):,}",
                 "erro" if erros else "ok")
        if erros:
            self.log(f"\n{'═'*92}","titulo")
            self.log("  ⚠  DIAGNÓSTICO DOS LOTES COM ERRO","titulo")
            self.log(f"{'═'*92}","titulo")
            for idx,e in enumerate(erros,1):
                diag=e.get("diagnostico",{}); suspeitas=diag.get("suspeitas",[])
                self.log(f"\n  ┌─ ERRO #{idx} ── Lote {e['num_lote']} "
                         f"│ Linhas {e['faixa_linhas']} │ {e['data']}","erro")
                self.log(f"  │  {e['descricao'][:74]}","aviso")
                self.log(f"  │  Total Déb : R$ {e['total_debito']:>12.2f}","info")
                self.log(f"  │  Total Créd: R$ {e['total_credito']:>12.2f}","info")
                self.log(f"  │  ► Diferença: R$ {e['diferenca']:>12.2f}  ◄","erro")
                self.log(f"  │  Sugestão: {diag.get('sugestao','')}","aviso")
                if suspeitas:
                    self.log("  │  ⚡ LINHA(S) SUSPEITA(S):","susp")
                    for s in suspeitas:
                        tp_s="DÉBITO" if s["tipo"]=="D" else "CRÉDITO"
                        cta=s["conta_debito"] or s["conta_credito"]
                        self.log(f"  │    ► Ln {s['linha_origem']:<5} {tp_s:<8} "
                                 f"Conta {cta:<10} R$ {s['valor']:>10.2f}","susp")
                        self.log(f"  │      {s['motivo']}","susp")
                self.log(f"  └{'─'*91}","info")
            self.log("\n  ⚠ Lotes com erro NÃO incluídos no arquivo de saída!","aviso")


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    App().mainloop()
