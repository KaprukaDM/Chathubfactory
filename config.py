import os
from supabase import create_client, Client
from dotenv import load_dotenv
import requests
from datetime import datetime

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


# ============================================
# TOKEN VALIDATION FUNCTIONS - NEW
# ============================================

def validate_page_token(page_id, access_token):
    """
    Validate a Facebook Page Access Token with the Graph API.
    
    Args:
        page_id: Facebook Page ID
        access_token: Page Access Token to validate
        
    Returns:
        dict: {'valid': bool, 'data': dict, 'error': str}
    """
    try:
        # Use debug_token endpoint to check token validity
        url = 'https://graph.facebook.com/v19.0/debug_token'
        params = {
            'input_token': access_token,
            'access_token': access_token  # Page token can validate itself
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if response.status_code != 200:
            return {
                'valid': False,
                'error': data.get('error', {}).get('message', 'Unknown error'),
                'data': None
            }
        
        token_data = data.get('data', {})
        
        # Check if token is valid
        is_valid = token_data.get('is_valid', False)
        expires_at = token_data.get('expires_at', 0)
        token_type = token_data.get('type', 'unknown')
        
        # Check expiry
        if expires_at == 0:
            expiry_msg = 'Never expires ✓'
        else:
            expiry_date = datetime.fromtimestamp(expires_at)
            days_left = (expiry_date - datetime.now()).days
            expiry_msg = f'Expires in {days_left} days'
            
            if days_left < 7:
                expiry_msg += ' ⚠ WARNING: Expiring soon!'
        
        return {
            'valid': is_valid,
            'data': {
                'type': token_type,
                'expires_at': expires_at,
                'expiry_message': expiry_msg,
                'scopes': token_data.get('scopes', [])
            },
            'error': None if is_valid else 'Token is invalid'
        }
        
    except requests.exceptions.Timeout:
        return {
            'valid': False,
            'error': 'Facebook API timeout',
            'data': None
        }
    except Exception as e:
        return {
            'valid': False,
            'error': f'Validation error: {str(e)}',
            'data': None
        }


def validate_all_tokens():
    """
    Validate all configured page tokens on startup.
    Prints detailed status for each page.
    """
    print('\n' + '='*60)
    print('VALIDATING FACEBOOK PAGE TOKENS')
    print('='*60)
    
    all_valid = True
    
    for page_id, config in PAGES_CONFIG.items():
        page_name = config.get('name')
        access_token = config.get('accessToken')
        
        print(f'\n📄 {page_name} (ID: {page_id})')
        print(f'   Validating token...')
        
        result = validate_page_token(page_id, access_token)
        
        if result['valid']:
            print(f'   ✅ Token is VALID')
            if result['data']:
                print(f'   📅 {result["data"]["expiry_message"]}')
                print(f'   🔑 Type: {result["data"]["type"]}')
        else:
            print(f'   ❌ Token is INVALID')
            print(f'   ⚠️  Error: {result["error"]}')
            print(f'   💡 Action: Generate a new token and update .env file')
            all_valid = False
    
    print('\n' + '='*60)
    if all_valid:
        print('✅ ALL TOKENS VALID - Ready to receive messages!')
    else:
        print('⚠️  SOME TOKENS INVALID - Please fix before deployment!')
    print('='*60 + '\n')
    
    return all_valid


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
