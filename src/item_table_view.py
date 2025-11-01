# -*- coding: latin-1 -*-
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import List, Dict, Optional


def show_item_table(parent, title: str, headers: List[str], records: List[Dict[str, str]], encoding: str = 'utf-8', file_path: Optional[Path] = None, embed: bool = False):
    """Mostra os registros em uma Treeview.

    Se embed==False (padrão), abre em Toplevel; se embed==True, usa o widget fornecido em `parent`
    como container (por exemplo um Frame dentro da janela principal).
    """
    if embed:
        container = parent
    else:
        win = tk.Toplevel(parent)
        win.title(f"{title} — encoding: {encoding}")
        win.geometry('1200x600')
        container = ttk.Frame(win)
        container.pack(fill='both', expand=True)

    # container para Treeview + scrollbars
    tv_frame = ttk.Frame(container)
    # centralizar visualização com padding
    tv_frame.pack(fill='both', expand=True, padx=12, pady=8)

    cols = headers
    tree = ttk.Treeview(tv_frame, columns=cols, show='headings')

    # configura colunas
    for c in cols:
        # largura proporcional, Name/Tip normalmente maior
        width = 120 if c.lower() not in ('name', 'tip') else 300
        tree.heading(c, text=c, anchor='center')
        tree.column(c, width=width, anchor='center')

    # scrollbars
    vbar = ttk.Scrollbar(tv_frame, orient='vertical', command=tree.yview)
    hbar = ttk.Scrollbar(tv_frame, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

    tree.grid(row=0, column=0, sticky='nsew')
    vbar.grid(row=0, column=1, sticky='ns')
    hbar.grid(row=1, column=0, sticky='ew')

    tv_frame.rowconfigure(0, weight=1)
    tv_frame.columnconfigure(0, weight=1)

    # inserir registros (cuidado com muitos registros)
    # inserir registros em lotes para evitar travamento em arquivos grandes
    tree.tag_configure('odd', background='#ffffff')
    tree.tag_configure('even', background='#f7f7f7')

    # Frame de controle com progresso e botão de cancelar
    ctrl_frame = ttk.Frame(container)
    ctrl_frame.pack(fill='x', pady=(4, 8))
    progress_lbl = ttk.Label(ctrl_frame, text=f'Carregando 0 / {len(records)}')
    progress_lbl.pack(side='left')
    stop_btn = ttk.Button(ctrl_frame, text='Cancelar carregamento')
    stop_btn.pack(side='right')

    cancelled = {'v': False}
    def do_cancel():
        cancelled['v'] = True
        stop_btn.config(state='disabled')

    stop_btn.config(command=do_cancel)

    batch_size = 500  # número de linhas inseridas por lote (ajustável)

    children_cache = []

    def insert_batch(start=0):
        # se o container ou tree foram destruídos, aborta limpeza
        try:
            if cancelled['v']:
                progress_lbl.config(text=f'Carregamento cancelado em {start} / {len(records)}')
                return
        except Exception:
            return
        if not tree.winfo_exists():
            # widget já destruído, cancelar carregamento
            cancelled['v'] = True
            return
        end = min(start + batch_size, len(records))
        try:
            for i in range(start, end):
                rec = records[i]
                vals = [rec.get(h, '') for h in headers]
                tag = 'even' if (i % 2 == 0) else 'odd'
                tree.insert('', 'end', values=vals, tags=(tag,))
        except tk.TclError:
            # widget foi destruído durante a inserção (usuário fechou janela) -> cancelar
            cancelled['v'] = True
            try:
                progress_lbl.config(text=f'Carregamento cancelado (widget destruído) {start} / {len(records)}')
            except Exception:
                pass
            return
        progress_lbl.config(text=f'Carregando {end} / {len(records)}')
        # schedule next batch
        if end < len(records):
            container.after(10, insert_batch, end)
        else:
            progress_lbl.config(text=f'Carregado {len(records)} registros')
            stop_btn.config(state='disabled')

    # iniciar inserção assíncrona — não bloqueia a UI
    # marcar cancelado se o container for destruído (fecha janela enquanto carrega)
    def _on_destroy(event):
        cancelled['v'] = True

    container.bind('<Destroy>', _on_destroy)

    container.after(20, insert_batch, 0)

    # simples função para mostrar detalhe quando selecionar
    detail = tk.Text(container, height=6, wrap='word')
    detail.pack(fill='x')

    def on_select(event=None):
        sel = tree.selection()
        if not sel:
            return
        item = sel[0]
        vals = tree.item(item, 'values')
        # mostra só algumas colunas formatadas
        out_lines = []
        for h, v in zip(headers, vals):
            if v:
                out_lines.append(f"{h}: {v}")
        detail.delete('1.0', 'end')
        detail.insert('1.0', '\n'.join(out_lines))

    tree.bind('<<TreeviewSelect>>', on_select)

    # edição por duplo-clique: abre um editor para a célula (usando Toplevel Text para multilinha)
    def on_double_click(event):
        rowid = tree.identify_row(event.y)
        colid = tree.identify_column(event.x)  # e.g. '#3'
        if not rowid or not colid:
            return
        try:
            col_index = int(colid.replace('#', '')) - 1
        except Exception:
            return
        if col_index < 0 or col_index >= len(headers):
            return
        header = headers[col_index]
        item_index = list(tree.get_children()).index(rowid)
        current_val = records[item_index].get(header, '')

        # editor multi-line
        root_toplevel = win if not embed else parent.winfo_toplevel()
        dlg = tk.Toplevel(root_toplevel)
        dlg.title(f'Editar: {header}')
        dlg.geometry('600x400')
        txt = tk.Text(dlg, wrap='word')
        txt.pack(fill='both', expand=True)
        txt.insert('1.0', current_val)

        def do_ok():
            new_val = txt.get('1.0', 'end').rstrip('\n')
            records[item_index][header] = new_val
            # atualizar linha na treeview
            new_vals = [records[item_index].get(h, '') for h in headers]
            tree.item(rowid, values=new_vals)
            dlg.destroy()

        def do_cancel():
            dlg.destroy()

        btns = ttk.Frame(dlg)
        btns.pack(fill='x')
        ttk.Button(btns, text='OK', command=do_ok).pack(side='left')
        ttk.Button(btns, text='Cancelar', command=do_cancel).pack(side='left', padx=6)

    tree.bind('<Double-1>', on_double_click)

    # botão para exportar como CSV
    btn_frame = ttk.Frame(container)
    btn_frame.pack(fill='x')
    def export_csv():
        fpath = Path.cwd() / f"{title}.export.csv"
        import csv
        with fpath.open('w', newline='', encoding=encoding) as fh:
            w = csv.writer(fh)
            w.writerow(headers)
            for rec in records:
                w.writerow([rec.get(h, '') for h in headers])
        tk.messagebox.showinfo('Exportado', f'Exportado: {fpath}')

    ttk.Button(btn_frame, text='Exportar CSV', command=export_csv).pack(side='left')

    # salvar de volta para o arquivo pipe (se file_path fornecido)
    def save_back():
        if not file_path:
            tk.messagebox.showinfo('Salvar', 'Nenhum arquivo de destino fornecido.')
            return
        # backup
        bak = file_path.with_name(file_path.name + '.bak')
        try:
            if file_path.exists():
                file_path.replace(bak)  # move original to backup
        except Exception:
            # fallback copy
            try:
                import shutil
                shutil.copy2(str(file_path), str(bak))
            except Exception as e:
                tk.messagebox.showwarning('Backup falhou', f'Não foi possível criar backup: {e}')

        try:
            with file_path.open('w', encoding=encoding, errors='replace', newline='') as fh:
                for rec in records:
                    parts = [rec.get(h, '') for h in headers]
                    # garante que cada registro termine com newline
                    line = '|'.join(parts)
                    fh.write(line + '\n')
            tk.messagebox.showinfo('Salvo', f'Salvo em: {file_path} (backup: {bak.name})')
        except Exception as e:
            tk.messagebox.showerror('Erro', f'Erro ao salvar: {e}')

    if file_path:
        ttk.Button(btn_frame, text='Salvar no arquivo', command=save_back).pack(side='left', padx=6)

    if embed:
        return container
    return win
