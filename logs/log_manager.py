#!/usr/bin/env python3
"""
로그 관리 유틸리티 스크립트

사용법:
    python log_manager.py --help
    python log_manager.py --list-logs
    python log_manager.py --view django api 2024-01-15
    python log_manager.py --tail fastapi error
    python log_manager.py --clean --days 30
    python log_manager.py --stats
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

# 현재 스크립트의 디렉토리 경로
SCRIPT_DIR = Path(__file__).resolve().parent
LOGS_DIR = SCRIPT_DIR
PROJECT_ROOT = SCRIPT_DIR.parent

# 로그 타입 정의
LOG_BACKENDS = ['django', 'fastapi', 'system']
LOG_TYPES = {
    'django': ['access', 'api', 'error', 'debug'],
    'fastapi': ['access', 'api', 'chatbot', 'error', 'debug'],
    'system': ['startup', 'performance', 'security']
}

class LogManager:
    """로그 관리 클래스"""
    
    def __init__(self):
        self.logs_dir = LOGS_DIR
    
    def list_logs(self, backend=None, log_type=None, days=7):
        """로그 파일 목록 조회"""
        print(f"\n📋 로그 파일 목록 (최근 {days}일)")
        print("=" * 60)
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for backend_name in LOG_BACKENDS:
            if backend and backend_name != backend:
                continue
                
            backend_dir = self.logs_dir / backend_name
            if not backend_dir.exists():
                continue
                
            print(f"\n🔧 {backend_name.upper()} 백엔드:")
            
            for type_name in LOG_TYPES[backend_name]:
                if log_type and type_name != log_type:
                    continue
                    
                type_dir = backend_dir / type_name
                if not type_dir.exists():
                    continue
                
                print(f"  📁 {type_name}:")
                
                log_files = []
                for log_file in type_dir.glob("*.txt"):
                    file_date = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_date >= cutoff_date:
                        file_size = log_file.stat().st_size
                        log_files.append((log_file, file_date, file_size))
                
                # 날짜순 정렬
                log_files.sort(key=lambda x: x[1], reverse=True)
                
                if log_files:
                    for log_file, file_date, file_size in log_files:
                        size_mb = file_size / (1024 * 1024)
                        print(f"    📄 {log_file.name} ({size_mb:.2f}MB, {file_date.strftime('%Y-%m-%d %H:%M')})")
                else:
                    print(f"    (로그 파일이 없습니다)")
    
    def view_log(self, backend, log_type, date=None, lines=50):
        """로그 파일 내용 조회"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        log_file = self.logs_dir / backend / log_type / f"{backend}_{log_type}_{date}.txt"
        
        if not log_file.exists():
            print(f"❌ 로그 파일을 찾을 수 없습니다: {log_file}")
            return
        
        print(f"\n📖 로그 파일: {log_file}")
        print(f"📅 날짜: {date}, 📊 라인 수: {lines}")
        print("=" * 80)
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                log_lines = f.readlines()
                
            # 마지막 N줄 출력
            start_idx = max(0, len(log_lines) - lines)
            for i, line in enumerate(log_lines[start_idx:], start_idx + 1):
                try:
                    # JSON 로그인 경우 파싱해서 보기 좋게 출력
                    log_data = json.loads(line.strip())
                    timestamp = log_data.get('timestamp', '')
                    level = log_data.get('level', '')
                    message = log_data.get('message', '')
                    
                    # 색상 코드 적용
                    color = self.get_level_color(level)
                    print(f"{i:4d} | {timestamp} | {color}{level:<7}{self.reset_color()} | {message}")
                    
                    # 추가 정보가 있으면 출력
                    extra_info = []
                    if log_data.get('request_id'):
                        extra_info.append(f"ID: {log_data['request_id'][:8]}")
                    if log_data.get('ip_address'):
                        extra_info.append(f"IP: {log_data['ip_address']}")
                    if log_data.get('response_time'):
                        extra_info.append(f"Time: {log_data['response_time']}ms")
                    
                    if extra_info:
                        print(f"     | {' | '.join(extra_info)}")
                    
                except json.JSONDecodeError:
                    # JSON이 아닌 일반 로그는 그대로 출력
                    print(f"{i:4d} | {line.rstrip()}")
                    
        except Exception as e:
            print(f"❌ 로그 파일 읽기 오류: {e}")
    
    def tail_log(self, backend, log_type, lines=50):
        """실시간 로그 모니터링 (tail -f 기능)"""
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = self.logs_dir / backend / log_type / f"{backend}_{log_type}_{today}.txt"
        
        if not log_file.exists():
            print(f"❌ 로그 파일을 찾을 수 없습니다: {log_file}")
            return
        
        print(f"🔄 실시간 로그 모니터링: {log_file}")
        print("📝 Ctrl+C를 눌러 종료합니다.")
        print("=" * 80)
        
        try:
            # tail -f 명령 실행
            if os.name == 'nt':  # Windows
                subprocess.run(['powershell', 'Get-Content', str(log_file), '-Tail', str(lines), '-Wait'], check=True)
            else:  # Unix/Linux
                subprocess.run(['tail', '-f', '-n', str(lines), str(log_file)], check=True)
        except KeyboardInterrupt:
            print("\n\n✅ 로그 모니터링을 종료합니다.")
        except subprocess.CalledProcessError as e:
            print(f"❌ tail 명령 실행 오류: {e}")
    
    def clean_logs(self, days=30, dry_run=False):
        """오래된 로그 파일 정리"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        print(f"🗑️ {days}일 이전 로그 파일 정리 {'(시뮬레이션)' if dry_run else ''}")
        print(f"📅 기준 날짜: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        total_deleted = 0
        total_size_freed = 0
        
        for backend_name in LOG_BACKENDS:
            backend_dir = self.logs_dir / backend_name
            if not backend_dir.exists():
                continue
            
            print(f"\n🔧 {backend_name.upper()} 백엔드:")
            
            for type_name in LOG_TYPES[backend_name]:
                type_dir = backend_dir / type_name
                if not type_dir.exists():
                    continue
                
                print(f"  📁 {type_name}:")
                
                deleted_count = 0
                size_freed = 0
                
                for log_file in type_dir.glob("*.txt"):
                    file_date = datetime.fromtimestamp(log_file.stat().st_mtime)
                    
                    # 에러 로그와 보안 로그는 더 오래 보관
                    if type_name in ['error', 'security']:
                        actual_cutoff = datetime.now() - timedelta(days=90)
                    else:
                        actual_cutoff = cutoff_date
                    
                    if file_date < actual_cutoff:
                        file_size = log_file.stat().st_size
                        
                        print(f"    ❌ 삭제 대상: {log_file.name} ({file_size/(1024*1024):.2f}MB, {file_date.strftime('%Y-%m-%d')})")
                        
                        if not dry_run:
                            log_file.unlink()
                        
                        deleted_count += 1
                        size_freed += file_size
                
                if deleted_count > 0:
                    print(f"    ✅ {deleted_count}개 파일 삭제됨 ({size_freed/(1024*1024):.2f}MB)")
                    total_deleted += deleted_count
                    total_size_freed += size_freed
                else:
                    print(f"    (삭제할 파일이 없습니다)")
        
        print(f"\n📊 총 정리 결과:")
        print(f"  📄 삭제된 파일: {total_deleted}개")
        print(f"  💾 확보된 용량: {total_size_freed/(1024*1024):.2f}MB")
    
    def get_stats(self):
        """로그 통계 조회"""
        print("\n📊 로그 시스템 통계")
        print("=" * 60)
        
        total_files = 0
        total_size = 0
        backend_stats = {}
        
        for backend_name in LOG_BACKENDS:
            backend_dir = self.logs_dir / backend_name
            if not backend_dir.exists():
                continue
            
            backend_stats[backend_name] = {'files': 0, 'size': 0, 'types': {}}
            
            for type_name in LOG_TYPES[backend_name]:
                type_dir = backend_dir / type_name
                if not type_dir.exists():
                    continue
                
                type_files = 0
                type_size = 0
                
                for log_file in type_dir.glob("*.txt"):
                    file_size = log_file.stat().st_size
                    type_files += 1
                    type_size += file_size
                
                backend_stats[backend_name]['types'][type_name] = {
                    'files': type_files,
                    'size': type_size
                }
                backend_stats[backend_name]['files'] += type_files
                backend_stats[backend_name]['size'] += type_size
            
            total_files += backend_stats[backend_name]['files']
            total_size += backend_stats[backend_name]['size']
        
        # 전체 통계 출력
        print(f"📄 총 로그 파일: {total_files}개")
        print(f"💾 총 사용 용량: {total_size/(1024*1024):.2f}MB")
        
        # 백엔드별 통계
        for backend_name, stats in backend_stats.items():
            if stats['files'] > 0:
                print(f"\n🔧 {backend_name.upper()}:")
                print(f"  📄 파일 수: {stats['files']}개")
                print(f"  💾 용량: {stats['size']/(1024*1024):.2f}MB")
                
                for type_name, type_stats in stats['types'].items():
                    if type_stats['files'] > 0:
                        print(f"    📁 {type_name}: {type_stats['files']}개, {type_stats['size']/(1024*1024):.2f}MB")
    
    def get_level_color(self, level):
        """로그 레벨에 따른 색상 코드 반환"""
        colors = {
            'DEBUG': '\033[36m',    # 청록색
            'INFO': '\033[32m',     # 녹색
            'WARNING': '\033[33m',  # 노란색
            'ERROR': '\033[31m',    # 빨간색
            'CRITICAL': '\033[35m', # 마젠타
        }
        return colors.get(level, '\033[0m')
    
    def reset_color(self):
        """색상 리셋"""
        return '\033[0m'

def main():
    parser = argparse.ArgumentParser(description='로그 관리 유틸리티')
    
    # 서브커맨드 설정
    subparsers = parser.add_subparsers(dest='command', help='사용 가능한 명령')
    
    # list 명령
    list_parser = subparsers.add_parser('list', help='로그 파일 목록 조회')
    list_parser.add_argument('--backend', choices=LOG_BACKENDS, help='백엔드 필터')
    list_parser.add_argument('--type', help='로그 타입 필터')
    list_parser.add_argument('--days', type=int, default=7, help='조회할 일수 (기본: 7일)')
    
    # view 명령
    view_parser = subparsers.add_parser('view', help='로그 파일 내용 조회')
    view_parser.add_argument('backend', choices=LOG_BACKENDS, help='백엔드 선택')
    view_parser.add_argument('type', help='로그 타입 선택')
    view_parser.add_argument('--date', help='날짜 (YYYY-MM-DD 형식, 기본: 오늘)')
    view_parser.add_argument('--lines', type=int, default=50, help='출력할 라인 수 (기본: 50)')
    
    # tail 명령
    tail_parser = subparsers.add_parser('tail', help='실시간 로그 모니터링')
    tail_parser.add_argument('backend', choices=LOG_BACKENDS, help='백엔드 선택')
    tail_parser.add_argument('type', help='로그 타입 선택')
    tail_parser.add_argument('--lines', type=int, default=50, help='초기 출력할 라인 수 (기본: 50)')
    
    # clean 명령
    clean_parser = subparsers.add_parser('clean', help='오래된 로그 파일 정리')
    clean_parser.add_argument('--days', type=int, default=30, help='보관할 일수 (기본: 30일)')
    clean_parser.add_argument('--dry-run', action='store_true', help='실제로 삭제하지 않고 시뮬레이션만 실행')
    
    # stats 명령
    stats_parser = subparsers.add_parser('stats', help='로그 통계 조회')
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    log_manager = LogManager()
    
    try:
        if args.command == 'list':
            log_manager.list_logs(args.backend, args.type, args.days)
        
        elif args.command == 'view':
            log_manager.view_log(args.backend, args.type, args.date, args.lines)
        
        elif args.command == 'tail':
            log_manager.tail_log(args.backend, args.type, args.lines)
        
        elif args.command == 'clean':
            log_manager.clean_logs(args.days, args.dry_run)
        
        elif args.command == 'stats':
            log_manager.get_stats()
            
    except KeyboardInterrupt:
        print("\n\n✅ 작업이 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 