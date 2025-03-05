import discord
from discord import app_commands
import openai
import os
from dotenv import load_dotenv
import requests
import json

# Load environment variables
load_dotenv()

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Create Discord client
class StudentCounselorBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Enable message content intent
        intents.members = True          # Enable members intent
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = StudentCounselorBot()

async def call_openai_api(question):
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
                {"role": "user", "content": question}
            ]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"Failed to get response from OpenAI: {str(e)}"

async def call_perplexity_api(question):
    try:
        api_key = os.getenv('PERPLEXITY_API_KEY')
        api_url = "https://api.perplexity.ai/chat/completions"

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful and empathetic college application counselor. "
                        "Be data-driven and reference sources with numbers [1], [2], etc. "
                        "Focus on strategic approaches and insider tips for college applications. "
                        "Keep responses structured and concise. "
                        "Use bullet points for clarity."
                        "Give the answer directly, without any preamble or introduction."
                    )
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 1000,
            "return_citations": True
        }

        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        
        response_data = response.json()
        
        # Get the main answer and citations
        answer = response_data['choices'][0]['message']['content']
        citations = response_data.get('citations', [])
        
        # Format response with numbered citations
        if citations:
            # Add numbered references to the answer if they don't exist
            if not '[1]' in answer:
                modified_answer = answer
                for i, citation in enumerate(citations, 1):
                    citation_domain = citation.split('/')[2]
                    if citation_domain in modified_answer:
                        modified_answer = modified_answer.replace(
                            citation_domain,
                            f"[{i}]"
                        )
                answer = modified_answer

            # Add a compact reference section
            answer += "\n\n**References:**"
            for i, citation in enumerate(citations, 1):
                # Make the URL shorter by removing common elements
                short_url = citation.replace('https://', '').replace('www.', '')
                answer += f"\n[{i}] <{citation}>"
        
        return answer
        
    except Exception as e:
        return f"Failed to get response from Perplexity: {str(e)}"

async def get_ai_response(question):
    # Choose which AI service to use
    return await call_perplexity_api(question)
    # To use OpenAI instead, comment out the above line and uncomment the below line
    # return await call_openai_api(question)

@client.event
async def on_ready():
    print(f'Bot is ready! Logged in as {client.user}')
    try:
        synced = await client.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

async def split_long_message(message):
    """Split a long message into chunks of 1900 characters (leaving room for formatting)"""
    if len(message) <= 1900:
        return [message]
    
    chunks = []
    current_chunk = ""
    
    # Split by lines first to keep formatting
    for line in message.split('\n'):
        if len(current_chunk) + len(line) + 1 <= 1900:
            current_chunk += line + '\n'
        else:
            # If current chunk is not empty, add it to chunks
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line + '\n'
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

@client.tree.command(name="counselor", description="Ask a question to the academic counselor")
async def counselor(interaction: discord.Interaction, question: str):
    try:
        # Defer the response since AI might take time
        await interaction.response.defer(ephemeral=False)
        
        # Create a thread for the question
        thread = await interaction.channel.create_thread(
            name=f"Question: {question[:50]}...",
            type=discord.ChannelType.public_thread
        )
        
        # Get AI response
        response = await get_ai_response(question)
        
        # Split response if it's too long
        message_chunks = await split_long_message(response)
        
        # Send each chunk in the thread
        for chunk in message_chunks:
            await thread.send(chunk)
            
        await interaction.followup.send(f"Here's my answer to question: {question}")
        
    except discord.errors.Forbidden as e:
        print(f"Permission error: {str(e)}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Sorry, I don't have permission to do that. Please check my permissions.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "Sorry, I don't have permission to do that. Please check my permissions.",
                ephemeral=True
            )
    except Exception as e:
        print(f"Error in counselor command: {str(e)}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Sorry, I encountered an error. Please try again.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "Sorry, I encountered an error. Please try again.",
                ephemeral=True
            )

@client.event
async def on_message(message):
    print("NEW VERSION: Running updated message handler!")  # Debug print
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Only respond if the bot is mentioned and message ends with question mark
    is_question = message.content.strip().endswith('?')
    bot_mentioned = client.user.mentioned_in(message)

    if is_question and bot_mentioned:
        try:
            # Get AI response first
            response = await get_ai_response(message.content)
            
            # Format initial response with user mention
            initial_response = f"{message.author.mention}, here's your answer:\n\n{response}"
            
            # Send first message in channel (up to 1900 chars to be safe)
            if len(initial_response) <= 1900:
                await message.channel.send(initial_response)
            else:
                # Send first chunk and create thread from it
                first_chunk = initial_response[:1900]
                first_message = await message.channel.send(first_chunk)
                
                # Create thread only if we have more content
                thread = await first_message.create_thread(
                    name=f"Question: {message.content[:50]}...",
                    type=discord.ChannelType.public_thread
                )
                
                # Send remaining content in thread
                remaining_content = initial_response[1900:]
                chunks = await split_long_message(remaining_content)
                for chunk in chunks:
                    await thread.send(chunk)
                
        except Exception as e:
            print(f"Error in message handler: {str(e)}")
            await message.channel.send("Sorry, I encountered an error. Please try again.")

# Run the bot
client.run(os.getenv('DISCORD_TOKEN')) 