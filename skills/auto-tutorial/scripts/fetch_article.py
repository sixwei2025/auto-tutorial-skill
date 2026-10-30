#!/usr/bin/env python3
"""Step A｜抓文章正文 + 下载配图 —— 链接 → article.json

用法：
  TV_PROJECT=/path python3 fetch_article.py <url> [--no-images]

产出：
  article.json      {url,title,account,author,digest,blocks[],images[]}
  assets/raw/*.png  原始配图（按正文出现顺序编号）

跨平台：纯标准库，无第三方依赖；公众号配图带 Referer 绕过防盗链。
"""
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT

RAW = os.path.join(PROJECT, "assets", "raw")
os.makedirs(RAW, exist_ok=True)

UA_MAC = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
UA_WX = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.49")

JUNK = ("点击上方", "点击下方", "关注公众号", "关注我们", "长按识别", "扫码", "阅读原文",
        "分享", "点赞", "在看", "设为星标", "星标", "转载", "投稿", "广告",
        "预览时标签不可点", "微信扫一扫", "识别二维码", "以下文章", "向上滑动",
        "滑动查看", "视频加载失败", "点击蓝字", "点个", "收藏", "转发")


class Extractor(HTMLParser):
    """按文档顺序抽取标题/段落/图片/视频块。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.capture = False
        self.depth = 0
        self.cur = None
        self.cur_tag = None
        self.title = ""
        self.meta = {}
        self.seen = set()

    # ---------------- 开始标签 ----------------
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)

        if tag == "meta":
            k = (a.get("property") or a.get("name") or "").lower()
            v = (a.get("content") or "").strip()
            if not v:
                return
            if k in ("og:title", "twitter:title"):
                self.title = self.title or v
            elif k in ("og:description", "description"):
                self.meta.setdefault("digest", v)
            elif k in ("author", "og:article:author", "og:article:author_name"):
                self.meta.setdefault("author", v)
            elif k in ("og:site_name", "twitter:site"):
                self.meta.setdefault("account", v)
            return

        if tag == "h1" and not self.title:
            self.title = ""
            self.cur, self.cur_tag = [], "h1"
            return

        if not self.capture:
            if a.get("id") in ("js_content", "article-content", "js_article"):
                self.capture, self.depth = True, 0
            return

        if tag in ("div", "section", "article", "main"):
            self.depth += 1

        if tag in ("h1", "h2", "h3", "h4"):
            self._flush(); self.cur, self.cur_tag = [], tag
        elif tag in ("p", "li", "td", "figcaption"):
            self._flush(); self.cur, self.cur_tag = [], "p"
        elif tag == "blockquote":
            self._flush(); self.cur, self.cur_tag = [], "quote"
        elif tag == "br":
            if self.cur is not None:
                self.cur.append(" ")
        elif tag == "img":
            src = (a.get("data-src") or a.get("data-original") or a.get("src") or "").strip()
            if src and not src.startswith("data:") and src not in self.seen:
                self.seen.add(src)
                self._flush()
                self.blocks.append({"type": "img", "src": src})
        elif tag in ("video", "iframe"):
            src = a.get("data-src") or a.get("src") or ""
            if tag == "video" or "videoplayer" in src or "v.qq.com" in src or "mpvideo" in src:
                self._flush()
                self.blocks.append({"type": "video",
                                    "note": "正文内嵌视频（需人工录屏或截图替代）"})

    # ---------------- 结束标签 ----------------
    def handle_endtag(self, tag):
        if self.capture and tag in ("div", "section", "article", "main"):
            self.depth -= 1
            if self.depth <= -1:
                self.capture, self.depth = False, 0
        if tag in ("h1", "h2", "h3", "h4", "p", "li", "td", "blockquote", "figcaption"):
            self._flush()

    def handle_data(self, data):
        if self.cur is None:
            return
        self.cur.append(data)

    def _flush(self):
        if self.cur is None or self.cur_tag is None:
            self.cur, self.cur_tag = None, None
            return
        txt = re.sub(r"[ \t\r\n\u200b\u200c\u200d\ufeff\u00a0]+", " ", "".join(self.cur)).strip()
        self.cur, self.cur_tag = None, None
        if len(txt) < 2 or any(j in txt for j in JUNK):
            return
        kind = "h" if (self.cur_tag or "").startswith("h") else (self.cur_tag or "p")
        self.blocks.append({"type": kind, "text": txt})


def fetch(url, ua, referer=None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "zh-CN,zh"})
    if referer:
        req.add_header("Referer", referer)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def classify(w, h):
    if not h:
        return "unknown"
    r = w / h
    if r >= 1.45:
        return "wide"
    if r <= 0.72:
        return "tall"
    return "square"


def image_size(path):
    """读图片尺寸，不依赖 Pillow 也能退化处理。"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return (0, 0)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit("用法：python3 fetch_article.py <文章链接> [--no-images]")
    url = args[0]
    want_images = "--no-images" not in sys.argv
    is_wx = "mp.weixin.qq.com" in url

    print("▶ 抓取 %s" % url)
    html = fetch(url, UA_WX if is_wx else UA_MAC).decode("utf-8", errors="ignore")
    print("  HTML %.0f KB" % (len(html) / 1024))

    p = Extractor()
    p.feed(html)

    title = (p.title or p.meta.get("digest", "")[:30] or "未命名").strip()
    title = re.sub(r"\s+", " ", title)

    blocks = p.blocks
    imgs = [b for b in blocks if b["type"] == "img"]
    texts = [b for b in blocks if b["type"] != "img"]
    videos = [b for b in blocks if b["type"] == "video"]

    print("  正文 %d 块 / 图片 %d 张 / 视频 %d 处" % (len(texts), len(imgs), len(videos)))
    if not texts:
        raise SystemExit("没抓到正文。可能是付费墙、需要登录，或页面结构变了；"
                         "可手动复制正文到 article.json 再继续。")

    images = []
    if want_images:
        print("▶ 下载配图（Referer 绕防盗链）")
        for i, b in enumerate(imgs, 1):
            ext = "gif" if ".gif" in b["src"].lower() else "png"
            dst = os.path.join(RAW, "%02d.%s" % (i, ext))
            try:
                data = fetch(b["src"], UA_MAC, referer="https://mp.weixin.qq.com/")
                if data[:1] == b"<":          # 返回 HTML = 视频占位/失效
                    print("  %02d ✗ 非图片（可能是视频占位）" % i)
                    continue
                open(dst, "wb").write(data)
                w, h = image_size(dst)
                images.append({"n": i, "file": "assets/raw/%02d.%s" % (i, ext),
                               "src": b["src"], "width": w, "height": h,
                               "kind": classify(w, h)})
                print("  %02d ✓ %dx%d %s" % (i, w, h, classify(w, h)))
            except Exception as e:
                print("  %02d ✗ %s" % (i, str(e)[:60]))

    article = {
        "url": url,
        "title": title,
        "account": p.meta.get("account", ""),
        "author": p.meta.get("author", ""),
        "digest": p.meta.get("digest", ""),
        "blocks": [b for b in blocks if b["type"] != "video"],
        "videos": videos,
        "images": images,
    }
    out = os.path.join(PROJECT, "article.json")
    json.dump(article, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n✅ %s" % out)
    print("   标题：%s" % title)
    print("   可用图 %d 张（wide %d / tall %d / square %d）"
          % (len(images),
             sum(1 for x in images if x["kind"] == "wide"),
             sum(1 for x in images if x["kind"] == "tall"),
             sum(1 for x in images if x["kind"] == "square")))
    if videos:
        print("   ⚠ 有 %d 处内嵌视频，脚本下不了，需人工截图或录屏补" % len(videos))


if __name__ == "__main__":
    main()
