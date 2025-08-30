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

# 공통.
- 환경설정은 uv add "pakage" 또는 uv pip install 로.
- 각 과정에서 각 llm 토큰 사용량, 걸린 시간 등 모니터링을 편하게 할 수잇는 프레임워크 도입.
- reddis DB 사용
- pytest 를 통해 테스트 커버리지 확보 (90% 이상); uv run pytest 통과 목표.
- 시스템 설계의 지침은 "what_is_good_system.md" 를 참고할 것!
