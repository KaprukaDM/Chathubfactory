import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Webhook verification token for Facebook
WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN', 'your-webhook-token')

# Page configurations - IMPORTANT: Each page MUST have an accessToken
PAGES_CONFIG = {
    '109408748617460': {  # Your Facebook Page ID
        'name': 'Social Mart - Sri Lanka',
        'accessToken': 'EAAdarVZBfyZCgBP66f09Cls0B6ZBx5YTk34UFKCSfFWunDFIo7cxgWAgSAZBKA9ovZCqDfnD7ECMtFGkTgVWMcQNJA70iEUTmZC3oZB8VHFCxWBZBkeL7IZCkBL3DLQuNZAbkUwXHRlZCFq0cUjNMrZAZCgD3E3f1ZCSttMy5MHx9jFqIOW9tbA8nu5WpQOZCLwtPJmXW51EgGKqhIbkiKNYfmx184ZD'  # TODO: Replace with your actual Page Access Token
    }
}

def get_page_config(page_id):
    """
    Get configuration for a specific page.
    
    Args:
        page_id: Facebook Page ID
        
    Returns:
        Dictionary with page config including 'name' and 'accessToken'
        or None if page not found
    """
    config = PAGES_CONFIG.get(str(page_id))
    
    if not config:
        print(f'Page {page_id} not found in configuration')
        return None
    
    # Validate that accessToken exists
    if not config.get('accessToken'):
        print(f'ERROR: Page {page_id} ({config.get("name")}) is missing accessToken!')
        print('Please add the accessToken to PAGES_CONFIG in config.py')
        return None
    
    return config
