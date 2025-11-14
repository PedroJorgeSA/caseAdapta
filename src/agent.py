import os
import sys
import json
import re
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
import requests
from dotenv import load_dotenv

# Configurar encoding para UTF-8 no Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

# Estado do grafo
class AgentState(TypedDict):
    api_name: str
    base_url: str
    auth_type: str
    endpoints: List[dict]
    mcp_code: str
    error: str

# Configuração do Perplexity
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

def call_perplexity(prompt: str, model="sonar") -> str:
    """Chama a API do Perplexity"""
    
    if not PERPLEXITY_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY não encontrada no .env")
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Você é um especialista em criar servidores MCP (Model Context Protocol) com FastMCP. Gere código Python limpo, funcional e bem documentado."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }
    
    try:
        response = requests.post(PERPLEXITY_API_URL, json=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"[DEBUG] Status Code: {response.status_code}")
            print(f"[DEBUG] Response: {response.text}")
            
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        raise Exception(f"Erro na API Perplexity: {str(e)}")

def parse_endpoint_input(endpoint_text: str) -> dict:
    """
    Parse do formato: GET /path URL: https://example.com/path
    """
    try:
        # Extrair método e path
        method_match = re.match(r'^(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]*)', endpoint_text)
        if not method_match:
            return None
        
        method = method_match.group(1)
        path = method_match.group(2)
        
        # Extrair URL completa (se houver)
        url_match = re.search(r'URL:\s*([^\s]+)', endpoint_text)
        full_url = url_match.group(1) if url_match else None
        
        # Gerar nome da função a partir do path
        # Remove parâmetros e caracteres especiais
        clean_path = re.sub(r'\{[^}]+\}', '', path)
        clean_path = re.sub(r'[^\w/]', '', clean_path)
        parts = [p for p in clean_path.split('/') if p]
        func_name = '_'.join(parts) if parts else 'endpoint'
        func_name = method.lower() + '_' + func_name
        
        # Extrair parâmetros do path
        params = re.findall(r'\{([^}]+)\}', path)
        
        return {
            "metodo": method,
            "path": path,
            "full_url": full_url,
            "nome_funcao": func_name,
            "parametros": [{"nome": p, "tipo": "str", "obrigatorio": True} for p in params]
        }
    except Exception as e:
        print(f"[ERRO] Erro ao parsear endpoint: {endpoint_text}")
        print(f"[ERRO] {str(e)}")
        return None

def collect_endpoints_from_terminal() -> tuple:
    """Coleta informações dos endpoints via terminal"""
    print("\n" + "="*80)
    print("GERADOR DE SERVIDORES MCP")
    print("="*80 + "\n")
    
    # Informações básicas
    api_name = input("Nome da API (ex: Slack, GitHub): ").strip()
    base_url = input("URL base da API (ex: https://slack.com/api): ").strip()
    
    print("\nTipo de autenticação:")
    print("1. Bearer Token")
    print("2. API Key (header)")
    print("3. API Key (query)")
    print("4. Sem autenticação")
    auth_choice = input("Escolha (1-4): ").strip()
    
    auth_map = {
        "1": "bearer",
        "2": "api_key_header",
        "3": "api_key_query",
        "4": "none"
    }
    auth_type = auth_map.get(auth_choice, "bearer")
    
    print("\n" + "-"*80)
    print("ENDPOINTS")
    print("-"*80)
    print("Digite os endpoints no formato:")
    print("  GET /path")
    print("  GET /path URL: https://exemplo.com/docs")
    print("  POST /users/{id}")
    print("\nDigite 'fim' quando terminar\n")
    
    endpoints = []
    count = 1
    
    while True:
        endpoint_text = input(f"[{count}] Endpoint: ").strip()
        
        if endpoint_text.lower() == 'fim':
            break
        
        if not endpoint_text:
            continue
        
        parsed = parse_endpoint_input(endpoint_text)
        if parsed:
            endpoints.append(parsed)
            print(f"    ✓ Adicionado: {parsed['metodo']} {parsed['path']} -> {parsed['nome_funcao']}()")
            count += 1
        else:
            print("    ✗ Formato inválido. Tente novamente.")
    
    return api_name, base_url, auth_type, endpoints

def generate_mcp_code_node(state: AgentState) -> AgentState:
    """Gera o código MCP baseado nos endpoints fornecidos"""
    print("\n[*] Gerando código MCP...")
    
    if state.get("error"):
        return state
    
    # Preparar descrição dos endpoints
    endpoints_desc = "\n".join([
        f"- {ep['metodo']} {ep['path']} -> função: {ep['nome_funcao']}()"
        for ep in state['endpoints']
    ])
    
    prompt = f"""Gere um servidor MCP Python completo usando FastMCP para esta API:

**Informações da API:**
- Nome: {state['api_name']}
- Base URL: {state['base_url']}
- Autenticação: {state['auth_type']}

**Endpoints para implementar:**
{endpoints_desc}

**Requisitos:**
1. Use `from fastmcp import FastMCP`
2. Crie o servidor: `mcp = FastMCP("{state['api_name']}")`
3. Defina BASE_URL = "{state['base_url']}"
4. Configure autenticação com os.getenv("API_TOKEN")
5. Para cada endpoint, crie uma função @mcp.tool() com:
   - Nome da função conforme especificado
   - Docstring explicativa
   - Parâmetros tipados (extraia do path se houver {{}})
   - Chamada HTTP correta (requests.get, post, etc)
   - Return do response.json()
6. Adicione tratamento de erros básico
7. Finalize com: if __name__ == "__main__": mcp.run()

**Exemplo de estrutura:**
```python
from fastmcp import FastMCP
import requests
import os

mcp = FastMCP("API_Name")
BASE_URL = "https://api.example.com"
API_TOKEN = os.getenv("API_TOKEN")

headers = {{"Authorization": f"Bearer {{API_TOKEN}}"}}

@mcp.tool()
def get_users() -> dict:
    \"\"\"Lista todos os usuários\"\"\"
    response = requests.get(f"{{BASE_URL}}/users", headers=headers)
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    mcp.run()
```

IMPORTANTE: Retorne APENAS código Python válido, sem markdown, sem explicações."""
    
    try:
        mcp_code = call_perplexity(prompt)
        
        # Limpar markdown
        mcp_code = re.sub(r'^```python\s*', '', mcp_code.strip())
        mcp_code = re.sub(r'^```\s*', '', mcp_code)
        mcp_code = re.sub(r'\s*```$', '', mcp_code)
        
        state["mcp_code"] = mcp_code
        print("[OK] Código MCP gerado!")
        print(f"[INFO] {len(state['endpoints'])} tools criadas")
        print(f"[INFO] {len(mcp_code)} caracteres gerados")
        
    except Exception as e:
        state["error"] = f"Erro ao gerar código: {str(e)}"
        print(f"[ERRO] {state['error']}")
    
    return state

def validate_code_node(state: AgentState) -> AgentState:
    """Valida a sintaxe do código gerado"""
    print("[*] Validando código...")
    
    if state.get("error"):
        return state
    
    if not state.get("mcp_code"):
        state["error"] = "Nenhum código foi gerado"
        print(f"[ERRO] {state['error']}")
        return state
    
    try:
        compile(state["mcp_code"], '<string>', 'exec')
        print("[OK] Código válido!")
    except SyntaxError as e:
        state["error"] = f"Erro de sintaxe na linha {e.lineno}: {str(e)}"
        print(f"[ERRO] {state['error']}")
        print(f"[DEBUG] Código problemático:\n{state['mcp_code'][:500]}")
    
    return state

def create_mcp_generator():
    """Cria o grafo LangGraph"""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("generate", generate_mcp_code_node)
    workflow.add_node("validate", validate_code_node)
    
    workflow.set_entry_point("generate")
    workflow.add_edge("generate", "validate")
    workflow.add_edge("validate", END)
    
    return workflow.compile()

def main():
    """Função principal"""
    
    # Verificar API key
    if not PERPLEXITY_API_KEY:
        print("\n[ERRO] PERPLEXITY_API_KEY não encontrada no arquivo .env")
        print("Crie um arquivo .env com: PERPLEXITY_API_KEY=sua_chave\n")
        return
    
    try:
        # Coletar informações via terminal
        api_name, base_url, auth_type, endpoints = collect_endpoints_from_terminal()
        
        if not endpoints:
            print("\n[ERRO] Nenhum endpoint fornecido!")
            return
        
        print(f"\n[INFO] {len(endpoints)} endpoints coletados")
        print("[INFO] Gerando servidor MCP...\n")
        
        # Criar estado inicial
        initial_state = {
            "api_name": api_name,
            "base_url": base_url,
            "auth_type": auth_type,
            "endpoints": endpoints,
            "mcp_code": "",
            "error": ""
        }
        
        # Executar grafo
        app = create_mcp_generator()
        result = app.invoke(initial_state)
        
        # Verificar erros
        if result.get("error"):
            print(f"\n[ERRO] {result['error']}")
            return
        
        # Exibir código gerado
        print("\n" + "="*80)
        print("CÓDIGO MCP GERADO:")
        print("="*80)
        print(result["mcp_code"])
        
        # Salvar em arquivo
        filename = f"{api_name.lower().replace(' ', '_')}_mcp.py"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(result["mcp_code"])
        
        print("\n" + "="*80)
        print(f"[SALVO] Código salvo em '{filename}'")
        print("="*80)
        
        print("\nPara usar:")
        print(f"1. Configure a variável API_TOKEN no .env")
        print(f"2. Execute: python {filename}")
        
    except KeyboardInterrupt:
        print("\n\n[INFO] Operação cancelada pelo usuário")
    except Exception as e:
        print(f"\n[ERRO FINAL] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()