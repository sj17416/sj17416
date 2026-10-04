"""Blogger batch publisher. Python 3.10+. All paths are relative to this file."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCOPES = ['https://www.googleapis.com/auth/blogger']


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def load_posts(path):
    items = read_json(path)
    if not isinstance(items, list) or not items:
        raise ValueError('글 목록은 비어 있지 않은 JSON 배열이어야 합니다.')
    result, ids = [], set()
    for item in items:
        key = item['id']
        if not isinstance(key, str) or not key.strip() or key in ids:
            raise ValueError('각 글에 서로 다른 문자열 id가 필요합니다.')
        ids.add(key)
        title = item['title']
        if not isinstance(title, str) or not title.strip():
            raise ValueError('제목을 입력하세요.')
        content = (path.parent / item['content_file']).read_text(encoding='utf-8-sig')
        if not content.strip():
            raise ValueError('본문이 비어 있습니다.')
        mode = item.get('mode', 'draft')
        if mode not in ('draft', 'publish', 'schedule'):
            raise ValueError('mode: draft, publish, schedule 중 하나를 사용하세요.')
        date = None
        if mode == 'schedule':
            date = datetime.fromisoformat(item['publish_at'].replace('Z', '+00:00'))
            if date.tzinfo is None or date <= datetime.now(timezone.utc):
                raise ValueError('예약 시간은 시간대가 포함된 미래 시간이어야 합니다.')
            date = date.isoformat()
        labels = item.get('labels', [])
        if not isinstance(labels, list) or any(not isinstance(x, str) for x in labels):
            raise ValueError('labels는 문자열 배열이어야 합니다.')
        body = {'title': title, 'content': content, 'labels': labels}
        fingerprint = hashlib.sha256(json.dumps([body, mode, date], sort_keys=True).encode()).hexdigest()
        result.append((key, body, mode, date, fingerprint))
    return result


def service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    token = ROOT / 'token.json'
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        secret = ROOT / 'credentials.json'
        if not secret.exists():
            raise ValueError('데스크톱 앱 OAuth JSON을 credentials.json으로 저장하세요.')
        if 'installed' not in read_json(secret):
            raise ValueError('OAuth 애플리케이션 유형을 데스크톱 앱으로 생성하세요.')
        creds = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES).run_local_server(
            host='localhost', port=0, prompt='consent', timeout_seconds=180)
    token.write_text(creds.to_json(), encoding='utf-8')
    return build('blogger', 'v3', credentials=creds, cache_discovery=False)


def run(api, blog_id, posts, state_path):
    state = read_json(state_path) if state_path.exists() else {}
    for key, body, mode, date, fingerprint in posts:
        state_key = f'{blog_id}:{key}'
        entry = state.get(state_key)
        if entry:
            if entry['fingerprint'] != fingerprint:
                raise ValueError(f'{key}: 이미 처리한 글이 변경되었습니다. 새 글이면 새 id를 사용하세요.')
            if entry['phase'] == 'done':
                print(f'건너뜀: {body["title"]}')
                continue
            if entry['phase'] == 'creating':
                raise ValueError(f'{key}: 이전 업로드 결과가 불확실합니다. Blogger에서 초안을 확인한 후 사용설명서에 따라 복구하세요.')
        else:
            entry = {'fingerprint': fingerprint, 'phase': 'creating'}
            state[state_key] = entry
            save_json(state_path, state)
            post = api.posts().insert(blogId=blog_id, body=body, isDraft=True).execute(num_retries=0)
            entry.update(post_id=post['id'], phase='draft')
            save_json(state_path, state)
        if mode != 'draft':
            remote = api.posts().get(blogId=blog_id, postId=entry['post_id']).execute(num_retries=2)
            if remote.get('status') not in ('LIVE', 'SCHEDULED'):
                kwargs = {'publishDate': date} if date else {}
                api.posts().publish(blogId=blog_id, postId=entry['post_id'], **kwargs).execute(num_retries=0)
        entry['phase'] = 'done'
        save_json(state_path, state)
        print(f'완료 ({mode}): {body["title"]} / 글 ID {entry["post_id"]}')


def main():
    parser = argparse.ArgumentParser(description='블로그스팟 자동 발행')
    parser.add_argument('command', choices=['blogs', 'preview', 'run'])
    parser.add_argument('--blog-id')
    parser.add_argument('--posts', default='posts.json')
    args = parser.parse_args()
    if args.command == 'blogs':
        api = service()
        page = api.blogs().listByUser(userId='self').execute(num_retries=2)
        for blog in page.get('items', []):
            print(f'{blog["id"]}  {blog["name"]}  {blog["url"]}')
        return
    posts = load_posts(ROOT / args.posts)
    if args.command == 'preview':
        for key, body, mode, date, _ in posts:
            print(f'{key}: {body["title"]} | {mode} | {date or "예약 없음"} | 본문 {len(body["content"])}자')
        print('검사 완료. 업로드하지 않았습니다.')
        return
    if not args.blog_id or not args.blog_id.isdigit():
        raise ValueError('--blog-id에 blogs 명령으로 확인한 숫자 ID를 입력하세요.')
    lock = ROOT / '.run.lock'
    try:
        with lock.open('x'):
            pass
    except FileExistsError:
        raise ValueError('실행 중인 프로그램이 있습니다. 강제 종료했다면 실행 중인 프로세스가 없는지 확인 후 .run.lock을 삭제하세요.')
    try:
        run(service(), args.blog_id, posts, ROOT / 'state.json')
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'오류: {exc}')
        raise SystemExit(1)
