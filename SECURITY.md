# Security policy and 2026-08-25 audit note

Do not commit API tokens, credentials, cookies, private URLs or raw notebooks without a dedicated review. DarkPipe's official default sources require no secret.

During adjacent-source archaeology, a hard-coded NASA ADS credential was found inside an immutable public Zenodo/GitHub-era OpenADS artifact. Its value is intentionally not reproduced here, was not used, and is not present in DarkPipe. The required remediation is to revoke/rotate that credential at NASA ADS and publish a sanitized successor release; historical bytes should remain immutable and be documented as affected.

Before publication, the repository is scanned for common secret formats and the exact exposed value. CI and releases must repeat a secret scan appropriate to the hosting environment.

To report a new vulnerability, open a private security advisory in GitHub rather than a public issue containing the secret.
