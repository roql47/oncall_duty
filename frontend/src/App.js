import React, { useState, useRef, useEffect } from 'react';
import './App.css';

// UUID v4 생성 함수
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// 환경에 따른 API 기본 URL 설정
const getApiBaseUrl = () => {
  // 환경 변수에서 API URL 가져오기 (최우선)
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }
  
  // 현재 호스트에 따라 자동 설정
  const hostname = window.location.hostname;
  const port = window.location.port;
  
  // 로컬 환경: 항상 localhost:8080 직접 호출
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8080';
  }
  
  // 외부 환경: 포트에 따라 프록시 vs 직접 호출 구분
  if (port === '80' || port === '') {
    // nginx 프록시 사용 (포트 80)
    return '/chatbot';
  } else {
    // FastAPI 서버 직접 호출 (포트 3000 등)
    return `http://${hostname}:8080`;
  }
};

const API_BASE_URL = getApiBaseUrl();

console.log('API Base URL:', API_BASE_URL);

function App() {
  const [messages, setMessages] = useState([
    { from: 'bot', text: '안녕하세요! 궁금한 당직 정보를 입력해 주세요. 예: "오늘 순환기내과 당직 누구야?"', timestamp: new Date() }
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
  const [activeTab, setActiveTab] = useState('chat'); // 새로운 상태 추가
  const [vectorInfo, setVectorInfo] = useState(null);
  const [vectorLoading, setVectorLoading] = useState(false);
  const [departments, setDepartments] = useState([]);
  const [departmentsLoading, setDepartmentsLoading] = useState(false);
  const [apiConnectionError, setApiConnectionError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  // 세션 ID 상태 추가
  const [sessionId, setSessionId] = useState(() => {
    // 로컬 스토리지에서 세션 ID 가져오거나 새로 생성
    const savedSessionId = localStorage.getItem('chatbot_session_id');
    if (savedSessionId) {
      return savedSessionId;
    } else {
      const newSessionId = generateUUID();
      localStorage.setItem('chatbot_session_id', newSessionId);
      return newSessionId;
    }
  });

  // 세션 초기화 함수
  const resetSession = () => {
    const newSessionId = generateUUID();
    setSessionId(newSessionId);
    localStorage.setItem('chatbot_session_id', newSessionId);
    setMessages([]);
    console.log('세션이 초기화되었습니다:', newSessionId);
  };

  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  // 예제 질문 목록
  const exampleQuestions = [
    '오늘 순환기내과 당직 누구야?',
    '내일 외과 당직의 연락처 알려줘',
    '정형외과 당직의 번호는?',
    '응급의학과 당직 일정 알려줘',
    '지금 순환기내과 병동 당직 누구야?'
  ];

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 컴포넌트 마운트 시 부서 목록 가져오기
  useEffect(() => {
    fetchDepartments();
    
    // 5초 후에도 연결되지 않으면 알림 표시
    const connectionTimeout = setTimeout(() => {
      if (departmentsLoading) {
        setApiConnectionError(true);
        console.error('FastAPI 서버 연결 타임아웃');
      }
    }, 5000);
    
    return () => clearTimeout(connectionTimeout);
  }, [departmentsLoading]);

  // 당직 관련 키워드 체크 함수
  const isValidQuery = (text) => {
    const keywords = [
      '당직', '의사', '병원', '스케줄', '일정', '연락처', '번호', 
      '순환기내과', '외과', '정형외과', '응급의학과', '내과', '소아과',
      '오늘', '내일', '명일', '익일', '모레', '어제', '글피', '누구', '언제', '몇시', '시간',
      // 주차 관련 키워드 추가
      '이번주', '다음주', '다다음주', '저번주', '지난주',
      '월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일',
      '담당의', '주치의', '진료', '의료진',
      // 부서 목록 질문 키워드
      '어떤 과', '무슨 과', '어떤 부서', '무슨 부서', '어느 과', '어느 부서',
      '과 목록', '부서 목록', '과 리스트', '부서 리스트', 
      '과가 있', '부서가 있', '과가 뭐', '부서가 뭐',
      '과를 알려', '부서를 알려', '과 알려', '부서 알려',
      '과 종류', '부서 종류', '과명', '부서명',
      '진료과', '진료부서', '어떤 진료과', '무슨 진료과',
      '과 전체', '부서 전체', '모든 과', '모든 부서',
      '과는 뭐', '부서는 뭐', '과는 무엇', '부서는 무엇'
    ];
    
    // 입력 텍스트 정리
    const cleanQuery = text.trim();
    
    // 기본 키워드 체크
    const hasKeyword = keywords.some(keyword => text.includes(keyword));
    
    // 날짜 형식 패턴 체크 (7/25, 2025-07-25, 07-25 등)
    const datePatterns = [
      /\d{4}-\d{1,2}-\d{1,2}/, // 2025-07-25
      /\d{4}\/\d{1,2}\/\d{1,2}/, // 2025/7/25
      /\d{1,2}-\d{1,2}/, // 07-25, 7-25
      /\d{1,2}\/\d{1,2}/, // 7/25, 07/25
      /\d{1,2}월\s*\d{1,2}일/, // 7월 25일
      /\d{1,2}일/, // 25일
      /\d+일\s*(?:후|뒤)/ // 3일 후, 5일 뒤
    ];
    
    const hasDatePattern = datePatterns.some(pattern => pattern.test(text));
    
    // 후속 질문 패턴 체크 ("내일은?", "다음주는?" 등)
    const followUpPatterns = [
      // 기본 후속 질문 패턴
      /^내일은\?*$/,
      /^내일모레는\?*$/,
      /^내일모레\?*$/,
      /^다음주는\?*$/,
      /^이번주는\?*$/,
      /^저번주는\?*$/,
      /^지난주는\?*$/,
      /^어제는\?*$/,
      /^모레는\?*$/,
      /^글피는\?*$/,
      /^다다음주는\?*$/,
      
      // "그럼/그러면" 접두사가 있는 패턴
      /^그럼\s*(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)는\?*/,
      /^그러면\s*(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)는\?*/,
      
      // "당직은" 접미사가 있는 패턴
      /^(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)\s*당직은\?*/,
      /^(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)은\?*/,
      /^(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)\?*$/,
      
      // n일 후/뒤 패턴
      /^\d+일\s*(?:후|뒤).*\?*$/,  // 가장 포괄적인 패턴
      /^그럼\s*\d+일\s*(?:후|뒤).*\?*$/,
      /^그러면\s*\d+일\s*(?:후|뒤).*\?*$/,
      
      // 요일 패턴
      /^(월요일|화요일|수요일|목요일|금요일|토요일|일요일)은\?*$/,
      /^(월요일|화요일|수요일|목요일|금요일|토요일|일요일)\?*$/,
      /^그럼\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)은\?*/,
      /^그러면\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)은\?*/,
      
      // 주차 + 요일 조합 패턴
      /^(이번주|다음주|저번주|지난주|다다음주)\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)은\?*$/,
      /^(이번주|다음주|저번주|지난주|다다음주)\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)\?*$/,
      
      // 간단한 질문 패턴
      /^그날은\?*$/,
      /^언제\?*$/,
      /^몇일\?*$/,
      /^며칠\?*$/
    ];
    
    const isFollowUp = followUpPatterns.some(pattern => pattern.test(cleanQuery));
    
    // 연락처 관련 패턴 체크
    const contactPatterns = [
      /([가-힣]{2,4})\s*(?:의사|선생님|박사)?\s*(?:연락처|전화번호)\s*(?:알려줘|뭐야|는)/,
      /([가-힣]{2,4})\s*(?:연락처|전화번호)/,
      /^연락처\s*알려줘\?*$/,
      /^연락처\s*뭐야\?*$/,
      /^연락처는\?*$/,
      /^전화번호\s*알려줘\?*$/,
      /^전화번호\s*뭐야\?*$/,
      /^전화번호는\?*$/
    ];
    
    const hasContactPattern = contactPatterns.some(pattern => pattern.test(cleanQuery));
    
    return hasKeyword || hasDatePattern || isFollowUp || hasContactPattern;
  };

  // 과명이 포함되어 있는지 체크하는 함수 (기존 유지)
  const hasDepartmentName = (text) => {
    return departments.some(dept => {
      // 전체 부서명이 포함된 경우
      if (text.includes(dept)) {
        return true;
      }
      
      // 부서명에서 핵심 키워드 추출하여 매칭
      const deptKeywords = dept
        .replace(/\([^)]*\)/g, '') // 괄호 안 내용 제거 예: "외과(ER call only)" → "외과"
        .replace(/\s+(당직의|수술의|병동|응급내시경|ER|NICU|중환자실|on call)/g, '') // 후속 키워드 제거
        .trim()
        .split(/\s+/); // 공백으로 분리
      
      // 핵심 키워드가 사용자 텍스트에 포함되어 있는지 확인
      return deptKeywords.some(keyword => {
        if (keyword.length >= 2) { // 2글자 이상의 키워드만 체크
          return text.includes(keyword);
        }
        return false;
      });
    });
  };

  // 정확한 부서 매칭인지 확인하는 함수 (새로 추가)
  const hasExactDepartmentMatch = (text) => {
    return departments.some(dept => {
      // 전체 부서명이 정확히 포함된 경우
      if (text.includes(dept)) {
        return true;
      }
      return false;
    });
  };

  // 애매한 매칭인지 확인하는 함수 (새로 추가)
  const hasAmbiguousMatch = (text) => {
    const matches = findSimilarDepartments(text);
    return matches.length > 1; // 여러 개의 유사한 부서가 있으면 애매한 매칭
  };

  // 비슷한 부서명을 찾는 함수
  const findSimilarDepartments = (text) => {
    if (departments.length === 0) return [];
    
    // 사용자 텍스트에서 과명 추출 (당직, 연락처 등 제외)
    const userKeywords = text
      .replace(/(당직|연락처|번호|누구|의사|담당의|오늘|내일|지금|현재|알려줘|알려주세요)/g, '')
      .trim()
      .split(/\s+/)
      .filter(keyword => keyword.length >= 2);
    
    const similarDepts = [];
    
    departments.forEach(dept => {
      // 부서명에서 핵심 키워드 추출
      const deptCore = dept
        .replace(/\([^)]*\)/g, '') // 괄호 제거
        .replace(/\s+(당직의|수술의|병동|응급내시경|ER|NICU|중환자실|on call)/g, '') // 후속 키워드 제거
        .trim();
      
      // 사용자 키워드가 부서명에 포함되어 있는지 확인
      userKeywords.forEach(userKeyword => {
        if (deptCore.includes(userKeyword) || dept.includes(userKeyword)) {
          if (!similarDepts.includes(dept)) {
            similarDepts.push(dept);
          }
        }
      });
    });
    
    return similarDepts;
  };

  // 당직 관련 질문인지 체크하는 함수
  const isDutyRelatedQuery = (text) => {
    const dutyKeywords = ['당직', '담당의', '의료진'];
    const timeKeywords = ['오늘', '내일', '명일', '익일', '모레', '어제', '글피', '지금', '현재'];
    const questionKeywords = ['누구', '누가', '의사', '연락처', '번호'];
    
    const hasDutyKeyword = dutyKeywords.some(keyword => text.includes(keyword));
    const hasTimeKeyword = timeKeywords.some(keyword => text.includes(keyword));
    const hasQuestionKeyword = questionKeywords.some(keyword => text.includes(keyword));
    
    return hasDutyKeyword || (hasTimeKeyword && hasQuestionKeyword);
  };

  const sendMessage = async (text = input) => {
    if (!text.trim()) return;
    
    console.log('🔗 현재 세션 ID:', sessionId);
    
    const userMsg = { from: 'user', text, timestamp: new Date() };
    setMessages(msgs => [...msgs, userMsg]);
    setInput('');
    setLoading(true);
    
    // 당직 관련 질문인지 먼저 체크
    if (!isValidQuery(text)) {
      const warningMsg = {
        from: 'bot',
        text: '⚠️ 당직 스케줄과 관련된 질문을 해주세요.\n\n예시:\n• "오늘 순환기내과 당직 누구야?"\n• "내일 외과 당직의 연락처는?"\n• "정형외과 당직의 번호 알려줘"\n\n의료진 당직 정보에 대해서만 답변드릴 수 있습니다.',
        timestamp: new Date()
      };
      setMessages(msgs => [...msgs, warningMsg]);
      setLoading(false);
      // input field에 다시 포커스 주기
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
        }
      }, 100);
      return;
    }

    // 클라이언트 정보 수집
    const clientInfo = {
      userAgent: navigator.userAgent,
      platform: navigator.platform,
      language: navigator.language,
      screenSize: `${window.screen.width}x${window.screen.height}`,
      timestamp: new Date().toISOString(),
      referrer: document.referrer,
      url: window.location.href,
    };

    console.log('📤 요청 데이터:', { 
      message: text, 
      session_id: sessionId,
      headers: {
        'X-Session-ID': sessionId,
        'X-Client-Info': JSON.stringify(clientInfo)
      }
    });

    try {
      const res = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-Session-ID': sessionId,
          'X-Client-Info': JSON.stringify(clientInfo),
        },
        body: JSON.stringify({ 
          message: text,
          session_id: sessionId
        }),
      });
      
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      
      const data = await res.json();
      
      // API 연결 성공 시 연결 오류 상태 해제
      setApiConnectionError(false);
      setRetryCount(0);
      
      // 백엔드 응답도 체크해서 적절한 답변이 없을 때 안내
      const response = data.answer;
      const noResultKeywords = [
        '모르겠습니다', '찾을 수 없습니다', '관련 정보가 없습니다', 
        '답변할 수 없습니다', '정보가 부족합니다', '해당하는 정보가 없습니다'
      ];
      
      if (noResultKeywords.some(keyword => response.includes(keyword))) {
        const enhancedResponse = `${response}\n\n💡 다시 시도해보세요:\n• 구체적인 날짜를 포함해서 질문\n• 정확한 과명을 포함해서 질문\n• "벡터 DB 업데이트" 버튼을 눌러 최신 정보 반영`;
        setMessages(msgs => [...msgs, { from: 'bot', text: enhancedResponse, timestamp: new Date() }]);
      } else {
        setMessages(msgs => [...msgs, { from: 'bot', text: response, timestamp: new Date() }]);
      }
    } catch (e) {
      setApiConnectionError(true);
      const errorMsg = e.message.includes('fetch') || e.message.includes('Failed to fetch')
        ? `🚨 FastAPI 서버에 연결할 수 없습니다 (${API_BASE_URL})\n\n📋 해결 방법:\n1. "start_fastapi_debug.bat" 파일을 실행하여 디버그 모드로 서버를 시작하세요\n2. 브라우저에서 http://localhost:8080/departments 에 접속해보세요\n3. 서버 실행 시 오류 메시지가 나오면 스크린샷을 찍어주세요\n\n💡 서버 정상 실행 후 "재연결 시도" 버튼을 클릭하세요.`
        : `서버 오류: ${e.message}`;
      
      setMessages(msgs => [...msgs, { 
        from: 'bot', 
        text: errorMsg,
        timestamp: new Date()
      }]);
      console.error('API 연결 오류 상세:', {
        error: e,
        message: e.message,
        apiUrl: API_BASE_URL,
        timestamp: new Date().toISOString()
      });
    } finally {
      setLoading(false);
      // 메시지 전송 후 input field에 다시 포커스 주기
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
        }
      }, 100);
    }
  };

  // 업데이트 진행 상황 폴링
  const pollUpdateProgress = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/update-progress`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
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
      setApiConnectionError(true);
      setUpdateStatus('❌ 서버 연결 실패');
      setPolling(false);
      setTimeout(() => {
        setUpdateStatus('');
        setUpdateProgress({ status: 'idle', progress: 0, message: '' });
      }, 5000);
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
      const res = await fetch(`${API_BASE_URL}/update-vectors`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data = await res.json();
      
      // API 연결 성공 시 연결 오류 상태 해제
      setApiConnectionError(false);
      setRetryCount(0);
      
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
      setApiConnectionError(true);
      const errorMsg = e.message.includes('fetch') 
        ? '❌ FastAPI 서버에 연결할 수 없습니다. 서버를 실행해주세요.'
        : `❌ 업데이트 실패: ${e.message}`;
      setUpdateStatus(errorMsg);
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

  // 진료과 클릭 핸들러
  const handleDepartmentClick = (departmentName) => {
    const question = `오늘 ${departmentName} 당직 누구야?`;
    setInput(question);
    sendMessage(question);
  };

  // 벡터 정보 가져오기
  const fetchVectorInfo = async () => {
    setVectorLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/vector-info`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setVectorInfo(data);
      // API 연결 성공 시 연결 오류 상태 해제
      setApiConnectionError(false);
      setRetryCount(0);
    } catch (error) {
      console.error('벡터 정보 조회 오류:', error);
      setApiConnectionError(true);
      const errorMsg = error.message.includes('fetch') 
        ? 'FastAPI 서버에 연결할 수 없습니다.'
        : `벡터 정보를 가져올 수 없습니다: ${error.message}`;
      setVectorInfo({
        status: 'error',
        message: errorMsg,
        total_vectors: 0,
        departments: {},
        date_range: {},
        roles: {}
      });
    } finally {
      setVectorLoading(false);
    }
  };

  // 부서 목록 가져오기
  const fetchDepartments = async () => {
    setDepartmentsLoading(true);
    setApiConnectionError(false);
    try {
      const response = await fetch(`${API_BASE_URL}/departments`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      if (data.status === 'success') {
        setDepartments(data.departments);
        setApiConnectionError(false);
        setRetryCount(0);
      } else {
        console.error('부서 목록 조회 실패:', data.message);
        // 백업용 기본 부서 목록
        setDepartments(['순환기내과', '외과', '정형외과', '응급의학과', '내과', '소아과']);
      }
    } catch (error) {
      console.error('부서 목록 조회 오류:', error);
      setApiConnectionError(true);
      // 백업용 기본 부서 목록
      setDepartments(['순환기내과', '외과', '정형외과', '응급의학과', '내과', '소아과']);
    } finally {
      setDepartmentsLoading(false);
    }
  };

  // API 연결 재시도 함수
  const retryApiConnection = async () => {
    setRetryCount(prev => prev + 1);
    await fetchDepartments();
  };

  // 벡터 DB 삭제
  // eslint-disable-next-line no-unused-vars
  const deleteVectorDB = async () => {
    if (!window.confirm('정말로 벡터 DB를 삭제하시겠습니까?\n\n⚠️ 주의사항:\n- 벡터 DB만 삭제되고 실제 스케줄 데이터는 유지됩니다\n- 챗봇 기능을 다시 사용하려면 벡터 DB 업데이트가 필요합니다\n- 이 작업은 되돌릴 수 없습니다')) {
      return;
    }

    setVectorLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/vector-db`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        alert('✅ ' + data.message);
        // 벡터 정보 새로고침
        fetchVectorInfo();
      } else {
        alert('❌ 삭제 실패: ' + data.message);
      }
    } catch (error) {
      console.error('벡터 DB 삭제 오류:', error);
      alert('❌ 벡터 DB 삭제 중 오류가 발생했습니다: ' + error.message);
    } finally {
      setVectorLoading(false);
    }
  };

  // 탭 전환
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (tab === 'vectors' && !vectorInfo) {
      fetchVectorInfo();
    }
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
            <button 
              className={`nav-button ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => handleTabChange('chat')}
            >
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
              </svg>
              <span>채팅</span>
            </button>
          </li>
          <li className="nav-item">
            <button 
              className={`nav-button ${activeTab === 'vectors' ? 'active' : ''}`}
              onClick={() => handleTabChange('vectors')}
            >
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M4 7v10c0 2.21 1.79 4 4 4h8c2.21 0 4-1.79 4-4V7c0-2.21-1.79-4-4-4H8c-2.21 0-4 1.79-4 4zm4 0h8v2H8V7zm0 4h8v2H8v-2zm0 4h5v2H8v-2z"/>
              </svg>
              <span>벡터 정보</span>
            </button>
          </li>
        </ul>
      </div>

      {/* 메인 컨텐츠 */}
      <div className="main-content">
        {activeTab === 'chat' && (
          <>
            <div className="chat-header">
              <div className="header-title">
                💬 당직 스케줄 챗봇
              </div>
              <div className="update-section">
                <button 
                  onClick={resetSession} 
                  className="reset-session-button"
                  title="새로운 대화를 시작합니다"
                >
                  🔄 새 대화
                </button>
                <button 
                  onClick={updateVectorDB} 
                  className="update-button"
                  disabled={polling}
                >
                  DB 업데이트
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
              {/* 워터마크 이미지 */}
              <div 
                className="chat-watermark"
                style={{
                  position: 'fixed',
                  top: '50%',
                  left: '50%',
                  transform: 'translate(-50%, -50%)',
                  opacity: 0.5,
                  pointerEvents: 'none',
                  zIndex: 0
                }}
              >
                <img 
                  src="/images/logo.PNG" 
                  alt="워터마크" 
                  style={{
                    width: '250px',
                    height: '250px',
                    objectFit: 'contain'
                  }}
                />
              </div>
              
              {messages.map((msg, idx) => (
                <div key={idx} className={`message-wrapper ${msg.from}`}>
                  {msg.from === 'bot' && (
                    <div className="profile-image">
                      <img 
                        src="/images/Gwangryong.png" 
                        alt="챗봇 프로필" 
                        loading="eager"
                        decoding="sync"
                      />
                    </div>
                  )}
                  <div className="chat-bubble">
                    {msg.text && msg.text.split('\n').map((line, i) => (
                      <React.Fragment key={i}>
                        {line}
                        {i < msg.text.split('\n').length - 1 && <br />}
                      </React.Fragment>
                    ))}
                  </div>
                  <div className="message-time">
                    {msg.timestamp ? msg.timestamp.toLocaleTimeString('ko-KR', { 
                      hour: '2-digit', 
                      minute: '2-digit', 
                      hour12: false 
                    }) : ''}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="message-wrapper bot">
                  <div className="profile-image">
                    <img 
                      src="/images/Gwangryong.png" 
                      alt="챗봇 프로필" 
                      loading="eager"
                      decoding="sync"
                    />
                  </div>
                  <div className="chat-bubble loading">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
            
            <div className="chat-input-area">
              {apiConnectionError && (
                <div className="input-error-banner">
                  <span>⚠️ FastAPI 서버에 연결할 수 없습니다.</span>
                  <button 
                    className="banner-retry-button"
                    onClick={retryApiConnection}
                    disabled={departmentsLoading}
                  >
                    재연결
                  </button>
                </div>
              )}
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={apiConnectionError ? "서버 연결 후 질문을 입력하세요..." : "궁금한 당직 정보를 입력하세요..."}
                disabled={loading || apiConnectionError}
              />
              <button
                onClick={() => sendMessage()}
                disabled={loading || !input.trim() || apiConnectionError}
                className="send-button"
              >
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                  <path d="M22 2L11 13" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
          </>
        )}

        {activeTab === 'vectors' && (
          <div className="vector-info-container">
            <div className="vector-header">
              <div className="header-title">
                📊 벡터 DB 정보
              </div>
              <div className="vector-actions">
                <button 
                  onClick={fetchVectorInfo}
                  className="refresh-button"
                  disabled={vectorLoading}
                >
                  {vectorLoading ? '새로고침 중...' : '새로고침'}
                </button>
                <button 
                  onClick={deleteVectorDB}
                  className="delete-button"
                  disabled={vectorLoading}
                >
                  🗑️ DB 삭제
                </button>
              </div>
            </div>

            {vectorLoading ? (
              <div className="loading-container">
                <div className="loading-spinner"></div>
                <p>벡터 정보를 불러오는 중...</p>
              </div>
            ) : vectorInfo ? (
              <div className="vector-info-content">
                {vectorInfo.status === 'error' ? (
                  <div className="error-container">
                    <h3>❌ 오류</h3>
                    <p>{vectorInfo.message}</p>
                  </div>
                ) : (
                  <>
                    <div className="stats-grid">
                      <div className="stat-card">
                        <h3>총 벡터 수</h3>
                        <div className="stat-number">{vectorInfo.total_vectors?.toLocaleString()}</div>
                      </div>
                      <div className="stat-card">
                        <h3>메타데이터 수</h3>
                        <div className="stat-number">{vectorInfo.total_metadata?.toLocaleString()}</div>
                      </div>
                      <div className="stat-card">
                        <h3>스케줄 ID 수</h3>
                        <div className="stat-number">{vectorInfo.total_schedule_ids?.toLocaleString()}</div>
                      </div>
                      <div className="stat-card">
                        <h3>벡터 차원</h3>
                        <div className="stat-number">{vectorInfo.vector_dim}</div>
                      </div>
                    </div>

                    {vectorInfo.date_range && Object.keys(vectorInfo.date_range).length > 0 && (
                      <div className="info-section">
                        <h3>📅 날짜 범위</h3>
                        <div className="date-info">
                          <p><strong>시작일:</strong> {vectorInfo.date_range.earliest}</p>
                          <p><strong>종료일:</strong> {vectorInfo.date_range.latest}</p>
                          <p><strong>총 일수:</strong> {vectorInfo.date_range.total_days}일</p>
                        </div>
                      </div>
                    )}

                    {vectorInfo.departments && Object.keys(vectorInfo.departments).length > 0 && (
                      <div className="info-section">
                        <h3>🏥 부서별 통계</h3>
                        <div className="departments-grid">
                          {Object.entries(vectorInfo.departments).map(([dept, count]) => (
                            <div key={dept} className="department-item">
                              <span className="department-name">{dept}</span>
                              <span className="department-count">{count}개</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {vectorInfo.roles && Object.keys(vectorInfo.roles).length > 0 && (
                      <div className="info-section">
                        <h3>👨‍⚕️ 역할별 통계</h3>
                        <div className="roles-grid">
                          {Object.entries(vectorInfo.roles).slice(0, 10).map(([role, count]) => (
                            <div key={role} className="role-item">
                              <span className="role-name">{role}</span>
                              <span className="role-count">{count}개</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {vectorInfo.recent_schedules && vectorInfo.recent_schedules.length > 0 && (
                      <div className="info-section">
                        <h3>🕒 최근 추가된 스케줄</h3>
                        <div className="recent-schedules">
                          {vectorInfo.recent_schedules.map((schedule, idx) => (
                            <div key={idx} className="schedule-item">
                              <div className="schedule-date">{schedule.date}</div>
                              <div className="schedule-department">{schedule.department}</div>
                              <div className="schedule-role">{schedule.role}</div>
                              <div className="schedule-name">{schedule.name}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            ) : (
              <div className="empty-state">
                <p>벡터 정보를 불러오려면 새로고침 버튼을 클릭하세요.</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 우측 사이드바 */}
      <div className="sidebar-right">
        <div className="info-section">
          <h3>조회 가능한 진료과</h3>
          {apiConnectionError && (
            <div className="api-error-notice">
              <div className="error-icon">⚠️</div>
              <div className="error-text">
                <strong>API 연결 실패</strong>
                <p>FastAPI 서버가 실행되지 않았습니다.</p>
                <button 
                  className="retry-button"
                  onClick={retryApiConnection}
                  disabled={departmentsLoading}
                >
                  {departmentsLoading ? '재연결 중...' : '재연결 시도'}
                </button>
                {retryCount > 0 && (
                  <small>재시도 {retryCount}회</small>
                )}
              </div>
            </div>
          )}
          <div className="departments-simple-list">
            {departmentsLoading ? (
              <div className="departments-loading">
                <span>로딩 중...</span>
              </div>
            ) : departments.length > 0 ? (
              departments.map((dept, index) => (
                <div 
                  key={index} 
                  className="department-item-simple"
                  onClick={() => handleDepartmentClick(dept)}
                >
                  {dept}
                </div>
              ))
            ) : (
              <div className="departments-error-simple">
                진료과 목록을 불러올 수 없습니다.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
