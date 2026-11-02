import streamlit as st

from agent import llm_status, solve

st.set_page_config(page_title="Reasoning Agent", page_icon="🧠")
st.title("🧠 Multi-Step Reasoning Agent")
st.caption(f"Plan → Execute → Verify  ·  LLM: {llm_status()}")

question = st.text_input("Your question", placeholder="e.g. 45 - 18 + 6")

if st.button("Solve", type="primary") and question.strip():
    result = solve(question)
    if result.get("llm_error"):
        st.warning(f"⚠️ The LLM didn't respond, so built-in rules were used. Reason: {result['llm_error']}")
    if result["status"] == "success":
        st.success(f"**Answer:** {result['answer']}")
    else:
        st.error(result["answer"])
    st.write("**How:**", result["explanation"])
    with st.expander("Debug info"):
        st.json(result["debug"])
