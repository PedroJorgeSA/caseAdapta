import re
from urllib.parse import urlparse

from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END


def extract_url_from_message(message: str) -> str | None:
    """Extract URL from the message content."""
    # Simple URL pattern matching
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, message)
    return urls[0] if urls else None


async def scrape_web_page(url: str) -> str:
    """Scrape a web page and return its content."""
    try:
        loader = AsyncHtmlLoader([url])
        documents = await loader.aload()
        
        if documents:
            # Return the entire page content
            return documents[0].page_content
        return "Error: Could not load page content"
    except Exception as e:
        return f"Error scraping page: {str(e)}"


def scrape_web_page_sync(url: str) -> str:
    """Synchronous wrapper for web scraping."""
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(scrape_web_page(url))


def scrape_node(state: MessagesState) -> dict[str, list[AnyMessage]]:
    """Node that scrapes the web page from the URL in the message."""
    # Get the last user message
    last_message = state["messages"][-1]
    
    if isinstance(last_message, HumanMessage):
        message_content = last_message.content
        
        # Extract URL from message
        url = extract_url_from_message(str(message_content))
        
        if url:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                response = AIMessage(
                    content=f"Invalid URL format: {url}. Please provide a valid URL (e.g., https://example.com)"
                )
            else:
                # Scrape the web page
                page_content = scrape_web_page_sync(url)
                response = AIMessage(
                    content=f"Page content from {url}:\n\n{page_content}"
                )
        else:
            response = AIMessage(
                content="No valid URL found in your message. Please provide a URL to scrape (e.g., https://example.com)"
            )
    else:
        response = AIMessage(
            content="Please provide a URL to scrape."
        )
    
    return {"messages": [response]}


def build_agent_graph():
    """Build the web scraper agent graph."""
    graph = StateGraph(MessagesState)

    # Add the scraping node
    graph.add_node("scrape", scrape_node)

    # Set up the flow
    graph.add_edge(START, "scrape")
    graph.add_edge("scrape", END)

    app = graph.compile()
    return app


