#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
生成静态站点：
1) 解析项目根目录下的 `papers.md` 表格（列：日期/标题/链接/简要总结）。
2) 从第四列提取 <details> ... </details> 中的实际内容。
3) 对内容进行“自动补换行”修复（因原始换行丢失）。
4) 将修复后的 Markdown 渲染为 HTML（无第三方依赖，内置简易渲染器）。
5) 输出站点到 `site/`：index.html、assets/style.css、assets/app.js、assets/data.json。
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_MD = PROJECT_ROOT / "papers.md"
SITE_DIR = PROJECT_ROOT / "site"
ASSETS_DIR = SITE_DIR / "assets"

# GitHub Pages 子路径配置
BASE_PATH = "/daily-arxiv-trajectory-prediction"  # 仓库名对应的路径


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(content)


def parse_markdown_table(md_text: str) -> List[Dict[str, str]]:
    """
    解析 markdown 表格为记录列表。
    预期表头：| 日期 | 标题 | 链接 | 简要总结 |
    """
    lines = [line for line in md_text.splitlines() if line.strip()]
    if len(lines) < 3:
        return []

    records: List[Dict[str, str]] = []
    # 跳过表头两行
    for line in lines[2:]:
        if not line.strip().startswith("|"):
            continue
        # 朴素分割，并去除首尾竖线
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 4:
            continue
        date_str, title, link, summary_cell = parts[0], parts[1], parts[2], "|".join(parts[3:]).strip()

        # 提取 <details> 内容
        details_content = extract_details(summary_cell)
        records.append({
            "date": date_str,
            "title": title,
            "link": link,
            "details_raw": details_content,
        })
    return records


def extract_details(cell_html: str) -> str:
    """
    从单元格中提取 <details> 内容，去除 <summary>...
    """
    # 去壳
    m = re.search(r"<details>([\s\S]*?)</details>", cell_html, re.IGNORECASE)
    content = m.group(1) if m else cell_html
    # 去掉 <summary>...</summary>
    content = re.sub(r"<summary>[\s\S]*?</summary>", "", content, flags=re.IGNORECASE)
    # 去掉包裹空白
    return content.strip()


def auto_add_linebreaks(text: str) -> str:
    """
    自动添加换行符的启发式规则：
    - 标题前换行：在 "###" 等子标题前插入换行
    - 项目符号：将内嵌的 " - "/" – " 转为行首列表项
    - 有序列表："1. ", "2. " 等编号若非行首，则前置换行
    - 水平分割线：在 --- 周围添加换行
    - 粗体小节：将 " - **小节**" 等模式置于新行
    """
    t = text

    # 标题前强制换行
    t = re.sub(r"\s*(#+\s*)", lambda m: "\n" + m.group(1), t)

    # 水平线周围换行
    t = re.sub(r"\s*---\s*", "\n---\n", t)

    # 列表项前换行（无序）
    t = re.sub(r"\s+[-–]\s+", "\n- ", t)

    # 有序列表：将内联的 " 1. " 变为换行起始
    t = re.sub(r"(?<!\n)(\s*)(\d+\.\s+)", lambda m: "\n" + m.group(2), t)

    # 粗体小节项：" - **...**" → 换行
    t = re.sub(r"\s+-\s+\*\*(.+?)\*\*", lambda m: "\n- **" + m.group(1) + "**", t)

    # 在中文句号+标题锚点之间分段（谨慎）
    t = re.sub(r"([。！？；])\s*(###)\s*", r"\1\n\2 ", t)

    # 合并多余空行为最多两个
    t = re.sub(r"\n{3,}", "\n\n", t)

    return t.strip()


def markdown_to_html(md: str) -> str:
    """
    极简 Markdown 渲染器（覆盖本项目所需）：
    - ###, #### -> h3/h4
    - 无序列表/有序列表
    - 行内加粗 **text**、行内代码 `code`
    - 链接 [text](url)
    - 段落/换行
    """
    lines = md.splitlines()
    html_lines: List[str] = []

    def render_inline(s: str) -> str:
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<a href=\"\2\" target=\"_blank\" rel=\"noopener noreferrer\">\1</a>", s)
        return s

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        if not line:
            html_lines.append("")
            i += 1
            continue

        # 标题
        if line.startswith("### "):
            html_lines.append(f"<h3>{render_inline(line[4:].strip())}</h3>")
            i += 1
            continue
        if line.startswith("#### "):
            html_lines.append(f"<h4>{render_inline(line[5:].strip())}</h4>")
            i += 1
            continue
        if line.strip() == "---":
            html_lines.append("<hr/>")
            i += 1
            continue

        # 列表（无序）
        if re.match(r"^- ", line):
            ul_items: List[str] = []
            while i < len(lines) and re.match(r"^- ", lines[i]):
                ul_items.append(f"<li>{render_inline(lines[i][2:].strip())}</li>")
                i += 1
            html_lines.append("<ul>" + "".join(ul_items) + "</ul>")
            continue

        # 列表（有序）
        if re.match(r"^\d+\. ", line):
            ol_items: List[str] = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                item_txt = re.sub(r"^\d+\. ", "", lines[i]).strip()
                ol_items.append(f"<li>{render_inline(item_txt)}</li>")
                i += 1
            html_lines.append("<ol>" + "".join(ol_items) + "</ol>")
            continue

        # 普通段落
        html_lines.append(f"<p>{render_inline(line)}</p>")
        i += 1

    # 合并相邻空行
    out: List[str] = []
    prev_blank = False
    for h in html_lines:
        is_blank = (h == "")
        if is_blank and prev_blank:
            continue
        out.append(h)
        prev_blank = is_blank
    return "\n".join(out).strip()


def build_data(records: List[Dict[str, str]]) -> List[Dict[str, str]]:
    data: List[Dict[str, str]] = []
    for rec in records:
        raw = rec["details_raw"]
        fixed = auto_add_linebreaks(raw)
        html = markdown_to_html(fixed)
        data.append({
            "date": rec["date"],
            "title": rec["title"],
            "link": rec["link"],
            "summary_markdown": fixed,
            "summary_html": html,
        })
    return data


def generate_index_html() -> str:
    return f"""<!doctype html>
<html lang=\"zh-CN\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>ArXiv Papers</title>
    <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />
    <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin />
    <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap\" rel=\"stylesheet\" />
    <link rel=\"stylesheet\" href=\"{BASE_PATH}/assets/style.css\" />
  </head>
  <body>
    <header class=\"container\">
      <h1>ArXiv 精选</h1>
      <div class=\"controls\"> 
        <input id=\"search\" type=\"search\" placeholder=\"搜索标题或内容…\" aria-label=\"搜索\" />
      </div>
    </header>

    <main class=\"container\">
      <section id=\"groups\"></section>
    </main>

    <div id=\"modal\" class=\"modal hidden\" role=\"dialog\" aria-modal=\"true\" aria-labelledby=\"modal-title\"> 
      <div class=\"modal-backdrop\"></div>
      <div class=\"modal-content\">
        <button id=\"modal-close\" class=\"icon-btn\" aria-label=\"关闭\">✕</button>
        <h2 id=\"modal-title\"></h2>
        <div id=\"modal-meta\" class=\"muted\"></div>
        <article id=\"modal-body\"></article>
      </div>
    </div>

    <script src=\"{BASE_PATH}/assets/app.js\"></script>
  </body>
</html>
""".strip()


def generate_style_css() -> str:
    return """
:root{ --bg:#0b0d12; --card:#131722; --text:#e6e8ee; --muted:#9aa3b2; --brand:#5b8cff; --chip:#1b2130; --chip-active:#2b3650; }
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.container{max-width:1100px;margin:0 auto;padding:24px}
h1{margin:8px 0 16px;font-size:28px}
.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
input[type=search]{flex:1;min-width:260px;padding:12px 14px;border-radius:10px;border:1px solid #223;outline:none;background:#0e1320;color:var(--text)}
.group{margin:18px 0 8px}
.group h2{margin:14px 0 8px;font-size:18px;color:#dfe5f2}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;margin-top:16px}
.card{background:var(--card);border:1px solid #1b2233;border-radius:14px;padding:16px;display:flex;flex-direction:column;gap:12px;box-shadow:0 4px 16px rgba(0,0,0,.24)}
.title{font-weight:700;line-height:1.3;color:#f3f5f8}
.btn-row{display:flex;gap:8px;margin-top:auto}
.btn{appearance:none;border:1px solid #2b3a66;background:#111933;color:var(--text);padding:8px 10px;border-radius:10px;cursor:pointer;transition:.2s}
.btn:hover{border-color:#3b5bdd;background:#0f1630}
.btn.primary{background:linear-gradient(135deg,#4e6cff,#6aa0ff);border-color:#4e6cff;color:white}
.btn.primary:hover{filter:brightness(1.05)}
.icon-btn{appearance:none;background:transparent;border:none;color:var(--muted);cursor:pointer;font-size:18px}
.icon-btn:hover{color:#fff}
.modal{position:fixed;inset:0;display:none}
.modal:not(.hidden){display:block}
.modal-backdrop{position:absolute;inset:0;background:rgba(0,0,0,.5);backdrop-filter:blur(2px)}
.modal-content{position:relative;max-width:860px;margin:6vh auto;background:#0f1422;border:1px solid #1c2540;border-radius:14px;padding:20px}
#modal-close{position:absolute;top:10px;right:10px}
.muted{color:var(--muted);font-size:13px;margin-bottom:8px}
article h3{margin:16px 0 8px}
article h4{margin:14px 0 6px}
article p{margin:8px 0;line-height:1.7}
article ul,article ol{margin:8px 0 8px 22px}
article code{background:#0b1120;border:1px solid #1b2440;padding:2px 5px;border-radius:6px}
article a{color:#80aaff}
hr{border:none;border-top:1px solid #223}
""".strip()


def generate_app_js() -> str:
    return f"""
/**
 * @file app.js
 * @description 前端逻辑：加载 data.json，渲染卡片、搜索、日期筛选、详情弹窗。
 */
(function(){{
  /** @type {{Array<{{date:string,title:string,link:string,summary_markdown:string,summary_html:string}}>}} */
  let DATA = [];

  const $ = (sel) => document.querySelector(sel);
  const groupsEl = $('#groups');
  const searchEl = $('#search');
  const modal = $('#modal');
  const modalTitle = $('#modal-title');
  const modalMeta = $('#modal-meta');
  const modalBody = $('#modal-body');
  const modalClose = $('#modal-close');

  /**
   * @param {{Array}} items
   * @param {{string}} q
   * @param {{string|null}} date
   */
  function filterItems(items, q){{
    const kw = (q||'').trim().toLowerCase();
    return items.filter(it => {{
      if(!kw) return true;
      const hay = (it.title + ' ' + it.summary_markdown).toLowerCase();
      return hay.includes(kw);
    }});
  }}

  /**
   * @param {{Array}} items  已过滤后的项目
   */
  function renderGroups(items){{
    // 分组：按日期降序
    const map = new Map();
    items.forEach(it=>{{ if(!map.has(it.date)) map.set(it.date, []); map.get(it.date).push(it); }});
    const dates = Array.from(map.keys()).sort((a,b)=> b.localeCompare(a));

    groupsEl.innerHTML = '';
    dates.forEach(d => {{
      const group = document.createElement('section');
      group.className = 'group';
      const h = document.createElement('h2');
      h.textContent = d;
      const grid = document.createElement('div');
      grid.className = 'grid';
      map.get(d).forEach(it => {{
        const card = document.createElement('div');
        card.className = 'card';
        const title = document.createElement('div');
        title.className = 'title';
        title.textContent = it.title;
        const btnRow = document.createElement('div');
        btnRow.className = 'btn-row';
        const viewBtn = document.createElement('a');
        viewBtn.className = 'btn';
        viewBtn.href = it.link; viewBtn.target = '_blank'; viewBtn.rel = 'noopener noreferrer';
        viewBtn.textContent = '查看原文';
        const detailBtn = document.createElement('button');
        detailBtn.className = 'btn primary';
        detailBtn.textContent = '详情';
        detailBtn.onclick = ()=> openModal(it);
        btnRow.appendChild(viewBtn);
        btnRow.appendChild(detailBtn);
        card.appendChild(title);
        card.appendChild(btnRow);
        grid.appendChild(card);
      }});
      group.appendChild(h);
      group.appendChild(grid);
      groupsEl.appendChild(group);
    }});
  }}

  /**
   * @param {{title:string,date:string,summary_html:string,link:string}} it
   */
  function openModal(it){{
    modalTitle.textContent = it.title;
    modalMeta.innerHTML = `${{it.date}} · <a href="${{it.link}}" target="_blank" rel="noopener noreferrer">原文链接</a>`;
    modalBody.innerHTML = it.summary_html; // 已在后端修复换行并渲染
    modal.classList.remove('hidden');
  }}

  function closeModal(){{ modal.classList.add('hidden'); }}

  function sync(){{
    const items = filterItems(DATA, searchEl.value);
    renderGroups(items);
  }}

  modalClose.addEventListener('click', closeModal);
  modal.addEventListener('click', (e)=>{{ if(e.target.classList.contains('modal-backdrop')) closeModal(); }});
  searchEl.addEventListener('input', sync);

  fetch('{BASE_PATH}/assets/data.json').then(r=>r.json()).then(arr=>{{ DATA = arr; sync(); }});
}})();
""".strip()


def main() -> int:
    if not INPUT_MD.exists():
        print(f"未找到 {INPUT_MD}", file=sys.stderr)
        return 1

    md_text = read_text(INPUT_MD)
    records = parse_markdown_table(md_text)
    data = build_data(records)

    # 输出静态资源
    write_text(SITE_DIR / "index.html", generate_index_html())
    write_text(ASSETS_DIR / "style.css", generate_style_css())
    write_text(ASSETS_DIR / "app.js", generate_app_js())
    write_text(ASSETS_DIR / "data.json", json.dumps(data, ensure_ascii=False, indent=2))

    print(f"生成完成：{SITE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


