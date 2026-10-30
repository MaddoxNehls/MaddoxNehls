"""Build the profile SVGs. Runs daily from .github/workflows/daily.yml.

Writes assets/card-*.svg (the neofetch card, Uptime counted from 2017), assets/tiles-*.svg,
assets/signoff-*.svg (a different line each day), and refreshes the Letterboxd block in
README.md when the LETTERBOXD_USER environment variable is set.

Needs: fonttools, brotli
"""
import base64, datetime, io, os, re, urllib.request
import xml.etree.ElementTree as ET
from html import escape
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools import subset

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'assets')
TODAY = datetime.date.today()
STARTED = datetime.date(2017, 1, 1)

THEMES = {
    'dark':  dict(key='#7ee787', val='#e6edf3', dot='#3d444d', head='#f0f6fc', art='#8b949e', muted='#9198a1', line='#3d444d'),
    'light': dict(key='#116329', val='#1f2328', dot='#c8d1da', head='#1f2328', art='#59636e', muted='#59636e', line='#d1d9e0'),
}
FS, CW, LH = 16, 9.6, 21          # card text: font size, char width, line height
AFS, ACW, ALH = 11, 6.6, 14.2     # portrait text
PANEL_W = 62                      # card panel width in characters

def uptime(start, now):
    y, m, d = now.year - start.year, now.month - start.month, now.day - start.day
    if d < 0:
        m -= 1
        d += (now.replace(day=1) - datetime.timedelta(days=1)).day
    if m < 0:
        y -= 1; m += 12
    s = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return f"{s(y, 'year')}, {s(m, 'month')}, {s(d, 'day')}"

# (key, value); None is a spacer; ('#', title) is a section header
ROWS = [
    ('#', 'maddox@nehls'),
    ('OS', 'Windows 11, macOS'),
    ('Uptime', uptime(STARTED, TODAY)),
    ('Host', 'Beaverton, Oregon'),
    ('Kernel', 'Full Stack Software Engineer'),
    ('Shell', 'Oregon State University, B.S. CS (Honors)'),
    ('IDE', 'VS Code, Cursor, CLion'),
    None,
    ('Languages.Code', 'TypeScript, Python, Go, Rust, Java, PHP'),
    ('Languages.Web', 'React, Next.js, Vue, Tailwind'),
    ('Languages.Data', 'PostgreSQL, MySQL, MongoDB'),
    None,
    ('Superpower', 'Finding the bug everyone gave up on'),
    ('Hackathon.BOLT2', 'Top finish'),
    ('Shipped', 'Pulse Floor, a live multiplayer game'),
    None,
    ('Hobbies.Active', 'Gym, rock climbing'),
    ('Hobbies.Build', 'Custom mechanical keyboards'),
    ('Hobbies.Watch', 'Movies and TV shows'),
    ('Hobbies.Explore', 'Traveling'),
    None,
    ('#', 'Contact'),
    ('Portfolio', 'maddoxnehls.vercel.app'),
    ('Email', 'maddoxmnehls@gmail.com'),
    ('LinkedIn', 'in/maddox-nehls'),
]

TILES = [
    ('Climbing', 'Bouldering, V5', 'mountain'),
    ('Gym', '5-6 days a week', 'dumbbell'),
    ('Keyboards', 'Gasket 75%, lubed', 'keyboard'),
    ('Movies & TV', 'Money Heist fan', 'film'),
    ('Travel', 'Next stop: Mexico', 'plane'),
]
ICONS = {  # 24x24 stroke icons
    'mountain': '<path d="m8 3 4 8 5-5 5 15H2L8 3z"/>',
    'dumbbell': '<path d="M6 6v12M3 9v6M18 6v12M21 9v6M6 12h12"/>',
    'keyboard': '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01M10 13h.01M14 13h.01M18 13h.01M8 16h8"/>',
    'film': '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M3 7.5h4M3 12h18M3 16.5h4M17 3v18M17 7.5h4M17 16.5h4"/>',
    'plane': '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>',
}

def font_face():
    faces = []
    for w in (400, 700):
        inst = instancer.instantiateVariableFont(TTFont(os.path.join(ROOT, 'scripts', 'fonts', 'JetBrainsMono.ttf')), {'wght': w})
        opts = subset.Options(); opts.flavor = 'woff2'; opts.layout_features = []
        sub = subset.Subsetter(opts); sub.populate(text=''.join(chr(c) for c in range(32, 127)) + '—'); sub.subset(inst)
        buf = io.BytesIO(); inst.flavor = 'woff2'; inst.save(buf)
        faces.append("@font-face{font-family:'J';font-weight:%d;src:url(data:font/woff2;base64,%s) format('woff2')}" % (w, base64.b64encode(buf.getvalue()).decode()))
    return ''.join(faces)
FACE = font_face()
BASE_CSS = f"{FACE}text{{font-family:'J',ui-monospace,Consolas,monospace;font-size:{FS}px;white-space:pre;font-variant-ligatures:none}}"

def svg(w, h, css, body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><style>{BASE_CSS}{css}</style>{body}</svg>'

def card(mode):
    t = THEMES[mode]
    with open(os.path.join(ROOT, 'data', f'portrait-{mode}.txt'), encoding='utf-8') as fh:
        art = fh.read().splitlines()
    cols = max(len(l) for l in art)
    ax, px = 18, round(18 + cols * ACW + 36)
    lines = []
    for i, row in enumerate(ROWS):
        if row is None:
            lines.append(f'<tspan fill="{t["dot"]}">.</tspan>'); continue
        k, v = row
        if k == '#':
            label = v if i == 0 else f'- {v}'
            lines.append(f'<tspan fill="{t["head"]}">{escape(label)}</tspan> <tspan fill="{t["dot"]}">{"—" * (PANEL_W - len(label) - 1)}</tspan>')
            continue
        dots = '.' * max(2, PANEL_W - len(k) - len(v) - 6)
        lines.append(f'<tspan fill="{t["dot"]}">. </tspan><tspan fill="{t["key"]}">{escape(k)}</tspan><tspan fill="{t["val"]}">:</tspan> '
                     f'<tspan fill="{t["dot"]}">{dots}</tspan> <tspan fill="{t["val"]}">{escape(v)}</tspan>')
    art_h, pan_h = len(art) * ALH, len(lines) * LH
    inner = max(art_h, pan_h); top = (inner - pan_h) // 2
    W, H = round(px + PANEL_W * CW + 18), round(inner + 36)
    css = (f".a{{font-size:{AFS}px}}.r{{opacity:0;animation:in .35s ease-out forwards}}@keyframes in{{to{{opacity:1}}}}"
           ".cur{animation:blink 1.1s steps(1) infinite}@keyframes blink{50%{opacity:0}}")
    body = [f'<text class="a" x="{ax}" y="{18 + (inner - art_h) // 2 + 10}" fill="{t["art"]}">']
    body += [f'<tspan x="{ax}" dy="{0 if r == 0 else ALH}">{escape(s)}</tspan>' for r, s in enumerate(art)]
    body.append('</text>')
    body += [f'<text class="r" style="animation-delay:{.15 + i * .07:.2f}s" x="{px}" y="{18 + top + 15 + i * LH}">{s}</text>' for i, s in enumerate(lines)]
    last_y = 18 + top + 15 + (len(lines) - 1) * LH
    body.append(f'<rect class="cur" x="{px}" y="{last_y + LH - 14}" width="{CW}" height="17" fill="{t["key"]}"/>')
    return svg(W, H, css, ''.join(body))

def tiles(mode):
    t = THEMES[mode]
    W, H, gap, n = 1100, 132, 14, len(TILES)
    tw = (W - 2 - gap * (n - 1)) / n
    body = []
    for i, (title, detail, icon) in enumerate(TILES):
        x = 1 + i * (tw + gap)
        body.append(f'<rect x="{x:.1f}" y="1" width="{tw:.1f}" height="{H - 2}" rx="12" fill="none" stroke="{t["line"]}" stroke-width="1.5"/>'
                    f'<g transform="translate({x + 20:.1f},20) scale(1.25)" fill="none" stroke="{t["key"]}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{ICONS[icon]}</g>'
                    f'<text x="{x + 20:.1f}" y="84" font-weight="700" fill="{t["val"]}">{escape(title)}</text>'
                    f'<text x="{x + 20:.1f}" y="108" style="font-size:13.5px" fill="{t["muted"]}">{escape(detail)}</text>')
    return svg(W, H, '', ''.join(body))

def signoff(mode, line):
    """Two lines at a larger size: the echo, then the author as a comment when there is one."""
    t = THEMES[mode]
    text, _, who = line.partition(' | ')
    fs, cw = 22, 13.2
    W, H = 1100, 104 if who else 64
    shown = f'"{text}"'
    end = 18 + (len('$ echo ') + len(shown)) * cw
    css = ".cur{animation:blink 1.1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
    body = (f'<text x="18" y="40" style="font-size:{fs}px"><tspan fill="{t["key"]}">$ </tspan><tspan fill="{t["val"]}">echo {escape(shown)}</tspan></text>'
            f'<rect class="cur" x="{end + 8:.1f}" y="22" width="{cw}" height="24" fill="{t["key"]}"/>')
    if who:
        body += f'<text x="18" y="84" style="font-size:{fs - 4}px" fill="{t["muted"]}"># {escape(who)}</text>'
    return svg(W, H, css, body)

def todays_line():
    with open(os.path.join(ROOT, 'data', 'lines.txt'), encoding='utf-8') as fh:
        lines = [l.strip() for l in fh if l.strip() and not l.startswith('#')]
    return lines[TODAY.toordinal() % len(lines)]

def letterboxd(user):
    """Latest three films from a public Letterboxd RSS feed, as Markdown."""
    req = urllib.request.Request(f'https://letterboxd.com/{user}/rss/', headers={'User-Agent': 'profile-readme'})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
    ns = {'lb': 'https://letterboxd.com'}
    films = []
    for item in root.iter('item'):
        title = item.findtext('lb:filmTitle', namespaces=ns)
        if title and title not in films:
            films.append(title)
        if len(films) == 3:
            break
    return f'**Recently logged on [Letterboxd](https://letterboxd.com/{user}/):** ' + ' · '.join(films) if films else ''

def write(name, text):
    with open(os.path.join(ASSETS, name), 'w', encoding='utf-8') as fh:
        fh.write(text)

if __name__ == '__main__':
    os.makedirs(ASSETS, exist_ok=True)
    line = todays_line()
    for mode in THEMES:
        write(f'card-{mode}.svg', card(mode))
        write(f'tiles-{mode}.svg', tiles(mode))
        write(f'signoff-{mode}.svg', signoff(mode, line))
    user = os.environ.get('LETTERBOXD_USER', '').strip()
    if user:
        path = os.path.join(ROOT, 'README.md')
        with open(path, encoding='utf-8') as fh:
            readme = fh.read()
        block = letterboxd(user)
        readme = re.sub(r'(<!-- letterboxd:start -->).*?(<!-- letterboxd:end -->)', lambda m: f'{m[1]}\n{block}\n{m[2]}', readme, flags=re.S)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(readme)
    print('built', uptime(STARTED, TODAY), '|', line)
