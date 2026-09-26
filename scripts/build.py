#!/usr/bin/env python3
"""content/<slug>.md と templates/case.html から public/<slug>/index.html を、
content/en/<slug>.md（日本語版の英訳）と同じテンプレートから public/en/<slug>/index.html を、
content/index.md（事例一覧）と templates/index.html から public/index.html を生成する。

使い方: python3 scripts/build.py （標準ライブラリのみ）

本文の書き方
  ## 見出し            <section> を始める（次の ## か、section 外のブロックまで）
  ### 見出し           <h3>
  <p style="…">…</p>   1行の HTML はそのまま出力する
  それ以外の1行        <p>。段落は1行で書き、空行で区切る
  ::: クラス名 … :::   クラス付きのブロック。中身の書き方は下の各関数を参照

本文テキストは HTML としてそのまま出力する（<br> などが使える）。
出力の改行・インデントは原本に合わせてあり、scripts/verify.py で原本と突き合わせる。
"""
import html
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
FRONT_MATTER_KEYS = ('title', 'description', 'school')
OPTIONAL_KEYS = ('image',)  # 索引カードの写真。同梱画像が無い事例（顔の判別できる写真しか無い場合など）は省く
LOGO_SLUG = 'tokushima-kita-2025'  # ヘッダーのロゴは徳島北の画像フォルダにある（全ページ共通）

FLAGS = {
    '日本': '<rect width="30" height="20" fill="#fff"/><circle cx="15" cy="10" r="6" fill="#BC002D"/>',
    'インドネシア': '<rect width="30" height="10" fill="#CE1126"/><rect y="10" width="30" height="10" fill="#fff"/>',
}
FLAGS.update({'Japan': FLAGS['日本'], 'Indonesia': FLAGS['インドネシア']})  # 英語版の aria-label

# 事例ページのヘッダー・パンくず・footer（言語ごと）。{{ root }} は public/ までの相対パス
CHROME = {
    'ja': {
        'lang': 'ja', 'root': '..', 'title_suffix': '｜導入事例｜AirPangaea', 'site': 'https://ja.airpangaea.com',
        'nav_home': 'ホーム', 'nav_program': 'プログラム', 'nav_case': '導入事例', 'nav_corporate': '会社概要',
        'case_link': '/', 'crumb_sep': ' ／ ',
        'foot_privacy': 'プライバシーポリシー', 'foot_terms': '利用規約', 'foot_tokushoho': '特定商取引法に基づく表記',
    },
    'en': {
        'lang': 'en', 'root': '../..', 'title_suffix': ' | Case | AirPangaea', 'site': 'https://www.airpangaea.com',
        'nav_home': 'Home', 'nav_program': 'Program', 'nav_case': 'Case', 'nav_corporate': 'Corporate',
        'case_link': 'https://www.airpangaea.com/case',  # 英語の事例一覧ができるまでは Wix の英語版 /case
        'crumb_sep': ' / ',
        'foot_privacy': 'Privacy Policy', 'foot_terms': 'Terms and Conditions',
        'foot_tokushoho': 'Specified Commercial Transactions',
    },
}
FLAG_FRAME = '<rect x=".5" y=".5" width="29" height="19" fill="none" stroke="#D3DBE1"/>'


class BuildError(Exception):
    pass


def attr(value):
    return html.escape(value, quote=True)


OWN_HOSTS = ('ja.airpangaea.com', 'www.airpangaea.com', 'case.airpangaea.com')


def link_attrs(href):
    """他社サイト（http/https）へのリンクは新しいタブで開く。
    サイト内と自社サイト（OWN_HOSTS）へのリンクは、一体感のため同じタブで開く（ヘッダー・footer はテンプレート側）"""
    if not href.startswith('http') or urlparse(href).hostname in OWN_HOSTS:
        return ''
    return ' target="_blank" rel="noopener noreferrer"'


def indent(lines, width=2):
    return [' ' * width + line if line else '' for line in lines]


def fields(body, name, count=None):
    lines = [line for line in body if line]
    if count is not None and len(lines) != count:
        raise BuildError(f'::: {name} は空行を除いて{count}行: {lines}')
    return lines


def split_groups(body):
    groups, current = [], []
    for line in body + ['']:
        if line:
            current.append(line)
        elif current:
            groups.append(current)
            current = []
    return groups


class Images:
    def __init__(self, slug, root='..'):
        self.dir = ROOT / 'public' / 'images' / slug
        self.url = f'{root}/images/{slug}'

    def require(self, name):
        if not (self.dir / name).is_file():
            raise BuildError(f'画像ファイルがない: {self.dir / name}')

    def tag(self, line):
        m = re.fullmatch(r'!\[([^\]]+)\]\(([\w.-]+)\)', line)
        if not m:
            raise BuildError(f'画像は ![代替テキスト](ファイル名) で書く: {line}')
        alt, name = m.groups()
        self.require(name)
        return f'<img src="{self.url}/{name}" alt="{attr(alt)}">'


# ── ブロック ──────────────────────────────────────────

def hero(body, images):
    """# 見出し ／ リード文 ／ 出典の注記（任意。[文言](URL) でリンクにできる）"""
    lines = fields(body, 'hero')
    if len(lines) not in (2, 3) or not lines[0].startswith('# '):
        raise BuildError(f'::: hero は「# 見出し」「リード文」「出典の注記（任意）」: {lines}')
    h1, lede, *note = lines
    out = ['<div class="hero">', f'  <h1>{h1[2:]}</h1>', f'  <p class="lede">{lede}</p>']
    if note:
        text = re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+|/[^)\s]*)\)',
                      lambda m: f'<a href="{attr(m.group(2))}"{link_attrs(m.group(2))}>{m.group(1)}</a>', note[0])
        out.append(f'  <p class="source-note">{text}</p>')
    return out + ['</div>']


def hero_shot(body, images):
    """![代替テキスト](画像) ／ キャプション"""
    image, caption = fields(body, 'hero-shot', 2)
    return ['<figure class="hero-shot">', '  ' + images.tag(image),
            f'  <figcaption>{caption}</figcaption>', '</figure>']


def pair(body, images):
    """学校（国旗：国名 ／ 国・地域 ／ 校名 ／ 詳細）、回数（2行）、学校 を空行で区切る"""
    groups = split_groups(body)
    if [len(g) for g in groups] != [4, 2, 4]:
        raise BuildError('::: pair は「学校4行」「回数2行」「学校4行」を空行で区切る')
    out = ['<div class="pair">']
    for i, lines in enumerate(groups):
        if i == 1:
            out += ['  <div class="link">', f'    <b>{lines[0]}</b>', f'    <span>{lines[1]}</span>', '  </div>']
            continue
        flag, country, name, detail = lines
        label = flag.removeprefix('国旗：').removeprefix('Flag: ')
        if label == flag or label not in FLAGS:
            raise BuildError(f'国旗は「国旗：{"／".join(FLAGS)}」のいずれか: {flag}')
        svg = (f'<svg class="flag" viewBox="0 0 30 20" role="img" aria-label="{attr(label)}">'
               f'{FLAGS[label]}{FLAG_FRAME}</svg>')
        out += ['  <div class="school">', f'    {svg}', f'    <p class="country">{country}</p>',
                f'    <p class="school-name">{name}</p>', f'    <p class="school-detail">{detail}</p>', '  </div>']
    return out + ['</div>']


def facts(body, images):
    """項目名 ／ : 内容 を空行で区切る"""
    out = ['<div class="facts">', '  <dl>']
    for g in split_groups(body):
        if len(g) != 2 or not g[1].startswith(': '):
            raise BuildError(f'::: facts は「項目名」「: 内容」の2行ずつ: {g}')
        out += [f'    <dt>{g[0]}</dt>', f'    <dd>{g[1][2:]}</dd>']
    return out + ['  </dl>', '</div>']


def days(body, images):
    """ラベル ／ タイトル ／ 説明 を空行で区切る"""
    out = ['<ol class="days">']
    for g in split_groups(body):
        if len(g) != 3:
            raise BuildError(f'::: days は「ラベル」「タイトル」「説明」の3行ずつ: {g}')
        label, title, text = g
        out += ['  <li>', f'    <div class="day-no">{label}</div>', '    <div>',
                f'      <p class="day-title">{title}</p>', f'      <p>{text}</p>', '    </div>', '  </li>']
    return out + ['</ol>']


def photos(body, images):
    """![代替テキスト](画像) を並べ、最後の行がキャプション"""
    lines = fields(body, 'photos')
    if len(lines) < 2:
        raise BuildError('::: photos は画像1行以上とキャプション1行')
    *shots, caption = lines
    return ['<div class="photos">', *('  ' + images.tag(s) for s in shots), '</div>',
            f'<p class="photos-cap">{caption}</p>']


def roles(body, images):
    """### 見出し ／ - 項目 … を空行で区切る"""
    out = ['<div class="roles">']
    for g in split_groups(body):
        if not g[0].startswith('### ') or len(g) < 2 or not all(line.startswith('- ') for line in g[1:]):
            raise BuildError(f'::: roles は「### 見出し」と「- 項目」: {g}')
        out += ['  <div>', f'    <h3>{g[0][4:]}</h3>', '    <ul>',
                *(f'      <li>{line[2:]}</li>' for line in g[1:]), '    </ul>', '  </div>']
    return out + ['</div>']


def q(body, images):
    """設問 ／ 注記 ／ - 項目名 数値% …"""
    lines = fields(body, 'q')
    if len(lines) < 3:
        raise BuildError('::: q は設問・注記・項目1行以上')
    text, note, *items = lines
    out = ['<div class="q">', f'  <p class="q-text">{text}</p>', f'  <p class="q-note">{note}</p>',
           '  <ul class="bars">']
    for item in items:
        m = re.fullmatch(r'- (.+) (\d+)%', item)
        if not m or int(m.group(2)) > 100:
            raise BuildError(f'::: q の項目は「- 項目名 数値%」（100以下）: {item}')
        label, value = m.groups()
        out += ['    <li>',
                f'      <div class="bar-label"><span>{label}</span><span class="bar-val">{value}%</span></div>',
                f'      <div class="track"><div class="fill" style="width:{value}%"></div></div>',
                '    </li>']
    return out + ['  </ul>', '</div>']


def voices(body, images):
    """- 声 …"""
    lines = fields(body, 'voices')
    if not lines or not all(line.startswith('- ') for line in lines):
        raise BuildError('::: voices は「- 声」の行のみ')
    return ['<ul class="voices">', *(f'  <li>{line[2:]}</li>' for line in lines), '</ul>']


def next_block(body, images):
    """## 見出し ／ 本文"""
    h2, text = fields(body, 'next', 2)
    if not h2.startswith('## '):
        raise BuildError(f'::: next の1行目は ## 見出し: {h2}')
    return ['<div class="next">', f'  <h2>{h2[3:]}</h2>', f'  <p>{text}</p>', '</div>']


def cta(body, images):
    """## 見出し ／ 本文 ／ [ボタンの文言](URL)"""
    h2, text, button = fields(body, 'cta', 3)
    m = re.fullmatch(r'\[(.+)\]\((\S+)\)', button)
    if not h2.startswith('## ') or not m:
        raise BuildError('::: cta は「## 見出し」「本文」「[ボタンの文言](URL)」')
    label, href = m.groups()
    return ['<section class="cta">', f'  <h2>{h2[3:]}</h2>', f'  <p>{text}</p>',
            f'  <a class="btn" href="{attr(href)}"{link_attrs(href)}>{label}</a>', '</section>']


# section の外に置くブロックと、section の中に置くブロック
OUTSIDE = {'hero': hero, 'hero-shot': hero_shot, 'pair': pair, 'facts': facts, 'next': next_block, 'cta': cta}
INSIDE = {'days': days, 'photos': photos, 'roles': roles, 'q': q, 'voices': voices}


# ── 本文 ──────────────────────────────────────────────

def split_blocks(lines):
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line:
            i += 1
            continue
        if line.startswith(':::'):
            name = line[3:].strip()
            if name not in OUTSIDE and name not in INSIDE:
                raise BuildError(f'未知のブロック: {line}')
            try:
                close = lines.index(':::', i + 1)
            except ValueError:
                raise BuildError(f'閉じていないブロック: {line}') from None
            blocks.append((name, lines[i + 1:close]))
            i = close + 1
            continue
        if line.startswith('## '):
            kind = 'h2'
        elif line.startswith('### '):
            kind = 'h3'
        elif line.startswith('<'):
            kind = 'raw'
        elif line.startswith(('#', '- ', '![')):
            raise BuildError(f'この書式はブロックの中でのみ使える: {line}')
        else:
            kind = 'p'
            if lines[i - 1] and blocks and blocks[-1][0] == 'p':
                raise BuildError(f'段落の途中で改行しない（段落は空行で区切る）: {line}')
        blocks.append((kind, [line]))
        i += 1
    return blocks


def render_section(children):
    # 原本の整形：複数行のブロックの前後に空行を入れる（h2 の直後を除く）
    out = ['<section>']
    prev_kind, prev_lines = None, None
    for kind, lines in children:
        if prev_kind not in (None, 'h2') and (len(prev_lines) > 1 or len(lines) > 1):
            out.append('')
        out += indent(lines)
        prev_kind, prev_lines = kind, lines
    return out + ['</section>']


def render_body(lines, images):
    top, section = [], None
    for kind, body in split_blocks(lines):
        if kind == 'h2' or kind in OUTSIDE:
            if section is not None:
                top.append(render_section(section))
                section = None
            if kind == 'h2':
                section = [('h2', [f'<h2>{body[0][3:]}</h2>'])]
            else:
                top.append(OUTSIDE[kind](body, images))
            continue
        if section is None:
            raise BuildError(f'## 見出しより前には置けない: {body[0] if kind in ("h3", "raw", "p") else "::: " + kind}')
        if kind == 'h3':
            section.append((kind, [f'<h3>{body[0][4:]}</h3>']))
        elif kind == 'raw':
            section.append((kind, body))
        elif kind == 'p':
            section.append((kind, [f'<p>{body[0]}</p>']))
        else:
            section.append((kind, INSIDE[kind](body, images)))
    if section is not None:
        top.append(render_section(section))
    out = []
    for block in top:
        if out:
            out.append('')
        out += indent(block)
    return '\n'.join(out)


# ── ページ ────────────────────────────────────────────

def parse_front_matter(text, path, required=FRONT_MATTER_KEYS, optional=()):
    lines = text.split('\n')
    try:
        if lines[0] != '---':
            raise ValueError
        end = lines.index('---', 1)
    except ValueError:
        raise BuildError(f'{path.name}: 先頭に --- で囲んだ front matter が必要') from None
    allowed = (*required, *optional)
    meta = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(': ')
        if not sep or key not in allowed or key in meta or not value:
            raise BuildError(f'{path.name}: front matter の行が不正（使える項目は {", ".join(allowed)}）: {line}')
        meta[key] = value
    missing = [key for key in required if key not in meta]
    if missing:
        raise BuildError(f'{path.name}: front matter に {", ".join(missing)} がない')
    return meta, lines[end + 1:]


def fill(template, values):
    def replace(m):
        if m.group(1) not in values:
            raise BuildError(f'テンプレートの差し込み先に対応する値がない: {m.group(0)}')
        return values[m.group(1)]
    return re.sub(r'\{\{ (\w+) \}\}', replace, template)


def build(md_path, lang='ja'):
    slug = md_path.stem
    if lang != 'ja' and not (ROOT / 'content' / f'{slug}.md').is_file():
        raise BuildError(f'{md_path.relative_to(ROOT)}: 元になる日本語版 content/{slug}.md がない')
    meta, body = parse_front_matter(md_path.read_text(encoding='utf-8'), md_path, optional=OPTIONAL_KEYS)
    chrome = CHROME[lang]
    images = Images(slug, chrome['root'])
    logo = Images(LOGO_SLUG, chrome['root'])
    logo.require('logo.png')
    case_link = chrome['case_link']
    page = fill((ROOT / 'templates' / 'case.html').read_text(encoding='utf-8'), {
        **{key: value for key, value in chrome.items() if key != 'case_link'},
        'case_href': f'href="{attr(case_link)}"',  # 自社サイト内の移動なので同じタブで開く
        'title': attr(meta['title']),
        'description': attr(meta['description']),
        'school': attr(meta['school']),
        'images': logo.url,
        'content': render_body(body, images),
    })
    out = ROOT / 'public' / ('' if lang == 'ja' else lang) / slug / 'index.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding='utf-8')
    return out


# ── 事例一覧 ──────────────────────────────────────────

INDEX_IMAGES = 'images/index'
PARTNER_LOGOS = {'EducationLink': 'educationlink.jpg'}


def public_file(src):
    if not (ROOT / 'public' / src).is_file():
        raise BuildError(f'画像ファイルがない: public/{src}')
    return src


def inline(text):
    """**太字** だけを <strong> にする（Wix の強調をそのまま写す）"""
    parts = html.escape(text, quote=False).split('**')
    if len(parts) % 2 == 0:
        raise BuildError(f'** の対応が取れていない: {text}')
    return ''.join(f'<strong>{p}</strong>' if i % 2 else p for i, p in enumerate(parts))


def card(ref):
    """「- 事例」1行をカードにする。external/ は Wix に残っている事例（front matter のみ）"""
    path = ROOT / 'content' / f'{ref}.md'
    if not path.is_file():
        raise BuildError(f'index.md が参照する事例がない: {path.relative_to(ROOT)}')
    text = path.read_text(encoding='utf-8')
    if ref.startswith('external/'):
        meta, body = parse_front_matter(text, path, ('title', 'description', 'image', 'url'), ('role', 'partner'))
        if any(body):
            raise BuildError(f'{path.name}: external/ には front matter だけを書く')
        href, photo = meta['url'], f'images/external/{meta["image"]}'
    else:
        meta, _ = parse_front_matter(text, path, optional=OPTIONAL_KEYS)
        href, photo = f'/{ref}/', f'images/{ref}/{meta["image"]}' if 'image' in meta else None
    schools = ''.join(f'<span>{attr(s)}</span>' for s in meta['title'].split(' × '))
    out = ['<li class="card">', f'  <p class="card-schools">{schools}</p>']
    if 'role' in meta or 'partner' in meta:
        if 'role' not in meta or meta.get('partner') not in PARTNER_LOGOS:
            raise BuildError(f'{path.name}: role と partner（{"／".join(PARTNER_LOGOS)}）は組で書く')
        logo = public_file(f'{INDEX_IMAGES}/{PARTNER_LOGOS[meta["partner"]]}')
        out.append(f'  <p class="card-role">{attr(meta["role"])}<img src="{logo}" alt="{attr(meta["partner"])}" width="97" height="19"></p>')
    out += [f'  <p class="card-desc">{attr(meta["description"])}</p>',
            f'  <p class="card-more"><a href="{attr(href)}"{link_attrs(href)}>→もっと読む</a></p>']
    if photo:
        out.append(f'  <a class="card-photo" href="{attr(href)}"{link_attrs(href)} tabindex="-1" aria-hidden="true"><img src="{public_file(photo)}" alt=""></a>')
    return out + ['</li>']


def index_program(heading, logo, cards):
    """## 見出し（1〜2行）／ ![代替テキスト](ロゴ)（任意）／ - 事例"""
    if not cards:
        raise BuildError(f'index.md:「{" ".join(heading)}」に事例がない')
    spans = ''.join(f'<span>{attr(h)}</span>' for h in heading)
    head = ['    <div class="program-head">', f'      <h2>{spans}</h2>']
    if logo:
        src = public_file(f'{INDEX_IMAGES}/{logo[1]}')
        head.append(f'      <img class="program-logo" src="{src}" alt="{attr(logo[0])}">')
    return ['<section class="program">', '  <div class="inner">', *head, '    </div>',
            f'    <ul class="cards{" single" if len(cards) == 1 else ""}">',
            *indent([line for c in cards for line in c], 6), '    </ul>', '  </div>', '</section>']


def index_news(body):
    """[ラベル] ／ URL ／ タイトル（**太字** 可）を空行で区切る"""
    items = []
    for g in split_groups(body):
        if len(g) != 3 or not (g[0].startswith('[') and g[0].endswith(']')) or not g[1].startswith('https://'):
            raise BuildError(f'::: news は「[ラベル]」「URL」「タイトル」の3行ずつ: {g}')
        items.append(f'      <li><span class="news-label">{attr(g[0])}</span> <a href="{attr(g[1])}"{link_attrs(g[1])}>{inline(g[2])}</a></li>')
    return ['<section class="news">', '  <div class="inner">', '    <h2>最新事例</h2>', '    <ul>', *items,
            '    </ul>', '  </div>', '</section>']


def index_voices(body):
    """### 分類 ／ 小見出し（任意）／ - 声（**太字** 可）"""
    cats = []
    for line in body:
        if not line:
            continue
        if line.startswith('### '):
            cats.append((line[4:], []))
        elif not cats:
            raise BuildError(f'::: voices は ### 分類 から始める: {line}')
        elif line.startswith('- '):
            if not cats[-1][1]:
                cats[-1][1].append((None, []))
            cats[-1][1][-1][1].append(line[2:])
        else:
            cats[-1][1].append((line, []))
    out = ['<section class="voices">', '  <div class="inner">', '    <h2>生徒たちの声</h2>']
    for name, subs in cats:
        wide = len(subs) == 1 and subs[0][0] is None and len(subs[0][1]) >= 6
        out += [f'    <div class="voice-cat{" voice-wide" if wide else ""}">', f'      <h3>{attr(name)}</h3>', '      <div class="voice-subs">']
        for label, quotes in subs:
            if not quotes:
                raise BuildError(f'::: voices の「{label or name}」に声がない')
            out += ['        <div class="voice-sub">', *([f'          <h4>{attr(label)}</h4>'] if label else []),
                    '          <ul>', *(f'            <li>{inline(q)}</li>' for q in quotes), '          </ul>', '        </div>']
        out += ['      </div>', '    </div>']
    return out + ['  </div>', '</section>']


def build_index():
    """content/index.md（::: news ／ ## プログラム ＋ - 事例 ／ ::: voices）から public/index.html を作る"""
    path = ROOT / 'content' / 'index.md'
    meta, body = parse_front_matter(path.read_text(encoding='utf-8'), path, ('title', 'description'))
    blocks, current = [], None

    def close_program():
        nonlocal current
        if current:
            blocks.append(index_program(*current))
        current = None

    i = 0
    while i < len(body):
        line = body[i]
        if line.startswith(':::'):
            renderer = {'news': index_news, 'voices': index_voices}.get(line[3:].strip())
            if not renderer:
                raise BuildError(f'index.md: 未知のブロック: {line}')
            try:
                end = body.index(':::', i + 1)
            except ValueError:
                raise BuildError(f'index.md: 閉じていないブロック: {line}') from None
            close_program()
            blocks.append(renderer(body[i + 1:end]))
            i = end + 1
            continue
        if line.startswith('## '):
            if current is None or current[2]:
                close_program()
                current = ([], None, [])
            current[0].append(line[3:])
        elif line.startswith('![') and current and not current[2]:
            m = re.fullmatch(r'!\[([^\]]+)\]\(([\w.-]+)\)', line)
            if not m:
                raise BuildError(f'index.md: ロゴは ![代替テキスト](ファイル名) で書く: {line}')
            current = (current[0], m.groups(), current[2])
        elif line.startswith('- ') and current:
            current[2].append(card(line[2:]))
        elif line:
            raise BuildError(f'index.md の書式が不正: {line}')
        i += 1
    close_program()
    logo = Images(LOGO_SLUG)
    logo.require('logo.png')
    page = fill((ROOT / 'templates' / 'index.html').read_text(encoding='utf-8'), {
        'title': attr(meta['title']),
        'description': attr(meta['description']),
        'images': logo.url.removeprefix('../'),
        'content': '\n\n'.join('\n'.join(b) for b in blocks),
    })
    for src in re.findall(r'src="(images/[^"]+)"', page):
        public_file(src)
    out = ROOT / 'public' / 'index.html'
    out.write_text(page, encoding='utf-8')
    return out


def main():
    try:
        for md_path in sorted((ROOT / 'content').glob('*.md')):
            if md_path.name != 'index.md':
                print(build(md_path).relative_to(ROOT))
        for md_path in sorted((ROOT / 'content' / 'en').glob('*.md')):
            print(build(md_path, 'en').relative_to(ROOT))
        print(build_index().relative_to(ROOT))
    except BuildError as e:
        sys.exit(f'build error: {e}')


if __name__ == '__main__':
    main()
