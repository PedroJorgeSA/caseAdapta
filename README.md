case adapta

## LangGraph Agent - Projeto Básico

Este projeto contém um setup mínimo para criar e testar um agent com LangGraph em Python.

### Requisitos
- Python 3.10+
- Windows (testado via Git Bash) ou outro SO compatível

### Instalação
1. Criar e ativar um ambiente virtual:
   - PowerShell:
     ```powershell
     python -m venv .venv
     .venv\\Scripts\\Activate.ps1
     ```
   - Git Bash:
     ```bash
     python -m venv .venv
     source .venv/Scripts/activate
     ```

2. Instalar dependências:
   ```bash
   pip install -r requirements.txt
   ```

### Executar o agent de exemplo
```bash
python -m src.run
```

Você verá a execução do grafo com um nó simples transformando o texto de entrada.

### Estrutura
- `requirements.txt`: dependências do projeto
- `src/agent.py`: definição do grafo/agent LangGraph
- `src/run.py`: script de execução com exemplo de entrada

### Notas
- O exemplo não requer chave de API. Para usar LLMs (ex.: OpenAI), crie um `.env` a partir de `.env.example` e ajuste o `agent.py` conforme necessário.
