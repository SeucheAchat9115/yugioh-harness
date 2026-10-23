"""Provider-specific network work stays outside harness engine execution."""
import json
import os
import subprocess
import sys
from urllib.parse import urlparse

class OpenAICompatible:
    """A fresh tool-free HTTP request per call, no history or automatic retries."""
    def __init__(self, endpoint="https://api.openai.com/v1/chat/completions", *,
                 key_env="OPENAI_API_KEY", timeout_seconds=90, max_output_tokens=512,
                 referee_output_tokens=1024, token_parameter="max_completion_tokens"):
        url=urlparse(endpoint)
        if url.scheme!="https" and not (url.scheme=="http" and url.hostname in {"localhost","127.0.0.1","::1"}):
            raise ValueError("Use HTTPS or a local test endpoint")
        if url.username or url.password:
            raise ValueError("Credentials belong in the configured environment variable")
        if type(timeout_seconds) is not int or not 1<=timeout_seconds<=120:
            raise ValueError("Timeout must fit the 1-120 second harness deadline")
        if token_parameter not in {"max_completion_tokens","max_tokens"}:
            raise ValueError("Unsupported provider token-limit field")
        if any(type(v) is not int or v<1 for v in (max_output_tokens,referee_output_tokens)):
            raise ValueError("Positive output token budgets required")
        self.config=dict(endpoint=endpoint,key_env=key_env,timeout_seconds=timeout_seconds,
                         max_output_tokens=max_output_tokens,referee_output_tokens=referee_output_tokens,
                         token_parameter=token_parameter)
        self.timeout_seconds=timeout_seconds
        self.boundary={"method":"context-only","parent_history":False,"tools":[],"filesystem":False,
                       "evidence":"Fresh bounded HTTP worker sends only archived messages, offers no tools and inherits no conversation."}

    def preflight(self, options):
        if not isinstance(options,dict):
            raise ValueError("Provider options must be a JSON object")
        if not os.environ.get(self.config["key_env"]):
            raise ValueError("Configured model API key is unavailable")
        if {"messages","model","tools","tool_choice","stream","response_format",
            "max_tokens","max_completion_tokens"} & set(options):
            raise ValueError("Options cannot replace messages or isolation/output controls")

    def __call__(self,model,request,*,role,options):
        self.preflight(options)
        if not os.environ.get(self.config["key_env"]):
            raise ValueError("Configured model API key is unavailable")
        forbidden={"messages","model","tools","tool_choice","stream","response_format",
                   "max_tokens","max_completion_tokens"}
        if forbidden & set(options):
            raise ValueError("Options cannot replace messages or isolation/output controls")
        payload={**self.config,"model":model,"request":request,"options":options}
        if role=="referee":payload["max_output_tokens"]=self.config["referee_output_tokens"]
        # subprocess.run kills and waits for the local worker on timeout; no leaked
        # request thread may mutate state. Remote billing on a timeout stays unknown.
        done=subprocess.run([sys.executable,"-m","yugioh_benchmark.transport_worker"],
            input=json.dumps(payload),text=True,encoding="utf-8",capture_output=True,
            timeout=self.timeout_seconds,check=False)
        try:return json.loads(done.stdout)
        except (ValueError,TypeError):raise RuntimeError("Provider worker returned no valid record") from None
