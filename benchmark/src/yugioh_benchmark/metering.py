"""Observed call timing and provider usage; unavailable cost never becomes zero."""
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import math
from statistics import median
from time import perf_counter
from .kpis import digest

def _amount(value):
    if isinstance(value, bool):
        raise ValueError("Invalid monetary value")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid monetary value") from None
    if not result.is_finite() or result < 0:
        raise ValueError("Prices/costs must be finite and nonnegative")
    return result

def validate_prices(prices):
    if not isinstance(prices, dict):
        raise ValueError("Price book must be an object keyed by exact model ID")
    for model,rate in prices.items():
        if not isinstance(model,str) or not model.strip():
            raise ValueError("Exact model ID is required for pricing")
        if (not isinstance(rate, dict) or not rate.get("source") or not rate.get("effective_date")
                or any(k not in rate for k in ("input_usd_per_million","output_usd_per_million"))):
            raise ValueError("Pin price source/date and input/output rates")
        allowed={"source","effective_date","input_usd_per_million","output_usd_per_million","cached_input_usd_per_million"}
        if set(rate)-allowed:
            raise ValueError("Unknown price field; use the pricing schema")
        if not isinstance(rate["source"],str):
            raise ValueError("Price source must be a string")
        date.fromisoformat(rate["effective_date"])
        for k, v in rate.items():
            if k.endswith("_usd_per_million"):
                if type(v) not in (int,float):
                    raise ValueError("Price rates must be JSON numbers")
                _amount(v)
    return deepcopy(prices)

def normalize_usage(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Provider usage must be an object")
    usage = {}
    for name in ("input_tokens","output_tokens","total_tokens","cached_input_tokens","reasoning_tokens"):
        n = value.get(name)
        if n is not None and (type(n) is not int or n < 0):
            raise ValueError("Token counts must be reported nonnegative integers")
        usage[name] = n
    inp, out = usage["input_tokens"], usage["output_tokens"]
    if inp is not None and out is not None:
        if usage["total_tokens"] is not None and usage["total_tokens"] != inp + out:
            raise ValueError("Inconsistent provider token total")
        usage["total_tokens"] = inp + out
    for part, whole in (("cached_input_tokens","input_tokens"),("reasoning_tokens","output_tokens")):
        if usage[part] is not None and usage[whole] is not None and usage[part] > usage[whole]:
            raise ValueError("Token subcount exceeds reported total")
    return usage

def cost_for(model, usage, prices, billed=None):
    if billed is not None:
        return {"usd": str(_amount(billed)), "basis":"provider_reported", "pricing_sha256":None}
    rate = prices.get(model)
    if rate is None or usage is None or any(usage[k] is None for k in ("input_tokens","output_tokens")):
        return {"usd":None,"basis":"unavailable","pricing_sha256":None}
    cached = usage["cached_input_tokens"]
    input_rate = _amount(rate["input_usd_per_million"])
    cache_rate = _amount(rate.get("cached_input_usd_per_million", input_rate))
    if cached is None and cache_rate != input_rate:
        return {"usd":None,"basis":"unavailable_cached_usage","pricing_sha256":digest(rate)}
    cached = cached or 0
    # Reasoning tokens are a subset of output, never charged twice.
    amount = ((usage["input_tokens"]-cached)*input_rate + cached*cache_rate
              + usage["output_tokens"]*_amount(rate["output_usd_per_million"])) / Decimal(1_000_000)
    return {"usd":str(amount),"basis":"price_book_estimate","pricing_sha256":digest(rate)}

class Meter:
    def __init__(self, prices=None, clock=perf_counter):
        self.prices = validate_prices(prices or {})
        self.clock = clock
        self.calls = []

    def call(self, transport, model, request, *, case_id, role, options=None):
        record = {"case_id":case_id,"role":role,"requested_model":model,
                  "request_sha256":digest(request),"options_sha256":digest(options or {}),
                  "started_at":datetime.now(timezone.utc).isoformat()}
        start = self.clock()
        result = None
        error = None
        try:
            result = transport(model, deepcopy(request), role=role, options=deepcopy(options or {}))
            if not isinstance(result, dict):
                raise ValueError("Transport response must be an object")
            record["reported_model"] = result.get("reported_model")
            record["usage"] = normalize_usage(result.get("usage"))
            record["pricing_model"] = result.get("reported_model") or model
            record["cost"] = cost_for(record["pricing_model"], record["usage"], self.prices, result.get("cost_usd"))
            if result.get("error"):
                if result["error"]=="timeout":
                    raise TimeoutError("Provider call timed out")
                raise RuntimeError("Provider rejected the request or returned no text")
            if not isinstance(result.get("response"), str) or not result["response"].strip():
                raise ValueError("Transport returned no response")
        except Exception as exc:
            error = exc
            record["error_type"] = type(exc).__name__  # Never store credentials/server error text.
        finally:
            elapsed = self.clock() - start
            if not math.isfinite(elapsed) or elapsed < 0:
                raise ValueError("Invalid monotonic timing")
            record.update(finished_at=datetime.now(timezone.utc).isoformat(),
                          elapsed_seconds=elapsed,status="failed" if error else "completed")
            record.setdefault("usage", None)
            record.setdefault("cost", {"usd":None,"basis":"unavailable","pricing_sha256":None})
            self.calls.append(record)
        if error:
            raise error
        return result["response"]

def summarize(calls):
    result = {}
    for name, selected in (("evaluation",[c for c in calls if c["role"]=="evaluation"]),
                           ("referee",[c for c in calls if c["role"]=="referee"]),("pipeline",calls)):
        elapsed = sorted(c["elapsed_seconds"] for c in selected)
        costs = [c["cost"]["usd"] for c in selected]
        known = sum((_amount(v) for v in costs if v is not None), Decimal(0))
        result[name] = {"calls":len(selected),"failed_calls":sum(c["status"]=="failed" for c in selected),
                        "total_call_seconds":sum(elapsed),"median_call_seconds":median(elapsed) if elapsed else None,
                        "p95_call_seconds":elapsed[max(0,math.ceil(.95*len(elapsed))-1)] if elapsed else None,
                        "cost_usd":str(known) if selected and all(v is not None for v in costs) else None,
                        "known_cost_subtotal_usd":str(known),"unpriced_calls":sum(v is None for v in costs)}
        result[name]["cost_basis_counts"]={basis:sum(c["cost"]["basis"]==basis for c in selected)
                                           for basis in sorted({c["cost"]["basis"] for c in selected})}
        for key in ("input_tokens","output_tokens","total_tokens","cached_input_tokens","reasoning_tokens"):
            vals = [(c.get("usage") or {}).get(key) for c in selected]
            result[name][key] = sum(vals) if vals and all(v is not None for v in vals) else None
    return result
