class PSAPredictorApp {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        const form = document.getElementById('predictionForm');
        const player1Input = document.getElementById('player1');
        const player2Input = document.getElementById('player2');

        form.addEventListener('submit', (e) => this.handlePrediction(e));

        player1Input.addEventListener('input', (e) => this.handlePlayerSearch(e, 'suggestions1'));
        player2Input.addEventListener('input', (e) => this.handlePlayerSearch(e, 'suggestions2'));

        // 点击其他地方关闭建议框
        document.addEventListener('click', (e) => {
            if (!e.target.matches('input[type="text"]')) {
                this.hideAllSuggestions();
            }
        });
    }

    async handlePlayerSearch(event, suggestionsId) {
        const query = event.target.value.trim();
        const suggestions = document.getElementById(suggestionsId);

        if (query.length < 2) {
            suggestions.style.display = 'none';
            return;
        }

        try {
            const response = await fetch(`/search_players?q=${encodeURIComponent(query)}`);
            const players = await response.json();

            this.showSuggestions(suggestions, players, event.target);
        } catch (error) {
            console.error('搜索选手错误:', error);
            suggestions.style.display = 'none';
        }
    }

    showSuggestions(suggestions, players, input) {
        if (players.length === 0) {
            suggestions.style.display = 'none';
            return;
        }

        suggestions.innerHTML = '';
        players.forEach(player => {
            const div = document.createElement('div');
            div.className = 'suggestion-item';
            div.textContent = player.name;
            div.addEventListener('click', () => {
                input.value = player.name;
                suggestions.style.display = 'none';
            });
            suggestions.appendChild(div);
        });

        suggestions.style.display = 'block';
    }

    hideAllSuggestions() {
        document.querySelectorAll('.suggestions').forEach(suggestions => {
            suggestions.style.display = 'none';
        });
    }

    async handlePrediction(event) {
        event.preventDefault();

        const player1 = document.getElementById('player1').value.trim();
        const player2 = document.getElementById('player2').value.trim();

        if (!player1 || !player2) {
            this.showError('请输入两名选手的名字');
            return;
        }

        if (player1.toLowerCase() === player2.toLowerCase()) {
            this.showError('请选择不同的选手');
            return;
        }

        this.showLoading();
        this.hideResult();
        this.hideError();

        try {
            const formData = new FormData();
            formData.append('player1', player1);
            formData.append('player2', player2);

            const response = await fetch('/predict', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || '预测失败');
            }

            this.showResult(data);
        } catch (error) {
            this.showError(error.message);
        } finally {
            this.hideLoading();
        }
    }

    showLoading() {
        document.getElementById('loading').classList.remove('hidden');
        document.getElementById('predictBtn').disabled = true;
    }

    hideLoading() {
        document.getElementById('loading').classList.add('hidden');
        document.getElementById('predictBtn').disabled = false;
    }

    showResult(data) {
        const resultDiv = document.getElementById('result');

        let resultHTML = `
            <div class="prediction-header">
                <div class="matchup">${data.player1} vs ${data.player2}</div>
                <div class="winner">预测获胜者: ${data.predicted_winner}</div>
                <div class="confidence">置信度: ${data.confidence}%</div>
            </div>

            <div class="probabilities">
                <div class="probability">
                    <div class="name">${data.player1}</div>
                    <div class="percentage">${data.player1_win_probability}%</div>
                    <div class="label">获胜概率</div>
                </div>
                <div class="probability">
                    <div class="name">${data.player2}</div>
                    <div class="percentage">${data.player2_win_probability}%</div>
                    <div class="label">获胜概率</div>
                </div>
            </div>
        `;

        if (data.analysis) {
            resultHTML += `
                <div class="analysis">
                    <strong>分析:</strong> ${data.analysis}
                </div>
            `;
        }

        resultDiv.innerHTML = resultHTML;
        resultDiv.classList.remove('hidden');
    }

    showError(message) {
        const errorDiv = document.getElementById('error');
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
    }

    hideError() {
        document.getElementById('error').classList.add('hidden');
    }

    hideResult() {
        document.getElementById('result').classList.add('hidden');
    }
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    new PSAPredictorApp();
});