"""
A simple multi-step reasoning agent: Plan -> Execute -> Verify (with retries).

Python solves the supported problem types exactly.
Anything else goes to a local LLM (Ollama), if one is running.
"""
import ast
import json
import operator
import os
import re

import requests

from prompts import EXECUTOR, PLANNER, VERIFIER

OLLAMA_URL = "http://localhost:11434/api/generate"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")      # change if Groq retires it
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "ten": 10}
SLOT = r"(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})"
OFF_ON = r"(gets?|got|getting)\s+(off|on)|board\w*"   # "12 passengers get off", "8 get on"
TAKE = r"giv\w*|gave|ate|eat\w*|los\w*|sold|sell\w*|spen\w*|used|broke|paid|donat\w*"
ADD = r"gets?(?!\s+(?:off|on)\b)|got(?!\s+(?:off|on)\b)|buy\w*|bought|f(?:i|ou)nds?|found|receiv\w*|won|earn\w*|collect\w*"


LAST_LLM_ERROR = {"message": ""}
LAST_EXPRESSION = {"value": None}


def llm_status():
    """Short text for the app: which LLM will be used."""
    if os.getenv("OPENAI_API_KEY"):
        return f"OpenAI ({OPENAI_MODEL})"
    if os.getenv("GROQ_API_KEY"):
        return f"Groq ({GROQ_MODEL})"
    return "No API key found, so the agent will try local Ollama"


# ---------- Small helpers ----------
def minutes(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m


def nice(x):
    return str(int(x)) if float(x).is_integer() else str(round(x, 2))


OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.USub: operator.neg}


def calc(expr):
    """Safely work out + - * / ( ) with the right order of operations."""
    def ev(n):
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.BinOp):
            return OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp):
            return OPS[type(n.op)](ev(n.operand))
        raise ValueError("not maths")
    return ev(ast.parse(expr, mode="eval").body)


def ask_llm(prompt):
    try:
        return _ask_llm(prompt)
    except Exception as e:
        text = str(e)
        if "401" in text:
            text = "The API key was rejected (401). Copy the key again and check for extra spaces."
        elif "404" in text:
            var = "OPENAI_MODEL" if os.getenv("OPENAI_API_KEY") else "GROQ_MODEL"
            text = f"Model not found (404). Set {var} to a model listed in your account."
        elif "11434" in text:
            text = "No OPENAI_API_KEY or GROQ_API_KEY is set, and Ollama isn't running on this computer."
        elif "429" in text:
            text = "Rate limit or quota reached (429). Wait a minute, or check your API credits/billing."
        LAST_LLM_ERROR["message"] = text
        raise


def _chat_api(url, key, model, prompt):
    """OpenAI and Groq use the same request format."""
    r = requests.post(url, headers={"Authorization": f"Bearer {key}"},
                      json={"model": model, "temperature": 0,
                            "messages": [{"role": "user", "content": prompt}]},
                      timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _ask_llm(prompt):
    """Use OpenAI if OPENAI_API_KEY is set, else Groq if GROQ_API_KEY is set, else local Ollama."""
    if os.getenv("OPENAI_API_KEY"):
        return _chat_api("https://api.openai.com/v1/chat/completions", os.getenv("OPENAI_API_KEY"),
                         OPENAI_MODEL, prompt)
    if os.getenv("GROQ_API_KEY"):
        return _chat_api("https://api.groq.com/openai/v1/chat/completions", os.getenv("GROQ_API_KEY"),
                         GROQ_MODEL, prompt)
    r = requests.post(OLLAMA_URL, json={"model": "llama3", "prompt": prompt,
                                        "stream": False}, timeout=60)
    return r.json()["response"]


def read_json(text):
    return json.loads(re.search(r"\{.*\}", text, re.S).group(0))


FRACTIONS = {"half": 1 / 2, "one-third": 1 / 3, "one third": 1 / 3, "a third": 1 / 3,
             "a quarter": 1 / 4, "one-fourth": 1 / 4, "two-thirds": 2 / 3}


def story_actions(q):
    """
    Find each action in order, e.g.
    'sells half' -> (-1, half), 'gives 5' -> (-1, 5), '12 passengers get off' -> (-1, 12).
    Returns None if any number in the question isn't explained by an action,
    so the agent says "could not solve" instead of guessing.
    """
    amount = r"(" + "|".join(FRACTIONS) + r"|\d+%|\d+|" + "|".join(WORDS) + r")(?!\w)"
    found = {}  # position of the amount -> (sign, amount text, how sure)

    # "<action> ... <amount>", e.g. "gives 5", "sells half of them"
    for m in re.finditer(r"\b(" + TAKE + "|" + ADD + r")\s+(?:[a-z]+\s+){0,3}?" + amount, q):
        sign = -1 if re.fullmatch(TAKE, m.group(1)) else 1
        found[m.start(2)] = (sign, m.group(2), 2)
    # "<amount> ... get off / get on", e.g. "half of the passengers get off"
    for m in re.finditer(amount + r"\s+(?:[a-z]+\s+){0,3}?(?:" + OFF_ON + r")\b", q):
        sign = -1 if m.group(3) == "off" else 1
        found[m.start(1)] = (sign, m.group(1), 2)
    # "and <number>" repeats the last action, e.g. "sold 18 in the morning and 12 in the evening"
    for m in re.finditer(r"\band\s+(\d+)\b", q):
        found.setdefault(m.start(1), (0, m.group(1), 1))

    actions, last = [], 0
    for pos in sorted(found):
        sign, text, _ = found[pos]
        if sign == 0:
            if last == 0:
                continue
            sign = last
        actions.append((pos, sign, text))
        last = sign
    if not actions:
        return None

    # Safety check: every amount after the starting one must belong to an action
    amounts = [m.start(1) for m in re.finditer(r"(?<![\w-])" + amount, q)]
    used = {pos for pos, _, _ in actions}
    if any(pos not in used for pos in amounts[1:]):
        return None
    return [(sign, text) for _, sign, text in actions]


def apply(amount, sign, text):
    """Apply one action. Fractions and % are taken from the current amount."""
    if text in FRACTIONS:
        change = amount * FRACTIONS[text]
    elif text.endswith("%"):
        change = amount * int(text[:-1]) / 100
    else:
        change = int(text) if text.isdigit() else WORDS[text]
    return amount + sign * change, change


# ---------- 1. Plan ----------
def pure_expression(q):
    """Return the expression if the question is ONLY maths, e.g. 'What is 12 * 4 / 3?'."""
    q = re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", "*", q.lower()).replace("÷", "/")
    expr = re.sub(r"\b(what|is|calculate|compute|find|the|value|of)\b|[?=:]", " ", q).strip()
    if re.fullmatch(r"[\d\.\s+\-*/()]+", expr) and re.search(r"\d\s*[-+*/]\s*\(?\d", expr):
        return expr
    return None


def plan(question):
    q = question.lower()
    # Clear-cut types: solved exactly in Python
    if re.search(SLOT, question):
        return "scheduling", ["Find the meeting length", "Measure each slot", "Keep slots that are long enough"]
    if len(re.findall(r"\d{1,2}:\d{2}", question)) == 2 and re.search(r"how long|duration|how much time", q):
        return "time", ["Convert both times to minutes", "Subtract (add 24 h if negative)", "Convert to hours and minutes"]
    if re.search(r"\d+(\s*,\s*\d+){2,}\s*,\s*(_|\?)", question):
        return "sequence", ["Check the gaps between numbers", "Check the ratios", "Continue the pattern"]
    if pure_expression(question):
        return "arithmetic", ["Find the expression", "Apply order of operations", "Give the result"]

    # Everything else: ask the LLM
    try:
        steps = [s.strip("- ").strip() for s in ask_llm(PLANNER.format(question=question)).splitlines()
                 if s.strip().startswith("-")]
        return "llm", steps
    except Exception:
        pass

    # No LLM reachable: fall back to simple keyword rules
    if re.search(r"twice|times as many|more \w+ than", q):
        return "word", ["Find the first amount", "Work out the second amount", "Add them if a total is asked"]
    if re.search(r"\b(left|now|remain\w*|have|has)\b", q) and story_actions(q):
        return "story", ["Find the starting amount", "Apply each action in order", "Give the result"]
    return "unknown", []


# ---------- 2. Execute ----------
def execute(question, kind, steps, feedback=""):
    q = question.lower()

    if kind == "arithmetic":
        expr = pure_expression(question)
        return nice(calc(expr)), f"{expr} = {nice(calc(expr))}"

    if kind == "word":
        base = int(re.search(r"\d+", q).group())
        if "twice" in q:
            other, how = base * 2, f"{base} x 2"
        elif m := re.search(r"(\d+|\w+) times as many", q):
            n = int(m.group(1)) if m.group(1).isdigit() else WORDS[m.group(1)]
            other, how = base * n, f"{base} x {n}"
        else:
            n = int(re.search(r"(\d+) more", q).group(1))
            other, how = base + n, f"{base} + {n}"
        total = any(w in q for w in ["total", "altogether", "in all"])
        result = base + other if total else other
        unit = re.search(r"how many (\w+)", q)
        unit = f" {unit.group(1)}" if unit and unit.group(1) not in ("does", "do") else ""
        working = f"First = {base}; Second = {how} = {other}" + (f"; Total = {result}" if total else "")
        return f"{result}{unit}", working

    if kind == "story":
        word = re.search(r"\b(\d+|" + "|".join(WORDS) + r")\b", q).group(1)
        amount = int(word) if word.isdigit() else WORDS[word]
        steps = [f"Start = {amount}"]
        for sign, text in story_actions(q):
            new, change = apply(amount, sign, text)
            steps.append(f"{'-' if sign < 0 else '+'}{text} ({nice(change)}) = {nice(new)}")
            amount = new
        unit = re.search(r"how many (\w+)", q)
        unit = f" {unit.group(1)}" if unit and unit.group(1) not in ("does", "do", "will", "are") else ""
        return f"{nice(amount)}{unit}", "; ".join(steps)

    if kind == "sequence":
        nums = [int(n) for n in re.findall(r"\d+", question)]
        gaps = [b - a for a, b in zip(nums, nums[1:])]
        if len(set(gaps)) == 1:
            return str(nums[-1] + gaps[0]), f"Gap is always {gaps[0]}"
        ratio = nums[1] / nums[0]
        if all(b == a * ratio for a, b in zip(nums, nums[1:])):
            return nice(nums[-1] * ratio), f"Each number is x{nice(ratio)}"
        step = gaps[1] - gaps[0]
        return str(nums[-1] + gaps[-1] + step), f"Gaps {gaps} grow by {step}"

    if kind == "time":
        start, end = [minutes(t) for t in re.findall(r"\d{1,2}:\d{2}", question)]
        diff = (end - start) % (24 * 60)
        h, m = divmod(diff, 60)
        answer = (f"{h} hours " if h else "") + (f"{m} minutes" if m or not h else "")
        return answer.strip(), f"{end} - {start} = {diff} minutes"

    if kind == "scheduling":
        dur = re.search(r"(\d+)\s*(minute|hour)", q)
        need = int(dur.group(1)) * (60 if dur.group(2) == "hour" else 1)
        slots = re.findall(SLOT, question)
        fit = [f"{a}–{b}" for a, b in slots if minutes(b) - minutes(a) >= need]
        working = "; ".join(f"{a}–{b} = {minutes(b) - minutes(a)} min" for a, b in slots)
        return (" and ".join(fit) or "No slots fit"), f"Need {need} min; {working}"

    if kind == "llm":
        try:
            reply = read_json(ask_llm(EXECUTOR.format(
                question=question, plan="\n".join(steps),
                feedback=f"Your previous answer was wrong: {feedback}. Fix it." if feedback else "")))
            answer, working = str(reply["answer"]), str(reply["working"])
            # Re-calculate the LLM's expression in Python so the arithmetic is exact
            if reply.get("expression"):
                try:
                    LAST_EXPRESSION["value"] = calc(str(reply["expression"]).replace("×", "*").replace("÷", "/"))
                    working += f"; Python check: {reply['expression']} = {nice(LAST_EXPRESSION['value'])}"
                except Exception:
                    pass
            return answer, working
        except Exception:
            pass
    return None, "Could not solve this question"


# ---------- 3. Verify ----------
def verify(question, kind, answer):
    """Check the answer a different way from how it was found."""
    if answer is None:
        return False, "No answer"
    q = question.lower()
    try:
        if kind == "time":
            start, end = [minutes(t) for t in re.findall(r"\d{1,2}:\d{2}", question)]
            h = re.search(r"(\d+) hour", answer)
            m = re.search(r"(\d+) minute", answer)
            total = (int(h.group(1)) if h else 0) * 60 + (int(m.group(1)) if m else 0)
            return (start + total) % 1440 == end, "start + duration should equal end"

        if kind == "scheduling":
            need = int(re.search(r"(\d+)\s*(minute|hour)", q).group(1))
            need *= 60 if "hour" in q else 1
            for a, b in re.findall(SLOT, question):
                listed = f"{a}–{b}" in answer
                long_enough = minutes(b) - minutes(a) >= need
                if listed != long_enough:
                    return False, f"Slot {a}–{b} is wrongly {'listed' if listed else 'missing'}"
            return True, "every slot checked"

        if kind == "sequence":
            nums = [int(n) for n in re.findall(r"\d+", question)] + [float(answer)]
            gaps = [b - a for a, b in zip(nums, nums[1:])]
            ok = (len(set(gaps)) == 1 or len({b / a for a, b in zip(nums, nums[1:])}) == 1
                  or len({b - a for a, b in zip(gaps, gaps[1:])}) == 1)
            return ok, "pattern continues with the answer"

        if kind == "arithmetic":
            # Re-calculate with Python's own eval (only digits and + - * / ( ) are allowed)
            expr = re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", "*", q).replace("÷", "/")
            expr = max(re.findall(r"[\d\.\s+\-*/()]+", expr), key=len).strip()
            expected = eval(expr, {"__builtins__": {}})
            return abs(float(answer) - expected) < 1e-9, f"re-calculated {expr} = {nice(expected)}"

        if kind == "story":
            # Replay each action and make sure nothing impossible happens on the way
            word = re.search(r"\b(\d+|" + "|".join(WORDS) + r")\b", q).group(1)
            amount = int(word) if word.isdigit() else WORDS[word]
            for sign, text in story_actions(q):
                amount, _ = apply(amount, sign, text)
                if amount < 0:
                    return False, "the amount went below 0"
                if amount != int(amount):
                    return False, "items can't be split (e.g. half of 7)"
            return abs(float(re.search(r"-?\d+(\.\d+)?", answer).group()) - amount) < 1e-9, "replayed every step"

        if kind == "word":
            value = float(re.search(r"-?\d+(\.\d+)?", answer).group())
            return value >= 0, "a count can't be negative"

        if kind == "llm":
            value = LAST_EXPRESSION["value"]
            number = re.search(r"-?\d+(\.\d+)?", answer)
            if value is not None and number and abs(float(number.group()) - value) > 1e-6:
                return False, f"your expression gives {nice(value)} but your answer says {number.group()}"
            reply = read_json(ask_llm(VERIFIER.format(question=question, answer=answer)))
            return bool(reply["passed"]), reply.get("issue", "")
    except Exception as e:
        return False, f"Check failed: {e}"
    return False, "Unknown problem type"


# ---------- The loop ----------
def solve(question, max_retries=2):
    LAST_LLM_ERROR["message"] = ""
    kind, steps = plan(question)
    feedback, attempts = "", []

    for retry in range(max_retries + 1):
        LAST_EXPRESSION["value"] = None
        answer, working = execute(question, kind, steps, feedback)
        passed, note = verify(question, kind, answer)
        attempts.append({"answer": answer, "passed": passed, "note": note})

        if passed:
            return {"answer": answer, "status": "success", "explanation": working,
                    "llm_error": LAST_LLM_ERROR["message"],
                    "debug": {"type": kind, "plan": steps, "retries": retry, "attempts": attempts,
                              "llm": llm_status(), "llm_error": LAST_LLM_ERROR["message"]}}

        # Python solvers give the same answer every time, so only retry with the LLM.
        if kind not in ("llm",):
            break
        feedback = note

    if LAST_LLM_ERROR["message"]:
        note = f"The LLM could not be reached: {LAST_LLM_ERROR['message']}"
    return {"answer": "Could not solve this question", "status": "failed",
            "explanation": note, "llm_error": LAST_LLM_ERROR["message"],
            "debug": {"type": kind, "plan": steps, "retries": len(attempts) - 1, "attempts": attempts,
                      "llm": llm_status(), "llm_error": LAST_LLM_ERROR["message"]}}
