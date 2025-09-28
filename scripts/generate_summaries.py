import os
import re
from typing import List, Tuple

import requests
from dotenv import load_dotenv
from openai import OpenAI


"""
/**
 * @file generate_summaries.py
 * @description 读取项目根目录 `papers.md`，为“简要总结”列仍为“待生成”的条目生成摘要，
 * 使用在 `test_api.py` 中相同的推理接口（ModelScope OpenAI 兼容 API），并将结果回写到 `papers.md`。
 */
"""


def get_client() -> OpenAI:
    """
    /**
     * @function get_client
     * @description 构造 OpenAI 客户端（ModelScope），从环境变量读取 `MODELSCOPE_ACCESS_TOKEN`。
     * @returns {OpenAI} 已初始化的客户端
     */
    """
    load_dotenv()
    api_key = os.getenv("MODELSCOPE_ACCESS_TOKEN")
    if not api_key:
        raise RuntimeError("缺少环境变量 MODELSCOPE_ACCESS_TOKEN")
    return OpenAI(api_key=api_key, base_url="https://api-inference.modelscope.cn/v1/")


def get_papers_md_path() -> str:
    """
    /**
     * @function get_papers_md_path
     * @description 获取项目根目录下的 `papers.md` 绝对路径。
     */
    """
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(scripts_dir)
    return os.path.join(root_dir, "papers.md")


def is_placeholder_summary(cell: str) -> bool:
    """
    /**
     * @function is_placeholder_summary
     * @description 判断“简要总结”单元格是否为默认占位（待生成）。
     */
    """
    return "待生成" in cell


def parse_table_line(line: str) -> List[str]:
    """
    /**
     * @function parse_table_line
     * @description 解析 markdown 表格行，返回去除空项后的单元格列表。
     * @param {str} line - 形如 `| a | b | c | d |\n`
     * @returns {List[str]} 单元格列表
     */
    """
    parts = [p.strip() for p in line.strip().split("|")]
    # 去除首尾空项（因为行首尾都有 `|`）
    cells = [p for p in parts if p and p != "---"]
    return cells


def rebuild_line(date_str: str, title: str, link: str, summary_html: str) -> str:
    """
    /**
     * @function rebuild_line
     * @description 将四列内容重建为表格行。
     */
    """
    safe_title = title.replace("|", "\\|")
    safe_summary = summary_html.replace("|", "\\|")
    return f"| {date_str} | {safe_title} | {link} | {safe_summary} |\n"


def generate_summary_for_link(client: OpenAI, link: str, model: str = "deepseek-ai/DeepSeek-R1-0528") -> str:
    """
    /**
     * @function generate_summary_for_link
     * @description 抓取 arXiv HTML 原文并让模型基于 HTML 生成简要总结。
     * @param {OpenAI} client - OpenAI 客户端
     * @param {str} link - arXiv 链接
     * @param {str} model - ModelScope 模型 ID
     * @returns {str} 简要总结文本
     */
    """
    # 将 /abs/ 链接转换为 /html/ 页面
    html_url = re.sub(r"/abs/", "/html/", link)

    # 抓取 HTML 文本
    resp = requests.get(html_url, timeout=30)
    resp.raise_for_status()
    html_content = resp.text

    # 按需截断，避免上下文过长
    max_chars = 180000
    if len(html_content) > max_chars:
        html_content = html_content[:max_chars]

    # 与 test_api.py 保持一致的提示风格（基于 HTML）
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                'role': 'system',
                'content': '你是一名论文阅读专家。根据提供的Arxiv论文HTML原文，用中文简明扼要总结论文的要点，不需要输出其他内容。'
            },
            {
                'role': 'user',
                'content': f"以下为论文的HTML原文（可能已截断）：\n\n{html_content}"
            },
        ],
        stream=True,
    )

    chunks: List[str] = []
    for chunk in response:
        delta = getattr(chunk.choices[0], "delta", None)
        if not delta:
            continue
        piece = getattr(delta, "content", None)
        if piece:
            chunks.append(piece)

    text = "".join(chunks).strip()
    # 精简多余空白
    text = re.sub(r"\s+", " ", text)
    return text


def default_summary_cell() -> str:
    """
    /**
     * @function default_summary_cell
     * @description 默认折叠占位单元格 HTML。
     */
    """
    return "<details><summary>展开</summary>待生成</details>"


def wrap_in_details(summary_text: str) -> str:
    """
    /**
     * @function wrap_in_details
     * @description 将纯文本包装为折叠 HTML。
     */
    """
    return f"<details><summary>展开</summary>{summary_text}</details>"


def update_papers_md() -> Tuple[int, int]:
    """
    /**
     * @function update_papers_md
     * @description 读取 `papers.md`，为缺失摘要的条目生成并写回。
     * @returns {Tuple[int,int]} (总需更新数, 实际更新成功数)
     */
    """
    papers_md = get_papers_md_path()
    if not os.path.exists(papers_md):
        raise FileNotFoundError(f"未找到 {papers_md}，请先运行爬取初始化")

    with open(papers_md, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if len(lines) < 2:
        return 0, 0

    header = lines[:2]
    body = lines[2:]

    client = get_client()

    need_count = 0
    success_count = 0

    for idx, line in enumerate(body):
        if not line.strip().startswith("|"):
            continue
        cells = parse_table_line(line)
        if len(cells) != 4:
            continue
        date_str, title, link, summary_cell = cells
        if not is_placeholder_summary(summary_cell):
            continue

        need_count += 1
        try:
            summary_text = generate_summary_for_link(client, link)
            if not summary_text:
                # 无内容则跳过，不覆盖占位
                continue
            new_summary_cell = wrap_in_details(summary_text)
            new_line = rebuild_line(date_str, title, link, new_summary_cell)
            # 立即写回：更新内存中的行并写入文件
            body[idx] = new_line
            with open(papers_md, "w", encoding="utf-8") as f:
                f.writelines(header + body)
            success_count += 1
        except Exception as e:
            # 单条失败跳过，不中断整体
            print(f"生成摘要失败: {link}: {e}")

    return need_count, success_count


if __name__ == "__main__":
    total, updated = update_papers_md()
    print(f"需要生成摘要的条目: {total}，已更新: {updated}")


