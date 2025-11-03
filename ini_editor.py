# -*- coding: latin-1 -*-
"""
INI Editor - GUI principal reescrito
- Lista arquivos em Assets/
- Detecta arquivos pipe-delimited (items) usando src.parser
- Abre visualização tabular para arquivos de items (src.item_table_view)
- Para INI tradicionais, mostra seções/chaves/valor e permite editar/salvar usando a codificação detectada

Uso: python ini_editor.py
"""

from pathlib import Path
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import configparser
from typing import Optional

# tenta importar módulos do pacote src
try:
    from src import parser as data_parser
    from src import item_table_view
except Exception:
    data_parser = None
    item_table_view = None

PREFERRED_ENCODINGS = ['utf-8', 'big5', 'cp1252', 'latin-1']

SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR / 'Assets'
HEADERS_DIR = ASSETS_DIR / 'Headers'
H_ITEM = HEADERS_DIR / 'h_item'


def read_text_with_encodings(path: Path, encodings=None):
    """Tenta ler o arquivo com várias encodings até encontrar que funcione.
    Retorna (text, encoding)
    """
    # se não informado, usar encodings preferidas
    if encodings is None:
        encodings = PREFERRED_ENCODINGS

    # Leitura de bytes e heurística de seleção de encoding baseada em contagem de
    # caracteres CJK e número de caracteres de substituição (). Isso evita escolher
    # latin-1/cp1252 quando o conteúdo for Big5 (chines tradicional).
    raw = path.read_bytes()
    best = None
    best_score = None
    import re
    cjk_re = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
    for enc in encodings:
        try:
            txt = raw.decode(enc, errors='replace')
        except Exception:
            continue
        repl = txt.count('\ufffd') + txt.count('')
        cjk = len(cjk_re.findall(txt))
        # score: prefer many CJK chars and penalize replacements
        score = cjk * 10 - repl * 100
        if best_score is None or score > best_score:
            best_score = score
            best = (txt, enc)

    if best is not None:
        return best
    # fallback permissivo
    return raw.decode('latin-1', errors='replace'), 'latin-1'


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
        # Layout: left = file list, right = viewer (sections + table + value editor)
        main = ttk.Frame(self)
        main.pack(fill='both', expand=True)

        left = ttk.Frame(main, width=320)
        left.pack(side='left', fill='y')

        ttk.Label(left, text='Arquivos (Assets)').pack(anchor='w', padx=8, pady=(8,0))
        self.file_listbox = tk.Listbox(left, width=48)
        self.file_listbox.pack(fill='y', expand=True, padx=8, pady=8)
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_select)

        btns = ttk.Frame(left)
        btns.pack(fill='x', padx=8, pady=8)
        ttk.Button(btns, text='Recarregar', command=self.refresh_file_list).pack(side='left')
        ttk.Button(btns, text='Abrir pasta...', command=self.choose_folder).pack(side='left', padx=6)

        # right area
        right = ttk.Frame(main)
        right.pack(side='right', fill='both', expand=True)

        # área principal de visualização: centralizada e única (remoção do painel de seções/chaves)
        self.viewer_frame = ttk.Frame(right)
        self.viewer_frame.pack(fill='both', expand=True, padx=8, pady=8)

        # placeholder: uma Label discreta até um arquivo ser aberto
        self.viewer_placeholder = ttk.Label(self.viewer_frame, text='Abra um arquivo à esquerda para visualizar (tabela/RAW)')
        self.viewer_placeholder.pack(expand=True)

    def ensure_ini_widgets(self):
        """Cria os widgets necessários para editar INI (seções, chaves, editor) dentro de
        `self.viewer_frame` caso ainda não existam. Usado apenas quando abrimos um arquivo
        INI tradicional."""
        if hasattr(self, 'sections_lb') and hasattr(self, 'keys_tree') and hasattr(self, 'value_text'):
            return
        # limpar o conteúdo atual do viewer
        for c in list(self.viewer_frame.winfo_children()):
            c.destroy()

        top = ttk.Frame(self.viewer_frame)
        top.pack(fill='both', expand=True, padx=8, pady=8)

        # sections list
        sframe = ttk.Frame(top)
        sframe.pack(side='left', fill='y')
        ttk.Label(sframe, text='Seções').pack(anchor='w')
        self.sections_lb = tk.Listbox(sframe, width=30)
        self.sections_lb.pack(fill='y', expand=True)
        self.sections_lb.bind('<<ListboxSelect>>', self.on_section_select)
        sbtns = ttk.Frame(sframe)
        sbtns.pack(fill='x', pady=6)
        ttk.Button(sbtns, text='Nova Seção', command=self.add_section).pack(side='left')
        ttk.Button(sbtns, text='Remover Seção', command=self.remove_section).pack(side='left', padx=6)

        # keys table
        kframe = ttk.Frame(top)
        kframe.pack(side='left', fill='both', expand=True, padx=(8,0))
        ttk.Label(kframe, text='Chaves (tabela)').pack(anchor='w')
        self.keys_tree = ttk.Treeview(kframe, columns=('key', 'value'), show='headings')
        self.keys_tree.heading('key', text='Chave')
        self.keys_tree.heading('value', text='Valor (preview)')
        self.keys_tree.column('key', width=220, anchor='w')
        self.keys_tree.column('value', width=420, anchor='w')
        self.keys_tree.pack(fill='both', expand=True)
        self.keys_tree.bind('<<TreeviewSelect>>', self.on_key_select)
        self.keys_tree.bind('<Double-1>', self.on_key_double_click)

        kbtns = ttk.Frame(kframe)
        kbtns.pack(fill='x', pady=6)
        ttk.Button(kbtns, text='Nova Chave', command=self.add_key).pack(side='left')
        ttk.Button(kbtns, text='Remover Chave', command=self.remove_key).pack(side='left', padx=6)

        # value editor
        vframe = ttk.Frame(top)
        vframe.pack(side='left', fill='both', expand=True, padx=(8,0))
        ttk.Label(vframe, text='Valor').pack(anchor='w')
        self.value_text = tk.Text(vframe, wrap='none')
        self.value_text.pack(fill='both', expand=True)

        vbtns = ttk.Frame(vframe)
        vbtns.pack(fill='x', pady=6)
        ttk.Button(vbtns, text='Salvar', command=self.save_current).pack(side='left')
        ttk.Button(vbtns, text='Recarregar', command=self.reload_current).pack(side='left', padx=6)

    def refresh_file_list(self):
        self.file_listbox.delete(0, 'end')
        if not self.assets_dir.exists():
            messagebox.showwarning('Assets não encontrado', f'Pasta {self.assets_dir} não existe.')
            return
        files = []
        for root, dirs, filenames in os.walk(self.assets_dir):
            for f in filenames:
                if f.lower().endswith('.ini') or f.lower().endswith('.txt'):
                    full = Path(root) / f
                    try:
                        rel = full.relative_to(SCRIPT_DIR)
                    except Exception:
                        rel = full
                    files.append(rel)
        files.sort()
        for p in files:
            self.file_listbox.insert('end', str(p))

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=str(SCRIPT_DIR), title='Escolha a pasta Assets')
        if not folder:
            return
        self.assets_dir = Path(folder)
        self.refresh_file_list()

    def on_file_select(self, event=None):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        rel = self.file_listbox.get(sel[0])
        path = Path(rel)
        if not path.is_absolute():
            path = SCRIPT_DIR / rel
        self.open_file(path)

    def open_file(self, path: Path):
        self.current_file = path
        try:
            text, enc = read_text_with_encodings(path)
            self.current_encoding = enc
        except Exception as e:
            messagebox.showerror('Erro ao abrir', f'Erro ao ler {path}: {e}')
            return

        # primeiro tente detectar arquivos pipe-delimited (items) usando headers correspondentes
        try:
            if data_parser:
                # construir candidatos de header com base no nome do arquivo
                stem = path.stem.lower()  # ex: 'c_item' ou 'c_itemmall'
                candidates = []
                if stem.startswith('c_'):
                    candidates.append('h_' + stem[2:])
                if stem.startswith('c') and not stem.startswith('c_'):
                    candidates.append('h' + stem[1:])
                candidates.append('h_' + stem)
                # não adicionar fallback genérico (usar apenas header com mesmo nome);
                # se nenhum header existir, geraremos Unknown headers abaixo

                # detectar linha de metadados no início do arquivo (ex: "|V.16|93|")
                import re
                meta_re = re.compile(r'^[\|\s]*V\.\d+\|(\d+)\|')
                expected_fields_from_meta = None
                # procurar na primeira 5 linhas
                for ln in text.splitlines()[:5]:
                    m = meta_re.match(ln.strip())
                    if m:
                        try:
                            expected_fields_from_meta = int(m.group(1))
                        except Exception:
                            expected_fields_from_meta = None
                        break

                # procurar header cujo nome corresponda a um dos padrões desejados
                chosen_headers = None
                chosen_path = None
                # construir nomes-alvo (sem considerar extensão), case-insensitive
                stem_orig = path.stem  # e.g. 'C_Item'
                stem_low = stem_orig.lower()
                if stem_low.startswith('c_'):
                    stripped = stem_low[2:]
                elif stem_low.startswith('c'):
                    stripped = stem_low[1:]
                else:
                    stripped = stem_low

                target_names = set([
                    f"h_{stem_low}",      # h_c_item or similar
                    f"h_{stripped}",      # h_item
                    f"h{stripped}",       # hitem
                    f"h{stem_low}",       # hc_item
                    f"h_{stem_orig.lower()}",
                    f"h_{stem_orig}",
                    f"h_{path.name.lower()}",
                    f"h_{path.name}",
                    f"h_{path.stem}",
                    f"h_{path.stem.lower()}",
                    f"h_{stripped}",
                    f"h_{stripped}.ini",
                    f"h_{stem_low}.ini",
                    f"h_{stem_orig}.ini",
                    f"h_{path.stem}.ini",
                    f"h_{path.name}.ini",
                    f"h_{path.name.lower()}.ini",
                    f"H_{path.stem}",     # H_C_Item
                    f"H_{path.stem}.ini",
                ])

                # procurar arquivos no diretório Headers que batam com os nomes-alvo (case-insensitive)
                if HEADERS_DIR.exists():
                    # priorizar nome padronizado 'H_<stem>' (case-insensitive)
                    prioritized = []
                    prioritized.extend([f'H_{path.stem}', f'h_{path.stem.lower()}'])
                    # depois procurar outros candidatos encontrados anteriormente
                    prioritized.extend(list(target_names))
                    seen = set()
                    for hf in HEADERS_DIR.iterdir():
                        if not hf.is_file():
                            continue
                        name_no_ext = hf.stem
                        lname = name_no_ext.lower()
                        if lname in {s.lower() for s in prioritized} and lname not in seen:
                            seen.add(lname)
                            try:
                                hdrs = data_parser.load_headers(hf)
                            except Exception:
                                continue
                            # se temos metadado, validar/ajustar tamanho do header
                            if expected_fields_from_meta is not None:
                                if len(hdrs) != expected_fields_from_meta:
                                    # ajustar hdrs: truncar ou preencher com Unknown
                                    if len(hdrs) > expected_fields_from_meta:
                                        hdrs = hdrs[:expected_fields_from_meta]
                                    else:
                                        hdrs = hdrs + [f'Unknown {i}' for i in range(len(hdrs), expected_fields_from_meta)]
                            if data_parser.is_pipe_file(text, hdrs):
                                chosen_headers = hdrs
                                chosen_path = hf
                                break

                # se encontramos headers compatíveis, parse e mostrar
                if chosen_headers is not None:
                    records = data_parser.parse_pipe_text(text, chosen_headers)
                    if item_table_view:
                        for c in list(self.viewer_frame.winfo_children()):
                            c.destroy()
                        item_table_view.show_item_table(self.viewer_frame, path.name, chosen_headers, records, encoding=enc, file_path=path, embed=True)
                        self.title(f'INI Editor — {path.name} (encoding: {enc})')
                        return

                # se não encontramos nenhum header existente, tentar deduzir número de campos
                # se não encontramos nenhum header existente, primeiro procurar linha de metadados
                # do tipo |V.<vers>|<ncols>| ou V.<vers>|<ncols>| e usar <ncols> como número de colunas
                import re
                meta_re = re.compile(r'^[\|\s]*V\.\d+\|(\d+)\|')
                lines = text.splitlines()
                ncols = None
                for ln in lines:
                    s = ln.strip()
                    if not s:
                        continue
                    m = meta_re.match(s)
                    if m:
                        try:
                            ncols = int(m.group(1))
                        except Exception:
                            ncols = None
                    break

                if ncols is None:
                    # fallback: procurar a linha com maior número de pipes e usar isso
                    max_pipes = 0
                    for ln in lines:
                        pc = ln.count('|')
                        if pc > max_pipes:
                            max_pipes = pc
                    if max_pipes >= 2:
                        ncols = max_pipes + 1

                if ncols and ncols >= 1:
                    expected_fields = ncols
                    # criar headers Unknown 0..N-1
                    gen_headers = [f'Unknown {i}' for i in range(expected_fields)]
                    records = data_parser.parse_pipe_text(text, gen_headers)
                    if item_table_view:
                        for c in list(self.viewer_frame.winfo_children()):
                            c.destroy()
                        # passa gen_headers — usuário poderá renomear via UI
                        item_table_view.show_item_table(self.viewer_frame, path.name, gen_headers, records, encoding=enc, file_path=path, embed=True)
                        self.title(f'INI Editor — {path.name} (encoding: {enc})')
                        return
        except Exception:
            # se falhar, continuar para tentar INI
            pass

        # tentar abrir como INI com configparser
        self.cfg = configparser.ConfigParser(allow_no_value=True)
        try:
            # prefer read_string (usamos o texto já lido)
            self.cfg.read_string(text)
        except configparser.MissingSectionHeaderError:
            # arquivo não tem seções — informar e mostrar raw
            messagebox.showinfo('Formato', f'O arquivo {path} não contém sections; abrindo visualizador bruto.')
            self.show_raw_text(text)
            return
        except Exception as e:
            # tentar ler via cfg.read
            try:
                self.cfg.read(path, encoding=enc)
            except Exception as e2:
                messagebox.showerror('Erro', f'Erro ao parsear INI: {e}\n{e2}')
                self.show_raw_text(text)
                return

        # preencher UI de INI
        self.populate_ini_ui()
        self.title(f'INI Editor — {path.name}')

    def show_raw_text(self, text: str):
        # mostrar raw dentro do viewer central (não abrir Toplevel)
        for c in list(self.viewer_frame.winfo_children()):
            c.destroy()
        lbl = ttk.Label(self.viewer_frame, text='Visualizador bruto')
        lbl.pack(anchor='w')
        txt = tk.Text(self.viewer_frame, wrap='none')
        txt.pack(fill='both', expand=True)
        txt.insert('1.0', text)

    def populate_ini_ui(self):
        # garantir widgets do editor INI
        self.ensure_ini_widgets()
        # preencher seções
        self.sections_lb.delete(0, 'end')
        for s in self.cfg.sections():
            self.sections_lb.insert('end', s)
        # limpar keys
        for iid in self.keys_tree.get_children():
            self.keys_tree.delete(iid)
        self.value_text.delete('1.0', 'end')

    def on_section_select(self, event=None):
        sel = self.sections_lb.curselection()
        for iid in self.keys_tree.get_children():
            self.keys_tree.delete(iid)
        self.value_text.delete('1.0', 'end')
        if not sel:
            return
        sec = self.sections_lb.get(sel[0])
        for k in self.cfg[sec]:
            v = self.cfg.get(sec, k, fallback='')
            preview = v.splitlines()[0] if v else ''
            if len(preview) > 200:
                preview = preview[:197] + '...'
            self.keys_tree.insert('', 'end', values=(k, preview))

    def on_key_select(self, event=None):
        sel = self.keys_tree.selection()
        ssel = self.sections_lb.curselection()
        self.value_text.delete('1.0', 'end')
        if not sel or not ssel:
            return
        sec = self.sections_lb.get(ssel[0])
        item = sel[0]
        vals = self.keys_tree.item(item, 'values')
        if not vals:
            return
        key = vals[0]
        val = self.cfg.get(sec, key, fallback='')
        self.value_text.insert('1.0', val)

    def on_key_double_click(self, event=None):
        # editar value in-place: abre drawer similar ao item_table_view
        sel = self.keys_tree.selection()
        ssel = self.sections_lb.curselection()
        if not sel or not ssel:
            return
        sec = self.sections_lb.get(ssel[0])
        item = sel[0]
        key = self.keys_tree.item(item, 'values')[0]
        cur = self.cfg.get(sec, key, fallback='')
        dlg = tk.Toplevel(self)
        dlg.title(f'Editar {key}')
        dlg.geometry('600x400')
        txt = tk.Text(dlg, wrap='word')
        txt.pack(fill='both', expand=True)
        txt.insert('1.0', cur)

        def do_ok():
            new = txt.get('1.0', 'end').rstrip('\n')
            self.cfg.set(sec, key, new)
            # atualizar preview
            preview = new.splitlines()[0] if new else ''
            if len(preview) > 200:
                preview = preview[:197] + '...'
            self.keys_tree.item(item, values=(key, preview))
            dlg.destroy()

        def do_cancel():
            dlg.destroy()

        fb = ttk.Frame(dlg)
        fb.pack(fill='x')
        ttk.Button(fb, text='OK', command=do_ok).pack(side='left')
        ttk.Button(fb, text='Cancelar', command=do_cancel).pack(side='left', padx=6)

    def add_section(self):
        name = simple_input(self, 'Nova Seção', 'Nome da seção:')
        if not name:
            return
        if not self.cfg.has_section(name):
            self.cfg.add_section(name)
            self.populate_ini_ui()
            idx = list(self.cfg.sections()).index(name)
            self.sections_lb.select_set(idx)
        else:
            messagebox.showinfo('Info', 'Seção já existe')

    def remove_section(self):
        sel = self.sections_lb.curselection()
        if not sel:
            return
        sec = self.sections_lb.get(sel[0])
        if messagebox.askyesno('Confirmar', f'Remover seção "{sec}"?'):
            self.cfg.remove_section(sec)
            self.populate_ini_ui()

    def add_key(self):
        ssel = self.sections_lb.curselection()
        if not ssel:
            messagebox.showinfo('Info', 'Selecione uma seção primeiro')
            return
        sec = self.sections_lb.get(ssel[0])
        key = simple_input(self, 'Nova Chave', 'Nome da chave:')
        if not key:
            return
        val = simple_input(self, 'Valor', 'Valor inicial (opcional):') or ''
        self.cfg.set(sec, key, val)
        self.on_section_select()

    def remove_key(self):
        ksel = self.keys_tree.selection()
        ssel = self.sections_lb.curselection()
        if not ksel or not ssel:
            return
        sec = self.sections_lb.get(ssel[0])
        item = ksel[0]
        key = self.keys_tree.item(item, 'values')[0]
        if messagebox.askyesno('Confirmar', f'Remover chave "{key}"?'):
            self.cfg.remove_option(sec, key)
            self.on_section_select()

    def save_current(self):
        if not self.current_file:
            messagebox.showinfo('Info', 'Nenhum arquivo aberto')
            return
        # se há seleção de key (modo INI), atualiza a cfg com o valor do editor
        if hasattr(self, 'keys_tree') and hasattr(self, 'sections_lb'):
            try:
                ksel = self.keys_tree.selection()
                ssel = self.sections_lb.curselection()
                if ksel and ssel:
                    sec = self.sections_lb.get(ssel[0])
                    item = ksel[0]
                    key = self.keys_tree.item(item, 'values')[0]
                    val = self.value_text.get('1.0', 'end').rstrip('\n')
                    self.cfg.set(sec, key, val)
            except Exception:
                # se não houver widgets (modo table), ignora
                pass

        enc = self.current_encoding or 'utf-8'
        # salvar com encoding detectado
        try:
            # gravar atomically: escrever em temporário e renomear
            tmp = self.current_file.with_suffix(self.current_file.suffix + '.tmp')
            with tmp.open('w', encoding=enc, errors='replace', newline='') as fh:
                self.cfg.write(fh)
            # backup
            bak = self.current_file.with_name(self.current_file.name + '.bak')
            try:
                if self.current_file.exists():
                    self.current_file.replace(bak)
            except Exception:
                import shutil
                shutil.copy2(str(self.current_file), str(bak))
            # move tmp to original
            tmp.replace(self.current_file)
            messagebox.showinfo('Salvo', f'Arquivo salvo: {self.current_file} (backup: {bak.name})')
        except Exception as e:
            messagebox.showerror('Erro', f'Erro ao salvar: {e}')

    def reload_current(self):
        if not self.current_file:
            return
        self.open_file(self.current_file)


def simple_input(root, title, prompt):
    dlg = tk.Toplevel(root)
    dlg.title(title)
    dlg.transient(root)
    dlg.grab_set()
    ttk.Label(dlg, text=prompt).pack(padx=10, pady=6)
    ent = ttk.Entry(dlg, width=60)
    ent.pack(padx=10, pady=(0,10))
    ent.focus()

    res = {'value': None}

    def ok():
        res['value'] = ent.get().strip()
        dlg.destroy()

    def cancel():
        dlg.destroy()

    btns = ttk.Frame(dlg)
    btns.pack(pady=(0,10))
    ttk.Button(btns, text='OK', command=ok).pack(side='left')
    ttk.Button(btns, text='Cancelar', command=cancel).pack(side='left', padx=6)

    root.wait_window(dlg)
    return res['value']


if __name__ == '__main__':
    app = IniEditorApp()
    app.mainloop()
