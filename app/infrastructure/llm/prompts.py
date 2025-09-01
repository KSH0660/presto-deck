from langchain.prompts import ChatPromptTemplate

DECK_PLAN_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert presentation designer. Your task is to create a comprehensive deck plan based on the user's requirements.

Create a well-structured presentation plan that is engaging and appropriate for the target audience. Consider logical flow, appropriate pacing, and content variety.""",
        ),
        (
            "human",
            """Create a presentation deck plan with the following requirements:

Title: {title}
Topic: {topic}
Target Audience: {audience}
Number of Slides: {slide_count}
Style: {style}
Language: {language}

Please ensure the presentation has a logical flow, engaging content, and appropriate pacing for the audience.""",
        ),
    ]
)


SLIDE_CONTENT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert content creator for presentations. Generate engaging slide content with proper HTML formatting.

Create well-formatted HTML content using appropriate tags (h1, h2, p, ul, li, strong, em, etc.). Make the content professional and engaging. Include detailed presenter notes that provide additional context and speaking points.""",
        ),
        (
            "human",
            """Generate content for this slide:

Deck Context:
- Title: {deck_title}
- Topic: {deck_topic}
- Target Audience: {deck_audience}

Slide Information:
- Number: {slide_number}
- Title: {slide_title}
- Type: {slide_type}
- Key Points: {key_points}
- Content Type: {content_type}

Create engaging content with {notes_detail} presenter notes.""",
        ),
    ]
)


SLIDE_UPDATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert presentation editor. Update the existing slide content based on user feedback while maintaining consistency and quality.

Incorporate the user's requested changes while preserving the professional tone and structure of the presentation.""",
        ),
        (
            "human",
            """Update this slide content based on the user's feedback:

Current Slide Content:
{current_content}

User's Update Request:
{update_prompt}

Slide Context:
{slide_context}

Please update the slide content according to the user's request while maintaining quality and consistency.""",
        ),
    ]
)
