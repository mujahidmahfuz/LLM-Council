# LLM-Council

<p align="center">
  <img src="./assets/banner.png" alt="LLM Council Banner" width="800"/>
</p>

<h1 align="center">🧙‍♂️ LLM-Council — Multi-Model Round-Table Intelligence</h1>
<p align="center">Created by <b>Mujahid Mahfuz</b></p>

<p align="center">
  <a href="https://github.com/mujahidmahfuz/LLM-Council/stargazers">
    <img src="https://img.shields.io/github/stars/mujahidmahfuz/LLM-Council?style=flat-square&color=blue"/>
  </a>
  <a href="https://github.com/mujahidmahfuz/LLM-Council/issues">
    <img src="https://img.shields.io/github/issues/mujahidmahfuz/LLM-Council?style=flat-square"/>
  </a>
  <img src="https://img.shields.io/badge/Status-Active-success?style=flat-square"/>
  <img src="https://img.shields.io/badge/License-Apache%202.0-green?style=flat-square"/>
</p>

---

## 🎯 Overview

**LLM-Council** is a multi-agent AI project where instead of using a single large language model, your request is evaluated by a **council of multiple LLMs**. Each model gives its own opinion, and then a **Judge Model** analyzes all answers and delivers the final synthesized verdict.

This creates a more **accurate, reliable, explainable, and transparent** decision system through structured AI collaboration.

---

## 🧠 System Design

### Round-Table Council (Concept Illustration)





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


## 🏆 Judge Evaluator

context = f"User Question: {prompt}\n\n"
for item in model_responses:
    context += f"Model {item['model']} said:\n{item['answer']}\n\n"

context += "You are the Head Councilor. Pick the best answer and explain why."
decision = await fetch_model_response(client, judge_model, context)


#🖥 Frontend Rendering

## frontend/App.jsx

<div className="grid">
  {responses.map((item, index) => (
    <div key={index} className="card">
      <h3>{item.model}</h3>
      <p>{item.answer}</p>
    </div>
  ))}
</div>


## frontend/App.css

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

# 🚀 Running Locally

## Backend — FastAPI
cd backend
pip install fastapi uvicorn httpx python-dotenv
uvicorn main:app --reload

## Frontend — React + Vite
cd frontend
npm install
npm run dev

## Open in browser:
http://localhost:5173




