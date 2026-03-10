# pipeline/nova.py
"""
Nova client factory + invoke wrapper.
- Reads all config from settings (no hardcoded keys anywhere)
- Returns typed text output or raises NovaInvokeError
- Extended thinking is opt-in per call
"""

from __future__ import annotations

import json
import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from config import settings

logger = logging.getLogger(__name__)


class NovaInvokeError(Exception):
    """Raised when Bedrock returns no usable text block."""


def get_nova_client():
    """
    Build a boto3 bedrock-runtime client from settings.
    Called once per node invocation — boto3 handles connection pooling internally.
    """
    kwargs = {
        "service_name": "bedrock-runtime",
        "region_name":  settings.aws_region,
    }
    # Only pass explicit keys if provided — allows IAM role auth in prod
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"]     = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

    return boto3.client(**kwargs)


def invoke_nova(
    client,
    system_prompt: str,
    user_prompt: str,
    use_extended_thinking: bool = False,
) -> str:
    """
    Call Amazon Nova via the Bedrock converse API.

    Args:
        client:                 boto3 bedrock-runtime client
        system_prompt:          System instruction for the model
        user_prompt:            User turn content
        use_extended_thinking:  Enable Nova's reasoning mode (uses more tokens)

    Returns:
        Raw text string from the first text block in the response.

    Raises:
        NovaInvokeError:  If no text block is found in the response.
        ClientError:      Propagated from boto3 on auth / throttle failures.
    """
    body: dict = {
        "modelId":  settings.nova_model_id,
        "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
        "system":   [{"text": system_prompt}],
        "inferenceConfig": {
            "maxTokens":   settings.nova_max_tokens,
            "temperature": settings.nova_temperature,
        },
    }

    if use_extended_thinking:
        body["additionalModelRequestFields"] = {
            "reasoningConfig": {
                "type":               "enabled",
                "maxReasoningEffort": settings.nova_thinking_effort,
            }
        }
        # Temperature must be omitted when extended thinking is enabled
        del body["inferenceConfig"]["temperature"]
        body["inferenceConfig"]["maxTokens"] = settings.nova_thinking_max_tokens

    mode = "extended-thinking" if use_extended_thinking else "standard"
    logger.info("Invoking Nova [%s] model=%s", mode, settings.nova_model_id)

    try:
        response = client.converse(**body)
    except (BotoCoreError, ClientError) as exc:
        logger.error("Bedrock API error: %s", exc)
        raise

    # Extract first text block from response
    content_blocks = response.get("output", {}).get("message", {}).get("content", [])
    for block in content_blocks:
        if "text" in block:
            text = block["text"]
            logger.info("Nova response received (%d chars)", len(text))
            logger.debug("Nova response preview: %.300s", text)
            return text

    logger.error("Nova returned no text block. Raw blocks: %s", content_blocks)
    raise NovaInvokeError(
        f"Nova returned no text block for model {settings.nova_model_id}. "
        f"Got {len(content_blocks)} block(s): {[list(b.keys()) for b in content_blocks]}"
    )


def invoke_nova_json(
    client,
    system_prompt: str,
    user_prompt: str,
    use_extended_thinking: bool = False,
) -> dict:
    """
    Convenience wrapper — calls invoke_nova and parses JSON automatically.
    Strips markdown fences before parsing so Nova's formatting quirks don't break things.

    Returns:
        Parsed dict from Nova's JSON response.

    Raises:
        NovaInvokeError:   If no text block returned.
        json.JSONDecodeError: If the response isn't valid JSON after stripping fences.
    """
    raw = invoke_nova(client, system_prompt, user_prompt, use_extended_thinking)
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    try:
        from json_repair import repair_json
        return json.loads(repair_json(cleaned))
    except Exception as exc:
        logger.error("Failed to parse Nova JSON response. Full response: %s", cleaned)
        raise json.JSONDecodeError(f"Nova returned invalid JSON: {exc}", cleaned, 0) from exc