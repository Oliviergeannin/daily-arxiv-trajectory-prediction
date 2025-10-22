import os
import re
from datetime import datetime
from typing import List, Set

import arxiv


class ArxivTPCollector:
	"""
	/**
	 * @class ArxivTPCollector
	 * @description 每日自动获取 arXiv 上包含 "TP" 关键词的论文，并维护项目根目录下的
	 * `papers.md` 表格（列：日期、标题、链接）。首次运行无数据时执行初始化，之后每日增量并去重。
	 */
	"""

	# 允许的主类目（与现有脚本一致）
	_ALLOWED_PRIMARY_CATEGORIES = {
		"cs.CV",
		"cs.AI",
		"cs.CL",
		"cs.LG",
		"cs.MM",
		"cs.RO",
	}

	def __init__(self, papers_path: str, init_results: int = 500, daily_results: int = 20):
		"""
		/**
		 * @constructor
		 * @param {str} papers_path - `papers.md` 绝对路径
		 * @param {int} init_results - 初始化抓取的最大论文数
		 * @param {int} daily_results - 每日增量抓取的最大论文数
		 */
		"""
		self.papers_path = papers_path
		self.init_results = init_results
		self.daily_results = daily_results
		self._client = arxiv.Client()

	def _search(self, max_results: int) -> List[arxiv.Result]:
		"""
		/**
		 * @private
		 * @param {int} max_results - 最大返回数量
		 * @returns {List[Result]} arxiv 结果列表（按提交时间降序）
		 */
		"""
		search = arxiv.Search(
			query="trajectory prediction",
			# trajectory prediction OR motion forecasting OR path prediction
			max_results=max_results,
			sort_by=arxiv.SortCriterion.SubmittedDate,
			sort_order=arxiv.SortOrder.Descending,
		)
		# return list(self._client.results(search))

		try:
			results = list(self._client.results(search))
			return results
		except arxiv.UnexpectedEmptyPageError as e:
			print(f"[警告] Arxiv 返回空页面，已停止抓取：{e}")
			return []
		except Exception as e:
			print(f"[错误] 抓取失败：{e}")
			return []

	def _filter_categories(self, results: List[arxiv.Result]) -> List[arxiv.Result]:
		"""
		/**
		 * @private 过滤到指定主类目
		 * @param {List[Result]} results - 原始结果
		 * @returns {List[Result]} 过滤后的结果
		 */
		"""
		filtered: List[arxiv.Result] = []
		for r in results:
			if r.primary_category in self._ALLOWED_PRIMARY_CATEGORIES:
				filtered.append(r)
		return filtered

	def _default_summary_cell(self) -> str:
		"""
		/**
		 * @private 返回简要总结列的默认折叠占位。
		 */
		"""
		return "<details><summary>展开</summary>待生成</details>"

	def _ensure_md_header(self) -> None:
		"""
		/**
		 * 确保 `papers.md` 存在且包含四列表头。
		 */
		"""
		four_header = "| 日期 | 标题 | 链接 | 简要总结 |\n"
		four_sep = "| --- | --- | --- | --- |\n"
		if not os.path.exists(self.papers_path):
			with open(self.papers_path, "w", encoding="utf-8") as f:
				f.write(four_header)
				f.write(four_sep)

	def _load_existing_links(self) -> Set[str]:
		"""
		/**
		 * 解析 `papers.md` 已有的 arXiv 链接集合，用于去重。
		 * @returns {Set[str]} 已存在的链接集合
		 */
		"""
		if not os.path.exists(self.papers_path):
			return set()
		links: Set[str] = set()
		link_pattern = re.compile(r"https?://arxiv\.org/abs/[\w\-\.\/]+", re.IGNORECASE)
		with open(self.papers_path, "r", encoding="utf-8") as f:
			for line in f:
				for m in link_pattern.findall(line):
					links.add(m)
		return links

	def _format_row(self, r: arxiv.Result) -> str:
		"""
		/**
		 * 将单条结果格式化为 Markdown 表格行（四列）。
		 * @param {Result} r - 论文结果
		 * @returns {str} 形如 `| 2025-09-26 | 标题 | https://arxiv.org/abs/xxxx | <details>..</details> |`
		 */
		"""
		date_str = r.published.strftime("%Y-%m-%d") if isinstance(r.published, datetime) else ""
		title = (r.title or "").replace("|", "\\|").strip()
		link = r.entry_id
		summary_cell = self._default_summary_cell()
		return f"| {date_str} | {title} | {link} | {summary_cell} |\n"

	def _append_rows(self, rows: List[str]) -> None:
		"""
		/**
		 * 将若干行插入到表头之后（保持最新内容靠前）。
		 * @param {List[str]} rows - 需要追加的行（已按时间降序）
		 */
		"""
		self._ensure_md_header()
		with open(self.papers_path, "r", encoding="utf-8") as f:
			lines = f.readlines()
		# 寻找表头分隔线所在索引（第二行）
		insert_idx = 2 if len(lines) >= 2 else len(lines)
		new_lines = lines[:insert_idx] + rows + lines[insert_idx:]
		with open(self.papers_path, "w", encoding="utf-8") as f:
			f.writelines(new_lines)

	def initialize(self) -> int:
		"""
		/**
		 * 初始化 `papers.md`：抓取较多历史论文并写入（去重）。
		 * @returns {int} 写入的论文数量
		 */
		"""
		self._ensure_md_header()
		existing = self._load_existing_links()
		results = self._filter_categories(self._search(self.init_results))
		rows: List[str] = []
		for r in results:
			if r.entry_id in existing:
				continue
			rows.append(self._format_row(r))
		if rows:
			self._append_rows(rows)
		return len(rows)

	def run_daily(self) -> int:
		"""
		/**
		 * 每日增量：抓取少量最新论文，与已存在内容去重后插入表头之后。
		 * @returns {int} 新增的论文数量
		 */
		"""
		self._ensure_md_header()
		existing = self._load_existing_links()
		results = self._filter_categories(self._search(self.daily_results))
		rows: List[str] = []
		for r in results:
			if r.entry_id in existing:
				continue
			rows.append(self._format_row(r))
		if rows:
			self._append_rows(rows)
		return len(rows)


def _default_papers_path() -> str:
	"""
	/**
	 * 计算项目根目录下的 `papers.md` 绝对路径。
	 * 假设当前文件位于 `<root>/scripts/`。
	 */
	"""
	scripts_dir = os.path.dirname(os.path.abspath(__file__))
	root_dir = os.path.dirname(scripts_dir)
	return os.path.join(root_dir, "papers.md")


if __name__ == "__main__":
	import sys
	
	papers_md = _default_papers_path()
	collector = ArxivTPCollector(papers_md)
	
	# 检查是否已有 papers.md 文件，决定运行模式
	if os.path.exists(papers_md) and os.path.getsize(papers_md) > 0:
		# 文件存在且不为空，执行每日增量更新
		count = collector.run_daily()
		print(f"每日更新完成，新增 {count} 篇论文，写入 {papers_md}")
	else:
		# 文件不存在或为空，执行初始化
		count = collector.initialize()
		print(f"初始化完成，新增 {count} 篇论文，写入 {papers_md}")