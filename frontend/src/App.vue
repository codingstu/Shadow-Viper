<template>
  <div class="app-layout">
    <nav class="sidebar">
      <div class="logo">🕷️</div>

      <div class="nav-item" :class="{ active: currentModule === 'crawler' }" @click="currentModule = 'crawler'">
        <span class="icon">🕸️</span><span class="text">Viper 爬虫</span>
      </div>
      <div class="nav-item" :class="{ active: currentModule === 'alchemy' }" @click="currentModule = 'alchemy'">
        <span class="icon">⚗️</span><span class="text">Alchemy 炼金</span>
      </div>
      <div class="nav-item" :class="{ active: currentModule === 'proxy' }" @click="currentModule = 'proxy'">
        <span class="icon">🌐</span><span class="text">代理猎手池</span>
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

// 🔥 异步按需加载 (只有点击时才下载代码)
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
body,
html {
  margin: 0;
  padding: 0;
  min-height: 100vh;
  background: linear-gradient(135deg, #1e2024 0%, #121212 100%);
  color: #e0e0e0;
  overflow: hidden;
}

.app-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
}

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
}

.sidebar:hover {
  width: 180px;
}

.content-area {
  flex: 1;
  padding: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.logo {
  font-size: 28px;
  margin-bottom: 30px;
  cursor: default;
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
  white-space: nowrap;
  opacity: 0;
  transition: opacity 0.2s;
  margin-left: 0;
}

.sidebar:hover .text {
  opacity: 1;
}

/* 加载动画样式 */
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

.loading-text {
  color: #666;
  font-family: monospace;
  font-size: 14px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>