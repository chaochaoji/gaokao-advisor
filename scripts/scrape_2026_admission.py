"""Scrape 2026 university admission rules from 阳光高考 (gaokao.chsi.com.cn)."""
import os, sys, re, time, sqlite3
from pathlib import Path
import requests
from bs4 import BeautifulSoup

DB = Path('D:/zhangxuefengagent/data/zhangxuefeng.db')
OUT = Path('D:/zhangxuefengagent/data/extracted/2026_招生政策')
OUT.mkdir(parents=True, exist_ok=True)

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

conn = sqlite3.connect(str(DB))
conn.execute("""CREATE TABLE IF NOT EXISTS raw_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL, source_dir TEXT NOT NULL,
    format TEXT NOT NULL, content TEXT NOT NULL,
    word_count INTEGER DEFAULT 0, metadata TEXT,
    status TEXT DEFAULT 'raw',
    created_at TEXT DEFAULT (datetime('now'))
)""")
in_db = set(r[0] for r in conn.execute('SELECT source_file FROM raw_data').fetchall())

# === Collected URLs from search results ===
urls = [
    # Provincial rules
    ('https://gaokao.chsi.com.cn/gkxx/zc/ss/202604/20260429/2293463207-8.html', '黑龙江2026年普通高等学校招生工作规定', '省级规定'),
    ('https://gaokao.chsi.com.cn/gkxx/zc/ss/202606/20260607/2293673157.html', '陕西2026年普通高等学校招生工作实施办法', '省级规定'),
    ('https://gaokao.chsi.com.cn/gkxx/zc/ss/202605/20260509/2293469089-5.html', '北京2026年普通高等学校招生工作规定', '省级规定'),
    ('https://gaokao.chsi.com.cn/gkxx/zc/ss/202604/20260414/2293468280.html', '贵州2026年普通高校招生工作通知', '省级规定'),
    ('https://gaokao.chsi.com.cn/gkxx/zc/ss/202605/20260519/2293475207-9.html', '安徽2026年普通高校招生工作实施办法', '省级规定'),
    ('https://gaokao.chsi.com.cn/gkxx/zc/ss/202606/20260602/2293523966.html', '湖南2026年普通高等学校招生工作通知', '省级规定'),
    ('https://gaokao.chsi.com.cn/gkxx/zc/ss/202606/20260615/2293808782.html', '浙江2026年网上填报志愿工作通知', '省级规定'),
    # University 章程
    ('https://gaokao.chsi.com.cn/zsgs/zhangcheng/listVerifedZszc--method-view,schId-549,infoId-7657200364.dhtml', '西安电子科技大学2026年本科招生章程', '高校章程'),
    ('https://gaokao.chsi.com.cn/zsgs/zhangcheng/listVerifedZszc--method-view,schId-473,infoId-7601035628.dhtml', '西南石油大学2026年本科招生章程', '高校章程'),
    ('https://gaokao.chsi.com.cn/zsgs/zhangcheng/listVerifedZszc--infoId-7659592123,method-view,schId-177.dhtml', '哈尔滨工程大学2026年本科招生章程', '高校章程'),
    ('https://gaokao.chsi.com.cn/zsgs/zhangcheng/listVerifedZszc--infoId-7657440953,method-view,schId-5638179069.dhtml', '信阳科技职业学院2026年招生章程', '高校章程'),
    ('https://gaokao.chsi.com.cn/zsgs/zhangcheng/listVerifedZszc--method-view,schId-1787,infoId-7656762789.dhtml', '兰州信息科技学院2026年招生章程', '高校章程'),
    ('https://gaokao.chsi.com.cn/zsgs/zhangcheng/listVerifedZszc--infoId-7595735903,method-view,schId-1905.dhtml', '武汉工程科技学院2026年招生章程', '高校章程'),
    ('https://gaokao.chsi.com.cn/zsgs/zhangcheng/listVerifedZszc--infoId-7656717607,method-view,schId-203.dhtml', '北京大学2026年招生章程', '高校章程'),
    ('https://gaokao.chsi.com.cn/zsgs/zhangcheng/listVerifedZszc--method-view,schId-233,infoId-7651090881.dhtml', '中国人民大学2026年招生章程', '高校章程'),
    # Policy guide
    ('https://gaokao.chsi.com.cn/gkxx/ksbd/202604/20260428/2293468839.html', '2026年5月高考热点-招生章程规划志愿', '政策指导'),
]

success = 0
total_chars = 0

for url, title, category in urls:
    fname = re.sub(r'[<>:\"/\\|?*]', '_', title)[:80]

    if fname in in_db:
        print(f'SKIP (already in DB): {title[:50]}')
        continue

    print(f'Fetching: {title[:50]}...', flush=True)

    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')

        # Extract main content - look for the largest text block
        body = soup.find('body')
        if not body:
            print(f'  No body found')
            continue

        # Remove nav, footer, scripts
        for tag in body.find_all(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()

        text = body.get_text(separator='\n', strip=True)

        # Clean up
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {3,}', '  ', text)

        # Find the actual content portion (skip nav menus)
        # Content usually starts after common menu items
        content_start = 0
        for keyword in ['招生章程', '招生工作规定', '招生工作实施', '第一章', '第一条', '各高校']:
            idx = text.find(keyword)
            if 100 < idx < 3000:  # within first 3000 chars
                content_start = idx
                break

        content = text[content_start:].strip()

        if len(content) < 100:
            print(f'  Too short: {len(content)} chars')
            continue

        # Save
        out_path = OUT / (fname + '.txt')
        out_path.write_text(content, encoding='utf-8')

        conn.execute(
            'INSERT OR IGNORE INTO raw_data(source_file,source_dir,format,content,word_count,metadata) VALUES(?,?,?,?,?,?)',
            (fname, '2026_招生政策', '.html', content, len(content), f'category:{category},url:{url}')
        )
        conn.commit()

        success += 1
        total_chars += len(content)
        print(f'  OK: {len(content)} chars [{category}]', flush=True)

        time.sleep(1)  # Be polite

    except Exception as e:
        print(f'  FAIL: {e}', flush=True)

conn.close()
print(f'\nDone! Scraped {success}/{len(urls)} articles, {total_chars} chars total.')
