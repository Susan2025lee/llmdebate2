from flask import Flask, render_template, request, Response, stream_with_context
import asyncio
import os
import json
from typing import Any, Optional, Callable
from queue import Queue
from threading import Thread
from dotenv import load_dotenv

# Import the core debate logic function
from debate_v3 import run_debate_logic

# Global reference to the human feedback queue for the current debate
feedback_queue: Optional[Queue] = None

load_dotenv()

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/debate', methods=['GET'])
def debate_stream():
    """Streams debate progress via Server-Sent Events (SSE)."""
    question = request.args.get('question')
    if not question:
        # Immediately return an error event
        def err():
            data = json.dumps({'error': 'No question provided.'})
            yield f"event: error\ndata: {data}\n\n"
        return Response(err(), mimetype='text/event-stream')

    q: Queue = Queue()
    # Expose the human feedback queue so the /debate/feedback route can use it
    global feedback_queue
    feedback_queue = Queue()

    def web_progress_callback(update_type: str, data: Any):
        try:
            payload = json.dumps(data)
        except Exception:
            payload = json.dumps({'error': str(data)})
        q.put(f"event: {update_type}\ndata: {payload}\n\n")

    def web_feedback_callback() -> str:
        # Signal browser to ask for feedback
        q.put(f"event: feedback_request\ndata: {json.dumps('Press Enter to continue or type feedback')}\n\n")
        # Wait for user feedback from the separate HTTP endpoint
        fb = feedback_queue.get()
        return fb

    def run_logic():
        try:
            q.put(f"event: status\ndata: {json.dumps('Starting debate process...')}\n\n")
            result = asyncio.run(run_debate_logic(
                question=question,
                top_k=int(os.getenv('WEB_TOP_K', '5')),
                max_rounds=int(os.getenv('WEB_MAX_ROUNDS', '3')),
                output=None,
                verbose=False,
                progress_callback=web_progress_callback,
                human_feedback_callback=web_feedback_callback
            ))
            if isinstance(result, str) and result.startswith('Error:'):
                q.put(f"event: error\ndata: {json.dumps({'error': result})}\n\n")
            else:
                q.put(f"event: final_answer\ndata: {json.dumps(result)}\n\n")
                q.put(f"event: complete\ndata: {json.dumps('Debate finished')}\n\n")
        except Exception as e:
            app.logger.error(f"Exception in debate logic thread: {e}", exc_info=True)
            err = json.dumps({'error': str(e)})
            q.put(f"event: error\ndata: {err}\n\n")
        finally:
            q.put(None)

    # start background thread to not block
    thread = Thread(target=run_logic)
    thread.daemon = True
    thread.start()

    @stream_with_context
    def event_stream():
        while True:
            msg = q.get()
            if msg is None:
                break
            yield msg

    resp = Response(event_stream(), mimetype='text/event-stream')
    # Disable caching and buffering for SSE
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp

@app.route('/debate/feedback', methods=['GET'])
def debate_feedback():
    """Endpoint that the browser calls to submit human feedback."""
    fb = request.args.get('feedback', '')
    if feedback_queue:
        feedback_queue.put(fb)
        return ('', 204)
    return ('No active debate', 400)

if __name__ == '__main__':
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true','1','t')
    app.run(host=host, port=port, debug=debug) 