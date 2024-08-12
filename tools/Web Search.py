import requests

SEARCH_URL = "https://api.duckduckgo.com/"
session = None

def activate():
    global session
    print("WebSearch tool activated")
    session = requests.Session()

def deactivate():
    global session
    print("WebSearch tool deactivated")
    if session:
        session.close()
        session = None

def execute(query, num_results=3):
    global session
    if not session:
        return "WebSearch tool is not activated."
    
    params = {
        'q': query,
        'format': 'json',
        'no_html': 1,
        'no_redirect': 1,
    }
    
    try:
        response = session.get(SEARCH_URL, params=params)
        data = response.json()
        
        results = []
        for result in data.get('RelatedTopics', [])[:num_results]:
            if 'Text' in result:
                results.append(result['Text'])
        
        if results:
            return "\n".join(f"{i+1}. {result}" for i, result in enumerate(results))
        else:
            return f"No results found for '{query}'."
    except Exception as e:
        return f"Error performing web search: {str(e)}"

# Example usage in the agent's system:

# result = execute("Python programming", num_results=5)

# print(result)

