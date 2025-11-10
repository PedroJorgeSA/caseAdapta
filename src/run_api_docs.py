import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from .api_docs_agent import build_api_docs_agent_graph


def main():
    # Carrega variáveis do .env
    if os.path.exists('.env'):
        load_dotenv()

    app = build_api_docs_agent_graph()

    # Solicita URL da documentação
    url = input("Digite a URL da documentação da API para extrair endpoints (ou pressione Enter para usar exemplo): ").strip()
    if not url:
        url = "https://developers.figma.com/docs/rest-api/"
    
    messages = [HumanMessage(content=f"Extract API endpoints from: {url}")]

    # Execução síncrona
    print(f"\nIniciando extração de endpoints da documentação: {url}")
    print("Isso pode levar alguns minutos...\n")
    result = app.invoke({"messages": messages})

    print("\n" + "="*80)
    print("RESULTADO DA EXTRAÇÃO:")
    print("="*80)
    print(result["messages"][-1].content)  # noqa: T201
    print("="*80)


if __name__ == "__main__":
    main()

