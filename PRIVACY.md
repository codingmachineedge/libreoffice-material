# LibreOffice Material update privacy

LibreOffice Material checks this repository's latest normal GitHub Release for a Windows x64 update. Automatic checking is enabled by default: a new profile checks when the update task first runs and then uses a weekly interval unless the user changes it. Automatic checking can be disabled under **Tools > Options > LibreOffice > Online Update**.

A check requests the public `windows-update-manifest.xml` release asset and therefore shares the ordinary network information needed for an HTTPS request with GitHub and its release-delivery infrastructure, including the requesting IP address and request time. The normal update user agent contains the product and version, build ID, operating system, and processor architecture. The optional **Send OS version and basic hardware information** setting adds those details to the user agent; it is off by default.

The updater does not upload documents, document contents, filenames, profile data, or telemetry. Automatic downloading is off by default. When a download begins, the updater may open the release-notes page on GitHub, which makes a separate HTTPS request.

When an update is available, LibreOffice Material downloads only the manifest's tag-specific canonical MSI from `codingmachineedge/libreoffice-material`. It verifies the declared byte count and SHA-256 after the file is closed and again immediately before installation. Installation is never silent: the updater asks for explicit confirmation, with **No** as the default, before starting the interactive Windows Installer.

Release packages are currently unsigned. Hash verification detects accidental corruption or replacement that does not match the published manifest, but it is not a substitute for publisher code signing and cannot protect against compromise of the GitHub repository itself.
