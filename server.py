import subprocess
import sys
import os
from pyngrok import ngrok
import logging
import time
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_ngrok():
    """Start ngrok tunnel"""
    try:
        # Get ngrok auth token from environment
        load_dotenv()
        ngrok_token = os.getenv('NGROK_AUTH_TOKEN')
        if ngrok_token:
            ngrok.set_auth_token(ngrok_token)
        
        # Open an HTTP tunnel on the default port 8080
        public_url = ngrok.connect(8080)
        logger.info(f"ngrok tunnel established at: {public_url}")
        
        return public_url
    except Exception as e:
        logger.error(f"Error starting ngrok: {str(e)}")
        return None

def run_bot():
    """Run the Discord bot"""
    try:
        # Start the bot process
        bot_process = subprocess.Popen([sys.executable, "bot.py"], 
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
        
        logger.info("Discord bot started")
        return bot_process
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        return None

def main():
    """Main function to run the server"""
    try:
        # Start ngrok
        ngrok_url = start_ngrok()
        if not ngrok_url:
            logger.error("Failed to start ngrok")
            return

        # Start the bot
        bot_process = run_bot()
        if not bot_process:
            logger.error("Failed to start bot")
            ngrok.kill()
            return

        # Keep the server running and monitor the bot process
        while True:
            # Check if bot is still running
            if bot_process.poll() is not None:
                # Bot has stopped, check exit code
                return_code = bot_process.poll()
                logger.error(f"Bot process stopped with return code: {return_code}")
                
                # Get any error output
                _, stderr = bot_process.communicate()
                if stderr:
                    logger.error(f"Bot error output: {stderr.decode()}")
                
                # Restart the bot
                logger.info("Attempting to restart bot...")
                bot_process = run_bot()
                if not bot_process:
                    logger.error("Failed to restart bot")
                    break
            
            # Log that server is still running
            logger.info("Server is running... (Press CTRL+C to stop)")
            time.sleep(60)  # Check every minute

    except KeyboardInterrupt:
        logger.info("Server shutdown initiated...")
    finally:
        # Cleanup
        if 'bot_process' in locals():
            bot_process.terminate()
            logger.info("Bot process terminated")
        
        ngrok.kill()
        logger.info("ngrok tunnel closed")

if __name__ == "__main__":
    main() 