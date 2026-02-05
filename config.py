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
# PAGE CONFIGURATIONS - Load from .env
# ============================================
# Dynamically loads pages from environment variables
# Pattern: FB_PAGE_1_*, FB_PAGE_2_*, etc.
# ============================================

PAGES_CONFIG = {}

# Load all pages from environment variables
page_index = 1
while True:
    page_id = os.getenv(f'FB_PAGE_{page_index}_ID')
    
    # Stop when no more pages found
    if not page_id:
        break
    
    page_name = os.getenv(f'FB_PAGE_{page_index}_NAME', f'Page {page_index}')
    page_token = os.getenv(f'FB_PAGE_{page_index}_ACCESS_TOKEN')
    
    # Only add if token exists and is not a placeholder
    if page_token and not page_token.startswith('YOUR_'):
        PAGES_CONFIG[page_id] = {
            'name': page_name,
            'accessToken': page_token
        }
        print(f'✓ Loaded page: {page_name} (ID: {page_id})')
    else:
        print(f'⚠ Skipped page {page_id}: Invalid or missing token')
    
    page_index += 1

# Print loaded configuration
if PAGES_CONFIG:
    print(f'\n✓ Total pages loaded: {len(PAGES_CONFIG)}')
else:
    print('\n⚠ WARNING: No pages configured! Please check your .env file')

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
    if not access_token or access_token.startswith('YOUR_') or len(access_token) < 50:
        print(f'ERROR: Page {page_id} ({config.get("name")}) has invalid or missing accessToken!')
        print('Please update the accessToken in your .env file')
        return None
    
    return config
