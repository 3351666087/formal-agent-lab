"""ArtifactStore.put/get: content-addressed, digest-verified large objects (local filesystem here; S3 in compose)."""

import tempfile

from formal_lab_runtime.artifacts import LocalArtifactStore

store = LocalArtifactStore(tempfile.mkdtemp())
ref = store.put(b'{"hello": "artifact"}', name="hello.json", media_type="application/json", format_version="example@1")
print(ref.uri, ref.size_bytes, ref.digest)
assert store.get(ref) == b'{"hello": "artifact"}'
