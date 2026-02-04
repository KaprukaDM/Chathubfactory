import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing Supabase configuration in environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Webhook Configuration
WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')

# Facebook Pages Configuration
FACEBOOK_PAGES = [
    {
        'id': os.getenv('FB_PAGE_1_ID'),
        'name': os.getenv('FB_PAGE_1_NAME'),
        'access_token': os.getenv('FB_PAGE_1_ACCESS_TOKEN')
    },
    {
        'id': os.getenv('FB_PAGE_2_ID'),
        'name': os.getenv('FB_PAGE_2_NAME'),
        'access_token': os.getenv('FB_PAGE_2_ACCESS_TOKEN')
    },
    {
        'id': os.getenv('FB_PAGE_3_ID'),
        'name': os.getenv('FB_PAGE_3_NAME'),
        'access_token': os.getenv('FB_PAGE_3_ACCESS_TOKEN')
    },
    {
        'id': os.getenv('FB_PAGE_4_ID'),
        'name': os.getenv('FB_PAGE_4_NAME'),
        'access_token': os.getenv('FB_PAGE_4_ACCESS_TOKEN')
    }
]

def get_page_config(page_id):
    """Get configuration for a specific Facebook page"""
    for page in FACEBOOK_PAGES:
        if page['id'] == page_id:
            return page
    return None

def get_all_pages():
    """Get all configured Facebook pages"""
    return FACEBOOK_PAGES
