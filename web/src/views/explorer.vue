<template>
  <div class="h-100vh w-100vw">
    <vue-finder id='explorer' class="h-100vh w-full" :request="request" max-height="100%" theme="dark"
      :features="features" locale="zhCN" persist></vue-finder>
  </div>
</template>

<script setup>

import { useAuthStore } from '@/store/auth'

import { FEATURES, FEATURE_ALL_NAMES } from 'vuefinder/dist/features.js';

const features = [
  ...FEATURE_ALL_NAMES,
  // Or remove the line above, specify the features want to include
  // Like...
  //FEATURES.LANGUAGE,
]

const authStore = useAuthStore() // 使用 useAuthStore 获取 authStore 实例
const authToken = authStore.token // 获取 token
const username = authStore.username // 获取 username

const request = {
  // baseUrl: "cloud_api/",
  baseUrl: `cloud_api/cloud/${username}`,
  // baseUrl: `http://127.0.0.1:8005/cloud/${username}`,
  // baseUrl: `http://127.0.0.1:8005`,
  headers: {
    "X-ADDITIONAL-HEADER": 'yes',
    "Authorization": `Bearer ${authToken}` // 使用 token
  },
  params: { additionalParam1: 'yes' },
  body: { additionalBody1: ['yes'] },

  transformRequest: req => {
    if (req.method === 'get') {
      req.params.vf = "1"
    }
    return req;
  },

  xsrfHeaderName: "X-CSRF-TOKEN",
}
</script>

<style>
.dark,
.light,
.vuefinder__main__container {
  height: 100%;
}
</style>