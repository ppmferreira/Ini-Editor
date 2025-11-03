# -*- coding: latin-1 -*-
"""
INI Editor - GUI principal modular
- Lista arquivos em Assets/
- Detecta arquivos pipe-delimited (items) usando src.parser
- Abre visualização tabular para arquivos de items (src.item_table_view)
- Para INI tradicionais, mostra seções/chaves/valor e permite editar/salvar

Uso: python ini_editor.py
"""

from pathlib import Path
import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import configparser
from typing import Optional, Tuple, List

try:
    from src import parser as data_parser
    from src import item_table_view
except Exception:
    data_parser = None
    item_table_view = None

# Constantes
PREFERRED_ENCODINGS = ['utf-8', 'big5', 'cp1252', 'latin-1']
SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR / 'Assets'
HEADERS_DIR = ASSETS_DIR / 'Headers'

# Regex para detectar metadados (ex: |V.16|93|)
META_REGEX = re.compile(r'^[\|\s]*V\.\d+\|(\d+)\|')


def detect_encoding(raw_bytes: bytes, encodings: List[str] = None) -> Tuple[str, str]:
    """Detecta melhor encoding usando heurística CJK.
    
    Returns:
        (texto_decodificado, encoding_usado)
    """
    if encodings is None:
        encodings = PREFERRED_ENCODINGS
    
    cjk_re = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
    best = None
    best_score = None
    
    for enc in encodings:
        try:
            txt = raw_bytes.decode(enc, errors='replace')
        except Exception:
            continue
        
        repl_count = txt.count('\ufffd') + txt.count('')
        cjk_count = len(cjk_re.findall(txt))
        score = cjk_count * 10 - repl_count * 100
        
        if best_score is None or score > best_score:
            best_score = score
            best = (txt, enc)
    
    if best:
        return best
    return raw_bytes.decode('latin-1', errors='replace'), 'latin-1'


def extract_metadata_columns(text: str) -> Optional[int]:
    """Extrai número de colunas da linha de metadados (ex: |V.16|93|).
    
    Returns:
        Número de colunas ou None se não encontrado
    """
    for line in text.splitlines()[:5]:
        match = META_REGEX.match(line.strip())
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                return None
    return None


def find_matching_header(file_path: Path, text: str, headers_dir: Path) -> Optional[Tuple[List[str], Path]]:
    """Procura arquivo de header correspondente ao arquivo.
    
    Prioriza padrões como H_<file_stem> e h_<file_stem>.
    Ajusta tamanho do header se metadados indicarem número diferente de colunas.
    
    Returns:
        (lista_headers, caminho_header) ou None se não encontrado
    """
    if not data_parser or not headers_dir.exists():
        return None
    
    # Detectar metadados
    expected_fields = extract_metadata_columns(text)
    
    # Gerar nomes candidatos priorizados
    stem = file_path.stem
    candidates_priority = [
        f'H_{stem}',           # H_C_Item (padrão preferido)
        f'h_{stem.lower()}',   # h_c_item
        f'h_{stem[2:].lower()}' if stem.lower().startswith('c_') else None,  # h_item
    ]
    candidates_priority = [c for c in candidates_priority if c]
    
    # Procurar headers que batam
    for hf in headers_dir.iterdir():
        if not hf.is_file():
            continue
        
        hf_stem_lower = hf.stem.lower()
        if hf_stem_lower not in [c.lower() for c in candidates_priority]:
            continue
        
        try:
            headers = data_parser.load_headers(hf)
        except Exception:
            continue
        
        # Ajustar tamanho se metadados indicarem valor diferente
        if expected_fields and len(headers) != expected_fields:
            if len(headers) > expected_fields:
                headers = headers[:expected_fields]
            else:
                headers.extend([f'Unknown {i}' for i in range(len(headers), expected_fields)])
        
        # Verificar se é arquivo pipe compatível
        if data_parser.is_pipe_file(text, headers):
            return (headers, hf)
    
    return None


def generate_unknown_headers(text: str) -> Optional[List[str]]:
    """Gera headers Unknown baseado em metadados ou máximo de pipes.
    
    Returns:
        Lista de headers ou None se não puder determinar
    """
    # Tentar usar metadados primeiro
    ncols = extract_metadata_columns(text)
    
    # Fallback: linha com mais pipes
    if ncols is None:
        max_pipes = max((line.count('|') for line in text.splitlines()), default=0)
        if max_pipes >= 2:
            ncols = max_pipes + 1
    
    if ncols and ncols >= 1:
        return [f'Unknown {i}' for i in range(ncols)]
    
    return None


def clear_frame(frame):
    """Remove todos os widgets filhos de um frame."""
    for child in list(frame.winfo_children()):
        child.destroy()


class IniEditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('INI Editor')
        self.geometry('1100x700')
        
        self.assets_dir = ASSETS_DIR
        self.current_file: Optional[Path] = None
        self.current_encoding: Optional[str] = None
        self.cfg = configparser.ConfigParser(allow_no_value=True)
        
        self.create_widgets()
        self.refresh_file_list()
    
    def create_widgets(self):
        """Cria layout principal: lista de arquivos (esquerda) e visualizador (direita)."""
        main = ttk.Frame(self)
        main.pack(fill='both', expand=True)
        
        # Painel esquerdo: lista de arquivos
        self._create_file_list_panel(main)
        
        # Painel direito: visualizador
        right = ttk.Frame(main)
        right.pack(side='right', fill='both', expand=True)
        
        self.viewer_frame = ttk.Frame(right)
        self.viewer_frame.pack(fill='both', expand=True, padx=8, pady=8)
        
        self.viewer_placeholder = ttk.Label(
            self.viewer_frame,
            text='Abra um arquivo à esquerda para visualizar'
        )
        self.viewer_placeholder.pack(expand=True)
    
    def _create_file_list_panel(self, parent):
        """Cria painel de lista de arquivos."""
        left = ttk.Frame(parent, width=320)
        left.pack(side='left', fill='y')
        
        ttk.Label(left, text='Arquivos (Assets)').pack(anchor='w', padx=8, pady=(8, 0))
        
        self.file_listbox = tk.Listbox(left, width=48)
        self.file_listbox.pack(fill='y', expand=True, padx=8, pady=8)
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_select)
        
        btns = ttk.Frame(left)
        btns.pack(fill='x', padx=8, pady=8)
        ttk.Button(btns, text='Recarregar', command=self.refresh_file_list).pack(side='left')
        ttk.Button(btns, text='Abrir pasta...', command=self.choose_folder).pack(side='left', padx=6)
    
    def refresh_file_list(self):
        """Recarrega lista de arquivos .ini e .txt da pasta Assets."""
        self.file_listbox.delete(0, 'end')
        
        if not self.assets_dir.exists():
            messagebox.showwarning('Assets não encontrado', f'Pasta {self.assets_dir} não existe.')
            return
        
        files = []
        for root, _, filenames in os.walk(self.assets_dir):
            for f in filenames:
                if f.lower().endswith(('.ini', '.txt')):
                    full_path = Path(root) / f
                    try:
                        rel_path = full_path.relative_to(SCRIPT_DIR)
                    except ValueError:
                        rel_path = full_path
                    files.append(rel_path)
        
        for path in sorted(files):
            self.file_listbox.insert('end', str(path))
    
    def choose_folder(self):
        """Permite escolher pasta Assets alternativa."""
        folder = filedialog.askdirectory(
            initialdir=str(SCRIPT_DIR),
            title='Escolha a pasta Assets'
        )
        if folder:
            self.assets_dir = Path(folder)
            self.refresh_file_list()
    
    def on_file_select(self, event=None):
        """Handler para seleção de arquivo na lista."""
        sel = self.file_listbox.curselection()
        if not sel:
            return
        
        rel_path = self.file_listbox.get(sel[0])
        path = Path(rel_path)
        
        if not path.is_absolute():
            path = SCRIPT_DIR / rel_path
        
        self.open_file(path)
    
    def open_file(self, path: Path):
        """Abre arquivo detectando tipo (pipe/INI/raw) e mostra visualização apropriada."""
        self.current_file = path
        
        # Ler arquivo com detecção de encoding
        try:
            raw = path.read_bytes()
            text, enc = detect_encoding(raw)
            self.current_encoding = enc
        except Exception as e:
            messagebox.showerror('Erro ao abrir', f'Erro ao ler {path}: {e}')
            return
        
        # Tentar abrir como arquivo pipe (items)
        if self._try_open_as_pipe_file(path, text, enc):
            return
        
        # Tentar abrir como INI tradicional
        if self._try_open_as_ini(path, text, enc):
            return
        
        # Fallback: mostrar como texto bruto
        self._show_raw_text(text)
    
    def _try_open_as_pipe_file(self, path: Path, text: str, encoding: str) -> bool:
        """Tenta abrir arquivo como pipe-delimited (items).
        
        Returns:
            True se conseguiu abrir, False caso contrário
        """
        if not data_parser or not item_table_view:
            return False
        
        try:
            # Procurar header correspondente
            header_result = find_matching_header(path, text, HEADERS_DIR)
            
            if header_result:
                headers, header_path = header_result
            else:
                # Gerar headers Unknown
                headers = generate_unknown_headers(text)
                if not headers:
                    return False
            
            # Parsear e mostrar
            records = data_parser.parse_pipe_text(text, headers)
            clear_frame(self.viewer_frame)
            
            item_table_view.show_item_table(
                self.viewer_frame,
                path.name,
                headers,
                records,
                encoding=encoding,
                file_path=path,
                embed=True
            )
            
            self.title(f'INI Editor — {path.name} (encoding: {encoding})')
            return True
            
        except Exception:
            return False
    
    def _try_open_as_ini(self, path: Path, text: str, encoding: str) -> bool:
        """Tenta abrir arquivo como INI tradicional.
        
        Returns:
            True se conseguiu abrir, False caso contrário
        """
        self.cfg = configparser.ConfigParser(allow_no_value=True)
        
        try:
            self.cfg.read_string(text)
        except configparser.MissingSectionHeaderError:
            return False
        except Exception:
            try:
                self.cfg.read(path, encoding=encoding)
            except Exception:
                return False
        
        self._show_ini_editor()
        self.title(f'INI Editor — {path.name}')
        return True
    
    def _show_raw_text(self, text: str):
        """Mostra texto bruto."""
        clear_frame(self.viewer_frame)
        
        ttk.Label(self.viewer_frame, text='Visualizador bruto').pack(anchor='w')
        txt = tk.Text(self.viewer_frame, wrap='none')
        txt.pack(fill='both', expand=True)
        txt.insert('1.0', text)
    
    def _show_ini_editor(self):
        """Mostra editor INI tradicional."""
        self._ensure_ini_widgets()
        
        # Preencher seções
        self.sections_lb.delete(0, 'end')
        for section in self.cfg.sections():
            self.sections_lb.insert('end', section)
        
        # Limpar keys e valor
        for iid in self.keys_tree.get_children():
            self.keys_tree.delete(iid)
        self.value_text.delete('1.0', 'end')
    
    def _ensure_ini_widgets(self):
        """Cria widgets de edição INI se não existirem."""
        if hasattr(self, 'sections_lb'):
            return
        
        clear_frame(self.viewer_frame)
        
        top = ttk.Frame(self.viewer_frame)
        top.pack(fill='both', expand=True, padx=8, pady=8)
        
        # Seções
        self._create_sections_panel(top)
        
        # Chaves
        self._create_keys_panel(top)
        
        # Editor de valor
        self._create_value_editor(top)
    
    def _create_sections_panel(self, parent):
        """Cria painel de seções."""
        frame = ttk.Frame(parent)
        frame.pack(side='left', fill='y')
        
        ttk.Label(frame, text='Seções').pack(anchor='w')
        self.sections_lb = tk.Listbox(frame, width=30)
        self.sections_lb.pack(fill='y', expand=True)
        self.sections_lb.bind('<<ListboxSelect>>', self.on_section_select)
        
        btns = ttk.Frame(frame)
        btns.pack(fill='x', pady=6)
        ttk.Button(btns, text='Nova Seção', command=self.add_section).pack(side='left')
        ttk.Button(btns, text='Remover Seção', command=self.remove_section).pack(side='left', padx=6)
    
    def _create_keys_panel(self, parent):
        """Cria painel de chaves."""
        frame = ttk.Frame(parent)
        frame.pack(side='left', fill='both', expand=True, padx=(8, 0))
        
        ttk.Label(frame, text='Chaves').pack(anchor='w')
        self.keys_tree = ttk.Treeview(frame, columns=('key', 'value'), show='headings')
        self.keys_tree.heading('key', text='Chave')
        self.keys_tree.heading('value', text='Valor (preview)')
        self.keys_tree.column('key', width=220, anchor='w')
        self.keys_tree.column('value', width=420, anchor='w')
        self.keys_tree.pack(fill='both', expand=True)
        self.keys_tree.bind('<<TreeviewSelect>>', self.on_key_select)
        self.keys_tree.bind('<Double-1>', self.on_key_double_click)
        
        btns = ttk.Frame(frame)
        btns.pack(fill='x', pady=6)
        ttk.Button(btns, text='Nova Chave', command=self.add_key).pack(side='left')
        ttk.Button(btns, text='Remover Chave', command=self.remove_key).pack(side='left', padx=6)
    
    def _create_value_editor(self, parent):
        """Cria painel de edição de valor."""
        frame = ttk.Frame(parent)
        frame.pack(side='left', fill='both', expand=True, padx=(8, 0))
        
        ttk.Label(frame, text='Valor').pack(anchor='w')
        self.value_text = tk.Text(frame, wrap='none')
        self.value_text.pack(fill='both', expand=True)
        
        btns = ttk.Frame(frame)
        btns.pack(fill='x', pady=6)
        ttk.Button(btns, text='Salvar', command=self.save_current).pack(side='left')
        ttk.Button(btns, text='Recarregar', command=self.reload_current).pack(side='left', padx=6)
    
    def on_section_select(self, event=None):
        """Handler para seleção de seção."""
        sel = self.sections_lb.curselection()
        
        # Limpar chaves
        for iid in self.keys_tree.get_children():
            self.keys_tree.delete(iid)
        self.value_text.delete('1.0', 'end')
        
        if not sel:
            return
        
        section = self.sections_lb.get(sel[0])
        for key in self.cfg[section]:
            value = self.cfg.get(section, key, fallback='')
            preview = value.splitlines()[0] if value else ''
            if len(preview) > 200:
                preview = preview[:197] + '...'
            self.keys_tree.insert('', 'end', values=(key, preview))
    
    def on_key_select(self, event=None):
        """Handler para seleção de chave."""
        sel = self.keys_tree.selection()
        ssel = self.sections_lb.curselection()
        
        self.value_text.delete('1.0', 'end')
        
        if not sel or not ssel:
            return
        
        section = self.sections_lb.get(ssel[0])
        item = sel[0]
        vals = self.keys_tree.item(item, 'values')
        if not vals:
            return
        
        key = vals[0]
        value = self.cfg.get(section, key, fallback='')
        self.value_text.insert('1.0', value)
    
    def on_key_double_click(self, event=None):
        """Handler para duplo-clique em chave (edição)."""
        sel = self.keys_tree.selection()
        ssel = self.sections_lb.curselection()
        
        if not sel or not ssel:
            return
        
        section = self.sections_lb.get(ssel[0])
        item = sel[0]
        key = self.keys_tree.item(item, 'values')[0]
        current = self.cfg.get(section, key, fallback='')
        
        new_value = self._show_edit_dialog(f'Editar {key}', current)
        if new_value is not None:
            self.cfg.set(section, key, new_value)
            # Atualizar preview
            preview = new_value.splitlines()[0] if new_value else ''
            if len(preview) > 200:
                preview = preview[:197] + '...'
            self.keys_tree.item(item, values=(key, preview))
    
    def _show_edit_dialog(self, title: str, initial_value: str) -> Optional[str]:
        """Mostra diálogo de edição multiline.
        
        Returns:
            Novo valor ou None se cancelado
        """
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.geometry('600x400')
        
        txt = tk.Text(dlg, wrap='word')
        txt.pack(fill='both', expand=True)
        txt.insert('1.0', initial_value)
        
        result = {'value': None}
        
        def do_ok():
            result['value'] = txt.get('1.0', 'end').rstrip('\n')
            dlg.destroy()
        
        def do_cancel():
            dlg.destroy()
        
        btns = ttk.Frame(dlg)
        btns.pack(fill='x')
        ttk.Button(btns, text='OK', command=do_ok).pack(side='left')
        ttk.Button(btns, text='Cancelar', command=do_cancel).pack(side='left', padx=6)
        
        self.wait_window(dlg)
        return result['value']
    
    def add_section(self):
        """Adiciona nova seção."""
        name = simple_input(self, 'Nova Seção', 'Nome da seção:')
        if not name:
            return
        
        if not self.cfg.has_section(name):
            self.cfg.add_section(name)
            self._show_ini_editor()
            idx = list(self.cfg.sections()).index(name)
            self.sections_lb.select_set(idx)
        else:
            messagebox.showinfo('Info', 'Seção já existe')
    
    def remove_section(self):
        """Remove seção selecionada."""
        sel = self.sections_lb.curselection()
        if not sel:
            return
        
        section = self.sections_lb.get(sel[0])
        if messagebox.askyesno('Confirmar', f'Remover seção "{section}"?'):
            self.cfg.remove_section(section)
            self._show_ini_editor()
    
    def add_key(self):
        """Adiciona nova chave."""
        ssel = self.sections_lb.curselection()
        if not ssel:
            messagebox.showinfo('Info', 'Selecione uma seção primeiro')
            return
        
        section = self.sections_lb.get(ssel[0])
        key = simple_input(self, 'Nova Chave', 'Nome da chave:')
        if not key:
            return
        
        value = simple_input(self, 'Valor', 'Valor inicial (opcional):') or ''
        self.cfg.set(section, key, value)
        self.on_section_select()
    
    def remove_key(self):
        """Remove chave selecionada."""
        ksel = self.keys_tree.selection()
        ssel = self.sections_lb.curselection()
        
        if not ksel or not ssel:
            return
        
        section = self.sections_lb.get(ssel[0])
        item = ksel[0]
        key = self.keys_tree.item(item, 'values')[0]
        
        if messagebox.askyesno('Confirmar', f'Remover chave "{key}"?'):
            self.cfg.remove_option(section, key)
            self.on_section_select()
    
    def save_current(self):
        """Salva arquivo atual."""
        if not self.current_file:
            messagebox.showinfo('Info', 'Nenhum arquivo aberto')
            return
        
        # Se há seleção de key (modo INI), atualiza cfg com valor do editor
        if hasattr(self, 'keys_tree') and hasattr(self, 'sections_lb'):
            try:
                ksel = self.keys_tree.selection()
                ssel = self.sections_lb.curselection()
                if ksel and ssel:
                    section = self.sections_lb.get(ssel[0])
                    item = ksel[0]
                    key = self.keys_tree.item(item, 'values')[0]
                    value = self.value_text.get('1.0', 'end').rstrip('\n')
                    self.cfg.set(section, key, value)
            except Exception:
                pass
        
        encoding = self.current_encoding or 'utf-8'
        
        try:
            # Escrever temporário
            tmp = self.current_file.with_suffix(self.current_file.suffix + '.tmp')
            with tmp.open('w', encoding=encoding, errors='replace', newline='') as fh:
                self.cfg.write(fh)
            
            # Criar backup
            bak = self.current_file.with_name(self.current_file.name + '.bak')
            if self.current_file.exists():
                try:
                    self.current_file.replace(bak)
                except Exception:
                    import shutil
                    shutil.copy2(str(self.current_file), str(bak))
            
            # Mover temporário para original
            tmp.replace(self.current_file)
            messagebox.showinfo('Salvo', f'Arquivo salvo: {self.current_file}\n(backup: {bak.name})')
        except Exception as e:
            messagebox.showerror('Erro', f'Erro ao salvar: {e}')
    
    def reload_current(self):
        """Recarrega arquivo atual."""
        if self.current_file:
            self.open_file(self.current_file)


def simple_input(root, title: str, prompt: str) -> Optional[str]:
    """Mostra diálogo simples de input.
    
    Returns:
        Valor digitado ou None se cancelado
    """
    dlg = tk.Toplevel(root)
    dlg.title(title)
    dlg.transient(root)
    dlg.grab_set()
    
    ttk.Label(dlg, text=prompt).pack(padx=10, pady=6)
    ent = ttk.Entry(dlg, width=60)
    ent.pack(padx=10, pady=(0, 10))
    ent.focus()
    
    result = {'value': None}
    
    def ok():
        result['value'] = ent.get().strip()
        dlg.destroy()
    
    def cancel():
        dlg.destroy()
    
    btns = ttk.Frame(dlg)
    btns.pack(pady=(0, 10))
    ttk.Button(btns, text='OK', command=ok).pack(side='left')
    ttk.Button(btns, text='Cancelar', command=cancel).pack(side='left', padx=6)
    
    root.wait_window(dlg)
    return result['value']


if __name__ == '__main__':
    app = IniEditorApp()
    app.mainloop()
