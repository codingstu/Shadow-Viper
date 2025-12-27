<template>
    <transition name="fade">
      <div 
        v-if="ipData"
        class="fixed top-5 right-5 z-[9999] flex items-center bg-[#1e1e20]/40 backdrop-blur-sm border border-white/5 shadow-lg rounded-full transition-all duration-300 ease-out group overflow-hidden select-none"
        :class="[
          isHovered || isPinned ? 'w-auto px-4 py-2 bg-[#1e1e20]/90 border-emerald-500/50 gap-3' : 'w-10 h-10 justify-center border-transparent hover:bg-[#1e1e20]/60'
        ]"
        @mouseenter="isHovered = true"
        @mouseleave="isHovered = false"
        @click="togglePin"
        title="点击可锁定/解锁展开状态"
      >
        <div class="text-xl filter drop-shadow-lg flex-shrink-0 cursor-pointer transition-transform duration-300"
             :class="isHovered || isPinned ? 'scale-110' : 'scale-100 opacity-80'">
          {{ ipData.flag }}
        </div>
  
        <div 
          class="flex flex-col items-end leading-none gap-1 whitespace-nowrap overflow-hidden transition-all duration-300"
          :style="{ maxWidth: isHovered || isPinned ? '200px' : '0', opacity: isHovered || isPinned ? 1 : 0 }"
        >
          <span class="font-bold text-gray-200 text-xs font-mono tracking-wide">
            {{ ipData.ip }}
          </span>
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-gray-400 font-medium uppercase">
              {{ ipData.country }}
            </span>
            <span v-if="isPinned" class="text-[8px] text-emerald-500 border border-emerald-500/30 px-1 rounded">PINNED</span>
          </div>
        </div>
  
        <div 
          class="relative flex h-2 w-2 flex-shrink-0 ml-1 transition-opacity duration-300"
          :class="isHovered || isPinned ? 'opacity-100' : 'opacity-0'"
        >
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
        </div>
      </div>
    </transition>
  </template>
  
  <script setup>
  import { ref, onMounted } from 'vue';
  import axios from 'axios';
  
  const ipData = ref(null);
  const isHovered = ref(false);
  const isPinned = ref(false); // 新增：是否点击锁定了展开状态
  
  function togglePin() {
    isPinned.value = !isPinned.value;
  }
  
  // 获取 IP 信息
  async function fetchGlobalIP() {
    try {
      const { data } = await axios.get('https://ipwho.is/', { timeout: 5000 });
      if (data.success) {
        ipData.value = {
          ip: data.ip,
          country: data.country,
          flag: data.flag.emoji
        };
      } else {
        ipData.value = { ip: '...', country: 'Unknown', flag: '🌐' };
      }
    } catch (error) {
      // 静默失败
    }
  }
  
  onMounted(() => {
    fetchGlobalIP();
    setInterval(fetchGlobalIP, 60000);
  });
  </script>
  
  <style scoped>
  .fade-enter-active, .fade-leave-active {
    transition: opacity 0.5s ease;
  }
  .fade-enter-from, .fade-leave-to {
    opacity: 0;
  }
  </style>