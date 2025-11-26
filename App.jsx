import {useState} from "react"
import "./App.css"

// IMPORTANT: We will change this URL in Part 2!
const API_URL = "http://127.0.0.1:8000/ask-council";

function App() {
  const [prompt, setPrompt] = useState('')
  // New State structure
  const [responses, setResponses] = useState([])
  const [verdict, setVerdict] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!prompt) return;
    setLoading(true);
    setResponses([]);
    setVerdict('');

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt })
      });
      const data = await res.json();
      
      // Update state with new backend structure
      setResponses(data.individual_responses);
      setVerdict(data.council_verdict);
      
    } catch (error) {
      console.error("Error:", error);
    }
    setLoading(false);
  }

  return (
    <div className="container">
      <h1>🧙‍♂️ The High Council</h1>
      
      <div className="input-area">
        <textarea 
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Ask the council..."
        />
        <button onClick={handleSubmit} disabled={loading}>
          {loading ? "Council is deliberating..." : "Consult Council"}
        </button>
      </div>

      {/* 1. The Verdict (ChatGPT Style - Best Answer) */}
      {verdict && (
        <div className="verdict-card">
          <h2>👑 The Council's Decision</h2>
          <p>{verdict}</p>
        </div>
      )}

      {/* 2. The Individual Opinions */}
      <div className="grid">
        {responses.map((item, index) => (
          <div key={index} className="card">
            <h3>{item.model}</h3>
            <p>{item.answer}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

export default App