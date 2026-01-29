"""Exception classes for Vagrant."""


class VagrantError(Exception):
    """Base exception for all Vagrant errors.
    
    All Vagrant-specific exceptions inherit from this class,
    making it easy to catch any Vagrant error.
    """

    def __init__(self, message: str, details: str | None = None) -> None:
        """Initialize error with message and optional details.
        
        Args:
            message: Human-readable error message.
            details: Additional context or debugging information.
        """
        self.message = message
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        """Return string representation."""
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message

    def __repr__(self) -> str:
        """Return detailed representation."""
        return f"{self.__class__.__name__}({self.message!r}, details={self.details!r})"


class SpecParseError(VagrantError):
    """Failed to parse API specification.
    
    Raised when an OpenAPI spec is malformed, missing required fields,
    or otherwise cannot be parsed into a valid ApiSpec.
    """

    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        line: int | None = None,
    ) -> None:
        """Initialize parse error.
        
        Args:
            message: Description of the parse error.
            file_path: Path to the spec file, if known.
            line: Line number where error occurred, if known.
        """
        self.file_path = file_path
        self.line = line

        details = None
        if file_path:
            details = f"in {file_path}"
            if line:
                details += f" at line {line}"

        super().__init__(message, details)


class NetworkError(VagrantError):
    """Network request failed.
    
    Raised when an HTTP request fails due to network issues
    (connection refused, timeout, DNS failure, etc.).
    """

    def __init__(
        self,
        message: str,
        url: str | None = None,
        status_code: int | None = None,
    ) -> None:
        """Initialize network error.
        
        Args:
            message: Description of the network error.
            url: URL that was being requested.
            status_code: HTTP status code, if request completed.
        """
        self.url = url
        self.status_code = status_code

        details = None
        if url:
            details = f"url={url}"
            if status_code:
                details += f", status={status_code}"

        super().__init__(message, details)


class AuthError(VagrantError):
    """Authentication failed.
    
    Raised when authentication is rejected by the server
    or when auth configuration is invalid.
    """

    def __init__(
        self,
        message: str,
        auth_type: str | None = None,
    ) -> None:
        """Initialize auth error.
        
        Args:
            message: Description of the auth error.
            auth_type: Type of authentication that failed.
        """
        self.auth_type = auth_type

        details = f"auth_type={auth_type}" if auth_type else None
        super().__init__(message, details)


class ConfigError(VagrantError):
    """Configuration error.
    
    Raised when configuration is invalid or cannot be loaded.
    """

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
    ) -> None:
        """Initialize config error.
        
        Args:
            message: Description of the config error.
            config_key: Configuration key that caused the error.
        """
        self.config_key = config_key

        details = f"key={config_key}" if config_key else None
        super().__init__(message, details)
