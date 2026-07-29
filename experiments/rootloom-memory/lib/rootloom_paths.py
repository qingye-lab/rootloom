"""Shared repository-path, secret-material, and security-domain policy."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
import stat


SENSITIVE_MATERIAL_EXACT_NAMES = {
    ".env",
    ".envrc",
    ".git-credentials",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "decryption-key.pem",
    "ec-key.pem",
    "ecdsa-key.pem",
    "ed25519-key.pem",
    "encryption-key.pem",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "kubeconfig",
    "privatekey.pem",
    "privkey.pem",
    "rsa-key.pem",
    "service-account.json",
    "secrets.yaml",
    "secrets.yml",
}
MAX_REVIEWABLE_PATHS = 64
PUBLIC_CERTIFICATE_SUFFIXES = {
    ".cer",
    ".crt",
    ".p7b",
    ".p7c",
}
STRONG_SENSITIVE_MATERIAL_SUFFIXES = {
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pfx",
    ".ppk",
}
AMBIGUOUS_SENSITIVE_MATERIAL_SUFFIXES = {".der", ".pem"}
SENSITIVE_MATERIAL_SUFFIXES = (
    STRONG_SENSITIVE_MATERIAL_SUFFIXES | AMBIGUOUS_SENSITIVE_MATERIAL_SUFFIXES
)
REVIEWABLE_ENV_TEMPLATE_NAMES = {
    ".env.dist",
    ".env.example",
    ".env.sample",
    ".env.template",
}
SENSITIVE_MATERIAL_CONFIG_SUFFIXES = {
    ".cfg",
    ".conf",
    ".ini",
    ".json",
    ".properties",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
SENSITIVE_MATERIAL_WORDS = {
    "certificate",
    "credential",
    "credentials",
    "keystore",
    "secret",
    "secrets",
    "token",
    "tokens",
}
STRONG_SENSITIVE_MATERIAL_WORDS = {
    "credential",
    "credentials",
    "keystore",
    "private",
    "secret",
    "secrets",
    "token",
    "tokens",
}
SECURITY_DOMAIN_DESCRIPTOR_WORDS = {
    "controller",
    "example",
    "fixture",
    "handler",
    "interface",
    "manager",
    "model",
    "parser",
    "policy",
    "provider",
    "sample",
    "schema",
    "service",
    "spec",
    "test",
    "tests",
    "type",
    "types",
    "validator",
}
SENSITIVE_MATERIAL_CONTEXTS = (
    frozenset({"client", "secret"}),
    frozenset({"api", "secret"}),
    frozenset({"app", "secret"}),
    frozenset({"api", "token"}),
    frozenset({"access", "token"}),
    frozenset({"refresh", "token"}),
    frozenset({"auth", "token"}),
    frozenset({"bearer", "token"}),
    frozenset({"session", "token"}),
    frozenset({"id", "token"}),
    frozenset({"client", "credentials"}),
    frozenset({"database", "credentials"}),
    frozenset({"db", "credentials"}),
    frozenset({"aws", "credentials"}),
    frozenset({"cloud", "credentials"}),
    frozenset({"gcp", "credentials"}),
    frozenset({"google", "credentials"}),
    frozenset({"azure", "credentials"}),
    frozenset({"service", "account"}),
    frozenset({"private", "key"}),
    frozenset({"api", "key"}),
    frozenset({"access", "key"}),
    frozenset({"tls", "key"}),
    frozenset({"signing", "key"}),
    frozenset({"client", "certificate"}),
    frozenset({"server", "certificate"}),
    frozenset({"tls", "certificate"}),
    frozenset({"client", "keystore"}),
    frozenset({"server", "keystore"}),
    frozenset({"app", "keystore"}),
)
AMBIGUOUS_STRONG_KEY_CONTEXTS = (
    frozenset({"client", "key"}),
    frozenset({"server", "key"}),
    frozenset({"host", "key"}),
    frozenset({"ssh", "key"}),
    frozenset({"identity", "key"}),
)
SENSITIVE_MATERIAL_ENVIRONMENTS = {
    "dev",
    "development",
    "local",
    "prod",
    "production",
    "stage",
    "staging",
    "test",
    "testing",
}
SENSITIVE_MATERIAL_DIRECTORIES = {
    ".credentials",
    ".private-keys",
    ".private_keys",
    ".secrets",
    "keystores",
    "private-keys",
    "private_keys",
    "private-secrets",
    "private_secrets",
}
ROOT_SENSITIVE_MATERIAL_DIRECTORIES = {"credentials", "secrets"}
SOURCE_CODE_SUFFIXES = {
    ".asm",
    ".bash",
    ".c",
    ".cc",
    ".clj",
    ".cljs",
    ".cpp",
    ".cs",
    ".dart",
    ".ex",
    ".exs",
    ".fish",
    ".fs",
    ".fsx",
    ".go",
    ".groovy",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".m",
    ".mm",
    ".pl",
    ".pm",
    ".php",
    ".ps1",
    ".py",
    ".r",
    ".rb",
    ".rs",
    ".scala",
    ".sh",
    ".sql",
    ".svelte",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
    ".zsh",
}
SECURITY_DOMAIN_WORDS = {
    "auth",
    "authentication",
    "authorization",
    "cert",
    "certs",
    "certificate",
    "certificates",
    "credential",
    "credentials",
    "crypto",
    "jwt",
    "keystore",
    "keystores",
    "oauth",
    "oidc",
    "permission",
    "permissions",
    "secret",
    "secrets",
    "security",
    "token",
    "tokens",
}
PROTECTED_STATE_WORDS = {"database", "databases", "db", "migration", "migrations"}
PROTECTED_STATE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
WORD_SPLIT = re.compile(r"[._-]+")
CAMEL_ACRONYM_BOUNDARY = re.compile(r"([A-Z]+)([A-Z][a-z])")
CAMEL_LOWER_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")


def normalize_repo_path(raw: str, *, label: str = "path") -> str:
    value = raw.strip().replace("\\", "/")
    parsed = PurePosixPath(value)
    if (
        not value
        or parsed.is_absolute()
        or any(part in {"", ".", ".."} for part in parsed.parts)
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(
            f"{label} must be a normalized repository-relative path: {raw!r}"
        )
    return parsed.as_posix()


def validate_git_repo_path(raw: str, *, label: str = "Git path") -> str:
    """Validate a Git-reported path without changing its byte-level meaning."""

    if raw != raw.strip() or "\\" in raw:
        raise ValueError(
            f"{label} cannot be represented safely without changing the path: {raw!r}"
        )
    normalized = normalize_repo_path(raw, label=label)
    if normalized != raw:
        raise ValueError(f"{label} is not a canonical repository path: {raw!r}")
    return normalized


def path_words(path: str) -> set[str]:
    words: set[str] = set()
    for part in PurePosixPath(path).parts:
        words.add(part.lower())
        for segment in WORD_SPLIT.split(part):
            if not segment:
                continue
            separated = CAMEL_ACRONYM_BOUNDARY.sub(r"\1 \2", segment)
            separated = CAMEL_LOWER_BOUNDARY.sub(r"\1 \2", separated)
            words.update(word.lower() for word in separated.split() if word)
    return words


def _matches_declared_root(lowered: str, raw_roots: set[str] | None) -> bool:
    if not raw_roots:
        return False
    for raw_root in raw_roots:
        root = normalize_repo_path(raw_root, label="sensitive path").casefold()
        if lowered == root or lowered.startswith(root + "/"):
            return True
    return False


def _is_environment_material_name(name: str) -> bool:
    lowered = name.casefold()
    return lowered in {".env", ".envrc"} or (
        lowered.startswith(".env.")
        and lowered not in REVIEWABLE_ENV_TEMPLATE_NAMES
    )


def _material_policy(normalized: str) -> tuple[bool, bool]:
    """Return (material, strong) for the built-in path-only policy."""

    lowered = normalized.casefold()
    parts = PurePosixPath(lowered).parts
    explicit_material_root = parts[0] in (
        SENSITIVE_MATERIAL_DIRECTORIES | ROOT_SENSITIVE_MATERIAL_DIRECTORIES
    )
    source_like = (
        PurePosixPath(lowered).suffix in SOURCE_CODE_SUFFIXES
        and not explicit_material_root
    )
    if any(
        part in SENSITIVE_MATERIAL_EXACT_NAMES
        or _is_environment_material_name(part)
        or PurePosixPath(part).suffix in STRONG_SENSITIVE_MATERIAL_SUFFIXES
        for part in parts
    ):
        return True, True
    ambiguous_suffix = any(
        PurePosixPath(part).suffix in AMBIGUOUS_SENSITIVE_MATERIAL_SUFFIXES
        for part in parts
    )
    for part in parts[:-1]:
        if part in SENSITIVE_MATERIAL_DIRECTORIES and (
            part.startswith(".") or not source_like
        ):
            return True, True
        if part in ROOT_SENSITIVE_MATERIAL_DIRECTORIES and not source_like:
            return True, True
    name = PurePosixPath(normalized).name
    name_words = path_words(name)
    suffix = PurePosixPath(name).suffix.casefold()
    config_like = suffix in SENSITIVE_MATERIAL_CONFIG_SUFFIXES or not suffix
    stem = PurePosixPath(name).stem.casefold()
    domain_descriptor = bool(name_words & SECURITY_DOMAIN_DESCRIPTOR_WORDS)
    strong_named_material = bool(
        name_words & STRONG_SENSITIVE_MATERIAL_WORDS
    ) or any(
        context.issubset(name_words) and "certificate" not in context
        for context in SENSITIVE_MATERIAL_CONTEXTS
    ) or (
        ambiguous_suffix
        and any(context.issubset(name_words) for context in AMBIGUOUS_STRONG_KEY_CONTEXTS)
    )
    if ambiguous_suffix and (
        stem in SENSITIVE_MATERIAL_EXACT_NAMES or stem == "key"
    ):
        return True, True
    if (
        suffix
        in (PUBLIC_CERTIFICATE_SUFFIXES | AMBIGUOUS_SENSITIVE_MATERIAL_SUFFIXES)
        and not domain_descriptor
        and strong_named_material
    ):
        return True, True
    if config_like and stem in SENSITIVE_MATERIAL_WORDS:
        return True, True
    if config_like and any(
        context.issubset(name_words)
        and not ((name_words - context) & SECURITY_DOMAIN_DESCRIPTOR_WORDS)
        for context in SENSITIVE_MATERIAL_CONTEXTS
    ):
        return True, True
    if (
        config_like
        and not domain_descriptor
        and name_words & {"credentials", "secrets"}
        and name_words & SENSITIVE_MATERIAL_ENVIRONMENTS
    ):
        return True, True
    return ambiguous_suffix, False


def validate_reviewable_policy_path(
    path: str, *, extra_sensitive: set[str] | None = None
) -> str:
    """Validate one normalized, path-only reviewability declaration."""

    normalized = normalize_repo_path(path, label="reviewable path")
    if any(character in normalized for character in "*?["):
        raise ValueError("reviewable path must be one exact file path, not a glob")
    if _matches_declared_root(normalized.casefold(), extra_sensitive):
        raise ValueError(
            f"reviewable path overlaps declared sensitive material: {normalized}"
        )
    _, strong = _material_policy(normalized)
    if strong:
        raise ValueError(
            f"reviewable path cannot override strong sensitive material: {normalized}"
        )
    return normalized


def validate_reviewable_paths(
    repo: Path,
    paths: list[str],
    *,
    extra_sensitive: set[str] | None = None,
    max_paths: int | None = None,
) -> list[str]:
    """Validate exact existing regular files without reading their contents."""

    normalized = normalize_reviewable_paths(
        paths,
        extra_sensitive=extra_sensitive,
        max_paths=max_paths,
    )
    for path in normalized:
        current = repo
        parts = PurePosixPath(path).parts
        for index, part in enumerate(parts):
            current /= part
            try:
                info = current.lstat()
            except FileNotFoundError as exc:
                raise ValueError(
                    f"reviewable path must name an existing regular file: {path}"
                ) from exc
            if stat.S_ISLNK(info.st_mode):
                component_type = (
                    "parent component"
                    if index < len(parts) - 1
                    else "target file"
                )
                component = current.relative_to(repo).as_posix()
                raise ValueError(
                    f"reviewable path {component_type} must not be a symlink: "
                    f"{component}"
                )
            if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
                raise ValueError(
                    f"reviewable path parent must be a directory: {path}"
                )
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"reviewable path must name a regular file: {path}")
        if info.st_nlink != 1:
            raise ValueError(
                f"reviewable path must have link count one: {path}"
            )
    return normalized


def normalize_reviewable_paths(
    paths: list[str],
    *,
    extra_sensitive: set[str] | None = None,
    max_paths: int | None = None,
) -> list[str]:
    """Validate path-only declarations before repository spelling is resolved."""

    if max_paths is not None and len(paths) > max_paths:
        raise ValueError(
            f"reviewable paths exceed configured {max_paths}-path budget"
        )
    normalized = [
        validate_reviewable_policy_path(path, extra_sensitive=extra_sensitive)
        for path in paths
    ]
    if max_paths is not None and len(normalized) > max_paths:
        raise ValueError(
            f"reviewable paths exceed configured {max_paths}-path budget"
        )
    folded = [path.casefold() for path in normalized]
    if len(folded) != len(set(folded)):
        raise ValueError("reviewable paths must not contain case-insensitive duplicates")
    return sorted(normalized)


def is_sensitive_material_path(
    path: str,
    *,
    extra_sensitive: set[str] | None = None,
    reviewable_paths: set[str] | None = None,
) -> bool:
    """Return whether path alone identifies content that must remain unread."""

    normalized = normalize_repo_path(path)
    lowered = normalized.casefold()
    if _matches_declared_root(lowered, extra_sensitive):
        return True
    material, strong = _material_policy(normalized)
    if reviewable_paths and normalized in reviewable_paths:
        return material and strong
    return material


def is_security_domain_path(
    path: str, *, reviewable_paths: set[str] | None = None
) -> bool:
    """Return whether a path names security behavior that raises review risk."""

    normalized = normalize_repo_path(path)
    words = path_words(normalized)
    parts = PurePosixPath(normalized.casefold()).parts
    suffix = PurePosixPath(normalized).suffix.casefold()
    return (
        bool(reviewable_paths and normalized in reviewable_paths)
        or is_sensitive_material_path(
            normalized,
            reviewable_paths=reviewable_paths,
        )
        or suffix in PUBLIC_CERTIFICATE_SUFFIXES
        or any(part in REVIEWABLE_ENV_TEMPLATE_NAMES for part in parts)
        or bool(words & SECURITY_DOMAIN_WORDS)
        or {"api", "key"}.issubset(words)
        or {"access", "key"}.issubset(words)
        or {"private", "key"}.issubset(words)
        or {"service", "account"}.issubset(words)
        or {"tls", "key"}.issubset(words)
        or {"signing", "key"}.issubset(words)
    )


def is_protected_deletion_path(
    path: str,
    *,
    extra_sensitive: set[str] | None = None,
    reviewable_paths: set[str] | None = None,
) -> bool:
    normalized = normalize_repo_path(path)
    return (
        is_sensitive_material_path(
            normalized,
            extra_sensitive=extra_sensitive,
            reviewable_paths=reviewable_paths,
        )
        or PurePosixPath(normalized).suffix.lower() in PROTECTED_STATE_SUFFIXES
        or bool(path_words(normalized) & PROTECTED_STATE_WORDS)
    )


def sensitive_material_git_pathspecs() -> list[str]:
    """Return bounded Git globs that find secret-material candidates."""

    patterns = {
        "**/.env",
        "**/.env.*",
        "**/.envrc",
        "**/.git-credentials",
        "**/.netrc",
        "**/.npmrc",
        "**/.pypirc",
        "**/credentials.json",
        "**/id_dsa",
        "**/id_ecdsa",
        "**/id_ed25519",
        "**/id_rsa",
        "**/kubeconfig",
        "**/service-account.json",
        "**/secrets.yaml",
        "**/secrets.yml",
        "**/*credential*",
        "**/*credential*/**",
        "**/*secret*",
        "**/*secret*/**",
        "**/*token*",
        "**/*token*/**",
        "**/*certificate*",
        "**/*keystore*",
        "**/*api*key*",
        "**/*access*key*",
        "**/*private*key*",
        "**/*service*account*",
        "**/*tls*key*",
        "**/*signing*key*",
    }
    for name in SENSITIVE_MATERIAL_EXACT_NAMES:
        patterns.add(f"**/{name}/**")
    for directory in (
        SENSITIVE_MATERIAL_DIRECTORIES | ROOT_SENSITIVE_MATERIAL_DIRECTORIES
    ):
        patterns.add(f"**/{directory}/**")
    for suffix in SENSITIVE_MATERIAL_SUFFIXES:
        patterns.add(f"**/*{suffix}")
        patterns.add(f"**/*{suffix}/**")
    patterns.add("**/.env.*/**")
    return [f":(glob,icase){pattern}" for pattern in sorted(patterns)]


def validate_nonsensitive_managed_targets(paths: list[str]) -> None:
    sensitive = sorted(path for path in paths if is_sensitive_material_path(path))
    if sensitive:
        raise ValueError(
            "setup target catalog must not manage sensitive paths: "
            + ", ".join(sensitive)
        )
