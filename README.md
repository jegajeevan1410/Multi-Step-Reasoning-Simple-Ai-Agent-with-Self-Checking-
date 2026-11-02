# Simple Multi-Step Reasoning Agent

A small agent that solves math, logic and scheduling questions in three steps, **Plan → Execute → Verify**, and checks its own answer before showing it.

**How it solves questions:**
- Python solves pure maths, number sequences, "how long" time questions and meeting slots exactly.
- Everything else (word problems, stories) goes to the LLM, which also writes one maths expression that Python checks.
- Without an LLM, simple built-in rules handle common word problems.

## How to Run

```bash
pip install -r requirements.txt
python -m streamlit run app.py     # web app at http://localhost:8501
python test.py                     # 19 test questions
```

For other kinds of questions, add an LLM (optional):
- **OpenAI:** in PowerShell run `$env:OPENAI_API_KEY="sk-your_key"` before starting the app.
- **Groq (free):** get a key at console.groq.com/keys, then run `$env:GROQ_API_KEY="gsk_your_key"`.
- **Ollama (local):** run `ollama run llama3`.

## Files

| File | What it does |
|------|--------------|
| `agent.py` | `plan()`, `execute()`, `verify()` and the `solve()` loop |
| `prompts.py` | The three LLM prompts (planner, executor, verifier) |
| `app.py` | Streamlit web page |
| `test.py` | Test questions with expected answers |

## Where Prompts Live

All prompts are in **`prompts.py`**. They're used only for questions the Python code can't solve, through OpenAI (`OPENAI_API_KEY`), Groq (`GROQ_API_KEY`) or Ollama, in that order.

## Assumptions

- Times use 24-hour `HH:MM` format. Slots are written like `09:00–09:30`.
- A meeting fits if the slot is equal to or longer than the meeting.
- If the arrival time is earlier than the departure time, the trip crosses midnight.
- With no API key and no Ollama, unsupported questions return "Could not solve" instead of a guess.

## Prompt Documentation

**Why designed this way**
- One short prompt per step (plan, solve, check), each with one job.
- The executor and verifier reply in JSON, so the code can read them reliably.
- The verifier solves the question again by itself, instead of trusting the executor.
- Python handles only clear-cut question types. Word problems go to the LLM, because keyword rules misread new phrasings.
- The LLM writes an expression that Python calculates. If it doesn't match the LLM's answer, the agent retries.

**What didn't work well**
- One big prompt for everything gave inconsistent answers.
- Adding all numbers when a `+` appeared gave wrong results (`45 - 18 + 6` → 69). A proper expression parser fixed it.
- A verifier that only checked "is it a number?" let wrong answers through.
- Keyword rules for every word problem passed the tests but failed on new phrasings ("one-third" read as "1").

**What I'd improve**
- Support percentages, units and "reverse" word problems.
- Run each LLM answer a few times and keep the most common answer.

## Example Runs

| Question | Answer |
|----------|--------|
| `45 - 18 + 6` | 33 |
| `12 * 4 / 3` | 16 |
| Ravi has 5 pencils and three times as many pens. How many items in total? | 20 items |
| `2, 4, 8, 16, _` | 32 |
| A train leaves at 23:50 and arrives at 00:20. How long is the journey? | 30 minutes |
| A call needs 45 minutes. Slots: 10:00–10:30, 13:15–14:00, 15:00–16:30. | 13:15–14:00 and 15:00–16:30 |

## Author

**V. Jegajeevan**: [GitHub](https://github.com/jegajeevan1410) · [LinkedIn](https://www.linkedin.com/in/jegajeevan1410)
