from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import os
import json
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
        'version': '2.1',
        'endpoints': {
            'webhook': '/webhook',
            'send_message': '/api/send',
            'send_image': '/api/send-image',
            'customer_name': '/api/customer-name/<psid>',
            'unreplied_counts': '/api/unreplied-counts',
            'conversations': '/api/conversations',
            'conversation': '/api/conversation/<id>',
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

        # Handle text messages and attachments
        if event.get('message'):
            message_id = event['message']['mid']
            message_text = event['message'].get('text', '')
            
            # Check for attachments (images, videos, files, etc.)
            attachments = event['message'].get('attachments', [])
            message_type = 'text'
            image_url = None
            attachment_type = None
            
            if attachments:
                for attachment in attachments:
                    att_type = attachment.get('type')
                    if att_type == 'image':
                        message_type = 'image'
                        attachment_type = 'image'
                        image_url = attachment.get('payload', {}).get('url')
                        if not message_text:
                            message_text = '[Image]'
                        break
                    elif att_type == 'video':
                        message_type = 'video'
                        attachment_type = 'video'
                        image_url = attachment.get('payload', {}).get('url')
                        if not message_text:
                            message_text = '[Video]'
                        break
                    elif att_type == 'file':
                        message_type = 'file'
                        attachment_type = 'file'
                        image_url = attachment.get('payload', {}).get('url')
                        if not message_text:
                            message_text = '[File]'
                        break
                    elif att_type == 'audio':
                        message_type = 'audio'
                        attachment_type = 'audio'
                        image_url = attachment.get('payload', {}).get('url')
                        if not message_text:
                            message_text = '[Audio]'
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
                    'customer_name_fetched': True if sender_name != 'Unknown' else False,
                    'last_message_time': datetime.now().isoformat(),
                    'status': 'active'
                }).execute()
                print(f'✅ New conversation created: {conversation_id}')
            else:
                # Update last message time and name if we got a real name
                update_data = {
                    'last_message_time': datetime.now().isoformat()
                }
                if sender_name != 'Unknown':
                    update_data['customer_name'] = sender_name
                    update_data['customer_name_fetched'] = True
                
                supabase.table('conversations').update(update_data).eq('conversation_id', conversation_id).execute()

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
                'attachment_type': attachment_type,
                'replied': False,
                'created_at': datetime.now().isoformat(),
                'status': 'received'
            }).execute()

            print(f'📨 Message stored: {conversation_id} - Type: {message_type}')

    except Exception as e:
        print(f'❌ Error handling message: {str(e)}')
        import traceback
        traceback.print_exc()

def get_sender_name(sender_id, access_token):
    """Fetch sender name from Facebook Graph API with detailed logging"""
    try:
        if not access_token:
            print('❌ Warning: access_token is missing')
            return 'Unknown'
        
        # Check if sender is valid
        if not sender_id or len(sender_id) < 5:
            print(f'❌ Invalid sender_id: {sender_id}')
            return 'Unknown'
            
        print(f'🔍 Fetching name from Facebook for PSID: {sender_id}')
        print(f'🔑 Using access token: {access_token[:20]}...')
        
        url = f'https://graph.facebook.com/v19.0/{sender_id}'
        params = {
            'fields': 'name',
            'access_token': access_token
        }
        
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        print(f'📡 Facebook API Response Status: {response.status_code}')
        print(f'📡 Facebook API Response Data: {data}')
        
        # Check for Facebook API errors
        if 'error' in data:
            error_msg = data['error'].get('message', 'Unknown error')
            error_code = data['error'].get('code', 'N/A')
            error_type = data['error'].get('type', 'N/A')
            error_subcode = data['error'].get('error_subcode', 'N/A')
            
            print(f'❌ Facebook API Error Details:')
            print(f'   Code: {error_code}')
            print(f'   Type: {error_type}')
            print(f'   Subcode: {error_subcode}')
            print(f'   Message: {error_msg}')
            
            # Common error handling
            if error_code == 190:
                print('⚠️ ACCESS TOKEN EXPIRED OR INVALID!')
                print('   → Go to Facebook Developer Console and regenerate token')
                print('   → Update environment variable in Render')
            elif error_code == 100:
                print('⚠️ Invalid parameter or insufficient permissions')
                print('   → Check if app has pages_read_engagement permission')
            elif error_code == 803:
                print('⚠️ Cannot query users by their user ID')
                print('   → This might be a page-scoped ID issue')
            elif 'page' in str(error_msg).lower():
                print('ℹ️ This appears to be a page, not a user')
                return data.get('name', 'Facebook Page')
            
            return 'Unknown'
        
        name = data.get('name', 'Unknown')
        print(f'✅ Successfully fetched name: {name}')
        return name
        
    except requests.exceptions.Timeout:
        print(f'⏱️ Timeout fetching name for {sender_id}')
        return 'Unknown'
    except requests.exceptions.RequestException as e:
        print(f'🌐 Network error fetching sender name: {str(e)}')
        return 'Unknown'
    except Exception as e:
        print(f'❌ Unexpected error fetching sender name: {str(e)}')
        import traceback
        traceback.print_exc()
        return 'Unknown'

# ============================================
# Send message with HUMAN_AGENT tag support
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

        print(f'📤 Send message request: page={page_id}, recipient={recipient_id}, use_tag={use_human_agent_tag}')

        if not all([page_id, recipient_id, message_text]):
            return jsonify({'error': 'Missing required fields'}), 400

        page_config = get_page_config(page_id)
        if not page_config:
            return jsonify({'error': f'Page {page_id} not configured'}), 400

        # Check if accessToken exists
        access_token = page_config.get('accessToken')
        if not access_token:
            print(f'❌ Error: accessToken missing for page {page_id}')
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
            print(f'🏷️ Using HUMAN_AGENT tag for message to {recipient_id}')
        else:
            payload['messaging_type'] = 'RESPONSE'

        print(f'📡 Sending to Facebook: {payload}')
        response = requests.post(url, params=params, headers=headers, json=payload, timeout=10)
        response_data = response.json()
        print(f'📡 Facebook response: {response_data}')

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

            print(f'✅ Message sent successfully: {response_data.get("message_id")}')
            return jsonify({'success': True, 'data': response_data}), 200
        else:
            error_msg = response_data.get('error', {}).get('message', 'Unknown Facebook error')
            error_code = response_data.get('error', {}).get('code', 'N/A')
            print(f'❌ Facebook API Error: [{error_code}] {error_msg}')
            return jsonify({'error': f'Facebook error: {error_msg}', 'code': error_code}), response.status_code

    except Exception as e:
        print(f'❌ Error in send_message: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# Send image message
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
        
        print(f'📤 Send image request: page={page_id}, recipient={recipient_id}, use_tag={use_human_agent_tag}')
        
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
            
        image_file = request.files['image']
        
        if not all([page_id, recipient_id]):
            return jsonify({'error': 'Missing required fields'}), 400

        if not image_file.filename:
            return jsonify({'error': 'No file selected'}), 400

        page_config = get_page_config(page_id)
        if not page_config:
            return jsonify({'error': f'Page {page_id} not configured'}), 400

        access_token = page_config.get('accessToken')
        if not access_token:
            return jsonify({'error': 'Page access token not configured'}), 400

        # Send image to Facebook
        url = 'https://graph.facebook.com/v19.0/me/messages'
        params = {'access_token': access_token}
        
        # Build message payload as JSON strings for multipart/form-data
        message_data = {
            'attachment': {
                'type': 'image',
                'payload': {
                    'is_reusable': True
                }
            }
        }
        
        # Prepare form data
        payload = {
            'recipient': json.dumps({'id': recipient_id}),
            'message': json.dumps(message_data)
        }
        
        if use_human_agent_tag:
            payload['messaging_type'] = 'MESSAGE_TAG'
            payload['tag'] = 'HUMAN_AGENT'
            print('🏷️ Using HUMAN_AGENT tag for image')
        else:
            payload['messaging_type'] = 'RESPONSE'

        # Read image file
        image_bytes = image_file.read()
        image_file.seek(0)
        
        # Prepare multipart form data
        files = {
            'filedata': (image_file.filename, image_bytes, image_file.content_type or 'image/jpeg')
        }

        print(f'📡 Sending image to Facebook: {image_file.filename} ({len(image_bytes)} bytes)')
        response = requests.post(url, params=params, data=payload, files=files, timeout=30)
        response_data = response.json()
        print(f'📡 Facebook image response: {response_data}')

        if response.status_code == 200:
            # Get attachment/message ID
            msg_id = response_data.get('message_id')
            attachment_id = response_data.get('attachment_id', '')
            
            # Store sent message
            conversation_id = f"fb_{page_id}_{recipient_id}"
            supabase.table('messages').insert({
                'conversation_id': conversation_id,
                'platform': 'facebook',
                'message_id': msg_id,
                'sender_type': 'agent',
                'message_text': '[Image]',
                'message_type': 'image',
                'image_url': attachment_id,
                'created_at': datetime.now().isoformat(),
                'status': 'sent'
            }).execute()

            print(f'✅ Image sent successfully: {msg_id}')
            return jsonify({'success': True, 'data': response_data}), 200
        else:
            error_msg = response_data.get('error', {}).get('message', 'Unknown error')
            error_code = response_data.get('error', {}).get('code', 'N/A')
            error_type = response_data.get('error', {}).get('type', 'N/A')
            print(f'❌ Facebook image error: [{error_code}] {error_type} - {error_msg}')
            print(f'Full error response: {response_data}')
            return jsonify({'error': f'Facebook error: {error_msg}', 'code': error_code}), response.status_code

    except Exception as e:
        print(f'❌ Error in send_image: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# Fetch customer name from Facebook - ENHANCED
# ============================================
@app.route('/api/customer-name/<psid>', methods=['GET'])
def get_customer_name(psid):
    """Fetch customer name from Facebook Graph API"""
    try:
        print(f'🔍 API Request: Fetching name for PSID: {psid}')
        
        # Find which page this customer belongs to (check conversations)
        conv_result = supabase.table('conversations').select('page_id, conversation_id').eq('customer_psid', psid).limit(1).execute()
        
        if not conv_result.data:
            print(f'⚠️ Customer {psid} not found in conversations')
            return jsonify({'error': 'Customer not found in database'}), 404
        
        page_id = conv_result.data[0]['page_id']
        print(f'📘 Found conversation for page: {page_id}')
        
        page_config = get_page_config(page_id)
        
        if not page_config:
            print(f'❌ Page {page_id} not configured')
            return jsonify({'error': 'Page not configured'}), 400
        
        access_token = page_config.get('accessToken')
        if not access_token:
            print(f'❌ Access token missing for page {page_id}')
            return jsonify({'error': 'Access token missing'}), 400
        
        print(f'🔑 Using access token for page: {page_config.get("name", "Unknown")}')
        
        # Fetch name from Facebook
        name = get_sender_name(psid, access_token)
        
        if name and name != 'Unknown':
            # Update all conversations with this customer
            update_result = supabase.table('conversations').update({
                'customer_name': name,
                'customer_name_fetched': True
            }).eq('customer_psid', psid).execute()
            
            print(f'✅ Updated {len(update_result.data)} conversations with name: {name}')
            return jsonify({'success': True, 'name': name}), 200
        else:
            print(f'⚠️ Could not fetch name from Facebook for {psid}')
            return jsonify({'success': False, 'name': None, 'error': 'Could not fetch name from Facebook'}), 200
            
    except Exception as e:
        print(f'❌ Error in get_customer_name: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# Get unreplied message counts
# ============================================
@app.route('/api/unreplied-counts', methods=['GET'])
def get_unreplied_counts():
    """Get count of unreplied messages per page/customer"""
    try:
        print('📊 Fetching unreplied counts...')
        
        # Try to call the Supabase function first
        try:
            result = supabase.rpc('get_unreplied_counts').execute()
            
            # Format as dictionary: "pageId_psid": count
            counts = {}
            if result.data:
                for row in result.data:
                    key = f"{row['page_id']}_{row['customer_psid']}"
                    counts[key] = row['unreplied_count']
            
            print(f'✅ Unreplied counts (from RPC): {len(counts)} conversations with unreplied messages')
            return jsonify({'success': True, 'counts': counts}), 200
            
        except Exception as rpc_error:
            print(f'⚠️ RPC function failed, using fallback method: {str(rpc_error)}')
            
            # Fallback: calculate manually
            convs = supabase.table('conversations').select('conversation_id, page_id, customer_psid').execute()
            counts = {}
            
            for conv in convs.data:
                # Count unreplied customer messages
                messages = supabase.table('messages').select('id').eq('conversation_id', conv['conversation_id']).eq('sender_type', 'customer').eq('replied', False).execute()
                
                count = len(messages.data)
                if count > 0:
                    key = f"{conv['page_id']}_{conv['customer_psid']}"
                    counts[key] = count
            
            print(f'✅ Unreplied counts (from fallback): {len(counts)} conversations')
            return jsonify({'success': True, 'counts': counts}), 200
        
    except Exception as e:
        print(f'❌ Error in get_unreplied_counts: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Get conversation messages
@app.route('/api/conversation/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """Get all messages for a conversation"""
    try:
        result = supabase.table('messages').select('*').eq('conversation_id', conversation_id).order('created_at').execute()
        return jsonify({'success': True, 'messages': result.data}), 200
    except Exception as e:
        print(f'❌ Error in get_conversation: {str(e)}')
        return jsonify({'error': str(e)}), 500

# Get all active conversations
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get all active conversations"""
    try:
        result = supabase.table('conversations').select('*').eq('status', 'active').order('last_message_time', desc=True).execute()
        return jsonify({'success': True, 'conversations': result.data}), 200
    except Exception as e:
        print(f'❌ Error in get_conversations: {str(e)}')
        return jsonify({'error': str(e)}), 500

# ============================================
# VALIDATE TOKENS ON STARTUP
# ============================================
from config import validate_all_tokens
validate_all_tokens()

if __name__ == '__main__':
    # For local development with Flask dev server
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
