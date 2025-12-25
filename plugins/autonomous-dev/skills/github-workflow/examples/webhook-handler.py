"""GitHub Webhook Handler with HMAC Signature Verification.

This module demonstrates secure webhook handling with:
- HMAC SHA-256 signature verification
- Event routing
- Error handling
- Security logging

Security:
- Always verify webhook signatures (CWE-345: Insufficient Verification)
- Use constant-time comparison (prevents timing attacks)
- Never log secrets or signatures
- Validate all inputs

Example:
    from flask import Flask, request
    from webhook_handler import WebhookHandler

    app = Flask(__name__)
    handler = WebhookHandler(secret=os.environ['GITHUB_WEBHOOK_SECRET'])

    @app.route('/webhook', methods=['POST'])
    def webhook():
        return handler.handle_request(request)
"""

import hmac
import hashlib
import logging
from typing import Dict, Any, Callable

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Secure GitHub webhook handler with signature verification.

    Attributes:
        secret: Webhook secret from GitHub settings
        event_handlers: Dict mapping event types to handler functions
    """

    def __init__(self, secret: str):
        """Initialize webhook handler.

        Args:
            secret: Webhook secret configured in GitHub settings

        Raises:
            ValueError: If secret is empty or None
        """
        if not secret:
            raise ValueError("Webhook secret cannot be empty")

        self.secret = secret
        self.event_handlers: Dict[str, Callable] = {}

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature using HMAC SHA-256.

        This method prevents unauthorized webhook requests by verifying
        the X-Hub-Signature-256 header against the payload.

        Args:
            payload: Raw request body (bytes)
            signature: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid, False otherwise

        Security:
            - Uses constant-time comparison (prevents timing attacks)
            - Validates signature format before comparison
            - Never logs secret or signature values

        Example:
            >>> handler = WebhookHandler(secret="my-secret")
            >>> payload = b'{"action": "opened"}'
            >>> signature = "sha256=abc123..."
            >>> handler.verify_signature(payload, signature)
            True
        """
        if not signature or not signature.startswith('sha256='):
            logger.warning("Invalid signature format")
            return False

        # Extract signature hash (remove 'sha256=' prefix)
        expected_signature = signature[7:]

        # Compute HMAC using webhook secret
        mac = hmac.new(
            self.secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        )
        computed_signature = mac.hexdigest()

        # Constant-time comparison prevents timing attacks
        is_valid = hmac.compare_digest(computed_signature, expected_signature)

        if not is_valid:
            logger.warning("Webhook signature verification failed")

        return is_valid

    def register_handler(self, event: str, handler: Callable):
        """Register event handler function.

        Args:
            event: GitHub event type (e.g., 'push', 'pull_request')
            handler: Function to handle event (receives event data dict)

        Example:
            >>> def handle_push(data):
            ...     print(f"Push to {data['repository']['name']}")
            >>> handler.register_handler('push', handle_push)
        """
        self.event_handlers[event] = handler
        logger.info(f"Registered handler for '{event}' event")

    def handle_request(self, request) -> tuple:
        """Handle incoming webhook request.

        This is the main entry point for webhook processing. It:
        1. Verifies the webhook signature
        2. Extracts event type and payload
        3. Routes to appropriate event handler

        Args:
            request: Flask/Django request object with:
                - headers: Dict containing X-Hub-Signature-256, X-GitHub-Event
                - get_data(): Returns raw request body
                - get_json(): Returns parsed JSON payload

        Returns:
            Tuple of (response_dict, status_code)

        Example:
            >>> @app.route('/webhook', methods=['POST'])
            ... def webhook():
            ...     return handler.handle_request(request)
        """
        # Extract signature header
        signature = request.headers.get('X-Hub-Signature-256')
        if not signature:
            logger.warning("Missing X-Hub-Signature-256 header")
            return {'error': 'Missing signature header'}, 401

        # Get raw payload for signature verification
        payload = request.get_data()

        # Verify signature
        if not self.verify_signature(payload, signature):
            logger.warning("Webhook signature verification failed")
            return {'error': 'Invalid signature'}, 401

        # Extract event type
        event = request.headers.get('X-GitHub-Event')
        if not event:
            logger.warning("Missing X-GitHub-Event header")
            return {'error': 'Missing event header'}, 400

        # Parse JSON payload
        try:
            data = request.get_json()
        except Exception as e:
            logger.error(f"Failed to parse JSON payload: {e}")
            return {'error': 'Invalid JSON payload'}, 400

        # Route to event handler
        if event in self.event_handlers:
            try:
                self.event_handlers[event](data)
                logger.info(f"Successfully handled '{event}' event")
                return {'status': 'success', 'event': event}, 200
            except Exception as e:
                logger.error(f"Error handling '{event}' event: {e}")
                return {'error': 'Handler failed', 'event': event}, 500
        else:
            logger.info(f"No handler registered for '{event}' event")
            return {'status': 'ignored', 'event': event}, 200


# Example event handlers

def handle_push(data: Dict[str, Any]):
    """Handle push event.

    Args:
        data: Webhook payload containing push information
    """
    repository = data['repository']['name']
    ref = data['ref']
    commits = len(data['commits'])

    logger.info(f"Push to {repository} on {ref}: {commits} commits")

    # Example: Trigger CI/CD pipeline
    # deploy_pipeline.trigger(repository, ref)


def handle_pull_request(data: Dict[str, Any]):
    """Handle pull request event.

    Args:
        data: Webhook payload containing PR information
    """
    action = data['action']
    pr_number = data['pull_request']['number']
    repository = data['repository']['name']

    logger.info(f"PR #{pr_number} {action} in {repository}")

    # Example: Auto-label PR
    # if action == 'opened':
    #     apply_labels(pr_number)


def handle_issues(data: Dict[str, Any]):
    """Handle issue event.

    Args:
        data: Webhook payload containing issue information
    """
    action = data['action']
    issue_number = data['issue']['number']
    repository = data['repository']['name']

    logger.info(f"Issue #{issue_number} {action} in {repository}")

    # Example: Auto-assign issue
    # if action == 'opened':
    #     assign_issue(issue_number)


# Flask application example

def create_app():
    """Create Flask application with webhook endpoint."""
    from flask import Flask, request
    import os

    app = Flask(__name__)

    # Initialize webhook handler
    webhook_secret = os.environ.get('GITHUB_WEBHOOK_SECRET')
    if not webhook_secret:
        raise ValueError("GITHUB_WEBHOOK_SECRET environment variable not set")

    handler = WebhookHandler(secret=webhook_secret)

    # Register event handlers
    handler.register_handler('push', handle_push)
    handler.register_handler('pull_request', handle_pull_request)
    handler.register_handler('issues', handle_issues)

    @app.route('/webhook', methods=['POST'])
    def webhook():
        """Webhook endpoint."""
        return handler.handle_request(request)

    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint."""
        return {'status': 'healthy'}, 200

    return app


if __name__ == '__main__':
    import os

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create and run app
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
