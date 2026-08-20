def CloudClient(
    tenant: Optional[str] = None,
    database: Optional[str] = None,
    api_key: Optional[str] = None,
    settings: Optional[Settings] = None,
    *,  # Following arguments are keyword-only, intended for testing only.
    cloud_host: str = "api.trychroma.com",
    cloud_port: int = 443,
    enable_ssl: bool = True,
) -> ClientAPI:
    """Create a client for Chroma Cloud.

    If not provided, `tenant`, `database`, and `api_key` will be inferred from the environment variables `CHROMA_TENANT`, `CHROMA_DATABASE`, and `CHROMA_API_KEY`.

    Args:
        tenant: Tenant name to use, or None to infer from credentials.
        database: Database name to use, or None to infer from credentials.
        api_key: API key for Chroma Cloud.
        settings: Optional settings to override defaults.

    Returns:
        ClientAPI: A configured client instance.

    Raises:
        ValueError: If no API key is provided or available in the environment.
    """

    required_args = [
        CloudClientArg(name="api_key", env_var="CHROMA_API_KEY", value=api_key),
    ]

    # If api_key is not provided, try to load it from the environment variable
    if not all([arg.value for arg in required_args]):
        for arg in required_args:
            arg.value = arg.value or os.environ.get(arg.env_var)

    missing_args = [arg for arg in required_args if arg.value is None]
    if missing_args:
        raise ValueError(
            f"Missing required arguments: {', '.join([arg.name for arg in missing_args])}. "
            f"Please provide them or set the environment variables: {', '.join([arg.env_var for arg in missing_args])}"
        )

    if settings is None:
        settings = Settings()

    # Make sure paramaters are the correct types -- users can pass anything.
    tenant = tenant or os.environ.get("CHROMA_TENANT")
    if tenant is not None:
        tenant = str(tenant)
    database = database or os.environ.get("CHROMA_DATABASE")
    if database is not None:
        database = str(database)
    api_key = str(api_key)
    cloud_host = str(cloud_host)
    cloud_port = int(cloud_port)
    enable_ssl = bool(enable_ssl)

    settings.chroma_api_impl = "chromadb.api.fastapi.FastAPI"
    settings.chroma_server_host = cloud_host
    settings.chroma_server_http_port = cloud_port
    settings.chroma_server_ssl_enabled = enable_ssl

    settings.chroma_client_auth_provider = (
        "chromadb.auth.token_authn.TokenAuthClientProvider"
    )
    settings.chroma_client_auth_credentials = api_key
    settings.chroma_auth_token_transport_header = TokenTransportHeader.X_CHROMA_TOKEN
    settings.chroma_overwrite_singleton_tenant_database_access_from_auth = True

    return ClientCreator(tenant=tenant, database=database, settings=settings)
