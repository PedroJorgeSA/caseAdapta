import re
import asyncio
from collections import defaultdict
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END


def extract_url_from_message(message: str) -> str | None:
    """Extract URL from the message content."""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, message)
    return urls[0] if urls else None


async def scrape_web_page_with_links(url: str) -> tuple[str, list[str]]:
    """Scrape a web page and return its content and links."""
    try:
        # Get raw HTML first
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    html = await response.text()
        except ImportError:
            # Fallback to requests if aiohttp not available
            import requests
            response = requests.get(url, timeout=10)
            html = response.text
        except Exception as e:
            return f"Error fetching page: {str(e)}", []
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract text content (remove script and style tags)
        for script in soup(["script", "style", "meta", "link"]):
            script.decompose()
        
        # Get text content
        page_content = soup.get_text(separator=' ', strip=True)
        
        # Extract all links
        links = []
        base_url = url
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            absolute_url = urljoin(base_url, href)
            # Only include links from the same domain
            parsed_base = urlparse(base_url)
            parsed_link = urlparse(absolute_url)
            if parsed_link.netloc == parsed_base.netloc:
                links.append(absolute_url)
        
        return page_content, list(set(links))
        
    except Exception as e:
        return f"Error scraping page: {str(e)}", []


def scrape_web_page_with_links_sync(url: str) -> tuple[str, list[str]]:
    """Synchronous wrapper for web scraping with links."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(scrape_web_page_with_links(url))


def extract_api_endpoints(content: str, base_url: str) -> list[dict[str, Any]]:
    """Extract API endpoints from page content."""
    endpoints = []
    found_endpoints = set()
    
    # Pattern 1: HTTP method followed by path (e.g., "GET /api/v1/files")
    api_pattern = r'(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+([/][^\s\)\<\>"]+)'
    for match in re.finditer(api_pattern, content, re.IGNORECASE):
        method = match.group(1).upper()
        path = match.group(2).strip()
        
        # Clean up path
        path = re.sub(r'[\)\]\}\<\>]', '', path)
        path = path.split()[0] if path else ''
        
        if path and len(path) > 1 and path.startswith('/'):
            endpoint_key = f"{method}:{path}"
            if endpoint_key not in found_endpoints:
                found_endpoints.add(endpoint_key)
                endpoints.append({
                    'method': method,
                    'path': path,
                    'full_url': urljoin(base_url, path),
                    'source': 'method_path'
                })
    
    # Pattern 2: Full API URLs (e.g., "https://api.figma.com/v1/files")
    full_url_pattern = r'https?://[^/]+(/[^\s\)\<\>"]+)'
    for match in re.finditer(full_url_pattern, content, re.IGNORECASE):
        full_url = match.group(0)
        path = match.group(1)
        
        # Try to extract method from context
        method = 'GET'  # Default
        context_start = max(0, match.start() - 50)
        context = content[context_start:match.start()].upper()
        if 'POST' in context:
            method = 'POST'
        elif 'PUT' in context:
            method = 'PUT'
        elif 'DELETE' in context:
            method = 'DELETE'
        elif 'PATCH' in context:
            method = 'PATCH'
        
        if path and len(path) > 1:
            endpoint_key = f"{method}:{path}"
            if endpoint_key not in found_endpoints:
                found_endpoints.add(endpoint_key)
                endpoints.append({
                    'method': method,
                    'path': path,
                    'full_url': full_url,
                    'source': 'full_url'
                })
    
    # Pattern 3: Paths in code blocks or backticks
    code_pattern = r'`([/][^`]+)`'
    for match in re.finditer(code_pattern, content):
        path = match.group(1).strip()
        
        # Try to find method in nearby context
        method = 'GET'
        context_start = max(0, match.start() - 100)
        context_end = min(len(content), match.end() + 100)
        context = content[context_start:context_end].upper()
        
        if 'POST' in context:
            method = 'POST'
        elif 'PUT' in context:
            method = 'PUT'
        elif 'DELETE' in context:
            method = 'DELETE'
        elif 'PATCH' in context:
            method = 'PATCH'
        
        if path and len(path) > 1 and path.startswith('/'):
            endpoint_key = f"{method}:{path}"
            if endpoint_key not in found_endpoints:
                found_endpoints.add(endpoint_key)
                endpoints.append({
                    'method': method,
                    'path': path,
                    'full_url': urljoin(base_url, path),
                    'source': 'code_block'
                })
    
    # Pattern 4: Look for curl commands
    curl_pattern = r'curl\s+(?:-X\s+(\w+)\s+)?["\']?https?://[^/]+(/[^\s"\']+)'
    for match in re.finditer(curl_pattern, content, re.IGNORECASE):
        method = match.group(1).upper() if match.group(1) else 'GET'
        path = match.group(2).strip()
        
        if path and len(path) > 1:
            endpoint_key = f"{method}:{path}"
            if endpoint_key not in found_endpoints:
                found_endpoints.add(endpoint_key)
                endpoints.append({
                    'method': method,
                    'path': path,
                    'full_url': urljoin(base_url, path),
                    'source': 'curl_command'
                })
    
    # Pattern 5: Look for paths that look like API endpoints (contain /v1/, /v2/, /api/, etc.)
    api_path_pattern = r'(/v\d+/[^\s\)\<\>"]+|/api/[^\s\)\<\>"]+)'
    for match in re.finditer(api_path_pattern, content, re.IGNORECASE):
        path = match.group(1).strip()
        
        # Try to find method in context
        method = 'GET'
        context_start = max(0, match.start() - 100)
        context = content[context_start:match.start()].upper()
        if 'POST' in context:
            method = 'POST'
        elif 'PUT' in context:
            method = 'PUT'
        elif 'DELETE' in context:
            method = 'DELETE'
        elif 'PATCH' in context:
            method = 'PATCH'
        
        if path and len(path) > 1:
            endpoint_key = f"{method}:{path}"
            if endpoint_key not in found_endpoints:
                found_endpoints.add(endpoint_key)
                endpoints.append({
                    'method': method,
                    'path': path,
                    'full_url': urljoin(base_url, path),
                    'source': 'api_path_pattern'
                })
    
    return endpoints


async def crawl_documentation(
    start_url: str,
    max_depth: int = 3,
    max_pages: int = 20,
    visited: set[str] | None = None
) -> dict[str, Any]:
    """Crawl documentation pages and extract API endpoints."""
    if visited is None:
        visited = set()
    
    all_endpoints = []
    pages_crawled = []
    corpus_snippets: list[str] = []
    queue = [(start_url, 0)]  # (url, depth)
    
    while queue and len(pages_crawled) < max_pages:
        current_url, depth = queue.pop(0)
        
        # Skip if already visited or depth exceeded
        if current_url in visited:
            continue
        
        if depth > max_depth:
            continue
        
        visited.add(current_url)
        print(f"Crawling (depth {depth}): {current_url}")
        
        try:
            # Use async function directly since we're in an async context
            content, links = await scrape_web_page_with_links(current_url)
            
            # Check if we got content successfully
            if content and not content.startswith("Error"):
                pages_crawled.append({
                    'url': current_url,
                    'depth': depth,
                    'content_length': len(content)
                })
                # Keep a bounded corpus of docs text for later analysis
                snippet = content[:8000]
                corpus_snippets.append(snippet)
                
                # Extract endpoints from this page
                endpoints = extract_api_endpoints(content, current_url)
                all_endpoints.extend(endpoints)
                print(f"  Found {len(endpoints)} endpoints on this page (total: {len(all_endpoints)})")
                print(f"  Found {len(links)} links on this page")
            else:
                print(f"  Error: Could not get content from {current_url}")
                print(f"  Content preview: {content[:200] if content else 'None'}")
            
            # Add new links to queue if we haven't reached max depth
            if depth < max_depth and links:
                added_count = 0
                for link in links:
                    if link not in visited and link not in [url for url, _ in queue]:
                        # More lenient filtering - follow links within the same docs domain
                        parsed_base = urlparse(start_url)
                        parsed_link = urlparse(link)
                        
                        # Follow links that are:
                        # 1. In the same domain as the start URL
                        # 2. Or contain documentation-related keywords
                        if (parsed_link.netloc == parsed_base.netloc or 
                            any(keyword in link.lower() for keyword in ['api', 'endpoint', 'docs', 'reference', 'rest', 'documentation'])):
                            queue.append((link, depth + 1))
                            added_count += 1
                            if added_count <= 5:  # Only print first 5
                                print(f"  Added to queue: {link}")
                if added_count > 5:
                    print(f"  Added {added_count} more links to queue")
        
        except Exception as e:
            print(f"Error crawling {current_url}: {str(e)}")
            import traceback
            traceback.print_exc()
            continue
    
    # Deduplicate endpoints
    unique_endpoints = {}
    for endpoint in all_endpoints:
        key = f"{endpoint['method']}:{endpoint['path']}"
        if key not in unique_endpoints:
            unique_endpoints[key] = endpoint
    
    return {
        'endpoints': list(unique_endpoints.values()),
        'pages_crawled': pages_crawled,
        'total_endpoints': len(unique_endpoints),
        'docs_corpus': "\n\n".join(corpus_snippets[:25])  # cap total size
    }


def crawl_documentation_sync(start_url: str, max_depth: int = 3, max_pages: int = 20) -> dict[str, Any]:
    """Synchronous wrapper for crawling."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(crawl_documentation(start_url, max_depth, max_pages))


def format_endpoints_output(result: dict[str, Any]) -> str:
    """Format the extracted endpoints into a readable string."""
    output = []
    output.append("=" * 80)
    output.append("API ENDPOINTS EXTRACTION RESULTS")
    output.append("=" * 80)
    output.append(f"\nTotal Pages Crawled: {len(result['pages_crawled'])}")
    output.append(f"Total Unique Endpoints Found: {result['total_endpoints']}\n")
    
    # Group endpoints by method
    by_method = defaultdict(list)
    for endpoint in result['endpoints']:
        by_method[endpoint['method']].append(endpoint)
    
    # Display endpoints grouped by HTTP method
    for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
        if method in by_method:
            output.append(f"\n{method} Endpoints ({len(by_method[method])}):")
            output.append("-" * 80)
            for endpoint in sorted(by_method[method], key=lambda x: x['path']):
                output.append(f"  {endpoint['method']:6} {endpoint['path']}")
                output.append(f"           Full URL: {endpoint['full_url']}")
    
    # List all pages crawled
    output.append("\n\nPages Crawled:")
    output.append("-" * 80)
    for page in result['pages_crawled']:
        output.append(f"  Depth {page['depth']}: {page['url']}")
    
    return "\n".join(output)


def analyze_endpoints(endpoints: list[dict[str, Any]], docs_corpus: str) -> list[dict[str, Any]]:
    """Heuristically describe each endpoint using docs corpus.

    Extracts: short description, path params and their meaning, and common usage hints.
    """
    analyses: list[dict[str, Any]] = []

    # Precompute a simplified corpus for fuzzy matching
    normalized_corpus = docs_corpus

    for ep in endpoints:
        method = ep['method']
        path = ep['path']
        full_url = ep['full_url']

        # Detect path params like {id} or :id
        params = re.findall(r"\{([^}]+)\}", path)
        if not params:
            params = re.findall(r":([A-Za-z0-9_]+)", path)

        # Try to locate a nearby description in the corpus around the path
        desc = ""
        try:
            # Look for occurrences of the path or tail segments
            path_tail = path.split("/")[-1]
            candidates = [
                re.escape(path),
                re.escape(path_tail),
            ]
            # Build a small window around the first match
            match_pos = -1
            for pat in candidates:
                m = re.search(pat, normalized_corpus, re.IGNORECASE)
                if m:
                    match_pos = m.start()
                    break
            if match_pos >= 0:
                start = max(0, match_pos - 300)
                end = min(len(normalized_corpus), match_pos + 500)
                window = normalized_corpus[start:end]
                # Try to pull a sentence around it
                sentences = re.split(r"(?<=[.!?])\s+", window)
                # Choose a sentence that contains the path tail or method
                picked = ""
                for s in sentences:
                    if path_tail.lower() in s.lower() or method in s.upper():
                        picked = s.strip()
                        if len(picked) > 20:
                            break
                desc = picked or window.strip()
        except Exception:
            desc = ""

        # Clean and condense description
        if desc:
            # Remove excessive whitespace
            desc = re.sub(r"\s+", " ", desc).strip()
            # Trim overly long snippets
            if len(desc) > 280:
                desc = desc[:277] + "..."

        # Compose a human-readable hint about params
        param_hint = ""
        if params:
            # Create a simple hint about replacing params
            pretty_params = ", ".join(params)
            param_hint = f"Path params: {pretty_params}. Replace each placeholder with the corresponding value (e.g., IDs, keys)."

        # Default description if nothing found
        if not desc:
            # Provide a generic action based on method
            action = {
                "GET": "retrieves",
                "POST": "creates",
                "PUT": "replaces",
                "PATCH": "updates",
                "DELETE": "deletes",
            }.get(method, "operates on")
            desc = f"{method} {path} {action} the resource. {param_hint}".strip()

        analyses.append({
            "method": method,
            "path": path,
            "full_url": full_url,
            "description": desc,
            "params": params,
        })

    return analyses


def format_endpoint_analyses(analyses: list[dict[str, Any]]) -> str:
    """Render endpoint analyses in a readable form."""
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("API ENDPOINTS ANALYSIS")
    lines.append("=" * 80)

    # Group by method for readability
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in analyses:
        by_method[item["method"]].append(item)

    for method in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']:
        if method in by_method:
            lines.append(f"\n{method} ({len(by_method[method])})")
            lines.append("-" * 80)
            for item in sorted(by_method[method], key=lambda x: x["path"]):
                lines.append(f"{method:6} {item['path']}")
                lines.append(f"  URL: {item['full_url']}")
                lines.append(f"  What it does: {item['description']}")
                if item["params"]:
                    lines.append(f"  Path params: {', '.join(item['params'])}")
    return "\n".join(lines)

def api_docs_node(state: MessagesState) -> dict[str, list[AnyMessage]]:
    """Node that crawls documentation and extracts API endpoints."""
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
                    content=f"Invalid URL format: {url}. Please provide a valid URL (e.g., https://example.com/docs)"
                )
            else:
                # Crawl documentation and extract endpoints
                print(f"Starting documentation crawl from: {url}")
                result = crawl_documentation_sync(url, max_depth=3, max_pages=20)
                
                # Format the output
                formatted_output = format_endpoints_output(result)
                response = AIMessage(content=formatted_output)
        else:
            response = AIMessage(
                content="No valid URL found in your message. Please provide a documentation URL to crawl (e.g., https://developers.figma.com/docs/rest-api/)"
            )
    else:
        response = AIMessage(
            content="Please provide a documentation URL to extract API endpoints from."
        )
    
    return {"messages": [response]}


def build_api_docs_agent_graph():
    """Build the API documentation crawler agent graph."""
    graph = StateGraph(MessagesState)

    # Add the API docs extraction node
    graph.add_node("extract_endpoints", api_docs_node)

    # Set up the flow
    graph.add_edge(START, "extract_endpoints")
    graph.add_edge("extract_endpoints", END)

    app = graph.compile()
    return app

