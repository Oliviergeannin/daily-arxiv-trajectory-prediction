/**
 * @file app.js
 * @description 前端逻辑：加载 data.json，渲染卡片、搜索、日期筛选、详情弹窗。
 */
(function(){
  /** @type {Array<{date:string,title:string,link:string,summary_markdown:string,summary_html:string}>} */
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
   * @param {Array} items
   * @param {string} q
   * @param {string|null} date
   */
  function filterItems(items, q){
    const kw = (q||'').trim().toLowerCase();
    return items.filter(it => {
      if(!kw) return true;
      const hay = (it.title + ' ' + it.summary_markdown).toLowerCase();
      return hay.includes(kw);
    });
  }

  /**
   * @param {Array} items  已过滤后的项目
   */
  function renderGroups(items){
    // 分组：按日期降序
    const map = new Map();
    items.forEach(it=>{ if(!map.has(it.date)) map.set(it.date, []); map.get(it.date).push(it); });
    const dates = Array.from(map.keys()).sort((a,b)=> b.localeCompare(a));

    groupsEl.innerHTML = '';
    dates.forEach(d => {
      const group = document.createElement('section');
      group.className = 'group';
      const h = document.createElement('h2');
      h.textContent = d;
      const grid = document.createElement('div');
      grid.className = 'grid';
      map.get(d).forEach(it => {
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
      });
      group.appendChild(h);
      group.appendChild(grid);
      groupsEl.appendChild(group);
    });
  }

  /**
   * @param {title:string,date:string,summary_html:string,link:string} it
   */
  function openModal(it){
    modalTitle.textContent = it.title;
    modalMeta.innerHTML = `${it.date} · <a href="${it.link}" target="_blank" rel="noopener noreferrer">原文链接</a>`;
    modalBody.innerHTML = it.summary_html; // 已在后端修复换行并渲染
    modal.classList.remove('hidden');
  }

  function closeModal(){ modal.classList.add('hidden'); }

  function sync(){
    const items = filterItems(DATA, searchEl.value);
    renderGroups(items);
  }

  modalClose.addEventListener('click', closeModal);
  modal.addEventListener('click', (e)=>{ if(e.target.classList.contains('modal-backdrop')) closeModal(); });
  searchEl.addEventListener('input', sync);

  fetch('/daily-arxiv-vla/assets/data.json').then(r=>r.json()).then(arr=>{ DATA = arr; sync(); });
})();