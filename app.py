# -*- coding: utf-8 -*-
"""
Domínio Sistemas — Conversor Unificado (Streamlit) V3.7.0

Novidades V3.7.0 (sobre V3.6.2):
  ┌─ DETECÇÃO DE LEIAUTE ─────────────────────────────────────────────────────┐
  │ • Validação precisa do SPED ECD via campo LECD no registro 0000           │
  │ • Badge de confiança: Alta / Média / Baixa                                │
  │ • Painel de opções de conversão por leiaute detectado                     │
  │ • Bloqueio com mensagem clara para formatos desconhecidos                 │
  └───────────────────────────────────────────────────────────────────────────┘
  ┌─ PARTICIONAMENTO ─────────────────────────────────────────────────────────┐
  │ • Por Mês   — gera um arquivo .txt por mês (data do |6100|)               │
  │ • Por Linhas — gera N arquivos com máx. X linhas de |6100|                │
  │ • Lançamentos SEMPRE fechados — nunca cortados no meio de |6000|→|6100|   │
  │ • Download individual por partição + ZIP com todas                        │
  └───────────────────────────────────────────────────────────────────────────┘
  ┌─ MÓDULO SALDO INICIAL ────────────────────────────────────────────────────┐
  │ • Modo 1 — Apenas Patrimonial (I155)                                      │
  │ • Modo 2 — Aberto com Resultado (I155 + I355)                             │
  │ • Dedução automática do resultado líquido da conta PL                     │
  └───────────────────────────────────────────────────────────────────────────┘
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════
import os
import re
import gc
import io
import time
import zipfile
import traceback
import unicodedata
from collections import OrderedDict
from datetime import datetime

import numpy  as np
import pandas as pd
import streamlit as st

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES GLOBAIS
# ═══════════════════════════════════════════════════════════════════════════════
VERSAO        = "V3.7.0"
CHUNK_SIZE    = 100_000
WRITE_CHUNK   = 5_000
TOL_VALOR     = 0.005
MAX_UPLOAD_MB = 200

COLS_PADRAO = [
    "Data", "Cód. Conta Debito", "Cód. Conta Credito", "Valor",
    "Cód. Histórico", "Complemento Histórico", "Inicia Lote",
    "Código Matriz/Filial", "Centro de Custo Débito", "Centro de Custo Crédito",
]

# Registros exclusivos do SPED ECD — usados na validação precisa
REGISTROS_ECD = frozenset({
    "0000", "0001",
    "I010", "I050", "I052", "I075", "I100",
    "I150", "I155", "I200", "I250", "I299",
    "I350", "I355", "I990",
    "J050", "J100", "J150", "J800", "J930",
    "9001", "9900", "9999",
})

# ═══════════════════════════════════════════════════════════════════════════════
# TEMA / CSS
# ═══════════════════════════════════════════════════════════════════════════════
def apply_theme() -> None:
    st.markdown("""
    <style>
    html, body, [class*='css'] {
        font-family: 'Segoe UI', Arial, sans-serif;
        color: #E8ECF0;
    }
    .stApp { background-color: #0A0E1A; }
    h1, h2, h3 { color: #FF6B00; font-weight: 700; }

    /* ── Sidebar ── */
    section[data-testid='stSidebar'] {
        background-color: #0D1526;
        border-right: 2px solid #1A3050;
    }
    section[data-testid='stSidebar'] * { color: #E8ECF0 !important; }

    /* ── Botões ── */
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

    /* ── Elementos gerais ── */
    hr { border-color: #FF6B00; }
    [data-testid='metric-container'] {
        background-color: #102040;
        border-left: 4px solid #FF6B00;
        border-radius: 4px; padding: 10px;
    }
    .stProgress > div > div > div > div {
        background-color: #FF6B00 !important;
    }

    /* ── Log ── */
    .bloco-log {
        background: #060B14; border: 1px solid #1A3050;
        border-radius: 6px; padding: 14px;
        font-family: Consolas, monospace; font-size: 12px;
        white-space: pre-wrap; max-height: 520px;
        overflow-y: auto; color: #E8ECF0;
    }

    /* ── Badges de leiaute ── */
    .badge-ecd {
        background: #1a0a2e; color: #F472B6; font-weight: 700;
        padding: 6px 14px; border-radius: 6px;
        border: 1px solid #F472B6; display: inline-block;
    }
    .badge-excel {
        background: #0a2e1a; color: #00C896; font-weight: 700;
        padding: 6px 14px; border-radius: 6px;
        border: 1px solid #00C896; display: inline-block;
    }
    .badge-lote {
        background: #2e2a0a; color: #FFD166; font-weight: 700;
        padding: 6px 14px; border-radius: 6px;
        border: 1px solid #FFD166; display: inline-block;
    }
    .badge-pos {
        background: #0a1a2e; color: #6EC6FF; font-weight: 700;
        padding: 6px 14px; border-radius: 6px;
        border: 1px solid #6EC6FF; display: inline-block;
    }
    .badge-si {
        background: #1a0a2e; color: #FF9EBC; font-weight: 700;
        padding: 6px 14px; border-radius: 6px;
        border: 1px solid #FF9EBC; display: inline-block;
    }
    .badge-desconhecido {
        background: #2e0a0a; color: #FF4444; font-weight: 700;
        padding: 6px 14px; border-radius: 6px;
        border: 1px solid #FF4444; display: inline-block;
    }

    /* ── Cards ── */
    .header-box {
        background: #102040; padding: 20px 24px 14px;
        border-radius: 8px; border-top: 5px solid #FF6B00;
        margin-bottom: 20px;
    }
    .cnpj-auto {
        background: #0a2e1a; border: 1px solid #00C896;
        border-radius: 8px; padding: 12px 18px;
        margin: 10px 0 16px 0; color: #00C896; font-weight: 700;
    }
    .cnpj-auto span { color: #FFD166; }
    .info-box {
        background: #102040; border-left: 4px solid #FF6B00;
        border-radius: 4px; padding: 12px 16px;
        margin: 8px 0; font-size: 13px;
    }
    .card-ok {
        background: #0a2e1a; border: 2px solid #00C896;
        border-radius: 10px; padding: 18px 24px; margin: 12px 0;
    }
    .card-err {
        background: #2e0a0a; border: 2px solid #FF4444;
        border-radius: 10px; padding: 18px 24px; margin: 12px 0;
    }
    .card-warn {
        background: #1a1000; border-left: 4px solid #FFD166;
        border-radius: 4px; padding: 10px 16px; margin: 8px 0;
    }
    .filial-box {
        background: #0a1a2e; border: 1px solid #6EC6FF;
        border-radius: 8px; padding: 14px 18px; margin: 10px 0;
    }
    .si-box {
        background: #1a0a2e; border: 1px solid #FF9EBC;
        border-radius: 8px; padding: 14px 18px; margin: 10px 0;
    }

    /* ── Painel de detecção ── */
    .painel-deteccao {
        background: #102040; border-left: 4px solid #6EC6FF;
        border-radius: 6px; padding: 14px 18px; margin: 10px 0;
    }

    /* ── Particionamento ── */
    .part-box {
        background: #0a1a0a; border: 1px solid #00C896;
        border-radius: 8px; padding: 14px 18px; margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# CRONÔMETRO
# ═══════════════════════════════════════════════════════════════════════════════
class Cronometro:
    """Cronômetro com suporte a etapas nomeadas."""

    def __init__(self) -> None:
        self._inicio_total: float = 0.0
        self._etapas: list        = []
        self._inicio_etapa: float = 0.0
        self._etapa_atual: str    = ""

    def iniciar(self) -> None:
        self._inicio_total = time.perf_counter()
        self._etapas.clear()

    def etapa(self, nome: str) -> None:
        agora = time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({
                "nome":     self._etapa_atual,
                "segundos": round(agora - self._inicio_etapa, 3),
            })
        self._etapa_atual  = nome
        self._inicio_etapa = agora

    def encerrar(self) -> float:
        agora = time.perf_counter()
        if self._etapa_atual:
            self._etapas.append({
                "nome":     self._etapa_atual,
                "segundos": round(agora - self._inicio_etapa, 3),
            })
            self._etapa_atual = ""
        return round(agora - self._inicio_total, 3)

    @staticmethod
    def fmt(s: float) -> str:
        if s < 0.001: return "<1ms"
        if s < 1:     return f"{s * 1000:.0f}ms"
        if s < 60:    return f"{s:.2f}s"
        m = int(s // 60)
        return f"{m}min {s % 60:.1f}s"

    @property
    def etapas(self) -> list:
        return self._etapas
		
# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — SANITIZAÇÃO DE TEXTO
# ═══════════════════════════════════════════════════════════════════════════════

# Mapa de caracteres especiais → equivalentes latin-1 seguros
_MAPA_ESPECIAIS = {
    "\u2018": "'",  "\u2019": "'",  "\u201C": '"',  "\u201D": '"',
    "\u2013": "-",  "\u2014": "-",  "\u2026": "...","\u00A0": " ",
    "\u00D7": "x",  "\u00F7": "/",  "\u20AC": "EUR","\u00A7": "S/",
    "\u00AE": "(R)","\u00A9": "(C)","\u2122": "(TM)",
    # Vogais maiúsculas com diacríticos
    "\u00C0": "A",  "\u00C1": "A",  "\u00C2": "A",  "\u00C3": "A",
    "\u00C4": "A",  "\u00C5": "A",
    # Vogais minúsculas com diacríticos
    "\u00E0": "a",  "\u00E1": "a",  "\u00E2": "a",  "\u00E3": "a",
    "\u00E4": "a",  "\u00E5": "a",
    "\u00C8": "E",  "\u00C9": "E",  "\u00CA": "E",  "\u00CB": "E",
    "\u00E8": "e",  "\u00E9": "e",  "\u00EA": "e",  "\u00EB": "e",
    "\u00CC": "I",  "\u00CD": "I",  "\u00CE": "I",  "\u00CF": "I",
    "\u00EC": "i",  "\u00ED": "i",  "\u00EE": "i",  "\u00EF": "i",
    "\u00D2": "O",  "\u00D3": "O",  "\u00D4": "O",  "\u00D5": "O",
    "\u00D6": "O",
    "\u00F2": "o",  "\u00F3": "o",  "\u00F4": "o",  "\u00F5": "o",
    "\u00F6": "o",
    "\u00D9": "U",  "\u00DA": "U",  "\u00DB": "U",  "\u00DC": "U",
    "\u00F9": "u",  "\u00FA": "u",  "\u00FB": "u",  "\u00FC": "u",
    "\u00DD": "Y",  "\u00FD": "y",  "\u00FF": "y",
    "\u00C7": "C",  "\u00E7": "c",
    "\u00D1": "N",  "\u00F1": "n",
    "\u00BA": "o",  "\u00AA": "a",  "\u00B0": "o",
    "\u00BD": "1/2","\u00BC": "1/4","\u00BE": "3/4",
    "\u0131": "i",  "\u00DF": "ss",
}


def _norm_hist(texto: str) -> str:
    """
    Normaliza um texto para uso em históricos do leiaute Domínio.
    - Substitui caracteres especiais por equivalentes ASCII/latin-1
    - Remove caracteres de controle
    - Substitui pipes (|) por espaço
    - Limita a 250 caracteres
    """
    if not texto:
        return ""

    # Substitui caracteres especiais mapeados
    for orig, dest in _MAPA_ESPECIAIS.items():
        texto = texto.replace(orig, dest)

    texto = unicodedata.normalize("NFC", texto)
    res   = []

    for ch in texto:
        cp = ord(ch)

        # Remove caracteres de controle (exceto TAB)
        if cp < 0x20 and cp != 9:
            continue

        # Pipe vira espaço (protege o leiaute)
        if ch == "|":
            res.append(" ")
            continue

        # Tenta encodar diretamente em latin-1
        try:
            ch.encode("latin-1")
            res.append(ch)
            continue
        except UnicodeEncodeError:
            pass

        # Tenta a base do caractere decomposto (ex: ã → a)
        decomposto = unicodedata.normalize("NFD", ch)
        base       = decomposto[0]
        try:
            base.encode("latin-1")
            res.append(base)
            continue
        except UnicodeEncodeError:
            pass

        # Tenta extrair a letra base pelo nome unicode
        nome = unicodedata.name(ch, "")
        if "LATIN" in nome:
            partes = nome.split()
            for i, p in enumerate(partes):
                if p == "LETTER" and i + 1 < len(partes):
                    letra = partes[i + 1]
                    if len(letra) == 1:
                        res.append(
                            letra.lower() if "SMALL" in nome else letra.upper()
                        )
                        break
        # Caracteres sem equivalente são simplesmente descartados

    return re.sub(r" {2,}", " ", "".join(res)).strip()[:250]


def sanitizar_texto(t: str) -> str:
    """Sanitiza qualquer texto para uso seguro no leiaute."""
    return _norm_hist(str(t) if t else "")


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — FORMATAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def formatar_data(v) -> str:
    """Converte qualquer representação de data para DD/MM/YYYY."""
    try:
        if isinstance(v, (datetime, pd.Timestamp)):
            return v.strftime("%d/%m/%Y")
        return pd.to_datetime(v, dayfirst=True).strftime("%d/%m/%Y")
    except Exception:
        return str(v)


def _fmt_valor_layout(valor) -> str:
    """
    Formata um valor numérico para o padrão do leiaute Domínio: 9999,99
    Aceita float, int, str com ponto ou vírgula como separador decimal.
    """
    if isinstance(valor, (int, float)):
        return f"{float(valor):.2f}".replace(".", ",")

    v = str(valor).strip()

    # Detecta separador de milhar vs decimal
    if "." in v and "," in v:
        if v.index(".") < v.index(","):
            # Formato BR: 1.234,56
            v = v.replace(".", "").replace(",", ".")
        else:
            # Formato US: 1,234.56
            v = v.replace(",", "")
    elif "," in v:
        v = v.replace(",", ".")

    try:
        return f"{float(v):.2f}".replace(".", ",")
    except ValueError:
        return "0,00"


def fmt_cnpj(n: str) -> str:
    """Formata CNPJ: 00.000.000/0001-00"""
    c = re.sub(r"\D", "", str(n))
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else n


def fmt_cpf(n: str) -> str:
    """Formata CPF: 000.000.000-00"""
    c = re.sub(r"\D", "", str(n))
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else n


def fmt_reg_0000(ni: str) -> str:
    """Gera o registro |0000|CNPJ/CPF|"""
    return f"|0000|{ni}|"


def fmt_reg_6000(tp: str) -> str:
    """Gera o registro |6000|TIPO||||"""
    return f"|6000|{tp}||||"


def fmt_reg_6100(data, deb, cred, valor,
                 cod_hist: str = "", desc: str = "",
                 _u: str = "", _f: str = "", _s: str = "") -> str:
    """
    Gera o registro |6100| no leiaute padrão Domínio (sem filial).
    Para versão com filial, usar _fmt_reg_6100_excel().
    """
    return (
        f"|6100|{data}|{deb}|{cred}"
        f"|{_fmt_valor_layout(valor)}"
        f"||{_norm_hist(desc)}|||||||"
    )


def ts_log() -> str:
    """Timestamp para uso em logs: YYYY-MM-DD HH:MM:SS"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def so_nums(v) -> str:
    """Remove todos os caracteres não numéricos."""
    return re.sub(r"\D", "", str(v))


def eh_vazio(v) -> bool:
    """Retorna True se o valor é considerado vazio/nulo."""
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except Exception:
        pass
    return str(v).strip() in ("", "nan", "NaN", "None")


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — VALIDAÇÃO DE CNPJ / CPF
# ═══════════════════════════════════════════════════════════════════════════════

def validar_cnpj(cnpj) -> bool:
    """Valida CNPJ com dígitos verificadores."""
    c = so_nums(cnpj)
    if len(c) != 14 or len(set(c)) == 1:
        return False

    def _dv(c: str, pesos: list) -> int:
        s = sum(int(c[i]) * pesos[i] for i in range(len(pesos)))
        r = s % 11
        return 0 if r < 2 else 11 - r

    return (
        int(c[12]) == _dv(c, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]) and
        int(c[13]) == _dv(c, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    )


def validar_cpf(cpf) -> bool:
    """Valida CPF com dígitos verificadores."""
    c = so_nums(cpf)
    if len(c) != 11 or len(set(c)) == 1:
        return False

    def _dv(c: str, n: int) -> int:
        s = sum(int(c[i]) * (n - i) for i in range(n - 1))
        r = (s * 10) % 11
        return 0 if r == 10 else r

    return int(c[9]) == _dv(c, 10) and int(c[10]) == _dv(c, 11)


def validar_inscricao(v: str) -> tuple:
    """
    Valida CNPJ ou CPF.
    Retorna (valido: bool, tipo: str, numero_limpo: str)
    """
    n = so_nums(v)
    if len(n) == 14 and validar_cnpj(n):
        return True,  "CNPJ", n
    if len(n) == 11 and validar_cpf(n):
        return True,  "CPF",  n
    return False, "", n


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — VETORIZAÇÃO NUMPY (performance em DataFrames)
# ═══════════════════════════════════════════════════════════════════════════════

_VAZIO_CONTA = frozenset(("", "nan", "none", "0", "0.0"))


def limpar_contas_vec(serie: pd.Series) -> np.ndarray:
    """
    Limpa e normaliza uma coluna de contas contábeis de forma vetorizada.
    - Remove NaN, zeros e strings vazias → ""
    - Converte floats como "123.0" → "123"
    - Retorna np.ndarray de strings
    """
    arr = serie.fillna("").astype(str).str.strip().str.lower().to_numpy()
    out = np.where(np.isin(arr, list(_VAZIO_CONTA)), "", arr)
    mask = out != ""

    if mask.any():
        vals = out[mask]
        conv = np.empty(len(vals), dtype=object)
        for i, v in enumerate(vals):
            try:
                conv[i] = str(int(float(v.replace(",", "."))))
            except Exception:
                conv[i] = v
        out[mask] = conv

    return out


def limpar_valor_vec(serie: pd.Series) -> np.ndarray:
    """
    Converte uma coluna de valores para float64 de forma vetorizada.
    - Aceita vírgula ou ponto como separador decimal
    - NaN e inválidos → 0.0
    - Arredonda para 2 casas decimais
    """
    return (
        pd.to_numeric(
            serie.fillna("0")
                 .astype(str)
                 .str.strip()
                 .str.replace(",", ".", regex=False)
                 .str.replace(r"[^\d.\-]", "", regex=True),
            errors="coerce"
        )
        .fillna(0.0)
        .round(2)
        .to_numpy(dtype=np.float64)
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — DETECÇÃO DE ENCODING
# ═══════════════════════════════════════════════════════════════════════════════

# Caracteres típicos do português — usados para confirmar encoding
_CHARS_PT = set(
    "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞß"
    "àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿºª"
)


def _detectar_encoding_bytes(conteudo: bytes) -> str:
    """
    Detecta o encoding de um arquivo de bytes testando os mais comuns.
    Prioriza encodings que produzem caracteres portugueses válidos.
    Retorna o nome do encoding detectado (padrão: 'latin-1').
    """
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            texto = conteudo.decode(enc, errors="strict")
            # Valida pela presença de caracteres PT ou por ser UTF-8
            if (
                sum(1 for c in texto[:4096] if c in _CHARS_PT) > 0
                or enc in ("utf-8-sig", "utf-8")
            ):
                return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — GERAÇÃO DO REGISTRO 6110 (CENTRO DE CUSTOS)
# ═══════════════════════════════════════════════════════════════════════════════

def _gerar_6110_linha(deb_cta: str, cred_cta: str,
                      valor_fmt: str, modo: str) -> list:
    """
    Gera linha(s) do registro |6110| para centro de custos.

    Parâmetros:
        deb_cta   : código da conta de débito do CC
        cred_cta  : código da conta de crédito do CC
        valor_fmt : valor já formatado no padrão 9999,99
        modo      : "ambos" | "deb" | "cred"

    Retorna lista de strings (0, 1 ou 2 linhas).
    """
    linhas = []
    if modo in ("ambos", "deb")  and deb_cta:
        linhas.append(f"|6110|{deb_cta}||{valor_fmt}|")
    if modo in ("ambos", "cred") and cred_cta:
        linhas.append(f"|6110||{cred_cta}|{valor_fmt}|")
    return linhas


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — LIMPEZA DE FILIAL E CENTRO DE CUSTO
# ═══════════════════════════════════════════════════════════════════════════════

def _limpar_filial(v) -> str:
    """
    Normaliza o código de filial.
    - Zeros, vazios e NaN → ""
    - Floats como "1.0" → "1"
    """
    s = str(v).strip() if v is not None else ""
    if s.lower() in ("", "nan", "none", "0", "0.0"):
        return ""
    try:
        n = int(float(s))
        return "" if n == 0 else str(n)
    except Exception:
        return s


def _limpar_cc(v) -> str:
    """
    Normaliza o código de centro de custo.
    Mesma lógica de _limpar_filial.
    """
    s = str(v).strip() if v is not None else ""
    if s.lower() in ("", "nan", "none", "0", "0.0"):
        return ""
    try:
        n = int(float(s))
        return "" if n == 0 else str(n)
    except Exception:
        return s


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — CONVERSÃO DE VALORES DO SPED ECD
# ═══════════════════════════════════════════════════════════════════════════════

def _str2float(v) -> float:
    """
    Converte string de valor do SPED ECD para float.
    Aceita vírgula ou ponto como separador decimal.
    Retorna 0.0 em caso de falha.
    """
    if isinstance(v, (int, float)):
        return float(v)

    v = str(v).strip()

    if "." in v and "," in v:
        if v.index(".") < v.index(","):
            # Formato: 1.234,56
            v = v.replace(".", "").replace(",", ".")
        else:
            # Formato: 1,234.56
            v = v.replace(",", "")
    elif "," in v:
        v = v.replace(",", ".")

    try:
        return float(v)
    except Exception:
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — FORMATO EXCEL COM FILIAL
# ═══════════════════════════════════════════════════════════════════════════════

def _fmt_reg_6100_excel(data: str, deb: str, cred: str,
                        valor, desc: str, filial: str) -> str:
    """
    Gera o registro |6100| com campo de filial (leiaute Excel/Posicional).
    Diferente de fmt_reg_6100() que não inclui filial.
    """
    return (
        f"|6100|{data}|{deb}|{cred}"
        f"|{_fmt_valor_layout(valor)}"
        f"||{_norm_hist(desc)}||{filial}||"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — SPLIT DE PIPE (SPED)
# ═══════════════════════════════════════════════════════════════════════════════

def _split_pipe(linha: str) -> list:
    """
    Divide uma linha do SPED pelo separador pipe (|).
    Remove os campos vazios das bordas (pipe inicial e final).
    Ex: "|0000|LECD|..." → ["0000", "LECD", ...]
    """
    c = linha.strip().split("|")
    if c and c[0]  == "": c = c[1:]
    if c and c[-1] == "": c = c[:-1]
    return c


def _campo(campos: list, idx: int, default: str = "") -> str:
    """
    Retorna o campo de índice `idx` de uma lista de campos SPED.
    Retorna `default` se o índice não existir.
    """
    return campos[idx].strip() if idx < len(campos) else default


def _conta_valida(conta: str) -> bool:
    """
    Valida se um código de conta é numérico e não vazio.
    Contas do SPED ECD devem ser numéricas no I250.
    """
    return bool(conta) and conta.isdigit()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — NORMALIZAÇÃO DE DATA ECD
# ═══════════════════════════════════════════════════════════════════════════════

def _normalizar_data_ecd(d: str) -> str:
    """
    Normaliza datas do SPED ECD para o formato DD/MM/YYYY.
    Aceita:
        - DDMMYYYY  (formato compacto do SPED)
        - DD/MM/YYYY (já normalizado)
        - YYYY-MM-DD (ISO)
    """
    d = d.strip()
    if not d:
        return ""

    # Já está no formato correto
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", d):
        return d

    # Formato compacto SPED: DDMMYYYY
    if re.fullmatch(r"\d{8}", d):
        return f"{d[:2]}/{d[2:4]}/{d[4:]}"

    # Formato ISO: YYYY-MM-DD
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", d)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"

    return d


def _fmt_data_ecd(d: str) -> str:
    """
    Converte data do SPED ECD (DDMMYYYY) para DD/MM/YYYY.
    Se já contiver '/', retorna sem alteração.
    """
    d = d.strip()
    if "/" in d:
        return d
    if len(d) == 8 and d.isdigit():
        return f"{d[:2]}/{d[2:4]}/{d[4:]}"
    return d


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — LOG E RELATÓRIO DE ERROS ECD
# ═══════════════════════════════════════════════════════════════════════════════

def _txt_erros_ecd(registros_erro: list, cnpj: str) -> str:
    """
    Gera o conteúdo de texto do relatório de erros do SPED ECD.
    Retorna string pronta para download.
    """
    linhas = [
        "=" * 70,
        "RELATÓRIO DE ERROS — SPED ECD",
        f"CNPJ  : {cnpj}",
        f"Total : {len(registros_erro)}",
        f"Data  : {ts_log()}",
        "=" * 70,
        "",
    ]
    for i, r in enumerate(registros_erro, 1):
        linhas += [
            f"[{i:04d}] Linha    : {r.get('linha', '-')}",
            f"       Motivo   : {r.get('motivo', '')}",
            f"       Conteúdo : {r.get('conteudo', '')}",
            "",
        ]
    linhas += ["=" * 70, "FIM DO RELATÓRIO"]
    return "\n".join(linhas)


def _montar_log_lote(resumo: list, erros: list, ni: str,
                     ti: str, inf: str, n_gravados: int,
                     ignoradas: int, enc: str,
                     crono: "Cronometro") -> str:
    """
    Monta o log completo de conversão para arquivos TXT/Excel.
    Retorna string formatada para download.
    """
    td = sum(v["total_debito"]  for v in resumo)
    tc = sum(v["total_credito"] for v in resumo)
    ok = len(resumo) - len(erros)
    conc = (
        "SUCESSO"
        if not erros
        else f"ATENÇÃO — {len(erros)} lote(s) desbalanceado(s)"
    )

    SEP  = "═" * 90
    sep2 = "─" * 90

    L = [
        SEP,
        "  DOMÍNIO SISTEMAS  |  Thomson Reuters",
        "  LOG DE VALIDAÇÃO — LANÇAMENTOS CONTÁBEIS",
        SEP,
        f"  Data/Hora     : {ts_log()}",
        f"  Encoding leit.: {enc or 'N/A'}",
        f"  {ti:<6}         : {inf}",
        SEP, "",
        "  RESUMO GERAL", sep2,
        f"  Lotes total   : {len(resumo):>10,}",
        f"  Lotes OK      : {ok:>10,}",
        f"  Lotes ERRO    : {len(erros):>10,}",
        f"  Reg. 6000+6100: {n_gravados:>10,}",
        f"  Ignoradas     : {ignoradas:>10,}",
        f"  Total Déb.    : R$ {td:>14.2f}",
        f"  Total Créd.   : R$ {tc:>14.2f}",
        f"  Conclusão     : {conc}",
        "",
    ]

    # Relatório de tempo por etapa
    if crono and crono.etapas:
        total_seg = sum(e["segundos"] for e in crono.etapas)
        L += [sep2, "  RELATÓRIO DE TEMPO", sep2]
        for e in crono.etapas:
            L.append(
                f"  {'  ' + e['nome']:<38} {Cronometro.fmt(e['segundos']):>8}"
            )
        L += [
            "  " + "─" * 46,
            f"  {'  TOTAL':<38} {Cronometro.fmt(total_seg):>8}",
            "",
        ]

    # Detalhe por lote
    L += [
        SEP,
        f"  {'Lote':<8}{'Linhas':<16}{'Data':<13}{'Qtd':<6}"
        f"{'Débito':>15}{'Crédito':>15}{'Diferença':>13}  Status",
        "  " + "─" * 88,
    ]
    for v in resumo:
        L.append(
            f"  {str(v['num_lote']):<8}{v['faixa_linhas']:<16}"
            f"{v['data']:<13}{str(v['qtd_linhas']):<6}"
            f"R$ {v['total_debito']:>12.2f}  "
            f"R$ {v['total_credito']:>12.2f}  "
            f"R$ {v['diferenca']:>10.2f}   "
            f"{'✔ OK' if v['balanceado'] else '✖ ERRO'}"
        )
    L += [
        "  " + "─" * 88,
        f"  {'TOTAIS':<37}R$ {td:>12.2f}  R$ {tc:>12.2f}",
        "",
        SEP,
        f"  Fim  │  {ts_log()}",
        f"  Resultado │  {conc}",
        SEP,
    ]

    return "\n".join(L)
	
# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 3 — IDENTIFICAÇÃO PRECISA DE LEIAUTE
# ═══════════════════════════════════════════════════════════════════════════════
#
# Substitui a função identificar_tipo() do V3.6.2 por uma validação rigorosa
# baseada no campo LECD do registro 0000, que é EXCLUSIVO do SPED ECD.
#
# Fluxo de decisão:
#   1. Excel       → pela extensão (.xlsx/.xls/.xlsm)
#   2. SPED ECD    → 0000 + campo[1] == "LECD"  (alta confiança)
#   3. SPED ECD    → 0000 sem LECD mas ≥3 registros ECD  (média confiança)
#   4. Outro SPED  → 0000 sem LECD e <3 registros ECD   (desconhecido)
#   5. Posicional  → registros 01/02/03 sem pipe
#   6. TXT Lote    → maioria das linhas contém ";"
#   7. Desconhecido → nenhum dos anteriores
# ═══════════════════════════════════════════════════════════════════════════════


def validar_e_identificar_arquivo(nome_arquivo: str, conteudo: bytes) -> dict:
    """
    Identifica com precisão o tipo e subtipo do arquivo enviado.

    Retorna um dict com as chaves:
        tipo        : "ecd" | "lote" | "excel" | "dominio_pos" | "desconhecido"
        subtipo     : "ecd_lancamentos" | "ecd_saldo_inicial" | None
        confianca   : "alta" | "media" | "baixa"
        motivo      : str  — explicação textual da decisão
        avisos      : list[str]  — alertas (não impedem o processamento)
        cnpj        : str  — extraído do 0000 (se disponível)
        nome_empresa: str  — extraído do 0000 (se disponível)
        dt_ini      : str  — data inicial do período (SPED)
        dt_fin      : str  — data final do período (SPED)
    """
    ext    = os.path.splitext(nome_arquivo)[1].lower()
    avisos = []

    # ── 1. Excel — detecção pela extensão ────────────────────────────────────
    if ext in (".xlsx", ".xls", ".xlsm"):
        return {
            "tipo":         "excel",
            "subtipo":      None,
            "confianca":    "alta",
            "motivo":       f"Arquivo Excel detectado pela extensão '{ext}'.",
            "avisos":       [],
            "cnpj":         "",
            "nome_empresa": "",
            "dt_ini":       "",
            "dt_fin":       "",
        }

    # ── Decodifica amostra para análise ──────────────────────────────────────
    enc = _detectar_encoding_bytes(conteudo)
    try:
        amostra = conteudo[:20480].decode(enc, errors="replace")
    except Exception:
        amostra = conteudo[:20480].decode("utf-8", errors="replace")

    linhas   = [l for l in amostra.splitlines() if l.strip()]
    primeiras = linhas[:80]

    # Metadados extraídos do 0000
    cnpj         = ""
    nome_empresa = ""
    dt_ini       = ""
    dt_fin       = ""

    # Flags de detecção
    tem_0000              = False
    tem_lecd              = False   # campo[1] == "LECD" → assinatura exclusiva da ECD
    tem_i010              = False
    tem_i050              = False
    tem_i150              = False
    tem_i155              = False
    tem_i200              = False
    tem_i250              = False
    tem_i355              = False
    tem_9999              = False
    tem_reg_pos           = False
    tem_separador_semi    = False

    registros_ecd_achados: set = set()

    for linha in primeiras:
        campos = _split_pipe(linha)
        if not campos:
            continue

        reg = campos[0].strip()

        # ── Registro 0000 ─────────────────────────────────────────────────
        if reg == "0000":
            tem_0000 = True

            # Campo índice 1 = COD_LEIAUTE → "LECD" é exclusivo da ECD
            leiaute = _campo(campos, 1).strip().upper()
            if leiaute == "LECD":
                tem_lecd = True

            # Extrai metadados do período e empresa
            dt_ini       = _campo(campos, 2).strip()   # DT_INI
            dt_fin       = _campo(campos, 3).strip()   # DT_FIN
            # Campo 5 = CNPJ na ECD (após DT_INI, DT_FIN, COD_SIT, IND_SIT_ESP)
            # Layout real: |0000|LECD|DT_INI|DT_FIN|COD_SIT|CNPJ|...
            cnpj_raw     = _campo(campos, 5).strip()
            nome_raw     = _campo(campos, 6).strip()
            cnpj         = re.sub(r"\D", "", cnpj_raw)
            nome_empresa = _norm_hist(nome_raw)

            # Normaliza as datas para DD/MM/YYYY
            dt_ini = _normalizar_data_ecd(dt_ini)
            dt_fin = _normalizar_data_ecd(dt_fin)

        # ── Registros exclusivos da ECD ───────────────────────────────────
        elif reg == "I010":
            tem_i010 = True
            registros_ecd_achados.add(reg)

        elif reg == "I050":
            tem_i050 = True
            registros_ecd_achados.add(reg)

        elif reg == "I150":
            tem_i150 = True
            registros_ecd_achados.add(reg)

        elif reg == "I155":
            tem_i155 = True
            registros_ecd_achados.add(reg)

        elif reg == "I200":
            tem_i200 = True
            registros_ecd_achados.add(reg)

        elif reg == "I250":
            tem_i250 = True
            registros_ecd_achados.add(reg)

        elif reg == "I355":
            tem_i355 = True
            registros_ecd_achados.add(reg)

        elif reg == "9999":
            tem_9999 = True

        elif reg in REGISTROS_ECD:
            registros_ecd_achados.add(reg)

        # ── Detecção de posicional Domínio ────────────────────────────────
        s = linha.rstrip("\r\n")
        if not tem_reg_pos:
            # Registro 01: linha com ≥54 chars, começa com "01",
            # posição 43 = "N" (IND_DAD) — layout posicional Domínio
            if len(s) >= 54 and s[:2] == "01" and "|" not in s[:20]:
                tem_reg_pos = True
            # Registro 02: linha com ≥20 chars, começa com "02",
            # sem pipes nos primeiros 10 chars
            elif len(s) >= 20 and s[:2] == "02" and "|" not in s[:10]:
                tem_reg_pos = True
            # Registro 03: linha com ≥20 chars, começa com "03",
            # sem pipes nos primeiros 10 chars
            elif len(s) >= 20 and s[:2] == "03" and "|" not in s[:10]:
                tem_reg_pos = True

        # ── Detecção de TXT com separador ";" ────────────────────────────
        if not tem_separador_semi and ";" in linha and "|" not in linha:
            tem_separador_semi = True

    # ── DECISÃO DE TIPO ───────────────────────────────────────────────────────

    # ── Caso 1: 0000 + LECD → SPED ECD confirmado (alta confiança) ──────────
    if tem_0000 and tem_lecd:

        # Determina subtipo pelo conteúdo detectado
        if tem_i200 or tem_i250:
            subtipo = "ecd_lancamentos"
            motivo  = (
                f"SPED ECD confirmado — campo LECD presente no 0000. "
                f"Lançamentos detectados (I200/I250). "
                f"Registros ECD: {sorted(registros_ecd_achados)}"
            )
        elif tem_i155 or tem_i355:
            subtipo = "ecd_saldo_inicial"
            motivo  = (
                f"SPED ECD confirmado — campo LECD presente no 0000. "
                f"Apenas saldos detectados (I155/I355) — sem lançamentos I200. "
                f"Registros ECD: {sorted(registros_ecd_achados)}"
            )
        else:
            # Arquivo ECD válido mas amostra pequena — default lançamentos
            subtipo = "ecd_lancamentos"
            motivo  = (
                f"SPED ECD confirmado — campo LECD presente no 0000. "
                f"Subtipo não determinado na amostra — assumindo lançamentos. "
                f"Registros detectados: {sorted(registros_ecd_achados)}"
            )

        if not cnpj:
            avisos.append(
                "⚠️ CNPJ não encontrado no registro 0000. "
                "Informe manualmente antes de processar."
            )

        return {
            "tipo":         "ecd",
            "subtipo":      subtipo,
            "confianca":    "alta",
            "motivo":       motivo,
            "avisos":       avisos,
            "cnpj":         cnpj,
            "nome_empresa": nome_empresa,
            "dt_ini":       dt_ini,
            "dt_fin":       dt_fin,
        }

    # ── Caso 2: 0000 sem LECD — pode ser EFD-ICMS, ECF, EFD-Contrib ─────────
    if tem_0000 and not tem_lecd:

        n_regs_ecd = len(registros_ecd_achados)

        if n_regs_ecd >= 3:
            # Tem vários registros típicos de ECD → provavelmente ECD com
            # campo LECD ausente na amostra (arquivo grande, 0000 fora da amostra)
            avisos.append(
                "⚠️ Registro 0000 encontrado, mas campo LECD ausente na amostra. "
                f"{n_regs_ecd} registros típicos de ECD detectados. "
                "Processando como ECD — verifique se o arquivo é realmente um SPED ECD."
            )
            subtipo = "ecd_lancamentos" if (tem_i200 or tem_i250) else (
                "ecd_saldo_inicial" if (tem_i155 or tem_i355) else "ecd_lancamentos"
            )
            return {
                "tipo":         "ecd",
                "subtipo":      subtipo,
                "confianca":    "media",
                "motivo":       (
                    f"0000 encontrado sem LECD, mas {n_regs_ecd} registros ECD detectados. "
                    f"Registros: {sorted(registros_ecd_achados)}"
                ),
                "avisos":       avisos,
                "cnpj":         cnpj,
                "nome_empresa": nome_empresa,
                "dt_ini":       dt_ini,
                "dt_fin":       dt_fin,
            }

        else:
            # Pouco ou nenhum registro ECD → outro módulo SPED
            return {
                "tipo":         "desconhecido",
                "subtipo":      None,
                "confianca":    "baixa",
                "motivo":       (
                    "Registro 0000 encontrado, mas campo LECD ausente e poucos "
                    "registros ECD detectados. Provável EFD-ICMS, ECF ou "
                    "EFD-Contribuições — não é um SPED ECD válido."
                ),
                "avisos":       [
                    "⛔ Este arquivo não parece ser um SPED ECD. "
                    "Verifique se o módulo correto foi selecionado para exportação."
                ],
                "cnpj":         cnpj,
                "nome_empresa": nome_empresa,
                "dt_ini":       dt_ini,
                "dt_fin":       dt_fin,
            }

    # ── Caso 3: Sem 0000 — verifica outros formatos ───────────────────────────
    if tem_reg_pos:
        return {
            "tipo":         "dominio_pos",
            "subtipo":      None,
            "confianca":    "alta",
            "motivo":       (
                "Arquivo posicional Domínio detectado — "
                "registros 01/02/03 sem separador pipe."
            ),
            "avisos":       [],
            "cnpj":         "",
            "nome_empresa": "",
            "dt_ini":       "",
            "dt_fin":       "",
        }

    # Conta linhas com ";" para confirmar TXT lote
    n_com_semi = sum(1 for l in primeiras if ";" in l and "|" not in l)
    pct_semi   = n_com_semi / len(primeiras) if primeiras else 0.0

    if pct_semi >= 0.4 or tem_separador_semi:
        return {
            "tipo":         "lote",
            "subtipo":      None,
            "confianca":    "media" if pct_semi >= 0.4 else "baixa",
            "motivo":       (
                f"TXT separado por ';' detectado — "
                f"{n_com_semi}/{len(primeiras)} linhas com separador "
                f"({pct_semi*100:.0f}%)."
            ),
            "avisos":       (
                ["⚠️ Poucas linhas com ';' — verifique se o formato está correto."]
                if pct_semi < 0.4 else []
            ),
            "cnpj":         "",
            "nome_empresa": "",
            "dt_ini":       "",
            "dt_fin":       "",
        }

    # ── Caso 4: Formato desconhecido ─────────────────────────────────────────
    return {
        "tipo":         "desconhecido",
        "subtipo":      None,
        "confianca":    "baixa",
        "motivo":       (
            "Formato não reconhecido. Nenhum indicador de leiaute "
            "detectado na amostra do arquivo."
        ),
        "avisos":       [
            "⛔ Formato de arquivo não suportado. "
            "Formatos aceitos: SPED ECD (.txt), TXT separado por ';', "
            "Excel (.xlsx/.xls), TXT Posicional Domínio."
        ],
        "cnpj":         "",
        "nome_empresa": "",
        "dt_ini":       "",
        "dt_fin":       "",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAPA DE BADGES E CONFIANÇA — usados na renderização do painel de detecção
# ═══════════════════════════════════════════════════════════════════════════════

BADGE_MAP = {
    "ecd": (
        "<span class='badge-ecd'>📋 SPED ECD</span>",
        "#F472B6"
    ),
    "lote": (
        "<span class='badge-lote'>📄 TXT Lote (;)</span>",
        "#FFD166"
    ),
    "excel": (
        "<span class='badge-excel'>📊 Excel</span>",
        "#00C896"
    ),
    "dominio_pos": (
        "<span class='badge-pos'>📋 TXT Posicional</span>",
        "#6EC6FF"
    ),
    "desconhecido": (
        "<span class='badge-desconhecido'>❓ Formato Desconhecido</span>",
        "#FF4444"
    ),
}

CONFIANCA_MAP = {
    "alta":  ("✅ Alta",  "#00C896"),
    "media": ("⚠️ Média", "#FFD166"),
    "baixa": ("❌ Baixa", "#FF4444"),
}

SUBTIPO_LABEL = {
    "ecd_lancamentos":   "Lançamentos (I200/I250)",
    "ecd_saldo_inicial": "Saldo Inicial (I155/I355)",
}


def _render_painel_deteccao(deteccao: dict, nome_arquivo: str,
                             tamanho_bytes: int) -> None:
    """
    Renderiza o painel de identificação do leiaute na interface Streamlit.

    Exibe:
        - Badge colorido com o tipo detectado
        - Nome do arquivo e tamanho
        - Confiança da detecção
        - Motivo (explicação técnica)
        - Metadados extraídos do 0000 (empresa, CNPJ, período)
        - Avisos (se houver)
        - Bloco de erro + st.stop() se formato desconhecido
    """
    tipo      = deteccao["tipo"]
    subtipo   = deteccao.get("subtipo") or ""
    confianca = deteccao.get("confianca", "baixa")

    badge_html, badge_cor = BADGE_MAP.get(tipo, BADGE_MAP["desconhecido"])
    conf_txt,   conf_cor  = CONFIANCA_MAP.get(confianca, ("?", "#FF4444"))

    mb = tamanho_bytes / (1024 * 1024)

    # Linha de subtipo (só para ECD)
    subtipo_html = ""
    if subtipo and subtipo in SUBTIPO_LABEL:
        subtipo_html = (
            f"&nbsp;|&nbsp;"
            f"<span style='color:#FF9EBC;font-weight:600;'>"
            f"🔖 {SUBTIPO_LABEL[subtipo]}</span>"
        )

    st.markdown(
        f"""
        <div style='background:#102040;border-left:4px solid {badge_cor};
                    border-radius:6px;padding:14px 18px;margin:10px 0;'>
            <div style='display:flex;align-items:center;gap:12px;flex-wrap:wrap;'>
                {badge_html}
                {subtipo_html}
                <span style='color:#9BB0C8;font-size:13px;'>
                    📄 {nome_arquivo}
                    &nbsp;|&nbsp; {mb:.1f} MB
                    &nbsp;|&nbsp; Confiança:
                    <b style='color:{conf_cor};'>{conf_txt}</b>
                </span>
            </div>
            <div style='color:#9BB0C8;font-size:12px;margin-top:8px;'>
                {deteccao['motivo']}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Metadados do 0000 (empresa / período)
    if deteccao.get("cnpj") or deteccao.get("nome_empresa"):
        cnpj_fmt = fmt_cnpj(deteccao["cnpj"]) if len(deteccao["cnpj"]) == 14 else deteccao["cnpj"]
        periodo  = ""
        if deteccao.get("dt_ini") or deteccao.get("dt_fin"):
            periodo = f"&nbsp;|&nbsp; Período: {deteccao['dt_ini']} a {deteccao['dt_fin']}"

        st.markdown(
            f"<div class='cnpj-auto'>"
            f"🏢 <b style='color:#6EC6FF;'>Empresa:</b> "
            f"<span>{deteccao['nome_empresa'] or '—'}</span>"
            f"&nbsp;|&nbsp; CNPJ: <b>{cnpj_fmt or '—'}</b>"
            f"{periodo}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Avisos
    for aviso in deteccao.get("avisos", []):
        st.warning(aviso)

    # Formato desconhecido — bloqueia o fluxo
    if tipo == "desconhecido":
        st.error(
            "⛔ **Formato de arquivo não suportado.**\n\n"
            "**Formatos aceitos:**\n"
            "- 📋 SPED ECD (`.txt` com `|0000|LECD|...`)\n"
            "- 📄 TXT separado por `;`\n"
            "- 📊 Excel (`.xlsx` / `.xls` / `.xlsm`)\n"
            "- 📋 TXT Posicional Domínio (registros 01/02/03)"
        )
        st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# COMPATIBILIDADE — mantém identificar_tipo() para não quebrar código legado
# ═══════════════════════════════════════════════════════════════════════════════

def identificar_tipo(nome_arquivo: str, conteudo: bytes) -> str:
    """
    Wrapper de compatibilidade com o V3.6.2.
    Internamente usa validar_e_identificar_arquivo() e retorna apenas o tipo.

    Mapeamento de retorno:
        "ecd"         → arquivo SPED ECD (lançamentos ou saldo inicial)
        "lote"        → TXT separado por ";"
        "excel"       → Excel (.xlsx/.xls/.xlsm)
        "dominio_pos" → TXT Posicional Domínio
        "lote"        → fallback para desconhecido (mantém comportamento anterior)
    """
    det = validar_e_identificar_arquivo(nome_arquivo, conteudo)
    tipo = det["tipo"]

    # Desconhecido → fallback "lote" (comportamento do V3.6.2)
    if tipo == "desconhecido":
        return "lote"

    return tipo


def _tipo_para_subtipo_ecd(deteccao: dict) -> str:
    """
    Retorna o subtipo ECD detectado para uso no session_state.
    Retorna "ecd" para lançamentos ou "ecd_saldo" para saldo inicial.
    """
    subtipo = deteccao.get("subtipo", "ecd_lancamentos")
    if subtipo == "ecd_saldo_inicial":
        return "ecd_saldo"
    return "ecd"
	
# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 4 — MÓDULO SPED ECD LANÇAMENTOS (I200/I250)
# Integra:
#   • _parse_ecd()        — leitura dos registros I050, I075, I200, I250
#   • _gerar_ecd()        — geração dos registros 6000 + 6100
#   • _injetar_6110_ecd() — injeção do 6110 com CC (se ativo)
#   • extrair_centros_custos() — extrai COD_CCUS dos I250
#   • Suporte ao map_final_para_geracao (DE/PARA de contas)
#   • Suporte ao cc_map (DE/PARA de Centro de Custo)
# ═══════════════════════════════════════════════════════════════════════════════


# ── Estrutura de dados do SPED ECD ──────────────────────────────────────────

class SpedECD:
    """Estrutura de dados que representa um SPED ECD lido."""

    __slots__ = ("cnpj", "contas", "historicos", "lancamentos")

    def __init__(self) -> None:
        self.cnpj:        str  = ""
        self.contas:      dict = {}   # cod_cta → nome
        self.historicos:  dict = {}   # cod_hist → descricao
        self.lancamentos: list = []   # list[dict] — cada dict é um I200 + suas partidas I250


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRAÇÃO DE CENTROS DE CUSTO (COD_CCUS do I250)
# ═══════════════════════════════════════════════════════════════════════════════

def extrair_centros_custos(content_sped: list) -> set:
    """
    Extrai todos os códigos de Centro de Custo únicos
    presentes nos registros I250 do SPED ECD.

    Layout I250 (campos após split por '|', bordas removidas):
        [0] I250
        [1] COD_CTA      — código reduzido da conta
        [2] NUM_LCTO     — número do lançamento
        [3] DT_LCTO      — data do lançamento
        [4] VL_DC        — valor
        [5] IND_DC       — D ou C
        [6] NUM_SEQ      — sequencial
        [7] COD_HIST     — código do histórico
        [8] COD_CCUS     — ← Centro de Custo (campo que nos interessa)

    Retorna set de strings com os códigos únicos encontrados.
    Ignora valores vazios, "0" e ausentes.
    """
    centros: set = set()

    for linha in content_sped:
        if not linha.startswith("|I250|"):
            continue

        campos = _split_pipe(linha)
        # campos[0] = "I250", campos[8] = COD_CCUS
        if len(campos) > 8:
            cc = campos[8].strip()
            if cc and cc not in ("0", ""):
                centros.add(cc)

    return centros


# ═══════════════════════════════════════════════════════════════════════════════
# PARSE DO SPED ECD — LEITURA DOS REGISTROS
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_ecd(conteudo: bytes, log: list) -> tuple:
    """
    Lê o arquivo SPED ECD e extrai:
        - CNPJ (registro 0000)
        - Plano de contas (registro I050)
        - Históricos (registro I075)
        - Lançamentos (registros I200 + I250)

    Cada lançamento é um dict:
        {
            "num":     str   — NUM_LCTO do I200
            "data":    str   — DT_LCTO do I200 (formato DDMMYYYY ou DD/MM/YYYY)
            "valor":   str   — VL_LC do I200
            "partidas": list — list[dict] com as partidas do I250
        }

    Cada partida é um dict:
        {
            "conta":      str — COD_CTA (código reduzido)
            "valor":      str — VL_DC
            "dc":         str — IND_DC ("D" ou "C")
            "descr_hist": str — histórico normalizado
            "cod_ccus":   str — COD_CCUS (Centro de Custo, pode ser "")
        }

    Retorna (SpedECD | None, list[dict] erros)
    """
    ecd             = SpedECD()
    lote_atual      = None
    erros_parse     = 0
    registros_erro  = []
    contas_invalidas = 0
    i200_count      = 0
    i250_count      = 0

    enc = _detectar_encoding_bytes(conteudo)
    log.append(f"  Encoding detectado : {enc}")

    try:
        texto = conteudo.decode(enc, errors="replace")
    except Exception:
        texto = conteudo.decode("utf-8", errors="replace")

    linhas = texto.splitlines()
    log.append(f"  Total de linhas    : {len(linhas):,}")

    for num, linha in enumerate(linhas, 1):
        linha_orig = linha
        linha      = linha.strip()
        if not linha:
            continue

        campos = _split_pipe(linha)
        if not campos:
            continue

        reg = campos[0]

        try:
            # ── Registro 0000 — CNPJ ────────────────────────────────────────
            if reg == "0000":
                # Layout: |0000|LECD|DT_INI|DT_FIN|COD_SIT|CNPJ|...
                if len(campos) > 5:
                    ecd.cnpj = re.sub(r"\D", "", _campo(campos, 5))

            # ── Registro I050 — Plano de Contas ─────────────────────────────
            elif reg == "I050":
                # Layout: |I050|...|COD_NAT|IND_CTA|...|COD_CTA|COD_STA|NOME|...
                # Campo 5 = COD_CTA, Campo 7 = NOME (layout padrão SPED ECD)
                cod  = _campo(campos, 5)
                nome = _campo(campos, 7)
                if cod:
                    ecd.contas[cod] = nome

            # ── Registro I075 — Históricos Padronizados ──────────────────────
            elif reg == "I075":
                # Layout: |I075|COD_HIST|DESCR_HIST|
                cod  = _campo(campos, 1)
                desc = _campo(campos, 2)
                if cod:
                    ecd.historicos[cod] = _norm_hist(desc)

            # ── Registro I200 — Lançamento ───────────────────────────────────
            elif reg == "I200":
                # Layout: |I200|NUM_LCTO|DT_LCTO|VL_LC|IND_DC_LC|...|
                lote_atual = {
                    "num":      _campo(campos, 1),
                    "data":     _campo(campos, 2),
                    "valor":    _campo(campos, 3),
                    "partidas": [],
                }
                ecd.lancamentos.append(lote_atual)
                i200_count += 1

            # ── Registro I250 — Partida ──────────────────────────────────────
            elif reg == "I250":
                # Layout: |I250|COD_CTA|NUM_LCTO|DT_LCTO|VL_DC|IND_DC|
                #                NUM_SEQ|COD_HIST|COD_CCUS|...
                if lote_atual is None:
                    registros_erro.append({
                        "linha":    num,
                        "motivo":   "I250 sem I200 precedente",
                        "conteudo": linha_orig.strip(),
                    })
                    continue

                conta      = _campo(campos, 1)
                valor_str  = _campo(campos, 4)
                dc         = _campo(campos, 5).upper()
                cod_hist   = _campo(campos, 7)
                cod_ccus   = _campo(campos, 8)   # COD_CCUS — Centro de Custo

                # Monta histórico: tenta I075, senão usa o campo 7 diretamente
                descr_hist = ecd.historicos.get(
                    cod_hist,
                    _norm_hist(cod_hist)
                )

                # Validações
                if dc not in ("D", "C"):
                    registros_erro.append({
                        "linha":    num,
                        "motivo":   f"IND_DC='{dc}' inválido (esperado D ou C)",
                        "conteudo": linha_orig.strip(),
                    })
                    continue

                if not _conta_valida(conta):
                    registros_erro.append({
                        "linha":    num,
                        "motivo":   f"Conta '{conta}' inválida (deve ser numérica)",
                        "conteudo": linha_orig.strip(),
                    })
                    contas_invalidas += 1
                    continue

                lote_atual["partidas"].append({
                    "conta":      conta,
                    "valor":      valor_str,
                    "dc":         dc,
                    "descr_hist": descr_hist,
                    "cod_ccus":   cod_ccus.strip(),
                })
                i250_count += 1

            # ── Registros de encerramento de lançamento ──────────────────────
            elif reg in ("I299", "I300"):
                lote_atual = None

        except Exception as ex:
            registros_erro.append({
                "linha":    num,
                "motivo":   f"Exceção: {ex}",
                "conteudo": linha_orig.strip(),
            })
            erros_parse += 1
            if erros_parse > 50:
                log.append("  ERRO: muitos erros consecutivos — parse abortado.")
                return None, registros_erro

    # ── Validação pós-parse ──────────────────────────────────────────────────
    if not ecd.cnpj:
        log.append("  ERRO: CNPJ não encontrado no registro 0000.")
        return None, registros_erro

    log.append(f"  CNPJ               : {ecd.cnpj}")
    log.append(f"  Contas (I050)      : {len(ecd.contas):,}")
    log.append(f"  Históricos (I075)  : {len(ecd.historicos):,}")
    log.append(f"  Lançamentos (I200) : {i200_count:,}")
    log.append(f"  Partidas (I250)    : {i250_count:,}")

    if contas_invalidas:
        log.append(f"  Contas inválidas   : {contas_invalidas:,}")
    if registros_erro:
        log.append(f"  Erros/avisos       : {len(registros_erro):,}")

    return ecd, registros_erro


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS DE LANÇAMENTO
# ═══════════════════════════════════════════════════════════════════════════════

def _montar_hist_ecd(partida: dict) -> str:
    """Retorna o histórico normalizado de uma partida."""
    return partida.get("descr_hist", "").strip()


def _primeiro_hist(partidas: list) -> str:
    """Retorna o primeiro histórico não vazio das partidas."""
    for p in partidas:
        h = _montar_hist_ecd(p)
        if h:
            return h
    return ""


def _classif(nd: int, nc: int) -> str:
    """
    Classifica o tipo de lançamento pelo número de débitos e créditos.
        X — 1 débito  × 1 crédito
        D — 1 débito  × N créditos
        C — N débitos × 1 crédito
        V — N débitos × N créditos
    """
    if nd == 1 and nc == 1: return "X"
    if nd == 1 and nc > 1:  return "D"
    if nd > 1  and nc == 1: return "C"
    return "V"


def tipo_lancamento(nd: int, nc: int) -> str:
    """Wrapper público de _classif()."""
    return _classif(nd, nc)


# ═══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DAS LINHAS 6000 + 6100 POR LANÇAMENTO
# ═══════════════════════════════════════════════════════════════════════════════

def _linhas_ecd(lanc: dict,
                map_contas: dict,
                cc_map: dict,
                usar_cc: bool,
                gerar_6110: bool) -> list:
    """
    Converte um lançamento ECD (I200 + partidas I250) em linhas do leiaute
    Domínio: |6000| + |6100| (+ |6110| se habilitado).

    Parâmetros:
        lanc       : dict do lançamento (saído do _parse_ecd)
        map_contas : dict {cod_antigo → cod_novo} — DE/PARA de contas
        cc_map     : dict {cc_antigo → cc_novo}   — DE/PARA de CC
        usar_cc    : bool — se True, substitui COD_CCUS pelo cc_map
        gerar_6110 : bool — se True, injeta |6110| após cada |6100|

    Retorna lista de strings (linhas prontas para escrita).
    Retorna [] se o lançamento não tiver débitos E créditos.
    """
    partidas = lanc["partidas"]
    debs     = [p for p in partidas if p["dc"] == "D"]
    creds    = [p for p in partidas if p["dc"] == "C"]

    if not debs or not creds:
        return []

    data = _fmt_data_ecd(lanc["data"])
    nd   = len(debs)
    nc   = len(creds)
    hist = _primeiro_hist(partidas)
    out  = []

    def _conta_dest(conta_orig: str) -> str:
        """Aplica o DE/PARA de contas."""
        return str(map_contas.get(conta_orig, conta_orig)).strip().replace("|", "")

    def _cc_dest(cc_orig: str) -> str:
        """Aplica o DE/PARA de Centro de Custo."""
        if not usar_cc or not cc_orig:
            return cc_orig
        return str(cc_map.get(cc_orig, cc_orig)).strip().replace("|", "")

    def _hist_p(p: dict) -> str:
        return _montar_hist_ecd(p) or hist

    def _linha_6100(deb: str, cred: str, valor, h: str) -> str:
        return fmt_reg_6100(data, deb, cred, valor, "", h)

    def _linhas_6110(p: dict, modo: str) -> list:
        """Gera linhas |6110| para a partida, se habilitado."""
        if not gerar_6110:
            return []
        cc_orig = p.get("cod_ccus", "")
        cc_novo = _cc_dest(cc_orig)
        if not cc_novo:
            return []
        v_fmt = _fmt_valor_layout(_str2float(p["valor"]))
        if modo == "deb":
            return _gerar_6110_linha(cc_novo, "",      v_fmt, "deb")
        if modo == "cred":
            return _gerar_6110_linha("",      cc_novo, v_fmt, "cred")
        # "ambos" — para tipo X onde a partida tem deb e cred
        return _gerar_6110_linha(cc_novo, cc_novo, v_fmt, "ambos")

    # ── Tipo X — 1 débito × 1 crédito ───────────────────────────────────────
    if nd == 1 and nc == 1:
        db = debs[0]; cr = creds[0]
        h  = _montar_hist_ecd(db) or _montar_hist_ecd(cr) or hist
        cd = _conta_dest(db["conta"])
        cc = _conta_dest(cr["conta"])
        v  = _str2float(db["valor"])

        out.append(fmt_reg_6000("X"))
        out.append(_linha_6100(cd, cc, v, h))

        # 6110 para tipo X: débito usa CC do db, crédito usa CC do cr
        if gerar_6110:
            cc_deb  = _cc_dest(db.get("cod_ccus", ""))
            cc_cred = _cc_dest(cr.get("cod_ccus", ""))
            v_fmt   = _fmt_valor_layout(v)
            if cc_deb or cc_cred:
                for l6110 in _gerar_6110_linha(cc_deb, cc_cred, v_fmt, "ambos"):
                    out.append(l6110)

    # ── Tipo D — 1 débito × N créditos ──────────────────────────────────────
    elif nd == 1 and nc > 1:
        db = debs[0]
        h  = _montar_hist_ecd(db) or hist
        cd = _conta_dest(db["conta"])
        v  = _str2float(db["valor"])

        out.append(fmt_reg_6000("D"))
        out.append(_linha_6100(cd, "", v, h))
        out.extend(_linhas_6110(db, "deb"))

        for cr in creds:
            h_cr = _montar_hist_ecd(cr) or _montar_hist_ecd(db) or hist
            cc   = _conta_dest(cr["conta"])
            v_cr = _str2float(cr["valor"])
            out.append(_linha_6100("", cc, v_cr, h_cr))
            out.extend(_linhas_6110(cr, "cred"))

    # ── Tipo C — N débitos × 1 crédito ──────────────────────────────────────
    elif nd > 1 and nc == 1:
        cr = creds[0]
        h  = _montar_hist_ecd(cr) or hist
        cc = _conta_dest(cr["conta"])
        v  = _str2float(cr["valor"])

        out.append(fmt_reg_6000("C"))
        out.append(_linha_6100("", cc, v, h))
        out.extend(_linhas_6110(cr, "cred"))

        for db in debs:
            h_db = _montar_hist_ecd(db) or _montar_hist_ecd(cr) or hist
            cd   = _conta_dest(db["conta"])
            v_db = _str2float(db["valor"])
            out.append(_linha_6100(cd, "", v_db, h_db))
            out.extend(_linhas_6110(db, "deb"))

    # ── Tipo V — N débitos × N créditos ─────────────────────────────────────
    else:
        out.append(fmt_reg_6000("V"))

        for cr in creds:
            h_cr = _montar_hist_ecd(cr) or hist
            cc   = _conta_dest(cr["conta"])
            v_cr = _str2float(cr["valor"])
            out.append(_linha_6100("", cc, v_cr, h_cr))
            out.extend(_linhas_6110(cr, "cred"))

        for db in debs:
            h_db = _montar_hist_ecd(db) or hist
            cd   = _conta_dest(db["conta"])
            v_db = _str2float(db["valor"])
            out.append(_linha_6100(cd, "", v_db, h_db))
            out.extend(_linhas_6110(db, "deb"))

    return out


# ═══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DO ARQUIVO COMPLETO (0000 + 6000 + 6100 + 6110)
# ═══════════════════════════════════════════════════════════════════════════════

def _gerar_ecd(ecd: SpedECD,
               map_contas: dict,
               cc_map: dict,
               usar_cc: bool,
               gerar_6110: bool,
               log: list,
               prog_bar,
               status) -> list:
    """
    Itera sobre todos os lançamentos do SpedECD e gera a lista de linhas
    no leiaute Domínio: |0000| + (|6000| + |6100| [+ |6110|]) × N

    Parâmetros:
        ecd        : SpedECD parseado
        map_contas : DE/PARA de contas {cod_antigo → cod_novo}
        cc_map     : DE/PARA de CC     {cc_antigo  → cc_novo}
        usar_cc    : bool — ativa substituição de COD_CCUS
        gerar_6110 : bool — ativa injeção do registro 6110
        log        : list de strings para log
        prog_bar   : st.progress widget
        status     : st.empty widget para texto de status

    Retorna list[str] — linhas prontas para join e encode.
    """
    linhas: list = [fmt_reg_0000(re.sub(r"\D", "", ecd.cnpj))]

    t6000    = 0
    t6100    = 0
    t6110    = 0
    ignorados = 0
    debug    = {"X": 0, "D": 0, "C": 0, "V": 0}
    total    = len(ecd.lancamentos)

    for idx, lanc in enumerate(ecd.lancamentos):

        # Atualiza progresso a cada 500 lançamentos
        if idx % 500 == 0 or idx == total - 1:
            pct = min(55 + int(((idx + 1) / total) * 35), 99)
            prog_bar.progress(pct)
            status.text(f"Gerando lançamento {idx + 1:,}/{total:,}...")

        if not lanc.get("partidas"):
            ignorados += 1
            continue

        novas = _linhas_ecd(lanc, map_contas, cc_map, usar_cc, gerar_6110)

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
            elif l.startswith("|6110|"):
                t6110 += 1

        linhas.extend(novas)

    # ── Log de geração ───────────────────────────────────────────────────────
    log.append(f"  Reg. 6000 gerados  : {t6000:,}")
    log.append(f"  Reg. 6100 gerados  : {t6100:,}")
    if gerar_6110:
        log.append(f"  Reg. 6110 gerados  : {t6110:,}")
    log.append(f"  Ignorados          : {ignorados:,}")
    log.append(
        f"  Tipos — "
        f"X:{debug.get('X', 0):,}  "
        f"D:{debug.get('D', 0):,}  "
        f"C:{debug.get('C', 0):,}  "
        f"V:{debug.get('V', 0):,}"
    )

    return linhas


# ═══════════════════════════════════════════════════════════════════════════════
# INJEÇÃO DO 6110 EM ARQUIVO JÁ GERADO (fallback — sem CC_MAP)
# Mantido para compatibilidade com fluxos que não usam cc_map
# ═══════════════════════════════════════════════════════════════════════════════

def _injetar_6110_ecd(linhas_ecd: list) -> list:
    """
    Injeta registros |6110| após cada |6100| existente,
    usando as próprias contas de débito/crédito como código de CC.

    Usado quando gerar_6110=True mas cc_map está vazio —
    o CC gerado será o mesmo código da conta contábil.

    Retorna nova lista com as linhas 6110 intercaladas.
    """
    resultado = []

    for l in linhas_ecd:
        resultado.append(l)

        if l.startswith("|6100|"):
            campos = l.split("|")
            if len(campos) >= 6:
                deb_l   = campos[3].strip() if len(campos) > 3 else ""
                cred_l  = campos[4].strip() if len(campos) > 4 else ""
                valor_l = campos[5].strip() if len(campos) > 5 else ""

                if deb_l and cred_l:
                    modo = "ambos"
                elif deb_l:
                    modo = "deb"
                else:
                    modo = "cred"

                for linha_6110 in _gerar_6110_linha(deb_l, cred_l, valor_l, modo):
                    resultado.append(linha_6110)

    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DO RELATÓRIO DE ERROS DO SPED ECD
# ═══════════════════════════════════════════════════════════════════════════════

def _txt_erros_ecd(registros_erro: list, cnpj: str) -> str:
    """
    Gera o conteúdo textual do relatório de erros do SPED ECD.
    Retorna string pronta para download (.txt).
    """
    SEP = "=" * 70
    linhas = [
        SEP,
        "RELATÓRIO DE ERROS — SPED ECD",
        f"CNPJ   : {cnpj}",
        f"Total  : {len(registros_erro):,}",
        f"Data   : {ts_log()}",
        SEP,
        "",
    ]

    for i, r in enumerate(registros_erro, 1):
        linhas += [
            f"[{i:04d}] Linha    : {r.get('linha', '-')}",
            f"       Motivo   : {r.get('motivo', '')}",
            f"       Conteúdo : {r.get('conteudo', '')}",
            "",
        ]

    linhas += [SEP, "FIM DO RELATÓRIO"]
    return "\n".join(linhas)


# ═══════════════════════════════════════════════════════════════════════════════
# PRÉ-SCAN DO CNPJ (leitura rápida do 0000 sem processar o arquivo inteiro)
# ═══════════════════════════════════════════════════════════════════════════════

def _pre_scan_cnpj_ecd(conteudo: bytes) -> str:
    """
    Lê apenas os primeiros 4096 bytes do arquivo para extrair o CNPJ
    do registro 0000, sem precisar decodificar o arquivo inteiro.

    Retorna string com 14 dígitos ou "" se não encontrar.
    """
    enc = _detectar_encoding_bytes(conteudo)
    try:
        amostra = conteudo[:4096].decode(enc, errors="replace")
    except Exception:
        amostra = conteudo[:4096].decode("utf-8", errors="replace")

    for linha in amostra.splitlines():
        campos = _split_pipe(linha.strip())
        if campos and campos[0] == "0000" and len(campos) > 5:
            cnpj = re.sub(r"\D", "", campos[5].strip())
            if len(cnpj) == 14:
                return cnpj

    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA DO MÓDULO ECD LANÇAMENTOS
# ═══════════════════════════════════════════════════════════════════════════════

def processar_ecd_lancamentos(conteudo: bytes,
                               ni: str,
                               map_contas: dict,
                               cc_map: dict,
                               usar_cc: bool,
                               gerar_6110: bool,
                               log: list,
                               prog_bar,
                               status) -> tuple:
    """
    Ponto de entrada do módulo SPED ECD — Lançamentos.

    Fluxo:
        1. _parse_ecd()    → lê I050, I075, I200, I250
        2. _gerar_ecd()    → gera 0000 + 6000 + 6100 (+ 6110 se ativo)
        3. Monta bytes de saída
        4. Retorna (resultado_bytes, metricas, registros_erro)

    Parâmetros:
        conteudo   : bytes do arquivo SPED ECD
        ni         : CNPJ/CPF limpo (14 ou 11 dígitos)
        map_contas : DE/PARA de contas
        cc_map     : DE/PARA de Centro de Custo
        usar_cc    : bool — ativa substituição de COD_CCUS
        gerar_6110 : bool — ativa injeção do registro 6110
        log        : list para log
        prog_bar   : widget st.progress
        status     : widget st.empty

    Retorna:
        resultado_bytes : bytes  — arquivo gerado (utf-8-sig)
        metricas        : dict   — métricas para exibição
        registros_erro  : list   — erros de parse
    """
    status.text("Lendo SPED ECD...")
    prog_bar.progress(10)
    log.append("── PARSE SPED ECD — LANÇAMENTOS ──")

    ecd, registros_erro = _parse_ecd(conteudo, log)

    if ecd is None:
        log.append("  ERRO FATAL: parse abortado.")
        return b"", {}, registros_erro

    # Usa CNPJ do arquivo se ni não foi informado
    cnpj_uso = ni if ni else ecd.cnpj
    if not cnpj_uso:
        log.append("  ERRO: CNPJ não encontrado.")
        return b"", {}, registros_erro + [
            {"linha": 0, "motivo": "CNPJ não encontrado", "conteudo": ""}
        ]

    prog_bar.progress(30)
    status.text("Gerando registros...")
    log.append("\n── GERAÇÃO ──")

    linhas_ecd = _gerar_ecd(
        ecd, map_contas, cc_map, usar_cc, gerar_6110,
        log, prog_bar, status
    )

    # Fallback: se gerar_6110 ativo mas cc_map vazio,
    # injeta 6110 usando as próprias contas como CC
    if gerar_6110 and not cc_map:
        log.append("  ℹ️ cc_map vazio — injetando 6110 com contas como CC (fallback).")
        linhas_ecd = _injetar_6110_ecd(linhas_ecd)

    prog_bar.progress(90)
    status.text("Montando arquivo...")
    log.append("\n── MONTAGEM ──")

    buf_out = io.StringIO()
    for i in range(0, len(linhas_ecd), WRITE_CHUNK):
        buf_out.write("\n".join(linhas_ecd[i:i + WRITE_CHUNK]) + "\n")

    resultado_bytes = buf_out.getvalue().encode("utf-8-sig")
    del buf_out, linhas_ecd
    gc.collect()

    n6000   = resultado_bytes.count(b"|6000|")
    n6100   = resultado_bytes.count(b"|6100|")
    n6110_f = resultado_bytes.count(b"|6110|")

    log.append(f"  Tamanho saída      : {len(resultado_bytes) / 1024:.1f} KB")

    metricas = {
        "CNPJ / CPF":        cnpj_uso,
        "Lançamentos (I200)": f"{len(ecd.lancamentos):,}",
        "Registros 6000":    f"{n6000:,}",
        "Registros 6100":    f"{n6100:,}",
        "Tamanho saída":     f"{len(resultado_bytes) / 1024:.1f} KB",
    }
    if gerar_6110:
        metricas["Registros 6110"] = f"{n6110_f:,}"
    if usar_cc and cc_map:
        metricas["CC mapeados"] = f"{len(cc_map):,}"

    prog_bar.progress(100)
    status.text("Concluído!")

    return resultado_bytes, metricas, registros_erro

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 5 — MÓDULO SALDO INICIAL V3.6.2
# Integra:
#   • _sugerir_conta_pl()          — sugestão automática da conta PL
#   • _parse_saldo_inicial_ecd()   — lê I050, I150, I155, I355
#   • _calcular_resultado_liquido_i355() — calcula superávit/déficit
#   • _encontrar_conta_pl_resultado()   — resolve conta PL (manual ou auto)
#   • _gerar_saldo_inicial_dominio()    — gera 0000+6000+6100
#   • _pre_scan_conta_pl_sugerida()     — pré-scan rápido sem processar tudo
#   • processar_saldo_inicial_ecd()     — ponto de entrada
# ═══════════════════════════════════════════════════════════════════════════════


# ── Palavras-chave para detecção da conta PL/Resultado no I050 ───────────────
_PALAVRAS_RESULTADO = (
    "SUPERAVIT", "DÉFICIT", "DEFICIT",
    "RESULTADO", "LUCRO", "PREJUIZO", "PREJUÍZO",
    "SOBRA", "PERDA", "SURPLUS",
    "RESULTADO DO EXERC", "LUCROS OU PREJUIZ",
)

# COD_NAT que indicam conta de resultado/PL no I050
_NAT_RESULTADO = frozenset(("05", "09", "5", "9"))


# ═══════════════════════════════════════════════════════════════════════════════
# SUGESTÃO AUTOMÁTICA DA CONTA PL/RESULTADO
# ═══════════════════════════════════════════════════════════════════════════════

def _sugerir_conta_pl(contas_pl_candidatas: list,
                      saldos_i155_raw: dict,
                      resultado_liquido: float,
                      log: list) -> str:
    """
    Sugere automaticamente a conta de Superávit/Déficit (PL) com base em:
        1. COD_NAT "09" ou "9" (conta de resultado — prioridade máxima)
        2. Proximidade do saldo no I155 com o resultado líquido do I355
        3. Palavras-chave no nome da conta (RESULTADO, SUPERAVIT, etc.)

    Parâmetros:
        contas_pl_candidatas : list[dict] com chaves:
                               cod_cta, nome, cod_nat, cod_sup, criterio
        saldos_i155_raw      : dict {cod_cta → (valor_float, ind_dc)}
        resultado_liquido    : float — valor absoluto do resultado líquido I355
        log                  : list para log

    Retorna:
        str — código da conta sugerida, ou "" se não encontrar candidatas
    """
    if not contas_pl_candidatas:
        log.append("  Sugestão PL        : nenhuma candidata encontrada no I050")
        return ""

    # Enriquece candidatas com saldo do I155 e diferença em relação ao resultado
    candidatas_com_saldo = []
    for c in contas_pl_candidatas:
        cod = c["cod_cta"]
        if cod in saldos_i155_raw:
            v, dc = saldos_i155_raw[cod]
            diff  = abs(abs(v) - resultado_liquido)
            candidatas_com_saldo.append({**c, "saldo": v, "dc": dc, "diff": diff})

    # Se nenhuma candidata tem saldo no I155, retorna a primeira pelo COD_NAT
    if not candidatas_com_saldo:
        c = contas_pl_candidatas[0]
        log.append(
            f"  Sugestão PL        : {c['cod_cta']} — {c['nome']} "
            f"(sem saldo no I155)"
        )
        return c["cod_cta"]

    def _score(c: dict) -> tuple:
        """
        Critério de ordenação:
            1. COD_NAT "09"/"9" → prioridade 0 (melhor)
            2. Diferença entre saldo I155 e resultado líquido (menor = melhor)
        """
        prioridade_nat = 0 if c["cod_nat"] in ("09", "9") else 1
        return (prioridade_nat, c["diff"])

    candidatas_com_saldo.sort(key=_score)
    melhor = candidatas_com_saldo[0]

    log.append("\n  ── SUGESTÃO AUTOMÁTICA — CONTA PL/RESULTADO ──")
    log.append(f"  Conta sugerida     : {melhor['cod_cta']}")
    log.append(f"  Nome               : {melhor['nome']}")
    log.append(f"  COD_NAT            : {melhor['cod_nat']}")
    log.append(f"  Saldo no I155      : R$ {melhor['saldo']:,.2f} {melhor['dc']}")
    log.append(f"  Resultado líquido  : R$ {resultado_liquido:,.2f}")
    log.append(f"  Critério detecção  : {melhor['criterio']}")

    return melhor["cod_cta"]


# ═══════════════════════════════════════════════════════════════════════════════
# PARSE DO SPED ECD — SALDO INICIAL (I150 + I155 + I355)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_saldo_inicial_ecd(conteudo: bytes, log: list) -> dict:
    """
    Lê I050, I150, I155 e I355 do SPED ECD.

    Separa automaticamente:
        - Contas patrimoniais (I155) — Ativo / Passivo / PL
        - Contas de resultado (I355) — Receitas / Despesas abertas

    Contas que aparecem no I355 são marcadas como resultado e
    excluídas do I155 patrimonial (evita duplicidade de saldo).

    Retorna dict com:
        cnpj              : str
        data_ref          : str — data de referência (DD/MM/YYYY)
        saldos_i155_pat   : dict {cod_cta → (valor, dc)} — patrimoniais
        saldos_i155_res   : dict {cod_cta → (valor, dc)} — resultado zerado
        saldos_i355       : dict {cod_cta → (valor, dc)} — resultado aberto
        conta_pl_sugerida : str — código sugerido automaticamente
        erros             : list[dict]
        cnt               : dict — contadores de registros
    """
    enc = _detectar_encoding_bytes(conteudo)
    log.append(f"  Encoding detectado : {enc}")

    try:
        texto = conteudo.decode(enc, errors="replace")
    except Exception:
        texto = conteudo.decode("utf-8", errors="replace")

    linhas = texto.splitlines()
    log.append(f"  Total de linhas    : {len(linhas):,}")

    # Metadados
    cnpj          = ""
    dt_fin_0000   = ""
    periodos      = []
    erros         = []

    # Saldos por período (I150 → I155)
    i155_por_periodo: dict = {}
    periodo_atual_idx = -1

    # Saldos de resultado (I355)
    saldos_i355:  dict = {}
    contas_i355:  set  = set()

    # Mapeamento de contas (I050)
    mapa_nome_cta:      dict = {}   # cod_cta → nome
    mapa_nat_cta:       dict = {}   # cod_cta → cod_nat
    contas_pl_candidatas: list = []

    # Contadores
    cnt = {"0000": 0, "I150": 0, "I155": 0, "I355": 0}

    for num_linha, linha in enumerate(linhas, 1):
        linha = linha.strip()
        if not linha:
            continue

        campos = _split_pipe(linha)
        if not campos:
            continue

        reg = campos[0]

        try:
            # ── Registro 0000 ─────────────────────────────────────────────
            if reg == "0000":
                cnt["0000"] = cnt.get("0000", 0) + 1
                if len(campos) > 5:
                    cnpj = re.sub(r"\D", "", _campo(campos, 5).strip())
                if len(campos) > 4:
                    dt_fin_0000 = _campo(campos, 4).strip()

            # ── Registro I050 — Plano de Contas ──────────────────────────
            elif reg == "I050":
                if len(campos) < 6:
                    continue

                cod_nat  = _campo(campos, 2).strip()
                ind_cta  = _campo(campos, 3).strip().upper()
                cod_cta  = _campo(campos, 5).strip()
                cod_sup  = _campo(campos, 6).strip() if len(campos) > 6 else ""
                nome_cta = _campo(campos, 7).strip() if len(campos) > 7 else ""

                if not cod_cta:
                    continue

                mapa_nome_cta[cod_cta] = nome_cta
                mapa_nat_cta[cod_cta]  = cod_nat

                # Verifica se é candidata a conta PL/Resultado
                eh_resultado_nat  = cod_nat in _NAT_RESULTADO
                nome_up           = nome_cta.upper()
                eh_resultado_nome = any(p in nome_up for p in _PALAVRAS_RESULTADO)

                # Apenas contas analíticas (IND_CTA = "A") são candidatas
                if ind_cta == "A" and (eh_resultado_nat or eh_resultado_nome):
                    contas_pl_candidatas.append({
                        "cod_cta":  cod_cta,
                        "nome":     nome_cta,
                        "cod_nat":  cod_nat,
                        "cod_sup":  cod_sup,
                        "criterio": "COD_NAT" if eh_resultado_nat else "NOME",
                    })

            # ── Registro I150 — Período de Saldos ────────────────────────
            elif reg == "I150":
                cnt["I150"] += 1
                dt_ini = _campo(campos, 1).strip()
                dt_fin = _campo(campos, 2).strip()
                periodos.append((dt_ini, dt_fin))
                periodo_atual_idx = len(periodos) - 1
                if periodo_atual_idx not in i155_por_periodo:
                    i155_por_periodo[periodo_atual_idx] = {}

            # ── Registro I155 — Saldos Patrimoniais ──────────────────────
            elif reg == "I155":
                cnt["I155"] += 1
                if periodo_atual_idx < 0:
                    erros.append({
                        "linha":    num_linha,
                        "motivo":   "I155 sem I150 precedente",
                        "conteudo": linha[:80],
                    })
                    continue

                cod_cta    = _campo(campos, 1).strip()
                vl_fin     = _campo(campos, 7).strip()   # VL_SLD_FIN_NC
                ind_dc_fin = _campo(campos, 8).strip().upper()  # IND_DC_FIN

                if not cod_cta:
                    continue
                if ind_dc_fin not in ("D", "C"):
                    ind_dc_fin = "D"

                try:
                    valor_f = _str2float(vl_fin)
                except Exception:
                    valor_f = 0.0

                i155_por_periodo[periodo_atual_idx][cod_cta] = (valor_f, ind_dc_fin)

            # ── Registro I355 — Saldos de Resultado ──────────────────────
            elif reg == "I355":
                cnt["I355"] += 1
                cod_cta = _campo(campos, 1).strip()
                vl_cta  = _campo(campos, 3).strip()
                ind_dc  = _campo(campos, 4).strip().upper()

                if not cod_cta:
                    continue
                if ind_dc not in ("D", "C"):
                    ind_dc = "D"

                try:
                    valor_f = _str2float(vl_cta)
                except Exception:
                    valor_f = 0.0

                saldos_i355[cod_cta] = (valor_f, ind_dc)
                contas_i355.add(cod_cta)

        except Exception as ex:
            erros.append({
                "linha":    num_linha,
                "motivo":   f"Exceção: {ex}",
                "conteudo": linha[:80],
            })

    # ── Saldos I155 do ÚLTIMO período ────────────────────────────────────────
    saldos_i155_raw: dict = {}
    if i155_por_periodo:
        ultimo_idx      = max(i155_por_periodo.keys())
        saldos_i155_raw = i155_por_periodo[ultimo_idx]
        log.append(f"  Períodos I150      : {len(periodos):,}")
        log.append(
            f"  Último período     : "
            f"{_normalizar_data_ecd(periodos[ultimo_idx][0])} a "
            f"{_normalizar_data_ecd(periodos[ultimo_idx][1])}"
        )
    else:
        log.append("  AVISO: Nenhum registro I150/I155 encontrado.")

    # ── Separa patrimoniais de resultado ─────────────────────────────────────
    saldos_i155_pat = {
        cta: (v, dc)
        for cta, (v, dc) in saldos_i155_raw.items()
        if cta not in contas_i355
    }
    saldos_i155_res = {
        cta: (v, dc)
        for cta, (v, dc) in saldos_i155_raw.items()
        if cta in contas_i355
    }

    # ── Data de referência ────────────────────────────────────────────────────
    data_ref = periodos[-1][1] if periodos else dt_fin_0000
    data_ref = _normalizar_data_ecd(data_ref)

    # ── Log ───────────────────────────────────────────────────────────────────
    log.append(f"  CNPJ               : {cnpj}")
    log.append(f"  Data referência    : {data_ref}")
    log.append(f"  I155 patrimoniais  : {len(saldos_i155_pat):,} contas")
    log.append(
        f"  I155 resultado     : {len(saldos_i155_res):,} contas "
        f"(zeradas no encerramento)"
    )
    log.append(f"  I355 resultado     : {len(saldos_i355):,} contas (antes do encerramento)")
    log.append(f"  Candidatas PL      : {len(contas_pl_candidatas):,} conta(s) detectada(s) no I050")
    if erros:
        log.append(f"  Erros/avisos       : {len(erros):,}")

    # ── Sugestão automática da conta PL ──────────────────────────────────────
    total_rec        = sum(v for v, dc in saldos_i355.values() if dc == "C")
    total_des        = sum(v for v, dc in saldos_i355.values() if dc == "D")
    resultado_liq    = round(abs(total_rec - total_des), 2)

    conta_pl_sugerida = _sugerir_conta_pl(
        contas_pl_candidatas, saldos_i155_raw, resultado_liq, log
    )

    # Grava sugestão no session_state para exibir na UI antes do processamento
    if conta_pl_sugerida:
        nome_sug = mapa_nome_cta.get(conta_pl_sugerida, "")
        st.session_state["conta_pl_sugerida"]      = conta_pl_sugerida
        st.session_state["conta_pl_sugerida_nome"] = nome_sug
        log.append("\n  ── ORIENTAÇÃO ──")
        log.append(f"  Conta sugerida     : {conta_pl_sugerida}")
        log.append(f"  Nome               : {nome_sug}")
        log.append("  Use este código no campo 'Conta PL/Resultado' abaixo.")

    return {
        "cnpj":              cnpj,
        "data_ref":          data_ref,
        "saldos_i155_pat":   saldos_i155_pat,
        "saldos_i155_res":   saldos_i155_res,
        "saldos_i355":       saldos_i355,
        "conta_pl_sugerida": conta_pl_sugerida,
        "mapa_nome_cta":     mapa_nome_cta,
        "erros":             erros,
        "cnt":               cnt,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CÁLCULO DO RESULTADO LÍQUIDO (I355)
# ═══════════════════════════════════════════════════════════════════════════════

def _calcular_resultado_liquido_i355(saldos_i355: dict) -> tuple:
    """
    Calcula o resultado líquido do exercício a partir dos saldos do I355.

    Receitas = contas com IND_DC = "C" (saldo credor)
    Despesas = contas com IND_DC = "D" (saldo devedor)

    Resultado líquido = Σ Receitas − Σ Despesas
        > 0 → Superávit  (resultado credor — aumenta o PL)
        < 0 → Déficit    (resultado devedor — reduz o PL)

    Retorna:
        (resultado_liquido: float, ind_dc_resultado: str)
        ind_dc_resultado = "C" se superávit, "D" se déficit
    """
    total_rec = sum(v for _, (v, dc) in saldos_i355.items() if dc == "C")
    total_des = sum(v for _, (v, dc) in saldos_i355.items() if dc == "D")
    resultado  = round(total_rec - total_des, 2)

    if resultado >= 0:
        return resultado, "C"    # Superávit → PL credor
    else:
        return abs(resultado), "D"   # Déficit → PL devedor


# ═══════════════════════════════════════════════════════════════════════════════
# RESOLUÇÃO DA CONTA PL (manual ou automática)
# ═══════════════════════════════════════════════════════════════════════════════

def _encontrar_conta_pl_resultado(saldos_i155_pat: dict,
                                  conta_pl_manual: str,
                                  log: list) -> str:
    """
    Resolve a conta de Superávit/Déficit no PL.

    Prioridade:
        1. Conta informada manualmente pelo usuário
        2. Conta cujo saldo no I155 é exatamente igual ao resultado líquido

    Retorna o código da conta ou "" se não encontrar.
    """
    if conta_pl_manual and conta_pl_manual.strip():
        cta = conta_pl_manual.strip()
        if cta in saldos_i155_pat:
            log.append(f"  Conta PL resultado : {cta} (informada manualmente)")
            return cta
        else:
            log.append(
                f"  AVISO: Conta {cta} não encontrada no I155 patrimonial. "
                f"O balanço pode não fechar."
            )
            return cta   # Mantém a conta informada mesmo sem saldo (pode ser nova)

    log.append(
        "  Conta PL resultado : não identificada automaticamente — "
        "informe manualmente para o modo Aberto com Resultado."
    )
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DO LANÇAMENTO DE SALDO INICIAL (0000 + 6000 + 6100)
# ═══════════════════════════════════════════════════════════════════════════════

def _gerar_saldo_inicial_dominio(parsed: dict,
                                  ni: str,
                                  historico_prefixo: str,
                                  modo: str,
                                  conta_pl_resultado: str,
                                  log: list) -> tuple:
    """
    Gera o arquivo de saldo inicial no leiaute Domínio.

    Modos:
        "apenas_patrimonial"   — usa somente I155 (Ativo/Passivo/PL)
                                 Contas de resultado NÃO entram.
                                 Correto para balanço de abertura fechado.

        "aberto_com_resultado" — usa I155 patrimonial + I355 (Receitas/Despesas)
                                 Deduz automaticamente o resultado líquido do I355
                                 da conta PL para que D = C.
                                 Permite encerrar as despesas/receitas no sistema destino.

    Retorna:
        resultado_bytes : bytes  — arquivo gerado (utf-8-sig)
        resumo          : dict   — métricas do lançamento
        erros_out       : list   — erros de balanceamento
    """
    data_ref    = parsed["data_ref"]
    saldos_pat  = parsed["saldos_i155_pat"]
    saldos_i355 = parsed["saldos_i355"]

    log.append(f"  Modo               : {modo}")

    # ── Modo 1: Apenas Patrimonial ────────────────────────────────────────────
    if modo == "apenas_patrimonial":
        todos_saldos = dict(saldos_pat)
        log.append(f"  Contas incluídas   : {len(todos_saldos):,} (somente patrimoniais)")

    # ── Modo 2: Aberto com Resultado ─────────────────────────────────────────
    elif modo == "aberto_com_resultado":

        if not saldos_i355:
            log.append(
                "  AVISO: Nenhum registro I355 encontrado — "
                "usando apenas patrimonial."
            )
            todos_saldos = dict(saldos_pat)

        elif not conta_pl_resultado:
            log.append(
                "  ERRO: Conta de PL/Resultado não informada — "
                "usando apenas patrimonial."
            )
            todos_saldos = dict(saldos_pat)

        else:
            res_liq, dc_res = _calcular_resultado_liquido_i355(saldos_i355)
            total_rec = round(
                sum(v for _, (v, dc) in saldos_i355.items() if dc == "C"), 2
            )
            total_des = round(
                sum(v for _, (v, dc) in saldos_i355.items() if dc == "D"), 2
            )
            log.append(f"  I355 — Receitas    : R$ {total_rec:,.2f}")
            log.append(f"  I355 — Despesas    : R$ {total_des:,.2f}")
            log.append(
                f"  Resultado líquido  : R$ {res_liq:,.2f} "
                f"({'Superávit' if dc_res == 'C' else 'Déficit'})"
            )

            # Começa com o patrimonial
            todos_saldos = dict(saldos_pat)

            if conta_pl_resultado in todos_saldos:
                saldo_pl, dc_pl = todos_saldos[conta_pl_resultado]
                log.append(
                    f"  Conta PL           : {conta_pl_resultado} | "
                    f"Saldo original: R$ {saldo_pl:,.2f} {dc_pl}"
                )

                # Retira o resultado líquido da conta PL para "reabrir" via I355
                # A lógica: se PL é credor e resultado é superávit, subtrai
                if dc_pl == "C" and dc_res == "C":
                    novo_saldo = round(saldo_pl - res_liq, 2)
                elif dc_pl == "D" and dc_res == "D":
                    novo_saldo = round(saldo_pl - res_liq, 2)
                elif dc_pl == "C" and dc_res == "D":
                    novo_saldo = round(saldo_pl + res_liq, 2)
                else:   # dc_pl == "D" e dc_res == "C"
                    novo_saldo = round(saldo_pl + res_liq, 2)

                if novo_saldo >= 0:
                    todos_saldos[conta_pl_resultado] = (novo_saldo, dc_pl)
                else:
                    # Saldo inverteu o sinal
                    dc_inv = "D" if dc_pl == "C" else "C"
                    todos_saldos[conta_pl_resultado] = (abs(novo_saldo), dc_inv)

                novo_v, novo_dc = todos_saldos[conta_pl_resultado]
                log.append(
                    f"  Conta PL ajustada  : R$ {novo_v:,.2f} {novo_dc} "
                    f"(resultado de R$ {res_liq:,.2f} retirado para reabrir via I355)"
                )
            else:
                log.append(
                    f"  AVISO: Conta {conta_pl_resultado} não encontrada no I155 — "
                    f"balanço pode não fechar."
                )

            # Inclui as contas de resultado abertas (I355)
            for cta, (v, dc) in saldos_i355.items():
                todos_saldos[cta] = (v, dc)

            log.append(
                f"  Contas incluídas   : {len(todos_saldos):,} "
                f"(patrimonial + {len(saldos_i355):,} contas de resultado abertas)"
            )

    else:
        todos_saldos = dict(saldos_pat)
        log.append("  Modo inválido — usando apenas_patrimonial.")

    # ── Remove saldos zerados ─────────────────────────────────────────────────
    todos_saldos = {
        cta: (v, dc)
        for cta, (v, dc) in todos_saldos.items()
        if abs(v) > 1e-6
    }

    if not todos_saldos:
        log.append("  AVISO: Nenhum saldo diferente de zero encontrado.")
        return b"", {}, []

    # ── Separa débitos e créditos ─────────────────────────────────────────────
    debs  = sorted(
        [(cta, v, dc) for cta, (v, dc) in todos_saldos.items() if dc == "D"],
        key=lambda x: x[0]
    )
    creds = sorted(
        [(cta, v, dc) for cta, (v, dc) in todos_saldos.items() if dc == "C"],
        key=lambda x: x[0]
    )

    total_deb  = round(sum(v for _, v, _ in debs),  2)
    total_cred = round(sum(v for _, v, _ in creds), 2)
    diferenca  = round(abs(total_deb - total_cred),  2)
    balanceado = diferenca < TOL_VALOR

    log.append(f"  Partidas débito    : {len(debs):,}  → R$ {total_deb:,.2f}")
    log.append(f"  Partidas crédito   : {len(creds):,}  → R$ {total_cred:,.2f}")
    log.append(f"  Diferença          : R$ {diferenca:,.2f}")
    log.append(
        f"  Balanceado         : "
        f"{'SIM ✅' if balanceado else 'NAO ⚠ — verifique a conta PL informada'}"
    )

    # ── Gera o arquivo ────────────────────────────────────────────────────────
    buf = io.StringIO()
    buf.write(fmt_reg_0000(ni) + "\n")

    nd = len(debs); nc = len(creds)
    if   nd == 1 and nc == 1: tp = "X"
    elif nd == 1 and nc > 1:  tp = "D"
    elif nd > 1  and nc == 1: tp = "C"
    else:                     tp = "V"

    buf.write(fmt_reg_6000(tp) + "\n")

    def _hist(cta: str) -> str:
        """Monta o histórico do lançamento de saldo inicial."""
        prefixo = (historico_prefixo or "SALDO INICIAL").strip()
        return _norm_hist(f"{prefixo} {cta}")[:250]

    # ── Tipo X — 1 débito × 1 crédito ────────────────────────────────────────
    if tp == "X":
        cta_d, v_d, _ = debs[0]
        cta_c, v_c, _ = creds[0]
        buf.write(
            fmt_reg_6100(
                data_ref, cta_d, cta_c,
                round((v_d + v_c) / 2, 2), "", _hist(cta_d)
            ) + "\n"
        )

    # ── Tipo D — 1 débito × N créditos ───────────────────────────────────────
    elif tp == "D":
        cta_d, v_d, _ = debs[0]
        buf.write(fmt_reg_6100(data_ref, cta_d, "", v_d, "", _hist(cta_d)) + "\n")
        for cta_c, v_c, _ in creds:
            buf.write(fmt_reg_6100(data_ref, "", cta_c, v_c, "", _hist(cta_c)) + "\n")

    # ── Tipo C — N débitos × 1 crédito ───────────────────────────────────────
    elif tp == "C":
        cta_c, v_c, _ = creds[0]
        buf.write(fmt_reg_6100(data_ref, "", cta_c, v_c, "", _hist(cta_c)) + "\n")
        for cta_d, v_d, _ in debs:
            buf.write(fmt_reg_6100(data_ref, cta_d, "", v_d, "", _hist(cta_d)) + "\n")

    # ── Tipo V — N débitos × N créditos ──────────────────────────────────────
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
        "data":          data_ref,
        "total_debito":  total_deb,
        "total_credito": total_cred,
        "diferenca":     diferenca,
        "balanceado":    balanceado,
        "qtd_debs":      nd,
        "qtd_creds":     nc,
        "tipo":          tp,
        "n6100":         n6100,
        "contas_i155":   len(saldos_pat),
        "contas_i355":   len(saldos_i355),
        "modo":          modo,
    }

    erros_out = []
    if not balanceado:
        erros_out.append({
            "linha":    0,
            "motivo":   (
                f"Lançamento desbalanceado: dif. R$ {diferenca:,.2f} "
                f"(D={total_deb:,.2f} / C={total_cred:,.2f}). "
                f"Verifique se a conta de PL/Resultado informada está correta."
            ),
            "conteudo": "",
        })

    return resultado_bytes, resumo, erros_out


# ═══════════════════════════════════════════════════════════════════════════════
# PRÉ-SCAN RÁPIDO — SUGESTÃO DA CONTA PL SEM PROCESSAR O ARQUIVO INTEIRO
# ═══════════════════════════════════════════════════════════════════════════════

def _pre_scan_conta_pl_sugerida(conteudo: bytes) -> None:
    """
    Lê apenas I050, I150, I155 e I355 para sugerir a conta PL
    sem precisar processar o arquivo completo.

    Grava o resultado diretamente no st.session_state:
        conta_pl_sugerida      : str
        conta_pl_sugerida_nome : str
    """
    log_tmp = []
    enc = _detectar_encoding_bytes(conteudo)

    try:
        texto = conteudo.decode(enc, errors="replace")
    except Exception:
        texto = conteudo.decode("utf-8", errors="replace")

    contas_pl_candidatas: list = []
    saldos_i355:          dict = {}
    mapa_nome_cta:        dict = {}
    i155_por_periodo:     dict = {}
    periodo_atual_idx           = -1

    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue

        campos = _split_pipe(linha)
        if not campos:
            continue

        reg = campos[0]

        if reg == "I050":
            if len(campos) < 6:
                continue
            cod_nat  = _campo(campos, 2).strip()
            ind_cta  = _campo(campos, 3).strip().upper()
            cod_cta  = _campo(campos, 5).strip()
            nome_cta = _campo(campos, 7).strip() if len(campos) > 7 else ""

            if not cod_cta:
                continue

            mapa_nome_cta[cod_cta] = nome_cta

            eh_resultado_nat  = cod_nat in _NAT_RESULTADO
            nome_up           = nome_cta.upper()
            eh_resultado_nome = any(p in nome_up for p in _PALAVRAS_RESULTADO)

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
            if periodo_atual_idx < 0:
                continue
            cod_cta = _campo(campos, 1).strip()
            vl_fin  = _campo(campos, 7).strip()
            ind_dc  = _campo(campos, 8).strip().upper()
            if not cod_cta:
                continue
            if ind_dc not in ("D", "C"):
                ind_dc = "D"
            try:
                valor_f = _str2float(vl_fin)
            except Exception:
                valor_f = 0.0
            i155_por_periodo[periodo_atual_idx][cod_cta] = (valor_f, ind_dc)

        elif reg == "I355":
            cod_cta = _campo(campos, 1).strip()
            vl_cta  = _campo(campos, 3).strip()
            ind_dc  = _campo(campos, 4).strip().upper()
            if not cod_cta:
                continue
            if ind_dc not in ("D", "C"):
                ind_dc = "D"
            try:
                valor_f = _str2float(vl_cta)
            except Exception:
                valor_f = 0.0
            saldos_i355[cod_cta] = (valor_f, ind_dc)

    # Pega saldos do último período I155
    saldos_i155_raw: dict = {}
    if i155_por_periodo:
        ultimo_idx      = max(i155_por_periodo.keys())
        saldos_i155_raw = i155_por_periodo[ultimo_idx]

    # Calcula resultado líquido do I355
    total_rec        = sum(v for v, dc in saldos_i355.values() if dc == "C")
    total_des        = sum(v for v, dc in saldos_i355.values() if dc == "D")
    resultado_liq    = round(abs(total_rec - total_des), 2)

    # Sugere e grava no session_state
    sugerida = _sugerir_conta_pl(
        contas_pl_candidatas, saldos_i155_raw, resultado_liq, log_tmp
    )

    if sugerida:
        st.session_state["conta_pl_sugerida"]      = sugerida
        st.session_state["conta_pl_sugerida_nome"] = mapa_nome_cta.get(sugerida, "")


# ═══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA DO MÓDULO SALDO INICIAL
# ═══════════════════════════════════════════════════════════════════════════════

def processar_saldo_inicial_ecd(conteudo: bytes,
                                 ni: str,
                                 historico_prefixo: str,
                                 modo: str,
                                 conta_pl_resultado: str,
                                 log: list,
                                 prog_bar,
                                 status) -> tuple:
    """
    Ponto de entrada do módulo Saldo Inicial V3.6.2.

    Fluxo:
        1. _parse_saldo_inicial_ecd() → lê I050, I150, I155, I355
        2. _gerar_saldo_inicial_dominio() → gera 0000 + 6000 + 6100
        3. Retorna (resultado_bytes, metricas, todos_erros)

    Parâmetros:
        conteudo           : bytes do arquivo SPED ECD
        ni                 : CNPJ/CPF limpo (14 ou 11 dígitos)
        historico_prefixo  : str — prefixo do histórico (ex: "SALDO INICIAL")
        modo               : "apenas_patrimonial" | "aberto_com_resultado"
        conta_pl_resultado : str — código da conta PL (pode ser "")
        log                : list para log
        prog_bar           : widget st.progress
        status             : widget st.empty

    Retorna:
        resultado_bytes : bytes  — arquivo gerado (utf-8-sig)
        metricas        : dict   — métricas para exibição
        todos_erros     : list   — erros de parse + balanceamento
    """
    status.text("Lendo SPED ECD — extraindo saldos (I155 + I355)...")
    prog_bar.progress(10)
    log.append("── PARSE SALDO INICIAL (ECD) V3.6.2 ──")

    parsed = _parse_saldo_inicial_ecd(conteudo, log)

    # Atualiza session_state com a sugestão de conta PL
    conta_pl_sugerida = parsed.get("conta_pl_sugerida", "")
    if conta_pl_sugerida:
        nome_pl = parsed.get("mapa_nome_cta", {}).get(conta_pl_sugerida, "")
        st.session_state["conta_pl_sugerida"]      = conta_pl_sugerida
        st.session_state["conta_pl_sugerida_nome"] = nome_pl

    # Usa CNPJ do arquivo se ni não foi informado
    cnpj_uso = ni if ni else parsed["cnpj"]
    if not cnpj_uso:
        log.append("ERRO: CNPJ não encontrado.")
        return b"", {}, [{"linha": 0, "motivo": "CNPJ não encontrado", "conteudo": ""}]

    prog_bar.progress(50)
    status.text("Gerando lançamento único de saldo inicial...")
    log.append("\n── GERAÇÃO ──")

    resultado_bytes, resumo, erros_ger = _gerar_saldo_inicial_dominio(
        parsed, cnpj_uso, historico_prefixo, modo, conta_pl_resultado, log
    )

    todos_erros = parsed["erros"] + erros_ger
    prog_bar.progress(90)

    n6100 = resultado_bytes.count(b"|6100|") if resultado_bytes else 0

    metricas = {
        "CNPJ / CPF":      cnpj_uso,
        "Data referência": resumo.get("data", ""),
        "Modo":            (
            "Patrimonial"
            if modo == "apenas_patrimonial"
            else "Aberto+Resultado"
        ),
        "Contas I155":     f"{resumo.get('contas_i155', 0):,}",
        "Contas I355":     f"{resumo.get('contas_i355', 0):,}",
        "Partidas D":      f"{resumo.get('qtd_debs', 0):,}",
        "Partidas C":      f"{resumo.get('qtd_creds', 0):,}",
        "Tipo":            resumo.get("tipo", "-"),
        "Reg. 6100":       f"{n6100:,}",
        "Balanceado":      "SIM" if resumo.get("balanceado") else "NAO",
        "Tamanho":         f"{len(resultado_bytes) / 1024:.1f} KB",
    }

    prog_bar.progress(100)
    status.text("Concluído!")

    return resultado_bytes, metricas, todos_erros

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 6 — MÓDULO TXT STREAMING (lote separado por ";")
# Integra:
#   • _filtrar_chunk()         — filtra linhas inválidas do chunk pandas
#   • ler_txt_streaming()      — lê o arquivo em chunks via pandas
#   • diagnosticar_lote()      — diagnóstico de lotes desbalanceados
#   • _gerar_linhas_6100()     — gera as linhas 6100 por tipo (X/D/C/V)
#   • _flush_lote()            — processa e grava um lote completo
#   • _flush_lote_normal()     — processa lotes sem linhas "ambos"
#   • processar_streaming()    — ponto de entrada do módulo
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# FILTRO DE CHUNK — remove linhas inválidas do DataFrame pandas
# ═══════════════════════════════════════════════════════════════════════════════

def _filtrar_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra e normaliza um chunk lido do arquivo TXT separado por ';'.

    Critérios de inclusão (linha deve satisfazer TODOS):
        1. Data válida (parseável pelo pandas)
        2. Pelo menos uma conta (débito OU crédito) preenchida
        3. Valor não vazio

    Também:
        - Garante que todas as colunas COLS_PADRAO existam (preenche com "")
        - Normaliza a coluna "Inicia Lote" — mantém apenas valores numéricos > 0

    Retorna DataFrame filtrado (cópia).
    """
    # Garante que todas as colunas existam
    for c in COLS_PADRAO:
        if c not in chunk.columns:
            chunk[c] = ""

    # Normaliza todas as colunas como string sem espaços extras
    for c in COLS_PADRAO:
        chunk[c] = chunk[c].fillna("").astype(str).str.strip()

    # Normaliza "Inicia Lote" — mantém apenas inteiros positivos
    il = chunk["Inicia Lote"].str.strip()
    chunk["Inicia Lote"] = il.where(il.str.fullmatch(r"[1-9]\d*"), "")

    # Máscara: data válida
    m_data = chunk["Data"] != ""
    datas  = pd.to_datetime(
        chunk.loc[m_data, "Data"], dayfirst=True, errors="coerce"
    )
    m_dv        = m_data.copy()
    m_dv[m_data] = datas.notna()

    # Máscara: pelo menos uma conta preenchida
    m_conta = (
        (chunk["Cód. Conta Debito"]  != "") |
        (chunk["Cód. Conta Credito"] != "")
    )

    # Máscara: valor não vazio
    m_valor = chunk["Valor"].str.strip() != ""

    return chunk[m_dv & m_conta & m_valor].copy()


# ═══════════════════════════════════════════════════════════════════════════════
# LEITURA EM STREAMING — gerador de chunks pandas
# ═══════════════════════════════════════════════════════════════════════════════

def ler_txt_streaming(conteudo: bytes):
    """
    Lê o arquivo TXT separado por ';' em chunks de CHUNK_SIZE linhas.

    Usa pandas.read_csv com chunksize para evitar carregar o arquivo
    inteiro em memória — adequado para arquivos de centenas de MB.

    Adiciona a coluna "_linha_origem" com o número da linha original
    no arquivo (base 1), para rastreabilidade nos erros.

    Yields:
        (chunk_filtrado: pd.DataFrame, encoding: str)

    Só faz yield se o chunk filtrado tiver pelo menos 1 linha válida.
    """
    enc = _detectar_encoding_bytes(conteudo)
    buf = io.BytesIO(conteudo)

    reader = pd.read_csv(
        buf,
        sep=";",
        header=None,
        names=COLS_PADRAO,
        dtype=str,
        encoding=enc,
        on_bad_lines="skip",    # pula linhas malformadas
        engine="c",             # engine C é mais rápido
        usecols=range(len(COLS_PADRAO)),
        chunksize=CHUNK_SIZE,
    )

    linha_at = 0

    for chunk in reader:
        n = len(chunk)

        # Adiciona número da linha original no arquivo
        chunk["_linha_origem"] = np.arange(
            linha_at + 1, linha_at + n + 1, dtype=np.int32
        )
        linha_at += n

        filtrado = _filtrar_chunk(chunk)
        del chunk

        if len(filtrado) > 0:
            yield filtrado, enc

        del filtrado


# ═══════════════════════════════════════════════════════════════════════════════
# DIAGNÓSTICO DE LOTES DESBALANCEADOS
# ═══════════════════════════════════════════════════════════════════════════════

def diagnosticar_lote(W: pd.DataFrame, dif: float) -> dict:
    """
    Gera um diagnóstico detalhado para um lote desbalanceado.

    Tenta identificar a(s) linha(s) suspeita(s) que causam o desequilíbrio:
        1. Procura linha cujo valor seja exatamente igual à diferença
        2. Procura linha cuja remoção zeraria o desequilíbrio

    Parâmetros:
        W   : DataFrame do lote (com colunas td, tc, vf, cd, cc, dt, desc, lo)
        dif : diferença absoluta entre total débito e total crédito

    Retorna dict com:
        total_debito    : float
        total_credito   : float
        diferenca       : float
        qtd_debitos     : int
        qtd_creditos    : int
        linhas          : list[dict] — detalhe de cada linha do lote
        suspeitas       : list[dict] — linhas candidatas ao erro
        sugestao        : str        — texto explicativo
    """
    debs  = W[W["td"]].copy()
    creds = W[W["tc"]].copy()

    td = round(float(debs["vf"].sum()),  2)
    tc = round(float(creds["vf"].sum()), 2)

    # Monta detalhe linha a linha
    linhas_det = []
    for _, r in W.iterrows():
        linhas_det.append({
            "linha_origem":  int(r["lo"]),
            "data":          formatar_data(r["dt"]),
            "conta_debito":  str(r["cd"]) if r["td"] else "",
            "conta_credito": str(r["cc"]) if r["tc"] else "",
            "valor":         float(r["vf"]),
            "descricao":     _norm_hist(str(r["desc"]))[:70],
            "tipo":          "D" if r["td"] else "C",
        })

    suspeitas = []
    dif_abs   = abs(dif)

    # Critério 1: valor == diferença
    for r in linhas_det:
        if abs(r["valor"] - dif_abs) < TOL_VALOR:
            suspeitas.append({
                **r,
                "motivo": f"Valor R$ {r['valor']:.2f} igual à diferença",
            })

    # Critério 2: remoção zeraria o lote
    if not suspeitas:
        for r in linhas_det:
            v = r["valor"]
            if r["tipo"] == "D":
                if abs(round(td - v, 2) - tc) < TOL_VALOR:
                    suspeitas.append({
                        **r,
                        "motivo": f"Remover DÉBITO R$ {v:.2f} zeraria o lote",
                    })
            else:
                if abs(td - round(tc - v, 2)) < TOL_VALOR:
                    suspeitas.append({
                        **r,
                        "motivo": f"Remover CRÉDITO R$ {v:.2f} zeraria o lote",
                    })

    sugestao = (
        f"Débito excede crédito em R$ {dif_abs:.2f}."
        if td > tc
        else f"Crédito excede débito em R$ {dif_abs:.2f}."
    )

    return {
        "total_debito":  td,
        "total_credito": tc,
        "diferenca":     dif_abs,
        "qtd_debitos":   len(debs),
        "qtd_creditos":  len(creds),
        "linhas":        linhas_det,
        "suspeitas":     suspeitas,
        "sugestao":      sugestao,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DAS LINHAS 6100 POR TIPO DE LANÇAMENTO
# ═══════════════════════════════════════════════════════════════════════════════

def _gerar_linhas_6100(debs: pd.DataFrame,
                       creds: pd.DataFrame,
                       tp: str) -> list:
    """
    Gera as linhas |6100| de um lote balanceado, respeitando o tipo
    de lançamento (X / D / C / V).

    Parâmetros:
        debs  : DataFrame com as linhas de débito do lote
        creds : DataFrame com as linhas de crédito do lote
        tp    : "X" | "D" | "C" | "V"

    Retorna list[str] com as linhas 6100 prontas para escrita.
    """
    out = []

    # ── Tipo X — 1 débito × 1 crédito ────────────────────────────────────────
    if tp == "X":
        rd = debs.iloc[0]
        rc = creds.iloc[0]
        out.append(fmt_reg_6100(
            formatar_data(rd["dt"]),
            str(rd["cd"]),
            str(rc["cc"]),
            float(rd["vf"]),
            "",
            _norm_hist(str(rd["desc"]) or str(rc["desc"])),
        ))

    # ── Tipo D — 1 débito × N créditos ───────────────────────────────────────
    elif tp == "D":
        rd = debs.iloc[0]
        # Linha de débito
        out.append(fmt_reg_6100(
            formatar_data(rd["dt"]),
            str(rd["cd"]), "",
            float(rd["vf"]),
            "",
            _norm_hist(str(rd["desc"])),
        ))
        # Linhas de crédito
        for _, rc in creds.iterrows():
            out.append(fmt_reg_6100(
                formatar_data(rd["dt"]),
                "", str(rc["cc"]),
                float(rc["vf"]),
                "",
                _norm_hist(str(rc["desc"]) or str(rd["desc"])),
            ))

    # ── Tipo C — N débitos × 1 crédito ───────────────────────────────────────
    elif tp == "C":
        rc = creds.iloc[0]
        # Linha de crédito
        out.append(fmt_reg_6100(
            formatar_data(debs.iloc[0]["dt"]),
            "", str(rc["cc"]),
            float(rc["vf"]),
            "",
            _norm_hist(str(rc["desc"])),
        ))
        # Linhas de débito
        for _, rd in debs.iterrows():
            out.append(fmt_reg_6100(
                formatar_data(rd["dt"]),
                str(rd["cd"]), "",
                float(rd["vf"]),
                "",
                _norm_hist(str(rd["desc"]) or str(rc["desc"])),
            ))

    # ── Tipo V — N débitos × N créditos ──────────────────────────────────────
    else:
        for _, rc in creds.iterrows():
            out.append(fmt_reg_6100(
                formatar_data(rc["dt"]),
                "", str(rc["cc"]),
                float(rc["vf"]),
                "",
                _norm_hist(str(rc["desc"])),
            ))
        for _, rd in debs.iterrows():
            out.append(fmt_reg_6100(
                formatar_data(rd["dt"]),
                str(rd["cd"]), "",
                float(rd["vf"]),
                "",
                _norm_hist(str(rd["desc"])),
            ))

    return out


# ═══════════════════════════════════════════════════════════════════════════════
# FLUSH DE LOTE — processa e grava um lote completo
# ═══════════════════════════════════════════════════════════════════════════════

def _flush_lote(df_lote: pd.DataFrame,
                num: int,
                saida_buf: io.StringIO,
                resumo: list,
                erros: list) -> None:
    """
    Processa um lote completo e grava as linhas no buffer de saída.

    Trata três casos:
        1. Todas as linhas têm débito E crédito ("ambos") →
           cada linha vira um lançamento X independente
        2. Algumas linhas têm "ambos", outras não →
           as "ambos" viram X individuais; o restante vai para _flush_lote_normal
        3. Nenhuma linha tem "ambos" →
           passa diretamente para _flush_lote_normal

    Parâmetros:
        df_lote   : DataFrame com as linhas do lote
        num       : número sequencial do lote
        saida_buf : StringIO onde as linhas são escritas
        resumo    : list acumuladora de métricas por lote
        erros     : list acumuladora de lotes com erro
    """
    if df_lote is None or len(df_lote) == 0:
        return

    # ── Vetorização numpy para performance ───────────────────────────────────
    v_float   = limpar_valor_vec(df_lote["Valor"])
    cd_arr    = limpar_contas_vec(df_lote["Cód. Conta Debito"])
    cc_arr    = limpar_contas_vec(df_lote["Cód. Conta Credito"])
    td_arr    = cd_arr != ""          # tem débito
    tc_arr    = cc_arr != ""          # tem crédito
    ambos_arr = td_arr & tc_arr       # tem débito E crédito na mesma linha

    vd_arr  = np.where(td_arr, v_float, 0.0)
    vc_arr  = np.where(tc_arr, v_float, 0.0)
    dt_arr  = df_lote["Data"].fillna("").astype(str).to_numpy()
    desc_arr = df_lote["Complemento Histórico"].fillna("").astype(str).to_numpy(dtype=object)

    # Normaliza históricos
    for i in range(len(desc_arr)):
        desc_arr[i] = _norm_hist(str(desc_arr[i]))

    lo_arr = df_lote["_linha_origem"].fillna(0).astype(int).to_numpy(dtype=np.int32)

    # Monta DataFrame de trabalho
    W = pd.DataFrame({
        "nl":    num,
        "lo":    lo_arr,
        "vd":    vd_arr,
        "vc":    vc_arr,
        "vf":    v_float,
        "cd":    cd_arr,
        "cc":    cc_arr,
        "td":    td_arr,
        "tc":    tc_arr,
        "ambos": ambos_arr,
        "dt":    dt_arr,
        "desc":  desc_arr,
    })

    lm    = int(lo_arr.min()) if len(lo_arr) else 0
    lx    = int(lo_arr.max()) if len(lo_arr) else 0
    fx    = f"{lm}–{lx}" if lm != lx else str(lm)
    dt_fmt = formatar_data(dt_arr[0]) if len(dt_arr) else ""

    # ── Caso 1: todas as linhas têm débito E crédito ──────────────────────────
    if ambos_arr.all():
        for _, row in W.iterrows():
            desc  = _norm_hist(str(row["desc"]))
            dt_l  = formatar_data(str(row["dt"]))
            vf    = float(row["vf"])

            saida_buf.write(fmt_reg_6000("X") + "\n")
            saida_buf.write(
                fmt_reg_6100(dt_l, str(row["cd"]), str(row["cc"]), vf, "", desc) + "\n"
            )
            resumo.append({
                "num_lote":      num,
                "data":          dt_l,
                "descricao":     desc,
                "total_debito":  vf,
                "total_credito": vf,
                "diferenca":     0.0,
                "balanceado":    True,
                "qtd_linhas":    1,
                "faixa_linhas":  str(int(row["lo"])),
                "diagnostico":   {},
            })
        del W
        return

    # ── Caso 2: algumas linhas têm "ambos" ────────────────────────────────────
    if ambos_arr.any():
        for _, row in W[W["ambos"]].iterrows():
            desc  = _norm_hist(str(row["desc"]))
            dt_l  = formatar_data(str(row["dt"]))
            vf    = float(row["vf"])

            saida_buf.write(fmt_reg_6000("X") + "\n")
            saida_buf.write(
                fmt_reg_6100(dt_l, str(row["cd"]), str(row["cc"]), vf, "", desc) + "\n"
            )
            resumo.append({
                "num_lote":      num,
                "data":          dt_l,
                "descricao":     desc,
                "total_debito":  vf,
                "total_credito": vf,
                "diferenca":     0.0,
                "balanceado":    True,
                "qtd_linhas":    1,
                "faixa_linhas":  str(int(row["lo"])),
                "diagnostico":   {},
            })

        # Processa o restante (linhas sem "ambos") normalmente
        W_resto = W[~W["ambos"]].reset_index(drop=True)
        if len(W_resto) > 0:
            _flush_lote_normal(W_resto, num, saida_buf, resumo, erros, fx, dt_fmt)

        del W
        return

    # ── Caso 3: nenhuma linha tem "ambos" ─────────────────────────────────────
    _flush_lote_normal(W, num, saida_buf, resumo, erros, fx, dt_fmt)
    del W


# ═══════════════════════════════════════════════════════════════════════════════
# FLUSH NORMAL — lotes sem linhas "ambos"
# ═══════════════════════════════════════════════════════════════════════════════

def _flush_lote_normal(W: pd.DataFrame,
                       num: int,
                       saida_buf: io.StringIO,
                       resumo: list,
                       erros: list,
                       fx: str,
                       dt_fmt: str) -> None:
    """
    Processa um lote onde cada linha tem apenas débito OU crédito
    (sem a combinação "ambos").

    Fluxo:
        1. Calcula total débito e total crédito
        2. Verifica balanceamento (diferença < TOL_VALOR)
        3. Se balanceado → classifica o tipo (X/D/C/V) e grava 6000 + 6100
        4. Se desbalanceado → executa diagnóstico e registra em erros

    Parâmetros:
        W         : DataFrame de trabalho do lote
        num       : número sequencial do lote
        saida_buf : StringIO de saída
        resumo    : list acumuladora de métricas
        erros     : list acumuladora de erros
        fx        : string da faixa de linhas (ex: "10–25")
        dt_fmt    : data formatada do lote (DD/MM/YYYY)
    """
    td_arr   = W["td"].to_numpy()
    tc_arr   = W["tc"].to_numpy()
    vd_arr   = W["vd"].to_numpy()
    vc_arr   = W["vc"].to_numpy()
    desc_arr = W["desc"].to_numpy()

    td_sum = round(float(vd_arr[td_arr].sum()), 2)
    tc_sum = round(float(vc_arr[tc_arr].sum()), 2)
    dif    = round(abs(td_sum - tc_sum), 2)
    ok     = dif < TOL_VALOR

    entrada = {
        "num_lote":      num,
        "data":          dt_fmt,
        "descricao":     _norm_hist(str(desc_arr[0])) if len(desc_arr) else "",
        "total_debito":  td_sum,
        "total_credito": tc_sum,
        "diferenca":     dif,
        "balanceado":    ok,
        "qtd_linhas":    len(W),
        "faixa_linhas":  fx,
        "diagnostico":   {},
    }

    if not ok:
        # Lote desbalanceado — diagnóstico e registro de erro
        entrada["diagnostico"] = diagnosticar_lote(W, dif)
        erros.append(entrada)

    else:
        # Lote balanceado — gera 6000 + 6100
        debs  = W[W["td"]].reset_index(drop=True)
        creds = W[W["tc"]].reset_index(drop=True)

        if len(debs) > 0 and len(creds) > 0:
            tp         = tipo_lancamento(len(debs), len(creds))
            linhas_out = [fmt_reg_6000(tp)] + _gerar_linhas_6100(debs, creds, tp)
            saida_buf.write("\n".join(linhas_out) + "\n")

    resumo.append(entrada)


# ═══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA DO MÓDULO TXT STREAMING
# ═══════════════════════════════════════════════════════════════════════════════

def processar_streaming(conteudo: bytes,
                        ni: str,
                        log: list) -> tuple:
    """
    Ponto de entrada do módulo TXT Streaming.

    Lê o arquivo TXT separado por ';' em chunks e processa cada lote,
    gerando o arquivo de saída no leiaute Domínio (0000 + 6000 + 6100).

    Estratégia de agrupamento de lotes:
        A. Se a coluna "Inicia Lote" tiver valores → usa como marcador de início
        B. Se todas as linhas tiverem débito E crédito → cada linha é um lote X
        C. Se algumas linhas tiverem "ambos" → usa mudança de chave + flag "ambos"
        D. Fallback → agrupa por mudança de Data + Complemento Histórico

    Parâmetros:
        conteudo : bytes do arquivo TXT
        ni       : CNPJ/CPF limpo (14 ou 11 dígitos)
        log      : list para log

    Retorna:
        saida_bytes  : bytes  — arquivo gerado (utf-8-sig)
        resumo       : list   — métricas por lote
        erros        : list   — lotes desbalanceados
        total_lins   : int    — total de linhas válidas lidas
        ignoradas    : int    — linhas ignoradas (reservado, sempre 0 aqui)
        enc_final    : str    — encoding detectado no arquivo
    """
    saida_buf   = io.StringIO()
    saida_buf.write(fmt_reg_0000(ni) + "\n")

    pendente      = None        # chunk parcial aguardando o próximo
    num_lote_g    = 0           # contador global de lotes
    usa_inicia    = None        # None = ainda não determinado
    resumo: list  = []
    erros:  list  = []
    total_lins    = 0
    ignoradas     = 0
    enc_final     = "utf-8"
    chunk_count   = 0

    for chunk_df, enc in ler_txt_streaming(conteudo):
        enc_final    = enc
        total_lins  += len(chunk_df)
        chunk_count += 1

        # Determina na primeira iteração se o arquivo usa "Inicia Lote"
        if usa_inicia is None:
            usa_inicia = bool(
                (chunk_df["Inicia Lote"].str.strip() != "").any()
            )

        # Prepende o pendente do chunk anterior (lote partido entre chunks)
        if pendente is not None and len(pendente) > 0:
            chunk_df = pd.concat([pendente, chunk_df], ignore_index=True)
            pendente = None

        # ── Estratégia A: "Inicia Lote" ──────────────────────────────────────
        if usa_inicia:
            inicia   = chunk_df["Inicia Lote"].fillna("").astype(str).str.strip()
            marcador = (inicia != "").to_numpy(dtype=bool)
            chunk_df["_num_lote"] = (
                np.cumsum(marcador, dtype=np.int32) + num_lote_g
            )

        # ── Estratégias B / C / D ─────────────────────────────────────────────
        else:
            cd_tmp    = limpar_contas_vec(chunk_df["Cód. Conta Debito"])
            cc_tmp    = limpar_contas_vec(chunk_df["Cód. Conta Credito"])
            ambos_tmp = (cd_tmp != "") & (cc_tmp != "")

            desc = (
                chunk_df["Complemento Histórico"]
                .fillna("").astype(str)
                .str.strip()
                .str.upper()
                .str.replace(r"\s+", " ", regex=True)
            )
            chave = (
                chunk_df["Data"].fillna("").astype(str).str.strip()
                + "|||" + desc
            ).to_numpy()

            # Detecta mudança de chave (Data + Descrição)
            muda       = np.empty(len(chave), dtype=bool)
            muda[0]    = True
            muda[1:]   = chave[1:] != chave[:-1]

            # ── B: todas as linhas têm "ambos" → cada linha é um lote
            if ambos_tmp.all():
                chunk_df["_num_lote"] = np.arange(
                    num_lote_g + 1,
                    num_lote_g + len(chunk_df) + 1,
                    dtype=np.int32
                )

            # ── C: algumas linhas têm "ambos" → combina flags
            elif ambos_tmp.any():
                chunk_df["_num_lote"] = (
                    np.cumsum(muda | ambos_tmp, dtype=np.int32) + num_lote_g
                )

            # ── D: fallback → agrupa por mudança de chave
            else:
                chunk_df["_num_lote"] = (
                    np.cumsum(muda, dtype=np.int32) + num_lote_g
                )

        # ── Preserva o último lote (pode continuar no próximo chunk) ──────────
        ultimo_lote  = int(chunk_df["_num_lote"].max())
        mask_ultimo  = chunk_df["_num_lote"] == ultimo_lote
        pendente     = chunk_df[mask_ultimo].copy()
        chunk_proc   = chunk_df[~mask_ultimo]
        del chunk_df

        # ── Processa os lotes completos deste chunk ───────────────────────────
        for nl, grupo in chunk_proc.groupby("_num_lote", sort=True):
            _flush_lote(grupo, int(nl), saida_buf, resumo, erros)

        # Atualiza o contador global de lotes
        # (subtrai 1 porque o último lote pode continuar)
        num_lote_g = ultimo_lote - 1
        del chunk_proc

        # Coleta lixo a cada 5 chunks para liberar memória
        if chunk_count % 5 == 0:
            gc.collect()

    # ── Processa o lote pendente final ───────────────────────────────────────
    if pendente is not None and len(pendente) > 0:
        num_lote_g += 1
        _flush_lote(pendente, num_lote_g, saida_buf, resumo, erros)
        del pendente

    gc.collect()

    # ── Log final ─────────────────────────────────────────────────────────────
    log.append(f"  Linhas lidas      : {total_lins:,}")
    log.append(f"  Lotes processados : {len(resumo):,}")
    log.append(f"  Lotes OK          : {len(resumo) - len(erros):,}")
    log.append(f"  Lotes com erro    : {len(erros):,}")

    saida_bytes = saida_buf.getvalue().encode("utf-8-sig")
    del saida_buf

    return saida_bytes, resumo, erros, total_lins, ignoradas, enc_final

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 7 — MÓDULO EXCEL V3.7.0
# Integra:
#   • detectar_cabecalho_excel()      — detecta a linha do cabeçalho automaticamente
#   • ler_excel_lote()                — lê o arquivo Excel em DataFrame
#   • _pre_scan_filiais_excel()       — pré-scan de filiais sem processar tudo
#   • montar_lotes_excel()            — agrupa linhas em lotes por estratégia
#   • _ordenar_lotes_por_data_filial()— reordena lotes por data + filial
#   • _flush_lote_excel()             — processa um lote (com suporte a "ambos")
#   • _flush_lote_excel_normal()      — processa lotes sem linhas "ambos"
#   • processar_excel()               — ponto de entrada do módulo
# ═══════════════════════════════════════════════════════════════════════════════


# Colunas esperadas no Excel — posições 0..7 mapeadas para COLS_PADRAO[:8]
_COLS_ESP_LOW = [c.lower() for c in COLS_PADRAO[:8]]


# ═══════════════════════════════════════════════════════════════════════════════
# DETECÇÃO AUTOMÁTICA DO CABEÇALHO
# ═══════════════════════════════════════════════════════════════════════════════

def detectar_cabecalho_excel(conteudo: bytes, sheet: str) -> tuple:
    """
    Detecta automaticamente a linha do cabeçalho em um arquivo Excel.

    Estratégia:
        Lê as primeiras 25 linhas sem cabeçalho e procura a linha que
        contenha pelo menos 4 das colunas esperadas (COLS_PADRAO[:8]).
        A comparação é feita de forma case-insensitive.

    Também tenta extrair o caminho de pasta da célula [1, 6]
    (linha 2, coluna G) — convenção usada em alguns modelos Domínio.

    Parâmetros:
        conteudo : bytes do arquivo Excel
        sheet    : nome da aba (sheet) a ler

    Retorna:
        (linha_cabecalho: int, pasta: str | None)
        linha_cabecalho : índice base-0 da linha do cabeçalho
        pasta           : caminho de pasta extraído da célula [1,6] ou None
    """
    buf = io.BytesIO(conteudo)
    raw = pd.read_excel(
        buf, sheet_name=sheet, header=None, nrows=25, engine="openpyxl"
    )

    # Tenta extrair caminho de pasta da célula [1, 6]
    pasta = None
    try:
        v = str(raw.iloc[1, 6]).strip()
        if v and v.lower() not in ("nan", "none", ""):
            pasta = v
    except Exception:
        pass

    # Procura a linha do cabeçalho
    for i, row in raw.iterrows():
        vals = [str(v).strip().lower() for v in row if not eh_vazio(v)]
        if sum(1 for c in _COLS_ESP_LOW if c in vals) >= 4:
            return i, pasta

    # Fallback: linha 3 (índice base-0)
    return 3, pasta


# ═══════════════════════════════════════════════════════════════════════════════
# LEITURA DO ARQUIVO EXCEL
# ═══════════════════════════════════════════════════════════════════════════════

def ler_excel_lote(conteudo: bytes, sheet: str, linha_h: int) -> tuple:
    """
    Lê o arquivo Excel e retorna um DataFrame normalizado.

    Fluxo:
        1. Lê o arquivo inteiro sem cabeçalho (dtype=str)
        2. Garante que existam colunas suficientes (preenche com "" se faltar)
        3. Descarta as linhas acima do cabeçalho (linha_h)
        4. Renomeia as colunas para COLS_PADRAO
        5. Remove linhas completamente vazias
        6. Adiciona coluna "_linha_origem" com o número da linha original

    Parâmetros:
        conteudo : bytes do arquivo Excel
        sheet    : nome da aba
        linha_h  : índice base-0 da linha do cabeçalho

    Retorna:
        (df: pd.DataFrame, pasta: str)
        df    : DataFrame normalizado com colunas COLS_PADRAO + _linha_origem
        pasta : caminho de pasta extraído da célula [1,6] (ou "C:\\Temp")
    """
    buf = io.BytesIO(conteudo)
    raw = pd.read_excel(
        buf, sheet_name=sheet, header=None, dtype=str, engine="openpyxl"
    )

    # Tenta extrair caminho de pasta
    pasta = "C:\\Temp"
    try:
        v = str(raw.iloc[1, 6]).strip()
        if v and v.lower() not in ("nan", "none", ""):
            pasta = v
    except Exception:
        pass

    # Garante que existam colunas suficientes
    while raw.shape[1] < len(COLS_PADRAO) + 2:
        raw[raw.shape[1]] = ""

    raw.columns = range(raw.shape[1])

    # Descarta linhas de cabeçalho e metadados
    df = raw.iloc[linha_h + 1:].reset_index(drop=True).copy()
    del raw
    gc.collect()

    # Renomeia colunas para COLS_PADRAO
    df.columns = list(range(df.shape[1]))
    df = df.rename(columns={i: c for i, c in enumerate(COLS_PADRAO)})

    # Normaliza todas as colunas de texto
    _VAZIOS = {"nan", "NaN", "None", "none", ""}
    for c in COLS_PADRAO:
        if c in df.columns:
            df[c] = (
                df[c]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace(list(_VAZIOS), "")
            )

    # Remove linhas completamente vazias
    mask = ~(
        (df["Data"] == "") &
        (df["Cód. Conta Debito"] == "") &
        (df["Cód. Conta Credito"] == "") &
        (df["Valor"] == "")
    )
    df = df[mask].reset_index(drop=True).copy()

    # Adiciona número da linha original (base no arquivo, não no DataFrame)
    df["_linha_origem"] = (df.index + linha_h + 2).astype(np.int32)

    return df, pasta


# ═══════════════════════════════════════════════════════════════════════════════
# PRÉ-SCAN DE FILIAIS (sem processar o arquivo inteiro)
# ═══════════════════════════════════════════════════════════════════════════════

def _pre_scan_filiais_excel(df: pd.DataFrame) -> list:
    """
    Extrai os códigos de filial únicos presentes no DataFrame Excel.

    Usa a coluna "Código Matriz/Filial" e aplica _limpar_filial() para
    normalizar os valores (remove zeros, floats como "1.0" → "1", etc.).

    Parâmetros:
        df : DataFrame já lido pelo ler_excel_lote()

    Retorna:
        list[str] — códigos de filial únicos, ordenados numericamente
    """
    col = "Código Matriz/Filial"
    if col not in df.columns:
        return []

    filiais: set = set()
    for v in df[col].fillna("").astype(str).str.strip():
        f = _limpar_filial(v)
        if f:
            filiais.add(f)

    return sorted(filiais, key=lambda x: int(x) if x.isdigit() else x)


# ═══════════════════════════════════════════════════════════════════════════════
# MONTAGEM DE LOTES
# ═══════════════════════════════════════════════════════════════════════════════

def montar_lotes_excel(df: pd.DataFrame) -> tuple:
    """
    Agrupa as linhas do DataFrame em lotes contábeis.

    Estratégias (em ordem de prioridade):

        A. "Inicia Lote" — se a coluna tiver valores numéricos > 0,
           cada valor diferente inicia um novo lote.
           Linhas sem valor herdam o lote anterior.

        B. "ambos" — se TODAS as linhas tiverem débito E crédito,
           cada linha é um lote independente (tipo X).

        C. "ambos parcial" — se ALGUMAS linhas tiverem "ambos",
           combina mudança de chave + flag "ambos" para delimitar lotes.

        D. Fallback — agrupa por mudança de Data + Complemento Histórico.

    Parâmetros:
        df : DataFrame com colunas COLS_PADRAO + _linha_origem

    Retorna:
        (df_com_lotes: pd.DataFrame, modo: str)
        df_com_lotes : DataFrame com coluna "_num_lote" adicionada
        modo         : descrição textual da estratégia usada
    """
    R = df.copy()

    # Garante que todas as colunas existam
    for col in COLS_PADRAO + ["_linha_origem"]:
        if col not in R.columns:
            R[col] = ""

    inicia_raw = R["Inicia Lote"].fillna("").astype(str).str.strip()
    inicia_num = pd.to_numeric(inicia_raw, errors="coerce")
    tem_ini    = bool((inicia_num > 0).any())

    # ── Estratégia A: "Inicia Lote" ──────────────────────────────────────────
    if tem_ini:
        lote_atual = 0
        lote_map   = {}
        lote_ids   = []

        for v in inicia_num:
            if pd.notna(v) and v > 0:
                v_int = int(v)
                if v_int not in lote_map:
                    lote_atual += 1
                    lote_map[v_int] = lote_atual
                lote_ids.append(lote_map[v_int])
            else:
                # Linha sem marcador herda o lote atual
                lote_ids.append(lote_atual if lote_atual > 0 else 1)

        R["_num_lote"] = np.array(lote_ids, dtype=np.int32)
        modo = "Inicia Lote (agrupamento por valor)"

    # ── Estratégias B / C / D ─────────────────────────────────────────────────
    else:
        cd_tmp    = limpar_contas_vec(R["Cód. Conta Debito"])
        cc_tmp    = limpar_contas_vec(R["Cód. Conta Credito"])
        ambos_tmp = (cd_tmp != "") & (cc_tmp != "")

        # Chave de agrupamento: Data + Complemento Histórico normalizado
        desc = (
            R["Complemento Histórico"]
            .fillna("").astype(str)
            .str.strip()
            .str.upper()
            .str.replace(r"\s+", " ", regex=True)
        )
        chave = (
            R["Data"].fillna("").astype(str).str.strip()
            + "|||" + desc
        ).to_numpy()

        # Detecta mudança de chave entre linhas consecutivas
        muda       = np.empty(len(chave), dtype=bool)
        muda[0]    = True
        muda[1:]   = chave[1:] != chave[:-1]

        # ── B: todas as linhas têm "ambos" → cada linha é um lote X ─────────
        if ambos_tmp.all():
            R["_num_lote"] = np.arange(1, len(R) + 1, dtype=np.int32)
            modo = "Ambos D+C por linha (cada linha = lote X)"

        # ── C: algumas linhas têm "ambos" → combina flags ────────────────────
        elif ambos_tmp.any():
            R["_num_lote"] = np.cumsum(muda | ambos_tmp, dtype=np.int32)
            modo = "Misto D/C + ambos (combinação de flags)"

        # ── D: fallback → agrupa por mudança de chave ────────────────────────
        else:
            R["_num_lote"] = np.cumsum(muda, dtype=np.int32)
            modo = "Data + Descrição (fallback)"

    return R, modo


# ═══════════════════════════════════════════════════════════════════════════════
# REORDENAÇÃO DE LOTES POR DATA + FILIAL
# ═══════════════════════════════════════════════════════════════════════════════

def _ordenar_lotes_por_data_filial(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reordena os lotes do DataFrame por data mínima e código de filial.

    Fluxo:
        1. Para cada lote, determina a data mínima e a filial representativa
        2. Ordena os lotes por (data_min ASC, filial ASC)
        3. Reatribui números de lote sequenciais na nova ordem

    Parâmetros:
        df : DataFrame com coluna "_num_lote"

    Retorna:
        DataFrame reordenado com "_num_lote" renumerado sequencialmente.
    """
    lote_info = []

    for num_lote, grupo in df.groupby("_num_lote", sort=False):
        # Data mínima do lote
        datas    = pd.to_datetime(
            grupo["Data"].fillna("").astype(str),
            dayfirst=True, errors="coerce"
        )
        data_min = datas.min()
        if pd.isna(data_min):
            data_min = pd.Timestamp("9999-12-31")

        # Filial representativa (primeira não vazia)
        filiais         = grupo["Código Matriz/Filial"].fillna("").astype(str).str.strip()
        filiais_validas = filiais[~filiais.str.lower().isin(["", "nan", "none", "0"])]
        filial_rep      = filiais_validas.iloc[0] if len(filiais_validas) > 0 else "0"

        try:
            filial_sort = int(float(filial_rep))
        except Exception:
            filial_sort = 0

        lote_info.append({
            "_num_lote":    num_lote,
            "_sort_data":   data_min,
            "_sort_filial": filial_sort,
        })

    if not lote_info:
        return df

    df_info = (
        pd.DataFrame(lote_info)
        .sort_values(["_sort_data", "_sort_filial"], ascending=[True, True])
    )
    ordem_lotes = df_info["_num_lote"].tolist()

    # Reconstrói o DataFrame na nova ordem
    partes   = [df[df["_num_lote"] == nl] for nl in ordem_lotes]
    df_ord   = pd.concat(partes, ignore_index=True)

    # Renumera os lotes sequencialmente
    mapa_novo         = {v: i + 1 for i, v in enumerate(ordem_lotes)}
    df_ord["_num_lote"] = df_ord["_num_lote"].map(mapa_novo).astype(np.int32)

    return df_ord


# ═══════════════════════════════════════════════════════════════════════════════
# FLUSH DE LOTE EXCEL — processa e grava um lote completo
# ═══════════════════════════════════════════════════════════════════════════════

def _flush_lote_excel(df_lote: pd.DataFrame,
                      num: int,
                      saida_buf: io.StringIO,
                      resumo: list,
                      erros: list,
                      mapa_filiais: dict,
                      gerar_6110: bool) -> None:
    """
    Processa um lote Excel completo e grava as linhas no buffer de saída.

    Diferenças em relação ao _flush_lote() do módulo TXT:
        - Suporte ao campo "Código Matriz/Filial" (filial por linha)
        - Suporte ao campo "Centro de Custo Débito/Crédito" (6110)
        - Aplica mapa_filiais (De/Para de filiais) se fornecido
        - Usa _fmt_reg_6100_excel() que inclui o campo de filial

    Trata três casos:
        1. Todas as linhas têm débito E crédito ("ambos") →
           cada linha vira um lançamento X independente
        2. Algumas linhas têm "ambos" →
           as "ambos" viram X individuais; o restante vai para _flush_lote_excel_normal
        3. Nenhuma linha tem "ambos" →
           passa diretamente para _flush_lote_excel_normal

    Parâmetros:
        df_lote     : DataFrame com as linhas do lote
        num         : número sequencial do lote
        saida_buf   : StringIO onde as linhas são escritas
        resumo      : list acumuladora de métricas por lote
        erros       : list acumuladora de lotes com erro
        mapa_filiais: dict {filial_orig → filial_dest} — De/Para de filiais
        gerar_6110  : bool — se True, gera registros |6110| de centro de custo
    """
    if df_lote is None or len(df_lote) == 0:
        return

    # ── Vetorização numpy ─────────────────────────────────────────────────────
    v_float   = limpar_valor_vec(df_lote["Valor"])
    cd_arr    = limpar_contas_vec(df_lote["Cód. Conta Debito"])
    cc_arr    = limpar_contas_vec(df_lote["Cód. Conta Credito"])
    td_arr    = cd_arr != ""
    tc_arr    = cc_arr != ""
    ambos_arr = td_arr & tc_arr

    dt_arr   = df_lote["Data"].fillna("").astype(str).to_numpy()
    desc_arr = df_lote["Complemento Histórico"].fillna("").astype(str).to_numpy(dtype=object)
    lo_arr   = df_lote["_linha_origem"].fillna(0).astype(int).to_numpy(dtype=np.int32)

    # Normaliza históricos
    for i in range(len(desc_arr)):
        desc_arr[i] = _norm_hist(str(desc_arr[i]))

    # Filiais — aplica De/Para se fornecido
    fil_raw = df_lote["Código Matriz/Filial"].fillna("").astype(str).to_numpy()
    fil_arr = np.array([_limpar_filial(f) for f in fil_raw], dtype=object)
    if mapa_filiais:
        fil_arr = np.array([mapa_filiais.get(f, f) for f in fil_arr], dtype=object)

    # Centros de custo
    col_ccd = "Centro de Custo Débito"
    col_ccc = "Centro de Custo Crédito"
    ccd_raw = (
        df_lote[col_ccd].fillna("").astype(str).to_numpy()
        if col_ccd in df_lote.columns
        else np.full(len(df_lote), "", dtype=object)
    )
    ccc_raw = (
        df_lote[col_ccc].fillna("").astype(str).to_numpy()
        if col_ccc in df_lote.columns
        else np.full(len(df_lote), "", dtype=object)
    )
    ccd_arr = np.array([_limpar_cc(v) for v in ccd_raw], dtype=object)
    ccc_arr = np.array([_limpar_cc(v) for v in ccc_raw], dtype=object)

    # Faixa de linhas e data para o resumo
    lm     = int(lo_arr.min()) if len(lo_arr) else 0
    lx     = int(lo_arr.max()) if len(lo_arr) else 0
    fx     = f"{lm}–{lx}" if lm != lx else str(lm)
    dt_fmt = formatar_data(dt_arr[0]) if len(dt_arr) else ""

    # Monta DataFrame de trabalho
    W = pd.DataFrame({
        "nl":    num,
        "lo":    lo_arr,
        "vf":    v_float,
        "cd":    cd_arr,
        "cc":    cc_arr,
        "td":    td_arr,
        "tc":    tc_arr,
        "ambos": ambos_arr,
        "dt":    dt_arr,
        "desc":  desc_arr,
        "fil":   fil_arr,
        "ccd":   ccd_arr,
        "ccc":   ccc_arr,
    })

    # ── Caso 1: todas as linhas têm "ambos" ──────────────────────────────────
    if ambos_arr.all():
        for _, row in W.iterrows():
            desc = str(row["desc"])
            dt_l = formatar_data(str(row["dt"]))
            fil  = str(row["fil"])
            vf   = float(row["vf"])

            saida_buf.write(fmt_reg_6000("X") + "\n")
            saida_buf.write(
                _fmt_reg_6100_excel(dt_l, str(row["cd"]), str(row["cc"]), vf, desc, fil) + "\n"
            )

            if gerar_6110:
                v_fmt = f"{vf:.2f}".replace(".", ",")
                for l6110 in _gerar_6110_linha(str(row["ccd"]), str(row["ccc"]), v_fmt, "ambos"):
                    saida_buf.write(l6110 + "\n")

            resumo.append({
                "num_lote":      num,
                "data":          dt_l,
                "descricao":     desc,
                "total_debito":  vf,
                "total_credito": vf,
                "diferenca":     0.0,
                "balanceado":    True,
                "qtd_linhas":    1,
                "faixa_linhas":  str(int(row["lo"])),
                "diagnostico":   {},
            })

        del W
        return

    # ── Caso 2: algumas linhas têm "ambos" ───────────────────────────────────
    if ambos_arr.any():
        for _, row in W[W["ambos"]].iterrows():
            desc = str(row["desc"])
            dt_l = formatar_data(str(row["dt"]))
            fil  = str(row["fil"])
            vf   = float(row["vf"])

            saida_buf.write(fmt_reg_6000("X") + "\n")
            saida_buf.write(
                _fmt_reg_6100_excel(dt_l, str(row["cd"]), str(row["cc"]), vf, desc, fil) + "\n"
            )

            if gerar_6110:
                v_fmt = f"{vf:.2f}".replace(".", ",")
                for l6110 in _gerar_6110_linha(str(row["ccd"]), str(row["ccc"]), v_fmt, "ambos"):
                    saida_buf.write(l6110 + "\n")

            resumo.append({
                "num_lote":      num,
                "data":          dt_l,
                "descricao":     desc,
                "total_debito":  vf,
                "total_credito": vf,
                "diferenca":     0.0,
                "balanceado":    True,
                "qtd_linhas":    1,
                "faixa_linhas":  str(int(row["lo"])),
                "diagnostico":   {},
            })

        # Processa o restante normalmente
        W_resto = W[~W["ambos"]].reset_index(drop=True)
        if len(W_resto) > 0:
            _flush_lote_excel_normal(W_resto, num, saida_buf, resumo, erros, fx, dt_fmt, gerar_6110)

        del W
        return

    # ── Caso 3: nenhuma linha tem "ambos" ─────────────────────────────────────
    _flush_lote_excel_normal(W, num, saida_buf, resumo, erros, fx, dt_fmt, gerar_6110)
    del W


# ═══════════════════════════════════════════════════════════════════════════════
# FLUSH NORMAL EXCEL — lotes sem linhas "ambos"
# ═══════════════════════════════════════════════════════════════════════════════

def _flush_lote_excel_normal(W: pd.DataFrame,
                              num: int,
                              saida_buf: io.StringIO,
                              resumo: list,
                              erros: list,
                              fx: str,
                              dt_fmt: str,
                              gerar_6110: bool) -> None:
    """
    Processa um lote Excel onde cada linha tem apenas débito OU crédito.

    Fluxo:
        1. Calcula total débito e total crédito
        2. Verifica balanceamento (diferença < TOL_VALOR)
        3. Se balanceado → classifica o tipo (X/D/C/V) e grava 6000 + 6100 (+ 6110)
        4. Se desbalanceado → executa diagnóstico e registra em erros

    Diferenças em relação ao _flush_lote_normal() do módulo TXT:
        - Inclui campo "fil" (filial) em cada linha 6100
        - Inclui campos "ccd" e "ccc" (centro de custo) para o 6110
        - Usa _fmt_reg_6100_excel() em vez de fmt_reg_6100()

    Parâmetros:
        W         : DataFrame de trabalho do lote
        num       : número sequencial do lote
        saida_buf : StringIO de saída
        resumo    : list acumuladora de métricas
        erros     : list acumuladora de erros
        fx        : string da faixa de linhas (ex: "10–25")
        dt_fmt    : data formatada do lote (DD/MM/YYYY)
        gerar_6110: bool — se True, gera registros |6110|
    """
    td_arr   = W["td"].to_numpy()
    tc_arr   = W["tc"].to_numpy()
    vf_arr   = W["vf"].to_numpy()
    desc_arr = W["desc"].to_numpy()

    vd_arr  = np.where(td_arr, vf_arr, 0.0)
    vc_arr  = np.where(tc_arr, vf_arr, 0.0)
    td_sum  = round(float(vd_arr[td_arr].sum()), 2)
    tc_sum  = round(float(vc_arr[tc_arr].sum()), 2)
    dif     = round(abs(td_sum - tc_sum), 2)
    ok      = dif < TOL_VALOR

    entrada = {
        "num_lote":      num,
        "data":          dt_fmt,
        "descricao":     _norm_hist(str(desc_arr[0])) if len(desc_arr) else "",
        "total_debito":  td_sum,
        "total_credito": tc_sum,
        "diferenca":     dif,
        "balanceado":    ok,
        "qtd_linhas":    len(W),
        "faixa_linhas":  fx,
        "diagnostico":   {},
    }

    if not ok:
        # Lote desbalanceado — diagnóstico e registro de erro
        entrada["diagnostico"] = diagnosticar_lote(W, dif)
        erros.append(entrada)

    else:
        # Lote balanceado — gera 6000 + 6100 (+ 6110)
        debs  = W[W["td"]].reset_index(drop=True)
        creds = W[W["tc"]].reset_index(drop=True)

        if len(debs) > 0 and len(creds) > 0:
            tp = tipo_lancamento(len(debs), len(creds))
            saida_buf.write(fmt_reg_6000(tp) + "\n")

            def _escreve(dc: str, cc: str, v: float, h: str,
                         fil: str, ccd: str, ccc: str, dt: str) -> None:
                """Grava uma linha 6100 e opcionalmente o 6110."""
                saida_buf.write(
                    _fmt_reg_6100_excel(dt, dc, cc, v, _norm_hist(h), fil) + "\n"
                )
                if gerar_6110:
                    if dc and cc:
                        modo = "ambos"
                    elif dc:
                        modo = "deb"
                    else:
                        modo = "cred"
                    v_fmt = f"{v:.2f}".replace(".", ",")
                    for l6110 in _gerar_6110_linha(ccd, ccc, v_fmt, modo):
                        saida_buf.write(l6110 + "\n")

            # ── Tipo X — 1 débito × 1 crédito ────────────────────────────────
            if tp == "X":
                rd = debs.iloc[0]
                rc = creds.iloc[0]
                _escreve(
                    str(rd["cd"]), str(rc["cc"]),
                    float(rd["vf"]),
                    str(rd["desc"]) or str(rc["desc"]),
                    str(rd["fil"]) or str(rc["fil"]),
                    str(rd["ccd"]), str(rc["ccc"]),
                    formatar_data(str(rd["dt"]))
                )

            # ── Tipo D — 1 débito × N créditos ───────────────────────────────
            elif tp == "D":
                rd = debs.iloc[0]
                _escreve(
                    str(rd["cd"]), "",
                    float(rd["vf"]),
                    str(rd["desc"]),
                    str(rd["fil"]),
                    str(rd["ccd"]), "",
                    formatar_data(str(rd["dt"]))
                )
                for _, rc in creds.iterrows():
                    _escreve(
                        "", str(rc["cc"]),
                        float(rc["vf"]),
                        str(rc["desc"]) or str(rd["desc"]),
                        str(rc["fil"]) or str(rd["fil"]),
                        "", str(rc["ccc"]),
                        formatar_data(str(rc["dt"]))
                    )

            # ── Tipo C — N débitos × 1 crédito ───────────────────────────────
            elif tp == "C":
                rc = creds.iloc[0]
                _escreve(
                    "", str(rc["cc"]),
                    float(rc["vf"]),
                    str(rc["desc"]),
                    str(rc["fil"]),
                    "", str(rc["ccc"]),
                    formatar_data(str(rc["dt"]))
                )
                for _, rd in debs.iterrows():
                    _escreve(
                        str(rd["cd"]), "",
                        float(rd["vf"]),
                        str(rd["desc"]) or str(rc["desc"]),
                        str(rd["fil"]) or str(rc["fil"]),
                        str(rd["ccd"]), "",
                        formatar_data(str(rd["dt"]))
                    )

            # ── Tipo V — N débitos × N créditos ──────────────────────────────
            else:
                for _, rc in creds.iterrows():
                    _escreve(
                        "", str(rc["cc"]),
                        float(rc["vf"]),
                        str(rc["desc"]),
                        str(rc["fil"]),
                        "", str(rc["ccc"]),
                        formatar_data(str(rc["dt"]))
                    )
                for _, rd in debs.iterrows():
                    _escreve(
                        str(rd["cd"]), "",
                        float(rd["vf"]),
                        str(rd["desc"]),
                        str(rd["fil"]),
                        str(rd["ccd"]), "",
                        formatar_data(str(rd["dt"]))
                    )

    resumo.append(entrada)


# ═══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA DO MÓDULO EXCEL
# ═══════════════════════════════════════════════════════════════════════════════

def processar_excel(df: pd.DataFrame,
                    ni: str,
                    mapa_filiais: dict,
                    gerar_6110: bool,
                    log: list) -> tuple:
    """
    Ponto de entrada do módulo Excel.

    Itera sobre todos os lotes do DataFrame (agrupados por "_num_lote")
    e chama _flush_lote_excel() para cada um, gerando o arquivo de saída
    no leiaute Domínio: |0000| + (|6000| + |6100| [+ |6110|]) × N

    Parâmetros:
        df           : DataFrame com colunas COLS_PADRAO + _num_lote + _linha_origem
        ni           : CNPJ/CPF limpo (14 ou 11 dígitos)
        mapa_filiais : dict {filial_orig → filial_dest} — De/Para de filiais
        gerar_6110   : bool — se True, gera registros |6110|
        log          : list para log

    Retorna:
        saida_bytes : bytes  — arquivo gerado (utf-8-sig)
        resumo      : list   — métricas por lote
        erros       : list   — lotes desbalanceados
    """
    saida_buf = io.StringIO()
    saida_buf.write(fmt_reg_0000(ni) + "\n")

    resumo: list = []
    erros:  list = []

    # Processa cada lote em ordem crescente
    for nl, grupo in df.groupby("_num_lote", sort=True):
        _flush_lote_excel(
            grupo, int(nl), saida_buf, resumo, erros, mapa_filiais, gerar_6110
        )

    gc.collect()

    # Contagem de registros 6110
    n6110 = saida_buf.getvalue().count("|6110|")

    # Log
    log.append(f"  Lotes processados : {len(resumo):,}")
    log.append(f"  Lotes OK          : {len(resumo) - len(erros):,}")
    log.append(f"  Lotes com erro    : {len(erros):,}")
    if gerar_6110:
        log.append(f"  Reg. 6110 gerados : {n6110:,}")

    saida_bytes = saida_buf.getvalue().encode("utf-8-sig")
    del saida_buf

    return saida_bytes, resumo, erros

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 8 — MÓDULO TXT POSICIONAL DOMÍNIO V3.7.0
# Integra:
#   • _extrair_filial()            — extrai código de filial da posição 557:564
#   • _extrair_cc()                — normaliza código de centro de custo
#   • _posicional_para_decimal()   — converte valor posicional para float
#   • _parse_posicional()          — lê registros 01/02/03/05/08/99
#   • _aplicar_de_para()           — aplica mapa De/Para de filiais
#   • _gerar_saida_posicional()    — gera 0000 + 6000 + 6100 (+ 6110)
#   • _pre_scan_posicional()       — pré-scan de filiais sem processar tudo
#   • _pre_popular_mapa_filiais()  — popula o DataFrame do editor De/Para
#   • _widget_de_para_filiais()    — widget Streamlit de mapeamento de filiais
#   • processar_dominio_posicional() — ponto de entrada do módulo
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRAÇÃO DE FILIAL (posição fixa 557:564 do registro 03)
# ═══════════════════════════════════════════════════════════════════════════════

def _extrair_filial(linha: str) -> str:
    """
    Extrai o código de filial do registro 03 do leiaute posicional Domínio.

    Layout posicional do registro 03:
        Posição 557:564 — COD_FILIAL (7 caracteres, numérico, zero-padded)

    Retorna:
        str — código de filial normalizado (sem zeros à esquerda),
              ou "" se ausente, não numérico ou igual a zero.
    """
    if len(linha) < 564:
        return ""

    raw = linha[557:564].strip()

    if not raw or not raw.isdigit():
        return ""

    codigo = str(int(raw))
    return "" if codigo == "0" else codigo


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRAÇÃO E NORMALIZAÇÃO DE CENTRO DE CUSTO
# ═══════════════════════════════════════════════════════════════════════════════

def _extrair_cc(raw: str) -> str:
    """
    Normaliza um código de Centro de Custo lido do leiaute posicional.

    Critérios:
        - Remove espaços
        - Deve ser numérico (isdigit)
        - Remove zeros à esquerda
        - Retorna "" se vazio, não numérico ou igual a zero

    Parâmetros:
        raw : str — valor bruto lido da posição fixa

    Retorna:
        str — código normalizado ou ""
    """
    raw = raw.strip()

    if not raw or not raw.isdigit():
        return ""

    codigo = str(int(raw))
    return "" if codigo == "0" else codigo


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSÃO DE VALOR POSICIONAL PARA DECIMAL
# ═══════════════════════════════════════════════════════════════════════════════

def _posicional_para_decimal(val_raw: str) -> float:
    """
    Converte um valor no formato posicional Domínio para float.

    O leiaute posicional armazena valores sem separador decimal —
    os dois últimos dígitos são os centavos.

    Exemplos:
        "000000000012345" → 123.45
        "000000000000100" → 1.00
        "0"               → 0.0
        ""                → 0.0

    Parâmetros:
        val_raw : str — valor bruto (string de dígitos, pode ter espaços)

    Retorna:
        float — valor convertido, arredondado a 2 casas decimais.
    """
    val_raw = val_raw.strip()

    if not val_raw or not val_raw.isdigit():
        return 0.0

    # Garante pelo menos 3 dígitos para separar centavos
    val_raw = val_raw.zfill(3)

    try:
        inteiros  = int(val_raw[:-2])
        centavos  = int(val_raw[-2:])
        return round(inteiros + centavos / 100, 2)
    except Exception:
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# PARSE DO ARQUIVO POSICIONAL DOMÍNIO
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_posicional(conteudo: bytes, log: list) -> dict:
    """
    Lê o arquivo TXT Posicional Domínio e extrai:
        - Cabeçalho (registro 01)
        - Lotes/lançamentos (registro 02)
        - Partidas (registro 03)
        - Centros de custo (registro 05)
        - Totalizadores (registro 08)
        - Encerramento (registro 99)

    Layout dos registros:
        01 — Cabeçalho:
            [2:9]   COD_EMPRESA
            [9:23]  CNPJ
            [23:33] DT_INI
            [33:43] DT_FIN
            [44:46] TIPO_NOTA

        02 — Lançamento:
            [2:9]   SEQ
            [9:10]  TIPO (X/D/C/V)
            [10:20] DATA
            [20:50] USUARIO

        03 — Partida:
            [2:9]   SEQ
            [9:16]  CTA_DEB  (código conta débito)
            [16:23] CTA_CRED (código conta crédito)
            [23:38] VALOR    (posicional, sem decimal)
            [38:45] COD_HIST
            [45:557] HISTORICO
            [557:564] COD_FILIAL

        05 — Centro de Custo:
            [2:9]   SEQ
            [9:16]  CC_DEB
            [16:23] CC_CRED
            [23:38] VALOR

        08 — Totalizador (informativo, não processado)
        99 — Encerramento

    Retorna dict com:
        cabecalho           : dict — dados do registro 01
        lotes               : list[dict] — cada lote tem partidas e centros
        erros               : list[dict] — erros de parse
        filiais_encontradas : list[str]  — filiais únicas detectadas
    """
    enc = _detectar_encoding_bytes(conteudo)
    log.append(f"  Encoding detectado : {enc}")

    try:
        texto = conteudo.decode(enc, errors="replace")
    except Exception:
        texto = conteudo.decode("utf-8", errors="replace")

    linhas = texto.splitlines()
    log.append(f"  Total de linhas    : {len(linhas):,}")

    cabecalho:   dict = {}
    lotes:       list = []
    lote_atual:  dict = None
    erros:       list = []
    filiais_set: set  = set()

    cnt = {"01": 0, "02": 0, "03": 0, "05": 0, "08": 0, "99": 0, "outro": 0}

    for num_linha, linha in enumerate(linhas, 1):

        if len(linha) < 2:
            continue

        reg = linha[:2]

        try:
            # ── Registro 01 — Cabeçalho ──────────────────────────────────────
            if reg == "01":
                cnt["01"] += 1
                cabecalho = {
                    "cod_empresa": linha[2:9].strip(),
                    "cnpj":        linha[9:23].strip(),
                    "dt_ini":      linha[23:33].strip(),
                    "dt_fin":      linha[33:43].strip(),
                    "tipo_nota":   linha[44:46].strip() if len(linha) > 45 else "",
                }
                log.append(
                    f"  Cabeçalho — Empresa: {cabecalho['cod_empresa']} | "
                    f"CNPJ: {cabecalho['cnpj']} | "
                    f"Período: {cabecalho['dt_ini']} a {cabecalho['dt_fin']}"
                )

            # ── Registro 02 — Lançamento (cabeçalho do lote) ─────────────────
            elif reg == "02":
                cnt["02"] += 1

                tipo_lanc = linha[9:10].strip().upper()
                data_lanc = linha[10:20].strip()
                usuario   = linha[20:50].strip()

                # Garante tipo válido — fallback "X"
                if tipo_lanc not in ("X", "D", "C", "V"):
                    tipo_lanc = "X"

                lote_atual = {
                    "seq":      linha[2:9].strip(),
                    "tipo":     tipo_lanc,
                    "data":     data_lanc,
                    "usuario":  usuario,
                    "partidas": [],
                    "centros":  [],
                }
                lotes.append(lote_atual)

            # ── Registro 03 — Partida ─────────────────────────────────────────
            elif reg == "03":
                cnt["03"] += 1

                if lote_atual is None:
                    erros.append({
                        "linha":    num_linha,
                        "motivo":   "Registro 03 sem Registro 02 precedente",
                        "conteudo": linha[:80],
                    })
                    continue

                cta_deb  = linha[9:16].strip()
                cta_cred = linha[16:23].strip()
                val_raw  = linha[23:38].strip()
                cod_hist = linha[38:45].strip()
                historico = linha[45:557].strip() if len(linha) > 45 else ""

                filial_p = _extrair_filial(linha)
                if filial_p:
                    filiais_set.add(filial_p)

                # Normaliza contas zeradas/nulas
                if cta_deb  in ("0000000", "0", ""):
                    cta_deb  = ""
                if cta_cred in ("0000000", "0", ""):
                    cta_cred = ""

                valor_dec = _posicional_para_decimal(val_raw)
                hist_norm = _norm_hist(historico)

                idx_partida = len(lote_atual["partidas"])

                lote_atual["partidas"].append({
                    "idx":      idx_partida,
                    "seq":      linha[2:9].strip(),
                    "cta_deb":  cta_deb,
                    "cta_cred": cta_cred,
                    "valor":    valor_dec,
                    "cod_hist": cod_hist,
                    "hist":     hist_norm,
                    "filial":   filial_p,
                })

            # ── Registro 05 — Centro de Custo ─────────────────────────────────
            elif reg == "05":
                cnt["05"] += 1

                if lote_atual is None:
                    erros.append({
                        "linha":    num_linha,
                        "motivo":   "Registro 05 sem Registro 02 precedente",
                        "conteudo": linha[:80],
                    })
                    continue

                if not lote_atual["partidas"]:
                    erros.append({
                        "linha":    num_linha,
                        "motivo":   "Registro 05 sem Registro 03 precedente",
                        "conteudo": linha[:80],
                    })
                    continue

                cc_deb_raw  = linha[9:16]  if len(linha) > 15 else "0000000"
                cc_cred_raw = linha[16:23] if len(linha) > 22 else "0000000"
                val_raw5    = linha[23:38].strip() if len(linha) > 37 else "0"

                cc_deb  = _extrair_cc(cc_deb_raw)
                cc_cred = _extrair_cc(cc_cred_raw)
                valor_c = _posicional_para_decimal(val_raw5)

                # Vincula o CC à última partida do lote
                idx_pai = lote_atual["partidas"][-1]["idx"]

                lote_atual["centros"].append({
                    "seq":         linha[2:9].strip(),
                    "cc_deb":      cc_deb,
                    "cc_cred":     cc_cred,
                    "valor":       valor_c,
                    "idx_partida": idx_pai,
                })

            # ── Registro 08 — Totalizador (informativo) ───────────────────────
            elif reg == "08":
                cnt["08"] = cnt.get("08", 0) + 1

            # ── Registro 99 — Encerramento ────────────────────────────────────
            elif reg == "99":
                cnt["99"] += 1

            else:
                cnt["outro"] += 1

        except Exception as ex:
            erros.append({
                "linha":    num_linha,
                "motivo":   str(ex),
                "conteudo": linha[:80],
            })

    # ── Log de parse ─────────────────────────────────────────────────────────
    log.append(f"  Reg 01 (cabeçalho)  : {cnt['01']}")
    log.append(f"  Reg 02 (lotes)      : {cnt['02']:,}")
    log.append(f"  Reg 03 (partidas)   : {cnt['03']:,}")
    log.append(f"  Reg 05 (c.custos)   : {cnt['05']:,}")
    log.append(f"  Reg 08 (totalizador): {cnt.get('08', 0):,}")
    log.append(f"  Reg 99 (encerramento): {cnt['99']}")

    if erros:
        log.append(f"  Erros/avisos        : {len(erros):,}")

    filiais_encontradas = sorted(
        filiais_set,
        key=lambda x: int(x) if x.isdigit() else x
    )
    if filiais_encontradas:
        log.append(f"  Filiais detectadas  : {filiais_encontradas}")

    return {
        "cabecalho":           cabecalho,
        "lotes":               lotes,
        "erros":               erros,
        "filiais_encontradas": filiais_encontradas,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# APLICAÇÃO DO DE/PARA DE FILIAIS
# ═══════════════════════════════════════════════════════════════════════════════

def _aplicar_de_para(filial: str, mapa: dict) -> str:
    """
    Aplica o mapa De/Para ao código de filial.

    Parâmetros:
        filial : str  — código original da filial
        mapa   : dict — {cod_original → cod_destino}

    Retorna:
        str — código mapeado ou o original se não encontrar no mapa.
    """
    if not filial:
        return ""
    return mapa.get(filial, filial)


# ═══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DO ARQUIVO DE SAÍDA (0000 + 6000 + 6100 + 6110)
# ═══════════════════════════════════════════════════════════════════════════════

def _gerar_saida_posicional(parsed: dict,
                             ni: str,
                             gerar_6110: bool,
                             usar_de_para: bool,
                             mapa_filiais: dict,
                             log: list) -> bytes:
    """
    Itera sobre todos os lotes parseados e gera o arquivo de saída
    no leiaute Domínio pipe-delimitado:
        |0000|CNPJ|
        |6000|TIPO||||
        |6100|DATA|DEB|CRED|VALOR||HIST||FILIAL||
        |6110|CC_DEB|CC_CRED|VALOR|   (opcional)

    Regras de geração:
        - Lotes sem partidas são ignorados
        - Lotes sem débito OU sem crédito são ignorados
        - O tipo (X/D/C/V) é recalculado pelo número de débitos × créditos
          (não confia no tipo declarado no registro 02)
        - Filial: aplica De/Para se habilitado
        - 6110: gerado para cada partida que tenha CC no registro 05

    Parâmetros:
        parsed      : dict retornado por _parse_posicional()
        ni          : CNPJ/CPF limpo (14 ou 11 dígitos)
        gerar_6110  : bool — se True, injeta |6110| após cada |6100|
        usar_de_para: bool — se True, aplica mapa_filiais
        mapa_filiais: dict — {filial_orig → filial_dest}
        log         : list para log

    Retorna:
        bytes — arquivo gerado (utf-8-sig)
    """
    buf = io.StringIO()
    buf.write(f"|0000|{ni}|\n")

    lotes     = parsed["lotes"]
    ok        = 0
    ignorados = 0
    cnt       = {"t6000": 0, "t6100": 0, "t6110": 0}
    debug     = {"X": 0, "D": 0, "C": 0, "V": 0}

    # Contas que indicam "sem conta" no posicional
    _NULOS = {"", "0", "0000000"}

    for lote in lotes:
        data     = lote.get("data", "")
        partidas = lote.get("partidas", [])
        centros  = lote.get("centros",  [])

        if not partidas:
            ignorados += 1
            continue

        # Separa débitos e créditos
        debs  = [p for p in partidas if p["cta_deb"]  not in _NULOS]
        creds = [p for p in partidas if p["cta_cred"] not in _NULOS]

        if not debs or not creds:
            ignorados += 1
            continue

        nd = len(debs)
        nc = len(creds)

        # Recalcula o tipo real pelo número de partidas
        if   nd == 1 and nc == 1: tipo_real = "X"
        elif nd == 1 and nc > 1:  tipo_real = "D"
        elif nd > 1  and nc == 1: tipo_real = "C"
        else:                     tipo_real = "V"

        debug[tipo_real] = debug.get(tipo_real, 0) + 1

        # Indexa centros de custo por partida (idx_partida)
        centros_por_partida: dict = {}
        for cc in centros:
            idx = cc.get("idx_partida", -1)
            if idx >= 0:
                centros_por_partida.setdefault(idx, []).append(cc)

        # ── Helpers internos ─────────────────────────────────────────────────

        def _filial_p(p: dict) -> str:
            """Retorna a filial da partida, aplicando De/Para se habilitado."""
            f = p.get("filial", "")
            if usar_de_para and mapa_filiais:
                f = _aplicar_de_para(f, mapa_filiais)
            return f

        def _escreve_6110(idx: int, modo: str = "ambos") -> None:
            """Gera e escreve as linhas |6110| para a partida de índice idx."""
            if not gerar_6110:
                return
            for cc in centros_por_partida.get(idx, []):
                cc_d  = cc.get("cc_deb",  "")
                cc_c  = cc.get("cc_cred", "")
                v_cc  = cc.get("valor",   0.0)
                v_fmt = f"{v_cc:.2f}".replace(".", ",")
                for linha_6110 in _gerar_6110_linha(cc_d, cc_c, v_fmt, modo):
                    buf.write(linha_6110 + "\n")
                    cnt["t6110"] += 1

        def _escreve(dc: str, cc: str, v: float,
                     h: str, fil: str, idx: int) -> None:
            """Gera e escreve uma linha |6100| (+ |6110| se habilitado)."""
            vf  = f"{v:.2f}".replace(".", ",")
            hs  = _norm_hist(h)
            buf.write(f"|6100|{data}|{dc}|{cc}|{vf}||{hs}||{fil}||\n")
            cnt["t6100"] += 1

            # Determina o modo do 6110
            if dc and cc:
                modo = "ambos"
            elif dc:
                modo = "deb"
            else:
                modo = "cred"

            _escreve_6110(idx, modo)

        # ── Escreve o 6000 ───────────────────────────────────────────────────
        buf.write(f"|6000|{tipo_real}||||\n")
        cnt["t6000"] += 1

        # ── Tipo X — 1 débito × 1 crédito ────────────────────────────────────
        if tipo_real == "X":
            d   = debs[0]
            c   = creds[0]
            h   = d["hist"] or c["hist"]
            fil = _filial_p(d) or _filial_p(c)
            _escreve(d["cta_deb"], c["cta_cred"], d["valor"], h, fil, d["idx"])

        # ── Tipo D — 1 débito × N créditos ───────────────────────────────────
        elif tipo_real == "D":
            d = debs[0]
            _escreve(d["cta_deb"], "", d["valor"], d["hist"], _filial_p(d), d["idx"])
            for c in creds:
                h   = c["hist"] or d["hist"]
                fil = _filial_p(c) or _filial_p(d)
                _escreve("", c["cta_cred"], c["valor"], h, fil, c["idx"])

        # ── Tipo C — N débitos × 1 crédito ───────────────────────────────────
        elif tipo_real == "C":
            c = creds[0]
            _escreve("", c["cta_cred"], c["valor"], c["hist"], _filial_p(c), c["idx"])
            for d in debs:
                h   = d["hist"] or c["hist"]
                fil = _filial_p(d) or _filial_p(c)
                _escreve(d["cta_deb"], "", d["valor"], h, fil, d["idx"])

        # ── Tipo V — N débitos × N créditos ──────────────────────────────────
        else:
            for c in creds:
                _escreve("", c["cta_cred"], c["valor"], c["hist"], _filial_p(c), c["idx"])
            for d in debs:
                _escreve(d["cta_deb"], "", d["valor"], d["hist"], _filial_p(d), d["idx"])

        ok += 1

    # ── Log de geração ───────────────────────────────────────────────────────
    log.append(f"  Reg. 6000 gerados  : {cnt['t6000']:,}")
    log.append(f"  Reg. 6100 gerados  : {cnt['t6100']:,}")
    if gerar_6110:
        log.append(f"  Reg. 6110 gerados  : {cnt['t6110']:,}")
    log.append(f"  Lotes OK           : {ok:,}")
    log.append(f"  Lotes ignorados    : {ignorados:,}")
    log.append(
        f"  Tipos — "
        f"X:{debug.get('X', 0):,}  "
        f"D:{debug.get('D', 0):,}  "
        f"C:{debug.get('C', 0):,}  "
        f"V:{debug.get('V', 0):,}"
    )

    resultado = buf.getvalue().encode("utf-8-sig")
    del buf
    gc.collect()

    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# PRÉ-SCAN DE FILIAIS (sem processar o arquivo inteiro)
# ═══════════════════════════════════════════════════════════════════════════════

def _pre_scan_posicional(conteudo: bytes) -> list:
    """
    Lê apenas os registros 03 do arquivo posicional para extrair
    os códigos de filial únicos, sem processar lotes nem partidas.

    Usado para popular o widget De/Para antes do processamento completo.

    Parâmetros:
        conteudo : bytes do arquivo posicional

    Retorna:
        list[str] — códigos de filial únicos, ordenados numericamente.
    """
    enc = _detectar_encoding_bytes(conteudo)

    try:
        texto = conteudo.decode(enc, errors="replace")
    except Exception:
        texto = conteudo.decode("utf-8", errors="replace")

    filiais: set = set()

    for linha in texto.splitlines():
        if len(linha) >= 564 and linha[:2] == "03":
            raw = linha[557:564].strip()
            if raw and raw.isdigit():
                codigo = str(int(raw))
                if codigo != "0":
                    filiais.add(codigo)

    return sorted(filiais, key=lambda x: int(x) if x.isdigit() else x)


# ═══════════════════════════════════════════════════════════════════════════════
# PRÉ-POPULAR O DATAFRAME DO EDITOR DE/PARA
# ═══════════════════════════════════════════════════════════════════════════════

def _pre_popular_mapa_filiais(filiais_encontradas: list) -> None:
    """
    Popula o st.session_state["mapa_filiais_df"] com as filiais detectadas,
    criando uma linha por filial com a coluna "Código Destino (Para)" vazia.

    Só recria o DataFrame se as filiais mudaram (evita resetar edições do usuário).

    Parâmetros:
        filiais_encontradas : list[str] — filiais detectadas no arquivo
    """
    df_atual = st.session_state.get("mapa_filiais_df")

    if df_atual is not None and len(df_atual) > 0:
        origens_atuais = set(
            str(r).strip()
            for r in df_atual["Código Original (De)"].tolist()
            if str(r).strip() not in ("", "nan", "None")
        )
        # Se as filiais não mudaram, mantém o DataFrame existente (preserva edições)
        if origens_atuais == set(filiais_encontradas):
            return

    rows = (
        [{"Código Original (De)": f, "Código Destino (Para)": ""}
         for f in filiais_encontradas]
        if filiais_encontradas
        else [{"Código Original (De)": "", "Código Destino (Para)": ""}]
    )

    st.session_state["mapa_filiais_df"] = pd.DataFrame(rows, dtype=str)


# ═══════════════════════════════════════════════════════════════════════════════
# WIDGET STREAMLIT — EDITOR DE/PARA DE FILIAIS
# ═══════════════════════════════════════════════════════════════════════════════

def _widget_de_para_filiais(habilitado: bool,
                             filiais_encontradas: list) -> dict:
    """
    Renderiza o widget Streamlit de mapeamento De/Para de filiais.

    Exibe um st.data_editor com:
        - Coluna "Código Original (De)"  — somente leitura
        - Coluna "Código Destino (Para)" — editável pelo usuário

    Persiste as edições no st.session_state["mapa_filiais_df"].

    Parâmetros:
        habilitado          : bool — se False, retorna {} sem renderizar
        filiais_encontradas : list[str] — filiais detectadas no arquivo

    Retorna:
        dict — {filial_orig → filial_dest} com as regras ativas.
               Linhas com destino vazio são ignoradas.
    """
    if not habilitado:
        return {}

    _pre_popular_mapa_filiais(filiais_encontradas)

    st.markdown(
        """
        <div style='background:#0a1a2e;border:1px solid #6EC6FF;
                    border-radius:8px;padding:14px 18px;margin:10px 0;'>
            <b style='color:#6EC6FF;'>🏢 Mapeamento De/Para — Código da Filial</b><br>
            <small style='color:#9BB0C8;'>
                Preencha <b style='color:#FFD166;'>Código Destino (Para)</b>
                para remapear. Linhas em branco mantêm o código original.
            </small>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_base = st.session_state["mapa_filiais_df"].copy()

    df_edit = st.data_editor(
        df_base,
        num_rows="fixed",
        use_container_width=True,
        column_config={
            "Código Original (De)": st.column_config.TextColumn(
                "Código Original (De)", disabled=True
            ),
            "Código Destino (Para)": st.column_config.TextColumn(
                "Código Destino (Para)", max_chars=20
            ),
        },
        key="editor_filiais",
    )

    # Persiste as edições
    st.session_state["mapa_filiais_df"] = df_edit

    # Monta o dicionário De/Para (ignora linhas com destino vazio)
    mapa: dict = {}
    for _, row in df_edit.iterrows():
        orig = str(row.get("Código Original (De)",  "")).strip()
        dest = str(row.get("Código Destino (Para)", "")).strip()

        if (
            orig
            and orig.lower() not in ("nan", "none", "")
            and dest
            and dest.lower() not in ("nan", "none", "")
        ):
            mapa[orig] = dest

    # Feedback ao usuário
    if mapa:
        regras = " | ".join(f"{k} → {v}" for k, v in sorted(mapa.items()))
        st.caption(f"✅ {len(mapa)} regra(s) ativa(s): {regras}")
    elif filiais_encontradas:
        st.caption("ℹ️ Nenhum código destino informado — filiais mantidas como estão.")
    else:
        st.caption("ℹ️ Nenhuma filial detectada no arquivo.")

    return mapa


# ═══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA DO MÓDULO TXT POSICIONAL
# ═══════════════════════════════════════════════════════════════════════════════

def processar_dominio_posicional(conteudo: bytes,
                                  ni: str,
                                  gerar_6110: bool,
                                  usar_de_para: bool,
                                  mapa_filiais: dict,
                                  log: list,
                                  prog_bar,
                                  status) -> tuple:
    """
    Ponto de entrada do módulo TXT Posicional Domínio.

    Fluxo:
        1. _parse_posicional()       → lê registros 01/02/03/05
        2. _gerar_saida_posicional() → gera 0000 + 6000 + 6100 (+ 6110)
        3. Retorna (resultado_bytes, metricas, erros, filiais_encontradas)

    Parâmetros:
        conteudo     : bytes do arquivo posicional
        ni           : CNPJ/CPF limpo (14 ou 11 dígitos)
        gerar_6110   : bool — se True, injeta |6110| (Centro de Custo)
        usar_de_para : bool — se True, aplica mapa_filiais
        mapa_filiais : dict — {filial_orig → filial_dest}
        log          : list para log
        prog_bar     : widget st.progress
        status       : widget st.empty

    Retorna:
        resultado_bytes     : bytes  — arquivo gerado (utf-8-sig)
        metricas            : dict   — métricas para exibição na UI
        erros               : list   — erros de parse
        filiais_encontradas : list   — filiais detectadas no arquivo
    """
    status.text("Lendo arquivo posicional Domínio...")
    prog_bar.progress(10)
    log.append("── PARSE POSICIONAL ──")

    parsed = _parse_posicional(conteudo, log)
    erros  = parsed["erros"]

    # Log do De/Para
    if usar_de_para and mapa_filiais:
        log.append(
            f"  De/Para filiais    : {len(mapa_filiais)} regra(s) → {mapa_filiais}"
        )
    else:
        log.append("  De/Para filiais    : desabilitado")

    prog_bar.progress(50)
    status.text("Gerando saída com separador pipe...")
    log.append("\n── GERAÇÃO ──")

    resultado_bytes = _gerar_saida_posicional(
        parsed, ni, gerar_6110, usar_de_para, mapa_filiais, log
    )

    prog_bar.progress(90)

    # Contagem de registros no arquivo gerado
    n6000 = resultado_bytes.count(b"|6000|")
    n6100 = resultado_bytes.count(b"|6100|")
    n6110 = resultado_bytes.count(b"|6110|")

    metricas = {
        "CNPJ / CPF":   ni,
        "Lotes":        f"{len(parsed['lotes']):,}",
        "Reg. 6000":    f"{n6000:,}",
        "Reg. 6100":    f"{n6100:,}",
        "Tamanho saída":f"{len(resultado_bytes) / 1024:.1f} KB",
    }
    if gerar_6110:
        metricas["Reg. 6110"] = f"{n6110:,}"
    if usar_de_para and mapa_filiais:
        metricas["Filiais remapeadas"] = f"{len(mapa_filiais):,}"

    prog_bar.progress(100)
    status.text("Concluído!")

    return resultado_bytes, metricas, erros, parsed["filiais_encontradas"]	
	
	# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 9 — MÓDULO COMPARAÇÃO I052 V3.7.0
# Integra:
#   • _parse_i052_completo()     — lê I050, I052, I150, I155, I355, 0000
#   • _comparar_i052()           — compara dois ECDs (mudanças de grupo + saldos)
#   • _render_comparacao_i052()  — renderiza o resultado na UI Streamlit
#   • _pre_scan_cnpj_ecd()       — extrai CNPJ do 0000 sem processar tudo
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# PARSE COMPLETO DO SPED ECD PARA COMPARAÇÃO I052
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_i052_completo(conteudo: bytes, log: list) -> dict:
    """
    Lê um SPED ECD e extrai todos os dados necessários para a comparação I052:

        - 0000  → CNPJ, período (DT_INI / DT_FIN)
        - I050  → mapa conta → nome / natureza (COD_NAT)
        - I052  → vínculos conta → COD_AGL (plano referencial COSIF/FCONT)
        - I150  → marcadores de período de saldos
        - I155  → saldo final de cada conta (último período)
        - I355  → saldo inicial de cada conta (abertura do período)

    Layout dos registros relevantes:
        0000  : |0000|LECD|DT_INI|DT_FIN|COD_SIT|CNPJ|...
        I050  : |I050|...|COD_NAT|IND_CTA|...|COD_CTA|COD_STA|NOME|...
        I052  : |I052|COD_CTA|COD_AGL|
        I150  : |I150|DT_INI|DT_FIN|
        I155  : |I155|COD_CTA|...|...|...|...|...|VL_SLD_FIN_NC|IND_DC_FIN|...
        I355  : |I355|COD_CTA|...|VL_CTA|IND_DC|...

    Parâmetros:
        conteudo : bytes do arquivo SPED ECD
        log      : list para log

    Retorna dict com:
        cnpj              : str — CNPJ limpo (14 dígitos)
        dt_ini            : str — data inicial normalizada (DD/MM/YYYY)
        dt_fin            : str — data final normalizada (DD/MM/YYYY)
        mapa_nome         : dict {cod_cta → nome}
        mapa_nat          : dict {cod_cta → cod_nat}
        i052              : dict {cod_cta → list[cod_agl]}
        saldos_finais     : dict {cod_cta → (valor, dc)} — último período I155
        saldos_iniciais   : dict {cod_cta → (valor, dc)} — I355
        erros             : list[dict]
    """
    enc = _detectar_encoding_bytes(conteudo)
    log.append(f"  Encoding           : {enc}")

    try:
        texto = conteudo.decode(enc, errors="replace")
    except Exception:
        texto = conteudo.decode("utf-8", errors="replace")

    linhas = texto.splitlines()
    log.append(f"  Total de linhas    : {len(linhas):,}")

    # Metadados do arquivo
    cnpj         = ""
    dt_ini_0000  = ""
    dt_fin_0000  = ""

    # Plano de contas
    mapa_nome: dict = {}   # cod_cta → nome
    mapa_nat:  dict = {}   # cod_cta → cod_nat

    # Vínculos I052
    i052: dict = {}        # cod_cta → list[cod_agl]

    # Saldos finais (I155) — por período
    i155_por_periodo: dict = {}
    periodo_atual_idx = -1

    # Saldos iniciais (I355)
    saldos_i355: dict = {}   # cod_cta → (valor, dc)

    # Contadores e erros
    cnt = {
        "0000": 0, "I050": 0, "I052": 0,
        "I150": 0, "I155": 0, "I355": 0,
    }
    erros: list = []

    for num_linha, linha in enumerate(linhas, 1):
        linha = linha.strip()
        if not linha:
            continue

        campos = _split_pipe(linha)
        if not campos:
            continue

        reg = campos[0]

        try:
            # ── Registro 0000 — Cabeçalho ─────────────────────────────────
            if reg == "0000":
                cnt["0000"] += 1
                # Layout: |0000|LECD|DT_INI|DT_FIN|COD_SIT|CNPJ|...
                if len(campos) > 2: dt_ini_0000 = _campo(campos, 2).strip()
                if len(campos) > 3: dt_fin_0000 = _campo(campos, 3).strip()
                if len(campos) > 5:
                    cnpj = re.sub(r"\D", "", _campo(campos, 5).strip())

            # ── Registro I050 — Plano de Contas ───────────────────────────
            elif reg == "I050":
                cnt["I050"] += 1
                if len(campos) < 6:
                    continue

                cod_nat  = _campo(campos, 2).strip()
                cod_cta  = _campo(campos, 5).strip()
                nome_cta = _campo(campos, 7).strip() if len(campos) > 7 else ""

                if cod_cta:
                    mapa_nome[cod_cta] = nome_cta
                    mapa_nat[cod_cta]  = cod_nat

            # ── Registro I052 — Vínculo Conta → COD_AGL ───────────────────
            elif reg == "I052":
                cnt["I052"] += 1
                # Layout: |I052|COD_CTA|COD_AGL|
                cod_cta = _campo(campos, 1).strip()
                cod_agl = _campo(campos, 2).strip()

                if cod_cta and cod_agl:
                    i052.setdefault(cod_cta, []).append(cod_agl)

            # ── Registro I150 — Marcador de Período ───────────────────────
            elif reg == "I150":
                cnt["I150"] += 1
                periodo_atual_idx += 1
                i155_por_periodo[periodo_atual_idx] = {}

            # ── Registro I155 — Saldo Final por Conta ─────────────────────
            elif reg == "I155":
                cnt["I155"] += 1
                if periodo_atual_idx < 0:
                    continue

                cod_cta   = _campo(campos, 1).strip()
                vl_fin    = _campo(campos, 7).strip()   # VL_SLD_FIN_NC
                ind_dc    = _campo(campos, 8).strip().upper()  # IND_DC_FIN

                if not cod_cta:
                    continue
                if ind_dc not in ("D", "C"):
                    ind_dc = "D"

                try:
                    valor_f = _str2float(vl_fin)
                except Exception:
                    valor_f = 0.0

                i155_por_periodo[periodo_atual_idx][cod_cta] = (valor_f, ind_dc)

            # ── Registro I355 — Saldo Inicial (Abertura) ──────────────────
            elif reg == "I355":
                cnt["I355"] += 1
                cod_cta = _campo(campos, 1).strip()
                vl_cta  = _campo(campos, 3).strip()
                ind_dc  = _campo(campos, 4).strip().upper()

                if not cod_cta:
                    continue
                if ind_dc not in ("D", "C"):
                    ind_dc = "D"

                try:
                    valor_f = _str2float(vl_cta)
                except Exception:
                    valor_f = 0.0

                saldos_i355[cod_cta] = (valor_f, ind_dc)

        except Exception as ex:
            erros.append({
                "linha":    num_linha,
                "motivo":   str(ex),
                "conteudo": linha[:80],
            })

    # ── Saldos finais do ÚLTIMO período I155 ─────────────────────────────────
    saldos_i155_final: dict = {}
    periodos_count = len(i155_por_periodo)

    if i155_por_periodo:
        ultimo_idx        = max(i155_por_periodo.keys())
        saldos_i155_final = i155_por_periodo[ultimo_idx]

    # ── Log de parse ─────────────────────────────────────────────────────────
    log.append(f"  CNPJ               : {cnpj}")
    log.append(
        f"  Período            : "
        f"{_normalizar_data_ecd(dt_ini_0000)} a "
        f"{_normalizar_data_ecd(dt_fin_0000)}"
    )
    log.append(f"  Registros I050     : {cnt['I050']:,}")
    log.append(
        f"  Registros I052     : {cnt['I052']:,}  "
        f"({len(i052):,} contas com vínculo)"
    )
    log.append(f"  Períodos I150      : {periodos_count:,}")
    log.append(f"  Saldos I155 finais : {len(saldos_i155_final):,}")
    log.append(f"  Saldos I355        : {len(saldos_i355):,}")

    if erros:
        log.append(f"  Erros/avisos       : {len(erros):,}")

    return {
        "cnpj":            cnpj,
        "dt_ini":          _normalizar_data_ecd(dt_ini_0000),
        "dt_fin":          _normalizar_data_ecd(dt_fin_0000),
        "mapa_nome":       mapa_nome,
        "mapa_nat":        mapa_nat,
        "i052":            i052,              # cod_cta → [cod_agl]
        "saldos_finais":   saldos_i155_final, # cod_cta → (valor, dc)
        "saldos_iniciais": saldos_i355,       # cod_cta → (valor, dc)
        "erros":           erros,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# COMPARAÇÃO DOS I052 — ECD ANTERIOR vs. ECD ATUAL
# ═══════════════════════════════════════════════════════════════════════════════

def _comparar_i052(ant: dict, atu: dict) -> dict:
    """
    Compara os I052 de dois ECDs e retorna um relatório completo com:

        contas_mudaram_grupo : list[dict]
            Contas que mudaram de COD_AGL entre os dois arquivos.
            Cada item contém:
                conta       : str — código da conta
                nome        : str — nome da conta (preferência do anterior)
                agl_ant     : list[str] — COD_AGL(s) no arquivo anterior
                agl_atu     : list[str] — COD_AGL(s) no arquivo atual
                adicionados : list[str] — COD_AGL novos no atual
                removidos   : list[str] — COD_AGL removidos do atual

        contas_so_anterior : list[str]
            Contas presentes no I052 anterior mas ausentes no atual.

        contas_so_atual : list[str]
            Contas novas no I052 atual (não existiam no anterior).

        divergencias_saldo : list[dict]
            COD_AGL cujo saldo final (anterior I155) ≠ saldo inicial (atual I355).
            Diferença calculada como: saldo_fin_ant − saldo_ini_atu

        resumo_agl : list[dict]
            Todos os COD_AGL encontrados com seus saldos e status.

        total_contas_ant : int
        total_contas_atu : int
        total_agls       : int

    Metodologia de saldo por COD_AGL:
        - Saldo final do anterior  = soma dos I155 (último período) agrupado por COD_AGL
          Sinal: Crédito → positivo, Débito → negativo
        - Saldo inicial do atual   = soma dos I355 agrupado por COD_AGL
          Sinal: Crédito → positivo, Débito → negativo
        - Divergência = |saldo_fin_ant − saldo_ini_atu| ≥ TOL_VALOR

    Parâmetros:
        ant : dict retornado por _parse_i052_completo() — arquivo anterior
        atu : dict retornado por _parse_i052_completo() — arquivo atual

    Retorna dict com o relatório completo.
    """
    i052_ant = ant["i052"]   # cod_cta → [cod_agl]
    i052_atu = atu["i052"]

    contas_ant = set(i052_ant.keys())
    contas_atu = set(i052_atu.keys())

    contas_so_anterior = sorted(contas_ant - contas_atu)
    contas_so_atual    = sorted(contas_atu - contas_ant)
    contas_comuns      = contas_ant & contas_atu

    # ── Contas que mudaram de COD_AGL ────────────────────────────────────────
    contas_mudaram_grupo: list = []

    for cta in sorted(contas_comuns):
        agls_ant = set(i052_ant[cta])
        agls_atu = set(i052_atu[cta])

        if agls_ant != agls_atu:
            contas_mudaram_grupo.append({
                "conta":      cta,
                "nome":       ant["mapa_nome"].get(cta, atu["mapa_nome"].get(cta, "")),
                "agl_ant":    sorted(agls_ant),
                "agl_atu":    sorted(agls_atu),
                "adicionados": sorted(agls_atu - agls_ant),
                "removidos":   sorted(agls_ant - agls_atu),
            })

    # ── Agrupa saldo final (anterior I155) por COD_AGL ───────────────────────
    # Convenção de sinal: Crédito → positivo, Débito → negativo
    agl_saldo_fin: dict = {}

    for cta, agls in i052_ant.items():
        if cta not in ant["saldos_finais"]:
            continue

        v, dc   = ant["saldos_finais"][cta]
        signed  = v if dc == "C" else -v

        for agl in agls:
            agl_saldo_fin[agl] = round(
                agl_saldo_fin.get(agl, 0.0) + signed, 2
            )

    # ── Agrupa saldo inicial (atual I355) por COD_AGL ────────────────────────
    agl_saldo_ini: dict = {}

    for cta, agls in i052_atu.items():
        if cta not in atu["saldos_iniciais"]:
            continue

        v, dc   = atu["saldos_iniciais"][cta]
        signed  = v if dc == "C" else -v

        for agl in agls:
            agl_saldo_ini[agl] = round(
                agl_saldo_ini.get(agl, 0.0) + signed, 2
            )

    # ── Monta o resumo por COD_AGL ────────────────────────────────────────────
    todos_agls = set(agl_saldo_fin.keys()) | set(agl_saldo_ini.keys())
    resumo_agl:         list = []
    divergencias_saldo: list = []

    for agl in sorted(todos_agls):
        sf  = agl_saldo_fin.get(agl, 0.0)
        si  = agl_saldo_ini.get(agl, 0.0)
        dif = round(sf - si, 2)
        ok  = abs(dif) < TOL_VALOR

        row = {
            "cod_agl":       agl,
            "saldo_fin_ant": sf,
            "saldo_ini_atu": si,
            "diferenca":     dif,
            "ok":            ok,
        }
        resumo_agl.append(row)

        if not ok:
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


# ═══════════════════════════════════════════════════════════════════════════════
# RENDERIZAÇÃO DO RESULTADO NA UI STREAMLIT
# ═══════════════════════════════════════════════════════════════════════════════

def _render_comparacao_i052(resultado: dict,
                             label_ant: str,
                             label_atu: str,
                             parsed_ant: dict,
                             parsed_atu: dict) -> None:
    """
    Renderiza o resultado da comparação I052 na interface Streamlit.

    Seções exibidas:
        1. Cabeçalho dos dois arquivos (empresa, CNPJ, período, total de contas)
        2. Métricas resumo (5 colunas)
        3. Card de status geral (OK / divergências)
        4. Tabela de contas que mudaram de COD_AGL
        5. Expander: contas apenas no anterior
        6. Expander: contas apenas no atual
        7. Tabela de saldos por COD_AGL com filtro e download CSV

    Parâmetros:
        resultado   : dict retornado por _comparar_i052()
        label_ant   : str — nome do arquivo anterior (ex: "ECD_2023.txt")
        label_atu   : str — nome do arquivo atual    (ex: "ECD_2024.txt")
        parsed_ant  : dict retornado por _parse_i052_completo() — anterior
        parsed_atu  : dict retornado por _parse_i052_completo() — atual
    """
    st.markdown("---")
    st.markdown("## 📊 Resultado da Comparação I052")

    # ── Cabeçalho dos dois arquivos ───────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        cnpj_ant = fmt_cnpj(parsed_ant["cnpj"]) if parsed_ant["cnpj"] else "—"
        st.markdown(
            f"<div class='filial-box'>"
            f"<b style='color:#6EC6FF;'>📁 ANTERIOR</b><br>"
            f"<span style='color:#FFD166;'>{label_ant}</span><br>"
            f"CNPJ: {cnpj_ant}<br>"
            f"Período: {parsed_ant['dt_ini']} a {parsed_ant['dt_fin']}<br>"
            f"Contas I052: {resultado['total_contas_ant']:,}"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_b:
        cnpj_atu = fmt_cnpj(parsed_atu["cnpj"]) if parsed_atu["cnpj"] else "—"
        st.markdown(
            f"<div class='filial-box'>"
            f"<b style='color:#6EC6FF;'>📁 ATUAL</b><br>"
            f"<span style='color:#FFD166;'>{label_atu}</span><br>"
            f"CNPJ: {cnpj_atu}<br>"
            f"Período: {parsed_atu['dt_ini']} a {parsed_atu['dt_fin']}<br>"
            f"Contas I052: {resultado['total_contas_atu']:,}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Métricas resumo ───────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Contas — Anterior",  f"{resultado['total_contas_ant']:,}")
    m2.metric("Contas — Atual",     f"{resultado['total_contas_atu']:,}")
    m3.metric("Mudaram de grupo",   f"{len(resultado['contas_mudaram_grupo']):,}")
    m4.metric("Só no anterior",     f"{len(resultado['contas_so_anterior']):,}")
    m5.metric("Só no atual",        f"{len(resultado['contas_so_atual']):,}")

    # ── Card de status geral ──────────────────────────────────────────────────
    n_div = len(resultado["divergencias_saldo"])

    if n_div == 0:
        st.markdown(
            "<div class='card-ok'>"
            "✅ <b style='color:#00C896;'>"
            "Todos os saldos por COD_AGL batem entre o saldo final do "
            "anterior e o saldo inicial do atual."
            "</b></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='card-err'>"
            f"⚠️ <b style='color:#FF4444;'>"
            f"{n_div} COD_AGL(s) com divergência de saldo entre os dois arquivos."
            f"</b></div>",
            unsafe_allow_html=True,
        )

    # ── Seção 1: Contas que mudaram de COD_AGL ───────────────────────────────
    st.markdown("#### 🔀 Contas que mudaram de COD_AGL")

    if resultado["contas_mudaram_grupo"]:
        rows_mud = []
        for r in resultado["contas_mudaram_grupo"]:
            rows_mud.append({
                "Conta":        r["conta"],
                "Nome":         r["nome"],
                "AGL Anterior": ", ".join(r["agl_ant"]),
                "AGL Atual":    ", ".join(r["agl_atu"]),
                "Adicionados":  ", ".join(r["adicionados"]),
                "Removidos":    ", ".join(r["removidos"]),
            })

        st.dataframe(
            pd.DataFrame(rows_mud),
            use_container_width=True,
            hide_index=True,
        )

        # Download da tabela de mudanças como CSV
        csv_mud = (
            pd.DataFrame(rows_mud)
            .to_csv(index=False, sep=";", decimal=",")
            .encode("utf-8-sig")
        )
        st.download_button(
            "⬇ Baixar mudanças de grupo (.csv)",
            data=csv_mud,
            file_name="comparacao_i052_mudancas.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.success("Nenhuma conta mudou de grupo entre os dois arquivos.")

    # ── Seção 2: Contas apenas no anterior ───────────────────────────────────
    with st.expander(
        f"📤 Contas presentes APENAS no anterior "
        f"({len(resultado['contas_so_anterior']):,})",
        expanded=False,
    ):
        if resultado["contas_so_anterior"]:
            rows_ant = [
                {
                    "Conta": c,
                    "Nome":  parsed_ant["mapa_nome"].get(c, ""),
                    "Nat.":  parsed_ant["mapa_nat"].get(c, ""),
                }
                for c in resultado["contas_so_anterior"]
            ]
            st.dataframe(
                pd.DataFrame(rows_ant),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhuma conta exclusiva do arquivo anterior.")

    # ── Seção 3: Contas apenas no atual ──────────────────────────────────────
    with st.expander(
        f"📥 Contas presentes APENAS no atual "
        f"({len(resultado['contas_so_atual']):,})",
        expanded=False,
    ):
        if resultado["contas_so_atual"]:
            rows_atu = [
                {
                    "Conta": c,
                    "Nome":  parsed_atu["mapa_nome"].get(c, ""),
                    "Nat.":  parsed_atu["mapa_nat"].get(c, ""),
                }
                for c in resultado["contas_so_atual"]
            ]
            st.dataframe(
                pd.DataFrame(rows_atu),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhuma conta exclusiva do arquivo atual.")

    # ── Seção 4: Saldos por COD_AGL ──────────────────────────────────────────
    st.markdown("#### 💰 Saldo Final (anterior) vs. Saldo Inicial (atual) por COD_AGL")
    st.caption(
        "Saldo final = soma dos I155 do último período do arquivo anterior, "
        "agrupado por COD_AGL.  \n"
        "Saldo inicial = soma dos I355 do arquivo atual, agrupado por COD_AGL.  \n"
        "Sinal: Crédito → positivo, Débito → negativo."
    )

    # Filtro de exibição
    filtro_agl = st.radio(
        "Exibir:",
        ["Todos os COD_AGL", "✅ Somente OK", "❌ Somente com divergência"],
        horizontal=True,
        key="filtro_agl_radio",
    )

    rows_agl = []
    for r in resultado["resumo_agl"]:
        if filtro_agl == "✅ Somente OK"              and not r["ok"]: continue
        if filtro_agl == "❌ Somente com divergência" and     r["ok"]: continue

        rows_agl.append({
            "COD_AGL":         r["cod_agl"],
            "Saldo Fin. Ant.": r["saldo_fin_ant"],
            "Saldo Ini. Atu.": r["saldo_ini_atu"],
            "Diferença":       r["diferenca"],
            "Status":          "✔ OK" if r["ok"] else "✖ DIVERGE",
        })

    if rows_agl:
        df_agl = pd.DataFrame(rows_agl)

        # Aplica estilo condicional
        styled = (
            df_agl.style
            .map(
                lambda v: (
                    "color:#00C896;font-weight:700"
                    if v == "✔ OK"
                    else "color:#FF4444;font-weight:700"
                ),
                subset=["Status"],
            )
            .map(
                lambda v: (
                    "color:#FF4444"
                    if abs(v) >= TOL_VALOR
                    else "color:#00C896"
                ),
                subset=["Diferença"],
            )
            .format({
                "Saldo Fin. Ant.": "R$ {:,.2f}",
                "Saldo Ini. Atu.": "R$ {:,.2f}",
                "Diferença":       "R$ {:,.2f}",
            })
        )

        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Download da tabela de saldos como CSV
        csv_bytes = (
            df_agl
            .to_csv(index=False, sep=";", decimal=",")
            .encode("utf-8-sig")
        )
        st.download_button(
            "⬇ Baixar comparação COD_AGL (.csv)",
            data=csv_bytes,
            file_name="comparacao_i052_agl.csv",
            mime="text/csv",
            use_container_width=True,
        )

    else:
        st.info("Nenhum COD_AGL encontrado para os filtros selecionados.")


# ═══════════════════════════════════════════════════════════════════════════════
# PRÉ-SCAN DO CNPJ — leitura rápida sem processar o arquivo inteiro
# ═══════════════════════════════════════════════════════════════════════════════

def _pre_scan_cnpj_ecd(conteudo: bytes) -> str:
    """
    Lê apenas os primeiros 4096 bytes do arquivo para extrair o CNPJ
    do registro 0000, sem precisar decodificar o arquivo inteiro.

    Usado no carregamento do arquivo para pré-preencher o campo CNPJ
    na UI antes do processamento completo.

    Retorna:
        str — CNPJ com 14 dígitos, ou "" se não encontrar.
    """
    enc = _detectar_encoding_bytes(conteudo)

    try:
        amostra = conteudo[:4096].decode(enc, errors="replace")
    except Exception:
        amostra = conteudo[:4096].decode("utf-8", errors="replace")

    for linha in amostra.splitlines():
        campos = _split_pipe(linha.strip())
        if campos and campos[0] == "0000" and len(campos) > 5:
            cnpj = re.sub(r"\D", "", campos[5].strip())
            if len(cnpj) == 14:
                return cnpj

    return ""
	
# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 10 — PARTICIONAMENTO POR MÊS E POR LINHAS V3.7.0
# Integra:
#   • _extrair_mes_linha_6100()      — extrai AAAA-MM de uma linha |6100|
#   • _particionar_por_mes()         — divide o arquivo em partes por mês
#   • _particionar_por_linhas()      — divide o arquivo em partes por N linhas
#   • _montar_zip_particoes()        — empacota todas as partes em um ZIP
#   • _render_painel_particoes()     — renderiza o painel de download na UI
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRAÇÃO DO MÊS DE UMA LINHA |6100|
# ═══════════════════════════════════════════════════════════════════════════════

def _extrair_mes_linha_6100(linha: str) -> str:
    """
    Extrai o mês de competência de uma linha |6100| no formato AAAA-MM.

    Layout do registro |6100|:
        |6100|DATA|DEB|CRED|VALOR||HIST|||...
        campo[1] = DATA no formato DD/MM/YYYY

    Parâmetros:
        linha : str — linha completa do arquivo (ex: "|6100|15/03/2024|...")

    Retorna:
        str — "AAAA-MM" (ex: "2024-03") ou "" se não conseguir extrair.
    """
    if not linha.startswith("|6100|"):
        return ""

    campos = linha.split("|")
    # campos[0] = "" (antes do primeiro pipe)
    # campos[1] = "6100"
    # campos[2] = DATA
    if len(campos) < 3:
        return ""

    data_raw = campos[2].strip()

    # Formato esperado: DD/MM/YYYY
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", data_raw):
        partes = data_raw.split("/")
        return f"{partes[2]}-{partes[1]}"   # AAAA-MM

    # Tenta via pandas como fallback
    try:
        dt = pd.to_datetime(data_raw, dayfirst=True, errors="raise")
        return dt.strftime("%Y-%m")
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# PARTICIONAMENTO POR MÊS
# ═══════════════════════════════════════════════════════════════════════════════

def _particionar_por_mes(conteudo_bytes: bytes, ni: str) -> dict:
    """
    Divide o arquivo de saída em partições por mês de competência.

    Regras:
        - Cada partição começa com |0000|CNPJ|
        - Um bloco |6000| e todos os seus |6100| ficam SEMPRE na mesma partição
          (nunca corta um lançamento no meio)
        - A partição é determinada pelo mês do PRIMEIRO |6100| do bloco
        - Blocos sem |6100| com data válida vão para a partição "sem_data"
        - A ordem dos meses no arquivo é preservada

    Parâmetros:
        conteudo_bytes : bytes — arquivo gerado (utf-8-sig)
        ni             : str  — CNPJ/CPF limpo

    Retorna:
        dict ordenado {chave_mes: bytes}
            chave_mes = "AAAA-MM" ou "sem_data"
            bytes = conteúdo da partição (utf-8-sig)

    Exemplo de retorno:
        {
            "2024-01": b"|0000|...|\\n|6000|X||||\\n|6100|...",
            "2024-02": b"|0000|...|\\n|6000|V||||\\n|6100|...",
            "sem_data": b"|0000|...|\\n|6000|X||||\\n|6100|...",
        }
    """
    try:
        texto = conteudo_bytes.decode("utf-8-sig", errors="replace")
    except Exception:
        texto = conteudo_bytes.decode("utf-8", errors="replace")

    linhas = texto.splitlines()

    # Acumuladores por mês — preserva ordem de inserção
    particoes: dict = OrderedDict()   # {mes: list[str]}

    bloco_atual:  list = []   # linhas do bloco corrente (6000 + seus 6100)
    mes_bloco:    str  = ""   # mês determinado pelo primeiro 6100 do bloco

    linha_0000 = fmt_reg_0000(ni)

    def _fechar_bloco() -> None:
        """Fecha o bloco atual e o adiciona à partição correta."""
        nonlocal bloco_atual, mes_bloco

        if not bloco_atual:
            return

        chave = mes_bloco if mes_bloco else "sem_data"

        if chave not in particoes:
            particoes[chave] = []

        particoes[chave].extend(bloco_atual)
        bloco_atual = []
        mes_bloco   = ""

    for linha in linhas:
        linha_strip = linha.strip()

        # Ignora linhas vazias e o |0000| original (será reinserido por partição)
        if not linha_strip:
            continue
        if linha_strip.startswith("|0000|"):
            continue

        # Início de novo bloco — fecha o anterior
        if linha_strip.startswith("|6000|"):
            _fechar_bloco()
            bloco_atual = [linha_strip]
            mes_bloco   = ""

        elif linha_strip.startswith("|6100|"):
            # Determina o mês pelo primeiro |6100| do bloco
            if not mes_bloco:
                mes_bloco = _extrair_mes_linha_6100(linha_strip)
            bloco_atual.append(linha_strip)

        elif linha_strip.startswith("|6110|"):
            # |6110| sempre segue o |6100| — mantém no mesmo bloco
            bloco_atual.append(linha_strip)

        else:
            # Linha desconhecida — adiciona ao bloco atual se existir
            if bloco_atual:
                bloco_atual.append(linha_strip)

    # Fecha o último bloco pendente
    _fechar_bloco()

    # Monta os bytes de cada partição
    resultado: dict = OrderedDict()

    for mes, linhas_part in sorted(particoes.items()):
        conteudo_part = linha_0000 + "\n" + "\n".join(linhas_part) + "\n"
        resultado[mes] = conteudo_part.encode("utf-8-sig")

    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# PARTICIONAMENTO POR LINHAS (|6100|)
# ═══════════════════════════════════════════════════════════════════════════════

def _particionar_por_linhas(conteudo_bytes: bytes,
                             ni: str,
                             max_linhas_6100: int) -> dict:
    """
    Divide o arquivo de saída em partições com no máximo N linhas |6100|.

    Regras:
        - Cada partição começa com |0000|CNPJ|
        - Um bloco |6000| e todos os seus |6100| ficam SEMPRE na mesma partição
          (nunca corta um lançamento no meio)
        - A partição é fechada quando o próximo bloco ultrapassaria o limite
        - Blocos com mais |6100| do que o limite são incluídos inteiros
          (o limite é respeitado no início do próximo bloco)

    Parâmetros:
        conteudo_bytes    : bytes — arquivo gerado (utf-8-sig)
        ni                : str  — CNPJ/CPF limpo
        max_linhas_6100   : int  — número máximo de linhas |6100| por partição

    Retorna:
        dict ordenado {"parte_001": bytes, "parte_002": bytes, ...}

    Exemplo:
        max_linhas_6100 = 1000
        Arquivo com 2.500 |6100| → 3 partições:
            parte_001: até 1.000 |6100|
            parte_002: até 1.000 |6100|
            parte_003: até   500 |6100|
    """
    if max_linhas_6100 < 1:
        max_linhas_6100 = 1

    try:
        texto = conteudo_bytes.decode("utf-8-sig", errors="replace")
    except Exception:
        texto = conteudo_bytes.decode("utf-8", errors="replace")

    linhas = texto.splitlines()

    linha_0000 = fmt_reg_0000(ni)

    # Acumuladores
    particoes:     list = []   # list[list[str]] — cada item é uma partição
    parte_atual:   list = []   # linhas da partição corrente
    cnt_6100_part: int  = 0    # contador de |6100| na partição corrente

    bloco_atual:   list = []   # linhas do bloco corrente (6000 + 6100 + 6110)
    cnt_6100_bloco: int = 0    # contador de |6100| no bloco corrente

    def _fechar_bloco_em_parte() -> None:
        """
        Fecha o bloco atual e decide se vai para a partição corrente
        ou para uma nova partição.
        """
        nonlocal parte_atual, cnt_6100_part, bloco_atual, cnt_6100_bloco

        if not bloco_atual:
            return

        # Se o bloco cabe na partição corrente (ou a partição está vazia)
        if cnt_6100_part == 0 or (cnt_6100_part + cnt_6100_bloco) <= max_linhas_6100:
            parte_atual.extend(bloco_atual)
            cnt_6100_part += cnt_6100_bloco
        else:
            # Fecha a partição corrente e abre uma nova
            if parte_atual:
                particoes.append(list(parte_atual))
            parte_atual   = list(bloco_atual)
            cnt_6100_part = cnt_6100_bloco

        bloco_atual    = []
        cnt_6100_bloco = 0

    for linha in linhas:
        linha_strip = linha.strip()

        if not linha_strip:
            continue
        if linha_strip.startswith("|0000|"):
            continue

        if linha_strip.startswith("|6000|"):
            _fechar_bloco_em_parte()
            bloco_atual    = [linha_strip]
            cnt_6100_bloco = 0

        elif linha_strip.startswith("|6100|"):
            bloco_atual.append(linha_strip)
            cnt_6100_bloco += 1

        elif linha_strip.startswith("|6110|"):
            bloco_atual.append(linha_strip)

        else:
            if bloco_atual:
                bloco_atual.append(linha_strip)

    # Fecha o último bloco e a última partição
    _fechar_bloco_em_parte()
    if parte_atual:
        particoes.append(parte_atual)

    # Monta os bytes de cada partição com nome sequencial
    resultado: dict = OrderedDict()

    for idx, linhas_part in enumerate(particoes, 1):
        chave         = f"parte_{idx:03d}"
        conteudo_part = linha_0000 + "\n" + "\n".join(linhas_part) + "\n"
        resultado[chave] = conteudo_part.encode("utf-8-sig")

    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# MONTAGEM DO ZIP COM TODAS AS PARTIÇÕES
# ═══════════════════════════════════════════════════════════════════════════════

def _montar_zip_particoes(particoes: dict,
                           nome_base: str,
                           ni: str) -> bytes:
    """
    Empacota todas as partições em um único arquivo ZIP.

    Parâmetros:
        particoes : dict {chave → bytes} — partições geradas
        nome_base : str — prefixo do nome dos arquivos dentro do ZIP
                         (ex: "lancamentos_12345678000195")
        ni        : str — CNPJ/CPF limpo (usado no nome dos arquivos)

    Retorna:
        bytes — conteúdo do arquivo ZIP pronto para download.

    Estrutura do ZIP:
        lancamentos_12345678000195_2024-01.txt
        lancamentos_12345678000195_2024-02.txt
        ...
        ou
        lancamentos_12345678000195_parte_001.txt
        lancamentos_12345678000195_parte_002.txt
        ...
    """
    buf_zip = io.BytesIO()

    with zipfile.ZipFile(buf_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for chave, conteudo_bytes in particoes.items():
            nome_arquivo = f"{nome_base}_{chave}.txt"
            zf.writestr(nome_arquivo, conteudo_bytes)

    buf_zip.seek(0)
    return buf_zip.read()


# ═══════════════════════════════════════════════════════════════════════════════
# RENDERIZAÇÃO DO PAINEL DE PARTICIONAMENTO NA UI STREAMLIT
# ═══════════════════════════════════════════════════════════════════════════════

def _render_painel_particoes(resultado_bytes: bytes,
                              ni: str,
                              nome_arquivo_base: str) -> None:
    """
    Renderiza o painel de particionamento na interface Streamlit.

    Exibe:
        1. Card de apresentação do módulo
        2. Seletor de modo: Por Mês | Por Linhas | Sem Partição
        3. Configuração específica do modo selecionado
        4. Botão de geração das partições
        5. Métricas das partições geradas
        6. Download individual de cada partição
        7. Download do ZIP com todas as partições

    Parâmetros:
        resultado_bytes   : bytes — arquivo de saída já gerado
        ni                : str  — CNPJ/CPF limpo
        nome_arquivo_base : str  — nome base para os arquivos (sem extensão)
    """
    if not resultado_bytes:
        return

    st.markdown("---")
    st.markdown(
        """
        <div class='part-box'>
            <b style='color:#00C896;font-size:15px;'>✂️ Particionamento do Arquivo</b><br>
            <small style='color:#9BB0C8;'>
                Divida o arquivo gerado em partes menores para facilitar
                a importação no Domínio Sistemas.
                Os lançamentos nunca são cortados no meio — cada bloco
                |6000|→|6100| permanece sempre inteiro na mesma partição.
            </small>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Seletor de modo ───────────────────────────────────────────────────────
    modo_part = st.radio(
        "Modo de particionamento:",
        ["🚫 Sem particionamento", "📅 Por Mês", "📏 Por Número de Linhas"],
        horizontal=True,
        key="radio_modo_particao",
    )

    # ── Sem particionamento — apenas exibe o download direto ─────────────────
    if modo_part == "🚫 Sem particionamento":
        n6100 = resultado_bytes.count(b"|6100|")
        n6000 = resultado_bytes.count(b"|6000|")
        st.caption(
            f"Arquivo único: {len(resultado_bytes)/1024:.1f} KB | "
            f"{n6000:,} lançamentos | {n6100:,} partidas"
        )
        return   # O download já está disponível na seção principal

    # ── Configuração do modo Por Linhas ──────────────────────────────────────
    max_linhas = 1000
    if modo_part == "📏 Por Número de Linhas":
        max_linhas = st.number_input(
            "Máximo de linhas |6100| por arquivo:",
            min_value=10,
            max_value=500_000,
            value=1_000,
            step=100,
            help=(
                "Cada partição terá no máximo este número de linhas |6100|. "
                "Lançamentos nunca são cortados no meio."
            ),
            key="num_max_linhas_part",
        )

    # ── Botão de geração ─────────────────────────────────────────────────────
    btn_part = st.button(
        "✂️ GERAR PARTIÇÕES",
        type="primary",
        use_container_width=True,
        key="btn_gerar_particoes",
    )

    if btn_part:
        with st.spinner("Particionando arquivo..."):

            if modo_part == "📅 Por Mês":
                particoes = _particionar_por_mes(resultado_bytes, ni)
                tipo_part = "mes"

            else:   # Por Número de Linhas
                particoes = _particionar_por_linhas(
                    resultado_bytes, ni, int(max_linhas)
                )
                tipo_part = "linhas"

        # Persiste no session_state para sobreviver ao rerun
        st.session_state["particoes"]      = particoes
        st.session_state["tipo_part"]      = tipo_part
        st.session_state["nome_base_part"] = nome_arquivo_base
        st.rerun()

    # ── Exibe resultado se já gerado ─────────────────────────────────────────
    if st.session_state.get("particoes"):
        particoes      = st.session_state["particoes"]
        tipo_part      = st.session_state.get("tipo_part", "mes")
        nome_base_part = st.session_state.get("nome_base_part", nome_arquivo_base)

        n_partes = len(particoes)

        # ── Métricas gerais ───────────────────────────────────────────────────
        st.markdown(f"#### ✂️ {n_partes} partição(ões) gerada(s)")

        total_6100 = sum(
            b.count(b"|6100|") for b in particoes.values()
        )
        total_kb = sum(len(b) for b in particoes.values()) / 1024

        m1, m2, m3 = st.columns(3)
        m1.metric("Partições",    f"{n_partes:,}")
        m2.metric("Total |6100|", f"{total_6100:,}")
        m3.metric("Tamanho total", f"{total_kb:.1f} KB")

        # ── Download do ZIP ───────────────────────────────────────────────────
        zip_bytes = _montar_zip_particoes(particoes, nome_base_part, ni)

        st.download_button(
            f"⬇ Baixar todas as partições (.zip) — {n_partes} arquivo(s)",
            data=zip_bytes,
            file_name=f"{nome_base_part}_particoes.zip",
            mime="application/zip",
            use_container_width=True,
            type="primary",
            key="dl_zip_particoes",
        )

        # ── Download individual por partição ──────────────────────────────────
        st.markdown("#### 📄 Download individual")

        # Exibe em colunas de 3
        chaves = list(particoes.keys())

        for i in range(0, len(chaves), 3):
            cols = st.columns(3)
            for j, chave in enumerate(chaves[i:i + 3]):
                conteudo_part = particoes[chave]
                n6100_p = conteudo_part.count(b"|6100|")
                n6000_p = conteudo_part.count(b"|6000|")
                kb_p    = len(conteudo_part) / 1024

                # Label amigável
                if tipo_part == "mes":
                    try:
                        ano, mes = chave.split("-")
                        label = datetime(int(ano), int(mes), 1).strftime("%b/%Y")
                    except Exception:
                        label = chave.replace("_", " ").title()
                else:
                    label = chave.replace("_", " ").title()

                with cols[j]:
                    st.markdown(
                        f"<div style='background:#0a1a0a;border:1px solid #00C896;"
                        f"border-radius:6px;padding:10px;margin:4px 0;'>"
                        f"<b style='color:#00C896;'>{label}</b><br>"
                        f"<small style='color:#9BB0C8;'>"
                        f"{n6000_p:,} lanç. | {n6100_p:,} partidas | {kb_p:.1f} KB"
                        f"</small></div>",
                        unsafe_allow_html=True,
                    )
                    st.download_button(
                        f"⬇ {label}",
                        data=conteudo_part,
                        file_name=f"{nome_base_part}_{chave}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key=f"dl_part_{chave}",
                    )
# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 11 — ESTADO DA SESSÃO + RENDERIZAÇÃO DE RESULTADOS V3.7.0
# Integra:
#   • _init_state()                    — inicializa todos os defaults do session_state
#   • _reset()                         — limpa o estado entre uploads
#   • _render_resultados_lote()        — renderiza resultado TXT/Excel (lotes)
#   • _render_resultados_ecd()         — renderiza resultado SPED ECD lançamentos
#   • _render_resultados_posicional()  — renderiza resultado TXT Posicional
#   • _render_resultados_saldo_inicial()— renderiza resultado Saldo Inicial
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# INICIALIZAÇÃO DO ESTADO DA SESSÃO
# ═══════════════════════════════════════════════════════════════════════════════

def _init_state() -> None:
    """
    Inicializa todas as chaves do st.session_state com valores padrão.

    Só atribui o valor se a chave ainda não existir — preserva o estado
    entre reruns sem sobrescrever dados já preenchidos pelo usuário.

    Grupos de chaves:
        Arquivos gerados:
            resultado_bytes     : bytes | None — arquivo de saída gerado
            resultado_nome      : str          — nome do arquivo para download
            erros_bytes         : bytes | None — relatório de erros
            erros_nome          : str
            log_bytes           : bytes | None — log completo para download
            log_nome            : str

        Dados de processamento:
            log_linhas          : list[str]    — linhas do log para exibição na UI
            resumo              : list[dict]   — métricas por lote (TXT/Excel)
            erros_lote          : list[dict]   — lotes desbalanceados
            metricas            : dict         — métricas para exibição (st.metric)

        Detecção de leiaute:
            tipo_detectado      : str | None   — "ecd"|"lote"|"excel"|"dominio_pos"|"ecd_saldo"
            deteccao            : dict | None  — resultado completo de validar_e_identificar_arquivo()

        Excel:
            sheets              : list[str]    — abas disponíveis no Excel
            sheet_sel           : str          — aba selecionada

        Arquivo atual:
            arquivo_bytes       : bytes | None — conteúdo do arquivo carregado
            arquivo_nome        : str          — nome do arquivo carregado
            processado          : bool         — True se o arquivo já foi processado

        SPED ECD:
            cnpj_ecd            : str          — CNPJ extraído do 0000 (14 dígitos)
            cnpj_ecd_fmt        : str          — CNPJ formatado (00.000.000/0001-00)

        Filiais:
            mapa_filiais_df     : pd.DataFrame | None — tabela De/Para de filiais
            filiais_detectadas  : list[str]    — filiais únicas detectadas no arquivo

        Saldo Inicial:
            modo_saldo_inicial  : bool         — True se o módulo Saldo Inicial está ativo
            hist_prefixo_si     : str          — prefixo do histórico
            modo_resultado_si   : str          — "apenas_patrimonial"|"aberto_com_resultado"
            conta_pl_resultado_si: str         — código da conta PL/Resultado
            conta_pl_sugerida   : str          — sugerida automaticamente pelo pré-scan
            conta_pl_sugerida_nome: str        — nome da conta sugerida

        Particionamento:
            particoes           : dict | None  — {chave → bytes} das partições geradas
            tipo_part           : str          — "mes"|"linhas"
            nome_base_part      : str          — prefixo dos nomes dos arquivos

        Comparação I052:
            i052_resultado      : dict | None  — resultado de _comparar_i052()
            i052_parsed_ant     : dict | None  — parsed do arquivo anterior
            i052_parsed_atu     : dict | None  — parsed do arquivo atual
            i052_label_ant      : str          — nome do arquivo anterior
            i052_label_atu      : str          — nome do arquivo atual
            i052_log            : list[str]    — log da comparação
    """
    defaults = {
        # Arquivos gerados
        "resultado_bytes":          None,
        "resultado_nome":           "saida.txt",
        "erros_bytes":              None,
        "erros_nome":               "erros.txt",
        "log_bytes":                None,
        "log_nome":                 "log.txt",

        # Dados de processamento
        "log_linhas":               [],
        "resumo":                   [],
        "erros_lote":               [],
        "metricas":                 {},

        # Detecção de leiaute
        "tipo_detectado":           None,
        "deteccao":                 None,

        # Excel
        "sheets":                   [],
        "sheet_sel":                "",

        # Arquivo atual
        "arquivo_bytes":            None,
        "arquivo_nome":             "",
        "processado":               False,

        # SPED ECD
        "cnpj_ecd":                 "",
        "cnpj_ecd_fmt":             "",

        # Filiais
        "mapa_filiais_df":          None,
        "filiais_detectadas":       [],

        # Saldo Inicial
        "modo_saldo_inicial":       False,
        "hist_prefixo_si":          "SALDO INICIAL",
        "modo_resultado_si":        "apenas_patrimonial",
        "conta_pl_resultado_si":    "",
        "conta_pl_sugerida":        "",
        "conta_pl_sugerida_nome":   "",

        # Particionamento
        "particoes":                None,
        "tipo_part":                "mes",
        "nome_base_part":           "lancamentos",

        # Comparação I052
        "i052_resultado":           None,
        "i052_parsed_ant":          None,
        "i052_parsed_atu":          None,
        "i052_label_ant":           "",
        "i052_label_atu":           "",
        "i052_log":                 [],
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ═══════════════════════════════════════════════════════════════════════════════
# RESET DO ESTADO (entre uploads)
# ═══════════════════════════════════════════════════════════════════════════════

def _reset() -> None:
    """
    Limpa o estado de processamento entre uploads de arquivos.

    Preserva intencionalmente:
        - mapa_filiais_df       — o usuário pode ter editado o De/Para
        - conta_pl_sugerida     — sugestão automática (será reatribuída pelo pré-scan)
        - i052_*                — resultado da comparação (aba independente)
        - Configurações de UI   — hist_prefixo_si, modo_resultado_si, etc.

    Zera:
        - Todos os bytes gerados (resultado, erros, log)
        - Resumo, erros_lote, métricas
        - Tipo detectado, detecção, sheets
        - CNPJ ECD, filiais detectadas
        - Flag processado
        - Partições
    """
    # Chaves que voltam para lista vazia
    _listas = (
        "log_linhas", "resumo", "erros_lote",
        "sheets", "filiais_detectadas", "i052_log",
    )
    # Chaves que voltam para None
    _nones = (
        "resultado_bytes", "erros_bytes", "log_bytes",
        "tipo_detectado", "deteccao",
        "arquivo_bytes", "particoes",
        "i052_resultado", "i052_parsed_ant", "i052_parsed_atu",
    )
    # Chaves que voltam para False
    _falsos = ("processado", "modo_saldo_inicial")

    # Chaves que voltam para string vazia
    _strings = (
        "resultado_nome", "erros_nome", "log_nome",
        "arquivo_nome", "cnpj_ecd", "cnpj_ecd_fmt",
        "sheet_sel", "tipo_part", "nome_base_part",
        "conta_pl_sugerida", "conta_pl_sugerida_nome",
        "i052_label_ant", "i052_label_atu",
    )

    for k in _listas:
        st.session_state[k] = []

    for k in _nones:
        st.session_state[k] = None

    for k in _falsos:
        st.session_state[k] = False

    for k in _strings:
        st.session_state[k] = ""

    st.session_state["metricas"] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# RENDERIZAÇÃO — RESULTADOS TXT/EXCEL (LOTES)
# ═══════════════════════════════════════════════════════════════════════════════

def _render_resultados_lote(exibir_log: bool) -> None:
    """
    Renderiza o painel de resultados para conversões de TXT Lote e Excel.

    Seções exibidas:
        1. Título e métricas gerais (st.metric)
        2. Card de status (OK / erro)
        3. Barra de progresso de lotes balanceados
        4. Totais de débito, crédito e diferença geral
        5. Tabela de detalhe por lote com filtro (Todos / OK / Erro)
        6. Diagnóstico expandido dos lotes desbalanceados
        7. Seção de downloads (arquivo, erros, log)
        8. Painel de particionamento (Bloco 10)
        9. Log de processamento (opcional)

    Parâmetros:
        exibir_log : bool — se True, exibe o log na UI
    """
    resumo  = st.session_state.resumo    or []
    erros   = st.session_state.erros_lote or []
    metricas = st.session_state.metricas  or {}

    st.markdown("---")
    st.markdown("## 📊 Resultado da Conversão")

    # ── Métricas gerais ───────────────────────────────────────────────────────
    if metricas:
        cols = st.columns(len(metricas))
        for i, (k, v) in enumerate(metricas.items()):
            cols[i].metric(k, v)

    # ── Totais e status ───────────────────────────────────────────────────────
    if resumo:
        total    = len(resumo)
        n_ok     = sum(1 for v in resumo if v["balanceado"])
        n_err    = total - n_ok
        pct_ok   = n_ok / total if total > 0 else 0.0

        td_total  = sum(v["total_debito"]  for v in resumo)
        tc_total  = sum(v["total_credito"] for v in resumo)
        dif_geral = round(abs(td_total - tc_total), 2)
        tudo_ok   = dif_geral < TOL_VALOR and n_err == 0

        # Card de status
        if tudo_ok:
            st.markdown(
                "<div class='card-ok'>"
                "<span style='font-size:22px;'>✅</span> "
                "<b style='color:#00C896;font-size:18px;'>"
                "Todos os lotes balanceados.</b></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div class='card-err'>"
                f"<span style='font-size:22px;'>⚠️</span> "
                f"<b style='color:#FF4444;font-size:18px;'>"
                f"{n_err} lote(s) desbalanceado(s).</b></div>",
                unsafe_allow_html=True,
            )

        # Barra de progresso
        col_barra, col_nums = st.columns([3, 1])
        with col_barra:
            st.progress(pct_ok)
            st.caption(
                f"{n_ok:,} de {total:,} lotes balanceados "
                f"({pct_ok * 100:.1f}%)"
            )
        with col_nums:
            st.metric("✅ Balanceados", f"{n_ok:,}")
            st.metric("❌ Com erro",    f"{n_err:,}")

        # Totais financeiros
        col_d, col_c, col_dif = st.columns(3)
        col_d.metric("Total Débito",   f"R$ {td_total:,.2f}")
        col_c.metric("Total Crédito",  f"R$ {tc_total:,.2f}")
        col_dif.metric(
            "Diferença Geral",
            f"R$ {dif_geral:,.2f}",
            delta="OK" if tudo_ok else f"R$ {dif_geral:,.2f}",
            delta_color="normal" if tudo_ok else "inverse",
        )

    # ── Tabela de detalhe por lote ────────────────────────────────────────────
    if resumo:
        st.markdown("#### 📋 Detalhe por Lote")

        filtro = st.radio(
            "Exibir lotes:",
            ["Todos", "✅ Somente OK", "❌ Somente com erro"],
            horizontal=True,
            key="filtro_lotes_radio",
        )

        rows = []
        for v in resumo:
            if filtro == "✅ Somente OK"       and not v["balanceado"]: continue
            if filtro == "❌ Somente com erro"  and     v["balanceado"]: continue
            rows.append({
                "Lote":      v["num_lote"],
                "Linhas":    v["faixa_linhas"],
                "Data":      v["data"],
                "Qtd":       v["qtd_linhas"],
                "Débito":    v["total_debito"],
                "Crédito":   v["total_credito"],
                "Diferença": v["diferenca"],
                "Status":    "✔ OK" if v["balanceado"] else "✖ ERRO",
            })

        if rows:
            df_res = pd.DataFrame(rows)
            styled = (
                df_res.style
                .map(
                    lambda v: (
                        "color:#00C896;font-weight:700"
                        if v == "✔ OK"
                        else "color:#FF4444;font-weight:700"
                    ),
                    subset=["Status"],
                )
                .map(
                    lambda v: (
                        "color:#FF4444"
                        if v > TOL_VALOR
                        else "color:#00C896"
                    ),
                    subset=["Diferença"],
                )
                .format({
                    "Débito":    "R$ {:,.2f}",
                    "Crédito":   "R$ {:,.2f}",
                    "Diferença": "R$ {:,.2f}",
                })
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Diagnóstico dos lotes desbalanceados ──────────────────────────────────
    if erros:
        st.markdown("#### 🔍 Diagnóstico dos Lotes Desbalanceados")

        for e in erros:
            diag  = e.get("diagnostico", {})
            label = (
                f"Lote {e['num_lote']}  │  "
                f"Linhas {e['faixa_linhas']}  │  "
                f"Data {e['data']}  │  "
                f"Dif. R$ {e['diferenca']:,.2f}"
            )

            with st.expander(label, expanded=(len(erros) == 1)):

                # Sugestão
                if diag.get("sugestao"):
                    st.markdown(
                        f"<div class='card-warn'>"
                        f"💡 <b style='color:#FFD166;'>Sugestão:</b> "
                        f"{diag['sugestao']}</div>",
                        unsafe_allow_html=True,
                    )

                # Métricas do lote
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Débito",    f"R$ {diag.get('total_debito',  0):,.2f}")
                c2.metric("Crédito",   f"R$ {diag.get('total_credito', 0):,.2f}")
                c3.metric("Diferença", f"R$ {diag.get('diferenca',     0):,.2f}")
                c4.metric(
                    "Partidas",
                    f"D:{diag.get('qtd_debitos', 0)} / "
                    f"C:{diag.get('qtd_creditos', 0)}"
                )

                # Linhas suspeitas
                for s in diag.get("suspeitas", []):
                    tp  = "DÉBITO" if s["tipo"] == "D" else "CRÉDITO"
                    cta = s["conta_debito"] or s["conta_credito"]
                    st.markdown(
                        f"- Linha `{s['linha_origem']}` — "
                        f"**{tp}** Cta `{cta}` — "
                        f"R$ `{s['valor']:,.2f}` — {s['motivo']}"
                    )

                # Tabela detalhada das partidas do lote
                if diag.get("linhas"):
                    df_det = pd.DataFrame(diag["linhas"])
                    cols_show = [
                        c for c in [
                            "linha_origem", "tipo", "conta_debito",
                            "conta_credito", "valor", "descricao",
                        ]
                        if c in df_det.columns
                    ]
                    st.dataframe(
                        df_det[cols_show].style
                        .map(
                            lambda v: (
                                "color:#6EC6FF;font-weight:700"
                                if v == "D"
                                else "color:#FF9EBC;font-weight:700"
                            ),
                            subset=["tipo"],
                        )
                        .format({"valor": "R$ {:,.2f}"}),
                        use_container_width=True,
                        hide_index=True,
                    )

    # ── Downloads ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ⬇ Downloads")

    dl1, dl2, dl3 = st.columns(3)
    n_err = len(erros)
    n_ok  = len(resumo) - n_err

    with dl1:
        if st.session_state.resultado_bytes:
            if n_err == 0:
                st.success(f"✅ {n_ok:,} lotes — arquivo pronto!")
            else:
                st.warning(f"⚠ {n_ok:,} OK / {n_err:,} com erro")

            st.download_button(
                "⬇ Baixar arquivo convertido",
                data=st.session_state.resultado_bytes,
                file_name=st.session_state.resultado_nome,
                mime="text/plain",
                use_container_width=True,
                type="primary",
                key="dl_resultado_lote",
            )

    with dl2:
        if erros:
            linhas_err = [
                "RELATÓRIO DE LOTES DESBALANCEADOS",
                "=" * 60, "",
                f"Data/Hora  : {ts_log()}",
                f"Total erros: {len(erros):,}",
                "", "=" * 60, "",
            ]
            for e in erros:
                linhas_err += [
                    f"Lote: {e['num_lote']}  │  "
                    f"Data: {e['data']}  │  "
                    f"Dif: R$ {e['diferenca']:,.2f}",
                    "",
                ]
            st.error(f"❌ {len(erros):,} lote(s) com erro.")
            st.download_button(
                "⬇ Baixar relatório de erros",
                data="\n".join(linhas_err).encode("utf-8-sig"),
                file_name="erros_lotes.txt",
                mime="text/plain",
                use_container_width=True,
                key="dl_erros_lote",
            )
        elif st.session_state.erros_bytes:
            st.download_button(
                "⬇ Baixar relatório de erros",
                data=st.session_state.erros_bytes,
                file_name=st.session_state.erros_nome,
                mime="text/plain",
                use_container_width=True,
                key="dl_erros_lote_alt",
            )

    with dl3:
        if st.session_state.log_bytes:
            st.download_button(
                "⬇ Baixar log completo",
                data=st.session_state.log_bytes,
                file_name=st.session_state.log_nome,
                mime="text/plain",
                use_container_width=True,
                key="dl_log_lote",
            )

    # ── Particionamento (Bloco 10) ────────────────────────────────────────────
    if st.session_state.resultado_bytes:
        ni_part = st.session_state.get("cnpj_ecd", "") or "00000000000000"
        nome_base = st.session_state.resultado_nome.replace(".txt", "")
        _render_painel_particoes(
            st.session_state.resultado_bytes,
            ni_part,
            nome_base,
        )

    # ── Log de processamento ──────────────────────────────────────────────────
    if exibir_log and st.session_state.log_linhas:
        st.markdown("#### 🖥 Log de Processamento")
        log_txt  = "\n".join(str(l) for l in st.session_state.log_linhas)
        tem_erro = any("ERRO" in str(l).upper() for l in st.session_state.log_linhas)
        st.markdown(
            f"<div class='bloco-log' style='border-color:"
            f"{'#FF4444' if tem_erro else '#1A3050'};'>"
            f"{log_txt}</div>",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# RENDERIZAÇÃO — RESULTADOS SPED ECD LANÇAMENTOS
# ═══════════════════════════════════════════════════════════════════════════════

def _render_resultados_ecd(exibir_log: bool) -> None:
    """
    Renderiza o painel de resultados para conversões de SPED ECD — Lançamentos.

    Seções exibidas:
        1. Título e métricas (st.metric)
        2. Downloads (arquivo convertido + relatório de erros)
        3. Particionamento (Bloco 10)
        4. Log de processamento (opcional)

    Parâmetros:
        exibir_log : bool — se True, exibe o log na UI
    """
    metricas = st.session_state.metricas or {}

    st.markdown("---")
    st.markdown("## 📊 Resultado da Conversão — SPED ECD")

    # Métricas
    if metricas:
        cols = st.columns(len(metricas))
        for i, (k, v) in enumerate(metricas.items()):
            cols[i].metric(k, v)

    # Downloads
    st.markdown("#### ⬇ Downloads")
    dl1, dl2 = st.columns(2)

    with dl1:
        if st.session_state.resultado_bytes:
            st.success("Arquivo gerado com sucesso!")
            st.download_button(
                "⬇ Baixar arquivo convertido",
                data=st.session_state.resultado_bytes,
                file_name=st.session_state.resultado_nome,
                mime="text/plain",
                use_container_width=True,
                type="primary",
                key="dl_resultado_ecd",
            )

    with dl2:
        if st.session_state.erros_bytes:
            st.warning("Arquivo de erros disponível.")
            st.download_button(
                "⬇ Baixar relatório de erros",
                data=st.session_state.erros_bytes,
                file_name=st.session_state.erros_nome,
                mime="text/plain",
                use_container_width=True,
                key="dl_erros_ecd",
            )

    # Particionamento
    if st.session_state.resultado_bytes:
        ni_part  = st.session_state.get("cnpj_ecd", "") or "00000000000000"
        nome_base = st.session_state.resultado_nome.replace(".txt", "")
        _render_painel_particoes(
            st.session_state.resultado_bytes,
            ni_part,
            nome_base,
        )

    # Log
    if exibir_log and st.session_state.log_linhas:
        st.markdown("#### 🖥 Log de Processamento")
        log_txt  = "\n".join(str(l) for l in st.session_state.log_linhas)
        tem_erro = any("ERRO" in str(l).upper() for l in st.session_state.log_linhas)
        st.markdown(
            f"<div class='bloco-log' style='border-color:"
            f"{'#FF4444' if tem_erro else '#1A3050'};'>"
            f"{log_txt}</div>",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# RENDERIZAÇÃO — RESULTADOS TXT POSICIONAL DOMÍNIO
# ═══════════════════════════════════════════════════════════════════════════════

def _render_resultados_posicional(exibir_log: bool) -> None:
    """
    Renderiza o painel de resultados para conversões de TXT Posicional Domínio.

    Seções exibidas:
        1. Título e métricas (st.metric)
        2. Downloads (arquivo convertido + relatório de erros)
        3. Particionamento (Bloco 10)
        4. Log de processamento (opcional)

    Parâmetros:
        exibir_log : bool — se True, exibe o log na UI
    """
    metricas = st.session_state.metricas or {}

    st.markdown("---")
    st.markdown("## 📊 Resultado — Leiaute Posicional Domínio")

    # Métricas
    if metricas:
        cols = st.columns(len(metricas))
        for i, (k, v) in enumerate(metricas.items()):
            cols[i].metric(k, v)

    # Downloads
    st.markdown("#### ⬇ Downloads")
    dl1, dl2 = st.columns(2)

    with dl1:
        if st.session_state.resultado_bytes:
            st.success("✅ Arquivo convertido com sucesso!")
            st.download_button(
                "⬇ Baixar arquivo convertido",
                data=st.session_state.resultado_bytes,
                file_name=st.session_state.resultado_nome,
                mime="text/plain",
                use_container_width=True,
                type="primary",
                key="dl_resultado_pos",
            )

    with dl2:
        if st.session_state.erros_bytes:
            st.warning("⚠ Há registros com erros de parse.")
            st.download_button(
                "⬇ Baixar relatório de erros",
                data=st.session_state.erros_bytes,
                file_name=st.session_state.erros_nome,
                mime="text/plain",
                use_container_width=True,
                key="dl_erros_pos",
            )

    # Particionamento
    if st.session_state.resultado_bytes:
        ni_part   = st.session_state.resultado_nome.split("_")[2] \
            if "_" in st.session_state.resultado_nome else "00000000000000"
        nome_base = st.session_state.resultado_nome.replace(".txt", "")
        _render_painel_particoes(
            st.session_state.resultado_bytes,
            ni_part,
            nome_base,
        )

    # Log
    if exibir_log and st.session_state.log_linhas:
        st.markdown("#### 🖥 Log de Processamento")
        log_txt  = "\n".join(str(l) for l in st.session_state.log_linhas)
        tem_erro = any("ERRO" in str(l).upper() for l in st.session_state.log_linhas)
        st.markdown(
            f"<div class='bloco-log' style='border-color:"
            f"{'#FF4444' if tem_erro else '#1A3050'};'>"
            f"{log_txt}</div>",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# RENDERIZAÇÃO — RESULTADOS SALDO INICIAL
# ═══════════════════════════════════════════════════════════════════════════════

def _render_resultados_saldo_inicial(exibir_log: bool) -> None:
    """
    Renderiza o painel de resultados para o módulo Saldo Inicial.

    Seções exibidas:
        1. Título
        2. Métricas em blocos de 5 colunas
        3. Card de status: Balanceado (OK) ou Desbalanceado (erro)
        4. Downloads em 3 colunas:
               col1 — arquivo de saldo inicial
               col2 — relatório de erros (se houver)
               col3 — log completo
        5. Particionamento (Bloco 10)
        6. Log de processamento (opcional)

    Parâmetros:
        exibir_log : bool — se True, exibe o log na UI
    """
    metricas = st.session_state.metricas or {}

    st.markdown("---")
    st.markdown("## 📊 Resultado — Saldo Inicial (SPED ECD → Domínio)")

    # Métricas em blocos de 5
    if metricas:
        items = list(metricas.items())
        for inicio in range(0, len(items), 5):
            bloco = items[inicio:inicio + 5]
            cols  = st.columns(len(bloco))
            for i, (k, v) in enumerate(bloco):
                cols[i].metric(k, v)

    # Card de status
    bal = metricas.get("Balanceado", "")

    if bal == "SIM":
        st.markdown(
            "<div class='card-ok'>"
            "<span style='font-size:22px;'>✅</span> "
            "<b style='color:#00C896;font-size:18px;'>"
            "Lançamento de saldo inicial balanceado (D = C).</b>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='card-err'>"
            "<span style='font-size:22px;'>⚠️</span> "
            "<b style='color:#FF4444;font-size:18px;'>"
            "Lançamento DESBALANCEADO — "
            "verifique a conta de PL/Resultado informada.</b>"
            "</div>",
            unsafe_allow_html=True,
        )

    # Downloads
    st.markdown("#### ⬇ Downloads")
    dl1, dl2, dl3 = st.columns(3)

    with dl1:
        if st.session_state.resultado_bytes:
            if bal == "SIM":
                st.success("✅ Arquivo de saldo inicial gerado!")
            else:
                st.warning("⚠ Arquivo gerado com diferença.")

            st.download_button(
                "⬇ Baixar saldo inicial (.txt)",
                data=st.session_state.resultado_bytes,
                file_name=st.session_state.resultado_nome,
                mime="text/plain",
                use_container_width=True,
                type="primary",
                key="dl_resultado_si",
            )

    with dl2:
        if st.session_state.erros_bytes:
            st.error("❌ Há erros — baixe o relatório.")
            st.download_button(
                "⬇ Baixar relatório de erros",
                data=st.session_state.erros_bytes,
                file_name=st.session_state.erros_nome,
                mime="text/plain",
                use_container_width=True,
                key="dl_erros_si",
            )

    with dl3:
        if st.session_state.log_linhas:
            log_txt = "\n".join(str(l) for l in st.session_state.log_linhas)
            st.download_button(
                "⬇ Baixar log",
                data=log_txt.encode("utf-8-sig"),
                file_name="log_saldo_inicial.txt",
                mime="text/plain",
                use_container_width=True,
                key="dl_log_si",
            )

    # Particionamento
    if st.session_state.resultado_bytes:
        ni_part   = st.session_state.get("cnpj_ecd", "") or "00000000000000"
        nome_base = st.session_state.resultado_nome.replace(".txt", "")
        _render_painel_particoes(
            st.session_state.resultado_bytes,
            ni_part,
            nome_base,
        )

    # Log de processamento
    if exibir_log and st.session_state.log_linhas:
        st.markdown("#### 🖥 Log de Processamento")
        log_txt  = "\n".join(str(l) for l in st.session_state.log_linhas)
        tem_erro = any(
            "ERRO" in str(l).upper() or "NAO" in str(l).upper()
            for l in st.session_state.log_linhas
        )
        st.markdown(
            f"<div class='bloco-log' style='border-color:"
            f"{'#FF4444' if tem_erro else '#1A3050'};'>"
            f"{log_txt}</div>",
            unsafe_allow_html=True,
        )
		
# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 12 — MAIN() — UI COMPLETA V3.7.0
# Integra:
#   • apply_theme()                    — CSS e tema (Bloco 1)
#   • _init_state() / _reset()         — estado da sessão (Bloco 11)
#   • validar_e_identificar_arquivo()  — detecção precisa de leiaute (Bloco 3)
#   • _render_painel_deteccao()        — painel de identificação (Bloco 3)
#   • processar_ecd_lancamentos()      — SPED ECD lançamentos (Bloco 4)
#   • processar_saldo_inicial_ecd()    — Saldo Inicial ECD (Bloco 5)
#   • processar_streaming()            — TXT separado por ";" (Bloco 6)
#   • processar_excel()                — Excel (Bloco 7)
#   • processar_dominio_posicional()   — TXT Posicional (Bloco 8)
#   • _parse_i052_completo()           — parse I052 (Bloco 9)
#   • _comparar_i052()                 — comparação I052 (Bloco 9)
#   • _render_comparacao_i052()        — renderização I052 (Bloco 9)
#   • _render_painel_particoes()       — particionamento (Bloco 10)
#   • _render_resultados_*()           — renderização de resultados (Bloco 11)
#
# Novidades V3.7.0 sobre V3.6.2:
#   • validar_e_identificar_arquivo() substitui identificar_tipo()
#   • _render_painel_deteccao() exibe badge + confiança + metadados do 0000
#   • processar_ecd_lancamentos() suporta map_contas + cc_map + gerar_6110
#   • Painel de particionamento integrado em todos os módulos de resultado
#   • Aba I052 com log persistido e download CSV
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    """
    Ponto de entrada da aplicação Streamlit V3.7.0.

    Estrutura:
        Sidebar   — configurações globais (log, versão, formatos suportados)
        Aba 1     — Conversor / Saldo Inicial
                      • Upload do arquivo
                      • Detecção de leiaute (validar_e_identificar_arquivo)
                      • Configuração por tipo (Excel → aba/cabeçalho,
                        ECD → CNPJ + DE/PARA + CC, Posicional → De/Para filiais)
                      • Módulo Saldo Inicial (ECD)
                      • Botão CONVERTER + barra de progresso
                      • Renderização de resultados + downloads + particionamento
        Aba 2     — Comparar I052
                      • Upload de dois ECDs (anterior + atual)
                      • Botão COMPARAR
                      • Renderização do resultado da comparação
    """

    # ── Configuração da página ────────────────────────────────────────────────
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
        f"<h2 style='color:#FF6B00;margin:0;'>"
        f"Domínio Sistemas — Conversor Unificado</h2>"
        f"<p style='color:#6B7A8D;margin:6px 0 0;'>"
        f"Lançamentos Contábeis (TXT / Excel / Posicional) &nbsp;|&nbsp; "
        f"SPED ECD &nbsp;→&nbsp; 0000 + 6000 + 6100 &nbsp;|&nbsp; "
        f"Saldo Inicial ECD &nbsp;|&nbsp; "
        f"<b style='color:#FF6B00;'>Thomson Reuters</b>"
        f"&nbsp;|&nbsp; <small>{VERSAO}</small></p></div>",
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
            "- 📊 Excel (`.xlsx` / `.xls`)\n"
            "- 📄 TXT separado por `;`\n"
            "- 📋 SPED ECD (`.txt`) — lançamentos\n"
            "- 📋 SPED ECD (`.txt`) — saldo inicial\n"
            "- 📋 TXT Posicional Domínio"
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
        "🔄 Conversor / Saldo Inicial",
        "🔍 Comparar I052 entre ECDs",
    ])

    # ═════════════════════════════════════════════════════════════════════════
    # ABA 2 — COMPARAÇÃO I052 (independente do upload principal)
    # ═════════════════════════════════════════════════════════════════════════
    with aba_i052:
        st.markdown("### 🔍 Comparação de I052 — ECD Anterior vs. ECD Atual")
        st.markdown(
            "<div class='info-box'>"
            "Suba os dois arquivos SPED ECD. O sistema irá:<br>"
            "① Extrair os <b>I052</b> (vínculos conta → COD_AGL) de cada arquivo<br>"
            "② Comparar o <b>saldo final</b> de cada COD_AGL no anterior com o "
            "<b>saldo inicial</b> no atual "
            "(<code>REGRA_VALIDA_BALANCO_SALDO_INI</code>)<br>"
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
            type="primary",
            use_container_width=True,
            key="btn_comparar_i052",
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

        # Renderiza resultado se já existe no session_state
        if st.session_state.get("i052_resultado"):
            _render_comparacao_i052(
                st.session_state["i052_resultado"],
                st.session_state["i052_label_ant"],
                st.session_state["i052_label_atu"],
                st.session_state["i052_parsed_ant"],
                st.session_state["i052_parsed_atu"],
            )

            # Download do log da comparação
            if st.session_state.get("i052_log"):
                log_i052_txt = "\n".join(st.session_state["i052_log"])
                st.download_button(
                    "⬇ Baixar log da comparação",
                    data=log_i052_txt.encode("utf-8-sig"),
                    file_name="log_comparacao_i052.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key="dl_log_i052",
                )

                if exibir_log:
                    st.markdown("#### 🖥 Log")
                    st.markdown(
                        f"<div class='bloco-log'>{log_i052_txt}</div>",
                        unsafe_allow_html=True,
                    )

    # ═════════════════════════════════════════════════════════════════════════
    # ABA 1 — CONVERSOR / SALDO INICIAL
    # ═════════════════════════════════════════════════════════════════════════
    with aba_conv:

        # ── Passo 1: Upload ───────────────────────────────────────────────────
        st.markdown("#### 📂 Passo 1 — Selecionar Arquivo")
        uploaded = st.file_uploader(
            f"Arraste ou clique (Excel, TXT separado por ';', SPED ECD ou "
            f"TXT Posicional — máx. {MAX_UPLOAD_MB} MB)",
            type=["xlsx", "xls", "xlsm", "txt", "csv"],
            key="upload_principal",
        )

        if uploaded is None:
            st.markdown(
                "<div class='info-box'>⬆ Selecione um arquivo para começar.</div>",
                unsafe_allow_html=True,
            )
            return   # Encerra sem st.stop() — não afeta aba_i052

        # ── Leitura e detecção do arquivo ─────────────────────────────────────
        conteudo = uploaded.read()
        mb = len(conteudo) / (1024 * 1024)

        if mb > MAX_UPLOAD_MB:
            st.error(
                f"⛔ Arquivo muito grande ({mb:.1f} MB). "
                f"Limite: {MAX_UPLOAD_MB} MB."
            )
            return

        # Detecta se é um arquivo novo (conteúdo ou nome mudou)
        arquivo_novo = (
            conteudo != st.session_state.get("arquivo_bytes")
            or uploaded.name != st.session_state.get("arquivo_nome", "")
        )

        if arquivo_novo:
            _reset()
            st.session_state["arquivo_bytes"] = conteudo
            st.session_state["arquivo_nome"]  = uploaded.name

            # ── Detecção precisa de leiaute (V3.7.0) ─────────────────────────
            deteccao = validar_e_identificar_arquivo(uploaded.name, conteudo)
            st.session_state["deteccao"]       = deteccao
            st.session_state["tipo_detectado"] = deteccao["tipo"]

            # Pré-processamentos específicos por tipo
            tipo_det = deteccao["tipo"]

            if tipo_det == "excel":
                try:
                    xl = pd.ExcelFile(io.BytesIO(conteudo), engine="openpyxl")
                    st.session_state["sheets"]    = xl.sheet_names
                    st.session_state["sheet_sel"] = (
                        "Plan1"
                        if "Plan1" in xl.sheet_names
                        else xl.sheet_names[0]
                    )
                except Exception:
                    st.session_state["sheets"] = []

            elif tipo_det == "ecd":
                # Extrai CNPJ do 0000 sem processar o arquivo inteiro
                cnpj_num = _pre_scan_cnpj_ecd(conteudo)
                st.session_state["cnpj_ecd"]     = cnpj_num
                st.session_state["cnpj_ecd_fmt"] = (
                    fmt_cnpj(cnpj_num) if cnpj_num else ""
                )
                # Sugere conta PL sem processar o arquivo inteiro
                _pre_scan_conta_pl_sugerida(conteudo)

                # Usa metadados extraídos pelo validar_e_identificar_arquivo
                if deteccao.get("cnpj") and not cnpj_num:
                    st.session_state["cnpj_ecd"]     = deteccao["cnpj"]
                    st.session_state["cnpj_ecd_fmt"] = fmt_cnpj(deteccao["cnpj"])

            elif tipo_det == "dominio_pos":
                filiais = _pre_scan_posicional(conteudo)
                st.session_state["filiais_detectadas"] = filiais
                _pre_popular_mapa_filiais(filiais)

        # Recupera estado atual
        deteccao = st.session_state.get("deteccao") or {}
        tipo     = st.session_state.get("tipo_detectado", "lote")

        # ── Painel de detecção (V3.7.0) ───────────────────────────────────────
        if deteccao:
            _render_painel_deteccao(deteccao, uploaded.name, len(conteudo))
            # _render_painel_deteccao chama st.stop() se tipo == "desconhecido"

        st.markdown("")

        # ── Passo 2: Configuração por tipo ────────────────────────────────────
        sheet_sel = ""
        linha_h   = 3
        auto_head = True

        # ── Excel ──────────────────────────────────────────────────────────────
        if tipo == "excel" and st.session_state.get("sheets"):
            st.markdown("#### 📋 Passo 2 — Configurar Excel")
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                sheet_sel = st.selectbox(
                    "Aba (Sheet)",
                    st.session_state["sheets"],
                    index=(
                        st.session_state["sheets"].index(st.session_state["sheet_sel"])
                        if st.session_state["sheet_sel"] in st.session_state["sheets"]
                        else 0
                    ),
                )
                st.session_state["sheet_sel"] = sheet_sel

            with col2:
                auto_head = st.checkbox(
                    "Detectar cabeçalho automaticamente", value=True
                )

            with col3:
                if not auto_head:
                    linha_h = (
                        st.number_input(
                            "Linha do cabeçalho",
                            min_value=1, max_value=50, value=4,
                        ) - 1
                    )

        # ── CNPJ para ECD ──────────────────────────────────────────────────────
        ni      = ""
        ok_insc = False
        ti      = ""
        inf     = ""

        if tipo == "ecd":
            st.markdown("#### 🏢 Passo 2 — CNPJ (preenchido automaticamente)")
            cnpj_ecd = st.session_state.get("cnpj_ecd", "")

            if cnpj_ecd and validar_cnpj(cnpj_ecd):
                st.markdown(
                    f"<div class='cnpj-auto'>✔ CNPJ extraído: "
                    f"<span>{st.session_state['cnpj_ecd_fmt']}</span></div>",
                    unsafe_allow_html=True,
                )
                st.code(fmt_reg_0000(cnpj_ecd), language=None)
                ok_insc = True
                ti      = "CNPJ"
                ni      = cnpj_ecd
                inf     = st.session_state["cnpj_ecd_fmt"]
            else:
                st.warning("⚠ CNPJ não encontrado. Informe manualmente.")
                cnpj_raw = st.text_input(
                    "CNPJ / CPF",
                    placeholder="00.000.000/0001-00",
                    key="cnpj_manual_ecd",
                )
                ok_insc, ti, ni = validar_inscricao(cnpj_raw)
                if cnpj_raw:
                    if ok_insc:
                        inf = fmt_cnpj(ni) if ti == "CNPJ" else fmt_cpf(ni)
                        st.success(f"✔ {ti} válido: {inf}")
                    else:
                        st.error("✖ CNPJ/CPF inválido")

            # ── DE/PARA de contas (ECD lançamentos) ──────────────────────────
            st.markdown("---")
            st.markdown(
                "<div class='info-box'>"
                "<b style='color:#FF6B00;'>🔀 DE/PARA de Contas (opcional)</b><br>"
                "<small style='color:#9BB0C8;'>"
                "Cole abaixo um JSON {\"cod_antigo\": \"cod_novo\"} para substituir "
                "os códigos reduzidos do SPED ECD antes de gerar o arquivo Domínio. "
                "Deixe em branco para usar os códigos originais.</small>"
                "</div>",
                unsafe_allow_html=True,
            )

            col_dep1, col_dep2 = st.columns(2)

            with col_dep1:
                map_contas_raw = st.text_area(
                    "DE/PARA de Contas (JSON)",
                    value="{}",
                    height=100,
                    key="map_contas_ecd_json",
                    help='Ex: {"12345": "50", "67890": "51"}',
                )
                try:
                    import json as _json
                    map_contas = {
                        str(k): str(v)
                        for k, v in _json.loads(map_contas_raw).items()
                    }
                    if map_contas:
                        st.caption(
                            f"✅ {len(map_contas)} regra(s) de conta carregada(s)."
                        )
                except Exception:
                    map_contas = {}
                    if map_contas_raw.strip() not in ("{}", ""):
                        st.warning("⚠ JSON inválido — DE/PARA de contas ignorado.")

            with col_dep2:
                cc_map_raw = st.text_area(
                    "DE/PARA de Centro de Custo (JSON)",
                    value="{}",
                    height=100,
                    key="cc_map_ecd_json",
                    help='Ex: {"CC001": "10", "CC002": "20"}',
                )
                try:
                    import json as _json
                    cc_map = {
                        str(k): str(v)
                        for k, v in _json.loads(cc_map_raw).items()
                    }
                    if cc_map:
                        st.caption(
                            f"✅ {len(cc_map)} regra(s) de CC carregada(s)."
                        )
                except Exception:
                    cc_map = {}
                    if cc_map_raw.strip() not in ("{}", ""):
                        st.warning("⚠ JSON inválido — DE/PARA de CC ignorado.")

            # ── Módulo Saldo Inicial ──────────────────────────────────────────
            st.markdown("---")
            st.markdown(
                "<div class='si-box'>"
                "<b style='color:#FF9EBC;font-size:15px;'>📥 Módulo Saldo Inicial</b><br>"
                "<small style='color:#C8A0B8;'>"
                "Extrai o saldo final do SPED ECD e gera um único lançamento "
                "de saldo inicial no leiaute Domínio.</small></div>",
                unsafe_allow_html=True,
            )

            col_si1, col_si2 = st.columns([1, 2])

            with col_si1:
                modo_saldo = st.checkbox(
                    "🔄 Gerar Saldo Inicial",
                    value=st.session_state.get("modo_saldo_inicial", False),
                    key="chk_saldo_inicial",
                )
                st.session_state["modo_saldo_inicial"] = modo_saldo

            with col_si2:
                hist_prefixo = st.text_input(
                    "Prefixo do histórico",
                    value=st.session_state.get("hist_prefixo_si", "SALDO INICIAL"),
                    max_chars=60,
                    key="hist_prefixo_si_widget",
                )
                st.session_state["hist_prefixo_si"] = hist_prefixo

            conta_pl = ""

            if modo_saldo:
                st.markdown("##### Tratamento das contas de Resultado")
                modo_resultado = st.radio(
                    "Como tratar as contas de Resultado (I355)?",
                    options=["apenas_patrimonial", "aberto_com_resultado"],
                    format_func=lambda x: {
                        "apenas_patrimonial":
                            "✅ Apenas Patrimonial — Ativo/Passivo/PL "
                            "(balanço fechado, sem resultado)",
                        "aberto_com_resultado":
                            "📂 Aberto com Resultado — inclui Receitas/Despesas "
                            "para encerrar no sistema destino",
                    }[x],
                    index=(
                        0
                        if st.session_state.get(
                            "modo_resultado_si", "apenas_patrimonial"
                        ) == "apenas_patrimonial"
                        else 1
                    ),
                    key="modo_resultado_si_widget",
                )
                st.session_state["modo_resultado_si"] = modo_resultado

                if modo_resultado == "aberto_com_resultado":
                    sugerida      = st.session_state.get("conta_pl_sugerida", "")
                    sugerida_nome = st.session_state.get("conta_pl_sugerida_nome", "")

                    if sugerida:
                        st.markdown(
                            f"<div class='si-box'>"
                            f"<b style='color:#FF9EBC;'>💡 Conta sugerida automaticamente:</b><br>"
                            f"<span style='color:#FFD166;font-size:18px;font-weight:700;'>"
                            f"{sugerida}</span>"
                            f"<span style='color:#9BB0C8;margin-left:12px;'>"
                            f"{sugerida_nome}</span><br>"
                            f"<small style='color:#9BB0C8;'>"
                            f"Detectada pelo COD_NAT/nome no I050 do SPED ECD.<br>"
                            f"Confirme se este é o código correto antes de processar."
                            f"</small></div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            "<div class='card-warn'>"
                            "⚠ <b style='color:#FFD166;'>"
                            "Informe a conta de Superávit/Déficit do PL.</b><br>"
                            "<small>O sistema irá deduzir o resultado líquido do I355 "
                            "desta conta para fechar o balanço (D=C).</small></div>",
                            unsafe_allow_html=True,
                        )

                    conta_pl = st.text_input(
                        "Código da conta de Superávit/Déficit (PL)",
                        value=(
                            sugerida
                            if sugerida
                            else st.session_state.get("conta_pl_resultado_si", "")
                        ),
                        placeholder="Ex: 311010101",
                        key="conta_pl_resultado_si_widget",
                    )
                    st.session_state["conta_pl_resultado_si"] = conta_pl

                    if not conta_pl:
                        st.warning(
                            "⚠ Informe a conta de PL/Resultado para que o "
                            "balanço feche corretamente."
                        )
                    elif sugerida and conta_pl != sugerida:
                        st.info(
                            f"ℹ Usando conta informada manualmente: {conta_pl} "
                            f"(sugestão era: {sugerida})"
                        )

                # Muda o tipo para "ecd_saldo" enquanto o módulo estiver ativo
                st.session_state["tipo_detectado"] = "ecd_saldo"
                tipo = "ecd_saldo"

            else:
                # Restaura tipo "ecd" se o módulo Saldo Inicial foi desativado
                if (
                    st.session_state.get("tipo_detectado") == "ecd_saldo"
                    and not st.session_state.get("processado")
                ):
                    st.session_state["tipo_detectado"] = "ecd"
                    tipo = "ecd"

        # ── CNPJ para TXT / Excel / Posicional ────────────────────────────────
        elif tipo != "ecd":
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
                    with col_a:
                        st.success(f"✔ {ti} válido")
                    with col_b:
                        st.code(fmt_reg_0000(ni), language=None)
                else:
                    st.error("✖ CNPJ/CPF inválido")

        # ── Passo 3: Opções de conversão ──────────────────────────────────────
        st.markdown("---")
        st.markdown("#### ⚙ Passo 3 — Opções e Conversão")

        col_op1, col_op2 = st.columns(2)

        with col_op1:
            gerar_6110 = st.checkbox(
                "Gerar registro 6110 (Centro de Custos)",
                value=False,
                disabled=(tipo not in ("ecd", "ecd_saldo", "dominio_pos", "excel")),
            )

        with col_op2:
            usar_de_para = st.checkbox(
                "🏢 Habilitar De/Para de filiais",
                value=False,
                disabled=(tipo not in ("dominio_pos", "excel")),
            )

        # ── Widget De/Para de filiais ─────────────────────────────────────────
        mapa_filiais: dict = {}

        if tipo == "dominio_pos" and usar_de_para:
            mapa_filiais = _widget_de_para_filiais(
                True,
                st.session_state.get("filiais_detectadas", []),
            )

        elif tipo == "excel" and usar_de_para:
            filiais_excel: list = []
            if (
                st.session_state.get("arquivo_bytes")
                and st.session_state.get("sheet_sel")
            ):
                try:
                    sh_scan      = st.session_state["sheet_sel"]
                    lh_scan, _   = detectar_cabecalho_excel(
                        st.session_state["arquivo_bytes"], sh_scan
                    )
                    df_scan, _   = ler_excel_lote(
                        st.session_state["arquivo_bytes"], sh_scan, lh_scan
                    )
                    filiais_excel = _pre_scan_filiais_excel(df_scan)
                    del df_scan
                except Exception:
                    filiais_excel = []

            mapa_filiais = _widget_de_para_filiais(True, filiais_excel)

        # ── Botões de ação ────────────────────────────────────────────────────
        col_b1, col_b2 = st.columns([2, 1])

        with col_b1:
            btn_converter = st.button(
                "▶ CONVERTER",
                disabled=not ok_insc,
                use_container_width=True,
                type="primary",
            )

        with col_b2:
            btn_limpar = st.button("🗑 Limpar tudo", use_container_width=True)

        if btn_limpar:
            _reset()
            st.rerun()

        # ── Processamento ─────────────────────────────────────────────────────
        if btn_converter and ok_insc:
            conteudo_proc = st.session_state["arquivo_bytes"]
            log:  list    = []
            crono         = Cronometro()
            crono.iniciar()

            status_txt = st.empty()
            prog_bar   = st.progress(0)

            try:

                # ── SALDO INICIAL ─────────────────────────────────────────────
                if tipo == "ecd_saldo":
                    crono.etapa("Saldo Inicial ECD")
                    log.append("── SALDO INICIAL — SPED ECD V3.7.0 ──")

                    resultado_bytes, metricas, todos_erros = (
                        processar_saldo_inicial_ecd(
                            conteudo_proc,
                            ni,
                            st.session_state.get("hist_prefixo_si", "SALDO INICIAL"),
                            st.session_state.get(
                                "modo_resultado_si", "apenas_patrimonial"
                            ),
                            st.session_state.get("conta_pl_resultado_si", ""),
                            log, prog_bar, status_txt,
                        )
                    )

                    st.session_state["resultado_bytes"] = resultado_bytes
                    st.session_state["resultado_nome"]  = f"SALDO_INI_{ni}.txt"
                    st.session_state["metricas"]        = metricas
                    st.session_state["processado"]      = True

                    if todos_erros:
                        st.session_state["erros_bytes"] = (
                            _txt_erros_ecd(todos_erros, ni).encode("utf-8-sig")
                        )
                        st.session_state["erros_nome"] = (
                            f"SALDO_INI_{ni}_erros.txt"
                        )

                    total_seg = crono.encerrar()
                    log.append(f"\n── TEMPO TOTAL: {Cronometro.fmt(total_seg)} ──")
                    for e in crono.etapas:
                        log.append(f"  {e['nome']}: {Cronometro.fmt(e['segundos'])}")

                    st.session_state["log_linhas"] = log
                    st.session_state["log_bytes"]  = (
                        "\n".join(log).encode("utf-8-sig")
                    )
                    st.session_state["log_nome"]   = f"log_saldo_ini_{ni}.txt"

                # ── SPED ECD LANÇAMENTOS (V3.7.0 — com map_contas + cc_map) ──
                elif tipo == "ecd":
                    crono.etapa("SPED ECD lançamentos")
                    log.append("── SPED ECD LANÇAMENTOS V3.7.0 ──")

                    # map_contas e cc_map definidos na seção de configuração
                    _map_contas = locals().get("map_contas", {})
                    _cc_map     = locals().get("cc_map", {})
                    _usar_cc    = bool(_cc_map)

                    resultado_bytes, metricas, registros_erro = (
                        processar_ecd_lancamentos(
                            conteudo_proc,
                            ni,
                            _map_contas,
                            _cc_map,
                            _usar_cc,
                            gerar_6110,
                            log, prog_bar, status_txt,
                        )
                    )

                    st.session_state["resultado_bytes"] = resultado_bytes
                    st.session_state["resultado_nome"]  = f"ECD_{ni}_dominio.txt"
                    st.session_state["metricas"]        = metricas
                    st.session_state["processado"]      = True

                    if registros_erro:
                        st.session_state["erros_bytes"] = (
                            _txt_erros_ecd(registros_erro, ni).encode("utf-8-sig")
                        )
                        st.session_state["erros_nome"] = f"ECD_{ni}_erros.txt"

                    total_seg = crono.encerrar()
                    log.append(f"\n── TEMPO TOTAL: {Cronometro.fmt(total_seg)} ──")
                    for e in crono.etapas:
                        log.append(f"  {e['nome']}: {Cronometro.fmt(e['segundos'])}")

                    st.session_state["log_linhas"] = log
                    st.session_state["log_bytes"]  = (
                        "\n".join(log).encode("utf-8-sig")
                    )
                    st.session_state["log_nome"]   = f"log_ecd_{ni}.txt"

                # ── EXCEL ──────────────────────────────────────────────────────
                elif tipo == "excel":
                    crono.etapa("Leitura Excel")
                    status_txt.text("Lendo Excel...")
                    prog_bar.progress(8)

                    sh    = st.session_state["sheet_sel"]
                    lh_det, _ = detectar_cabecalho_excel(conteudo_proc, sh)
                    lh    = lh_det if auto_head else linha_h

                    df, _ = ler_excel_lote(conteudo_proc, sh, lh)
                    log.append(f"Excel — Aba: {sh} | Cabeçalho: linha {lh + 1}")
                    log.append(f"Linhas carregadas: {len(df):,}")
                    prog_bar.progress(20)

                    crono.etapa("Montagem de lotes")
                    status_txt.text("Agrupando lotes...")
                    df, modo = montar_lotes_excel(df)
                    n_lotes  = int(df["_num_lote"].max()) if len(df) > 0 else 0
                    log.append(f"Lotes detectados  : {n_lotes:,} [modo: {modo}]")
                    prog_bar.progress(35)

                    crono.etapa("Ordenação")
                    status_txt.text("Reordenando lotes...")
                    df = _ordenar_lotes_por_data_filial(df)
                    log.append(f"Lotes reordenados : {n_lotes:,}")
                    prog_bar.progress(50)

                    log.append(
                        f"De/Para filiais   : {len(mapa_filiais)} regra(s)"
                        if mapa_filiais
                        else "De/Para filiais   : desabilitado"
                    )
                    log.append(
                        "Reg. 6110         : habilitado"
                        if gerar_6110
                        else "Reg. 6110         : desabilitado"
                    )

                    crono.etapa("Processamento")
                    status_txt.text("Processando lotes...")
                    resultado_bytes, resumo, erros = processar_excel(
                        df, ni, mapa_filiais, gerar_6110, log
                    )
                    del df
                    gc.collect()
                    prog_bar.progress(85)

                    n_gravados = resultado_bytes.count(b"|6000|")
                    n6110_f    = resultado_bytes.count(b"|6110|")

                    st.session_state["resultado_bytes"] = resultado_bytes
                    st.session_state["resultado_nome"]  = "lancamentos.txt"
                    st.session_state["resumo"]          = resumo
                    st.session_state["erros_lote"]      = erros

                    crono.etapa("Log")
                    log_txt = _montar_log_lote(
                        resumo, erros, ni, ti, inf,
                        n_gravados, 0, "N/A (Excel)", crono,
                    )
                    st.session_state["log_bytes"] = log_txt.encode("utf-8-sig")
                    st.session_state["log_nome"]  = "log_conversao.txt"

                    total_seg = crono.encerrar()
                    log.append(f"\nTempo total: {Cronometro.fmt(total_seg)}")

                    metricas = {
                        "Lotes total":   f"{len(resumo):,}",
                        "Lotes OK":      f"{len(resumo) - len(erros):,}",
                        "Lotes erro":    f"{len(erros):,}",
                        "Reg. gerados":  f"{n_gravados:,}",
                        "Tamanho saída": f"{len(resultado_bytes) / 1024:.1f} KB",
                    }
                    if gerar_6110:
                        metricas["Reg. 6110"] = f"{n6110_f:,}"

                    st.session_state["metricas"]   = metricas
                    st.session_state["log_linhas"] = log
                    st.session_state["processado"] = True
                    prog_bar.progress(100)
                    status_txt.text("Concluído!")

                # ── TXT POSICIONAL ─────────────────────────────────────────────
                elif tipo == "dominio_pos":
                    crono.etapa("Parse posicional")
                    log.append("── TXT POSICIONAL DOMÍNIO ──")

                    resultado_bytes, metricas, erros_parse, filiais_enc = (
                        processar_dominio_posicional(
                            conteudo_proc, ni,
                            gerar_6110, usar_de_para, mapa_filiais,
                            log, prog_bar, status_txt,
                        )
                    )

                    st.session_state["filiais_detectadas"] = filiais_enc
                    st.session_state["resultado_bytes"]    = resultado_bytes
                    st.session_state["resultado_nome"]     = (
                        f"DOM_POS_{ni}_dominio.txt"
                    )
                    st.session_state["metricas"]           = metricas
                    st.session_state["processado"]         = True

                    if erros_parse:
                        st.session_state["erros_bytes"] = (
                            _txt_erros_ecd(erros_parse, ni).encode("utf-8-sig")
                        )
                        st.session_state["erros_nome"] = (
                            f"DOM_POS_{ni}_erros.txt"
                        )

                    total_seg = crono.encerrar()
                    log.append(f"\n── TEMPO TOTAL: {Cronometro.fmt(total_seg)} ──")
                    for e in crono.etapas:
                        log.append(f"  {e['nome']}: {Cronometro.fmt(e['segundos'])}")

                    st.session_state["log_linhas"] = log
                    st.session_state["log_bytes"]  = (
                        "\n".join(log).encode("utf-8-sig")
                    )
                    st.session_state["log_nome"]   = f"log_pos_{ni}.txt"

                # ── TXT STREAMING (separado por ";") ──────────────────────────
                else:
                    crono.etapa("Streaming")
                    mb_txt = len(conteudo_proc) / (1024 * 1024)
                    status_txt.text(f"Processando {mb_txt:.1f} MB...")
                    prog_bar.progress(5)
                    log.append(f"── TXT STREAMING — {mb_txt:.1f} MB ──")

                    resultado_bytes, resumo, erros, total_lins, ignoradas, enc_usado = (
                        processar_streaming(conteudo_proc, ni, log)
                    )
                    prog_bar.progress(90)

                    n_gravados = resultado_bytes.count(b"|6000|")

                    st.session_state["resultado_bytes"] = resultado_bytes
                    st.session_state["resultado_nome"]  = "lancamentos.txt"
                    st.session_state["resumo"]          = resumo
                    st.session_state["erros_lote"]      = erros

                    crono.etapa("Log")
                    log_txt = _montar_log_lote(
                        resumo, erros, ni, ti, inf,
                        n_gravados, ignoradas, enc_usado, crono,
                    )
                    st.session_state["log_bytes"] = log_txt.encode("utf-8-sig")
                    st.session_state["log_nome"]  = "log_conversao.txt"

                    total_seg = crono.encerrar()
                    log.append(f"\nTempo total: {Cronometro.fmt(total_seg)}")

                    st.session_state["metricas"] = {
                        "Linhas lidas":  f"{total_lins:,}",
                        "Lotes total":   f"{len(resumo):,}",
                        "Lotes OK":      f"{len(resumo) - len(erros):,}",
                        "Lotes erro":    f"{len(erros):,}",
                        "Reg. gerados":  f"{n_gravados:,}",
                        "Tamanho saída": f"{len(resultado_bytes) / 1024:.1f} KB",
                    }
                    st.session_state["log_linhas"] = log
                    st.session_state["processado"] = True
                    prog_bar.progress(100)
                    status_txt.text("Concluído!")

            except Exception as ex:
                tb = traceback.format_exc()
                st.error(f"⛔ Erro inesperado: {ex}")
                log.append(f"ERRO FATAL: {ex}\n{tb}")
                st.session_state["log_linhas"] = log
                prog_bar.progress(0)
                status_txt.text("Falha.")

            st.rerun()

        # ── Renderização dos resultados ───────────────────────────────────────
        if st.session_state.get("processado"):
            tipo_proc = st.session_state.get("tipo_detectado")

            if   tipo_proc == "ecd_saldo":   _render_resultados_saldo_inicial(exibir_log)
            elif tipo_proc == "ecd":          _render_resultados_ecd(exibir_log)
            elif tipo_proc == "dominio_pos":  _render_resultados_posicional(exibir_log)
            else:                             _render_resultados_lote(exibir_log)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
