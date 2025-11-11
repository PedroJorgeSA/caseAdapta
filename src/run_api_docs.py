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

    # Segunda etapa: análise dos endpoints extraídos usando o corpus da documentação
    # Executa o mesmo crawl de forma programática para obter estrutura com corpus e endpoints
    from .api_docs_agent import crawl_documentation_sync, analyze_endpoints, format_endpoint_analyses
    crawl_result = crawl_documentation_sync(url, max_depth=3, max_pages=20)
    endpoints = crawl_result.get("endpoints", [])
    corpus = crawl_result.get("docs_corpus", "")
    if endpoints and corpus:
        analyses = analyze_endpoints(endpoints, corpus)
        analysis_text = format_endpoint_analyses(analyses)

        print("\n" + "="*80)
        print("ANÁLISE DOS ENDPOINTS:")
        print("="*80)
        print(analysis_text)  # noqa: T201
        print("="*80)

    else:
        print("\n[Aviso] Não foi possível obter endpoints ou corpus suficiente para análise.")  # noqa: T201


if __name__ == "__main__":
    main()

