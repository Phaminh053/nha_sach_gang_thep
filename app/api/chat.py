"""
Chat API for AI Chatbot.
Handles communication with Google Gemini API.
"""

import json
import logging
import os
import re

from flask import Blueprint, current_app, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from google import genai
from google.genai import types

from app.api.backend import dispatch_backend_request_data

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GeminiChatbot:
    """Google Gemini chatbot client with lazy initialization."""

    def __init__(self):
        self.gemini_client = None
        self.gemini_available = False
        self.last_error = None
        self.reload_config()

    def reload_config(self):
        """Reload Gemini configuration from environment variables."""
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model_id = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.max_tokens = int(os.environ.get("MAX_TOKENS", 1000))
        self.temperature = float(os.environ.get("TEMPERATURE", 0.7))

    def ensure_client(self):
        """Create the Gemini client lazily so startup does not fail hard."""
        self.reload_config()

        if self.gemini_client and self.gemini_available:
            return True

        if not self.api_key:
            self.last_error = "GEMINI_API_KEY not found in environment variables"
            logger.warning(self.last_error)
            self.gemini_client = None
            self.gemini_available = False
            return False

        try:
            self.gemini_client = genai.Client(api_key=self.api_key)
            self.gemini_available = True
            self.last_error = None
            logger.info("Gemini client initialized for model %s", self.model_id)
            return True
        except Exception as e:
            self.last_error = str(e)
            logger.exception("Gemini client initialization failed for model %s", self.model_id)
            self.gemini_client = None
            self.gemini_available = False
            return False

    def load_system_prompt(self):
        """Load system prompt from file."""
        try:
            prompt_path = os.path.join(os.path.dirname(__file__), "chatbot_prompt.txt")
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.error("Failed to load system prompt: %s", e)
            return "Bạn là trợ lý AI cho website bán sách Nhà sách Gang Thép."

    def extract_backend_request(self, text):
        """Extract BACKEND_REQUEST_JSON from AI response."""
        pattern = r"<<<BACKEND_REQUEST_JSON\s*(.*?)\s*BACKEND_REQUEST_JSON>>>"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                json_str = match.group(1).strip()
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error("Failed to parse backend request JSON: %s", e)
                return None
        return None

    def call_gemini(self, messages):
        """Call Google Gemini API."""
        if not self.ensure_client():
            return (
                "Xin lỗi, hệ thống AI hiện tại không khả dụng. "
                "Vui lòng kiểm tra cấu hình Gemini API hoặc liên hệ quản trị viên."
            )

        try:
            contents = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=msg["content"])],
                    )
                )

            config = types.GenerateContentConfig(
                max_output_tokens=self.max_tokens,
                temperature=self.temperature,
                system_instruction=self.load_system_prompt(),
            )

            response = self.gemini_client.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=config,
            )

            response_text = getattr(response, "text", None)
            if response_text:
                return response_text

            self.last_error = "Gemini response did not contain text content"
            logger.error(
                "Gemini response for model %s did not include text. Raw response type: %s",
                self.model_id,
                type(response).__name__,
            )
            self.gemini_client = None
            self.gemini_available = False
            return (
                "Xin lỗi, hệ thống AI hiện tại không trả về nội dung hợp lệ. "
                "Vui lòng thử lại sau."
            )
        except Exception as e:
            self.last_error = str(e)
            logger.exception("Gemini API call failed for model %s", self.model_id)
            self.gemini_client = None
            self.gemini_available = False
            return (
                "Xin lỗi, tôi gặp sự cố kỹ thuật với hệ thống AI. "
                "Vui lòng thử lại sau hoặc liên hệ với chúng tôi để được hỗ trợ."
            )


chatbot = GeminiChatbot()


def _with_no_cache(response_obj):
    response_obj.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response_obj.headers["Pragma"] = "no-cache"
    response_obj.headers["Expires"] = "0"
    return response_obj


@chat_bp.route("/message", methods=["POST"])
@limiter.limit("10 per minute")
def chat_message():
    """
    Handle chat message from user.
    Expected JSON: {"message": "user message", "conversation_id": "optional"}
    """
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "Message is required"}), 400

        user_message = data["message"].strip()
        if not user_message:
            return jsonify({"error": "Message cannot be empty"}), 400

        logger.info("User message: %s", user_message)

        messages = [{"role": "user", "content": user_message}]

        ai_response = chatbot.call_gemini(messages)
        logger.info("First AI response: %s...", ai_response[:200])

        backend_request = chatbot.extract_backend_request(ai_response)
        if not backend_request:
            logger.info("Direct AI response (no backend): %s...", ai_response[:100])
            return _with_no_cache(
                jsonify({
                    "response": ai_response,
                    "status": "success",
                })
            )

        logger.info("Backend request detected: %s", backend_request)

        try:
            backend_data, backend_status_code = dispatch_backend_request_data(backend_request)
            logger.info("Backend response: %s", backend_data)

            if backend_status_code != 200 or backend_data.get("status") == "error":
                return jsonify({
                    "response": (
                        f"Xin lỗi, {backend_data.get('message', 'không thể truy xuất dữ liệu')}. "
                        "Vui lòng thử lại sau."
                    ),
                    "status": "error",
                })

            if backend_data.get("status") == "not_found":
                return jsonify({
                    "response": f"Không tìm thấy thông tin phù hợp. {backend_data.get('message', '')}",
                    "status": "not_found",
                })

            messages.append({"role": "assistant", "content": ai_response})
            messages.append({
                "role": "user",
                "content": f"BACKEND_RESPONSE_JSON: {json.dumps(backend_data, ensure_ascii=False)}",
            })

            final_response = chatbot.call_gemini(messages)
            logger.info("Final AI response: %s...", final_response[:200])

            return _with_no_cache(
                jsonify({
                    "response": final_response,
                    "status": "success",
                })
            )
        except Exception:
            logger.exception("Backend dispatch integration failed")
            return jsonify({
                "response": "Xin lỗi, tôi gặp sự cố khi truy xuất dữ liệu. Vui lòng thử lại sau.",
                "status": "error",
            })

    except Exception as e:
        logger.exception("Chat endpoint error")
        payload = {
            "response": (
                "Xin lỗi, tôi gặp sự cố kỹ thuật. "
                "Vui lòng thử lại sau hoặc liên hệ với chúng tôi để được hỗ trợ."
            ),
            "status": "error",
        }
        if current_app.debug:
            payload["details"] = str(e)
        return jsonify(payload), 500


@chat_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    chatbot.reload_config()
    return jsonify({
        "status": "healthy" if chatbot.gemini_available else "unhealthy",
        "service": "chatbot",
        "configured": bool(chatbot.api_key),
        "model_id": chatbot.model_id,
        "gemini_available": chatbot.gemini_available,
        "last_error": chatbot.last_error,
        "message": (
            f"Google Gemini API ({chatbot.model_id}) service"
            if chatbot.gemini_available
            else "Gemini API not available - check configuration"
        ),
    })


@chat_bp.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "response": "Bạn đã gửi quá nhiều tin nhắn. Vui lòng chờ một chút rồi thử lại.",
        "status": "rate_limited",
    }), 429


@chat_bp.errorhandler(400)
def bad_request_handler(e):
    return jsonify({
        "response": "Tin nhắn không hợp lệ. Vui lòng thử lại.",
        "status": "error",
    }), 400


@chat_bp.errorhandler(500)
def internal_error_handler(e):
    return jsonify({
        "response": "Xin lỗi, tôi gặp sự cố kỹ thuật. Vui lòng thử lại sau.",
        "status": "error",
    }), 500
