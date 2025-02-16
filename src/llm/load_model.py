import os
import toml
import logging
import re
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAI

# Load environment variables
load_dotenv()
config = toml.load("config.toml")

# Setup logger correctly
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

class LoadGemini(GoogleGenerativeAI):
    def __init__(self):
        model = config["gemini"]["model"]
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        super().__init__(model=model, api_key=gemini_api_key)

    def gemini_response(self, query):
        response = self.invoke(query)
        return response


# gemini_object = LoadGemini()
# response = gemini_object.gemini_response('''
    
# ''')

# logger.info(f"Received Response from LLM:\n{response}")
