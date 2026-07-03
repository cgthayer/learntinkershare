#!/usr/bin/env python3

# example.py
# pip install smolagents[toolkit]
# pip install smolagents[litellm]
# put api keys in a .env file or environment vars

import dotenv
import os
from smolagents import ToolCallingAgent, LiteLLMModel

dotenv.load_dotenv()

if __name__ == "__main__":
    model = LiteLLMModel(
        model_id="anthropic/claude-4-5-sonnet-latest",
        temperature=0.0,
        api_key=os.environ["ANTHROPIC_API_KEY"]
    )
    agent = ToolCallingAgent(tools=[], model=model)
    result = agent.run("What are the days of the week as a JSON array?")
    print("GOT:", result)
