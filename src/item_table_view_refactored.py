# -*- coding: latin-1 -*-
"""
Visualizador tabular para arquivos de items
- Exibe registros em Treeview com colunas centralizadas
- Suporta edição de células (duplo-clique)
- Exporta para CSV
- Edita e salva headers
- Inserção em lote para evitar travamentos
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import List, Dict, Optional, Callable


class BatchInserter:
    """Gerencia inserção em lote em Treeview para evitar travamentos."""
    
    def __init__(self, tree: ttk.Treeview, records: List[Dict[str, str]], 
                 headers: List[str], batch_size: int = 500):
        """
        Args:
            tree: Treeview para inserir dados
            records: Lista de registros
            headers: Lista de headers
            batch_size: Registros por lote
        """
        self.tree = tree
        self.records = records
        self.headers = headers
        self.batch_size = batch_size
        self.index = 0
        self.cancelled = False
        self.progress_label: Optional[ttk.Label] = None
        self.cancel_button: Optional[ttk.Button] = None
    
    def start(self, progress_label: ttk.Label, cancel_button: ttk.Button):
        """Inicia inserção em lote.
        
        Args:
            progress_label: Label para mostrar progresso
            cancel_button: Botão para cancelar
        """
        self.progress_label = progress_label
        self.cancel_button = cancel_button
        self._insert_batch()
    
    def cancel(self):
        """Cancela inserção."""
        self.cancelled = True
    
    def _insert_batch(self):
        """Insere um lote de registros."""
        if self.cancelled or not self._widgets_exist():
            self._cleanup()
            return
        
        end_idx = min(self.index + self.batch_size, len(self.records))
        
        for i in range(self.index, end_idx):
            record = self.records[i]
            values = [record.get(h, '') for h in self.headers]
            
            # Limitar tamanho de preview (max 500 chars)
            values = [str(v)[:500] for v in values]
            
            # Inserir com alternância de cor
            tag = 'oddrow' if i % 2 else 'evenrow'
            self.tree.insert('', 'end', values=values, tags=(tag,))
        
        self.index = end_idx
        
        # Atualizar progresso
        if self.progress_label and self.progress_label.winfo_exists():
            progress = int((self.index / len(self.records)) * 100)
            self.progress_label.config(text=f'Carregando... {self.index}/{len(self.records)} ({progress}%)')
        
        # Continuar ou finalizar
        if self.index < len(self.records):
            self.tree.after(10, self._insert_batch)
        else:
            self._cleanup()
    
    def _widgets_exist(self) -> bool:
        """Verifica se widgets ainda existem."""
        try:
            return (self.tree.winfo_exists() and 
                    (not self.progress_label or self.progress_label.winfo_exists()))
        except tk.TclError:
            return False
    
    def _cleanup(self):
        """Remove widgets de progresso."""
        if self.progress_label and self.progress_label.winfo_exists():
            try:
                self.progress_label.destroy()
            except tk.TclError:
                pass
        
        if self.cancel_button and self.cancel_button.winfo_exists():
            try:
                self.cancel_button.destroy()
            except tk.TclError:
                pass


def show_item_table(parent, title: str, headers: List[str], records: List[Dict[str, str]],
                    encoding: str = 'utf-8', file_path: Optional[Path] = None, embed: bool = False):
    """Exibe tabela de items com funcionalidades de edição.
    
    Args:
        parent: Widget pai
        title: Título da janela/frame
        headers: Lista de nomes de colunas
        records: Lista de registros
        encoding: Encoding para salvar
        file_path: Caminho do arquivo original
        embed: Se True, embute em frame. Se False, cria janela toplevel
    """
    if embed:
        container = ttk.Frame(parent)
        container.pack(fill='both', expand=True)
    else:
        container = tk.Toplevel(parent)
        container.title(title)
        container.geometry('1280x720')
    
    # Criar UI
    _create_table_ui(container, title, headers, records, encoding, file_path)


def _create_table_ui(container: tk.Widget, title: str, headers: List[str], 
                     records: List[Dict[str, str]], encoding: str, file_path: Optional[Path]):
    """Cria interface da tabela."""
    # Título
    top_frame = ttk.Frame(container)
    top_frame.pack(fill='x', padx=8, pady=8)
    
    ttk.Label(top_frame, text=title, font=('Arial', 12, 'bold')).pack(side='left')
    ttk.Label(top_frame, text=f'({len(records)} registros)', font=('Arial', 10)).pack(side='left', padx=8)
    
    # Botões
    btn_frame = ttk.Frame(container)
    btn_frame.pack(fill='x', padx=8, pady=(0, 8))
    
    # Área de progresso (preenchida durante inserção)
    progress_frame = ttk.Frame(container)
    progress_frame.pack(fill='x', padx=8, pady=(0, 8))
    
    # Treeview
    tree_frame = ttk.Frame(container)
    tree_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))
    
    tree = ttk.Treeview(tree_frame, columns=headers, show='headings', selectmode='browse')
    
    # Scrollbars
    vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
    hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    
    tree.grid(row=0, column=0, sticky='nsew')
    vsb.grid(row=0, column=1, sticky='ns')
    hsb.grid(row=1, column=0, sticky='ew')
    
    tree_frame.rowconfigure(0, weight=1)
    tree_frame.columnconfigure(0, weight=1)
    
    # Configurar colunas com texto centralizado
    for header in headers:
        tree.heading(header, text=header)
        tree.column(header, width=150, anchor='center')
    
    # Tags para alternância de cores
    tree.tag_configure('oddrow', background='#f0f0f0')
    tree.tag_configure('evenrow', background='white')
    
    # Estado compartilhado
    state = {
        'headers': headers,
        'records': records,
        'encoding': encoding,
        'file_path': file_path,
        'inserter': None
    }
    
    # Criar handlers
    handlers = _create_handlers(tree, state)
    
    # Botões
    ttk.Button(btn_frame, text='Adicionar Linha', command=handlers['add_row']).pack(side='left')
    ttk.Button(btn_frame, text='Editar Headers', command=handlers['edit_headers']).pack(side='left', padx=6)
    ttk.Button(btn_frame, text='Salvar Header', command=handlers['save_header']).pack(side='left')
    ttk.Button(btn_frame, text='Exportar CSV', command=handlers['export_csv']).pack(side='left', padx=6)
    
    # Duplo-clique para editar célula
    tree.bind('<Double-1>', handlers['edit_cell'])
    
    # Cancelar inserção ao fechar
    def on_destroy(event=None):
        if state['inserter']:
            state['inserter'].cancel()
    
    container.bind('<Destroy>', on_destroy)
    
    # Iniciar inserção em lote
    progress_label = ttk.Label(progress_frame, text='Carregando...')
    progress_label.pack(side='left')
    
    cancel_btn = ttk.Button(progress_frame, text='Cancelar', 
                           command=lambda: state['inserter'].cancel() if state['inserter'] else None)
    cancel_btn.pack(side='left', padx=6)
    
    inserter = BatchInserter(tree, records, headers)
    state['inserter'] = inserter
    inserter.start(progress_label, cancel_btn)


def _create_handlers(tree: ttk.Treeview, state: Dict) -> Dict[str, Callable]:
    """Cria handlers para eventos da tabela."""
    
    def add_row():
        """Adiciona nova linha."""
        new_values = []
        for header in state['headers']:
            value = simple_input(tree, f'Novo valor para {header}', header)
            if value is None:
                return
            new_values.append(value)
        
        # Adicionar ao tree
        tag = 'oddrow' if len(tree.get_children()) % 2 else 'evenrow'
        tree.insert('', 'end', values=new_values, tags=(tag,))
        
        # Adicionar aos records
        new_record = {h: v for h, v in zip(state['headers'], new_values)}
        state['records'].append(new_record)
    
    def edit_headers():
        """Edita nomes de headers."""
        old_headers = state['headers']
        new_headers = []
        
        for old_h in old_headers:
            new_h = simple_input(tree, f'Renomear header "{old_h}"', old_h)
            if new_h is None:
                return
            new_headers.append(new_h)
        
        # Atualizar state
        state['headers'] = new_headers
        
        # Remapear records
        for record in state['records']:
            new_record = {}
            for old_h, new_h in zip(old_headers, new_headers):
                new_record[new_h] = record.get(old_h, '')
            record.clear()
            record.update(new_record)
        
        # Recriar tree
        for item in tree.get_children():
            tree.delete(item)
        
        for header in new_headers:
            tree.heading(header, text=header)
        
        tree.configure(columns=new_headers)
        
        # Reinserir dados
        for i, record in enumerate(state['records']):
            values = [record.get(h, '') for h in new_headers]
            tag = 'oddrow' if i % 2 else 'evenrow'
            tree.insert('', 'end', values=values, tags=(tag,))
    
    def save_header():
        """Salva header em arquivo."""
        if not state['file_path']:
            messagebox.showinfo('Info', 'Arquivo não definido')
            return
        
        # Determinar nome do header: H_<file_stem>.ini
        file_stem = state['file_path'].stem
        header_name = f'H_{file_stem}.ini'
        
        # Buscar pasta Headers
        headers_dir = state['file_path'].parent
        while headers_dir.name != 'Assets' and headers_dir.parent != headers_dir:
            headers_dir = headers_dir.parent
        
        headers_dir = headers_dir / 'Headers'
        
        if not headers_dir.exists():
            messagebox.showerror('Erro', f'Pasta Headers não encontrada: {headers_dir}')
            return
        
        header_path = headers_dir / header_name
        
        # Confirmar
        if not messagebox.askyesno('Salvar Header', 
                                   f'Salvar header como:\n{header_path}\n\nContinuar?'):
            return
        
        # Salvar
        try:
            header_line = ','.join(state['headers'])
            header_path.write_text(header_line, encoding='utf-8')
            messagebox.showinfo('Salvo', f'Header salvo: {header_path}')
        except Exception as e:
            messagebox.showerror('Erro', f'Erro ao salvar: {e}')
    
    def export_csv():
        """Exporta dados para CSV."""
        path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv'), ('All', '*.*')]
        )
        
        if not path:
            return
        
        try:
            import csv
            with open(path, 'w', encoding=state['encoding'], newline='', errors='replace') as f:
                writer = csv.DictWriter(f, fieldnames=state['headers'])
                writer.writeheader()
                writer.writerows(state['records'])
            
            messagebox.showinfo('Exportado', f'Exportado para: {path}')
        except Exception as e:
            messagebox.showerror('Erro', f'Erro ao exportar: {e}')
    
    def edit_cell(event):
        """Edita célula ao duplo-clique."""
        selection = tree.selection()
        if not selection:
            return
        
        item = selection[0]
        region = tree.identify_region(event.x, event.y)
        
        if region != 'cell':
            return
        
        col_id = tree.identify_column(event.x)
        col_idx = int(col_id.replace('#', '')) - 1
        
        if col_idx < 0 or col_idx >= len(state['headers']):
            return
        
        header = state['headers'][col_idx]
        current_value = tree.item(item, 'values')[col_idx]
        
        # Mostrar diálogo de edição
        new_value = multiline_input(tree, f'Editar {header}', current_value)
        
        if new_value is None:
            return
        
        # Atualizar tree
        values = list(tree.item(item, 'values'))
        values[col_idx] = new_value
        tree.item(item, values=values)
        
        # Atualizar record
        item_idx = tree.index(item)
        if 0 <= item_idx < len(state['records']):
            state['records'][item_idx][header] = new_value
    
    return {
        'add_row': add_row,
        'edit_headers': edit_headers,
        'save_header': save_header,
        'export_csv': export_csv,
        'edit_cell': edit_cell
    }


def simple_input(parent: tk.Widget, title: str, initial: str = '') -> Optional[str]:
    """Diálogo simples de input.
    
    Args:
        parent: Widget pai
        title: Título do diálogo
        initial: Valor inicial
        
    Returns:
        Valor digitado ou None se cancelado
    """
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.geometry('500x150')
    dlg.transient(parent)
    dlg.grab_set()
    
    ttk.Label(dlg, text=title).pack(padx=10, pady=10)
    
    entry = ttk.Entry(dlg, width=60)
    entry.pack(padx=10, pady=(0, 10))
    entry.insert(0, initial)
    entry.focus()
    
    result = {'value': None}
    
    def ok():
        result['value'] = entry.get()
        dlg.destroy()
    
    def cancel():
        dlg.destroy()
    
    btn_frame = ttk.Frame(dlg)
    btn_frame.pack(pady=10)
    
    ttk.Button(btn_frame, text='OK', command=ok).pack(side='left', padx=6)
    ttk.Button(btn_frame, text='Cancelar', command=cancel).pack(side='left')
    
    entry.bind('<Return>', lambda e: ok())
    entry.bind('<Escape>', lambda e: cancel())
    
    parent.wait_window(dlg)
    return result['value']


def multiline_input(parent: tk.Widget, title: str, initial: str = '') -> Optional[str]:
    """Diálogo de input multiline.
    
    Args:
        parent: Widget pai
        title: Título do diálogo
        initial: Valor inicial
        
    Returns:
        Valor digitado ou None se cancelado
    """
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.geometry('700x500')
    dlg.transient(parent)
    dlg.grab_set()
    
    ttk.Label(dlg, text=title, font=('Arial', 10, 'bold')).pack(padx=10, pady=10)
    
    text = tk.Text(dlg, wrap='word', width=80, height=25)
    text.pack(padx=10, pady=(0, 10), fill='both', expand=True)
    text.insert('1.0', initial)
    text.focus()
    
    result = {'value': None}
    
    def ok():
        result['value'] = text.get('1.0', 'end').rstrip('\n')
        dlg.destroy()
    
    def cancel():
        dlg.destroy()
    
    btn_frame = ttk.Frame(dlg)
    btn_frame.pack(pady=10)
    
    ttk.Button(btn_frame, text='OK', command=ok, width=12).pack(side='left', padx=6)
    ttk.Button(btn_frame, text='Cancelar', command=cancel, width=12).pack(side='left')
    
    parent.wait_window(dlg)
    return result['value']
