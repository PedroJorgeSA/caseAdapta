from fastmcp import FastMCP
import requests

# Criar servidor MCP
mcp = FastMCP("figma-mcp")

FIGMA_API = "https://api.figma.com/v1"
TOKEN = "FIGMA_ACCESS_TOKEN"

headers = {
    "X-Figma-Token": TOKEN,
    "Content-Type": "application/json"
}

@mcp.tool()
def post_v1_files_file_key_comments(file_key: str, body: dict) -> dict:
    """Cria um novo comentário em um arquivo Figma"""
    try:
        response = requests.post(
            f"{FIGMA_API}/files/{file_key}/comments",
            headers=headers,
            json=body,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

@mcp.tool()
def add_reaction(file_key: str, comment_id: str, emoji: str = "❤️"):
    """Adiciona uma reação a um comentário"""
    url = f"{FIGMA_API}/files/{file_key}/comments/{comment_id}/reactions"
    payload = {"emoji": emoji}
    return requests.post(url, json=payload, headers=headers).json()

@mcp.tool()
def get_comments(file_key: str):
    """Lista todos os comentários de um arquivo do Figma"""
    url = f"{FIGMA_API}/files/{file_key}/comments"
    return requests.get(url, headers=headers).json()


@mcp.tool()
def get_path() -> dict:
    """Obtém informações do path da API Slack"""
    try:
        response = requests.get(f"{BASE_URL}path", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}




if __name__ == "__main__":
    mcp.run()