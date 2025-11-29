import os
import httpx
from typing import Dict, List

class SearchService:
    def __init__(self):
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "")
        self.exa_api_key = os.getenv("EXA_API_KEY", "")
        self.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY", "")
        self.parallel_api_key = os.getenv("PARALLEL_API_KEY", "")

    async def search_tavily(self, query: str) -> Dict[str, any]:
        """Search using Tavily API"""
        if not self.tavily_api_key:
            raise Exception("Tavily API key not configured")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                'https://api.tavily.com/search',
                headers={'Content-Type': 'application/json'},
                json={
                    'api_key': self.tavily_api_key,
                    'query': query,
                    'search_depth': 'advanced',
                    'include_answer': True,
                    'include_raw_content': False,
                    'max_results': 5
                }
            )
            response.raise_for_status()
            result = response.json()

            answer = result.get('answer', '')
            results = result.get('results', [])
            citations = [{'url': r['url'], 'title': r.get('title', '')} for r in results[:5]]

            return {
                'answer': answer,
                'citations': citations
            }

    async def search_exa(self, query: str) -> Dict[str, any]:
        """Search using Exa API"""
        if not self.exa_api_key:
            raise Exception("Exa API key not configured")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                'https://api.exa.ai/search',
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': self.exa_api_key
                },
                json={
                    'query': query,
                    'type': 'auto',
                    'useAutoprompt': True,
                    'numResults': 5,
                    'contents': {
                        'text': True
                    }
                }
            )
            response.raise_for_status()
            result = response.json()

            results = result.get('results', [])
            answer_parts = []
            citations = []

            for r in results[:3]:
                if 'text' in r:
                    answer_parts.append(r['text'][:300])
                citations.append({
                    'url': r.get('url', ''),
                    'title': r.get('title', '')
                })

            answer = '\n\n'.join(answer_parts) if answer_parts else 'Search completed. See citations below.'

            return {
                'answer': answer,
                'citations': citations[:5]
            }

    async def search_perplexity(self, query: str) -> Dict[str, any]:
        """Search using Perplexity API"""
        if not self.perplexity_api_key:
            raise Exception("Perplexity API key not configured")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                'https://api.perplexity.ai/chat/completions',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.perplexity_api_key}'
                },
                json={
                    'model': 'sonar',
                    'messages': [
                        {'role': 'user', 'content': query}
                    ]
                }
            )
            response.raise_for_status()
            result = response.json()

            answer = result['choices'][0]['message']['content']
            citations_data = result.get('citations', [])

            citations = [{'url': url, 'title': url.split('/')[2] if '/' in url else url}
                        for url in citations_data[:5]]

            return {
                'answer': answer,
                'citations': citations
            }

    async def search_parallel(self, query: str) -> Dict[str, any]:
        """Search using Parallel AI API"""
        if not self.parallel_api_key:
            raise Exception("Parallel API key not configured")

        # Generate multiple search query variations for better results
        search_queries = [
            query,
            f"{query} facts",
            f"{query} information"
        ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                'https://api.parallel.ai/v1beta/search',
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': self.parallel_api_key,
                    'parallel-beta': 'search-extract-2025-10-10'
                },
                json={
                    'objective': query,
                    'search_queries': search_queries,
                    'max_results': 5,
                    'excerpts': {
                        'max_chars_per_result': 1000
                    }
                }
            )
            response.raise_for_status()
            result = response.json()

            # Parse Parallel AI response format
            results = result.get('results', [])

            # Build answer from excerpts
            answer_parts = []
            citations = []

            for r in results[:5]:
                # Get title and URL
                citations.append({
                    'url': r.get('url', ''),
                    'title': r.get('title', '')
                })

                # Get excerpts for answer
                excerpts = r.get('excerpts', [])
                if excerpts:
                    # Take first excerpt from each result
                    excerpt_text = excerpts[0][:500] if excerpts[0] else ''
                    if excerpt_text:
                        answer_parts.append(excerpt_text)

            # Combine excerpts into answer
            if answer_parts:
                answer = '\n\n'.join(answer_parts[:3])  # Use top 3 excerpts
            else:
                answer = 'Search completed. See citations below.'

            return {
                'answer': answer,
                'citations': citations
            }

    async def generate_search_response(self, query: str, provider: str) -> Dict[str, any]:
        """
        Generates a search response for a given query and provider.
        Returns dict with 'answer' and 'citations' keys.
        """
        provider_lower = provider.lower()

        if 'tavily' in provider_lower:
            return await self.search_tavily(query)
        elif 'exa' in provider_lower:
            return await self.search_exa(query)
        elif 'perplexity' in provider_lower:
            return await self.search_perplexity(query)
        elif 'parallel' in provider_lower:
            return await self.search_parallel(query)
        else:
            raise Exception(f"Unknown search provider: {provider}")
