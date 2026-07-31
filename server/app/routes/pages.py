"""用户/agent 友好的页面路由。

- GET /          : HTML 帮助主页(人类看)
- GET /agents.txt: agents.txt 协议(2025 AI 入口)
- GET /skill.md  : 完整 SKILL.md(给 agent 抓)
- GET /guide.md  : 详细 markdown 指南(给 LLM 抓)
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse

router = APIRouter(tags=["pages"])

SERVER_NAME = "agent-handoff"
SERVER_TAGLINE = "End-to-end encrypted chat handoff between AI agents"
SERVER_URL = "https://aishangai.shop"


# ==================== HTML 主页 ====================

# CSS 里的 {} 用 {{ }} 在 f-string 中转义
_INDEX_HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{SERVER_NAME} — {SERVER_TAGLINE}</title>
<meta name="description" content="End-to-end encrypted chat handoff between AI agents. Server stores only ciphertext.">
<style>
  :root {{
    --bg: #0f1115;
    --card: #1a1d23;
    --fg: #e4e6eb;
    --muted: #9ca3af;
    --accent: #4ade80;
    --code: #f5f5f5;
    --code-bg: #0a0c10;
    --border: #2a2d33;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                 "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    background: var(--bg);
    color: var(--fg);
    line-height: 1.6;
  }}
  .wrap {{ max-width: 880px; margin: 0 auto; padding: 48px 24px 96px; }}
  h1 {{ font-size: 36px; margin: 0 0 8px; }}
  .tag {{ color: var(--muted); font-size: 16px; margin-bottom: 32px; }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
  }}
  h2 {{ font-size: 20px; margin: 0 0 12px; color: var(--accent); }}
  h3 {{ font-size: 16px; margin: 16px 0 8px; color: var(--fg); }}
  p {{ margin: 8px 0; color: var(--muted); }}
  ol, ul {{ padding-left: 24px; color: var(--muted); }}
  li {{ margin: 6px 0; }}
  code {{
    background: var(--code-bg);
    color: var(--code);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 14px;
  }}
  pre {{
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    overflow-x: auto;
    margin: 12px 0;
  }}
  pre code {{
    background: none;
    padding: 0;
    color: var(--code);
    font-size: 13px;
    line-height: 1.5;
  }}
  .green {{ color: var(--accent); font-weight: 500; }}
  .links {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px; }}
  .links a {{
    color: var(--accent);
    text-decoration: none;
    padding: 8px 16px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 14px;
  }}
  .links a:hover {{ background: var(--code-bg); }}
  .steps {{ counter-reset: step; }}
  .steps li {{ counter-increment: step; list-style: none; position: relative; padding-left: 32px; }}
  .steps li::before {{
    content: counter(step);
    position: absolute;
    left: 0;
    top: 0;
    background: var(--accent);
    color: #0f1115;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 13px;
  }}
  .badge {{
    display: inline-block;
    background: var(--code-bg);
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    margin-right: 4px;
  }}
  /* Hero CTA */
  .hero {{
    background: linear-gradient(135deg, #1a1d23 0%, #0f4d2a 100%);
    border: 1px solid #2a5e3a;
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 24px;
    text-align: center;
  }}
  .hero h2 {{
    color: #4ade80;
    font-size: 22px;
    margin: 0 0 12px;
  }}
  .hero p {{
    color: var(--muted);
    margin: 0 0 20px;
  }}
  .cta {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #4ade80;
    color: #0f1115;
    border: none;
    padding: 14px 28px;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
    text-decoration: none;
    font-family: inherit;
  }}
  .cta:hover {{
    background: #22c55e;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(74, 222, 128, 0.3);
  }}
  .cta:active {{ transform: translateY(0); }}
  .cta.copied {{ background: #22c55e; color: white; }}
  .cta-hint {{
    color: var(--muted);
    font-size: 13px;
    margin-top: 12px;
  }}
  .cta-secondary {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border);
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s ease;
    font-family: inherit;
  }}
  .cta-secondary:hover {{
    background: var(--code-bg);
    color: var(--fg);
    border-color: #3a3d43;
  }}
  .sha-label {{
    color: var(--muted);
    font-size: 12px;
    margin-right: 4px;
  }}
  .sha-hash {{
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 11px;
    background: var(--code-bg);
    border: 1px solid var(--border);
    padding: 2px 6px;
    border-radius: 4px;
    color: #fbbf24;
    word-break: break-all;
  }}
  /* pre block + copy button */
  pre {{
    position: relative;
  }}
  .copy-btn {{
    position: absolute;
    top: 8px;
    right: 8px;
    background: #2a2d33;
    color: var(--muted);
    border: 1px solid #3a3d43;
    padding: 4px 10px;
    border-radius: 5px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s ease;
    font-family: inherit;
  }}
  .copy-btn:hover {{
    background: #3a3d43;
    color: var(--fg);
  }}
  .copy-btn.copied {{
    background: #22c55e;
    color: white;
    border-color: #22c55e;
  }}
  .url-bar {{
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 14px;
    margin: 12px 0;
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 13px;
  }}
  .url-bar .url {{ flex: 1; color: var(--code); overflow: hidden; text-overflow: ellipsis; }}
  footer {{ margin-top: 64px; text-align: center; color: var(--muted); font-size: 13px; }}
</style>
<script>
function copyText(btn) {{
  const text = btn.dataset.copy || (btn.previousElementSibling && btn.previousElementSibling.innerText) || '';
  if (!text) return;
  // 用 navigator.clipboard(优先),fallback 用 textarea + execCommand
  const after = (ok) => {{
    const orig = btn.textContent;
    btn.textContent = ok ? '✓ 已复制' : '复制失败';
    btn.classList.add('copied');
    setTimeout(() => {{
      btn.textContent = orig;
      btn.classList.remove('copied');
    }}, 1500);
  }};
  if (navigator.clipboard && window.isSecureContext) {{
    navigator.clipboard.writeText(text).then(() => after(true)).catch(() => fallback());
  }} else {{
    fallback();
  }}
  function fallback() {{
    try {{
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      after(ok);
    }} catch (e) {{ after(false); }}
  }}
}}

// 健康检查(给一个小红点表示服务状态)
(async function() {{
  try {{
    const r = await fetch('/api/v1/health');
    if (!r.ok) throw new Error('HTTP ' + r.status);
  }} catch (e) {{
    // 服务挂了就显示警告
    const h = document.querySelector('.tag');
    if (h) {{
      h.textContent += '  ⚠️ health check failed';
      h.style.color = '#f87171';
    }}
  }}
}})();
</script>
</head>
<body>
<div class="wrap">
  <h1>🔐 {SERVER_NAME}</h1>
  <div class="tag">{SERVER_TAGLINE}</div>

  <div class="hero">
    <h2>🚀 一键发给 Agent(无 install 模式)</h2>
    <p>把这段贴到目标 agent 对话。agent 只需 <code>curl</code> 拉一个 markdown 文档到自己 skills 目录,完全不用装任何东西、跑任何 install 脚本</p>
    <button class="cta" data-copy='我要用 agent-handoff(开源的 agent 任务上下文加密传递服务,部署在 https://aishangai.shop,端到端加密,服务端只看到密文)。

请按以下步骤操作(不需要 install,不需要装包,不需要创建任何进程,只需要 curl):

1. 拉技能文档到你的 skills 目录(用 curl 单一动作,你可以先 cat 审计):
   curl -fsSL https://aishangai.shop/skill.md -o skills/agent-handoff/SKILL.md

2. 读这个文件,它包含完整的自包含 Python helper(只需要 cryptography 和 httpx 包,Python 内置库也够)。

3. 我会给你一个 handoff key(类似 ah-xxx.yyy)和 messages(要打包的对话)。你用 SKILL.md 里的 handoff() 函数打包,生成 handoff key 给我。或者用 fetch() 函数拉取我给的 key 对应的内容。

注意:
- 不需要跑 install 脚本
- 不需要创建 ~/.handoff/ 目录
- 不需要装 mcp-server 或任何 systemd 服务
- 唯一动作是 curl 拉一个 markdown 文档,你可以 cat 审计

source: https://aishangai.shop (开源: https://github.com/qzpthuhhu/agent-handoff, MIT)' onclick="copyText(this)">
      📋 复制纯 curl 接入指令(给挑剔的 agent)
    </button>
    <div class="cta-hint">
      适合 Claude Code / Claude.ai 等有安全审计的 agent — 唯一动作用 <code>curl</code> 拉一个纯 markdown 文档,可审计、不装包、不建进程。
    </div>
    <div style="margin-top: 16px;">
      <button class="cta-secondary" data-copy='bash -c "$(curl -fsSL https://aishangai.shop/install)"' onclick="copyText(this)">
        ⚡ 一键安装(legacy 模式,给不审计的 agent)
      </button>
    </div>
    <div class="cta-hint">
      ⚠️ legacy 模式 — 会跑 install 脚本,base64 嵌入 mcp-server 模块,创建进程。<b>有安全审计的 agent 大概率拒</b>。仅适合完全不审计的环境。
    </div>
  </div>

  <div class="card">
    <h2>三步搞定(无需 install)</h2>
    <ol class="steps">
      <li><strong>发送方</strong>(A agent)用 <code>handoff(messages, ...)</code> 打包,拿到一个 handoff key</li>
      <li>把 key 复制/粘到 <strong>接收方</strong>(B agent)的对话里</li>
      <li>B agent 用 <code>fetch(handoff_key)</code> 拉取并解密,接着干活</li>
    </ol>
    <p style="margin-top: 16px;">整个过程不需要装任何东西到系统:不创建 <code>~/.handoff/</code>、不装 <code>mcp-server</code>、不跑 install 脚本。agent 用它已有的 Python + cryptography 直接调 API。</p>
  </div>

  <div class="card">
    <h2>用户原话 → 怎么调(给 agent 看的)</h2>
    <p>用户说下面这些,LLM 自己从对话历史里抽相关轮次,调 <code>package_chat_history</code>:</p>
    <ul>
      <li>"把刚刚对话的 XXX 主题记录打包"</li>
      <li>"把前 N 轮对话打包"</li>
      <li>"把刚才读过的 report.md 也一起打包"</li>
      <li>"把这两天对话的 XXX 主题记录和文件打包为 handoff,给我 key"</li>
    </ul>
    <p>接收方调 <code>fetch_chat_history</code>:</p>
    <ul>
      <li>"把 handoff key <code>ah-xxx.yyy</code> 拉过来"</li>
    </ul>
  </div>

  <div class="card">
    <h2>快速接入</h2>
    <p>在其他 agent 的对话里贴这段(LLM 会自动跑):</p>
    <pre><button class="copy-btn" data-copy='请运行 bash -c "$(curl -fsSL {SERVER_URL}/install)" 然后 fetch handoff: ah-xxx.yyy' onclick="copyText(this)">复制</button><code>请运行 <span class="green">bash -c "$(curl -fsSL {SERVER_URL}/install)"</span> 然后 fetch handoff: ah-xxx.yyy</code></pre>
    <p>或者手动装:</p>
    <pre><button class="copy-btn" data-copy='curl -fsSL {SERVER_URL}/install | bash
handoff package --messages-json ./msgs.json --hint '"'"'topic'"'"'
handoff fetch --handoff-key ah-xxx.yyy' onclick="copyText(this)">复制</button><code>curl -fsSL {SERVER_URL}/install | bash
handoff package --messages-json ./msgs.json --hint 'topic'
handoff fetch --handoff-key ah-xxx.yyy</code></pre>
  </div>

  <div class="card">
    <h2>给 agent 看的入口</h2>
    <p>如果你是 LLM/agent,直接抓这些资源:</p>
    <div class="links">
      <a href="/guide.md">📖 /guide.md</a>
      <a href="/agents.txt">🤖 /agents.txt</a>
      <a href="/skill.md">🛠 /skill.md</a>
      <a href="/install">⬇️ /install</a>
    </div>
  </div>

  <div class="card">
    <h2>API</h2>
    <p>纯 HTTP,任何语言都能用:</p>
    <ul>
      <li><code>POST /api/v1/bundles</code> — 上传密文</li>
      <li><code>GET  /api/v1/bundles/&#123;id&#125;</code> — 拉取密文</li>
      <li><code>DELETE /api/v1/bundles/&#123;id&#125;</code> — 强制删除(需 admin token)</li>
      <li><code>GET  /api/v1/health</code> — 健康检查</li>
    </ul>
    <div class="links">
      <a href="/docs">📚 Swagger UI</a>
      <a href="/redoc">📚 ReDoc</a>
      <a href="/openapi.json">{{ }} OpenAPI JSON</a>
    </div>
  </div>

  <div class="card">
    <h2>安全模型</h2>
    <p><span class="badge">AES-256-GCM</span> <span class="badge">E2E 加密</span> <span class="badge">7 天 TTL</span></p>
    <ul>
      <li>服务端只看到 base64 密文,看不到明文</li>
      <li>handoff key 格式: <code>ah-&#123;bundle_id&#125;.&#123;enc_key&#125;</code>(32 字节 AES key,URL-safe base64)</li>
      <li>bundle 默认 7 天过期,后台任务每 6 小时清理</li>
      <li>key 独立于服务端,服务端无法还原内容</li>
    </ul>
  </div>

  <footer>
    <p>open source · <a href="https://github.com/qzpthuhhu/agent-handoff" style="color: var(--accent);">GitHub</a> · MIT</p>
  </footer>
</div>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> str:
    """HTML 主页(人类看)。"""
    return _INDEX_HTML


# ==================== agents.txt ====================

_AGENTS_TXT = """# agents.txt — entry points for AI agents
# 2025 standard for LLM/agent discovery.
#
# If you're an LLM/agent reading this:
#   1. Read /guide.md for full getting-started instructions
#   2. Bootstrap the skill: bash -c "$(curl -fsSL https://aishangai.shop/install)"
#   3. Use package_chat_history / fetch_chat_history tools

User-Agent: *
Allow: /

# Primary agent-facing resources
Sitemap: https://aishangai.shop/guide.md
Sitemap: https://aishangai.shop/skill.md
Sitemap: https://aishangai.shop/install
Sitemap: https://aishangai.shop/openapi.json
"""


@router.get("/agents.txt", response_class=PlainTextResponse, include_in_schema=False)
def agents_txt() -> str:
    """agents.txt 入口(给 LLM/agent 看)。"""
    return _AGENTS_TXT


# ==================== /skill.md ====================
# 完整 SKILL.md,自包含 Python helper,agent fetch 后复制粘贴就能用,
# 不需要 install / 不创建进程 / 不装包 / 不动用户文件系统。

_SKILL_MD = """---
name: agent-handoff
description: 在两个 AI agent 之间端到端加密传递聊天记录和过程文件。无需 install — fetch 这个 skill 文档后,agent 用它自带的 Python + cryptography 直接调 API。
---

# agent-handoff

> 端到端加密传递对话上下文。**服务器只看到密文**,密钥只在你和目标 agent 之间流转。
> 
> 本 skill **不需要安装任何东西** — 只需要 Python(内置)+ `cryptography` 包(可能需要 `pip install cryptography`)。

## TL;DR

1. **A agent(发送方)**: 调 `handoff(messages, server_url, files=...)` 拿到一个 `handoff_key`
2. **用户**: 把 `handoff_key` 复制/粘到 B agent 的对话里
3. **B agent(接收方)**: 调 `fetch(handoff_key, server_url)` 拿到 messages 和 files

server URL: `https://aishangai.shop`(生产) / `http://localhost:8080`(本地开发)

## 接入(3 步,无需 install)

### Step 1: 确认环境

```bash
python3 -c "import cryptography; print('ok')" 2>/dev/null || pip3 install cryptography
```

### Step 2: 复制下面的 Python 代码到你的脚本/对话里

(下面有完整可用的 `handoff()` 和 `fetch()` 函数,100% 自包含,只需要 `cryptography` 包)

```python
# === agent-handoff: 自包含 helper ===
# 只需要 `cryptography` 包(pip install cryptography)
# 服务端只看到密文,无法还原明文

import json
import base64
import os
import tarfile
import io
from pathlib import Path
from typing import Optional, List

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    raise SystemExit("缺少 cryptography 包,请先 pip install cryptography")

import httpx  # 任何 HTTP client 都可以,用 httpx 演示

SERVER_URL_DEFAULT = "https://aishangai.shop"

def _new_key() -> bytes:
    import secrets
    return secrets.token_bytes(32)

def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")

def _from_b64(s: str) -> bytes:
    return base64.b64decode(s)

def _read_files(paths: Optional[List[str]]):
    files = []
    for p in paths or []:
        path = Path(p).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"文件不存在: {p}")
        raw = path.read_bytes()
        files.append({
            "name": path.name,
            "path": str(path),
            "content_b64": _b64(raw),
            "size": len(raw),
        })
    return files

def handoff(
    messages: list,
    server_url: str = SERVER_URL_DEFAULT,
    files: Optional[List[str]] = None,
    hint: Optional[str] = None,
    expires_in: int = 604800,
) -> str:
    \"\"\"打包 + 加密 + 上传,返回 handoff_key(给 B 端用)。
    
    Args:
        messages: 消息列表,每条 {role, content, ts?}
        server_url: handoff server URL
        files: 文件路径列表(可选)
        hint: 给接收方的备注(可选)
        expires_in: 过期秒数,默认 7 天
    Returns:
        handoff_key 字符串,形如 'ah-7f3a9b2c.3VLmNI...'
    \"\"\"
    if not messages:
        raise ValueError("messages 不能为空")
    
    bundle_id = secrets.token_hex(16)  # 16 字节 hex
    enc_key = _new_key()  # 32 字节
    
    # 构造明文
    payload = {
        "version": "1.0",
        "source": {},
        "messages": messages,
        "files": _read_files(files),
    }
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    
    # AES-256-GCM 加密(AAD 绑 bundle_id,防跨 bundle 替换)
    aesgcm = AESGCM(enc_key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext, bundle_id.encode("utf-8"))
    
    # 上传
    body = {
        "id": bundle_id,
        "ciphertext_b64": _b64(ct),
        "nonce_b64": _b64(nonce),
    }
    if expires_in:
        body["expires_in"] = expires_in
    if hint:
        body["hint"] = hint
    
    r = httpx.post(f"{server_url.rstrip('/')}/api/v1/bundles", json=body, timeout=30)
    r.raise_for_status()
    
    enc_key_b64 = _b64(enc_key).rstrip("=").replace("+", "-").replace("/", "_")  # urlsafe-b64-like
    # 上面那行是 base64 标准(非 urlsafe)。要 urlsafe 请用 base64.urlsafe_b64encode。
    return f"ah-{bundle_id}.{base64.urlsafe_b64encode(enc_key).rstrip(b'=').decode('ascii')}"


def fetch(
    handoff_key: str,
    server_url: str = SERVER_URL_DEFAULT,
    output_dir: Optional[str] = None,
) -> dict:
    \"\"\"拉取 + 解密 + 落盘,返回 summary。\"\"\"
    if not handoff_key.startswith("ah-"):
        raise ValueError("handoff_key 格式不合法")
    bid, enc_b64 = handoff_key[3:].split(".", 1)
    enc_key = base64.urlsafe_b64decode(enc_b64 + "=" * (-len(enc_b64) % 4))
    
    r = httpx.get(f"{server_url.rstrip('/')}/api/v1/bundles/{bid}", timeout=30)
    r.raise_for_status()
    blob = r.json()
    
    ct = _from_b64(blob["ciphertext_b64"])
    nonce = _from_b64(blob["nonce_b64"])
    aesgcm = AESGCM(enc_key)
    plaintext = aesgcm.decrypt(nonce, ct, bid.encode("utf-8"))
    payload = json.loads(plaintext.decode("utf-8"))
    
    # 落盘
    if output_dir is None:
        from datetime import datetime
        output_dir = f"./handoff/{bid}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    out = Path(output_dir)
    (out / "files").mkdir(parents=True, exist_ok=True)
    (out / "metadata.json").write_text(
        json.dumps({
            "version": payload.get("version"),
            "source": payload.get("source"),
            "n_messages": len(payload.get("messages", [])),
            "n_files": len(payload.get("files", [])),
            "metadata": payload.get("metadata", {}),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with open(out / "messages.jsonl", "w", encoding="utf-8") as f:
        for m in payload.get("messages", []):
            f.write(json.dumps(m, ensure_ascii=False) + "\\n")
    written_files = []
    for fi in payload.get("files", []):
        target = out / "files" / Path(fi["name"]).name
        target.write_bytes(_from_b64(fi["content_b64"]))
        written_files.append(str(target))
    
    return {
        "output_dir": str(out),
        "n_messages": len(payload.get("messages", [])),
        "n_files": len(payload.get("files", [])),
        "files": written_files,
        "source": payload.get("source", {}),
    }
```

### Step 3: 用

```python
# A 端
key = handoff(
    messages=[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
    server_url="https://aishangai.shop",
    files=["./report.md"],
    hint="Q3 财报 handoff",
)
print("handoff key:", key)  # 复制给 B 端

# B 端
summary = fetch(
    handoff_key="ah-7f3a9b2c....",
    server_url="https://aishangai.shop",
    output_dir="./received",
)
print("还原了", summary["n_messages"], "条消息 +", summary["n_files"], "个文件")
```

## API 端点(直调,不需要 Python helper)

```
POST /api/v1/bundles
{
  "id": "<32 字符 hex>",
  "ciphertext_b64": "<AES-GCM 密文 base64>",
  "nonce_b64": "<12 字节 base64>",
  "expires_in": 604800,
  "hint": "..."
}

GET /api/v1/bundles/{id}
→ 200: {id, ciphertext_b64, nonce_b64, ...}
→ 404 / 410

DELETE /api/v1/bundles/{id}  (需要 admin token)
GET  /api/v1/health
```

## 安全模型(关键)

- **AES-256-GCM** 端到端加密
- bundle id(16B)和 key(32B)**完全独立**,服务端无法还原
- AAD 绑 bundle_id,**防密文跨 bundle 替换**
- 服务端只看到 base64 密文
- handoff_key 格式:`ah-{bundle_id_hex}.{key_urlsafe_b64}`,~50 字符
- bundle 默认 7 天过期,后台任务每 6 小时清

## 文件

- README: https://github.com/qzpthuhhu/agent-handoff
- guide:  https://aishangai.shop/guide.md
- source:  MIT
"""


@router.get("/skill.md", response_class=PlainTextResponse, include_in_schema=False)
def skill_md() -> str:
    """自包含 SKILL.md:包含完整 Python helper,agent fetch 后即可使用。"""
    return _SKILL_MD


# ==================== /guide.md ====================

_GUIDE_MD = """# agent-handoff — Getting Started Guide

> End-to-end encrypted chat handoff between AI agents.
> Server stores only ciphertext; encryption keys never reach the server.

## TL;DR

1. **A agent**: package conversation → upload → get `handoff_key`
2. **User**: copy `handoff_key` (e.g. `ah-7f3a9b2c.3VLmNI...`)
3. **B agent**: paste key + run install script → fetch + decrypt

## User intent → tool call mapping

When a user says any of these natural-language requests, the LLM should:
1. Extract relevant `messages` from its own conversation history
2. Identify any `files` the user referenced
3. Call the appropriate tool

| User says | Tool call |
|---|---|
| "把刚刚对话的 XXX 主题记录打包" | `package_chat_history(messages=[...filtered...], server_url=...)` |
| "把前 N 轮对话打包" | `package_chat_history(messages=[...last N...], server_url=...)` |
| "把刚才读过的 report.md 也一起打包" | `package_chat_history(messages=[...], files=["/path/to/report.md"], ...)` |
| "把 handoff key `ah-xxx.yyy` 拉过来" | `fetch_chat_history(handoff_key="ah-xxx.yyy", server_url=...)` |
| "校验一下 key `ah-xxx.yyy` 是不是合法" | `inspect_handoff_key(handoff_key="ah-xxx.yyy")` |

The tools do **NOT** read your conversation context — you must construct
`messages` yourself from your context.

## One-line install (for new agents)

If a user wants to onboard a new agent:

```bash
bash -c "$(curl -fsSL https://aishangai.shop/install)"
```

This installs the handoff skill to `~/.handoff/` including:
- `SKILL.md` — this guide
- `handoff.py` — CLI wrapper
- `lib/agent_handoff_mcp/` — Python module
- Auto-installs `httpx`, `cryptography` if missing
- Writes `~/.handoff/config` with server URL

After install, the agent can:

```bash
handoff package --messages-json ./msgs.json --hint "topic"
handoff fetch --handoff-key ah-xxx.yyy --output-dir ./out
handoff inspect --handoff-key ah-xxx.yyy
```

## Tool reference

### `package_chat_history(messages, server_url, files?, metadata?, hint?, expires_in?)`

Pack messages + files, encrypt, upload, return handoff key.

**Required**:
- `messages`: list of `{role, content, ts?}`. You construct this from your context.
- `server_url`: the handoff server URL (e.g. `https://aishangai.shop`)

**Optional**:
- `files`: list of file paths to include
- `metadata`: extra info (e.g. `{"topic": "Q3 review"}`)
- `hint`: short note shown in the server (e.g. `"Q3 finance handoff"`)
- `expires_in`: TTL in seconds (default 604800 = 7 days, max 30 days)

**Returns**: handoff_key string like `ah-7f3a9b2c.3VLmNI...`

### `fetch_chat_history(handoff_key, server_url, output_dir?)`

Fetch a bundle by handoff key, decrypt, write to disk.

**Required**:
- `handoff_key`: the key like `ah-xxx.yyy`
- `server_url`: server URL

**Optional**:
- `output_dir`: where to write (default `./handoff/{bundle_id}-{ts}`)

**Returns**: `output_dir`, `metadata.json`, `messages.jsonl`, `files/` paths

### `inspect_handoff_key(handoff_key)`

Validate key format (no network call). Just checks structure.

## Calling examples

### Example 1: User says "把刚刚对话的 财务主题记录和文件打包给我 key"

```python
# 1. LLM extracts from its own context (semantic understanding)
messages = [
    {"role": "user", "content": "帮我看一下 Q3 营收数据"},
    {"role": "assistant", "content": "Q3 营收 $42M,增长 20%"},
    # ... LLM filters to only finance-related turns
]
files = ["/Users/me/work/q3-finance.pdf"]  # LLM finds this from context

# 2. Call the tool
result = package_chat_history(
    messages=messages,
    server_url="https://aishangai.shop",
    files=files,
    metadata={"topic": "Q3 财务"},
    hint="Q3 财务相关对话 handoff",
)

# 3. Show the key to the user
# Output: ah-7f3a9b2c.3VLmNI...
```

### Example 2: User says "把 handoff key `ah-xxx.yyy` 拉过来"

```python
summary = fetch_chat_history(
    handoff_key="ah-xxx.yyy",
    server_url="https://aishangai.shop",
    output_dir="./handoff",
)
# Read messages.jsonl and files/ in output_dir
```

## Security model

- **AES-256-GCM** end-to-end encryption
- Bundle ID (16 bytes random) and encryption key (32 bytes random) are independent
- Server stores ONLY: ciphertext, nonce, size, expires_at, hint
- Server CANNOT decrypt without the key
- Keys are base64url-encoded in `ah-{bundle_id}.{key}` format
- AAD binds ciphertext to bundle_id (prevents cross-bundle replay)

## API endpoints (raw HTTP)

If MCP / skill not available, use HTTP directly:

```
POST /api/v1/bundles
{
  "id": "<32-char hex bundle id>",
  "ciphertext_b64": "...",
  "nonce_b64": "...",
  "expires_in": 604800,
  "hint": "optional"
}

GET /api/v1/bundles/{id}
→ 200: {id, ciphertext_b64, nonce_b64, hint, expires_at}
→ 404: not found
→ 410: expired or consumed

GET /api/v1/health
→ 200: {status: "ok", storage: "local|tos", version: "..."}
```

## Tips

- Default TTL is 7 days. Plan accordingly for long-running handoffs.
- One-time consume mode: set `ONE_TIME_CONSUME=true` server-side, GET once then bundle is gone.
- Server has a 50MB default size cap per bundle (`MAX_BUNDLE_SIZE`).
- File paths in `files` are read on the A-side and base64-embedded — they don't leak to server.
- Reuse the same handoff_key for retries? NO — the key derives the encryption. Lost key = lost data.

## Open source

https://github.com/qzpthuhhu/agent-handoff

MIT License.
"""


@router.get("/guide.md", response_class=PlainTextResponse, include_in_schema=False)
def guide_md() -> str:
    """Markdown 格式的详细使用指南(给 LLM/agent 抓的)。"""
    return _GUIDE_MD
