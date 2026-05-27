def assert_tls(
    *, ca_cert: str, client_cert: str, client_key: str, service: str
) -> tuple[str, str, str]:
    """Validate required TLS file paths and return them unchanged."""
    if not ca_cert or not client_cert or not client_key:
        raise ValueError(
            f"{service}: TLS requires CA cert, client cert, and client key"
        )
    return ca_cert, client_cert, client_key
