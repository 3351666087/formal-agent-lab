# 第三方依赖与许可证清单

由 `scripts/license_inventory.py` 生成（2026-10-01T01:56:35Z）：Python 环境中实际安装的发行包（区分运行时闭包与开发/测试工具）与 Web 生产依赖。许可证取自包元数据；逐项清单见 `docs/execution/evidence/phase3/licenses.json`。项目本身：Apache-2.0（`LICENSE`、`NOTICE`）。上游复用与调用位置见 [reuse-ledger.md](reuse-ledger.md)。

- Python 运行时依赖 97 个，开发/测试工具 10 个；Web 生产依赖 8 个。

## 按许可证

| 许可证 | 包数 |
|---|---|
| MIT | 52 |
| BSD-3-Clause | 13 |
| Apache-2.0 | 10 |
| MIT License | 9 |
| Apache 2.0 | 3 |
| BSD | 3 |
| PSF-2.0 | 2 |
| Modified BSD License | 2 |
| Apache License 2.0 | 2 |
| LGPL-3.0-only | 2 |
| BSD-2-Clause | 2 |
| Apache-2.0 (from the bundled LICENSE) | 1 |
| Apache-2.0 AND MIT | 1 |
| MPL-2.0 | 1 |
| MIT AND PSF-2.0 | 1 |
| BSD-3-Clause AND ISC | 1 |
| BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 1 |
| Apache-2.0 OR BSD-2-Clause | 1 |
| Python Software Foundation License | 1 |
| 3-Clause BSD License | 1 |
| Dual License | 1 |
| Apache-2.0 AND CNRI-Python | 1 |
| BSD License | 1 |
| ISC License | 1 |
| MIT OR Apache-2.0 | 1 |
| MIT License … | 1 |

## 需要留意的条目（copyleft 或未声明）

| 包 | 版本 | 许可证 | 范围 | 使用方式 |
|---|---|---|---|---|
| certifi | 2026.7.22 | MPL-2.0 | runtime | MPL-2.0 (file-level copyleft): the CA bundle used unmodified via httpx; no files changed |
| psycopg | 3.3.6 | LGPL-3.0-only | runtime | LGPL-3.0: used unmodified as a separately installed library (PostgreSQL driver of the platform API / worker); not vendored or statically linked; replaceable by the user |
| psycopg-binary | 3.3.6 | LGPL-3.0-only | runtime | LGPL-3.0: binary wheel of psycopg, same arrangement (installed, not vendored) |

## Python 运行时依赖

| 包 | 版本 | 许可证 |
|---|---|---|
| agent-client-protocol | 0.12.1 | Apache-2.0 (from the bundled LICENSE) |
| aiobotocore | 3.9.1 | Apache-2.0 |
| aiohappyeyeballs | 2.7.1 | PSF-2.0 |
| aiohttp | 3.14.3 | Apache-2.0 AND MIT |
| aioitertools | 0.13.0 | MIT |
| aiosignal | 1.4.0 | Apache 2.0 |
| alembic | 1.20.0 | MIT |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| attrs | 26.1.0 | MIT |
| beautifulsoup4 | 4.15.0 | MIT License |
| boto3 | 1.43.75 | Apache-2.0 |
| botocore | 1.43.75 | Apache-2.0 |
| certifi | 2026.7.22 | MPL-2.0 |
| charset-normalizer | 3.5.1 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| debugpy | 1.8.22 | MIT |
| docstring_parser | 0.18.0 | MIT |
| fastapi | 0.141.1 | MIT |
| frozenlist | 1.8.0 | Apache-2.0 |
| fsspec | 2026.6.0 | BSD-3-Clause |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httptools | 0.8.0 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| ijson | 3.5.1 | BSD-3-Clause AND ISC |
| inspect_ai | 0.3.269 | MIT License |
| jmespath | 1.1.0 | MIT |
| jsonlines | 4.0.0 | BSD |
| jsonpatch | 1.33 | Modified BSD License |
| jsonpath-ng | 1.8.0 | Apache 2.0 |
| jsonpointer | 3.1.1 | Modified BSD License |
| jsonref | 1.1.0 | MIT |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| linkify-it-py | 2.2.0 | MIT |
| Mako | 1.4.3 | MIT |
| markdown-it-py | 4.2.0 | MIT License |
| MarkupSafe | 3.0.3 | BSD-3-Clause |
| mdit-py-plugins | 0.6.1 | MIT License |
| mdurl | 0.1.2 | MIT License |
| mmh3 | 5.3.0 | MIT License |
| multidict | 6.9.1 | Apache License 2.0 |
| nest-asyncio2 | 1.7.3 | BSD |
| nexus-rpc | 1.4.0 | MIT |
| numpy | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| pathlib_abc | 0.5.2 | Python Software Foundation License |
| platformdirs | 4.11.15 | MIT |
| propcache | 0.5.4 | Apache-2.0 |
| protobuf | 7.36.2 | 3-Clause BSD License |
| psutil | 7.2.2 | BSD-3-Clause |
| psycopg | 3.3.6 | LGPL-3.0-only |
| psycopg-binary | 3.3.6 | LGPL-3.0-only |
| pydantic | 2.13.5 | MIT |
| pydantic_core | 2.46.5 | MIT |
| pydantic-settings | 2.15.0 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| python-dateutil | 2.9.0.post0 | Dual License |
| python-dotenv | 1.2.3 | BSD-3-Clause |
| PyYAML | 6.0.3 | MIT |
| referencing | 0.37.0 | MIT |
| regex | 2026.9.10 | Apache-2.0 AND CNRI-Python |
| requests | 2.34.2 | Apache-2.0 |
| rich | 15.0.0 | MIT |
| rpds-py | 2026.6.3 | MIT |
| s3fs | 2026.6.0 | BSD |
| s3transfer | 0.19.2 | Apache License 2.0 |
| semver | 3.1.0 | BSD License |
| shellingham | 1.5.4 | ISC License |
| shortuuid | 1.0.13 | BSD-3-Clause |
| six | 1.17.0 | MIT |
| sniffio | 1.3.1 | MIT OR Apache-2.0 |
| soupsieve | 2.10 | MIT |
| SQLAlchemy | 2.1.1 | MIT |
| starlette | 1.7.0 | BSD-3-Clause |
| temporalio | 1.33.0 | MIT |
| tenacity | 9.1.4 | Apache 2.0 |
| textual | 8.2.8 | MIT |
| tiktoken | 0.14.0 | MIT License … |
| typer | 0.27.2 | MIT |
| types-protobuf | 7.35.1.20260906 | Apache-2.0 |
| typing_extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.4 | MIT |
| universal_pathlib | 0.3.10 | MIT |
| urllib3 | 2.8.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| uvloop | 0.22.1 | MIT License |
| watchfiles | 1.3.0 | MIT |
| websockets | 17.1 | BSD-3-Clause |
| wrapt | 2.4.1 | BSD-2-Clause |
| yarl | 1.25.1 | Apache-2.0 |
| z3-solver | 5.1.0.0 | MIT License |
| zipfile-zstd | 0.0.4 | MIT License |
| zipp | 4.1.0 | MIT |
| zstandard | 0.25.0 | BSD-3-Clause |
