<template>
  <!-- 🔥 核心修复：使用计算属性来代理 v-model -->
  <n-modal v-model:show="showProxy" preset="card" style="width: 90%; max-width: 1200px;" title="👁️‍🗨️ 访客日志">
    <n-data-table
      :columns="columns"
      :data="logs"
      :pagination="pagination"
      :loading="loading"
      @update:page="handlePageChange"
      remote
      flex-height
      style="height: 60vh"
    />
  </n-modal>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import { NModal, NDataTable, NTag } from 'naive-ui';
import axios from 'axios';

const props = defineProps({
  show: Boolean,
});

const emit = defineEmits(['update:show']);

// 🔥 核心修复：创建一个可读写的计算属性
const showProxy = computed({
  get: () => props.show,
  set: (value) => emit('update:show', value),
});

const loading = ref(false);
const logs = ref([]);
const pagination = ref({
  page: 1,
  pageSize: 15,
  itemCount: 0,
});

const columns = [
  { title: 'IP 地址', key: 'ip_address', width: 150 },
  { title: '国家', key: 'country', width: 120 },
  { title: '地区', key: 'region', width: 120 },
  { title: '城市', key: 'city', width: 120 },
  { title: '访问时间', key: 'timestamp', width: 180 },
  { title: '设备信息', key: 'user_agent' },
];

const fetchData = async (page = 1) => {
  if (loading.value) return;
  loading.value = true;
  try {
    const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL}/api/visitors`, {
      params: {
        page: page,
        limit: pagination.value.pageSize,
      },
    });
    logs.value = response.data.data;
    pagination.value.itemCount = response.data.total;
    pagination.value.page = page;
  } catch (error) {
    console.error("Failed to fetch visitor logs:", error);
  } finally {
    loading.value = false;
  }
};

const handlePageChange = (page) => {
  fetchData(page);
};

watch(() => props.show, (newVal) => {
  if (newVal) {
    fetchData(1);
  }
});
</script>
