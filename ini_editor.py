# -*- coding: latin-1 -*-
"""
Editor simples de arquivos INI
- Lista arquivos .ini e .txt (opcional) dentro de `Assets/` (recursivo)
- Mostra seções e chaves
- Permite adicionar/editar/remover chaves e seções
- Salva alterações no arquivo selecionado

Uso: python ini_editor.py
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import configparser
from pathlib import Path

# módulos do pacote src
try:
    from src import parser as data_parser
    from src import item_table_view
except Exception:
    data_parser = None
    item_table_view = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, 'Assets')

# Encodings tentadas ao abrir arquivos INI (ordem importa: mais prováveis primeiro)
PREFERRED_ENCODINGS = [
    'utf-8',
    'utf-8-sig',
    'utf-16',
    'utf-16le',
    'utf-16be',
    'big5',
    'cp1252',  # Windows ANSI / Western European
    'latin-1',
]

class IniEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('INI Editor')
        self.geometry('900x600')

        self.config_file = None
        # Guarda a codificação detectada do arquivo aberto (para salvar com mesma codificação)
        self.file_encoding = None
        # configparser permissivo para valores sem = (opcional)
        self.cfg = configparser.ConfigParser(allow_no_value=True)

        self.create_widgets()
        self.load_assets_directory()

    def create_widgets(self):
        # Left: arquivos
        left = ttk.Frame(self)
        left.pack(side='left', fill='y')

        ttk.Label(left, text='Arquivos (Assets)').pack(anchor='w', padx=6, pady=(6,0))
        self.file_list = tk.Listbox(left, width=40)
        self.file_list.pack(fill='y', expand=True, padx=6, pady=6)
        self.file_list.bind('<<ListboxSelect>>', self.on_file_select)

        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill='x', padx=6, pady=6)
        ttk.Button(btn_frame, text='Recarregar', command=self.load_assets_directory).pack(side='left')
        ttk.Button(btn_frame, text='Abrir Pasta...', command=self.choose_folder).pack(side='left', padx=6)

        # Right: secões/chaves/valor
        right = ttk.Frame(self)
        right.pack(side='right', fill='both', expand=True)

        top_right = ttk.Frame(right)
        top_right.pack(fill='both', expand=True, padx=6, pady=6)

        # Sections
        s_frame = ttk.Frame(top_right)
        s_frame.pack(side='left', fill='y')
        ttk.Label(s_frame, text='Seções').pack(anchor='w')
        self.section_list = tk.Listbox(s_frame, width=28)
        self.section_list.pack(fill='y', expand=True)
        self.section_list.bind('<<ListboxSelect>>', self.on_section_select)

        s_btns = ttk.Frame(s_frame)
        s_btns.pack(fill='x', pady=6)
        ttk.Button(s_btns, text='Nova Seção', command=self.add_section).pack(side='left')
        ttk.Button(s_btns, text='Remover Seção', command=self.remove_section).pack(side='left', padx=6)

        # Keys (tabela tipo CSV: coluna Chave | Valor)
        k_frame = ttk.Frame(top_right)
        k_frame.pack(side='left', fill='y', padx=(8,0))
        ttk.Label(k_frame, text='Chaves (tabela)').pack(anchor='w')

        # Treeview com duas colunas: Chave e Valor (preview)
        cols = ('chave', 'valor')
        self.key_tree = ttk.Treeview(k_frame, columns=cols, show='headings', selectmode='browse', height=20)
        self.key_tree.heading('chave', text='Chave')
        self.key_tree.heading('valor', text='Valor (preview)')
        self.key_tree.column('chave', width=180, anchor='w')
        self.key_tree.column('valor', width=320, anchor='w')
        self.key_tree.pack(fill='y', expand=True)
        self.key_tree.bind('<<TreeviewSelect>>', self.on_key_select)

        k_btns = ttk.Frame(k_frame)
        k_btns.pack(fill='x', pady=6)
        ttk.Button(k_btns, text='Nova Chave', command=self.add_key).pack(side='left')
        ttk.Button(k_btns, text='Remover Chave', command=self.remove_key).pack(side='left', padx=6)

        # Value editor
        v_frame = ttk.Frame(top_right)
        v_frame.pack(side='left', fill='both', expand=True, padx=(8,0))
        ttk.Label(v_frame, text='Valor').pack(anchor='w')
        self.value_text = tk.Text(v_frame, wrap='none')
        self.value_text.pack(fill='both', expand=True)

        save_frame = ttk.Frame(v_frame)
        save_frame.pack(fill='x', pady=6)
        ttk.Button(save_frame, text='Salvar', command=self.save_file).pack(side='left')
        ttk.Button(save_frame, text='Recarregar Arquivo', command=self.reload_current_file).pack(side='left', padx=6)

    def load_assets_directory(self):
        self.file_list.delete(0, 'end')
        if not os.path.isdir(ASSETS_DIR):
            messagebox.showwarning('Assets não encontrado', f"Pasta {ASSETS_DIR} não existe. Escolha a pasta Assets.")
            self.choose_folder()
            return

        files = []
        for root, dirs, filenames in os.walk(ASSETS_DIR):
            for f in filenames:
                if f.lower().endswith('.ini') or f.lower().endswith('.txt'):
                    files.append(os.path.join(root, f))
        files.sort()
        for p in files:
            self.file_list.insert('end', os.path.relpath(p, SCRIPT_DIR))

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=SCRIPT_DIR, title='Escolha a pasta Assets')
        if not folder:
            return
        global ASSETS_DIR
        ASSETS_DIR = folder
        self.load_assets_directory()

    def on_file_select(self, event=None):
        sel = self.file_list.curselection()
        if not sel:
            return
        rel = self.file_list.get(sel[0])
        path = os.path.join(SCRIPT_DIR, rel)
        self.open_file(path)

    def open_file(self, path):
        self.config_file = path
        self.file_encoding = None
        self._wrapped_root = False

        # tenta várias codificações até encontrar uma que permita leitura
        last_exception = None
        for enc in PREFERRED_ENCODINGS:
            try:
                with open(path, 'r', encoding=enc) as fh:
                    text = fh.read()

                # Detectar se é um arquivo pipe-delimited (items) comparando com header se disponível
                try:
                    headers_path = Path(SCRIPT_DIR) / 'Assets' / 'Headers' / 'h_item'
                    if headers_path.exists() and data_parser:
                        headers = data_parser.load_headers(headers_path)
                        # primeira tentativa rápida de detecção por amostra
                        sample = text[:16000]
                        expected_separators = max(0, len(headers) - 1)
                        is_pipe_sample = data_parser.detect_pipe_file_sample(sample, expected_separators)

                        # tenta parsear do texto lido para ser mais robusto (registros multilinha)
                        records = data_parser.parse_pipe_text(text, headers)
                        # heurística: considerar pipe-file se obtivemos pelo menos 1 registro
                        # e o primeiro registro tem a quantidade de campos esperada
                        if records and isinstance(records, list) and len(records[0]) == len(headers):
                            # abrir visualizador com encoding detectado nesta tentativa
                            self.file_encoding = enc
                            if item_table_view:
                                item_table_view.show_item_table(self, os.path.basename(path), headers, records, encoding=enc, file_path=Path(path))
                                return
                        # se não detectado e detect_pipe_file_sample indicar True, tentar parse via arquivo
                        if not records and is_pipe_sample:
                            records, used_enc = data_parser.parse_pipe_file(Path(path), headers)
                            if records:
                                self.file_encoding = used_enc
                                if item_table_view:
                                    item_table_view.show_item_table(self, os.path.basename(path), headers, records, encoding=used_enc, file_path=Path(path))
                                    return
                except Exception:
                    # se algo falhar no parser especializado, continuar para tentar configparser
                    pass

                # tenta interpretar com configparser
                cfg = configparser.ConfigParser(allow_no_value=True)
                try:
                    cfg.read_string(text)
                    self.cfg = cfg
                    self.file_encoding = enc
                    break
                except configparser.MissingSectionHeaderError:
                    # alguns INI não têm seção; tente ler com read (file path) usando encoding
                    cfg = configparser.ConfigParser(allow_no_value=True)
                    try:
                        # read aceita encoding desde Python 3.2
                        cfg.read(path, encoding=enc)
                        self.cfg = cfg
                        self.file_encoding = enc
                        break
                    except Exception as e:
                        last_exception = e
                        continue
                except Exception as e:
                    last_exception = e
                    continue
            except Exception as e:
                last_exception = e
                continue

        if not self.file_encoding:
            # última tentativa: leitura permissiva com latin-1 (mapeia bytes 1:1)
            try:
                with open(path, 'r', encoding='latin-1', errors='replace') as fh:
                    text = fh.read()
                cfg = configparser.ConfigParser(allow_no_value=True)
                try:
                    cfg.read_string(text)
                    self.cfg = cfg
                except Exception:
                    cfg.read(path, encoding='latin-1')
                    self.cfg = cfg
                self.file_encoding = 'latin-1'
            except Exception as e:
                messagebox.showerror('Erro', f'Erro ao abrir {path}: {e}\n{last_exception}')
                return

        self.refresh_ui()
        self.title(f'INI Editor — {os.path.relpath(path, SCRIPT_DIR)}')

    def refresh_ui(self):
        # sections
        self.section_list.delete(0, 'end')
        for s in self.cfg.sections():
            self.section_list.insert('end', s)
        # limpa tabela de chaves
        try:
            for iid in self.key_tree.get_children():
                self.key_tree.delete(iid)
        except Exception:
            pass
        self.value_text.delete('1.0', 'end')

    def on_section_select(self, event=None):
        sel = self.section_list.curselection()
        # limpa tabela
        try:
            for iid in self.key_tree.get_children():
                self.key_tree.delete(iid)
        except Exception:
            pass
        self.value_text.delete('1.0', 'end')
        if not sel:
            return
        sec = self.section_list.get(sel[0])
        for k in self.cfg[sec]:
            val = self.cfg.get(sec, k, fallback='')
            # preview: primeira linha ou truncado
            preview = val.splitlines()[0] if val else ''
            if len(preview) > 200:
                preview = preview[:197] + '...'
            self.key_tree.insert('', 'end', values=(k, preview))

    def on_key_select(self, event=None):
        sel = self.key_tree.selection()
        ssel = self.section_list.curselection()
        self.value_text.delete('1.0', 'end')
        if not sel or not ssel:
            return
        sec = self.section_list.get(ssel[0])
        item = sel[0]
        vals = self.key_tree.item(item, 'values')
        if not vals:
            return
        key = vals[0]
        val = self.cfg.get(sec, key, fallback='')
        self.value_text.insert('1.0', val)

    def add_section(self):
        name = simple_input(self, 'Nova Seção', 'Nome da seção:')
        if not name:
            return
        if not self.cfg.has_section(name):
            self.cfg.add_section(name)
            self.refresh_ui()
            # select new
            idx = self.section_list.get(0, 'end').index(name)
            self.section_list.select_set(idx)
        else:
            messagebox.showinfo('Info', 'Seção já existe')

    def remove_section(self):
        sel = self.section_list.curselection()
        if not sel:
            return
        sec = self.section_list.get(sel[0])
        if messagebox.askyesno('Confirmar', f'Remover seção "{sec}"?'):
            self.cfg.remove_section(sec)
            self.refresh_ui()

    def add_key(self):
        ssel = self.section_list.curselection()
        if not ssel:
            messagebox.showinfo('Info', 'Selecione uma seção primeiro')
            return
        sec = self.section_list.get(ssel[0])
        key = simple_input(self, 'Nova Chave', 'Nome da chave:')
        if not key:
            return
        val = simple_input(self, 'Valor', 'Valor inicial (opcional):') or ''
        self.cfg.set(sec, key, val)
        # atualiza tabela
        self.on_section_select()
        # selecionar nova chave na tabela
        for iid in self.key_tree.get_children():
            if self.key_tree.item(iid, 'values')[0] == key:
                self.key_tree.selection_set(iid)
                self.key_tree.see(iid)
                break

    def remove_key(self):
        ksel = self.key_tree.selection()
        ssel = self.section_list.curselection()
        if not ksel or not ssel:
            return
        sec = self.section_list.get(ssel[0])
        item = ksel[0]
        key = self.key_tree.item(item, 'values')[0]
        if messagebox.askyesno('Confirmar', f'Remover chave "{key}"?'):
            self.cfg.remove_option(sec, key)
            self.on_section_select()

    def save_file(self):
        if not self.config_file:
            messagebox.showinfo('Info', 'Nenhum arquivo aberto')
            return
        # if a key is selected, store current text
        ksel = self.key_tree.selection()
        ssel = self.section_list.curselection()
        if ksel and ssel:
            sec = self.section_list.get(ssel[0])
            item = ksel[0]
            key = self.key_tree.item(item, 'values')[0]
            val = self.value_text.get('1.0', 'end').rstrip('\n')
            self.cfg.set(sec, key, val)

        try:
            enc = self.file_encoding or 'utf-8'
            # escreve usando a codificação detectada (ou utf-8 por padrão)
            with open(self.config_file, 'w', encoding=enc, errors='replace') as fh:
                self.cfg.write(fh)
            messagebox.showinfo('Salvo', f'Arquivo salvo: {os.path.relpath(self.config_file, SCRIPT_DIR)} (codificação: {enc})')
        except Exception as e:
            messagebox.showerror('Erro', f'Erro ao salvar: {e}')

    def reload_current_file(self):
        if not self.config_file:
            return
        self.open_file(self.config_file)


def simple_input(root, title, prompt):
    dlg = tk.Toplevel(root)
    dlg.title(title)
    dlg.transient(root)
    dlg.grab_set()
    ttk.Label(dlg, text=prompt).pack(padx=10, pady=6)
    ent = ttk.Entry(dlg, width=60)
    ent.pack(padx=10, pady=(0,10))
    ent.focus()

    result = {'value': None}

    def ok():
        result['value'] = ent.get().strip()
        dlg.destroy()

    def cancel():
        dlg.destroy()

    btns = ttk.Frame(dlg)
    btns.pack(pady=(0,10))
    ttk.Button(btns, text='OK', command=ok).pack(side='left')
    ttk.Button(btns, text='Cancelar', command=cancel).pack(side='left', padx=6)

    root.wait_window(dlg)
    return result['value']

if __name__ == '__main__':
    app = IniEditor()
    app.mainloop()
