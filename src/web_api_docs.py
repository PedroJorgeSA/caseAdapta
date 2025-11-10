import os
from typing import List, Tuple

import gradio as gr
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage

from .api_docs_agent import build_api_docs_agent_graph


def _build_messages(history: List[Tuple[str, str]], user_message: str) -> list[AnyMessage]:
    messages: list[AnyMessage] = []
    for user, bot in history:
        if user:
            messages.append(HumanMessage(content=user))
        if bot:
            messages.append(AIMessage(content=bot))
    messages.append(HumanMessage(content=user_message))
    return messages


def main():
    if os.path.exists('.env'):
        load_dotenv()

    app = build_api_docs_agent_graph()

    def respond(message: str, history: List[Tuple[str, str]]):
        messages = _build_messages(history, message)
        result = app.invoke({"messages": messages})
        ai_text = result["messages"][-1].content
        return ai_text

    chat = gr.ChatInterface(
        fn=respond,
        title="API Documentation Crawler Agent",
        description="Digite uma URL de documentação da API para extrair todos os endpoints. O agente irá navegar pela documentação e extrair endpoints com seus métodos HTTP e URLs.",
    )

    chat.launch(server_name="127.0.0.1", server_port=7861)


if __name__ == "__main__":
    main()

