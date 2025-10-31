import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import List, Dict, Optional


def show_item_table(parent, title: str, headers: List[str], records: List[Dict[str, str]], encoding: str = 'utf-8', file_path: Optional[Path] = None):
    """Abre uma janela Toplevel mostrando os registros em uma Treeview com colunas horizontais.

    headers: lista de nomes de colunas
    records: lista de dicts header->valor
    """
    win = tk.Toplevel(parent)
    win.title(f"{title} — encoding: {encoding}")
    win.geometry('1200x600')

    frm = ttk.Frame(win)
    frm.pack(fill='both', expand=True)

    # container para Treeview + scrollbars
    tv_frame = ttk.Frame(frm)
    tv_frame.pack(fill='both', expand=True)

    cols = headers
    tree = ttk.Treeview(tv_frame, columns=cols, show='headings')

    # configura colunas
    for c in cols:
        # largura proporcional, Name normalmente maior
        width = 120 if c.lower() != 'name' and c.lower() != 'tip' else 300
        tree.heading(c, text=c)
        tree.column(c, width=width, anchor='w')

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
    for i, rec in enumerate(records):
        # ordem dos valores de acordo com headers
        vals = [rec.get(h, '') for h in headers]
        tree.insert('', 'end', values=vals)

    # simples função para mostrar detalhe quando selecionar
    detail = tk.Text(frm, height=6, wrap='word')
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
        dlg = tk.Toplevel(win)
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
    btn_frame = ttk.Frame(frm)
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

    return win
