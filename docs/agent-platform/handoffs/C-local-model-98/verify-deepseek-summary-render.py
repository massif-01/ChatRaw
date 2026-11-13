"""Check the two reconstructed 103 pre-summary requests without generation."""

import argparse
import copy
import hashlib
import json
import re
import urllib.request
from pathlib import Path


SUCCESS = "(no output)"
SUCCESS_WITH_EXIT = SUCCESS + "\n[exit code: 0]"
COMPLETED = "The approved run completed. Let me verify the actual result:"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def response_block(content):
    return f"<tool_response>\n{content.strip()}\n</tool_response>"


def check_render(prompt, messages):
    cursor = prompt.index("<|im_start|>assistant\n")
    calls = results = reasoning = 0
    completed_index = None
    for index, message in enumerate(messages):
        if message["role"] == "assistant":
            start = prompt.index("<|im_start|>assistant\n", cursor)
            cursor = prompt.index("<|im_end|>", start)
            block = prompt[start:cursor]
            assert message["reasoning"].strip() in block
            assert (message.get("content") or "").strip() in block
            if COMPLETED in (message.get("content") or ""):
                completed_index = index
                assert COMPLETED in block
            reasoning += 1
            offset = 0
            for call in message.get("tool_calls", []):
                function = call["function"]
                start = block.index(f"<function={function['name']}>\n", offset)
                offset = block.index("</function>", start)
                parameters = re.findall(
                    r"<parameter=([^>]+)>\n(.*?)\n</parameter>",
                    block[start:offset],
                    re.DOTALL,
                )
                assert dict(parameters) == json.loads(function["arguments"])
                assert call["id"] not in prompt
                calls += 1
        elif message["role"] == "tool":
            marker = response_block(message["content"])
            cursor = prompt.index(marker, cursor) + len(marker)
            results += 1

    assert calls == results == prompt.count("<tool_response>\n") == 7
    assert reasoning == 6 and completed_index is not None
    assert prompt.endswith("<|im_start|>assistant\n<think>\n")
    return {
        "calls": calls,
        "results": results,
        "reasoning": reasoning,
        "completed_message_index": completed_index,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("request_dir", type=Path)
    parser.add_argument("native_103", type=Path)
    args = parser.parse_args()
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path, body=None):
        target = urllib.request.Request(
            args.base_url.rstrip("/") + path,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with client.open(target, timeout=10) as response:
            return json.load(response)

    def read_body(label):
        return (args.request_dir / f"103-before-summary.{label}.json").read_bytes()

    reconstructed = read_body("request")
    control_bytes = read_body("control")
    explicit_bytes = read_body("explicit-exit0")
    control = json.loads(control_bytes)
    explicit = json.loads(explicit_bytes)
    assert control == {**json.loads(reconstructed), "temperature": 0}
    assert control["stream"] is True and len(control["tools"]) == 31
    assert control["chat_template_kwargs"] == {"enable_thinking": True}

    ledger = json.loads(args.native_103.read_bytes())["events"]
    native_calls = [row["data"] for row in ledger if row["type"] == "tool/call"]
    native_results = [row["data"]["message"] for row in ledger if row["type"] == "tool/result"]
    success = next(
        row["data"]["message"] for row in ledger
        if row["type"] == "tool/result" and row["seq"] == 28
    )
    success_id = success["toolCallId"]
    assert success["isError"] is False and success["content"][0]["text"] == SUCCESS
    approval = next(
        row["data"] for row in ledger
        if row["type"] == "approval/asked" and row["data"]["callId"] == success_id
    )
    assert any(
        row["type"] == "approval/decided" and row["data"]["id"] == approval["id"]
        and row["data"]["outcome"] == "allowed-once"
        for row in ledger
    )
    assert any(
        row["type"] == "job/settled" and row["data"]["detail"] == "exit code: 0"
        and row["data"]["toolCall"]["callId"] == success_id
        for row in ledger
    )

    messages = control["messages"]
    calls = [call for message in messages for call in message.get("tool_calls", [])]
    results = [message for message in messages if message["role"] == "tool"]
    assert [call["id"] for call in calls] == [result["tool_call_id"] for result in results]
    for call, native in zip(calls, native_calls, strict=True):
        function = call["function"]
        assert call["id"] == native["callId"] and function["name"] == native["name"]
        assert json.loads(function["arguments"]) == json.loads(native["arguments"])
    for result, native in zip(results, native_results, strict=True):
        assert result["tool_call_id"] == native["toolCallId"]
        assert result["content"] == "\n".join(block["text"] for block in native["content"])
    success_index, = [i for i, message in enumerate(messages) if message.get("tool_call_id") == success_id]
    changed = copy.deepcopy(control)
    changed["messages"][success_index]["content"] = SUCCESS_WITH_EXIT
    assert explicit == changed

    version = request("/version")["version"]
    report = {
        "server_version": version,
        "reconstructed_request_sha256": sha256(reconstructed),
        "only_changed_json_pointer": f"/messages/{success_index}/content",
        "arms": {},
    }
    renders = []
    prompts = []
    for label, body, raw in (("control", control, control_bytes), ("explicit-exit0", explicit, explicit_bytes)):
        rendered = request("/v1/chat/completions/render", raw)
        tokens = rendered["token_ids"]
        detokenize_body = json.dumps({"model": body["model"], "tokens": tokens}).encode()
        prompt = request("/detokenize", detokenize_body)["prompt"]
        checks = check_render(prompt, body["messages"])
        assert checks["completed_message_index"] > success_index
        report["arms"][label] = {
            **checks,
            "request_sha256": sha256(raw),
            "prompt_token_count": len(tokens),
            "prompt_token_ids_sha256": sha256(json.dumps(tokens, separators=(",", ":")).encode()),
            "rendered_prompt_sha256": sha256(prompt.encode()),
        }
        renders.append(rendered)
        prompts.append(prompt)

    sampling = renders[0]["sampling_params"]
    assert sampling == renders[1]["sampling_params"]
    assert sampling["temperature"] == 0 and sampling["max_tokens"] == 8192
    assert renders[0]["stream_options"] == renders[1]["stream_options"]
    assert prompts[0].count(response_block(SUCCESS)) == 1
    assert prompts[0].replace(response_block(SUCCESS), response_block(SUCCESS_WITH_EXIT), 1) == prompts[1]
    print(json.dumps({**report, "effective_sampling_params": sampling}, indent=2))


if __name__ == "__main__":
    main()
