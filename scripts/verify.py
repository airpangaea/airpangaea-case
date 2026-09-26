#!/usr/bin/env python3
"""公開用 HTML が承認済み原本と一致しているかを確かめる。

使い方: python3 scripts/build.py && python3 scripts/verify.py （標準ライブラリのみ）

source/<slug>.html ごとに public/<slug>/index.html と突き合わせる。
原本には先に APPROVED_CHANGES（指示を受けて意図的に変えた箇所）を当ててから比べる。
  1. 本文テキスト  文書全体（ヘッダー・footer 含む）を対象に、テキストと
                   alt・aria-label・meta description・href などの属性値
  2. 画像          書き出した画像ファイルが原本の base64 を復号したバイト列と同一で、余分な画像がないこと
  3. 本文 HTML     <main>…</main> の中だけを対象に、画像の src を除いて原本とバイト単位で一致すること
                   （CLAUDE.md「絶対に守ること 1.」が指す本文・見出し・数値・設問文・有効回答数は
                   すべて <main> の中にある。ヘッダー／footer／<head> はサイト共通の chrome で、
                   ユーザーの指示により随時変更する対象。そちらの文言・リンク先の変更は
                   引き続きチェック1（文書全体のテキスト）で検出される）
差があれば終了コード 1。差が出たら原本ではなくテンプレート側（content/・templates/・scripts/build.py）を直す。
"""
import base64
import difflib
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT_ATTRS = ('lang', 'content', 'href', 'alt', 'aria-label', 'title')
DATA_URI = re.compile(r'src="data:image/(?:png|jpeg);base64,([A-Za-z0-9+/=]+)"')
IMG_SRC = re.compile(r'<img\b[^>]*?\ssrc="([^"]+)"')

# 原本から意図的に変えている箇所：(内容, 原本の文字列, 出力の文字列)。原本の文字列はそれぞれ原本に1か所だけあること。
# ヘッダー／footer／<head> は <main> の外＝チェック3の対象外だが、リンク先や aria-label・alt など
# チェック1（TEXT_ATTRS）が見る値を追加・変更した場合はここに登録し、文書全体のテキスト一致を保つ。
# 純粋な CSS・class 名だけの変更（チェック1が見ない）は登録不要。
APPROVED_CHANGES = {
    'tokushima-kita-2025': [
        # 2026-09-16 指示：ヘッダーを Wix の導入事例ページに合わせる際、お問い合わせボタンも
        # 原本の /contact（404）から #contactus に変更し、外部リンクとして新しいタブで開くようにした
        ('お問い合わせボタンのリンク先',
         '<a class="btn" href="https://ja.airpangaea.com/contact">',
         '<a class="btn" href="https://ja.airpangaea.com/#contactus" target="_blank" rel="noopener noreferrer">'),
        # 2026-09-15 指示：ヘッダーを Wix の導入事例ページ（https://ja.airpangaea.com/case）に合わせる
        ('ヘッダーの書体読み込み（Raleway を追加）',
         '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Noto+Serif+JP:wght@500;600&display=swap" rel="stylesheet">',
         '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Noto+Serif+JP:wght@500;600&family=Raleway:wght@400;700&display=swap" rel="stylesheet">'),
        # 2026-09-15 指示：favicon を Wix と同じ画像にする
        ('favicon（Wix の導入事例ページと同じロゴ画像）',
         '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Noto+Serif+JP:wght@500;600&family=Raleway:wght@400;700&display=swap" rel="stylesheet">',
         '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Noto+Serif+JP:wght@500;600&family=Raleway:wght@400;700&display=swap" rel="stylesheet">\n'
         '<link rel="icon" type="image/png" sizes="32x32" href="../images/favicon/favicon-32.png">\n'
         '<link rel="icon" type="image/png" sizes="192x192" href="../images/favicon/favicon-192.png">\n'
         '<link rel="apple-touch-icon" href="../images/favicon/apple-touch-icon.png">'),
        # 2026-09-26 指示：西大和ページの出典の注記を細字にするため、本文書体に Light（300）を追加
        ('本文書体の読み込みに細字（300）を追加',
         'family=Noto+Sans+JP:wght@400;500;700&',
         'family=Noto+Sans+JP:wght@300;400;500;700&'),
        # 2026-09-15 指示：ヘッダー右上のログイン・日本語を削除
        ('ヘッダー右上のログイン・日本語を削除',
         '    </nav>\n'
         '    <div class="util"><a href="https://ja.airpangaea.com">ログイン</a><span>日本語</span></div>\n'
         '  </div>\n'
         '</header>',
         '    </nav>\n'
         '  </div>\n'
         '</header>'),
        # 2026-09-16 指示：徳島北ページの footer を事例一覧ページと揃え、SNS アイコン（Instagram・X・Facebook）を追加
        ('footer に SNS アイコンを追加（一覧ページと同じ Instagram・X・Facebook）',
         '      <a href="https://ja.airpangaea.com/tokushoho">特定商取引法に基づく表記</a>\n'
         '    </div>\n'
         '  </div>\n'
         '</footer>',
         '      <a href="https://ja.airpangaea.com/tokushoho">特定商取引法に基づく表記</a>\n'
         '    </div>\n'
         '    <div class="social">\n'
         '      <a href="https://www.instagram.com/airpangaeajapan/" aria-label="Instagram"><img alt=""></a>\n'
         '      <a href="https://x.com/airpangaeajapan" aria-label="X"><img alt=""></a>\n'
         '      <a href="https://www.facebook.com/airpangaeajapan" aria-label="Facebook"><img alt=""></a>\n'
         '    </div>\n'
         '  </div>\n'
         '</footer>'),
    ],
}


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script'):
            self.skip += 1
        self.items += [f'[{tag} {name}] {value}' for name, value in attrs if name in TEXT_ATTRS and value is not None]

    def handle_endtag(self, tag):
        if tag in ('style', 'script'):
            self.skip -= 1

    def handle_data(self, data):
        # 整形用の空白だけのテキストは無視し、連続する空白はブラウザと同じく1つにまとめる
        if not self.skip and data.strip():
            self.items.append(re.sub(r'\s+', ' ', data))


def text_items(markup):
    parser = TextExtractor()
    parser.feed(markup)
    parser.close()
    return parser.items


def extract_main(html_text, label):
    m = re.search(r'<main>.*</main>', html_text, re.S)
    if not m:
        raise SystemExit(f'{label}: <main>…</main> が見つからない')
    return m.group(0)


def diff(a, b, a_name, b_name, limit=60):
    lines = list(difflib.unified_diff(a, b, a_name, b_name, lineterm='', n=1))
    shown = [line if len(line) <= 200 else line[:200] + '…' for line in lines[:limit]]
    if len(lines) > limit:
        shown.append(f'…ほか {len(lines) - limit} 行')
    return '\n'.join('    ' + line for line in shown)


def verify(source_path):
    slug = source_path.stem
    public_path = ROOT / 'public' / slug / 'index.html'
    print(slug)
    if not public_path.is_file():
        print(f'  NG  {public_path.relative_to(ROOT)} がない（先に scripts/build.py を実行する）')
        return False
    source = source_path.read_text(encoding='utf-8')
    generated = public_path.read_text(encoding='utf-8')
    src_name, gen_name = str(source_path.relative_to(ROOT)), str(public_path.relative_to(ROOT))
    ok = True

    # 0. 意図的な差分を原本に当てる
    changes = APPROVED_CHANGES.get(slug, [])
    for note, old, new in changes:
        found = source.count(old)
        if found != 1:
            ok = False
            print(f'  NG  意図的な差分「{note}」: 原本に対象の文字列が {found} か所ある（1か所のはず）')
        source = source.replace(old, new)
    if changes:
        src_name += '（意図的な差分を反映）'
        print(f'  --  意図的な差分 {len(changes)} か所を原本に反映して比較: ' + '、'.join(note for note, _, _ in changes))

    # 1. 本文テキスト
    a, b = text_items(source), text_items(generated)
    if a == b:
        print(f'  OK  本文テキスト: 差分なし（{len(a)} 項目）')
    else:
        ok = False
        print('  NG  本文テキスト: 差分あり')
        print(diff(a, b, src_name, gen_name))

    # 2. 画像（原本の埋め込み画像4点が public/images/<slug>/ に同じバイト列で書き出されていること。
    #    favicon・SNS アイコンなど、あとから追加した chrome 用の画像は対象外）
    embedded = DATA_URI.findall(source)
    own_folder = f'images/{slug}/'
    srcs = [s for s in IMG_SRC.findall(generated) if own_folder in s]
    problems = []
    if len(embedded) != len(srcs):
        problems.append(f'原本の埋め込み画像 {len(embedded)} 点に対し、出力の img は {len(srcs)} 点')
    referenced = set()
    for b64, src in zip(embedded, srcs):
        if src.startswith('data:'):
            problems.append(f'base64 のまま残っている: {src[:40]}…')
            continue
        file = (public_path.parent / src).resolve()
        referenced.add(file)
        if not file.is_file():
            problems.append(f'画像ファイルがない: {src}')
        elif file.read_bytes() != base64.b64decode(b64, validate=True):
            problems.append(f'原本の画像とバイト列が異なる: {src}')
    image_dir = ROOT / 'public' / 'images' / slug
    extra = sorted(p.name for p in image_dir.iterdir() if p.is_file() and p.resolve() not in referenced) if image_dir.is_dir() else []
    if extra:
        problems.append(f'原本に無い画像が {image_dir.relative_to(ROOT)} にある: {", ".join(extra)}')
    if problems:
        ok = False
        print('  NG  画像:')
        print('\n'.join('    ' + p for p in problems))
    else:
        print(f'  OK  画像: {len(srcs)} 点とも原本の base64 を復号したバイト列と同一、余分な画像なし')

    # 3. 本文 HTML（<main>…</main> だけを対象に、画像の src を出力側の値に置き換えた原本と比べる）
    if len(embedded) == len(srcs):
        replacements = iter(srcs)
        expected = DATA_URI.sub(lambda m: f'src="{next(replacements)}"', source)
        expected_main, generated_main = extract_main(expected, src_name), extract_main(generated, gen_name)
        excluded = f'画像の src {len(srcs)} か所' + (f'と意図的な差分 {len(changes)} か所' if changes else '')
        if expected_main == generated_main:
            print(f'  OK  本文 HTML（<main>）: {excluded}を除き、原本とバイト単位で一致')
        else:
            ok = False
            print(f'  NG  本文 HTML（<main>）: {excluded}以外にも差分あり')
            print(diff(expected_main.split('\n'), generated_main.split('\n'), src_name, gen_name))
    return ok


def main():
    sources = sorted((ROOT / 'source').glob('*.html'))
    results = [verify(path) for path in sources]
    sys.exit(0 if results and all(results) else 1)


if __name__ == '__main__':
    main()
