#!/usr/bin/env python3
"""write_script.py — brief -> narration script, with domain intelligence.

Turns a topic/brief into a beat-timed explainer narration script. Crypto and
AI are first-class: the prompt injects the entity-bank vocabulary so authored
sentences land on drawable words, plus compliance guardrails (no price
predictions, no financial advice, no fabricated stats/dates).

Provider order (local-first, zero funding):
  1. in-process llama.cpp GGUF — NEXSTUDIO_WRITER_GGUF or largest *.gguf under
     ~/.cache/nexstudio/models (needs llama-cpp-python; CPU fine, a 7B Q4
     writes real domain scripts at ~4min/script)
  2. OpenAI-compatible HTTP — NEXSTUDIO_WRITER_BASE_URL (default
     http://127.0.0.1:8787/v1, the repo's NexMind llama.cpp server; LM Studio
     and Ollama speak the same shape) with NEXSTUDIO_WRITER_MODEL; falls
     back to OPENAI_BASE_URL/OPENAI_API_KEY

Usage:
  python3 write_script.py --brief "How liquid staking works on Solana" \
      --seconds 45 --out /tmp/script.txt
  python3 write_script.py --brief "..." --json   # full {title,logline,script}
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

STYLES = json.loads((ROOT / "styles.json").read_text())
BANK = STYLES["entity_bank"]


def _log(msg):
    print(f"[write_script] {msg}", file=sys.stderr)

MODELS_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "nexstudio" / "models"

WRITER_RULES = """\
You write short narration scripts for animated explainer videos.

Domain voice: you are a crypto and AI specialist. You use correct terminology
(wallet, custody, gas, settlement, L2, staking, tokenomics, model weights,
inference, context window, fine-tuning, embeddings, agents) naturally and
precisely — but you always explain the idea, never the jargon alone.

Hard rules — never break these:
- No price predictions, no "will moon", no guaranteed returns. Ever.
- No financial advice: no "buy", "sell", "you should invest". Explain
  mechanisms, not calls to action on assets.
- No fabricated numbers: never invent statistics, dates, funding amounts, or
  percentages. Prefer "record highs" over made-up figures unless given them.
- Speak in present tense, evergreen: scripts must age well.

Craft rules:
- One clear idea per sentence. Sentences run 6-16 words.
- Open by naming the thing plainly, then why it matters, then how it works,
  then what it changes. End on the shift, not a summary.
- Prefer concrete nouns the animation can draw (from the vocabulary list)
  over abstract verbs.
- No questions to the viewer, no "hey guys", no calls to subscribe.
"""


_DOMAIN_TOKENS = {
    "bitcoin", "ethereum", "crypto", "cryptocurrency", "token", "tokens",
    "coin", "blockchain", "chain", "wallet", "stake", "staking", "defi",
    "nft", "dao", "swap", "mint", "minting", "airdrop", "hash", "ledger",
    "liquidity", "yield", "vault", "custody", "mining", "miner", "protocol",
    "rollup", "oracle", "dapp", "web3", "halving", "mempool", "validator",
    "consensus", "seed", "bridge", "tokenomics", "mainnet", "testnet",
    "layer2", "l2", "sidechain", "exchange", "dex", "cex", "cold", "smart",
    "contract", "llm", "ai", "model", "agent", "agents", "neural",
    "embedding", "embeddings", "vector", "prompt", "prompts", "inference",
    "dataset", "gpu", "gpu", "robot", "transformer", "weights",
    "finetuning", "rag", "attention", "temperature", "llama", "mistral",
    "qwen", "deepseek", "gemini", "claude", "gpt", "openai", "anthropic",
    "nvidia", "huggingface", "perplexity", "xai", "groq", "cohere",
    "cursor", "vercel", "ollama", "vllm", "sora", "runway", "midjourney",
    "stability", "copilot", "chatbot", "automation", "ml",
}


def _vocabulary_hint(max_terms: int = 220) -> str:
    """Drawable vocabulary injected into the prompt: crypto+AI keys first, then
    everyday concepts — the writer prefers these words so the explainer can
    always illustrate what is said."""
    crypto_ai, everyday = [], []
    for k in BANK:
        blob = json.dumps(BANK[k])
        if "brand." in blob or _DOMAIN_TOKENS.intersection(k.split("_")):
            crypto_ai.append(k.replace("_", " "))
        else:
            everyday.append(k.replace("_", " "))
    return ("Drawable vocabulary — prefer these concrete terms:\nCRYPTO/AI: "
            + ", ".join(crypto_ai[:max_terms // 2])
            + "\nEVERYDAY: " + ", ".join(everyday[:max_terms // 2]))


def _chat_inprocess(system: str, user: str) -> str | None:
    gguf = os.environ.get("NEXSTUDIO_WRITER_GGUF") or (
        max(glob.glob(str(MODELS_DIR / "*.gguf")), key=os.path.getsize)
        if glob.glob(str(MODELS_DIR / "*.gguf")) else None)
    if not gguf:
        return None
    try:
        from llama_cpp import Llama
    except ImportError:
        return None
    llm = Llama(model_path=gguf, n_ctx=4096, n_threads=max(2, os.cpu_count() - 1),
                verbose=False)
    _log(f"writer model: {Path(gguf).name}")
    out = llm.create_chat_completion(
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.7, max_tokens=900)
    return out["choices"][0]["message"]["content"]


def _chat_http(system: str, user: str) -> str | None:
    base = os.environ.get("NEXSTUDIO_WRITER_BASE_URL",
                          os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8787/v1"))
    model = os.environ.get("NEXSTUDIO_WRITER_MODEL", "local")
    key = os.environ.get("NEXSTUDIO_WRITER_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    try:
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions",
            data=json.dumps({"model": model, "temperature": 0.7, "max_tokens": 900,
                             "messages": [{"role": "system", "content": system},
                                          {"role": "user", "content": user}]}).encode(),
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {key}"} if key else {})})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except Exception:
        return None


def generate(system: str, user: str) -> str:
    # quality-first: a local GGUF (typically a 7B writer model) beats the
    # small always-on NexMind server for domain scripts; when no GGUF is
    # installed, the HTTP server / OPENAI_* path answers instead
    out = _chat_inprocess(system, user)
    if out is None:
        out = _chat_http(system, user)
    if out is None:
        raise RuntimeError(
            "no writer backend: start the NexMind llama.cpp server on :8787, set "
            "NEXSTUDIO_WRITER_GGUF or drop a *.gguf in ~/.cache/nexstudio/models "
            "(in-process llama.cpp), or NEXSTUDIO_WRITER_BASE_URL + "
            "NEXSTUDIO_WRITER_MODEL / OPENAI_* for any OpenAI-compatible endpoint")
    return out


def _extract_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("writer returned no JSON object")
    return json.loads(m.group(0))


# deterministic compliance rails — a small model cannot be trusted to police
# itself, so these fire regardless of what it wrote
_COMPLIANCE = [
    (re.compile(r"\b(buy|sell|invest|accumulate|ape|long|short)\b[^.]*\b(bitcoin|eth|crypto|token|coin|stock|share)s?\b", re.I), "financial-advice"),
    (re.compile(r"\byou (should|could|need to|must)\b[^.]*\b(invest|buy|hold|stake)\b", re.I), "financial-advice"),
    (re.compile(r"\b(will|going to|about to|set to)\b[^.]*\b(moon|skyrocket|explode|rally|pump|crash|soar|x\d+|\d+x)\b", re.I), "price-prediction"),
    (re.compile(r"\b(price|value) (will|is going to|could reach|targets?|hits?)\b", re.I), "price-prediction"),
    (re.compile(r"\$\s?\d[\d,.]*[kmb]?\b", re.I), "invented-figure"),
    (re.compile(r"\b\d+(\.\d+)?\s?%|\bpercent\b", re.I), "invented-figure"),
    (re.compile(r"\b(guaranteed|risk-?free|cant lose|can't lose|sure thing)\b", re.I), "guarantee-claim"),
]


def compliance_flags(script: str) -> list[tuple[str, str]]:
    return [(s, tag) for s in re.split(r"(?<=[.!?])\s+", script)
            for rx, tag in _COMPLIANCE if rx.search(s)]


# uppercase ticker symbols read aloud as the asset name: TTS would otherwise
# say "sole" for SOL, whisper captions "sole", and the solana brand mark
# never picks. Only UPPERCASE forms rewrite — lowercase words stay untouched
_TICKERS = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "USDT": "Tether",
    "USDC": "USD Coin", "DOGE": "Dogecoin", "ADA": "Cardano",
    "DOT": "Polkadot", "LINK": "Chainlink", "AVAX": "Avalanche",
    "LTC": "Litecoin", "XMR": "Monero", "MATIC": "Polygon",
    "SUI": "Sui", "TON": "Toncoin", "TRX": "Tron", "ATOM": "Cosmos",
}
_TICKER_RX = re.compile(r"\b(" + "|".join(map(re.escape, _TICKERS)) + r")\b")


def normalize_tickers(text: str) -> str:
    """Written form -> spoken form ('SOL tokens' -> 'Solana tokens')."""
    return _TICKER_RX.sub(lambda m: _TICKERS[m.group(1)], text)


_MD_LINE = re.compile(r"^\s*(?:#{1,6}\s+|>\s*|[-*+•]\s+|\d{1,3}[.)]\s+)")


def plain_narration(text: str) -> str:
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if re.match(r"^\s*(```|~~~|([-*_])(\s*\2){2,}\s*$)", line):
            continue
        marked = bool(_MD_LINE.match(line)) and not re.match(r"^\s*>", line)
        line = _MD_LINE.sub("", line)
        line = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"`+([^`]+)`+", r"\1", line)
        line = re.sub(r"\*{2,}|_{2,}|~~", "", line)
        line = re.sub(r"(^|[^\w*])\*(?=\S)([^*]*?\S)\*(?![\w*])", r"\1\2", line)
        line = re.sub(r"(^|\s)\*(?=\S)|(?<=\S)\*(?=\s|$|[.,!?;:])", r"\1", line)
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        if marked and line and not re.search(r"[.!?:;,…][\"'”’)\]]*$", line):
            line += "."
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _coverage_report(script: str) -> tuple[str, list[str]]:
    """Sentence-level entity coverage — feedback for a second pass."""
    import make_reel as mr
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    thin = []
    for s in sentences:
        ws = [{"text": w, "start_ms": i * 400, "end_ms": i * 400 + 300}
              for i, w in enumerate(s.split())]
        if not mr.pick_entities(ws, "colour", set()):
            thin.append(s)
    return script, thin


def author_script(brief: str, seconds: int = 45, audience: str = "smart general") -> dict:
    """brief -> {title, logline, script}; outline->draft two-pass so small
    local models explain mechanisms instead of writing fluff; retries once
    when sentences are entity-poor and enforces compliance rules."""
    words_target = int(seconds * 2.4)  # ~145 wpm narration

    # pass 1 — structure: forces mechanism content before marketing language
    # can take over the draft
    outline = _extract_json(generate(WRITER_RULES, (
        f"Brief: {brief}\nAudience: {audience}\n\n"
        "Plan a {secs}-second explainer. Return ONLY JSON: {{"
        "\"title\": str, \"logline\": str, "
        "\"definition\": \"one-sentence plain definition of the thing\", "
        "\"mechanism\": [\"3-5 concrete steps of how it actually works, "
        "each a noun-phrase with real domain terms\"], "
        "\"shift\": \"what this changes for the audience\"}}"
    ).format(secs=seconds)))

    definition = outline.get("definition", "")
    mechanism = outline.get("mechanism", [])
    shift = outline.get("shift", "")

    # pass 2 — draft constrained to the scaffold
    user = (
        f"Brief: {brief}\nAudience: {audience}\n"
        f"Length: about {words_target} words of spoken narration "
        f"({seconds} seconds), 4-8 sentences.\n"
        f"Required structure:\n"
        f"- sentence 1 IS this definition (reworded fine): {definition}\n"
        f"- then one sentence per mechanism step, in order: "
        + " | ".join(f"{i+1}. {s}" for i, s in enumerate(mechanism)) + "\n"
        f"- end on this shift (reworded fine): {shift}\n\n"
        + _vocabulary_hint() +
        "\n\nReturn ONLY JSON: {\"title\": str, \"logline\": str, "
        "\"script\": \"the narration text, plain prose\"}")

    data = _extract_json(generate(WRITER_RULES, user))
    data.setdefault("title", outline.get("title", ""))
    data.setdefault("logline", outline.get("logline", ""))
    data["_outline"] = {"definition": definition, "mechanism": mechanism, "shift": shift}
    script = data.get("script", "").strip()

    # coverage pass: if any sentence draws nothing, retry once with the gaps
    _, thin = _coverage_report(script)
    if thin:
        raw2 = generate(WRITER_RULES, user +
                        "\n\nREVISION NEEDED: these sentences produced no drawable "
                        "imagery — rewrite them using vocabulary terms while keeping "
                        "the same meaning: " + " | ".join(thin))
        try:
            data2 = _extract_json(raw2)
            if data2.get("script"):
                script = data2["script"].strip()
                data = data2
        except Exception:
            pass  # keep first pass

    # compliance rails — rewrite once, then drop flagged sentences rather
    # than publish advice/predictions/fabricated numbers
    flags = compliance_flags(script)
    if flags:
        bad = " | ".join(s.strip() for s, _ in flags)
        try:
            data2 = _extract_json(generate(
                WRITER_RULES,
                user + "\n\nCOMPLIANCE FAILURE: remove or rewrite these "
                       "sentences — no price predictions, no investment advice, "
                       "no invented figures: " + bad))
            if data2.get("script"):
                script = data2["script"].strip()
                data = data2
        except Exception:
            pass
        still = {s.strip() for s, _ in compliance_flags(script)}
        if still:
            script = " ".join(s for s in re.split(r"(?<=[.!?])\s+", script)
                              if s.strip() and s.strip() not in still)
            data["script"] = script
            data["_compliance_dropped"] = sorted(still)
    data["script"] = normalize_tickers(script)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True, help="topic/brief, e.g. 'How liquid staking works on Solana'")
    ap.add_argument("--seconds", type=int, default=45)
    ap.add_argument("--audience", default="smart general")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", help="write script text here (default stdout)")
    a = ap.parse_args()
    data = author_script(a.brief, a.seconds, a.audience)
    script = data.get("script", "")

    if a.json:
        print(json.dumps(data, indent=1))
    elif a.out:
        Path(a.out).write_text(script + "\n")
        print(f"wrote {a.out} ({len(script.split())} words)", file=sys.stderr)
    else:
        print(script)


if __name__ == "__main__":
    main()
