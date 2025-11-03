# -*- coding: latin-1 -*-
"""
Parser para arquivos pipe-delimited (items)
- Detecta formato de items (linhas iniciando com ID| e múltiplos pipes)
- Parseia registros com suporte a continuação de linha para campo Tip
- Carrega headers CSV
- Preserva newlines em campos Tip, remove pipes do início/fim
"""

import re
from pathlib import Path
from typing import List, Dict, Optional

# Regex para linha de metadados (ex: |V.16|93| ou V.16|93|)
META_REGEX = re.compile(r'^[\|\s]*V\.[0-9]+\|[0-9]+')

# Regex para linha de continuação (não começa com número|)
CONTINUATION_REGEX = re.compile(r'^\s*\d+\|')


def load_headers(header_file_path: Path) -> List[str]:
    """Carrega headers de arquivo CSV.
    
    Args:
        header_file_path: Caminho para arquivo de headers
        
    Returns:
        Lista de nomes de colunas
    """
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            txt = header_file_path.read_text(encoding=enc, errors='replace')
            headers = [h.strip() for h in txt.splitlines()[0].split(',')]
            return headers
        except Exception:
            continue
    
    raise ValueError(f'Não foi possível ler headers de {header_file_path}')


def is_continuation_line(line: str) -> bool:
    """Verifica se linha é continuação (não começa com número|).
    
    Args:
        line: Linha para verificar
        
    Returns:
        True se for linha de continuação
    """
    return not CONTINUATION_REGEX.match(line.strip())


def clean_tip_field(value: str) -> str:
    """Remove pipes do início e fim do campo Tip.
    
    Args:
        value: Valor do campo Tip
        
    Returns:
        Valor limpo
    """
    return value.lstrip('|').rstrip('|')


def skip_metadata_lines(lines: List[str]) -> List[str]:
    """Remove linhas de metadados do início da lista.
    
    Args:
        lines: Lista de linhas
        
    Returns:
        Lista sem linhas de metadados
    """
    result = []
    for line in lines:
        stripped = line.strip()
        if not META_REGEX.match(stripped):
            result.append(line)
    return result


def build_records(lines: List[str], headers: List[str]) -> List[Dict[str, str]]:
    """Constrói lista de registros a partir de linhas.
    
    Implementa lógica de continuação de linha para campo Tip multiline.
    
    Args:
        lines: Lista de linhas (sem metadados)
        headers: Lista de nomes de colunas
        
    Returns:
        Lista de dicts {header: valor}
    """
    records = []
    expected_separators = len(headers) - 1
    acc_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Linha de continuação: adiciona ao acumulador
        if is_continuation_line(stripped) and acc_lines:
            acc_lines.append(stripped)
            continue
        
        # Nova linha de registro: processa acumulador anterior
        if acc_lines:
            records.append(_parse_record_lines(acc_lines, headers, expected_separators))
            acc_lines = []
        
        # Inicia novo acumulador
        acc_lines.append(stripped)
    
    # Processa último registro
    if acc_lines:
        records.append(_parse_record_lines(acc_lines, headers, expected_separators))
    
    return records


def _parse_record_lines(lines: List[str], headers: List[str], expected_separators: int) -> Dict[str, str]:
    """Parseia linhas acumuladas para criar um registro.
    
    Args:
        lines: Linhas do registro (primeira + continuações)
        headers: Lista de nomes de colunas
        expected_separators: Número esperado de pipes
        
    Returns:
        Dict {header: valor}
    """
    # Linha principal
    main_line = lines[0]
    
    # Verificar contagem de pipes
    if main_line.count('|') < expected_separators:
        # Linha incompleta, adicionar continuações
        for cont_line in lines[1:]:
            main_line += '\n' + cont_line
            if main_line.count('|') >= expected_separators:
                break
    
    # Dividir por pipe
    parts = main_line.split('|', maxsplit=len(headers))
    if len(parts) < len(headers):
        parts.extend([''] * (len(headers) - len(parts)))
    
    # Criar registro
    record = {}
    for i, header in enumerate(headers):
        value = parts[i] if i < len(parts) else ''
        
        # Processar campo Tip: preservar newlines, limpar pipes
        if header.lower() == 'tip':
            # Adicionar linhas de continuação ao Tip
            for cont_line in lines[1:]:
                if is_continuation_line(cont_line):
                    value += '\n' + cont_line
            
            value = clean_tip_field(value)
            record[header] = value
        else:
            # Outros campos: apenas strip
            record[header] = value.strip()
    
    return record


def parse_pipe_file(path: Path, headers: List[str]) -> List[Dict[str, str]]:
    """Parseia arquivo pipe-delimited com detecção de encoding.
    
    Args:
        path: Caminho do arquivo
        headers: Lista de nomes de colunas
        
    Returns:
        Lista de dicts {header: valor}
    """
    for enc in ['utf-8', 'big5', 'cp1252', 'latin-1']:
        try:
            txt = path.read_text(encoding=enc, errors='replace')
        except Exception:
            continue
        
        lines = [ln for ln in txt.splitlines() if ln.strip()]
        lines = skip_metadata_lines(lines)
        
        try:
            return build_records(lines, headers)
        except Exception:
            continue
    
    raise ValueError(f'Não foi possível parsear {path}')


def parse_pipe_text(text: str, headers: List[str]) -> List[Dict[str, str]]:
    """Parseia texto pipe-delimited.
    
    Args:
        text: Texto do arquivo
        headers: Lista de nomes de colunas
        
    Returns:
        Lista de dicts {header: valor}
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    lines = skip_metadata_lines(lines)
    return build_records(lines, headers)


def is_pipe_file(text: str, headers: Optional[List[str]] = None) -> bool:
    """Detecta se texto é arquivo pipe-delimited.
    
    Heurística: pelo menos 5 linhas começando com número| e múltiplos pipes.
    
    Args:
        text: Texto do arquivo
        headers: Headers esperados (para validar contagem de pipes)
        
    Returns:
        True se parece arquivo pipe-delimited
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 5:
        return False
    
    # Pular metadados
    lines = skip_metadata_lines(lines)
    
    # Contar linhas que começam com número|
    id_pattern = re.compile(r'^\d+\|')
    count = sum(1 for ln in lines[:20] if id_pattern.match(ln))
    
    if count < 5:
        return False
    
    # Verificar contagem de pipes
    if headers:
        expected_pipes = len(headers) - 1
        for ln in lines[:10]:
            if id_pattern.match(ln) and ln.count('|') >= expected_pipes:
                return True
    else:
        # Sem headers: verificar se tem pelo menos 3 pipes
        for ln in lines[:10]:
            if id_pattern.match(ln) and ln.count('|') >= 3:
                return True
    
    return False
