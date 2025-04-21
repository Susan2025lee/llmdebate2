from flask import Flask, render_template, request, Response, stream_with_context, jsonify
import asyncio
import os
import json
from typing import Any, Optional, Callable
from queue import Queue
from threading import Thread
from dotenv import load_dotenv
from flask_socketio import SocketIO, emit
import logging

# Import the core debate logic functions with aliases
from debate_v3 import run_debate_logic as run_debate_logic_v3
from debate_v4 import run_debate_logic as run_debate_logic_v4

# Global reference to the human feedback queue for the current debate
# feedback_queue: Optional[Queue] = None # No longer needed with Socket.IO

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading') # Use threading for background tasks

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Remove the entire /debate SSE endpoint (lines 32-133 in original file)
# @app.route('/debate', methods=['GET'])
# def debate_stream():
#    ...
#    return resp

# Remove the /debate/feedback endpoint (lines 135-141 in original file)
# @app.route('/debate/feedback', methods=['GET'])
# def debate_feedback():
#    ...
#    return ('No active debate', 400)

@app.route('/start_debate', methods=['POST'])
def start_debate_route():
    data = request.get_json()
    question = data.get('question')
    version = data.get('version', 'v3') # Default to v3 if not specified
    synthesizer_type = data.get('synthesizer_type') # Get synthesizer choice for V4

    if not question:
        return jsonify({'error': 'Question is required'}), 400

    # Define the progress callback using SocketIO
    def progress_callback(update_type, data):
        # Ensure data is JSON serializable, handle potential errors
        try:
            # Attempt to serialize complex objects if needed, or just pass strings
            serializable_data = data 
            if not isinstance(data, (str, int, float, bool, list, dict, type(None))):
                 # Basic attempt to convert unknown types to string
                 serializable_data = str(data)
            socketio.emit(update_type, serializable_data)
        except Exception as e:
            logging.error(f"Error emitting Socket.IO event '{update_type}': {e}. Data: {data}", exc_info=True)
            # Emit an error back to the client if possible
            try:
                socketio.emit('error', {'error': f'Internal error during event emission: {e}'})    
            except: 
                pass # Avoid recursive errors

    # Select the correct debate logic based on version
    debate_function = None
    # Remove V1/V2 options if they are not intended for the web UI
    # if version == 'v1':
    #    debate_function = run_debate_v1 # Needs import if re-enabled
    # elif version == 'v2':
    #    debate_function = run_debate_v2 # Needs import if re-enabled
    if version == 'v3':
        debate_function = run_debate_logic_v3
    elif version == 'v4':
        debate_function = run_debate_logic_v4
    else:
        return jsonify({'error': 'Invalid version specified'}), 400

    # Run the selected debate logic in a background thread
    def run_in_background():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Prepare arguments, adding synthesizer_type for V4
            args = {
                'question': question, 
                # Use env vars or defaults for web UI config
                'max_rounds': int(os.getenv('WEB_MAX_ROUNDS', '1' if version == 'v4' else '3')), 
                'output': None, 
                'verbose': False, 
                'progress_callback': progress_callback,
                 # Add V3 specific args if needed
                # 'top_k': int(os.getenv('WEB_TOP_K', '5')) if version == 'v3' else None, 
                 # Remove human feedback callback if not used via web
                 # 'human_feedback_callback': None 
            }
            
            # Filter out None args if the function doesn't expect them
            # args = {k: v for k, v in args.items() if v is not None}
            
            if version == 'v4':
                args['synthesizer_choice'] = synthesizer_type
            
            # Run the async function
            loop.run_until_complete(debate_function(**args))
            # Signal completion via Socket.IO
            progress_callback('complete', 'Debate process completed.')
        except Exception as e:
            logging.error(f"Error running debate in background: {e}", exc_info=True)
            # Ensure error is emitted via the Socket.IO callback
            progress_callback('error', f'Debate failed: {e}') 
        finally:
            loop.close()

    thread = Thread(target=run_in_background)
    thread.start()

    return jsonify({'message': f'Debate {version} started for question: {question}'}), 200

if __name__ == '__main__':
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true','1','t')
    # Use socketio.run for proper Socket.IO integration
    socketio.run(app, host=host, port=port, debug=debug) 
    # app.run(host=host, port=port, debug=debug) # Original Flask run 