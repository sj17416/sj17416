"""Windows desktop UI for blogger_auto.py (Python 3.10+)."""
import json
import sys
import html as html_tools
import queue
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import blogger_auto as engine
import content_engine

ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
ROOT = Path(sys.executable).resolve().parent / 'BlogFlow-data' if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
ROOT.mkdir(exist_ok=True)
engine.ROOT = ROOT


class App:
    def __init__(self, window):
        self.window = window
        window.title('BlogFlow · 블로그 발행 도우미')
        window.configure(background='#f4f7fc')
        style = ttk.Style(window)
        style.theme_use('clam')
        style.configure('.', font=('맑은 고딕', 10))
        style.configure('TFrame', background='#f4f7fc')
        style.configure('TLabel', background='#f4f7fc', foreground='#24324b')
        style.configure('TButton', padding=(12, 9))
        style.configure('Accent.TButton', background='#2f6fed', foreground='white')
        style.map('Accent.TButton', background=[('active', '#245ac5'), ('disabled', '#a7bde8')])
        if (ASSETS / 'logo.png').exists():
            self.logo = tk.PhotoImage(file=str(ASSETS / 'logo.png'))
            window.iconphoto(True, self.logo)
        window.geometry('1000x800')
        window.minsize(760, 620)
        self.events = queue.Queue()
        self.busy = False
        self.blogs = {}
        self.buttons = []
        self.category = tk.StringVar(value='정부지원금')
        self.keyword = tk.StringVar(value='에너지바우처')
        self.writing_style = tk.StringVar(value='공감형')
        self.description = tk.StringVar()
        self.generation_count = {}
        self.draft_history = []
        self.title = tk.StringVar(value='알뜰폰 요금제 비교: 싼 월 요금만 보고 바꾸기 전 확인할 1년 비용')
        self.labels = tk.StringVar(value='알뜰폰, 통신비 절약, 요금제 비교')
        self.mode = tk.StringVar(value='초안 저장')
        self.date = tk.StringVar(value=(datetime.now(timezone(timedelta(hours=9))) + timedelta(days=1)).strftime('%Y-%m-%d %H:%M'))
        self.status = tk.StringVar(value='먼저 OAuth JSON을 선택하고 Google 계정을 연결하세요.')
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill='both', expand=True)
        header = ttk.Frame(outer)
        header.pack(fill='x')
        if hasattr(self, 'logo'):
            self.header_logo = self.logo.subsample(4, 4)
            ttk.Label(header, image=self.header_logo).pack(side='left', padx=(0, 12))
        ttk.Label(header, text='BlogFlow', font=('맑은 고딕', 24, 'bold')).pack(side='left')
        self.button(header, '사용 안내', self.help).pack(side='right')
        ttk.Label(outer, text='1. 계정 연결   →   2. 글 작성   →   3. 초안 또는 예약 등록').pack(anchor='w', pady=(8, 12))
        account = ttk.Frame(outer)
        account.pack(fill='x')
        self.button(account, '인증 파일 선택', self.credentials).pack(side='left')
        self.button(account, 'Google 연결', self.connect).pack(side='left', padx=8)
        self.blog = ttk.Combobox(account, state='readonly', width=35)
        self.blog.pack(side='left', fill='x', expand=True)
        self.entry(outer, '글 제목', self.title)
        self.entry(outer, '라벨 (쉼표로 구분)', self.labels)
        notebook = ttk.Notebook(outer)
        notebook.pack(fill='both', expand=True, pady=12)
        self.notebook = notebook
        easy = ttk.Frame(notebook, padding=10)
        self.easy_tab = easy
        notebook.add(easy, text='쉬운 글쓰기')
        topic_controls = ttk.Frame(easy)
        topic_controls.pack(fill='x', pady=(0, 8))
        category_box = ttk.Combobox(topic_controls, textvariable=self.category, values=['정부지원금','생활비 절약·상품 비교'], state='readonly', width=20)
        category_box.pack(side='left')
        category_box.bind('<<ComboboxSelected>>', lambda e:self.update_keywords())
        self.keyword_box = ttk.Combobox(topic_controls, textvariable=self.keyword, state='readonly', width=24)
        self.keyword_box.pack(side='left', padx=6)
        ttk.Combobox(topic_controls, textvariable=self.writing_style, values=content_engine.STYLES, state='readonly', width=14).pack(side='left')
        actions = ttk.Frame(easy)
        actions.pack(fill='x', pady=(0,8))
        self.button(actions, '↻ 다른 문구 보기', self.regenerate).pack(side='left')
        self.button(actions, '이전 문구', self.previous_draft).pack(side='left', padx=6)
        self.button(actions, '마음에 드는 글 보관', self.favorite).pack(side='left')
        ttk.Label(easy, text='키워드·말투를 선택하고 새로고침하세요. 템플릿 기반 초안이며 최신 조건을 자동 조사하지 않습니다.', wraplength=850).pack(anchor='w', pady=(0, 8))
        self.easy = self.textbox(easy)
        self.easy.insert('1.0', '[문제]\n휴대폰 요금이 부담스럽지만 어떤 요금제로 바꿔야 할지 고민되나요?\n\n[공감]\n데이터가 부족해질까, 결합할인을 놓칠까 걱정되면 쉽게 결정하기 어렵습니다.\n\n[해결]\n같은 데이터와 통화 조건으로 할인 종료 후 가격까지 포함한 1년 비용을 비교하세요.\n\n[제안]\n최근 청구서와 데이터 사용량을 확인하고 필요한 조건을 메모해 보세요.\n\n[대상]\n데이터를 많이 남기거나 현재 결합 혜택이 적은 경우부터 후보를 비교해 보세요. 위약금이 크면 이동 비용을 먼저 확인하세요.\n\n[행동]\n후보 요금제 두 개를 골라 공식 가입 화면에서 할인 기간과 추가 비용을 확인하세요.')
        self.button(easy, '이 내용으로 PASONA 글 만들기', self.apply_easy).pack(anchor='e')
        content = ttk.Frame(notebook, padding=10)
        self.html_tab = content
        notebook.add(content, text='글 HTML · 고급 편집')
        tools = ttk.Frame(content)
        tools.pack(fill='x', pady=(0, 8))
        self.button(tools, 'PASONA 예시 불러오기', self.template).pack(side='left')
        self.button(tools, 'HTML 파일 열기', self.open_html).pack(side='left', padx=6)
        self.button(tools, '미리보기', self.preview).pack(side='left')
        self.button(tools, 'HTML 저장', self.save_html).pack(side='left', padx=6)
        self.body = self.textbox(content)
        ads = ttk.Frame(notebook, padding=10)
        notebook.add(ads, text='광고 코드')
        ttk.Label(ads, text='애드센스에서 복사한 광고 단위 코드를 넣으세요. 비어 있는 자리는 숨겨집니다.').pack(anchor='w')
        ttk.Label(ads, text='광고 로더는 한 번만 포함하세요. 실제 노출은 사이트 승인·계정 설정에 따라 달라집니다.').pack(anchor='w', pady=(0, 8))
        self.ad_boxes = {}
        for key, label in [('TOP', '상단 — 도입 뒤'), ('MID', '중간 — 비교표 뒤'), ('BOTTOM', '하단 — FAQ 앞')]:
            ttk.Label(ads, text=label).pack(anchor='w')
            self.ad_boxes[key] = self.textbox(ads, height=4)
        seo = ttk.Frame(notebook, padding=10)
        notebook.add(seo, text='검색 노출 · SEO')
        ttk.Label(seo, text='검색 설명 — Blogger 편집 화면의 검색 설명 칸에 직접 붙여 넣으세요.', wraplength=850).pack(anchor='w')
        ttk.Entry(seo, textvariable=self.description).pack(fill='x', pady=8)
        self.button(seo, '검색 설명 복사', self.copy_description).pack(anchor='w')
        ttk.Label(seo, text='검색 설명은 API 등록만으로 설정되지 않습니다. Blogger에서 검색 설명 기능을 활성화하고 글마다 입력하세요.').pack(anchor='w', pady=10)
        self.seo_result = tk.StringVar(value='글을 만든 뒤 기본 구조를 점검하세요. 검색 순위 점수가 아닙니다.')
        self.button(seo, '글 구조 점검', self.check_seo).pack(anchor='w')
        ttk.Label(seo, textvariable=self.seo_result, wraplength=850).pack(anchor='w', pady=10)
        ttk.Label(seo, text='제목·소제목·출처·FAQ를 정리합니다. 지원금 금액·신청 마감은 공식 자료를 확인해 본문에 추가하세요. 검색 노출이나 수익을 보장하지 않습니다.', wraplength=850).pack(anchor='w')
        controls = ttk.Frame(outer)
        controls.pack(fill='x')
        ttk.Label(controls, text='발행 방식').pack(side='left')
        ttk.Combobox(controls, textvariable=self.mode, values=['초안 저장', '예약 발행', '즉시 발행'], state='readonly', width=12).pack(side='left', padx=8)
        ttk.Label(controls, text='예약 시간 (한국)').pack(side='left')
        ttk.Entry(controls, textvariable=self.date, width=20).pack(side='left', padx=8)
        publish_button = self.button(controls, '블로그에 등록하기', self.publish)
        publish_button.configure(style='Accent.TButton')
        publish_button.pack(side='right')
        ttk.Label(outer, text='예약 입력: YYYY-MM-DD HH:MM · 예약 등록 후에는 앱을 종료해도 됩니다.').pack(anchor='w', pady=(8, 4))
        ttk.Label(outer, textvariable=self.status, wraplength=920).pack(anchor='w')
        self.template()
        self.load_settings()
        self.update_keywords(reset=False)
        if not (ROOT / 'settings.json').exists():
            self.regenerate()
        window.protocol('WM_DELETE_WINDOW', self.close)
        window.after(150, self.poll)

    def textbox(self, parent, height=12):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, pady=(0, 8))
        text = tk.Text(frame, wrap='word', height=height, undo=True, font=('맑은 고딕', 10))
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        text.pack(fill='both', expand=True)
        return text

    def button(self, parent, label, command):
        button = ttk.Button(parent, text=label, command=lambda: self.guard(command))
        self.buttons.append(button)
        return button

    def guard(self, command):
        try:
            command()
        except Exception as exc:
            messagebox.showerror('확인해 주세요', str(exc))

    def entry(self, parent, label, variable):
        ttk.Label(parent, text=label).pack(anchor='w', pady=(8, 2))
        ttk.Entry(parent, textvariable=variable).pack(fill='x')

    def credentials(self):
        filename = filedialog.askopenfilename(title='데스크톱 앱 OAuth JSON 선택', filetypes=[('JSON', '*.json')])
        if not filename:
            return
        data = engine.read_json(Path(filename))
        if 'installed' not in data:
            raise ValueError('Google Cloud에서 데스크톱 앱 유형으로 만든 OAuth JSON을 선택하세요.')
        if (ROOT / 'token.json').exists():
            raise ValueError('이미 연결된 계정이 있습니다. 계정을 바꾸려면 앱을 닫고 token.json을 삭제한 후 다시 실행하세요.')
        engine.save_json(ROOT / 'credentials.json', data)
        self.status.set('인증 파일을 저장했습니다. Google 연결 버튼을 누르세요.')

    def task(self, work, callback):
        self.busy = True
        for button in self.buttons:
            button.configure(state='disabled')
        def worker():
            try:
                self.events.put((callback, work(), None))
            except Exception as exc:
                self.events.put((callback, None, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            callback, result, error = self.events.get_nowait()
            self.busy = False
            for button in self.buttons:
                button.configure(state='normal')
            if error:
                self.status.set('작업을 완료하지 못했습니다. 오류를 확인하세요.')
                messagebox.showerror('오류', error)
            else:
                callback(result)
        except queue.Empty:
            pass
        self.window.after(150, self.poll)

    def connect(self):
        self.status.set('브라우저에서 Google 로그인을 완료하세요. 블로그를 조회 중입니다…')
        self.task(lambda: engine.service().blogs().listByUser(userId='self').execute(num_retries=2), self.connected)

    def connected(self, response):
        self.blogs = {f'{b["name"]} ({b["id"]})': b['id'] for b in response.get('items', [])}
        self.blog.configure(values=list(self.blogs))
        if self.blogs:
            self.blog.current(0)
        self.status.set(f'블로그 {len(self.blogs)}개를 찾았습니다. 발행할 블로그를 선택하세요.' if self.blogs else '이 계정에서 블로그를 찾지 못했습니다. Blogger 계정을 확인하세요.')

    def template(self):
        self.set_body((ASSETS / '알뜰폰-통신비-절약.html').read_text(encoding='utf-8-sig'))

    def help(self):
        messagebox.showinfo('처음 사용하는 방법', '① 인증 파일 선택: Google Cloud에서 만든 데스크톱 앱 OAuth JSON을 선택하세요.\n② Google 연결: 브라우저에서 로그인한 뒤 블로그를 선택하세요.\n③ 쉬운 글쓰기에서 여섯 항목을 수정하고 글 만들기를 누르세요. 예시 글은 HTML 탭에서 편집할 수 있습니다.\n④ 광고 코드가 있으면 광고 탭에 넣으세요.\n⑤ 기본값인 초안 저장으로 먼저 등록하고 Blogger에서 확인하세요.\n\n설정과 작업 기록은 실행 파일 옆 BlogFlow-data 폴더에 보관됩니다. 제목·광고 등을 바꾸고 다시 등록하면 새 글이 생성됩니다.')

    def update_keywords(self, reset=True):
        values = [k for k,v in content_engine.TOPICS.items() if v[0] == self.category.get()]
        self.keyword_box.configure(values=values)
        if reset or self.keyword.get() not in values:
            self.keyword.set(values[0])

    def snapshot(self):
        return {'title':self.title.get(), 'labels':self.labels.get(), 'description':self.description.get(), 'easy':self.easy.get('1.0','end-1c'), 'body':self.body.get('1.0','end-1c'), 'keyword':self.keyword.get(), 'style':self.writing_style.get()}

    def regenerate(self):
        self.draft_history.append(self.snapshot())
        self.draft_history = self.draft_history[-50:]
        key = self.keyword.get() + ':' + self.writing_style.get()
        sequence = int(self.generation_count.get(key, 0))
        info = content_engine.draft(self.keyword.get(), self.writing_style.get(), sequence)
        self.generation_count[key] = sequence + 1
        self.title.set(info['title'])
        self.labels.set(self.keyword.get() + ', ' + self.category.get())
        self.description.set(info['description'])
        self.easy.delete('1.0','end')
        self.easy.insert('1.0', '\n\n'.join(f'[{k}]\n{v}' for k,v in info['sections'].items()))
        self.apply_easy()
        self.notebook.select(self.easy_tab)
        self.check_seo()
        self.status.set(f'{self.keyword.get()} · {self.writing_style.get()} · 문구 {sequence+1}. 마음에 들 때까지 바꿀 수 있습니다. 현재 글·제목은 새 문구로 교체됩니다.')

    def previous_draft(self):
        if not self.draft_history:
            self.status.set('이전 문구가 없습니다. 먼저 다른 문구 보기를 눌러보세요.')
            return
        data = self.draft_history.pop()
        self.keyword.set(data['keyword'])
        self.category.set(content_engine.TOPICS[data['keyword']][0])
        self.writing_style.set(data['style'])
        self.update_keywords(reset=False)
        self.title.set(data['title']); self.labels.set(data['labels']); self.description.set(data['description'])
        self.easy.delete('1.0','end'); self.easy.insert('1.0', data['easy'])
        self.set_body(data['body'])
        self.save_settings()
        self.status.set('이전 글을 복원했습니다. 새 문구는 필요할 때 다시 생성하세요.')

    def favorite(self):
        self.apply_easy() if self.notebook.select() == str(self.easy_tab) else None
        folder = ROOT / 'favorites'
        folder.mkdir(exist_ok=True)
        import uuid
        name = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
        (folder / (name + '.html')).write_text(self.html(), encoding='utf-8')
        engine.save_json(folder / (name + '.json'), self.snapshot())
        self.status.set(f'보관했습니다: {name}. HTML 파일 열기로 다시 불러올 수 있습니다.')
        messagebox.showinfo('글 보관 완료', f'저장 위치: {folder}\nHTML 파일 열기로 다시 불러오세요. 제목과 검색 설명은 함께 저장된 JSON에서 확인할 수 있습니다.')

    def copy_description(self):
        self.window.clipboard_clear()
        self.window.clipboard_append(self.description.get())
        self.status.set('검색 설명을 복사했습니다. Blogger 글 편집 화면의 검색 설명에 붙여 넣으세요.')

    def check_seo(self):
        self.seo_result.set(content_engine.seo_review(self.title.get(), self.description.get(), self.keyword.get(), self.body.get('1.0','end-1c')))

    def apply_easy(self):
        import re
        raw = self.easy.get('1.0', 'end-1c')
        parts = re.split(r'\[(문제|공감|해결|제안|대상|행동)\]', raw)
        sections = dict(zip(parts[1::2], parts[2::2]))
        if any(not sections.get(k, '').strip() for k in ['문제', '공감', '해결', '제안', '대상', '행동']):
            raise ValueError('문제·공감·해결·제안·대상·행동 여섯 항목을 모두 작성하세요.')
        original = (ASSETS / '알뜰폰-통신비-절약.html').read_text(encoding='utf-8-sig')
        styles = ''.join(re.findall(r'<style>[\s\S]*?</style>', original))
        slots = re.findall(r'<div class="ad-slot"[\s\S]*?</div>', original)
        keyword = self.keyword.get()
        info = content_engine.draft(keyword, self.writing_style.get())
        safe = html_tools.escape(keyword)
        headings = {'문제':f'{keyword}, 무엇부터 확인할까요?', '공감':'조건이 복잡하게 느껴지는 이유', '해결':f'{keyword} 주요 확인 조건', '제안':'준비 자료와 확인 순서', '대상':'내 상황에 맞는지 확인하기', '행동':'공식 안내 확인과 다음 단계'}
        chunks = [styles, '<div class="mv"><span class="badge">생활 정보 가이드 · 공식 안내로 최종 조건 확인</span>', '<nav aria-label="글 목차"><b>이 글에서 확인할 내용</b><ul>']
        chunks.extend(f'<li><a href="#bf-section-{i}">{html_tools.escape(label)}</a></li>' for i,label in enumerate(headings.values()))
        chunks.append('</ul></nav>')
        for index, key in enumerate(headings):
            chunks.append(f'<h2 id="bf-section-{index}">' + html_tools.escape(headings[key]) + '</h2>')
            chunks.extend('<p>' + html_tools.escape(p.strip()).replace('\n', '<br>') + '</p>' for p in sections[key].strip().split('\n\n') if p.strip())
            if key == '행동':
                chunks.append('<div class="cta"><a href="' + html_tools.escape(info['source_url'], quote=True) + '" target="_blank" rel="noopener">' + safe + ' 공식 안내 확인하기</a></div><p>안내 내용을 읽은 뒤 적용 조건과 필요한 자료를 다시 확인하세요.</p>')
            if index in (1, 3, 5):
                chunks.append(slots[(index-1)//2])
        chunks.append('<h2>자주 묻는 질문</h2><details><summary>누구에게나 같은 조건이 적용되나요?</summary><p>개인·가구 상황, 선택한 사업 또는 상품에 따라 다릅니다. 공식 안내에서 자신의 조건을 확인하세요.</p></details><details><summary>이 글만 보고 바로 신청하거나 계약해도 되나요?</summary><p>이 글은 확인 순서를 정리한 가이드입니다. 금액·기간·제출 서류·추가 비용은 담당 기관 또는 사업자의 최신 안내를 확인하세요.</p></details>')
        chunks.append('<div class="src"><b>공식 참고 안내</b><p><a href="' + html_tools.escape(info['source_url'], quote=True) + '" target="_blank" rel="noopener">' + html_tools.escape(info['source_name']) + '</a></p><p>이 초안은 최신 공고를 자동 조회하거나 신청 자격을 판정하지 않습니다. 공식 자료 확인 후 구체적인 금액·기간과 확인일을 추가하세요.</p></div>')
        chunks.append('</div>')
        self.set_body('\n'.join(chunks))
        self.notebook.select(self.html_tab)
        self.save_settings()
        self.status.set('PASONA 글을 만들었습니다. 미리보기로 확인한 뒤 초안 저장하세요. 입력한 내용의 사실관계는 직접 확인해 주세요.')

    def save_settings(self):
        engine.save_json(ROOT / 'settings.json', {'category':self.category.get(), 'keyword':self.keyword.get(), 'style':self.writing_style.get(), 'description':self.description.get(), 'generation_count':self.generation_count, 'title':self.title.get(), 'labels':self.labels.get(), 'body':self.body.get('1.0','end-1c'), 'easy':self.easy.get('1.0','end-1c'), 'ads':{k:b.get('1.0','end-1c') for k,b in self.ad_boxes.items()}})

    def load_settings(self):
        path = ROOT / 'settings.json'
        if not path.exists():
            return
        try:
            data = engine.read_json(path)
            if 'keyword' not in data:
                self.keyword.set('알뜰폰 요금제 비교')
                self.category.set('생활비 절약·상품 비교')
            if data.get('keyword') in content_engine.TOPICS:
                self.keyword.set(data['keyword'])
                self.category.set(content_engine.TOPICS[data['keyword']][0])
            if data.get('style') in content_engine.STYLES:
                self.writing_style.set(data['style'])
            self.description.set(data.get('description',''))
            self.generation_count = data.get('generation_count', {})
            self.title.set(data.get('title', self.title.get()))
            self.labels.set(data.get('labels', self.labels.get()))
            self.set_body(data.get('body', self.body.get('1.0','end-1c')))
            if data.get('easy'):
                self.easy.delete('1.0','end'); self.easy.insert('1.0', data['easy'])
            for k,b in self.ad_boxes.items():
                b.insert('1.0', data.get('ads', {}).get(k, ''))
            self.status.set('지난 글과 광고 설정을 불러왔습니다. Google 연결 후 블로그를 선택하세요.')
        except Exception:
            self.status.set('저장된 설정을 읽지 못했습니다. 기본 예시로 시작합니다.')

    def set_body(self, value):
        self.body.delete('1.0', 'end')
        self.body.insert('1.0', value)

    def open_html(self):
        filename = filedialog.askopenfilename(filetypes=[('HTML', '*.html')])
        if filename:
            self.set_body(Path(filename).read_text(encoding='utf-8-sig'))

    def html(self):
        value = self.body.get('1.0', 'end-1c')
        if not value.strip():
            raise ValueError('글 본문을 입력하세요.')
        for key, box in self.ad_boxes.items():
            code = box.get('1.0', 'end-1c').strip()
            marker = f'<!-- AD_{key}: 이 주석을 애드센스에서 복사한 반응형 디스플레이 광고 단위 코드로 교체하세요. -->'
            if code:
                if marker not in value:
                    raise ValueError(f'{key} 광고 위치를 찾지 못했습니다. PASONA 예시를 사용하거나 HTML의 광고 주석을 복원하세요.')
                if 'adsbygoogle' not in code:
                    raise ValueError(f'{key}: 애드센스 광고 단위 코드를 확인하세요.')
                value = value.replace(marker, code, 1)
        return value

    def preview(self):
        content = self.html()
        # Preview reserves positions without loading ads or external article scripts.
        import re
        content = re.sub(r'<script\b[^>]*>[\s\S]*?</script\s*>', '', content, flags=re.I)
        content = re.sub(r'<ins\b[^>]*class=["\'][^"\']*adsbygoogle[^"\']*["\'][^>]*>[\s\S]*?</ins\s*>', '', content, flags=re.I)
        preview = ROOT / 'preview.html'
        preview.write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>글 배치 미리보기</title><style>body{padding:20px}.mv .ad-slot{display:block!important;min-height:100px;background:#f7f8fa!important}.mv .ad-slot:after{content:"광고 배치 미리보기 — 실제 광고를 불러오지 않습니다";display:block;text-align:center;padding:24px;font-size:13px;color:#687180}</style>' + content + '</html>', encoding='utf-8')
        webbrowser.open(preview.as_uri())
        self.status.set('브라우저에 배치 미리보기를 열었습니다. 계산기와 실제 광고는 게시 화면에서 확인하세요.')

    def save_html(self):
        value = self.html()
        filename = filedialog.asksaveasfilename(defaultextension='.html', filetypes=[('HTML', '*.html')], initialfile='블로그글.html')
        if filename:
            Path(filename).write_text(value, encoding='utf-8')
            self.status.set('HTML 파일을 저장했습니다.')

    def publish(self):
        if self.notebook.select() == str(self.easy_tab):
            self.apply_easy()
        blog_id = self.blogs.get(self.blog.get())
        if not blog_id:
            raise ValueError('Google 연결 후 블로그를 선택하세요.')
        title = self.title.get().strip()
        if not title:
            raise ValueError('글 제목을 입력하세요.')
        html = self.html()
        mode = {'초안 저장': 'draft', '예약 발행': 'schedule', '즉시 발행': 'publish'}[self.mode.get()]
        item = {'id': 'desktop-post', 'title': title, 'content_file': 'article.html', 'labels': [x.strip() for x in self.labels.get().split(',') if x.strip()], 'mode': mode}
        if mode == 'schedule':
            date = datetime.strptime(self.date.get().strip(), '%Y-%m-%d %H:%M').replace(tzinfo=timezone(timedelta(hours=9)))
            if date <= datetime.now(timezone.utc):
                raise ValueError('예약 시간을 미래로 입력하세요.')
            item['publish_at'] = date.isoformat()
        jobs = ROOT / 'jobs'
        jobs.mkdir(exist_ok=True)
        import hashlib
        fingerprint = hashlib.sha256((blog_id + json.dumps(item, ensure_ascii=False, sort_keys=True) + html).encode()).hexdigest()[:24]
        folder = jobs / fingerprint
        folder.mkdir(exist_ok=True)
        (folder / 'article.html').write_text(html, encoding='utf-8')
        engine.save_json(folder / 'posts.json', [item])
        posts = engine.load_posts(folder / 'posts.json')
        if not messagebox.askyesno('등록 확인', f'블로그: {self.blog.get()}\n제목: {title}\n방식: {self.mode.get()}\n' + (f'한국 시간: {self.date.get()}\n' if mode == 'schedule' else '') + '\n이 내용으로 등록할까요?'):
            return
        def work():
            lock = ROOT / '.run.lock'
            try:
                with lock.open('x'):
                    pass
            except FileExistsError:
                raise ValueError('다른 발행 작업이 진행 중입니다. 강제 종료한 경우 실행 중인 프로그램이 없는지 확인 후 .run.lock을 삭제하세요.')
            try:
                engine.run(engine.service(), blog_id, posts, folder / 'state.json')
                return engine.read_json(folder / 'state.json')[f'{blog_id}:desktop-post']
            finally:
                lock.unlink(missing_ok=True)
        self.status.set('등록 중입니다. 완료될 때까지 앱을 닫지 마세요…')
        self.task(work, lambda result: self.status.set(f'등록 완료 / 글 ID: {result["post_id"]}. 같은 내용 재등록은 건너뜁니다. Blogger 관리 화면에서 확인하세요.'))

    def close(self):
        if self.busy:
            messagebox.showinfo('작업 진행 중', 'Google 연결 또는 발행 작업이 끝난 후 닫아주세요.')
            return
        self.guard(self.save_settings)
        self.window.destroy()


if __name__ == '__main__':
    if sys.stdout is None:
        sys.stdout = open(ROOT / 'app.log', 'a', encoding='utf-8')
        sys.stderr = sys.stdout
    window = tk.Tk()
    if '--self-test' in sys.argv:
        window.withdraw()
        app = App(window)
        window.update()
        assert len(app.ad_boxes) == 3
        app.apply_easy()
        assert 'AD_TOP' in app.html() and '다음 단계' in app.html()
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        build('blogger', 'v3', developerKey='test', static_discovery=True)
        (ROOT / 'self-test.json').write_text(json.dumps({'ok':True,'ui':True,'template':True,'google_library':True}), encoding='utf-8')
        window.destroy()
    else:
        App(window)
        window.mainloop()
