        // --- DATA & CONFIG ---
        const MOCK_SCENARIOS = {
            paper: { basePrice: 350, specs: [{name: "Белизна", target: "160%", options: ["160%"]}, {name: "Плотность", target: "80 г/м2", options: ["80 г/м2"]}], mfrs: ["SvetoCopy", "Xerox"] },
            pc: { basePrice: 55000, specs: [{name: "CPU", target: "Core i5", options: ["i5", "i3"]}, {name: "RAM", target: "16GB", options: ["16GB", "8GB"]}], mfrs: ["HP", "Lenovo"] },
            generic: { basePrice: 1500, specs: [{name: "Стандарт", target: "ГОСТ", options: ["ГОСТ", "ТУ"]}], mfrs: ["Завод №1", "ПромТех"] }
        };

        let MOCK_HISTORY = []; // Будет заполнено в init
        
        // --- History Pagination State ---
        let currentHistoryPage = 1;
        const historyRowsPerPage = 10;
        let activeHistoryFilters = { name: '', status: '', date: '' };

        // --- Results Pagination State ---
        let currentContracts = [];
        let filteredContracts = [];
        let selectedContractIds = new Set();
        let currentPage = 1;
        const rowsPerPage = 10;
        
        let searchIntervals = {}; 
        let activeSidebarSearchId = null;

        document.addEventListener('DOMContentLoaded', () => {
            initMockHistory(); // Generate dummy data to show pagination
            renderHistory();
            document.getElementById('results-footer').classList.add('translate-y-full'); 
        });

        // Generate some history data so pagination is visible
        function initMockHistory() {
            MOCK_HISTORY = [
                { id: 101, date: "2026-01-21", name: "Бумага офисная A4", ktru: "17.12.14.110", status: "Завершен", found: 45, avg: 420.50, type: "paper" },
                { id: 102, date: "2026-01-20", name: "АРМ (Компьютеры)", ktru: "26.20.15.000", status: "Завершен", found: 15, avg: 54400.00, type: "pc" }
            ];
            // Add filler data
            for(let i=0; i<25; i++) {
                const day = 1 + Math.floor(Math.random() * 20);
                MOCK_HISTORY.push({
                    id: 200 + i,
                    date: `2025-12-${day < 10 ? '0'+day : day}`,
                    name: i % 3 === 0 ? "Картридж лазерный" : (i % 2 === 0 ? "Стул офисный" : "Папка-регистратор"),
                    ktru: "00.00.00.000",
                    status: Math.random() > 0.8 ? "Остановлен" : "Завершен",
                    found: Math.floor(Math.random() * 50),
                    avg: Math.random() * 5000,
                    type: "generic"
                });
            }
            // Sort by date desc
            MOCK_HISTORY.sort((a,b) => b.id - a.id);
        }

        // --- SEARCH LOGIC ---
        function handleFile(input) {
            if(input.files[0]) {
                document.getElementById('file-label').innerHTML = `<span class="text-gray-800 font-bold">${input.files[0].name}</span>`;
                document.getElementById('file-items-wrapper').classList.remove('hidden');
                showToast('Файл обработан. Выберите позицию из списка.', 'success');
            }
        }

        function autoFillFromTz() {
            const val = document.getElementById('file-item-select').value;
            if(val === "paper") {
                document.getElementById('obj-name-input').value = "Бумага офисная A4";
                document.getElementById('ktru-input').value = "17.12.14.110";
            } else if(val === "pc") {
                document.getElementById('obj-name-input').value = "Моноблок офисный";
                document.getElementById('ktru-input').value = "26.20.15";
            } else {
                document.getElementById('obj-name-input').value = "";
                document.getElementById('ktru-input').value = "";
            }
        }

        function startSearch(e) {
            e.preventDefault();
            
            const nameInput = document.getElementById('obj-name-input').value;
            const fileSelect = document.getElementById('file-item-select');
            const limitVal = parseInt(document.getElementById('limit-input').value) || 30;
            const specsText = document.getElementById('specs-text').value;

            let searchName = nameInput;
            let type = "generic";
            if(fileSelect && fileSelect.value) {
                const opt = fileSelect.options[fileSelect.selectedIndex];
                if(fileSelect.value !== "") {
                    searchName = opt.text;
                    type = fileSelect.value;
                }
            }
            if(!searchName) searchName = "Объект закупки";
            if(type === "generic") type = detectType(searchName);

            document.getElementById('btn-search').classList.add('hidden');
            document.getElementById('progress-panel').classList.remove('hidden');
            showToast('Поиск запущен...', 'info');

            const tempId = Date.now();
            activeSidebarSearchId = tempId;

            const newHistoryItem = { 
                id: tempId, 
                date: new Date().toISOString().split('T')[0], 
                name: searchName,
                ktru: document.getElementById('ktru-input').value || "---",
                status: "В работе", 
                found: 0, 
                avg: 0,
                targetMfr: document.getElementById('mfr-input').value, 
                type: type,
                limit: limitVal, 
                specsText: specsText 
            };
            
            MOCK_HISTORY.unshift(newHistoryItem);
            currentHistoryPage = 1; // Reset to page 1 on new search
            renderHistory();

            let progress = 0;
            searchIntervals[tempId] = setInterval(() => {
                progress += Math.random() * 3; 
                const count = Math.min(limitVal, Math.floor((progress / 100) * limitVal));
                
                if(activeSidebarSearchId === tempId) {
                    document.getElementById('proc-bar').style.width = `${Math.min(100, progress)}%`;
                    document.getElementById('proc-count').innerText = `${count}/${limitVal}`;
                }

                if(progress >= 100) {
                    finishSearch(tempId, limitVal);
                }
            }, 300);
        }

        function stopActiveSearch() {
            if(activeSidebarSearchId) stopSearch(activeSidebarSearchId);
        }

        function stopSearch(id) {
            if(searchIntervals[id]) {
                clearInterval(searchIntervals[id]);
                delete searchIntervals[id];
            }

            const item = MOCK_HISTORY.find(i => i.id === id);
            if(item && item.status === "В работе") {
                item.status = "Остановлен";
                showToast('Поиск остановлен пользователем', 'error');
                if(activeSidebarSearchId === id) {
                    resetSidebarUI();
                }
                renderHistory();
            }
        }

        function finishSearch(id, limitVal) {
            if(searchIntervals[id]) {
                clearInterval(searchIntervals[id]);
                delete searchIntervals[id];
            }

            const item = MOCK_HISTORY.find(i => i.id === id);
            if(item) {
                item.status = "Завершен";
                const baseFound = Math.floor(limitVal * 0.9);
                item.found = Math.max(1, baseFound + Math.floor(Math.random() * (limitVal * 0.2)));
            }

            if(activeSidebarSearchId === id) {
                resetSidebarUI();
            }

            showToast(`Поиск завершен. Найдено ${item.found}`, 'success');
            document.getElementById('badge-new').classList.remove('hidden');
            renderHistory();
            // Optional: Auto load results not annoying user
            // loadResults(item); 
        }

        function resetSidebarUI() {
            document.getElementById('progress-panel').classList.add('hidden');
            document.getElementById('btn-search').classList.remove('hidden');
            activeSidebarSearchId = null;
        }

        function detectType(name) {
            const n = name.toLowerCase();
            if(n.includes("бумаг")) return "paper";
            if(n.includes("комп") || n.includes("моноблок")) return "pc";
            return "generic";
        }

        // --- HISTORY TABLE & PAGINATION ---
        function updateHistoryFilter(key, value) {
            activeHistoryFilters[key] = value;
            currentHistoryPage = 1; // Reset to first page on filter change
            renderHistory();
        }

        function changeHistoryPage(delta) {
            currentHistoryPage += delta;
            renderHistory();
        }

        function refreshHistory() {
            renderHistory();
            showToast('История обновлена', 'info');
        }

        function renderHistory() {
            const tbody = document.getElementById('history-body');
            tbody.innerHTML = '';
            
            // 1. Filter Data
            let filteredData = MOCK_HISTORY.filter(item => {
                const matchName = item.name.toLowerCase().includes(activeHistoryFilters.name.toLowerCase());
                const matchStatus = activeHistoryFilters.status === '' || item.status === activeHistoryFilters.status;
                const matchDate = activeHistoryFilters.date === '' || item.date === activeHistoryFilters.date;
                return matchName && matchStatus && matchDate;
            });

            // 2. Paginate Data
            const total = filteredData.length;
            const totalPages = Math.ceil(total / historyRowsPerPage);
            
            // Bound checking
            if(currentHistoryPage < 1) currentHistoryPage = 1;
            if(currentHistoryPage > totalPages && totalPages > 0) currentHistoryPage = totalPages;
            
            const start = (currentHistoryPage - 1) * historyRowsPerPage;
            const end = start + historyRowsPerPage;
            const pageData = filteredData.slice(start, end);

            // 3. Render Rows
            pageData.forEach(item => {
                const tr = document.createElement('tr');
                tr.className = 'clickable-row border-b border-gray-50 group';
                tr.onclick = (e) => {
                    if(['BUTTON', 'I', 'SELECT'].includes(e.target.tagName)) return;
                    if(item.status === 'Завершен') loadResults(item);
                };

                let statusHtml = '';
                let actionHtml = '';

                if(item.status === 'В работе') {
                    statusHtml = `<span class="bg-blue-100 text-blue-700 text-xs px-2 py-1 rounded-full font-bold animate-pulse">В работе</span>`;
                    actionHtml = `<button onclick="stopSearch(${item.id}); event.stopPropagation()" class="text-white bg-red-500 hover:bg-red-600 text-xs px-3 py-1 rounded shadow transition">Остановить</button>`;
                } else if (item.status === 'Завершен') {
                    statusHtml = `<span class="bg-green-100 text-green-700 text-xs px-2 py-1 rounded-full font-bold">Завершен</span>`;
                    actionHtml = `<button class="text-gray-400 hover:text-blue-600"><i class="fas fa-chevron-right"></i></button>`;
                } else {
                    statusHtml = `<span class="bg-gray-100 text-gray-500 text-xs px-2 py-1 rounded-full font-bold">Остановлен</span>`;
                    actionHtml = `<span class="text-gray-300">-</span>`;
                }

                tr.innerHTML = `
                    <td class="p-3 text-gray-500 text-xs">${item.date}</td>
                    <td class="p-3 font-medium text-gray-900 group-hover:text-blue-600 transition-colors">${item.name}</td>
                    <td class="p-3 text-xs text-gray-500">${item.ktru}</td>
                    <td class="p-3">${statusHtml}</td>
                    <td class="p-3 text-center">${item.found}</td>
                    <td class="p-3 font-mono text-sm">${item.avg ? item.avg.toFixed(2) + ' ₽' : '-'}</td>
                    <td class="p-3 text-center text-xs">${actionHtml}</td>
                `;
                tbody.appendChild(tr);
            });

            // 4. Update Controls
            document.getElementById('hist-pg-start').innerText = total > 0 ? start + 1 : 0;
            document.getElementById('hist-pg-end').innerText = Math.min(end, total);
            document.getElementById('hist-pg-total').innerText = total;
            document.getElementById('hist-pg-current').innerText = currentHistoryPage;
            
            document.getElementById('hist-btn-prev').disabled = currentHistoryPage <= 1;
            document.getElementById('hist-btn-next').disabled = currentHistoryPage >= totalPages || total === 0;
        }

        // --- RESULTS LOGIC ---
        function loadResults(historyItem) {
            const count = historyItem.found;
            const scenario = MOCK_SCENARIOS[historyItem.type] || MOCK_SCENARIOS.generic;
            currentContracts = [];
            selectedContractIds.clear();

            for(let i=0; i<count; i++) {
                const year = 2023 + Math.floor(Math.random() * 4);
                let score = Math.floor(60 + Math.random()*40);
                let mfr = scenario.mfrs[0];
                
                currentContracts.push({
                    id: 2700000000 + i + Math.floor(Math.random()*9000),
                    date: `${year}-05-20`,
                    price: scenario.basePrice * (0.8 + Math.random() * 0.4),
                    type: score > 90 ? "Идентичный" : "Однородный",
                    manufacturer: mfr,
                    score: score,
                    is2025: year >= 2025,
                    targetMfr: historyItem.targetMfr,
                    specs: scenario.specs.map(s => ({name: s.name, target: s.target, actual: s.target, match: true}))
                });
            }
            
            currentContracts.sort((a,b) => b.score - a.score);
            currentContracts.slice(0, 3).forEach(c => selectedContractIds.add(c.id));

            document.getElementById('res-title').innerText = historyItem.name;
            document.getElementById('res-meta').innerText = `Найдено: ${count} | ${historyItem.ktru}`;
            
            document.getElementById('filter-id').value = '';
            document.getElementById('filter-score').value = '';
            
            filteredContracts = [...currentContracts];
            currentPage = 1;
            applyAllFilters();
            switchTab('results');
            if(window.innerWidth < 1024) document.getElementById('sidebar').classList.add('translate-x-full');
        }

        // --- UI HELPERS ---
        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(`tab-${tab}`).classList.add('active');
            document.getElementById('view-history').classList.toggle('hidden', tab !== 'history');
            document.getElementById('view-results').classList.toggle('hidden', tab !== 'results');
            
            const footer = document.getElementById('results-footer');
            if(tab === 'results') footer.classList.remove('translate-y-full'); else footer.classList.add('translate-y-full');
        }

        function toggleSidebar() { document.getElementById('sidebar').classList.toggle('translate-x-full'); }
        
        function applyAllFilters() {
            const idVal = document.getElementById('filter-id').value.toLowerCase();
            const typeVal = document.getElementById('filter-type').value;
            const scoreVal = parseInt(document.getElementById('filter-score').value) || 0;
            
            filteredContracts = currentContracts.filter(c => {
                return c.id.toString().includes(idVal) && 
                       (typeVal === "" || c.type === typeVal) && 
                       (c.score >= scoreVal);
            });
            renderResultsTable();
        }

        function renderResultsTable() {
            const tbody = document.getElementById('results-body');
            tbody.innerHTML = '';
            
            filteredContracts.sort((a,b) => (selectedContractIds.has(b.id) - selectedContractIds.has(a.id)) || b.score - a.score);
            
            const start = (currentPage - 1) * rowsPerPage;
            const end = start + rowsPerPage;
            const pageData = filteredContracts.slice(start, end);
            
            document.getElementById('pg-start').innerText = filteredContracts.length ? start + 1 : 0;
            document.getElementById('pg-end').innerText = Math.min(end, filteredContracts.length);
            document.getElementById('pg-total').innerText = filteredContracts.length;
            document.getElementById('pg-current').innerText = currentPage;
            document.getElementById('btn-prev').disabled = currentPage === 1;
            document.getElementById('btn-next').disabled = end >= filteredContracts.length;

            pageData.forEach(c => {
                const isSel = selectedContractIds.has(c.id);
                const tr = document.createElement('tr');
                tr.className = isSel ? 'bg-blue-50 border-l-4 border-blue-500' : 'hover:bg-gray-50 border-l-4 border-transparent';
                
                let mfrHtml = `<span>${c.manufacturer}</span>`;
                if(c.is2025 && c.targetMfr && !c.manufacturer.toLowerCase().includes(c.targetMfr.toLowerCase())) {
                     mfrHtml += ` <i class="fas fa-exclamation-triangle text-red-500 ml-1"></i>`;
                }

                tr.innerHTML = `
                    <td class="p-3 text-center"><input type="checkbox" ${isSel ? 'checked' : ''} onchange="toggleSelect(${c.id})"></td>
                    <td class="p-3 text-blue-600 font-mono text-xs cursor-pointer hover:underline">${c.id}</td>
                    <td class="p-3 text-sm">${c.date.substring(0,4)}</td>
                    <td class="p-3 font-bold text-sm">${c.price.toLocaleString('ru-RU')} ₽</td>
                    <td class="p-3 text-xs font-bold uppercase text-gray-500">${c.type}</td>
                    <td class="p-3 text-xs">${mfrHtml}</td>
                    <td class="p-3 text-xs font-bold">${c.score}%</td>
                    <td class="p-3 text-center"><button onclick="openComparison(${c.id})" class="text-gray-400 hover:text-blue-600 p-2"><i class="fas fa-eye"></i></button></td>
                `;
                tbody.appendChild(tr);
            });
            calcNMC();
        }

        function toggleSelect(id) {
            selectedContractIds.has(id) ? selectedContractIds.delete(id) : selectedContractIds.add(id);
            renderResultsTable();
        }

        function calcNMC() {
            let sum=0, count=0;
            currentContracts.forEach(c => { if(selectedContractIds.has(c.id)) { sum+=c.price; count++; } });
            document.getElementById('nmc-value').innerText = (count ? sum/count : 0).toLocaleString('ru-RU', {style:'currency', currency:'RUB'});
            const cnt = document.getElementById('selected-count');
            cnt.innerText = count;
            cnt.className = count === 3 ? "font-bold text-green-600" : "font-bold text-red-500";
        }
        
        function changePage(d) { currentPage += d; renderResultsTable(); }
        function openComparison(id) { document.getElementById('comparison-modal').classList.add('open'); }
        function closeModal() { document.getElementById('comparison-modal').classList.remove('open'); }
        function showToast(msg, type) { 
            const el = document.createElement('div'); el.className = `toast border-${type==='success'?'green':type==='error'?'red':'blue'}-500`; 
            el.innerHTML = `<span>${msg}</span>`; document.getElementById('notification-area').appendChild(el);
            setTimeout(() => el.classList.add('show'), 10); setTimeout(() => el.remove(), 3000); 
        }
        function exportReport() { showToast('Отчет скачан', 'success'); }
