<template>
    <transition name="slide-down">
      <div 
        v-if="stats"
        @click="toggleExpand"
        class="fixed top-5 z-[9990] flex items-center rounded-full border border-white/10 bg-[#1e1e20]/80 backdrop-blur-md shadow-xl select-none transition-all duration-300 cursor-pointer md:cursor-default overflow-hidden"
        :class="[
          // 位置：手机靠左，PC 避开侧边栏
          'left-4 md:left-[200px]',
          // 形状与尺寸控制
          // 手机端：折叠时是圆点 (w-10 h-10)，展开时是长条 (w-auto px-5)
          isExpanded ? 'w-auto px-5 py-2 bg-[#1e1e20]/95' : 'w-10 h-10 justify-center px-0 bg-[#1e1e20]/60',
          // PC端：强制始终为长条 (覆盖手机端的样式)
          'md:w-auto md:px-5 md:py-2 md:justify-start md:bg-[#1e1e20]/80'
        ]"
      >
        <div class="md:hidden text-amber-400 animate-pulse text-lg" v-if="!isExpanded">
          ⚡
        </div>
  
        <div 
          class="items-center gap-4 whitespace-nowrap"
          :class="isExpanded ? 'flex' : 'hidden md:flex'"
        >
          <div class="flex items-center gap-2">
            <span class="text-xs font-bold text-gray-500 font-mono">CPU</span>
            <div class="flex items-center gap-1.5">
              <div class="w-1.5 h-3 rounded-full bg-gray-700 overflow-hidden relative">
                <div 
                  class="absolute bottom-0 left-0 w-full transition-all duration-500"
                  :class="getColor(stats.cpu)"
                  :style="{ height: `${stats.cpu}%` }"
                ></div>
              </div>
              <span class="text-xs font-mono font-bold w-8 text-right" :class="getTextColor(stats.cpu)">
                {{ stats.cpu }}%
              </span>
            </div>
          </div>
  
          <div class="w-px h-3 bg-gray-700"></div>
  
          <div class="flex items-center gap-2">
            <span class="text-xs font-bold text-gray-500 font-mono">RAM</span>
            <div class="flex items-center gap-1.5">
              <span class="relative flex h-2 w-2">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" :class="getColor(stats.memory.percent)"></span>
                <span class="relative inline-flex rounded-full h-2 w-2" :class="getColor(stats.memory.percent)"></span>
              </span>
              <span class="text-xs font-mono font-bold" :class="getTextColor(stats.memory.percent)">
                {{ stats.memory.percent }}%
              </span>
              <span class="text-[10px] text-gray-600 font-mono hidden md:inline-block">
                ({{ stats.memory.used }}/{{ stats.memory.total }}G)
              </span>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </template>
  
  <script setup>
  import { ref, onMounted, onUnmounted } from 'vue';
  import axios from 'axios';
  
  const stats = ref(null);
  const isExpanded = ref(false); // 控制手机端展开状态
  let timer = null;
  
  // 点击切换展开/折叠 (仅限移动端生效)
  const toggleExpand = () => {
    if (window.innerWidth < 768) {
      isExpanded.value = !isExpanded.value;
    }
  };
  
  const getColor = (val) => {
    if (val < 50) return 'bg-emerald-500';
    if (val < 80) return 'bg-amber-500';
    return 'bg-red-500';
  };
  
  const getTextColor = (val) => {
    if (val < 50) return 'text-emerald-400';
    if (val < 80) return 'text-amber-400';
    return 'text-red-400';
  };
  
  const fetchStats = async () => {
    try {
      const { data } = await axios.get(`${import.meta.env.VITE_API_BASE_URL}/api/system/stats`);
      stats.value = data;
    } catch (e) {
      // 静默失败
    }
  };
  
  onMounted(() => {
    fetchStats();
    timer = setInterval(fetchStats, 3000);
  });
  
  onUnmounted(() => {
    if (timer) clearInterval(timer);
  });
  </script>
  
  <style scoped>
  .slide-down-enter-active, .slide-down-leave-active {
    transition: transform 0.5s ease, opacity 0.5s ease;
  }
  .slide-down-enter-from, .slide-down-leave-to {
    transform: translateY(-20px);
    opacity: 0;
  }
  </style>