# LLM-Council

# 🧙‍♂️ LLM High Council — Multi-Model Round-Table Intelligence System

The **LLM High Council** is a multi-agent AI system where multiple powerful Large Language Models sit like a *round-table council*, each giving their own perspective. A final **Judge Model** evaluates all responses and produces the **best final verdict**, providing more accurate, reliable, and trustworthy reasoning.

---

## 🌀 Concept — Visual Round Table of Models

                   [👨‍⚖️ Judge Model 👑]
                             ▲
                             |
 ┌───────────🧠─────────────┬──────────────🧠──────────────┐
 |                          |                               |

                   ⬇ (Evaluates and synthesizes)
                     👑 Final Verdict Sent to User


> Each AI acts as a council member. Judge compares, selects the best reasoning, and synthesizes the final answer.

---

## 📦 Models Used


---

## 🧠 Backend Logic Key Code — FastAPI Async Multi-Model Pipeline

`backend/main.py`
```python
tasks = [controlled_fetch(model) for model in MODELS]
results = await asyncio.gather(*tasks)
verdict = await get_council_decision(client, request.prompt, results)




