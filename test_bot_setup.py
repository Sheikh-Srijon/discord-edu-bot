import os
from dotenv import load_dotenv
import discord
import openai
import asyncio
import requests
import json

# Load environment variables
load_dotenv()

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

async def test_openai_interaction(message):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": (
                    "You are a helpful and empathetic college application counselor. "
                    "Follow these guidelines when answering student questions:\n"
                    "Do your research, be data driven, cite sources and include hyperlinks to your claims if you can.\n"
                    "• Be strategic – focus on the best approach for success in college applications. Think of college hacks or tips that upperclassmen would give.\n"
                    "• Be informative – provide clear, concise, and useful insights.\n"
                    "• Answer in bullet points – keep responses short and easy to read.\n"
                    "• Be succinct but complete – give direct answers without unnecessary details"
                )},
                {"role": "user", "content": message}
            ]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"Failed to get response from OpenAI: {e}"

async def call_perplexity_api(question):
    try:
        api_key = os.getenv('PERPLEXITY_API_KEY')
        api_url = "https://api.perplexity.ai/chat/completions"

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            "model": "sonar",  # Using sonar model as shown in docs
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful and empathetic college application counselor. "
                        "Be data-driven, cite sources, and include hyperlinks to your claims. "
                        "Focus on strategic approaches and insider tips for college applications. "
                        "Keep responses structured and concise."
                    )
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 1000,  # Adjust as needed
            "return_citations": True
        }

        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        
        response_data = response.json()
        
        # Format response with citations if available
        answer = response_data['choices'][0]['message']['content']
        citations = response_data.get('citations', [])
        
        formatted_response = answer
        if citations:
            formatted_response += "\n\nSources:"
            for citation in citations:
                formatted_response += f"\n• {citation}"
        
        return formatted_response
        
    except Exception as e:
        return f"Failed to get response from Perplexity: {str(e)}"

def interactive_mode():
    print("\nEntering interactive mode with Perplexity AI.")
    print("Type 'quit' or 'exit' to end the conversation.\n")
    
    while True:
        user_input = input("\nYour question: ")
        
        if user_input.lower() in ['quit', 'exit']:
            print("Ending conversation. Goodbye!")
            break
        # change next line to whichever llm api you wanna call
        response = asyncio.run(call_perplexity_api(user_input))
        print("\nPerplexity response:")
        print(response)

def test_bot_setup():
    # Check if environment variables are loaded
    discord_token = os.getenv('DISCORD_TOKEN')
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    # Assert that each environment variable is set
    assert discord_token is not None, "DISCORD_TOKEN is not set in the .env file."
    assert openai_api_key is not None, "OPENAI_API_KEY is not set in the .env file."
    
    print("Environment variables are set correctly:")
    print(f"DISCORD_TOKEN: {discord_token[:5]}...")
    print(f"OPENAI_API_KEY: {openai_api_key[:5]}...")
    
    # Test OpenAI interaction
    print("\nTesting OpenAI interaction...")
    test_question = "What are the requirements for applying to college?"
    response = asyncio.run(test_openai_interaction(test_question))
    print(f"\nTest Question: {test_question}")
    print(f"OpenAI Response:\n{response}")

# Run the test
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        interactive_mode()
    else:
        test_bot_setup() 