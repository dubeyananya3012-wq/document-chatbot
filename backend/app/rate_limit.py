"""
Rate limiting, backed by slowapi (in-memory, per-process - sufficient
for a single free-tier Render instance; a multi-instance deployment
would need a shared backend like Redis instead).

Keyed by client IP rather than by user_id. Keying by an unverified
claim inside the JWT would let an attacker spread requests across
forged "identities" to dodge the limit; IP is a more robust anti-abuse
key for this purpose even though it can be shared behind NAT.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
