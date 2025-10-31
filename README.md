# INI Editor

Aplicativo Python simples para listar, visualizar e editar arquivos INI dentro da pasta `Assets` do workspace.

Características
- Lista recursivamente arquivos `.ini` e `.txt` dentro de `Assets/`.
- Exibe seções e chaves.
- Permite criar/remover seções e chaves, editar valores e salvar.

Requisitos
- Python 3.8+ (Tkinter incluído na instalação padrão do CPython)

Como usar (Windows PowerShell)

1. Abra PowerShell na pasta do workspace (onde `ini_editor.py` está):

```powershell
cd "e:\Ini Editor"
python ini_editor.py
```

2. Se a pasta `Assets` não existir onde o script está, você será solicitado a escolher a pasta Assets.

Notas
- O editor usa `configparser` para salvar; ele reescreve o arquivo INI no formato do `configparser`.
- Para arquivos INI com formatações especiais ou comentários importantes, faça backup antes de salvar.

Próximos passos possíveis (opcional)
- Manter/Preservar comentários e ordem original do arquivo.
- Suporte a undo/redo.
- Interface web (Electron/Flask) para edição remota.
