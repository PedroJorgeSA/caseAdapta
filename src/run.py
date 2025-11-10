import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from .agent import build_agent_graph


def main():
    # Carrega variáveis do .env (ex.: OPENAI_API_KEY)
    if os.path.exists('.env'):
        load_dotenv()

    app = build_agent_graph()

    # Exemplo de entrada via mensagens - forneça uma URL para fazer scraping
    url = input("Digite a URL para fazer scraping (ou pressione Enter para usar exemplo): ").strip()
    if not url:
        url = "https://example.com"
    
    messages = [HumanMessage(content=f"Scrape this page: {url}")]

    # Execução síncrona
    print(f"Fazendo scraping de: {url}...")
    result = app.invoke({"messages": messages})

    print("\n" + "="*80)
    print("CONTEÚDO DA PÁGINA:")
    print("="*80)
    print(result["messages"][-1].content)  # noqa: T201
    print("="*80)


if __name__ == "__main__":
    main()


