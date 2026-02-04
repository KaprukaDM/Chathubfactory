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
        "origins": ["https://kaprukadm.github.io", "http://localhost:*"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
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
        if event.get('message') and event['message'].get('text'):
            message_text = event['message']['text']
            message_id = event['message']['mid']

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
                    'last_message_time': datetime.now().isoformat(),
                    'status': 'active'
                }).execute()
            else:
                # Update last message time and name
                supabase.table('conversations').update({
                    'last_message_time': datetime.now().isoformat(),
                    'customer_name': sender_name
                }).eq('conversation_id', conversation_id).execute()

            # Store message
            supabase.table('messages').insert({
                'conversation_id': conversation_id,
                'platform': 'facebook',
                'message_id': message_id,
                'sender_type': 'customer',
                'sender_psid': sender_id,
                'message_text': message_text,
                'created_at': datetime.now().isoformat(),
                'status': 'received'
            }).execute()

            print(f'Message stored: {conversation_id} - {message_text}')

    except Exception as e:
        print(f'Error handling message: {str(e)}')

def get_sender_name(sender_id, access_token):
    """Fetch sender name from Facebook Graph API"""
    try:
        if not access_token:
            print('Warning: access_token is missing')
            return 'Unknown'
            
        url = f'https://graph.facebook.com/v18.0/{sender_id}'
        params = {
            'fields': 'name',
            'access_token': access_token
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        return data.get('name', 'Unknown')
    except Exception as e:
        print(f'Error fetching sender name: {str(e)}')
        return 'Unknown'

# Send message API
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

        if not all([page_id, recipient_id, message_text]):
            return jsonify({'error': 'Missing required fields'}), 400

        page_config = get_page_config(page_id)
        if not page_config:
            return jsonify({'error': f'Page {page_id} not configured'}), 400

        # Check if accessToken exists
        access_token = page_config.get('accessToken')
        if not access_token:
            print(f'Error: accessToken missing for page {page_id}')
            return jsonify({'error': 'Page access token not configured. Check your config.py file.'}), 400

        # Send to Facebook
        url = 'https://graph.facebook.com/v18.0/me/messages'
        params = {'access_token': access_token}
        headers = {'Content-Type': 'application/json'}
        payload = {
            'recipient': {'id': recipient_id},
            'message': {'text': message_text},
            'messaging_type': 'RESPONSE'
        }

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
                'created_at': datetime.now().isoformat(),
                'status': 'sent'
            }).execute()

            return jsonify({'success': True, 'data': response_data}), 200
        else:
            error_msg = response_data.get('error', {}).get('message', 'Unknown Facebook error')
            print(f'Facebook API Error: {error_msg}')
            return jsonify({'error': f'Facebook error: {error_msg}'}), response.status_code

    except Exception as e:
        print(f'Error in send_message: {str(e)}')
        return jsonify({'error': str(e)}), 500

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
