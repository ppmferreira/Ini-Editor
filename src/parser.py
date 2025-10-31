from pathlib import Path
from typing import List, Tuple

PREFERRED_ENCODINGS = [
    'utf-8', 'utf-8-sig', 'utf-16', 'utf-16le', 'utf-16be', 'big5', 'cp1252', 'latin-1'
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

    # tenta decodificar usando as encodings preferidas
    text = None
    used_enc = None
    last_exc = None
    for enc in encodings:
        try:
            text = path.read_text(encoding=enc)
            used_enc = enc
            break
        except Exception as e:
            last_exc = e
            continue

    if text is None:
        # fallback permissivo
        text = path.read_text(encoding='latin-1', errors='replace')
        used_enc = 'latin-1'

    records = []
    buf_lines = []

    # processa linha a linha e acumula até ter separadores suficientes
    for raw_line in text.splitlines(keepends=True):
        buf_lines.append(raw_line)
        buf = ''.join(buf_lines)
        # se ainda não temos separadores suficientes, continue acumulando
        if buf.count('|') < expected_separators:
            continue
        # temos pelo menos o número esperado de separadores -> considerar registro completo
        parts = buf.rstrip('\n').split('|', expected_separators)
        if len(parts) < expected_fields:
            parts += [''] * (expected_fields - len(parts))
        rec = {headers[i]: parts[i] for i in range(expected_fields)}
        records.append(rec)
        buf_lines = []

    # se sobrou buffer no final, tentar parsear também
    if buf_lines:
        buf = ''.join(buf_lines)
        parts = buf.rstrip('\n').split('|', expected_separators)
        if len(parts) < expected_fields:
            parts += [''] * (expected_fields - len(parts))
        rec = {headers[i]: parts[i] for i in range(expected_fields)}
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

    for raw_line in text.splitlines(keepends=True):
        buf_lines.append(raw_line)
        buf = ''.join(buf_lines)
        if buf.count('|') < expected_separators:
            continue
        parts = buf.rstrip('\n').split('|', expected_separators)
        if len(parts) < expected_fields:
            parts += [''] * (expected_fields - len(parts))
        rec = {headers[i]: parts[i] for i in range(expected_fields)}
        records.append(rec)
        buf_lines = []

    if buf_lines:
        buf = ''.join(buf_lines)
        parts = buf.rstrip('\n').split('|', expected_separators)
        if len(parts) < expected_fields:
            parts += [''] * (expected_fields - len(parts))
        rec = {headers[i]: parts[i] for i in range(expected_fields)}
        records.append(rec)

    return records
