import os
from typing import List, Tuple

import gradio as gr
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage

from .agent import build_agent_graph


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

    app = build_agent_graph()

    def respond(message: str, history: List[Tuple[str, str]]):
        messages = _build_messages(history, message)
        result = app.invoke({"messages": messages})
        ai_text = result["messages"][-1].content
        return ai_text

    chat = gr.ChatInterface(
        fn=respond,
        title="Web Scraper Agent",
        description="Digite uma URL para fazer scraping da página. O agente retornará todo o conteúdo da página.",
    )

    chat.launch(server_name="127.0.0.1", server_port=7860)


if __name__ == "__main__":
    main()


