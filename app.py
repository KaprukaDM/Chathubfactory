from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import os
from config import supabase, WEBHOOK_VERIFY_TOKEN, get_page_config

app = Flask(__name__)

# Enable CORS for GitHub Pages
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://kaprukadm.github.io",
            "http://localhost:3000",
            "http://localhost:5000",
            "http://127.0.0.1:5000"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": False,
        "max_age": 3600
    }
})

# Root endpoint
@app.route('/')
def home():
    return jsonify({
        'message': 'Facebook Messenger Hub API',
        'endpoints': {
            'webhook': '/webhook',
            'send_message': '/api/send',
            'send_image': '/api/send-image',
            'customer_name': '/api/customer-name/<psid>',
            'unreplied_counts': '/api/unreplied-counts',
            'health': '/health'
        }
    })

# Health check
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

# Webhook verification (GET)
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode and token:
        if mode == 'subscribe' and token == WEBHOOK_VERIFY_TOKEN:
            print('WEBHOOK_VERIFIED')
            return challenge, 200
        else:
            return 'Forbidden', 403
    return 'Bad Request', 400

# Webhook receiver (POST)
@app.route('/webhook', methods=['POST'])
def webhook():
    body = request.get_json()

    if body.get('object') == 'page':
        for entry in body.get('entry', []):
            page_id = entry.get('id')

            for messaging_event in entry.get('messaging', []):
                handle_message(messaging_event, page_id)

        return 'EVENT_RECEIVED', 200
    else:
        return 'Not Found', 404

def handle_message(event, page_id):
    """Process incoming Facebook message"""
    try:
        sender_id = event['sender']['id']
        page_config = get_page_config(page_id)

        if not page_config:
            print(f'Page {page_id} not configured')
            return

        # Handle text messages
        if event.get('message'):
            message_id = event['message']['mid']
            message_text = event['message'].get('text', '')
            
            # Check for attachments (images, etc.)
            attachments = event['message'].get('attachments', [])
            message_type = 'text'
            image_url = None
            
            if attachments:
                for attachment in attachments:
                    if attachment.get('type') == 'image':
                        message_type = 'image'
                        image_url = attachment.get('payload', {}).get('url')
                        break

            # Get sender name from Facebook API
            sender_name = get_sender_name(sender_id, page_config.get('accessToken'))

            # Create conversation ID
            conversation_id = f"fb_{page_id}_{sender_id}"

            # Check if conversation exists
            result = supabase.table('conversations').select('*').eq('conversation_id', conversation_id).execute()

            if not result.data:
                # Create new conversation
                supabase.table('conversations').insert({
                    'conversation_id': conversation_id,
                    'platform': 'facebook',
                    'page_id': page_id,
                    'page_name': page_config.get('name', 'Unknown Page'),
                    'customer_psid': sender_id,
                    'customer_name': sender_name,
                    'customer_name_fetched': True,
                    'last_message_time': datetime.now().isoformat(),
                    'status': 'active'
                }).execute()
            else:
                # Update last message time and name
                supabase.table('conversations').update({
                    'last_message_time': datetime.now().isoformat(),
                    'customer_name': sender_name,
                    'customer_name_fetched': True
                }).eq('conversation_id', conversation_id).execute()

            # Store message
            supabase.table('messages').insert({
                'conversation_id': conversation_id,
                'platform': 'facebook',
                'message_id': message_id,
                'sender_type': 'customer',
                'sender_psid': sender_id,
                'message_text': message_text,
                'message_type': message_type,
                'image_url': image_url,
                'replied': False,
                'created_at': datetime.now().isoformat(),
                'status': 'received'
            }).execute()

            print(f'Message stored: {conversation_id} - Type: {message_type}')

    except Exception as e:
        print(f'Error handling message: {str(e)}')

def get_sender_name(sender_id, access_token):
    """Fetch sender name from Facebook Graph API"""
    try:
        if not access_token:
            print('Warning: access_token is missing')
            return 'Unknown'
            
        url = f'https://graph.facebook.com/v19.0/{sender_id}'
        params = {
            'fields': 'name',
            'access_token': access_token
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        # Check for Facebook API errors
        if 'error' in data:
            print(f'Facebook API Error getting sender name: {data["error"]}')
            return 'Unknown'
        
        return data.get('name', 'Unknown')
    except Exception as e:
        print(f'Error fetching sender name: {str(e)}')
        return 'Unknown'

# ============================================
# NEW ENDPOINT 1: Send message with HUMAN_AGENT tag support
# ============================================
@app.route('/api/send', methods=['POST', 'OPTIONS'])
def send_message():
    """Send reply back to Facebook Messenger"""

    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        page_id = data.get('page_id')
        recipient_id = data.get('recipient_id')
        message_text = data.get('message_text')
        use_human_agent_tag = data.get('use_human_agent_tag', False)

        if not all([page_id, recipient_id, message_text]):
            return jsonify({'error': 'Missing required fields'}), 400

        page_config = get_page_config(page_id)
        if not page_config:
            return jsonify({'error': f'Page {page_id} not configured'}), 400

        # Check if accessToken exists
        access_token = page_config.get('accessToken')
        if not access_token:
            print(f'Error: accessToken missing for page {page_id}')
            return jsonify({'error': 'Page access token not configured. Check your .env file.'}), 400

        # Send to Facebook
        url = 'https://graph.facebook.com/v19.0/me/messages'
        params = {'access_token': access_token}
        headers = {'Content-Type': 'application/json'}
        
        # Build payload with optional HUMAN_AGENT tag
        payload = {
            'recipient': {'id': recipient_id},
            'message': {'text': message_text}
        }
        
        if use_human_agent_tag:
            payload['messaging_type'] = 'MESSAGE_TAG'
            payload['tag'] = 'HUMAN_AGENT'
        else:
            payload['messaging_type'] = 'RESPONSE'

        response = requests.post(url, params=params, headers=headers, json=payload, timeout=10)
        response_data = response.json()

        if response.status_code == 200:
            # Store sent message
            conversation_id = f"fb_{page_id}_{recipient_id}"
            supabase.table('messages').insert({
                'conversation_id': conversation_id,
                'platform': 'facebook',
                'message_id': response_data.get('message_id'),
                'sender_type': 'agent',
                'message_text': message_text,
                'message_type': 'text',
                'created_at': datetime.now().isoformat(),
                'status': 'sent'
            }).execute()

            return jsonify({'success': True, 'data': response_data}), 200
        else:
            error_msg = response_data.get('error', {}).get('message', 'Unknown Facebook error')
            error_code = response_data.get('error', {}).get('code', 'N/A')
            print(f'Facebook API Error: [{error_code}] {error_msg}')
            return jsonify({'error': f'Facebook error: {error_msg}'}), response.status_code

    except Exception as e:
        print(f'Error in send_message: {str(e)}')
        return jsonify({'error': str(e)}), 500

# ============================================
# NEW ENDPOINT 2: Send image message
# ============================================
@app.route('/api/send-image', methods=['POST', 'OPTIONS'])
def send_image():
    """Send image message to Facebook Messenger"""
    
    if request.method == 'OPTIONS':
        return '', 204

    try:
        page_id = request.form.get('page_id')
        recipient_id = request.form.get('recipient_id')
        use_human_agent_tag = request.form.get('use_human_agent_tag', 'false').lower() == 'true'
        
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
            
        image_file = request.files['image']
        
        if not all([page_id, recipient_id]):
            return jsonify({'error': 'Missing required fields'}), 400

        page_config = get_page_config(page_id)
        if not page_config:
            return jsonify({'error': f'Page {page_id} not configured'}), 400

        access_token = page_config.get('accessToken')
        if not access_token:
            return jsonify({'error': 'Page access token not configured'}), 400

        # Send image to Facebook
        url = 'https://graph.facebook.com/v19.0/me/messages'
        params = {'access_token': access_token}
        
        # Build payload
        payload = {
            'recipient': {'id': recipient_id},
            'message': {
                'attachment': {
                    'type': 'image',
                    'payload': {
                        'is_reusable': True
                    }
                }
            }
        }
        
        if use_human_agent_tag:
            payload['messaging_type'] = 'MESSAGE_TAG'
            payload['tag'] = 'HUMAN_AGENT'
        else:
            payload['messaging_type'] = 'RESPONSE'

        # Prepare multipart form data
        files = {
            'message': (None, str(payload).replace("'", '"')),
            'filedata': (image_file.filename, image_file.read(), image_file.content_type)
        }

        response = requests.post(url, params=params, files=files, timeout=30)
        response_data = response.json()

        if response.status_code == 200:
            # Get image URL from response
            image_url = response_data.get('attachment_id', '')
            
            # Store sent message
            conversation_id = f"fb_{page_id}_{recipient_id}"
            supabase.table('messages').insert({
                'conversation_id': conversation_id,
                'platform': 'facebook',
                'message_id': response_data.get('message_id'),
                'sender_type': 'agent',
                'message_text': '[Image]',
                'message_type': 'image',
                'image_url': image_url,
                'created_at': datetime.now().isoformat(),
                'status': 'sent'
            }).execute()

            return jsonify({'success': True, 'data': response_data}), 200
        else:
            error_msg = response_data.get('error', {}).get('message', 'Unknown error')
            return jsonify({'error': f'Facebook error: {error_msg}'}), response.status_code

    except Exception as e:
        print(f'Error in send_image: {str(e)}')
        return jsonify({'error': str(e)}), 500

# ============================================
# NEW ENDPOINT 3: Fetch customer name from Facebook
# ============================================
@app.route('/api/customer-name/<psid>', methods=['GET'])
def get_customer_name(psid):
    """Fetch customer name from Facebook Graph API"""
    try:
        # Find which page this customer belongs to (check conversations)
        conv_result = supabase.table('conversations').select('page_id').eq('customer_psid', psid).limit(1).execute()
        
        if not conv_result.data:
            return jsonify({'error': 'Customer not found'}), 404
        
        page_id = conv_result.data[0]['page_id']
        page_config = get_page_config(page_id)
        
        if not page_config:
            return jsonify({'error': 'Page not configured'}), 400
        
        access_token = page_config.get('accessToken')
        if not access_token:
            return jsonify({'error': 'Access token missing'}), 400
        
        # Fetch name from Facebook
        name = get_sender_name(psid, access_token)
        
        if name and name != 'Unknown':
            # Update all conversations with this customer
            supabase.table('conversations').update({
                'customer_name': name,
                'customer_name_fetched': True
            }).eq('customer_psid', psid).execute()
            
            return jsonify({'success': True, 'name': name}), 200
        else:
            return jsonify({'success': False, 'name': None, 'error': 'Could not fetch name'}), 200
            
    except Exception as e:
        print(f'Error in get_customer_name: {str(e)}')
        return jsonify({'error': str(e)}), 500

# ============================================
# NEW ENDPOINT 4: Get unreplied message counts
# ============================================
@app.route('/api/unreplied-counts', methods=['GET'])
def get_unreplied_counts():
    """Get count of unreplied messages per page/customer"""
    try:
        # Call the Supabase function we created
        result = supabase.rpc('get_unreplied_counts').execute()
        
        # Format as dictionary: "pageId_psid": count
        counts = {}
        if result.data:
            for row in result.data:
                key = f"{row['page_id']}_{row['customer_psid']}"
                counts[key] = row['unreplied_count']
        
        return jsonify({'success': True, 'counts': counts}), 200
        
    except Exception as e:
        print(f'Error in get_unreplied_counts: {str(e)}')
        # Fallback: calculate manually if RPC fails
        try:
            # Get all conversations
            convs = supabase.table('conversations').select('conversation_id, page_id, customer_psid').execute()
            counts = {}
            
            for conv in convs.data:
                # Count unreplied customer messages
                messages = supabase.table('messages').select('id').eq('conversation_id', conv['conversation_id']).eq('sender_type', 'customer').eq('replied', False).execute()
                
                count = len(messages.data)
                if count > 0:
                    key = f"{conv['page_id']}_{conv['customer_psid']}"
                    counts[key] = count
            
            return jsonify({'success': True, 'counts': counts}), 200
        except Exception as e2:
            return jsonify({'error': str(e2)}), 500

# Get conversation messages
@app.route('/api/conversation/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """Get all messages for a conversation"""
    try:
        result = supabase.table('messages').select('*').eq('conversation_id', conversation_id).order('created_at').execute()
        return jsonify({'success': True, 'messages': result.data}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Get all active conversations
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get all active conversations"""
    try:
        result = supabase.table('conversations').select('*').eq('status', 'active').order('last_message_time', desc=True).execute()
        return jsonify({'success': True, 'conversations': result.data}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# VALIDATE TOKENS ON STARTUP (Issue #4 Fix)
# ============================================
# This runs when Gunicorn imports the app
from config import validate_all_tokens
validate_all_tokens()

if __name__ == '__main__':
    # For local development with Flask dev server
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
