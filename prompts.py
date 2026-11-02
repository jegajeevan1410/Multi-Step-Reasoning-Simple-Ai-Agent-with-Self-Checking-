"""All prompts live here. They are used only when the Python solvers can't answer."""

PLANNER = """You are a planner. Break the question into 2-5 short steps.
Do NOT solve it. Write one step per line, starting with "- ".

Question: {question}
"""

EXECUTOR = """You are a careful solver. Follow the plan and show each calculation.
Rules:
- Apply events in the order they happen. "Half of them", "one-third of the rest" and "25%"
  are taken from the amount at that moment.
- Use the order of operations (brackets, * and /, then + and -).
- Also write ONE arithmetic expression (numbers, + - * / and brackets only) for the final number,
  so the program can double-check it. Leave it empty if the answer is not a number.
Reply ONLY with JSON: {{"working": "...", "expression": "...", "answer": "..."}}

Example:
Question: A shop has 40 chocolates. It sells half, gives away 5, buys 12 more, then sells one-third of the rest. How many are left?
{{"working": "40 - 20 = 20; 20 - 5 = 15; 15 + 12 = 27; 27 - 9 = 18", "expression": "(40 - 40/2 - 5 + 12) * 2/3", "answer": "18 chocolates"}}

Question: {question}
Plan:
{plan}
{feedback}"""

VERIFIER = """You are a checker. Solve the question yourself from scratch,
then compare with the proposed answer.
Reply ONLY with JSON: {{"passed": true or false, "issue": "..."}}

Question: {question}
Proposed answer: {answer}
"""
