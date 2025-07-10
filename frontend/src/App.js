import React, { useState, useRef, useEffect } from 'react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    { from: 'bot', text: '안녕하세요! 궁금한 당직 정보를 입력해 주세요. 예: "오늘 순환기내과 당직 누구야?"' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [updateStatus, setUpdateStatus] = useState('');
  const [updateProgress, setUpdateProgress] = useState({
    status: 'idle',
    progress: 0,
    message: ''
  });
  const [polling, setPolling] = useState(false);

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

  // 당직 관련 키워드 체크 함수
  const isValidQuery = (text) => {
    const keywords = [
      '당직', '의사', '병원', '스케줄', '일정', '연락처', '번호', 
      '순환기내과', '외과', '정형외과', '응급의학과', '내과', '소아과',
      '오늘', '내일', '어제', '누구', '언제', '몇시', '시간',
      '담당의', '주치의', '진료', '의료진'
    ];
    return keywords.some(keyword => text.includes(keyword));
  };

  const sendMessage = async (text = input) => {
    if (!text.trim()) return;
    
    const userMsg = { from: 'user', text };
    setMessages(msgs => [...msgs, userMsg]);
    setInput('');
    setLoading(true);
    
    // 당직 관련 질문인지 먼저 체크
    if (!isValidQuery(text)) {
      const warningMsg = {
        from: 'bot',
        text: '⚠️ 당직 스케줄과 관련된 질문을 해주세요.\n\n예시:\n• "오늘 순환기내과 당직 누구야?"\n• "내일 외과 당직의 연락처는?"\n• "정형외과 당직의 번호 알려줘"\n\n의료진 당직 정보에 대해서만 답변드릴 수 있습니다.'
      };
      setMessages(msgs => [...msgs, warningMsg]);
      setLoading(false);
      return;
    }
    
    try {
      const res = await fetch(`http://127.0.0.1:8080/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });
      
      if (!res.ok) {
        throw new Error('서버 응답 오류');
      }
      
      const data = await res.json();
      
      // 백엔드 응답도 체크해서 적절한 답변이 없을 때 안내
      const response = data.answer;
      const noResultKeywords = [
        '모르겠습니다', '찾을 수 없습니다', '관련 정보가 없습니다', 
        '답변할 수 없습니다', '정보가 부족합니다', '해당하는 정보가 없습니다'
      ];
      
      if (noResultKeywords.some(keyword => response.includes(keyword))) {
        const enhancedResponse = `${response}\n\n💡 다시 시도해보세요:\n• 구체적인 날짜를 포함해서 질문\n• 정확한 과명을 포함해서 질문\n• "벡터 DB 업데이트" 버튼을 눌러 최신 정보 반영`;
        setMessages(msgs => [...msgs, { from: 'bot', text: enhancedResponse }]);
      } else {
        setMessages(msgs => [...msgs, { from: 'bot', text: response }]);
      }
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

  // 업데이트 진행 상황 폴링
  const pollUpdateProgress = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8080/update-progress');
      const progress = await response.json();
      console.log('Progress update:', progress); // 디버깅용 로그
      setUpdateProgress(progress);
      
      if (progress.status === 'running') {
        setTimeout(pollUpdateProgress, 500); // 0.5초마다 확인
      } else if (progress.status === 'completed') {
        setUpdateStatus('✅ 업데이트 완료!');
        setPolling(false);
        setTimeout(() => {
          setUpdateStatus('');
          setUpdateProgress({ status: 'idle', progress: 0, message: '' });
        }, 3000);
      } else if (progress.status === 'error') {
        setUpdateStatus(`❌ 업데이트 실패: ${progress.message}`);
        setPolling(false);
        setTimeout(() => {
          setUpdateStatus('');
          setUpdateProgress({ status: 'idle', progress: 0, message: '' });
        }, 5000);
      }
    } catch (error) {
      console.error('진행 상황 조회 오류:', error);
      setPolling(false);
    }
  };

  const updateVectorDB = async () => {
    const currentDate = new Date();
    const currentYear = currentDate.getFullYear();
    const currentMonth = currentDate.getMonth() + 1;
    
    setUpdateStatus(`${currentYear}년 ${currentMonth}월 데이터 업데이트 중...`);
    setUpdateProgress({ status: 'running', progress: 0, message: '업데이트 시작...' });
    setPolling(true);
    
    try {
      const res = await fetch('http://127.0.0.1:8080/update-vectors');
      const data = await res.json();
      
      // 폴링 시작
      if (data.status === 'started') {
        setTimeout(pollUpdateProgress, 500); // 0.5초 후 첫 번째 폴링
      } else {
        setUpdateStatus(`❌ 업데이트 실패: ${data.message}`);
        setPolling(false);
        setTimeout(() => {
          setUpdateStatus('');
          setUpdateProgress({ status: 'idle', progress: 0, message: '' });
        }, 5000);
      }
    } catch (e) {
      setUpdateStatus('업데이트 실패');
      setPolling(false);
      setTimeout(() => {
        setUpdateStatus('');
        setUpdateProgress({ status: 'idle', progress: 0, message: '' });
      }, 5000);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') sendMessage();
  };

  const handleExampleClick = (question) => {
    setInput(question);
    sendMessage(question);
  };



  return (
    <div className="App">
      {/* 좌측 사이드바 */}
      <div className="sidebar-left">
        <div className="logo-section">
          <h1>🏥 당직 챗봇</h1>
          <p>의료진 당직 스케줄을 쉽게 확인하세요</p>
        </div>
        
        <ul className="nav-menu">
          <li className="nav-item">
            <button className="nav-button active">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
              </svg>
              <span>채팅</span>
            </button>
          </li>
        </ul>
      </div>

      {/* 메인 컨텐츠 */}
      <div className="main-content">
        <div className="chat-header">
          <div className="header-title">
            💬 당직 스케줄 챗봇
          </div>
          <div className="update-section">
            <button 
              onClick={updateVectorDB} 
              className="update-button"
              disabled={polling}
            >
              현재 월 벡터 DB 업데이트
            </button>
            {updateProgress.status === 'running' && (
              <div className="progress-container">
                <div className="progress-bar">
                  <div 
                    className="progress-fill" 
                    style={{ width: `${updateProgress.progress}%` }}
                  />
                </div>
                <span className="progress-text">
                  {updateProgress.message} ({updateProgress.progress}%)
                </span>
              </div>
            )}
            {updateStatus && <span className="update-status">{updateStatus}</span>}
          </div>
        </div>
        
        <div className="examples-container">
          <p>💡 예제 질문:</p>
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
            placeholder="궁금한 당직 정보를 입력하세요..."
            disabled={loading}
          />
          <button
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            className="send-button"
          >
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
              <path d="M22 2L11 13" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </div>

      {/* 우측 사이드바 */}
      <div className="sidebar-right">
        <div className="info-section">
          <h3>📋 사용 가이드</h3>
          <div className="info-card">
            <h4>질문 예시</h4>
            <p>• "오늘 순환기내과 당직 누구야?"<br/>
            • "내일 외과 당직의 연락처 알려줘"<br/>
            • "정형외과 당직의 번호는?"</p>
          </div>

          <div className="info-card">
            <h4>업데이트</h4>
            <p>벡터 DB 업데이트 버튼을 클릭하여 최신 당직 정보를 반영하세요.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
