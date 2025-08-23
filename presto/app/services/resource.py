import asyncio
from typing import List, Optional

from presto.app.models.presentation import GatheredResource, EnrichedContext
from presto.app.core.llm_openai import generate_content_openai  # New import


class ResourceService:
    def __init__(self):
        pass

    async def _fetch_url_content(
        self, url: str
    ) -> Optional[
        str
    ]:  # 이부분은 openai deepresearch 를 쓰면 될 듯?! 유로 유저 기준 n 번만 쓸 수 있도록 하는 로직 필요해보임.
        """Fetches content from a given URL."""
        try:
            # In a real scenario, this would use a web scraping library or API
            # For now, we'll simulate with a placeholder or a simple web_fetch tool call if available
            # Assuming web_fetch tool is available and can return content
            # For this example, I'll use a placeholder. If a real web_fetch tool is available, it should be used.
            # For now, let's assume a simple web_fetch tool that returns text.
            # If the web_fetch tool is not available, this would be a point of failure or require external integration.
            # For the purpose of this plan, I'll assume a hypothetical web_fetch_tool.
            # If I had access to the actual web_fetch tool, I would use it like:
            # response = await web_fetch(prompt=f"Get content from {url}")
            # return response.get("content")
            print(f"Simulating fetching content from {url}")
            return f"Content from {url}: This is a simulated article about the topic."
        except Exception as e:
            print(f"Error fetching content from {url}: {e}")
            return None

    async def gather_and_enrich_resources(
        self,
        topic: str,
        user_provided_urls: Optional[List[str]] = None,
        user_provided_text: Optional[str] = None,  # Corrected type hint
        perform_web_search: bool = False,
        model: str = "gpt-4o-mini",  # Model for enrichment
    ) -> EnrichedContext:
        """
        Gathers resources from various sources and enriches them into a concise summary.
        """
        gathered_resources: List[GatheredResource] = []
        all_raw_content: List[str] = []

        # 1. Process user-provided text
        if user_provided_text:
            gathered_resources.append(
                GatheredResource(source="user_text", content=user_provided_text)
            )
            all_raw_content.append(user_provided_text)

        # 2. Fetch content from user-provided URLs
        if user_provided_urls:
            fetch_tasks = [self._fetch_url_content(url) for url in user_provided_urls]
            url_contents = await asyncio.gather(*fetch_tasks)
            for url, content in zip(user_provided_urls, url_contents):
                if content:
                    gathered_resources.append(
                        GatheredResource(source="user_url", content=content, url=url)
                    )
                    all_raw_content.append(content)

        # 3. Perform web search (if requested)
        if perform_web_search:  # TODO: 아직 구현 안됨.
            # In a real scenario, this would use google_web_search tool
            # For now, simulate web search results
            # If I had access to the actual google_web_search tool, I would use it like:
            # search_results = await google_web_search(query=topic)
            # For this example, I'll use a placeholder.
            # For now, let's assume a simulated search result adds to all_raw_content
            # In a real implementation, this would be actual search results
            # gathered_resources.append(GatheredResource(source="web_search", content=""))
            # all_raw_content.append(simulated_search_content)
            pass

        # 4. If no content gathered, use LLM to generate initial context
        if not all_raw_content:
            llm_generated_content_prompt = f"Generate a concise, informative overview of the topic: '{topic}'. Focus on key aspects and provide a good starting point for a presentation. The content should be suitable for a slide presentation."
            llm_response = await generate_content_openai(
                llm_generated_content_prompt, model=model
            )

            # Assuming llm_response is a string or has a 'text' attribute
            generated_text = (
                llm_response.text
                if hasattr(llm_response, "text")
                else str(llm_response)
            )

            gathered_resources.append(
                GatheredResource(source="llm_generation", content=generated_text)
            )
            all_raw_content.append(generated_text)
            print(f"LLM generated content for topic: {topic}")

        # 5. Create a summary from all raw content
        # In a real scenario, this would involve an LLM call to summarize all_raw_content
        # For now, we'll concatenate the content as a placeholder.
        concatenated_summary = (
            "\n\n".join(all_raw_content)
            if all_raw_content
            else f"No specific resources found for topic: {topic}."
        )

        return EnrichedContext(
            summary=concatenated_summary, raw_resources=gathered_resources
        )
