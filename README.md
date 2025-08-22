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

The core functionality is exposed through a single API endpoint.

### Generate a Presentation

  * **Endpoint:** `POST /api/v1/generate`

  * **Description:** Creates a new presentation based on a user-provided topic.

  * **Body:**

    ```json
    {
      "topic": "The Impact of AI on Marketing",
      "slide_count": 5
    }
    ```

  * **Success Response (200 OK):**

    ```json
    {
      "title": "The Impact of AI on Marketing",
      "slides_html": [
        "<html></html>",
        "<html></html>",
        "<html></html>"
      ]
    }
    ```

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