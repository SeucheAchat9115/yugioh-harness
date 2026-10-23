"""Private subprocess worker for a bounded OpenAI-compatible, tool-free call."""
import json
import os
import sys
import urllib.request
import urllib.error

def main():
    data = json.load(sys.stdin)
    key = os.environ.get(data["key_env"])
    if not key:
        raise ValueError("Configured model API key is unavailable")
    payload = dict(data["request"])
    payload.pop("tool_choice",None); payload.pop("tools",None)  # No tools are offered.
    payload.update(model=data["model"],stream=False,**data["options"])
    payload[data["token_parameter"]] = data["max_output_tokens"]
    payload["response_format"] = {"type":"json_object"}
    request = urllib.request.Request(data["endpoint"],json.dumps(payload).encode("utf-8"),
        {"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(request, timeout=data["timeout_seconds"]) as response:
        raw = response.read(16*1024*1024+1)
    if len(raw)>16*1024*1024:
        raise ValueError("Provider response exceeds limit")
    body = json.loads(raw)
    usage = body.get("usage")
    normalized = None
    if usage is not None:
        inp = usage.get("input_tokens",usage.get("prompt_tokens"))
        out = usage.get("output_tokens",usage.get("completion_tokens"))
        normalized = {"input_tokens":inp,"output_tokens":out,"total_tokens":usage.get("total_tokens"),
            "cached_input_tokens":(usage.get("prompt_tokens_details",usage.get("input_tokens_details")) or {}).get("cached_tokens"),
            "reasoning_tokens":(usage.get("completion_tokens_details",usage.get("output_tokens_details")) or {}).get("reasoning_tokens")}
    message = (body.get("choices") or [{}])[0].get("message",{})
    result = {"response":message.get("content"),"reported_model":body.get("model"),"usage":normalized}
    if message.get("tool_calls") or not isinstance(result["response"],str):
        result["error"]="invalid_provider_response"
    print(json.dumps(result))

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        timeout=isinstance(exc,TimeoutError) or (isinstance(exc,urllib.error.URLError) and isinstance(exc.reason,TimeoutError))
        print(json.dumps({"error":"timeout" if timeout else "transport_error","usage":None,"response":None}))
        sys.exit(1)
