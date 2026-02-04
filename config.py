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
    '123456789': {  # Replace with your Facebook Page ID
        'name': 'Your Page Name',
        'accessToken': 'YOUR_PAGE_ACCESS_TOKEN'  # REQUIRED - Get from Facebook Developer Console
    },
    '987654321': {  # Add more pages as needed
        'name': 'Another Page',
        'accessToken': 'ANOTHER_PAGE_ACCESS_TOKEN'
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
