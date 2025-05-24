from flask import Flask, request, jsonify
from flask_cors import CORS
from database import Database
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize database
db = Database()

@app.route('/check-subscription', methods=['POST'])
def check_subscription():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400
        
        # Check if user has active subscription
        has_access = db.is_subscription_active(user_id)
        
        return jsonify({
            'hasAccess': has_access,
            'userId': user_id
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 