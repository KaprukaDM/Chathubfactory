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

# ============================================
# PAGE CONFIGURATIONS - EDIT THIS SECTION
# ============================================
# Your Facebook Page ID: 109408748617460
# Page Name: Social Mart - Sri Lanka
# 
# INSTRUCTIONS:
# 1. Get your Page Access Token from Facebook Developers
# 2. Replace 'YOUR_PAGE_ACCESS_TOKEN' with the actual token
# 3. Do NOT include quotes inside the token
# 4. Keep the entire token (it's very long)
# ============================================

PAGES_CONFIG = {
    '109408748617460': {
        'name': 'Social Mart - Sri Lanka',
        'accessToken': 'EAAdarVZBfyZCgBP66f09Cls0B6ZBx5YTk34UFKCSfFWunDFIo7cxgWAgSAZBKA9ovZCqDfnD7ECMtFGkTgVWMcQNJA70iEUTmZC3oZB8VHFCxWBZBkeL7IZCkBL3DLQuNZAbkUwXHRlZCFq0cUjNMrZAZCgD3E3f1ZCSttMy5MHx9jFqIOW9tbA8nu5WpQOZCLwtPJmXW51EgGKqhIbkiKNYfmx184ZD'  # REPLACE WITH YOUR ACTUAL TOKEN
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
    
    # Validate that accessToken exists and is not a placeholder
    access_token = config.get('accessToken')
    # FIXED: Only check for placeholders and minimum length (removed EAAJZAZCHsJ0BA check)
    if not access_token or access_token.startswith('YOUR_') or len(access_token) < 50:
        print(f'ERROR: Page {page_id} ({config.get("name")}) has invalid or missing accessToken!')
        print('Please update the accessToken in PAGES_CONFIG')
        return None
    
    return config
