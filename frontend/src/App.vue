<template>
  <div class="app-layout">
    <GlobalNetworkStatus />
    <ServerMonitor />

    <nav class="sidebar">
      <div class="logo">🕷️</div>

      <div class="nav-item" :class="{ active: currentModule === 'crawler' }" @click="currentModule = 'crawler'">
        <span class="icon">🕸️</span><span class="text">Viper 爬虫</span>
      </div>
      <div class="nav-item" :class="{ active: currentModule === 'alchemy' }" @click="currentModule = 'alchemy'">
        <span class="icon">⚗️</span><span class="text">Alchemy 炼金</span>
      </div>
      <div class="nav-item" :class="{ active: currentModule === 'proxy' }" @click="currentModule = 'proxy'">
        <span class="icon">🌐</span><span class="text">猎手 IP 池</span>
      </div>
      <div class="nav-item" :class="{ active: currentModule === 'nodes' }" @click="currentModule = 'nodes'">
        <span class="icon">🛰️</span><span class="text">节点猎手</span>
      </div>
      <div class="nav-item" :class="{ active: currentModule === 'cyberrange' }" @click="currentModule = 'cyberrange'">
        <span class="icon">🛡️</span><span class="text">Cyber Range</span>
      </div>
      <div class="nav-item" :class="{ active: currentModule === 'eagle' }" @click="currentModule = 'eagle'">
        <span class="icon">👁️</span><span class="text">Eagle Eye</span>
      </div>
      <div class="nav-item" :class="{ active: currentModule === 'refinery' }" @click="currentModule = 'refinery'">
        <span class="icon">🏭</span><span class="text">Data Refinery</span>
      </div>
      <div class="nav-item" :class="{ active: currentModule === 'app_gen' }" @click="currentModule = 'app_gen'">
        <span class="icon">📱</span><span class="text">App 创世</span>
      </div>
      <div class="nav-item" :class="{ active: currentModule === 'game_gen' }" @click="currentModule = 'game_gen'">
        <span class="icon">🎮</span><span class="text">Game 创世</span>
      </div>
    </nav>

    <main class="content-area">
      <Suspense>
        <template #default>
          <KeepAlive :max="3">
            <component :is="currentComponent" :key="currentModule" />
          </KeepAlive>
        </template>

        <template #fallback>
          <div class="loading-placeholder">
            <div class="spinner"></div>
            <p class="loading-text">正在加载模块...</p>
          </div>
        </template>
      </Suspense>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, defineAsyncComponent } from 'vue';
import GlobalNetworkStatus from './components/GlobalNetworkStatus.vue';
import ServerMonitor from './components/ServerMonitor.vue';

const ViperCrawler = defineAsyncComponent(() => import('./components/ViperCrawler/ViperCrawler.vue'));
const AlchemyStudio = defineAsyncComponent(() => import('./components/AlchemyStudio/AlchemyStudio.vue'));
const ProxyStation = defineAsyncComponent(() => import('./components/ProxyStation/ProxyStation.vue'));
const NodeHunter = defineAsyncComponent(() => import('./components/NodeHunter/NodeHunter.vue'));
const CyberRange = defineAsyncComponent(() => import('./components/CyberRange/CyberRange.vue'));
const EagleEye = defineAsyncComponent(() => import('./components/EagleEye/EagleEye.vue'));
const DataRefinery = defineAsyncComponent(() => import('./components/DataRefinery/DataRefinery.vue'));
const AppGenerator = defineAsyncComponent(() => import('./components/AppGenerator/AppGenerator.vue'));
const GameGenerator = defineAsyncComponent(() => import('./components/GameGenerator/GameGenerator.vue'));

const currentModule = ref('crawler');

const currentComponent = computed(() => {
  switch (currentModule.value) {
    case 'crawler': return ViperCrawler;
    case 'alchemy': return AlchemyStudio;
    case 'proxy': return ProxyStation;
    case 'nodes': return NodeHunter;
    case 'cyberrange': return CyberRange;
    case 'eagle': return EagleEye;
    case 'refinery': return DataRefinery;
    case 'app_gen': return AppGenerator;
    case 'game_gen': return GameGenerator;
    default: return ViperCrawler;
  }
});
</script>

<style>
/* 全局重置 */
body, html {
  margin: 0;
  padding: 0;
  min-height: 100vh;
  background: linear-gradient(135deg, #1e2024 0%, #121212 100%);
  color: #e0e0e0;
  /* 移除 overflow: hidden，允许手机端内容滚动 */
  overflow-x: hidden; 
}

/* 布局容器 */
.app-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
}

/* --- 桌面端侧边栏默认样式 --- */
.sidebar {
  width: 70px;
  position: sticky;
  top: 0;
  height: 100vh;
  background: rgba(25, 25, 25, 0.95);
  backdrop-filter: blur(10px);
  border-right: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 20px;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1000;
  flex-shrink: 0;
  /* 隐藏滚动条 */
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar::-webkit-scrollbar { display: none; }

.sidebar:hover {
  width: 180px;
}

/* --- 内容区域 --- */
.content-area {
  flex: 1;
  padding: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto; /* 让内容区域独立滚动 */
  overflow-x: hidden;
  position: relative;
  scroll-behavior: smooth;
}

/* --- Logo & 导航项 --- */
.logo {
  font-size: 28px;
  margin-bottom: 30px;
  cursor: default;
  flex-shrink: 0;
}

.nav-item {
  width: 100%;
  padding: 12px 0;
  display: flex;
  align-items: center;
  cursor: pointer;
  color: #888;
  transition: all 0.2s;
  box-sizing: border-box;
  border-left: 3px solid transparent;
  white-space: nowrap; /* 防止文字换行 */
}

.nav-item:hover {
  background-color: rgba(255, 255, 255, 0.05);
  color: #fff;
}

.nav-item.active {
  background: rgba(66, 185, 131, 0.1);
  color: #42b983;
  border-left-color: #42b983;
}

.icon {
  font-size: 22px;
  width: 70px;
  text-align: center;
  flex-shrink: 0;
}

.text {
  font-size: 14px;
  font-weight: bold;
  opacity: 0;
  transition: opacity 0.2s;
  margin-left: 0;
}

.sidebar:hover .text {
  opacity: 1;
}

/* --- 🔥 核心：移动端适配 (屏幕宽度 < 768px) --- */
@media (max-width: 768px) {
  .app-layout {
    flex-direction: column; /* 改为垂直布局 */
  }

  /* 侧边栏变身为底部导航栏 */
  .sidebar {
    position: fixed;
    bottom: 0;
    top: auto;      /* 取消顶部定位 */
    width: 100vw;   /* 占满宽度 */
    height: 60px;   /* 固定高度 */
    flex-direction: row; /* 图标横向排列 */
    padding: 0;
    border-right: none;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    justify-content: flex-start; /* 允许横向滚动 */
    overflow-x: auto; /* 开启横向滚动 */
    overflow-y: hidden;
  }
  
  /* 手机端取消 hover 展开效果 */
  .sidebar:hover {
    width: 100vw;
  }

  /* 隐藏 Logo (太占地方) */
  .logo {
    display: none;
  }

  /* 导航项调整 */
  .nav-item {
    width: auto;     /* 宽度自适应 */
    min-width: 60px; /* 最小触摸区 */
    padding: 0 10px;
    height: 100%;
    border-left: none; /* 移除左边框指示器 */
    border-top: 3px solid transparent; /* 改为顶部指示器 */
    flex-direction: column;
    justify-content: center;
    gap: 2px;
  }
  
  /* 激活状态改为顶部边框高亮 */
  .nav-item.active {
    background: transparent;
    border-top-color: #42b983;
  }

  /* 调整图标大小 */
  .icon {
    width: auto;
    font-size: 20px;
    margin-bottom: 2px;
  }

  /* 手机端总是显示文字 (可选，或者设为 display:none 仅显示图标) */
  .text {
    opacity: 1;
    font-size: 10px;
    margin: 0;
    font-weight: normal;
  }

  /* 内容区域给底部留出空间 */
  .content-area {
    padding-bottom: 70px; /* 防止内容被底部栏遮挡 */
    height: calc(100vh - 60px);
  }
}

/* 加载动画 */
.loading-placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: #1e2024;
}
.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #333;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 15px;
}
.loading-text { color: #666; font-family: monospace; font-size: 14px; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>