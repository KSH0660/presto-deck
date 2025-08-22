import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_content_openai(prompt: str, model: str = "gpt-4o-mini") -> str:
    """Generates content using the specified OpenAI model."""
    if not aclient.api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables.")

    try:
        chat_completion = await aclient.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=model,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Error generating content with OpenAI: {e}")
        raise
