# -*- coding: latin-1 -*-
from pathlib import Path
from typing import List, Tuple

PREFERRED_ENCODINGS = [
    # Ordem de tentativa: UTF-8, Big5, ANSI (cp1252), Latin1
    'utf-8', 'big5', 'cp1252', 'latin-1'
]


def load_headers(header_path: Path) -> List[str]:
    """Carrega cabeçalhos a partir do arquivo de header (ex: Assets/Headers/h_item).
    Retorna lista de campos (stripped).
    """
    s = header_path.read_text(encoding='latin-1')
    headers = [h.strip() for h in s.strip().split(',') if h.strip()]
    return headers


def detect_pipe_file_sample(text: str, expected_separators: int) -> bool:
    """Detecta se um trecho de texto parece ser um arquivo pipe-delimited com o número
    esperado de separadores (ou mais)."""
    # usa contagem simples de '|' no sample
    return text.count('|') >= expected_separators


def parse_pipe_file(path: Path, headers: List[str], encodings: List[str] = None) -> Tuple[List[dict], str]:
    """Parseia um arquivo pipe-delimited onde registros podem ter quebras de linha em campos.

    Retorna (records, used_encoding). Cada record é um dict mapeando header->valor.
    """
    if encodings is None:
        encodings = PREFERRED_ENCODINGS

    expected_fields = len(headers)
    expected_separators = expected_fields - 1

    # ler bytes e escolher melhor decodificação por heurística (preferir Big5 se houver CJK)
    raw = path.read_bytes()
    text = None
    used_enc = None
    import re
    cjk_re = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
    best_score = None
    for enc in encodings:
        try:
            cand = raw.decode(enc, errors='replace')
        except Exception:
            continue
        repl = cand.count('\ufffd') + cand.count('')
        cjk = len(cjk_re.findall(cand))
        score = cjk * 10 - repl * 100
        if best_score is None or score > best_score:
            best_score = score
            text = cand
            used_enc = enc

    if text is None:
        text = raw.decode('latin-1', errors='replace')
        used_enc = 'latin-1'

    records = []
    buf_lines = []
    last_rec = None
    last_rec = None
    # pular linhas iniciais de metadados (ex: "V.16|93|") se existirem
    import re
    # aceita possíveis pipes ou espaços antes do metadado (ex: "|V.16|93|")
    meta_re = re.compile(r'^[\|\s]*V\.[0-9]+\|[0-9]+')
    # normaliza BOM e quebras, e remove primeira linha se for metadado
    t = text.lstrip('\ufeff')
    lines = t.splitlines(keepends=True)
    if lines and meta_re.match(lines[0].strip()):
        # descarta a primeira linha de metadados
        lines = lines[1:]

    import re
    newrec_re = re.compile(r'^\s*\d+\|')
    # processa linha a linha e acumula até ter separadores suficientes
    for raw_line in lines:
        # se não estamos acumulando um registro e a linha não parece iniciar um novo registro,
        # então pode ser continuação (Tip) do registro anterior
        if not buf_lines:
            if not newrec_re.match(raw_line) and raw_line.count('|') < expected_separators:
                # linha de continuação: anexar ao Tip do último registro, se existir
                if last_rec is not None:
                    # preservar quebra de linha entre linhas; limpar pipes mantidos na linha de
                    # continuação (muitas linhas de continuação começam com '|' por causa do formato)
                    prev = last_rec.get('Tip', '') or ''
                    cleaned = raw_line.rstrip('\n')
                    # remover um pipe inicial ou final que pertençam ao delimitador
                    if cleaned.startswith('|'):
                        cleaned = cleaned[1:]
                    if cleaned.endswith('|'):
                        cleaned = cleaned[:-1]
                    # adicionar nova linha entre partes se já havia conteúdo
                    if prev:
                        last_rec['Tip'] = prev + '\n' + cleaned
                    else:
                        last_rec['Tip'] = cleaned
                else:
                    # sem registro anterior — tratar como lixo/ignorar
                    pass
                continue
            # caso contrário, iniciar buffer com esta linha
        buf_lines.append(raw_line)
        buf = ''.join(buf_lines)
        # se ainda não temos separadores suficientes, continue acumulando
        if buf.count('|') < expected_separators:
            continue
        # temos pelo menos o número esperado de separadores -> considerar registro completo
        parts = buf.rstrip('\n').split('|', expected_separators)
        if len(parts) < expected_fields:
            parts += [''] * (expected_fields - len(parts))
        # preserve internal newlines for 'Tip' field; for other fields strip surrounding whitespace
        rec = {}
        for i in range(expected_fields):
            key = headers[i]
            val = parts[i]
            if key.lower() == 'tip':
                # limpar pipes remanescentes nas bordas e remover nova linha final
                cleaned = val.rstrip('\n')
                if cleaned.startswith('|'):
                    cleaned = cleaned[1:]
                if cleaned.endswith('|'):
                    cleaned = cleaned[:-1]
                rec[key] = cleaned
            else:
                rec[key] = val.strip()
        records.append(rec)
        last_rec = rec
        buf_lines = []

    # se sobrou buffer no final, tentar parsear também
    if buf_lines:
        buf = ''.join(buf_lines)
        parts = buf.rstrip('\n').split('|', expected_separators)
        if len(parts) < expected_fields:
            parts += [''] * (expected_fields - len(parts))
        rec = {}
        for i in range(expected_fields):
            key = headers[i]
            val = parts[i]
            if key.lower() == 'tip':
                cleaned = val.rstrip('\n')
                if cleaned.startswith('|'):
                    cleaned = cleaned[1:]
                if cleaned.endswith('|'):
                    cleaned = cleaned[:-1]
                rec[key] = cleaned
            else:
                rec[key] = val.strip()
        records.append(rec)

    return records, used_enc


def parse_pipe_text(text: str, headers: List[str]) -> List[dict]:
    """Parseia texto já carregado de um arquivo pipe-delimited.

    Retorna lista de records (dict). Não lida com encoding — assume que o texto
    já está decodificado corretamente.
    """
    expected_fields = len(headers)
    expected_separators = expected_fields - 1

    records = []
    buf_lines = []
    last_rec = None

    # pular metadados iniciais como "V.16|93|" se existirem
    import re
    # aceita possíveis pipes ou espaços antes do metadado (ex: "|V.16|93|")
    meta_re = re.compile(r'^[\|\s]*V\.[0-9]+\|[0-9]+')
    t = text.lstrip('\ufeff')
    lines = t.splitlines(keepends=True)
    if lines and meta_re.match(lines[0].strip()):
        lines = lines[1:]

    import re
    newrec_re = re.compile(r'^\s*\d+\|')
    for raw_line in lines:
        if not buf_lines:
            if not newrec_re.match(raw_line) and raw_line.count('|') < expected_separators:
                if last_rec is not None:
                    prev = last_rec.get('Tip', '') or ''
                    cleaned = raw_line.rstrip('\n')
                    if cleaned.startswith('|'):
                        cleaned = cleaned[1:]
                    if cleaned.endswith('|'):
                        cleaned = cleaned[:-1]
                    if prev:
                        last_rec['Tip'] = prev + '\n' + cleaned
                    else:
                        last_rec['Tip'] = cleaned
                else:
                    pass
                continue
        buf_lines.append(raw_line)
        buf = ''.join(buf_lines)
        if buf.count('|') < expected_separators:
            continue
        parts = buf.rstrip('\n').split('|', expected_separators)
        if len(parts) < expected_fields:
            parts += [''] * (expected_fields - len(parts))
        rec = {}
        for i in range(expected_fields):
            key = headers[i]
            val = parts[i]
            if key.lower() == 'tip':
                cleaned = val.rstrip('\n')
                if cleaned.startswith('|'):
                    cleaned = cleaned[1:]
                if cleaned.endswith('|'):
                    cleaned = cleaned[:-1]
                rec[key] = cleaned
            else:
                rec[key] = val.strip()
        records.append(rec)
        last_rec = rec
        buf_lines = []

    if buf_lines:
        buf = ''.join(buf_lines)
        parts = buf.rstrip('\n').split('|', expected_separators)
        if len(parts) < expected_fields:
            parts += [''] * (expected_fields - len(parts))
        rec = {}
        for i in range(expected_fields):
            key = headers[i]
            val = parts[i]
            if key.lower() == 'tip':
                cleaned = val.rstrip('\n')
                if cleaned.startswith('|'):
                    cleaned = cleaned[1:]
                if cleaned.endswith('|'):
                    cleaned = cleaned[:-1]
                rec[key] = cleaned
            else:
                rec[key] = val.strip()
        records.append(rec)

    return records


def is_pipe_file(text: str, headers: List[str]) -> bool:
    """Heurística rápida para dizer se o texto representa um arquivo pipe-delimited
    compatível com os headers fornecidos. Retorna True se encontrar ao menos um
    registro cujo split por '|' produza >= len(headers) partes (considerando
    linhas iniciais de metadados como "|V.16|93|")."""
    expected_fields = len(headers)
    expected_separators = expected_fields - 1
    import re
    meta_re = re.compile(r'^[\|\s]*V\.[0-9]+\|[0-9]+')
    t = text.lstrip('\ufeff')
    lines = t.splitlines(keepends=True)
    if lines and meta_re.match(lines[0].strip()):
        lines = lines[1:]

    buf = ''
    for ln in lines:
        buf += ln
        if buf.count('|') >= expected_separators:
            parts = buf.rstrip('\n').split('|', expected_separators)
            return len(parts) >= expected_fields
    return False
