# Security Policy

## Reporting a vulnerability

Please avoid publishing exploitable details in a public issue before a fix is available. Use GitHub's private security advisory feature for the repository when possible.

The parser is designed to process untrusted document text without executing document content. Optional PDF and DOCX ingestion relies on third-party parsers, so production deployments should keep dependencies patched and apply normal file-upload limits and sandboxing.
