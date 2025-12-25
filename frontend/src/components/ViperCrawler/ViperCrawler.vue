<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-global-style />
    <div class="h-screen w-full bg-[#121212] text-gray-200 flex flex-col p-2 md:p-4 overflow-hidden font-mono">
      
      <div class="shrink-0 text-center mb-4 md:mb-6">
        <h1 class="text-2xl md:text-3xl font-bold text-primary bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-cyan-500">
          🕷️ Viper 爬虫控制台
        </h1>
        <p class="text-xs md:text-sm text-gray-500 mt-2">
          多引擎驱动：极速 API · 智能 HTML 解析 · 深度流媒体嗅探
        </p>
      </div>

      <div class="shrink-0 mb-4 max-w-6xl mx-auto w-full">
        <div class="flex flex-col md:flex-row gap-3">
          
          <n-input 
            v-model:value="targetUrl" 
            type="text" 
            placeholder="输入网址 (支持 MissAV, Reddit, 知乎, B站等)" 
            :disabled="isCrawling" 
            size="large"
            class="flex-1"
            clearable
          >
            <template #prefix>🔗</template>
          </n-input>

          <div class="flex gap-2">
            <n-select 
              v-model:value="crawlMode" 
              :options="crawlModeOptions" 
              :disabled="isCrawling" 
              size="large"
              class="w-32 md:w-40" 
            />
            
            <n-select 
              v-model:value="networkType" 
              :options="networkOptions" 
              :disabled="isCrawling" 
              size="large"
              class="w-32 md:w-40" 
            />
          </div>

          <n-button 
            type="primary" 
            size="large" 
            @click="startCrawl" 
            :disabled="isCrawling || !targetUrl"
            :loading="isCrawling"
            class="w-full md:w-auto px-8 font-bold shadow-[0_0_15px_rgba(66,185,131,0.4)]"
          >
            {{ isCrawling ? '停止运行' : '开始爬取' }}
          </n-button>
        </div>
      </div>

      <div class="flex flex-col lg:flex-row gap-4 flex-1 min-h-0 overflow-hidden">
        
        <div class="w-full lg:w-1/3 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden">
          <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
            <div class="flex items-center gap-2">
              <span class="font-bold text-gray-300">📟 系统日志</span>
              <div 
                class="flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-xs transition-all duration-300"
                :class="isCrawling || isAnalyzing 
                  ? 'bg-emerald-900/30 border-emerald-500/50 text-emerald-400' 
                  : 'bg-gray-800 border-gray-700 text-gray-500'"
              >
                <span class="w-2 h-2 rounded-full transition-colors duration-300" 
                  :class="isCrawling || isAnalyzing ? 'bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]' : 'bg-gray-500'">
                </span>
                {{ isCrawling ? '爬取中...' : (isAnalyzing ? '分析中...' : '任务空闲') }}
              </div>
            </div>
          </div>

          <div class="flex-1 overflow-y-auto p-4 bg-[#1a1a1a] font-mono text-xs md:text-sm space-y-1 custom-scrollbar" ref="logWindowRef">
            <div v-for="(log, idx) in logs" :key="idx" class="break-all leading-relaxed">
              <span class="text-gray-500 mr-2">[{{ log.time }}]</span>
              <span :class="{
                'text-blue-400': log.type === 'info',
                'text-emerald-400': log.type === 'success',
                'text-red-400': log.type === 'error'
              }">> {{ log.text }}</span>
            </div>
            <div v-if="logs.length === 0" class="text-gray-600 text-center mt-10 italic">
              _等待指令输入...
            </div>
          </div>
        </div>

        <div class="w-full lg:w-2/3 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden">
          <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0 flex-wrap gap-2">
            <span class="font-bold text-gray-300">
              {{ crawlMode === 'text' ? '📊 文本视图' : '🎬 媒体流视图' }}
            </span>
            
            <div class="flex items-center gap-2">
              <n-tag v-if="previewData.length" type="info" size="small" round>
                {{ previewData.length }} 条数据
              </n-tag>
              
              <n-button 
                v-if="previewData.length > 0 && crawlMode === 'text'" 
                @click="startBattle" 
                size="tiny"
                type="warning"
                ghost
                :disabled="isAnalyzing"
              >
                {{ isAnalyzing ? '⚔️ 分析中...' : '⚔️ 开启战场' }}
              </n-button>

              <n-button 
                v-if="previewData.length > 0" 
                @click="clearPreview" 
                size="tiny" 
                type="error" 
                secondary
              >
                清除
              </n-button>
            </div>
          </div>

          <div class="flex-1 bg-[#161616] relative overflow-hidden">
            
            <div v-if="showBattlefield" class="absolute inset-0 flex flex-col bg-black z-20">
              <div class="h-10 bg-white/10 flex justify-between items-center px-4 shrink-0 backdrop-blur-sm">
                <span class="text-red-500 font-bold">{{ teamRed.name || '红方' }}: {{ teamRed.warriors.filter(w => w.hp > 0).length }}</span>
                <span class="text-gray-400 italic font-serif">VS</span>
                <span class="text-blue-500 font-bold">{{ teamBlue.name || '蓝方' }}: {{ teamBlue.warriors.filter(w => w.hp > 0).length }}</span>
                <button @click="closeBattle" class="text-white hover:text-red-500 text-xl">✕</button>
              </div>
              <div class="flex-1 relative w-full h-full">
                <canvas ref="canvasRef" class="w-full h-full block"></canvas>
                <div v-if="winner" class="absolute inset-0 bg-black/80 flex flex-col justify-center items-center text-amber-400 z-30 animate-in fade-in duration-500">
                  <h2 class="text-4xl font-bold mb-4">🏆 {{ winner.name }} 获胜!</h2>
                  <p class="text-gray-300 mb-6">MVP: {{ mvp.id }} (伤害: {{ mvp.damageDealt }})</p>
                  <n-button type="primary" @click="resetBattle">再战一场</n-button>
                </div>
              </div>
            </div>

            <div v-else-if="crawlMode === 'text'" class="h-full w-full overflow-auto custom-scrollbar">
              <n-table v-if="previewData.length > 0" size="small" :bordered="false" :single-line="false" class="bg-transparent text-gray-300">
                <thead>
                  <tr>
                    <th class="bg-[#252529] text-emerald-500 w-24">类型</th>
                    <th class="bg-[#252529] text-emerald-500">内容</th>
                    <th class="bg-[#252529] text-emerald-500 w-32">备注</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, idx) in previewData" :key="idx" class="hover:bg-white/5 transition-colors">
                    <td><n-tag size="small" :bordered="false" color="{ color: '#333', textColor: '#aaa' }">{{ row['类型'] }}</n-tag></td>
                    <td class="break-all min-w-[200px]">{{ row['内容'] }}</td>
                    <td class="text-gray-500 text-xs">{{ row['备注'] }}</td>
                  </tr>
                </tbody>
              </n-table>
              <div v-else class="flex flex-col items-center justify-center h-full text-gray-600">
                <span class="text-6xl mb-4 opacity-20">📄</span>
                <p>{{ isCrawling ? '正在解析数据...' : '暂无文本数据' }}</p>
              </div>
            </div>

            <div v-else class="h-full w-full overflow-y-auto p-4 custom-scrollbar">
              <div v-if="mediaItems.length > 0" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                <div v-for="(item, idx) in mediaItems" :key="idx" 
                     class="bg-[#252525] rounded-lg overflow-hidden border border-gray-700 hover:border-emerald-500/50 transition-colors flex flex-col">
                  
                  <template v-if="item.type === 'video'">
                    <div class="relative aspect-video bg-black group">
                      <video 
                        :ref="(el) => initVideoPlayer(el, item.url)" 
                        class="w-full h-full object-contain" 
                        controls
                        :poster="proxyUrl(item.cover)" 
                        playsinline
                      ></video>
                      <div class="absolute top-2 left-2 bg-emerald-500 text-black text-[10px] font-bold px-1.5 py-0.5 rounded">
                        {{ item.url.includes('.m3u8') ? 'HLS' : 'MP4' }}
                      </div>
                    </div>
                    <div class="p-3 flex gap-3">
                      <div v-if="item.cover && item.cover !== 'No Cover'" class="w-16 h-20 shrink-0 bg-black rounded overflow-hidden cursor-pointer hover:opacity-80" @click="openLink(item.cover)">
                        <img :src="proxyUrl(item.cover)" class="w-full h-full object-cover">
                      </div>
                      <div class="flex-1 min-w-0 flex flex-col">
                        <span class="text-xs font-bold text-amber-500 mb-1">VIDEO</span>
                        <h4 class="text-sm text-gray-200 line-clamp-2 leading-tight mb-2" :title="item.title">{{ item.title || 'Unknown Video' }}</h4>
                        <n-button size="tiny" secondary class="mt-auto w-full" @click="copyToClipboard(item.url)">复制地址</n-button>
                      </div>
                    </div>
                  </template>

                  <template v-else-if="item.type === 'image'">
                    <div class="p-2 bg-[#222] flex justify-center items-center cursor-pointer" @click="openLink(item.url)">
                      <img :src="proxyUrl(item.url)" class="max-h-[300px] object-contain" loading="lazy">
                    </div>
                    <div class="px-2 py-1 bg-[#252525] border-t border-gray-700 flex justify-between items-center">
                      <span class="text-xs font-bold text-blue-400">IMG</span>
                    </div>
                  </template>

                  <template v-else>
                    <div class="p-4 border-l-2 border-gray-500 bg-[#2a2a2a] h-full">
                      <span class="text-xs font-bold text-gray-400 block mb-2">{{ item.rawType }}</span>
                      <p class="text-sm text-gray-300 whitespace-pre-wrap break-all">{{ item.content }}</p>
                    </div>
                  </template>

                </div>
              </div>
              <div v-else class="flex flex-col items-center justify-center h-full text-gray-600">
                <span class="text-6xl mb-4 opacity-20">🎬</span>
                <p>{{ isCrawling ? '正在渲染数据流...' : '暂无媒体数据' }}</p>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, nextTick, computed, onUnmounted } from 'vue';
// 🔥 引入 Naive UI 组件和主题
import { 
  NConfigProvider, NGlobalStyle, NInput, NSelect, NButton, 
  NTag, NTable, darkTheme 
} from 'naive-ui';
import Hls from 'hls.js';
import axios from 'axios';

// 🔥 定义 Naive UI 的主题覆盖 (定制主色调为赛博绿)
const themeOverrides = {
  common: {
    primaryColor: '#42b983',
    primaryColorHover: '#5cd29d',
    primaryColorPressed: '#2a9163',
  },
  Input: {
    color: '#1e1e1e',
    textColor: '#fff',
    border: '1px solid #333',
  },
  Select: {
    peers: {
      InternalSelection: {
        color: '#252525',
        textColor: '#fff',
        border: '1px solid #333',
      }
    }
  }
};

// 🔥 补充 Select 的选项数据 (Naive UI 必需)
const crawlModeOptions = [
  { label: '📄 极速文本', value: 'text' },
  { label: '🎬 深度媒体', value: 'media' }
];

const networkOptions = [
  { label: '🤖 自动模式', value: 'auto' },
  { label: '🛰️ Shadow Matrix', value: 'node' },
  { label: '🌐 猎手 IP 池', value: 'proxy' },
  { label: '⚡️ 仅直连', value: 'direct' }
];

// --- 以下为原有业务逻辑，完全保持不变 ---

const targetUrl = ref('');
const crawlMode = ref('text');
const networkType = ref('auto');
const logs = ref([]);
const isCrawling = ref(false);
const logWindowRef = ref(null);
const previewData = ref([]);

const showBattlefield = ref(false);
const isAnalyzing = ref(false);
const canvasRef = ref(null);
const teamRed = ref({ name: '红方', warriors: [] });
const teamBlue = ref({ name: '蓝方', warriors: [] });
const winner = ref(null);
const mvp = ref({ id: '', damageDealt: 0 });
let animationFrameId = null;

const getCurrentTime = () => new Date().toLocaleTimeString();

const proxyUrl = (url) => {
  if (!url || url === 'No Cover') return '';
  return `${import.meta.env.VITE_API_BASE_URL}/api/proxy?url=${encodeURIComponent(url)}`;
};

const initVideoPlayer = (videoEl, originalUrl) => {
  if (!videoEl || !originalUrl || videoEl.dataset.initialized === 'true') return;
  const proxied = proxyUrl(originalUrl);
  if (originalUrl.includes('.m3u8')) {
    if (Hls.isSupported()) {
      const hls = new Hls();
      hls.loadSource(proxied);
      hls.attachMedia(videoEl);
    } else if (videoEl.canPlayType('application/vnd.apple.mpegurl')) {
      videoEl.src = proxied;
    }
  } else {
    videoEl.src = proxied;
  }
  videoEl.dataset.initialized = 'true';
};

const mediaItems = computed(() => {
  if (crawlMode.value !== 'media') return [];
  return previewData.value.map(row => {
    const type = row['类型'] || '';
    if (type === '视频') return { type: 'video', url: row['内容'], cover: row['备注'], title: row['标题'] };
    if (type === '图片') return { type: 'image', url: row['内容'] };
    if (!['标题', 'Meta', 'Title', 'Video-Title', 'API-Title'].includes(type) && row['内容']?.length > 2) {
      return { type: 'text', content: row['内容'], rawType: type };
    }
    return null;
  }).filter(Boolean);
});

const startCrawl = async () => {
  let finalUrl = targetUrl.value.trim();
  if (!finalUrl) return;
  if (!finalUrl.startsWith('http')) finalUrl = 'https://' + finalUrl;

  isCrawling.value = true;
  logs.value = [];
  clearPreview();
  showBattlefield.value = false;

  logs.value.push({ time: getCurrentTime(), text: `🚀 启动 Viper 引擎 [${crawlMode.value}] [Net: ${networkType.value}]...`, type: 'info' });

  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/crawl`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        url: finalUrl, 
        mode: crawlMode.value, 
        network_type: networkType.value,
      })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n').filter(line => line.trim());

      for (const line of lines) {
        try {
          const data = JSON.parse(line);
          if (data.step === 'done') {
            previewData.value = data.data;
            logs.value.push({ time: getCurrentTime(), text: `✅ 任务完成，已渲染 ${data.data.length} 条数据`, type: 'success' });
          } else if (data.step === 'error') {
            logs.value.push({ time: getCurrentTime(), text: '❌ ' + data.message, type: 'error' });
          } else {
            logs.value.push({ time: getCurrentTime(), text: data.message, type: 'info' });
          }
          await nextTick();
          if (logWindowRef.value) logWindowRef.value.scrollTop = logWindowRef.value.scrollHeight;
        } catch (e) { }
      }
    }
  } catch (err) {
    logs.value.push({ time: getCurrentTime(), text: '系统错误: ' + err.message, type: 'error' });
  } finally {
    isCrawling.value = false;
  }
};

const startBattle = async () => {
  if (previewData.value.length === 0) return;
  
  const titleRow = previewData.value.find(row => row['类型'] === '标题' || row['类型'] === 'H1');
  const postTitle = titleRow ? titleRow['内容'] : 'Unknown Topic';

  isAnalyzing.value = true;
  logs.value.push({ time: getCurrentTime(), text: '⚔️ 正在分析评论区阵营...', type: 'info' });
  
  try {
    const payload = {
      post_title: postTitle,
      comments: JSON.parse(JSON.stringify(previewData.value))
    };

    const response = await axios.post(`${import.meta.env.VITE_API_BASE_URL}/api/crawl/analyze_comments`, payload);
    
    teamRed.value = response.data.team_red;
    teamBlue.value = response.data.team_blue;
    
    showBattlefield.value = true;
    logs.value.push({ time: getCurrentTime(), text: `✅ 战局生成: ${teamRed.value.name} vs ${teamBlue.value.name}`, type: 'success' });
    
    await nextTick();
    setupBattle();
    
  } catch (error) {
    logs.value.push({ time: getCurrentTime(), text: '❌ 战局分析失败: ' + (error.response?.data?.detail || error.message), type: 'error' });
  } finally {
    isAnalyzing.value = false;
  }
};

const setupBattle = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  
  const container = canvas.parentElement;
  canvas.width = container.offsetWidth;
  canvas.height = container.offsetHeight;
  
  const ctx = canvas.getContext('2d');

  teamRed.value.warriors.forEach((w, i) => {
    w.x = 50 + Math.random() * 50;
    w.y = 50 + (i * 30) % (canvas.height - 100);
    w.hp = w.armor;
    w.maxHp = w.armor;
    w.damageDealt = 0;
    w.color = '#ff4444';
  });
  
  teamBlue.value.warriors.forEach((w, i) => {
    w.x = canvas.width - 100 + Math.random() * 50;
    w.y = 50 + (i * 30) % (canvas.height - 100);
    w.hp = w.armor;
    w.maxHp = w.armor;
    w.damageDealt = 0;
    w.color = '#4488ff';
  });

  winner.value = null;
  mvp.value = { id: '', damageDealt: 0 };
  
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  animateBattle();
};

const animateBattle = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  ctx.fillStyle = '#1a1a1a';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  drawTeam(ctx, teamRed.value.warriors);
  drawTeam(ctx, teamBlue.value.warriors);

  if (!winner.value) {
    if (Math.random() < 0.1) {
        simulateRound();
    }
    animationFrameId = requestAnimationFrame(animateBattle);
  } else {
    const allWarriors = [...teamRed.value.warriors, ...teamBlue.value.warriors];
    mvp.value = allWarriors.reduce((max, w) => w.damageDealt > max.damageDealt ? w : max, { id: 'None', damageDealt: 0 });
  }
};

const drawTeam = (ctx, warriors) => {
  warriors.forEach(w => {
    if (w.hp > 0) {
      ctx.fillStyle = w.color;
      ctx.fillRect(w.x, w.y, 10, 10);
      
      const hpPercent = w.hp / w.maxHp;
      ctx.fillStyle = '#333';
      ctx.fillRect(w.x, w.y - 6, 10, 3);
      ctx.fillStyle = '#0f0';
      ctx.fillRect(w.x, w.y - 6, 10 * hpPercent, 3);
      
      ctx.fillStyle = '#aaa';
      ctx.font = '10px monospace';
      ctx.fillText(w.id.substring(0, 8), w.x, w.y + 20);
    }
  });
};

const simulateRound = () => {
  const attack = (attackers, defenders) => {
    attackers.forEach(att => {
      if (att.hp <= 0) return;
      
      const targets = defenders.filter(d => d.hp > 0);
      if (targets.length === 0) return;
      
      const target = targets[Math.floor(Math.random() * targets.length)];
      
      att.x += (target.x - att.x) * 0.05;
      
      const dmg = Math.max(1, Math.floor((att.attack + att.poison) * 0.1));
      target.hp -= dmg;
      att.damageDealt += dmg;
      
      if (Math.abs(target.x - att.x) < 20) {
          att.x -= (target.x - att.x) * 0.5;
      }
    });
  };

  attack(teamRed.value.warriors, teamBlue.value.warriors);
  attack(teamBlue.value.warriors, teamRed.value.warriors);

  const redAlive = teamRed.value.warriors.some(w => w.hp > 0);
  const blueAlive = teamBlue.value.warriors.some(w => w.hp > 0);

  if (!blueAlive && redAlive) winner.value = teamRed.value;
  else if (!redAlive && blueAlive) winner.value = teamBlue.value;
  else if (!redAlive && !blueAlive) winner.value = { name: '平局' };
};

const resetBattle = () => { setupBattle(); };
const closeBattle = () => { showBattlefield.value = false; if (animationFrameId) cancelAnimationFrame(animationFrameId); };
const clearPreview = () => { previewData.value = []; showBattlefield.value = false; };
const openLink = (url) => window.open(url, '_blank');
const copyToClipboard = (text) => { navigator.clipboard.writeText(text); alert('地址已复制'); };

onUnmounted(() => {
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
});
</script>

<style scoped>
/* 滚动条美化 (Tailwind 默认不包含滚动条样式，这里手动补充) */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #1a1a1a;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #42b983;
}
</style>