"""Verified HTTPS policy shared by attended recovery tools."""

import os
import ssl


def client_context():
    """Use platform trust and optionally require the stronger host profile.

    Level 3 rejects marginal RSA key lengths that level 2 can round up. It
    requires RSA/DH >=3072 bits and EC >=256 bits and may reject legacy peers.
    The environment setting can strengthen, but never lower, platform policy.
    """
    value = os.environ.get("SLZB_TLS_SECURITY_LEVEL", "2")
    if value not in ("2", "3"):
        raise ValueError("SLZB_TLS_SECURITY_LEVEL must be 2 or 3")
    context = ssl.create_default_context()
    context.minimum_version = max(context.minimum_version, ssl.TLSVersion.TLSv1_2)
    level = max(int(value), context.security_level)
    if context.security_level < level:
        suites = ":".join(cipher["name"] for cipher in context.get_ciphers()
                          if cipher["protocol"] != "TLSv1.3")
        context.set_ciphers(f"{suites}:@SECLEVEL={level}")
    return context
