<template>
  <div class="h-100vh w-100vw">
    <vue-finder id='explorer' class="h-100vh w-full" :request="request" max-height="100%" theme="light"
      :features="features" locale="zhCN" persist ></vue-finder>
  </div>
</template>

<script setup>
import { inject } from 'vue'

import { FEATURES, FEATURE_ALL_NAMES } from 'vuefinder/dist/features.js';

const features = [
  ...FEATURE_ALL_NAMES,
  // Or remove the line above, specify the features want to include
  // Like...
  //FEATURES.LANGUAGE,
]

const authToken = inject('authToken') // 获取提供的 token

const request = {
  baseUrl: "http://127.0.0.1:8005",
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