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

async def split_long_message(message, first_chunk_size=500, subsequent_chunk_size=1900):
    """Split a long message into chunks with specified sizes for the first and subsequent chunks."""
    if len(message) <= first_chunk_size:
        return [message]
    
    chunks = []
    current_chunk = ""
    current_limit = first_chunk_size
    
    # Split by lines first to keep formatting
    for line in message.split('\n'):
        if len(current_chunk) + len(line) + 1 <= current_limit:
            current_chunk += line + '\n'
        else:
            # If the line itself is longer than the current limit, split it
            if len(line) > current_limit:
                words = line.split(' ')
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= current_limit:
                        current_chunk += word + ' '
                    else:
                        chunks.append(current_chunk.strip())
                        current_chunk = word + ' '
                        current_limit = subsequent_chunk_size
            else:
                # If current chunk is not empty, add it to chunks
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line + '\n'
                current_limit = subsequent_chunk_size
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

@client.tree.command(name="counselor", description="Ask a question to the academic counselor")
async def counselor(interaction: discord.Interaction, question: str):
    try:
        # Defer the response since AI might take time
        await interaction.response.defer(ephemeral=False)
        
        # Get AI response
        response = await get_ai_response(question)
        
        # Format initial response with user mention
        initial_response = f"{interaction.user.mention} Here's your answer to question: {question}\n\n{response}"
        
        # Split into chunks
        chunks = await split_long_message(initial_response)
        
        # Send first chunk (500 characters)
        first_message = await interaction.followup.send(chunks[0])
        
        # Check if we have more chunks to send
        if len(chunks) > 1:
            # If in a thread, send remaining chunks directly
            if isinstance(interaction.channel, discord.Thread):
                for chunk in chunks[1:]:
                    await interaction.channel.send(chunk)
            # If in a guild channel, create a thread
            elif interaction.guild:
                try:
                    thread = await interaction.channel.create_thread(
                        name=f"Answer: {question[:50]}..." if len(question) > 50 else f"Answer: {question}",
                        message=first_message,
                        auto_archive_duration=60  # Archive after 1 hour
                    )
                    
                    # Send remaining chunks in thread
                    for chunk in chunks[1:]:
                        await thread.send(chunk)
                        
                except Exception as thread_error:
                    # Log the error for debugging
                    print(f"Could not create thread: {str(thread_error)}")
                    
                    # Send remaining chunks as regular messages in the same channel
                    for chunk in chunks[1:]:
                        await interaction.followup.send(chunk)
            else:
                # If not in a guild, send remaining chunks as regular messages
                for chunk in chunks[1:]:
                    await interaction.followup.send(chunk)
                
    except Exception as e:
        print(f"Error in counselor command: {str(e)}")
        error_msg = "Sorry, I encountered an error. Please try again."
        if not interaction.response.is_done():
            await interaction.response.send_message(error_msg, ephemeral=True)
        else:
            await interaction.followup.send(error_msg, ephemeral=True)

# Run the bot
client.run(os.getenv('DISCORD_TOKEN')) 