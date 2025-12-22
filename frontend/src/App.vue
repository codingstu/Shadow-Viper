<template>
  <div class="app-layout">
    <nav class="sidebar">
      <div class="logo">🕷️</div>

      <div class="nav-item" :class="{ active: currentModule === 'crawler' }" @click="currentModule = 'crawler'">
        <span class="icon">🕸️</span>
        <span class="text">Viper 爬虫</span>
      </div>

      <div class="nav-item" :class="{ active: currentModule === 'alchemy' }" @click="currentModule = 'alchemy'">
        <span class="icon">⚗️</span>
        <span class="text">Alchemy 炼金</span>
      </div>

      <div class="nav-item" :class="{ active: currentModule === 'proxy' }" @click="currentModule = 'proxy'">
        <span class="icon">🌐</span>
        <span class="text">猎手 IP 池</span>
      </div>
      <div 
        class="nav-item" 
        :class="{ active: currentModule === 'nodes' }" 
        @click="currentModule = 'nodes'"
      >
        <span class="icon">🛰️</span>
        <span class="text">Shadow Matrix</span> 
      </div>

    </nav>

    <main class="content-area">
      <KeepAlive>
        <Transition name="fade" mode="out-in">
          <component :is="currentComponent" :key="currentModule" />
        </Transition>
      </KeepAlive>
    </main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import ViperCrawler from './components/ViperCrawler.vue';
import AlchemyStudio from './components/AlchemyStudio.vue';
import ProxyStation from './components/ProxyStation.vue';
import NodeHunter from './components/NodeHunter.vue';

const currentModule = ref('crawler');

const currentComponent = computed(() => {
  switch (currentModule.value) {
    case 'crawler': return ViperCrawler;
    case 'alchemy': return AlchemyStudio;
    case 'proxy': return ProxyStation;
    case 'nodes': return NodeHunter; // 🔥 新增
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
  /* 防止出现双滚动条 */
}

.app-layout {
  display: flex;
  height: 100vh;
  /* 强制占满全屏高度 */
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

/* 🔥 关键：消除大边距，让内容占满 */
.content-area {
  flex: 1;
  padding: 10px 15px;
  /* 从 30px 缩小到 10px */
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* 内部容器自己负责滚动 */
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

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>