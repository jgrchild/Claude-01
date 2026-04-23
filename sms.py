import logging

from twilio.rest import Client

import config

log = logging.getLogger(__name__)
_client = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    return _client


def send_sms(to: str, body: str) -> str:
    client = _get_client()
    message = client.messages.create(
        body=body,
        from_=config.TWILIO_PHONE_NUMBER,
        to=to,
    )
    log.info("Sent SMS to %s – sid=%s", to, message.sid)
    return message.sid
