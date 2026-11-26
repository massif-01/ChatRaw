#!/usr/bin/env python3
"""
AI Code Review Script for PR - Gemini / OpenAI compatible.
Reads PR patches as data from the GitHub API when invoked by Actions.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request

GITHUB_STEP_SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY")
GITHUB_BASE_REF = os.environ.get("GITHUB_BASE_REF", "main")
MAX_DIFF_CHARS = 15000

REVIEW_DIMENSIONS = """请从以下维度审查代码变更，给出简明扼要的中文反馈：

1. **安全**：是否存在潜在的安全漏洞（如注入、XSS、敏感信息泄露）
2. **Bug**：是否可能引入运行时错误或逻辑问题
3. **性能**：是否存在明显性能问题
4. **可读性**：命名、注释、结构是否清晰
5. **架构**：是否符合项目既有设计，是否过度设计或设计不足
6. **前端特有**（若含 JS/CSS）：DOM 操作是否安全、浏览器兼容性、无障碍性（a11y）"""

# 支持审查的文件类型
REVIEW_PATTERNS = [
    "*.py",
    "*.js",
    "*.css",
    "backend/**/*.py",
    "backend/**/*.js",
    "backend/**/*.css",
]


def run_cmd(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    """Run command, return (returncode, stdout+stderr)."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    out = (result.stdout or "") + (result.stderr or "")
    return result.returncode, out


def get_code_diff() -> tuple[list[str], str]:
    """Get list of changed .py/.js/.css files and the diff content."""
    pr_number = os.environ.get("PR_NUMBER")
    if pr_number:
        return get_pr_patches(pr_number)

    base_ref = f"origin/{GITHUB_BASE_REF}"
    # Get changed files (Python, JavaScript, CSS)
    rc, out = run_cmd(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD", "--"] + REVIEW_PATTERNS
    )
    if rc != 0:
        return [], ""
    files = [f.strip() for f in out.strip().split("\n") if f.strip()]
    if not files:
        return [], ""

    # Get full diff
    rc, diff_out = run_cmd(
        ["git", "diff", f"{base_ref}...HEAD", "--"] + REVIEW_PATTERNS
    )
    diff = diff_out if rc == 0 else ""

    if len(diff) > MAX_DIFF_CHARS:
        diff = (
            diff[:MAX_DIFF_CHARS]
            + f"\n\n...[diff 已截断，总计超出 {MAX_DIFF_CHARS} 字符]..."
        )

    return files, diff


def get_pr_patches(pr_number: str) -> tuple[list[str], str]:
    """Fetch PR file patches without checking out or executing PR content."""
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid GITHUB_REPOSITORY")
    if not pr_number.isascii() or not pr_number.isdigit() or not token:
        raise ValueError("Missing or invalid PR_NUMBER or GITHUB_TOKEN")

    files: list[str] = []
    patches: list[str] = []
    for page in range(1, 31):
        url = (
            f"https://api.github.com/repos/{repository}/pulls/{pr_number}/files"
            f"?per_page=100&page={page}"
        )
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "ChatRaw-PR-Review",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            page_files = json.load(response)
        if not isinstance(page_files, list):
            raise ValueError("Invalid GitHub PR file response")
        for item in page_files:
            name = item.get("filename", "")
            if not isinstance(name, str) or not name.lower().endswith(
                (".py", ".js", ".mjs", ".css")
            ):
                continue
            files.append(name)
            patch = item.get("patch")
            if not isinstance(patch, str):
                patch = "[GitHub did not provide a textual patch for this file.]"
            patches.append(f"--- {name}\n{patch}\n")
        if len(page_files) < 100:
            break

    diff = "\n".join(patches)
    if len(diff) > MAX_DIFF_CHARS:
        diff = (
            diff[:MAX_DIFF_CHARS]
            + f"\n\n...[diff 已截断，总计超出 {MAX_DIFF_CHARS} 字符]..."
        )
    return files, diff


def build_prompt(files: list[str], diff: str) -> str:
    """Build the review prompt."""
    py_count = sum(1 for f in files if f.endswith(".py"))
    js_count = sum(1 for f in files if f.lower().endswith((".js", ".mjs")))
    css_count = sum(1 for f in files if f.endswith(".css"))
    lang_parts = []
    if py_count:
        lang_parts.append(f"Python ({py_count})")
    if js_count:
        lang_parts.append(f"JavaScript ({js_count})")
    if css_count:
        lang_parts.append(f"CSS ({css_count})")
    lang_desc = "、".join(lang_parts)
    return f"""你是一位资深代码审查专家。请对以下 PR 中的代码变更进行审查，涉及语言：{lang_desc}。

## 修改的文件
{chr(10).join(f"- {f}" for f in files)}

## Diff
```
{diff}
```

{REVIEW_DIMENSIONS}

请直接输出审查结论，使用 Markdown 格式。"""


def call_gemini(prompt: str) -> str | None:
    """Call Gemini API, return response text or None on failure."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    model = os.environ.get("GEMINI_MODEL_FALLBACK", "gemini-2.5-flash")
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        if response:
            text = getattr(response, "text", None)
            if text:
                return str(text).strip()
            if hasattr(response, "candidates") and response.candidates:
                c = response.candidates[0]
                if hasattr(c, "content") and c.content and hasattr(c.content, "parts"):
                    for p in c.content.parts:
                        if hasattr(p, "text") and p.text:
                            return str(p.text).strip()
        return None
    except Exception:
        return None


def call_openai_compatible(prompt: str) -> str | None:
    """Call OpenAI-compatible API (DeepSeek/OpenAI/国产模型等)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    base_url = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    model = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        if response.choices:
            return response.choices[0].message.content.strip()
        return None
    except Exception:
        return None


def write_result(result: str) -> None:
    """Write result to ai_review_result.txt and GITHUB_STEP_SUMMARY."""
    with open("ai_review_result.txt", "w", encoding="utf-8") as f:
        f.write(result)

    if GITHUB_STEP_SUMMARY:
        with open(GITHUB_STEP_SUMMARY, "a", encoding="utf-8") as f:
            f.write("## AI 代码审查\n\n")
            f.write(result)
            f.write("\n")


def main() -> int:
    files, diff = get_code_diff()
    if not files:
        result = "本次 PR 无 Python/JavaScript/CSS 文件变更，跳过 AI 审查。"
        write_result(result)
        return 0

    prompt = build_prompt(files, diff)

    # 优先使用 OpenAI 兼容接口（DeepSeek/OpenAI/国产模型等），否则用 Gemini
    result = call_openai_compatible(prompt)
    if result is None:
        result = call_gemini(prompt)
    if result is None:
        result = "⚠️ AI 审查未执行：请配置 `OPENAI_API_KEY`（DeepSeek 等）或 `GEMINI_API_KEY`。"

    write_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
