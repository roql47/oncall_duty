import React, { useState, useRef, useEffect } from 'react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    { from: 'bot', text: '안녕하세요! 궁금한 당직 정보를 입력해 주세요. 예: "오늘 순환기내과 당직 누구야?"' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [updateStatus, setUpdateStatus] = useState('');
  const [useGemini, setUseGemini] = useState(false);
  const chatEndRef = useRef(null);

  // 예제 질문 목록
  const exampleQuestions = [
    '오늘 순환기내과 당직 누구야?',
    '내일 외과 당직의 연락처 알려줘',
    '정형외과 당직의 번호는?',
    '응급의학과 당직 일정 알려줘'
  ];

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text = input) => {
    if (!text.trim()) return;
    
    const userMsg = { from: 'user', text };
    setMessages(msgs => [...msgs, userMsg]);
    setInput('');
    setLoading(true);
    
    try {
      // useGemini 상태에 따라 엔드포인트 선택
      const endpoint = useGemini ? 'rag' : 'chat';
      
      const res = await fetch(`http://127.0.0.1:8080/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(useGemini ? { query: text, max_results: 10 } : { message: text })
      });
      
      if (!res.ok) {
        throw new Error('서버 응답 오류');
      }
      
      const data = await res.json();
      // useGemini 상태에 따라 응답 필드 선택
      const answer = useGemini ? data.answer : data.answer;
      setMessages(msgs => [...msgs, { from: 'bot', text: answer }]);
    } catch (e) {
      setMessages(msgs => [...msgs, { 
        from: 'bot', 
        text: '서버와 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.' 
      }]);
      console.error('Error:', e);
    } finally {
      setLoading(false);
    }
  };

  const updateVectorDB = async () => {
    setUpdateStatus('업데이트 중...');
    try {
      const res = await fetch('http://127.0.0.1:8080/update-vectors');
      const data = await res.json();
      setUpdateStatus(data.message || '업데이트 완료');
      setTimeout(() => setUpdateStatus(''), 3000);
    } catch (e) {
      setUpdateStatus('업데이트 실패');
      setTimeout(() => setUpdateStatus(''), 3000);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') sendMessage();
  };

  const handleExampleClick = (question) => {
    setInput(question);
    sendMessage(question);
  };

  const toggleGemini = () => {
    setUseGemini(!useGemini);
    setMessages([
      { from: 'bot', text: `안녕하세요! ${useGemini ? '일반' : 'Gemini'} 모드로 전환되었습니다. 궁금한 당직 정보를 입력해 주세요.` }
    ]);
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h1>당직 스케줄 벡터 DB 챗봇</h1>
        <div className="update-section">
          <button onClick={updateVectorDB} className="update-button">
            벡터 DB 업데이트
          </button>
          <button onClick={toggleGemini} className={`gemini-toggle ${useGemini ? 'active' : ''}`}>
            {useGemini ? 'Gemini 모드 ON' : '일반 모드'}
          </button>
          {updateStatus && <span className="update-status">{updateStatus}</span>}
        </div>
      </div>
      
      <div className="examples-container">
        <p>예제 질문:</p>
        <div className="examples">
          {exampleQuestions.map((q, i) => (
            <button 
              key={i} 
              className="example-question"
              onClick={() => handleExampleClick(q)}
            >
              {q}
            </button>
          ))}
        </div>
      </div>
      
      <div className="chat-body">
        {messages.map((msg, idx) => (
          <div key={idx} className={`chat-bubble ${msg.from}`}>
            {msg.text && msg.text.split('\n').map((line, i) => (
              <React.Fragment key={i}>
                {line}
                {i < msg.text.split('\n').length - 1 && <br />}
              </React.Fragment>
            ))}
          </div>
        ))}
        {loading && (
          <div className="chat-bubble bot loading">
            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>
      
      <div className="chat-input-area">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="메시지를 입력하세요..."
          disabled={loading}
        />
        <button onClick={() => sendMessage()} disabled={loading || !input.trim()}>
          전송
        </button>
      </div>
    </div>
  );
}

export default App;
