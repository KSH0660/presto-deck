# Presto ✨

**Presto** is an AI-powered presentation generator that transforms your simple topic into a full set of beautiful, editable slides in seconds. Stop wrestling with templates and focus on your message.

[](https://github.com)
[](https://opensource.org/licenses/MIT)

-----

## About The Project

Creating compelling presentations is time-consuming. You have to structure the narrative, write the content, find the right visuals, and design each slide. **Presto automates this entire process.**

By leveraging the power of Large Language Models (LLMs), Presto understands your topic, builds a logical story flow, writes the content for each slide, and matches it with the best visual layout. The result is a ready-to-use presentation delivered as clean HTML that you can edit directly in your browser.

### Core Features

  * **🤖 AI-Powered Content:** Generate a complete presentation outline and content from a single topic.
  * **🎨 Smart Layouts:** Automatically selects the best slide template for your content (e.g., title, list, image with text).
  * **✏️ In-Browser Editing:** Instantly edit text on your generated slides without needing any special software.
  * **🚀 Built with a Modern Stack:** Powered by Python, FastAPI, and the Gemini API for a fast and scalable backend.

-----

## Getting Started

Follow these steps to get the Presto server running on your local machine.

### Prerequisites

  * Python 3.10+
  * A virtual environment tool (e.g., `venv`)

### Installation & Setup

1.  **Clone the repository:**

    ```sh
    git clone https://github.com/your-username/presto.git
    cd presto
    ```

2.  **Create and activate a virtual environment:**

    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install the required dependencies:**

    ```sh
    pip install -r requirements.txt
    ```

4.  **Set up your environment variables:**
    Create a `.env` file in the project root. You can copy the example file to get started:

    ```sh
    cp .env.example .env
    ```

    Now, open the `.env` file and add your Gemini API key:

    ```
    GEMINI_API_KEY="YOUR_API_KEY_HERE"
    ```

5.  **Run the FastAPI server:**

    ```sh
    uvicorn app.main:app --reload
    ```

The API will now be running at `http://127.0.0.1:8000`. You can access the interactive API documentation at `http://127.0.0.1:8000/docs`.

-----

## API Usage

The API provides a simple end‑to‑end endpoint and modular endpoints for advanced flows like previews and partial retries.

### Orchestrator
- Endpoint: `POST /api/v1/generate`
- Description: Plan → select layouts → render all slides in one call.
- Body:
  ```json
  {
    "user_request": "Pitch deck for ...",
    "quality": "default" // one of: draft, default, premium
  }
  ```
- Success (200):
  ```json
  {
    "topic": "...",
    "audience": "...",
    "slides": [
      { "slide_id": 1, "template_name": "title.html", "html": "<h1>..." },
      { "slide_id": 2, "template_name": "content.html", "html": "<p>..." }
    ]
  }
  ```

### Modular Endpoints
- `POST /api/v1/plan`
  - Body:
    ```json
    { "user_request": "...", "quality": "default" }
    ```
  - Returns: `DeckPlan` only (no rendering)

- `POST /api/v1/layouts/select`
  - Body:
    ```json
    { "deck_plan": { /* DeckPlan */ }, "quality": "default" }
    ```
  - Returns: `LayoutSelection` with candidate templates per slide

- `POST /api/v1/slides/render`
  - Body:
    ```json
    {
      "deck_plan": { /* DeckPlan */ },
      "slides": [ /* optional: subset of SlideSpec */ ],
      "candidate_map": { "1": ["title.html"], "2": ["content.html"] },
      "quality": "default"
    }
    ```
  - Returns: `{ "slides": [ SlideHTML, ... ] }`

- `POST /api/v1/preview`
  - Body (either `slide` or `slide_id` is required):
    ```json
    {
      "deck_plan": { /* DeckPlan */ },
      "slide_id": 1,
      "candidate_templates": ["title.html"], // optional; auto-picks if omitted
      "quality": "default"
    }
    ```
  - Returns: one `SlideHTML`

### Utility Endpoints
- `GET /healthz`: Liveness check
- `GET /readyz`: Readiness check with template count and API key presence
- `GET /api/v1/meta`: Service metadata and quality tier config
- `GET /api/v1/templates`: Available template filenames

-----

## Project Roadmap

This is just the beginning\! Here are some of the features we're planning to add:

  * [ ] **More Design Themes:** Add a variety of professional design themes to choose from.
  * [ ] **Image Generation:** Integrate AI image generation to create custom visuals for slides.
  * [ ] **PPTX Export:** Allow users to download the final presentation as a `.pptx` file.
  * [ ] **User Accounts:** Save and manage your created presentations.

We welcome contributions\! Please feel free to fork the repository and submit pull requests.

## License

Distributed under the MIT License. See `LICENSE` for more information.
